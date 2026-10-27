# from django.urls import path
# from rest_framework.routers import DefaultRouter

# from .views import (
#     EmployeeViewSet,
#     SalaryAdvanceViewSet,
#     SalaryPaymentViewSet,
#     SettlementPreviewView,
#     SettlementView,
# )

# router = DefaultRouter()
# router.register("employees", EmployeeViewSet, basename="employee")
# router.register("advances", SalaryAdvanceViewSet, basename="advance")
# router.register("payments", SalaryPaymentViewSet, basename="payment")

# urlpatterns = [
#     path("settlements/", SettlementView.as_view(), name="settlement"),
#     path("settlements/preview/", SettlementPreviewView.as_view(), name="settlement-preview"),
# ] + router.urls

from rest_framework.routers import DefaultRouter

from .views import SalaryViewSet

router = DefaultRouter()
router.register("", SalaryViewSet, basename="salary")

urlpatterns = router.urls