import csv
from io import BytesIO

from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import (
    PAGE_SIZE, build_rows, day_detail, get_range,
    month_change_percent, parse_day, sum_rows,
)


class ReportListView(APIView):
    """Table + cards. ?date= / ?month= / ?year= / ?search= / ?page="""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        start, end, label = get_range(params)
        rows = build_rows(start, end, params.get("search"))
        totals = sum_rows(rows)

        paginator = Paginator(rows, PAGE_SIZE)
        page = paginator.get_page(params.get("page", 1))

        change = None
        if params.get("month") and not params.get("search"):
            change = month_change_percent(start, totals["total_income"])

        return Response(
            {
                "filter": label,
                "summary": {
                    "total_income": totals["total_income"],
                    "income_vs_last_month_percent": change,
                    "total_expenses": totals["total_expenses"],
                    "net_balance": totals["balance_amount"],
                    "net_profit": totals["daily_profit"],
                    "days": len(rows),
                },
                "count": paginator.count,
                "page": page.number,
                "total_pages": paginator.num_pages,
                "page_size": PAGE_SIZE,
                "results": list(page),
                "page_subtotal": sum_rows(list(page)),
            }
        )


class ReportDetailView(APIView):
    """The view (eye) button: full details of one day."""

    permission_classes = [IsAuthenticated]

    def get(self, request, date):
        data = day_detail(parse_day(date))
        if data is None:
            raise Http404("No data for this date.")
        return Response(data)


class ReportExportView(APIView):
    """CSV download with the same filters and search as the list."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        start, end, label = get_range(params)
        rows = build_rows(start, end, params.get("search"))

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="report-{label}.csv"'
        w = csv.writer(response)
        w.writerow(
            ["Date", "Weekday", "Income (Cash)", "Income (Card/POS)", "Total Income",
             "Total Expenses", "Balance Amount", "Room Rent", "Credit Repay", "Daily Profit"]
        )
        for r in rows:
            w.writerow(
                [r["display_date"], r["weekday"], r["income_cash"], r["income_card"],
                 r["total_income"], r["total_expenses"], r["balance_amount"],
                 r["room_rent"], r["credit_repay"], r["daily_profit"]]
            )
        t = sum_rows(rows)
        w.writerow(
            ["SUB TOTAL", "", t["income_cash"], t["income_card"], t["total_income"],
             t["total_expenses"], t["balance_amount"], t["room_rent"],
             t["credit_repay"], t["daily_profit"]]
        )
        return response


class ReportDayPdfView(APIView):
    """'Download Report (.pdf)' button in the day panel."""

    permission_classes = [IsAuthenticated]

    def get(self, request, date):
        d = parse_day(date)
        data = day_detail(d)
        if data is None:
            raise Http404("No data for this date.")

        lines = [
            ("Daily Report", 18),
            (data["display_date"], 12),
            ("", 12),
            ("Income Breakdown", 13),
            (f"Cash Income: Rs. {data['income_breakdown']['cash_income']}", 11),
            (f"Card & Online Income: Rs. {data['income_breakdown']['card_online_income']}", 11),
            (f"Total Income: Rs. {data['income_breakdown']['total']}", 11),
            ("", 12),
            ("Expenses Breakdown", 13),
        ]
        for item in data["expenses_breakdown"]["items"]:
            lines.append((f"{item['category']}: Rs. {item['amount']}", 11))
        lines += [
            (f"Total Expenses: Rs. {data['expenses_breakdown']['total']}", 11),
            ("", 12),
            ("Balance Allocations", 13),
            (f"Available Balance: Rs. {data['balance_allocations']['available_balance']}", 11),
            (f"Room Rent: Rs. {data['balance_allocations']['room_rent']}", 11),
            (f"Credit Repayment: Rs. {data['balance_allocations']['credit_repayment']}", 11),
            ("", 12),
            ("Day Balance Sheet", 13),
            (f"Net Retained Profit: Rs. {data['day_balance_sheet']['net_retained_profit']}", 12),
        ]

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        y = 800
        for text, size in lines:
            pdf.setFont("Helvetica-Bold" if size >= 13 else "Helvetica", size)
            pdf.drawString(50, y, text)
            y -= size + 8
        pdf.save()

        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="report-{d}.pdf"'
        return response