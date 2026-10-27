from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Employee, PaymentMode, SalaryAdvance, SalaryPayment
from .utils import month_end

ZERO = Decimal("0.00")


class SettlementError(Exception):
    """A bulk settlement failed. Nothing was saved."""

    def __init__(self, errors):
        super().__init__("Settlement failed")
        self.errors = errors


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _message(exc):
    detail = exc.detail
    if isinstance(detail, dict):
        detail = detail.get("message", detail)
    if isinstance(detail, list) and detail:
        detail = detail[0]
    return str(detail)


def advances_for_month(employee, start):
    total = SalaryAdvance.objects.filter(
        employee=employee, date__gte=start, date__lt=month_end(start)
    ).aggregate(t=Sum("amount"))["t"]
    return total or ZERO


def advance_error(employee, amount, adv_date, exclude_pk=None, check_active=True):
    """Return (field, message) if this advance is not allowed, otherwise None."""
    start = adv_date.replace(day=1)

    if check_active and not employee.is_active:
        return ("employee", "Cannot add an advance for an inactive employee.")

    if SalaryPayment.objects.filter(employee=employee, month=start).exists():
        return (
            None,
            "Salary for this month is already settled. Advances can't be changed.",
        )

    existing = SalaryAdvance.objects.filter(
        employee=employee, date__gte=start, date__lt=month_end(start)
    )
    if exclude_pk:
        existing = existing.exclude(pk=exclude_pk)
    total = (existing.aggregate(t=Sum("amount"))["t"] or ZERO) + amount
    if total > employee.monthly_salary:
        return (
            "amount",
            f"Total advances for {start:%B %Y} would be {total}, "
            f"which is more than the monthly salary {employee.monthly_salary}.",
        )
    return None


def pay_salary(employee, start, note="", payment_date=None, payment_mode=PaymentMode.CASH):
    """Settle one employee's salary for the month; advances are deducted."""
    if not employee.is_active:
        raise ValidationError({"message": "Cannot pay an inactive employee."})

    advance = advances_for_month(employee, start)
    net = max(employee.monthly_salary - advance, ZERO)
    try:
        with transaction.atomic():
            return SalaryPayment.objects.create(
                employee=employee,
                month=start,
                salary_amount=employee.monthly_salary,
                advance_deducted=advance,
                net_paid=net,
                payment_date=payment_date or timezone.localdate(),
                payment_mode=payment_mode,
                note=note or "",
            )
    except IntegrityError:
        raise ValidationError(
            {"message": f"Salary for {start:%B %Y} is already paid for {employee.name}."}
        )


def pay_all(start, note="", payment_date=None, payment_mode=PaymentMode.CASH):
    """Settle every active employee who is still pending for the month."""
    already_paid = SalaryPayment.objects.filter(month=start).values("employee_id")
    pending = Employee.objects.filter(is_active=True).exclude(pk__in=already_paid)
    with transaction.atomic():
        return [
            pay_salary(e, start, note, payment_date, payment_mode) for e in pending
        ]


def settle_full(employee_ids, start, payment_date, payment_mode, note=""):
    """Full settlement for the selected staff. All succeed or none are saved."""
    employees = Employee.objects.in_bulk(employee_ids)
    errors, payments = [], []
    with transaction.atomic():
        for pk in employee_ids:
            employee = employees.get(pk)
            if employee is None:
                errors.append({"employee": pk, "name": None, "message": "Employee not found."})
                continue
            try:
                payments.append(
                    pay_salary(employee, start, note, payment_date, payment_mode)
                )
            except ValidationError as exc:
                errors.append(
                    {"employee": pk, "name": employee.name, "message": _message(exc)}
                )
        if errors:
            raise SettlementError(errors)  # rolls back everything above
    return payments


def give_advances(items, start, payment_date, payment_mode, note=""):
    """Advance only: one advance per selected staff. All succeed or none are saved."""
    employees = Employee.objects.in_bulk([i["employee"] for i in items])
    errors, created = [], []
    with transaction.atomic():
        for item in items:
            pk, amount = item["employee"], item["amount"]
            employee = employees.get(pk)
            if employee is None:
                errors.append({"employee": pk, "name": None, "message": "Employee not found."})
                continue
            error = advance_error(employee, amount, payment_date)
            if error:
                errors.append({"employee": pk, "name": employee.name, "message": error[1]})
                continue
            created.append(
                SalaryAdvance.objects.create(
                    employee=employee,
                    amount=amount,
                    date=payment_date,
                    payment_mode=payment_mode,
                    note=note or "",
                )
            )
        if errors:
            raise SettlementError(errors)
    return created


def preview(kind, start, employee_ids):
    """Rows and totals for the Salary Payment modal, before 'Mark As Paid'."""
    employees = Employee.objects.in_bulk(employee_ids)
    settled = set(
        SalaryPayment.objects.filter(
            month=start, employee_id__in=employee_ids
        ).values_list("employee_id", flat=True)
    )

    rows = []
    for pk in employee_ids:
        employee = employees.get(pk)
        if employee is None:
            rows.append(
                {"employee": pk, "name": None, "can_settle": False, "reason": "Employee not found."}
            )
            continue

        advance = advances_for_month(employee, start)
        reason = None
        if not employee.is_active:
            reason = "Employee is inactive."
        elif pk in settled:
            reason = f"Salary for {start:%B %Y} is already settled."

        pending = max(employee.monthly_salary - advance, ZERO)
        row = {
            "employee": pk,
            "name": employee.name,
            "monthly_salary": employee.monthly_salary,
            "can_settle": reason is None,
            "reason": reason,
        }
        if kind == "full":
            row["advance"] = advance
            row["pending"] = pending
            row["settling"] = pending if reason is None else ZERO
        else:
            row["existing_advance"] = advance
            row["max_advance"] = pending if reason is None else ZERO
        rows.append(row)

    valid = [r for r in rows if r.get("name")]
    totals = {
        "staff_count": len(rows),
        "monthly_salary": sum((r["monthly_salary"] for r in valid), ZERO),
    }
    if kind == "full":
        totals["advance"] = sum((r["advance"] for r in valid), ZERO)
        totals["pending"] = sum((r["pending"] for r in valid), ZERO)
        totals["settling"] = sum((r["settling"] for r in valid), ZERO)
    return {"type": kind, "month": f"{start:%Y-%m}", "rows": rows, "totals": totals}