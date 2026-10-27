from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class PaymentType(models.TextChoices):
    CASH = "cash", "Cash"
    CARD = "card", "Card"
    UPI = "upi", "UPI"
    BANK = "bank", "Bank Transfer"


class ExpenseCategory(models.Model):
    """Fixed categories (is_default=True) plus any custom ones the user adds."""

    name = models.CharField(max_length=100, unique=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "id"]
        verbose_name_plural = "expense categories"

    def __str__(self):
        return self.name


class Expense(models.Model):
    """One 'Save Expense' click: a date, a payment type and amounts per category."""

    date = models.DateField(default=timezone.localdate)
    payment_type = models.CharField(
        max_length=10, choices=PaymentType.choices, default=PaymentType.CASH
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]

    @property
    def total_amount(self):
        return sum((i.amount for i in self.items.all()), Decimal("0.00"))

    def __str__(self):
        return f"Expense {self.date} ({self.payment_type})"


class ExpenseItem(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="items")
    category = models.ForeignKey(
        ExpenseCategory, on_delete=models.PROTECT, related_name="items"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["expense", "category"], name="unique_category_per_expense"
            )
        ]

    def __str__(self):
        return f"{self.category.name}: {self.amount}"


class Income(models.Model):
    """One 'Save Income' click: a date with cash and card/online collections."""

    date = models.DateField(default=timezone.localdate)
    cash_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    card_online_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]

    @property
    def total_income(self):
        return self.cash_amount + self.card_online_amount

    def __str__(self):
        return f"Income {self.date}: {self.total_income}"