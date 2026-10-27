import calendar
from datetime import date
from decimal import Decimal, InvalidOperation


from django.db.models import DecimalField, F, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from transactions.models import ExpenseItem, Income

from .models import DEFAULT_CREDIT_REPAY, DEFAULT_ROOM_RENT, DailyAllocation

ZERO = Decimal("0.00")
MONEY = DecimalField(max_digits=14, decimal_places=2)
PAGE_SIZE = 7


# ---------- filters: ?date=2026-10-22 | ?month=2026-10 | ?year=2026 ----------

def parse_day(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError({"date": "Use the format YYYY-MM-DD."})


def get_range(params):
    """Return (start, end, label). No filter -> (None, None, 'all')."""
    if params.get("date"):
        d = parse_day(params["date"])
        return d, d, f"{d:%Y-%m-%d}"
    if params.get("month"):
        try:
            y, m = map(int, params["month"].split("-"))
            start = date(y, m, 1)
        except (ValueError, TypeError):
            raise ValidationError({"month": "Use the format YYYY-MM."})
        return start, date(y, m, calendar.monthrange(y, m)[1]), f"{y}-{m:02d}"
    if params.get("year"):
        try:
            y = int(params["year"])
            return date(y, 1, 1), date(y, 12, 31), str(y)
        except ValueError:
            raise ValidationError({"year": "Use the format YYYY."})
    return None, None, "all"


# ---------- totals from the transactions app ----------

def _income_totals(start, end):
    """Cash + Card/Online, summed per date."""
    qs = Income.objects.all()
    if start:
        qs = qs.filter(date__gte=start, date__lte=end)
    return {
        r["date"]: r["total"]
        for r in qs.values("date").annotate(
            total=Sum(F("cash_amount") + F("card_online_amount"), output_field=MONEY)
        )
    }


def _expense_totals(start, end):
    """All category amounts, summed per expense date."""
    qs = ExpenseItem.objects.all()
    if start:
        qs = qs.filter(expense__date__gte=start, expense__date__lte=end)
    return {
        r["expense__date"]: r["total"]
        for r in qs.values("expense__date").annotate(total=Sum("amount"))
    }


# ---------- search ----------

def _matches(row, search):
    s = search.strip().lower()
    if s in f"{row['date']:%Y-%m-%d} {row['date']:%d %b %Y}".lower():
        return True
    try:
        amount = Decimal(s)
    except InvalidOperation:
        return False
    return amount in (
        row["total_income"], row["total_expenses"],
        row["room_rent"], row["credit_repay"], row["daily_balance"],
    )


# ---------- table rows ----------

def build_rows(start=None, end=None, search=None):
    income = _income_totals(start, end)
    expense = _expense_totals(start, end)

    allocs = DailyAllocation.objects.all()
    if start:
        allocs = allocs.filter(date__gte=start, date__lte=end)
    allocs = {a.date: a for a in allocs}
    default_rent = DEFAULT_ROOM_RENT
    default_credit = DEFAULT_CREDIT_REPAY
    today = timezone.localdate()

    rows = []
    for d in sorted(set(income) | set(expense) | set(allocs), reverse=True):
        a = allocs.get(d)
        inc = income.get(d, ZERO)
        exp = expense.get(d, ZERO)
        rent = a.room_rent if a else default_rent
        credit = a.credit_repay if a else default_credit
        rows.append(
            {
                "date": d,
                "display_date": f"{d:%d %b %Y}",
                "weekday": f"{d:%A}",
                "is_today": d == today,
                "total_income": inc,
                "total_expenses": exp,
                "room_rent": rent,
                "credit_repay": credit,
                "daily_balance": inc - (exp + rent + credit),
                "is_edited": a is not None,
            }
        )

    if search:
        rows = [r for r in rows if _matches(r, search)]
    return rows


def sum_rows(rows):
    return {
        "total_income": sum((r["total_income"] for r in rows), ZERO),
        "total_expenses": sum((r["total_expenses"] for r in rows), ZERO),
        "room_rent": sum((r["room_rent"] for r in rows), ZERO),
        "credit_repay": sum((r["credit_repay"] for r in rows), ZERO),
        "daily_balance": sum((r["daily_balance"] for r in rows), ZERO),
    }