from datetime import date, datetime

from django.utils import timezone
from rest_framework.exceptions import ValidationError


def parse_month(value):
    """'YYYY-MM' or 'YYYY-MM-DD' -> first day of that month. Empty -> current month."""
    if not value:
        return timezone.localdate().replace(day=1)
    try:
        return datetime.strptime(str(value)[:7], "%Y-%m").date()
    except ValueError:
        raise ValidationError({"month": "Use the format YYYY-MM (e.g. 2024-10)."})


def month_end(start):
    """First day of the following month (exclusive upper bound)."""
    if start.month == 12:
        return date(start.year + 1, 1, 1)
    return date(start.year, start.month + 1, 1)


def get_month(request):
    """Read ?month=... from the query string or the request body."""
    value = request.query_params.get("month")
    if not value and hasattr(request.data, "get"):
        value = request.data.get("month")
    return parse_month(value)