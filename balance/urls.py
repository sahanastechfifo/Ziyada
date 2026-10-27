from django.urls import path

from .views import BalanceDetailView, BalanceExportView, BalanceListView

urlpatterns = [
    path("", BalanceListView.as_view()),
    path("export/", BalanceExportView.as_view()),
    path("<str:date>/", BalanceDetailView.as_view()),
]