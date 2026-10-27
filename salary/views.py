import csv
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Salary
from .pagination import SalaryPagination
from .serializers import (
    AdvanceSerializer,
    BulkAdvanceSerializer,
    BulkPaySerializer,
    PayOptionsSerializer,
    SalarySerializer,
)
from .utils import get_month

ZERO = Decimal("0.00")


def advance_error(salary, amount):
    if salary.is_settled:
        return "Salary for this month is already settled. Advances can't be changed."
    left = salary.monthly_salary - salary.advance
    if amount > left:
        return f"Advance can't be more than the remaining salary ({left})."
    return None


class MessageMixin:
    label = "Record"

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response(
            {"message": f"{self.label} added successfully", "data": response.data},
            status=201,
        )

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return Response(
            {"message": f"{self.label} updated successfully", "data": response.data}
        )

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return Response({"message": f"{self.label} deleted successfully"})


class SalaryViewSet(MessageMixin, viewsets.ModelViewSet):
    serializer_class = SalarySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = SalaryPagination
    label = "Salary"

    # these work on one month (?month=YYYY-MM)
    MONTH_ACTIONS = ("list", "summary", "export")

    def get_queryset(self):
        qs = Salary.objects.all()
        params = self.request.query_params

        if self.action in self.MONTH_ACTIONS:
            qs = qs.filter(month=get_month(self.request))

        search = params.get("search")
        if search:
            cond = Q(name__icontains=search) | Q(mobile_number__icontains=search)
            try:
                amount = Decimal(search)
                if amount.is_finite():
                    cond |= Q(monthly_salary=amount)
            except InvalidOperation:
                pass
            qs = qs.filter(cond)

        status = (params.get("status") or "").lower()
        if status == "pending":
            qs = qs.filter(is_settled=False)
        elif status == "settled":
            qs = qs.filter(is_settled=True)

        return qs.order_by("is_settled", "name")

    def destroy(self, request, *args, **kwargs):
        if self.get_object().is_settled:
            return Response(
                {"message": "A settled salary can't be deleted."}, status=400
            )
        return super().destroy(request, *args, **kwargs)

    # ---------- cards and export ----------

    @action(detail=False, methods=["get"])
    def summary(self, request):
        rows = list(self.get_queryset())
        pending = [r for r in rows if not r.is_settled]
        return Response(
            {
                "month": f"{get_month(request):%Y-%m}",
                "staff_count": len(rows),
                "total_monthly_salary": sum((r.monthly_salary for r in rows), ZERO),
                "advances_given": sum((r.advance for r in rows), ZERO),
                "salary_outstanding": sum((r.net_payable for r in pending), ZERO),
                "pending_count": len(pending),
                "settled_count": len(rows) - len(pending),
            }
        )

    @action(detail=False, methods=["get"])
    def export(self, request):
        start = get_month(request)
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="salary-{start:%Y-%m}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Staff Name", "Mobile", "Monthly Salary", "Advance", "Net Payable", "Status"])
        for s in self.get_queryset():
            writer.writerow([
                s.name, s.mobile_number, s.monthly_salary, s.advance, s.net_payable,
                "Settled" if s.is_settled else "Pending",
            ])
        return response

    # ---------- 1. single advance ----------

    @action(detail=True, methods=["post"], url_path="add-advance")
    def add_advance(self, request, pk=None):
        salary = self.get_object()
        ser = AdvanceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        amount = ser.validated_data["amount"]

        error = advance_error(salary, amount)
        if error:
            return Response({"message": error}, status=400)

        salary.advance += amount
        salary.save()
        return Response(
            {"message": "Advance added successfully", "data": self.get_serializer(salary).data},
            status=201,
        )

    # ---------- 2. bulk advance ----------

    @action(detail=False, methods=["post"], url_path="bulk-advance")
    def bulk_advance(self, request):
        ser = BulkAdvanceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        items = ser.validated_data["advances"]

        with transaction.atomic():
            rows = Salary.objects.select_for_update().in_bulk([i["id"] for i in items])
            errors = []
            for item in items:
                salary = rows.get(item["id"])
                if not salary:
                    errors.append({"id": item["id"], "name": None, "message": "Salary record not found."})
                    continue
                error = advance_error(salary, item["amount"])
                if error:
                    errors.append({"id": salary.id, "name": salary.name, "message": error})

            if errors:
                return Response(
                    {"message": "Nothing was saved. Fix the errors below and try again.", "errors": errors},
                    status=400,
                )

            for item in items:
                salary = rows[item["id"]]
                salary.advance += item["amount"]
                salary.save()

        done = [rows[i["id"]] for i in items]
        return Response(
            {
                "message": f"Advance given to {len(done)} employee(s)",
                "count": len(done),
                "total_amount": sum((i["amount"] for i in items), ZERO),
                "items": self.get_serializer(done, many=True).data,
            },
            status=201,
        )

    # ---------- 3. single settlement ----------

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        salary = self.get_object()
        if salary.is_settled:
            return Response({"message": "Salary is already settled."}, status=400)

        opts = PayOptionsSerializer(data=request.data)
        opts.is_valid(raise_exception=True)
        d = opts.validated_data

        salary.is_settled = True
        salary.payment_date = d.get("payment_date") or timezone.localdate()
        salary.payment_mode = d["payment_mode"]
        salary.note = d.get("note", salary.note)
        salary.paid_on = timezone.now()
        salary.save()
        return Response(
            {"message": "Salary paid successfully", "data": self.get_serializer(salary).data},
            status=201,
        )

    # ---------- 4. bulk settlement ----------

    @action(detail=False, methods=["post"], url_path="bulk-pay")
    def bulk_pay(self, request):
        ser = BulkPaySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        with transaction.atomic():
            rows = Salary.objects.select_for_update().in_bulk(d["ids"])
            errors = []
            for sid in d["ids"]:
                salary = rows.get(sid)
                if not salary:
                    errors.append({"id": sid, "name": None, "message": "Salary record not found."})
                elif salary.is_settled:
                    errors.append({"id": sid, "name": salary.name, "message": "Salary for this month is already settled."})

            if errors:
                return Response(
                    {"message": "Nothing was saved. Fix the errors below and try again.", "errors": errors},
                    status=400,
                )

            pay_date = d.get("payment_date") or timezone.localdate()
            now = timezone.now()
            done = []
            for sid in d["ids"]:
                salary = rows[sid]
                salary.is_settled = True
                salary.payment_date = pay_date
                salary.payment_mode = d["payment_mode"]
                salary.note = d.get("note", salary.note)
                salary.paid_on = now
                salary.save()
                done.append(salary)

        return Response(
            {
                "message": f"Salary settled for {len(done)} employee(s)",
                "count": len(done),
                "total_paid": sum((s.net_payable for s in done), ZERO),
                "items": self.get_serializer(done, many=True).data,
            },
            status=201,
        )

    # ---------- pay every pending salary of the month ----------

    @action(detail=False, methods=["post"], url_path="pay-all")
    def pay_all(self, request):
        opts = PayOptionsSerializer(data=request.data)
        opts.is_valid(raise_exception=True)
        d = opts.validated_data

        pending = Salary.objects.filter(month=get_month(request), is_settled=False)
        total = sum((s.net_payable for s in pending), ZERO)
        count = pending.update(
            is_settled=True,
            payment_date=d.get("payment_date") or timezone.localdate(),
            payment_mode=d["payment_mode"],
            paid_on=timezone.now(),
        )
        if not count:
            return Response({"message": "No pending salaries for this month", "count": 0})
        return Response(
            {"message": f"Salary paid for {count} employee(s)", "count": count, "total_paid": total},
            status=201,
        )