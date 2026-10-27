# from decimal import Decimal

# from django.core.validators import MinValueValidator, RegexValidator
# from django.db import models
# from django.utils import timezone

# mobile_validator = RegexValidator(
#     regex=r"^\d{10}$",
#     message="Mobile number must be exactly 10 digits.",
# )


# class PaymentMode(models.TextChoices):
#     CASH = "cash", "Cash"
#     BANK = "bank", "Bank"
#     UPI = "upi", "UPI"


# class Employee(models.Model):
#     """A staff member who receives a fixed monthly salary."""

#     name = models.CharField(max_length=150)
#     mobile_number = models.CharField(
#         max_length=10, unique=True, validators=[mobile_validator]
#     )
#     monthly_salary = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         validators=[MinValueValidator(Decimal("0.01"))],
#     )
#     joining_date = models.DateField(null=True, blank=True)
#     is_active = models.BooleanField(default=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         ordering = ["name"]

#     def __str__(self):
#         return f"{self.name} ({self.mobile_number})"


# class SalaryAdvance(models.Model):
#     """Money given to an employee in advance. Deducted from that month's salary.

#     `date` is the payment date; the salary month is the month of that date.
#     """

#     employee = models.ForeignKey(
#         Employee, on_delete=models.PROTECT, related_name="advances"
#     )
#     amount = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         validators=[MinValueValidator(Decimal("0.01"))],
#     )
#     date = models.DateField(default=timezone.localdate)
#     payment_mode = models.CharField(
#         max_length=10, choices=PaymentMode.choices, default=PaymentMode.CASH
#     )
#     note = models.CharField(max_length=255, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         ordering = ["-date", "-id"]

#     def __str__(self):
#         return f"{self.employee.name} - advance {self.amount} on {self.date}"


# class SalaryPayment(models.Model):
#     """One settled salary for one employee for one month."""

#     employee = models.ForeignKey(
#         Employee, on_delete=models.PROTECT, related_name="payments"
#     )
#     month = models.DateField(help_text="First day of the salary month")
#     salary_amount = models.DecimalField(max_digits=12, decimal_places=2)
#     advance_deducted = models.DecimalField(
#         max_digits=12, decimal_places=2, default=Decimal("0.00")
#     )
#     net_paid = models.DecimalField(max_digits=12, decimal_places=2)
#     payment_date = models.DateField(default=timezone.localdate)
#     payment_mode = models.CharField(
#         max_length=10, choices=PaymentMode.choices, default=PaymentMode.CASH
#     )
#     paid_on = models.DateTimeField(default=timezone.now)
#     note = models.CharField(max_length=255, blank=True)

#     class Meta:
#         ordering = ["-month", "-paid_on"]
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["employee", "month"], name="unique_salary_payment_per_month"
#             )
#         ]

#     def __str__(self):
#         return f"{self.employee.name} - {self.month:%b %Y} - {self.net_paid}"

from decimal import Decimal

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

mobile_validator = RegexValidator(
    regex=r"^\d{10}$",
    message="Mobile number must be exactly 10 digits.",
)


class PaymentMode(models.TextChoices):
    CASH = "cash", "Cash"
    BANK = "bank", "Bank"
    UPI = "upi", "UPI"


class Salary(models.Model):
    """One employee's salary for one month (employee details are stored on it)."""

    # employee details
    name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=10, validators=[mobile_validator])
    joining_date = models.DateField(null=True, blank=True)

    # salary details
    month = models.DateField(help_text="First day of the salary month")
    monthly_salary = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    advance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    # payment details (filled when marked as paid)
    is_settled = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)
    payment_mode = models.CharField(
        max_length=10, choices=PaymentMode.choices, default=PaymentMode.CASH
    )
    paid_on = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["is_settled", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["mobile_number", "month"],
                name="unique_salary_per_employee_per_month",
            )
        ]

    @property
    def net_payable(self):
        return max(self.monthly_salary - self.advance, Decimal("0.00"))

    def __str__(self):
        return f"{self.name} - {self.month:%b %Y}"