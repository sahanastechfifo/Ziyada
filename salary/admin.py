# from django.contrib import admin

# from .models import Employee, SalaryAdvance, SalaryPayment


# @admin.register(Employee)
# class EmployeeAdmin(admin.ModelAdmin):
#     list_display = ("name", "mobile_number", "monthly_salary", "is_active")
#     search_fields = ("name", "mobile_number")
#     list_filter = ("is_active",)


# @admin.register(SalaryAdvance)
# class SalaryAdvanceAdmin(admin.ModelAdmin):
#     list_display = ("employee", "amount", "date")
#     list_filter = ("date",)


# @admin.register(SalaryPayment)
# class SalaryPaymentAdmin(admin.ModelAdmin):
#     list_display = ("employee", "month", "salary_amount", "advance_deducted", "net_paid")
#     list_filter = ("month",)

from django.contrib import admin

from .models import Salary


@admin.register(Salary)
class SalaryAdmin(admin.ModelAdmin):
    list_display = (
        "name", "mobile_number", "month", "monthly_salary",
        "advance", "is_settled", "payment_mode",
    )
    list_filter = ("month", "is_settled", "payment_mode")
    search_fields = ("name", "mobile_number")