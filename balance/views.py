import csv

from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DailyAllocation
from .serializers import DailyAllocationSerializer
from .services import PAGE_SIZE, build_rows, get_range, parse_day, sum_rows


class BalanceListView(APIView):
    """GET = table + cards (filters, search, pagination). POST = add an allocation for a date."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        start, end, label = get_range(params)
        rows = build_rows(start, end, params.get("search"))

        paginator = Paginator(rows, PAGE_SIZE)
        page = paginator.get_page(params.get("page", 1))

        return Response(
            {
                "filter": label,
                "summary": {**sum_rows(rows), "days_allocated": len(rows)},
                "count": paginator.count,
                "page": page.number,
                "total_pages": paginator.num_pages,
                "page_size": PAGE_SIZE,
                "results": list(page),
                "page_subtotal": sum_rows(list(page)),
            }
        )

    def post(self, request):
        serializer = DailyAllocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data["date"]
        if DailyAllocation.objects.filter(date=d).exists():
            return Response(
                {"message": "An allocation for this date already exists. Use PATCH to edit it."},
                status=400,
            )
        serializer.save()
        return Response(
            {"message": "Allocation added successfully", "data": build_rows(d, d)[0]},
            status=201,
        )


class BalanceDetailView(APIView):
    """One day: GET (view), PATCH (edit room rent / credit repay), DELETE (reset to default)."""

    permission_classes = [IsAuthenticated]

    def _row(self, d):
        rows = build_rows(d, d)
        if not rows:
            raise Http404("No data for this date.")
        return rows[0]

    def get(self, request, date):
        return Response(self._row(parse_day(date)))

    def patch(self, request, date):
        d = parse_day(date)
        obj, _ = DailyAllocation.objects.get_or_create(date=d)
        data = {k: v for k, v in request.data.items() if k in ("room_rent", "credit_repay")}
        serializer = DailyAllocationSerializer(obj, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Allocation updated successfully", "data": self._row(d)}
        )

    def delete(self, request, date):
        d = parse_day(date)
        DailyAllocation.objects.filter(date=d).delete()
        return Response({"message": "Allocation reset to default values"})


class BalanceExportView(APIView):
    """CSV download of the same filter (?date= / ?month= / ?year= / ?search=)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        start, end, label = get_range(params)
        rows = build_rows(start, end, params.get("search"))

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="balance-{label}.csv"'
        writer = csv.writer(response)
        writer.writerow(
            ["Date", "Weekday", "Total Income", "Total Expenses", "Room Rent", "Credit Repay", "Daily Balance"]
        )
        for r in rows:
            writer.writerow(
                [r["display_date"], r["weekday"], r["total_income"], r["total_expenses"],
                 r["room_rent"], r["credit_repay"], r["daily_balance"]]
            )
        t = sum_rows(rows)
        writer.writerow(
            ["TOTAL", "", t["total_income"], t["total_expenses"],
             t["room_rent"], t["credit_repay"], t["daily_balance"]]
        )
        return response