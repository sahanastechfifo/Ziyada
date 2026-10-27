from django.apps import AppConfig
from django.db.models.signals import post_migrate

# Fixed categories: the same every month. Only the amounts change.
DEFAULT_CATEGORIES = [
    "Electricity & Utilities",
    "Inventory Purchases & Supplies",
    "Staff Refreshments & Allowances",
    "Delivery & Logistics",
]


def create_default_categories(sender, **kwargs):
    """Runs after `migrate`; creates the fixed categories if they are missing."""
    Category = kwargs["apps"].get_model("transactions", "ExpenseCategory")
    using = kwargs.get("using", "default")
    for name in DEFAULT_CATEGORIES:
        Category.objects.using(using).update_or_create(
            name=name, defaults={"is_default": True}
        )


class TransactionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transactions"

    def ready(self):
        post_migrate.connect(create_default_categories, sender=self)