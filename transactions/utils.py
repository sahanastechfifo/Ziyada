from datetime import date, datetime

from rest_framework.exceptions import ValidationError


def _parse_date(value, name):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError({name: "Use the format YYYY-MM-DD (e.g. 2026-10-24)."})


def _month_bounds(value):
    try:
        start = datetime.strptime(value[:7], "%Y-%m").date()
    except ValueError:
        raise ValidationError({"month": "Use the format YYYY-MM (e.g. 2026-10)."})
    if start.month == 12:
        return start, date(start.year + 1, 1, 1)
    return start, date(start.year, start.month + 1, 1)


def filter_period(qs, params, field="date"):
    """?date=YYYY-MM-DD  or  ?month=YYYY-MM  or  ?from=...&to=..."""
    if params.get("date"):
        return qs.filter(**{field: _parse_date(params["date"], "date")})
    if params.get("month"):
        start, end = _month_bounds(params["month"])
        return qs.filter(**{f"{field}__gte": start, f"{field}__lt": end})
    if params.get("from"):
        qs = qs.filter(**{f"{field}__gte": _parse_date(params["from"], "from")})
    if params.get("to"):
        qs = qs.filter(**{f"{field}__lte": _parse_date(params["to"], "to")})
    return qs


def period_label(params):
    return params.get("date") or params.get("month") or "all"