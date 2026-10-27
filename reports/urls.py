from django.urls import path

from .views import ReportDayPdfView, ReportDetailView, ReportExportView, ReportListView

urlpatterns = [
    path("", ReportListView.as_view()),
    path("export/", ReportExportView.as_view()),
    path("<str:date>/download/", ReportDayPdfView.as_view()),
    path("<str:date>/", ReportDetailView.as_view()),
]