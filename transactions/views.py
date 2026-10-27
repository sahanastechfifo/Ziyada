from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Expense, ExpenseCategory, Income, PaymentType
from .serializers import (
    ExpenseCategorySerializer,
    ExpenseSerializer,
    IncomeSerializer,
)


class SaveMessageMixin(mixins.CreateModelMixin):
    """POST only: saves the record and returns a friendly message."""

    created_message = "Saved successfully"

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response({"message": self.created_message, "data": response.data}, status=201)


class PaymentTypeListView(APIView):
    """Values for the Payment Type dropdown (Add Expense page)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([{"value": v, "label": l} for v, l in PaymentType.choices])


class ExpenseCategoryViewSet(SaveMessageMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET = the category boxes on the page. POST = 'Add Custom Category'."""

    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # the whole list, fixed categories first
    created_message = "Category added successfully"


class ExpenseViewSet(SaveMessageMixin, viewsets.GenericViewSet):
    """POST = 'Save Expense' button."""

    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]
    created_message = "Expense saved successfully"


class IncomeViewSet(SaveMessageMixin, viewsets.GenericViewSet):
    """POST = 'Save Income' button."""

    queryset = Income.objects.all()
    serializer_class = IncomeSerializer
    permission_classes = [IsAuthenticated]
    created_message = "Income saved successfully"
    