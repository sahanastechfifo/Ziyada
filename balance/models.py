# from decimal import Decimal

# from django.conf import settings
# from django.db import models


# def default_room_rent():
#     return Decimal(str(settings.DEFAULT_ROOM_RENT))


# def default_credit_repay():
#     return Decimal(str(settings.DEFAULT_CREDIT_REPAY))

from decimal import Decimal

from django.db import models

DEFAULT_ROOM_RENT = Decimal("3000.00")
DEFAULT_CREDIT_REPAY = Decimal("2000.00")


def default_room_rent():
    return DEFAULT_ROOM_RENT


def default_credit_repay():
    return DEFAULT_CREDIT_REPAY


class DailyAllocation(models.Model):
    date = models.DateField(unique=True)
    room_rent = models.DecimalField(
        max_digits=12, decimal_places=2, default=default_room_rent
    )
    credit_repay = models.DecimalField(
        max_digits=12, decimal_places=2, default=default_credit_repay
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date} rent={self.room_rent} credit={self.credit_repay}"