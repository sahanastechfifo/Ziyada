from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ExpenseCategoryViewSet,
    ExpenseViewSet,
    IncomeViewSet,
    PaymentTypeListView,
)

router = DefaultRouter()
router.register("expense-categories", ExpenseCategoryViewSet, basename="expense-category")
router.register("expenses", ExpenseViewSet, basename="expense")
router.register("incomes", IncomeViewSet, basename="income")

urlpatterns = [
    path("payment-types/", PaymentTypeListView.as_view(), name="payment-types"),
] + router.urls