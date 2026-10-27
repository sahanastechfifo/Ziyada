from django.contrib import admin

from .models import Expense, ExpenseCategory, ExpenseItem, Income


class ExpenseItemInline(admin.TabularInline):
    model = ExpenseItem
    extra = 0


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("date", "payment_type", "total_amount")
    list_filter = ("payment_type", "date")
    inlines = [ExpenseItemInline]


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_default")


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ("date", "cash_amount", "card_online_amount", "total_income")
    list_filter = ("date",)