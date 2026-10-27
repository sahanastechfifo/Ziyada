from decimal import Decimal

from rest_framework import serializers

from .models import PaymentMode, Salary
from .utils import parse_month

MOBILE_ERROR = "Mobile number must be exactly 10 digits."


class MonthField(serializers.Field):
    """Input 'YYYY-MM', stored as the 1st of that month."""

    def to_internal_value(self, value):
        return parse_month(value)

    def to_representation(self, value):
        return f"{value:%Y-%m}"


# class SalarySerializer(serializers.ModelSerializer):
#         mobile_number = serializers.RegexField(
#         regex=r"^\d{8,10}$", error_messages={"invalid": MOBILE_ERROR}
#     )
#     month = MonthField()
#     net_payable = serializers.DecimalField(
#         max_digits=12, decimal_places=2, read_only=True
#     )
#     status = serializers.SerializerMethodField()

class SalarySerializer(serializers.ModelSerializer):
    mobile_number = serializers.RegexField(
        regex=r"^\d{8,10}$", error_messages={"invalid": MOBILE_ERROR}
    )
    month = MonthField()
    net_payable = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    status = serializers.SerializerMethodField()

    class Meta:
        model = Salary
        fields = (
            "id", "name", "mobile_number", "joining_date",
            "month", "monthly_salary", "advance", "net_payable", "status",
            "is_settled", "payment_date", "payment_mode", "paid_on", "note",
        )
        read_only_fields = ("is_settled", "payment_date", "paid_on")

    def get_status(self, obj):
        return "Settled" if obj.is_settled else "Pending"

    def validate(self, attrs):
        inst = self.instance
        if inst and inst.is_settled:
            raise serializers.ValidationError(
                "This salary is already settled and can't be changed."
            )

        salary = attrs.get("monthly_salary", inst.monthly_salary if inst else None)
        advance = attrs.get("advance", inst.advance if inst else Decimal("0.00"))
        if salary is not None and advance > salary:
            raise serializers.ValidationError(
                {"advance": "Advance cannot be more than the monthly salary."}
            )

        mobile = attrs.get("mobile_number", inst.mobile_number if inst else None)
        month = attrs.get("month", inst.month if inst else None)
        clash = Salary.objects.filter(mobile_number=mobile, month=month)
        if inst:
            clash = clash.exclude(pk=inst.pk)
        if clash.exists():
            raise serializers.ValidationError(
                "A salary for this mobile number and month already exists."
            )
        return attrs


# ---------- inputs for pay / advance / bulk actions ----------


def _no_duplicates(ids):
    if len(set(ids)) != len(ids):
        raise serializers.ValidationError("Each employee can appear only once.")


class PayOptionsSerializer(serializers.Serializer):
    payment_date = serializers.DateField(required=False)
    payment_mode = serializers.ChoiceField(
        choices=PaymentMode.choices, default=PaymentMode.CASH
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)


class AdvanceSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )


class BulkAdvanceItemSerializer(AdvanceSerializer):
    id = serializers.IntegerField(min_value=1)


class BulkAdvanceSerializer(serializers.Serializer):
    advances = BulkAdvanceItemSerializer(many=True, allow_empty=False)

    def validate_advances(self, items):
        _no_duplicates([i["id"] for i in items])
        return items


class BulkPaySerializer(PayOptionsSerializer):
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=False
    )

    def validate_ids(self, ids):
        _no_duplicates(ids)
        return ids