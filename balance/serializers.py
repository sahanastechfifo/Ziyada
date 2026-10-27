from decimal import Decimal

from rest_framework import serializers

from .models import DailyAllocation


class DailyAllocationSerializer(serializers.ModelSerializer):
    room_rent = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.00"), required=False
    )
    credit_repay = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.00"), required=False
    )

    class Meta:
        model = DailyAllocation
        fields = ("id", "date", "room_rent", "credit_repay")