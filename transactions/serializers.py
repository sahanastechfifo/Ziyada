from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from .models import Expense, ExpenseCategory, ExpenseItem, Income


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ("id", "name", "is_default", "created_at")
        read_only_fields = ("is_default", "created_at")
        # uniqueness is checked (ignoring upper/lower case) in validate_name
        extra_kwargs = {"name": {"validators": []}}

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("Category name is required.")
        clash = ExpenseCategory.objects.filter(name__iexact=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value

    def validate(self, attrs):
        instance = self.instance
        if (
            instance
            and instance.is_default
            and "name" in attrs
            and attrs["name"] != instance.name
        ):
            raise serializers.ValidationError({"name": "Fixed categories can't be renamed."})
        return attrs


class ExpenseItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = ExpenseItem
        fields = ("id", "category", "category_name", "amount")


class ExpenseSerializer(serializers.ModelSerializer):
    items = ExpenseItemSerializer(many=True)
    items_count = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Expense
        fields = (
            "id",
            "date",
            "payment_type",
            "items",
            "items_count",
            "total_amount",
            "created_at",
        )
        read_only_fields = ("created_at",)

    def get_items_count(self, obj):
        return len(obj.items.all())

    def get_total_amount(self, obj):
        return obj.total_amount

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("Add at least one expense amount.")
        for item in items:
            if "category" not in item or "amount" not in item:
                raise serializers.ValidationError("Each item needs a category and an amount.")
        ids = [item["category"].pk for item in items]
        if len(set(ids)) != len(ids):
            raise serializers.ValidationError("Each category can appear only once.")
        return items

    @staticmethod
    def _save_items(expense, items):
        ExpenseItem.objects.bulk_create(
            [ExpenseItem(expense=expense, **item) for item in items]
        )

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop("items")
        expense = Expense.objects.create(**validated_data)
        self._save_items(expense, items)
        return expense

    @transaction.atomic
    def update(self, instance, validated_data):
        items = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items is not None:  # sending items replaces the whole list
            instance.items.all().delete()
            self._save_items(instance, items)
        return instance


class IncomeSerializer(serializers.ModelSerializer):
    total_income = serializers.SerializerMethodField()

    class Meta:
        model = Income
        fields = (
            "id",
            "date",
            "cash_amount",
            "card_online_amount",
            "total_income",
            "created_at",
        )
        read_only_fields = ("created_at",)

    def get_total_income(self, obj):
        return obj.total_income

    def validate(self, attrs):
        instance = self.instance
        cash = attrs.get("cash_amount", getattr(instance, "cash_amount", Decimal("0")))
        card = attrs.get(
            "card_online_amount", getattr(instance, "card_online_amount", Decimal("0"))
        )
        if cash + card <= 0:
            raise serializers.ValidationError("Enter a cash or card/online amount.")
        return attrs