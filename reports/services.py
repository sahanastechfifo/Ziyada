from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Sum
from django.utils import timezone

from balance.models import DEFAULT_CREDIT_REPAY, DEFAULT_ROOM_RENT, DailyAllocation
from balance.services import PAGE_SIZE, _expense_totals, get_range, parse_day  # noqa: F401
from transactions.models import Expense, ExpenseItem, Income

ZERO = Decimal("0.00")


def _income_totals(start, end):
    """{date: (cash, card_online)} summed per date."""
    qs = Income.objects.all()
    if start:
        qs = qs.filter(date__gte=start, date__lte=end)
    return {
        r["date"]: (r["cash"], r["card"])
        for r in qs.values("date").annotate(
            cash=Sum("cash_amount"), card=Sum("card_online_amount")
        )
    }


def _matches(row, search):
    s = search.strip().lower()
    if s in f"{row['date']:%Y-%m-%d} {row['date']:%d %b %Y}".lower():
        return True
    try:
        amount = Decimal(s)
    except InvalidOperation:
        return False
    return amount in (
        row["income_cash"], row["income_card"], row["total_income"],
        row["total_expenses"], row["balance_amount"],
        row["room_rent"], row["credit_repay"], row["daily_profit"],
    )


def build_rows(start=None, end=None, search=None):
    income = _income_totals(start, end)
    expense = _expense_totals(start, end)

    allocs = DailyAllocation.objects.all()
    if start:
        allocs = allocs.filter(date__gte=start, date__lte=end)
    allocs = {a.date: a for a in allocs}

    today = timezone.localdate()
    rows = []
    for d in sorted(set(income) | set(expense) | set(allocs), reverse=True):
        cash, card = income.get(d, (ZERO, ZERO))
        total_income = cash + card
        exp = expense.get(d, ZERO)
        a = allocs.get(d)
        rent = a.room_rent if a else DEFAULT_ROOM_RENT
        credit = a.credit_repay if a else DEFAULT_CREDIT_REPAY
        balance_amount = total_income - exp
        rows.append(
            {
                "date": d,
                "display_date": f"{d:%d %b %Y}",
                "weekday": f"{d:%A}",
                "is_today": d == today,
                "income_cash": cash,
                "income_card": card,
                "total_income": total_income,
                "total_expenses": exp,
                "balance_amount": balance_amount,
                "room_rent": rent,
                "credit_repay": credit,
                "daily_profit": balance_amount - rent - credit,
            }
        )

    if search:
        rows = [r for r in rows if _matches(r, search)]
    return rows


def sum_rows(rows):
    keys = (
        "income_cash", "income_card", "total_income", "total_expenses",
        "balance_amount", "room_rent", "credit_repay", "daily_profit",
    )
    return {k: sum((r[k] for r in rows), ZERO) for k in keys}


def month_change_percent(start, current_income):
    """'+18.4% vs last month' under Total Income. Only used for a month filter."""
    prev_end = start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    prev = sum((c + k for c, k in _income_totals(prev_start, prev_end).values()), ZERO)
    if not prev:
        return None
    return round((current_income - prev) / prev * 100, 1)


# ---------- one-day detail (the view button) ----------

def _neighbour_dates(d):
    dates = set(Income.objects.values_list("date", flat=True))
    dates |= set(Expense.objects.values_list("date", flat=True))
    dates |= set(DailyAllocation.objects.values_list("date", flat=True))
    before = [x for x in dates if x < d]
    after = [x for x in dates if x > d]
    return (max(before) if before else None), (min(after) if after else None)


def day_detail(d):
    rows = build_rows(d, d)
    if not rows:
        return None
    r = rows[0]

    categories = (
        ExpenseItem.objects.filter(expense__date=d)
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    previous_date, next_date = _neighbour_dates(d)
    allocated = r["room_rent"] + r["credit_repay"]

    return {
        "date": d,
        "display_date": f"{d:%A, %d %b %Y}",
        "is_today": r["is_today"],
        "previous_date": previous_date,
        "next_date": next_date,
        "cards": {
            "total_day_income": r["total_income"],
            "total_day_expenses": r["total_expenses"],
            "daily_net_movement": r["balance_amount"],
            "daily_net_profit": r["daily_profit"],
        },
        "income_breakdown": {
            "cash_income": r["income_cash"],
            "card_online_income": r["income_card"],
            "total": r["total_income"],
        },
        "expenses_breakdown": {
            "items": [{"category": c["category__name"], "amount": c["total"]} for c in categories],
            "total": r["total_expenses"],
        },
        "balance_allocations": {
            "available_balance": r["balance_amount"],
            "room_rent": r["room_rent"],
            "credit_repayment": r["credit_repay"],
            "total_allocated": allocated,
        },
        "day_balance_sheet": {
            "total_income": r["total_income"],
            "total_expenses": r["total_expenses"],
            "room_rent_allocation": r["room_rent"],
            "credit_debt_repayment": r["credit_repay"],
            "net_retained_profit": r["daily_profit"],
        },
    }