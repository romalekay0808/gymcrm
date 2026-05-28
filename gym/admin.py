from django.contrib import admin
from .models import Trainer, Client, Training, Expense, Settlement, Membership

@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "phone",
        "telegram_id",
        "personal_percent",
        "split_percent",
        "membership_percent",
        "single_percent",
        "ubd_percent",
    )

    search_fields = (
        "name",
        "phone",
        "telegram_id",
    )

    list_per_page = 25


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "phone",
        "created_at",
    )

    search_fields = (
        "name",
        "phone",
    )

    list_filter = (
        "created_at",
    )

    list_per_page = 25


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "client",
        "trainer",
        "training_type",
        "payment_type",
        "money_location",
        "amount",
        "trainer_income",
        "gym_income",
        "comment",
    )

    list_filter = (
        "date",
        "trainer",
        "training_type",
        "payment_type",
        "money_location",
    )

    search_fields = (
        "client__name",
        "client__phone",
        "trainer__name",
    )

    date_hierarchy = "date"

    list_per_page = 30

    fieldsets = (
        ("Основна інформація", {
            "fields": (
                "date",
                "client",
                "trainer",
                "training_type",
                "payment_type",
                "money_location",
                "amount",
            )
        }),

        ("Додатково", {
            "fields": (
                "comment",
            )
        }),
    )


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "category",
        "amount",
        "comment",
    )

    list_filter = (
        "date",
        "category",
    )

    search_fields = (
        "comment",
    )

    date_hierarchy = "date"

    list_per_page = 30


@admin.register(Settlement)
class SettlementAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "trainer",
        "settlement_type",
        "amount",
        "comment",
    )

    list_filter = (
        "date",
        "trainer",
        "settlement_type",
    )

    search_fields = (
        "trainer__name",
        "comment",
    )

    date_hierarchy = "date"

    list_per_page = 30

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = (
        "client",
        "trainer",
        "name",
        "price",
        "start_date",
        "end_date",
        "status",
        "days_left",
    )

    list_filter = (
        "status",
        "trainer",
        "start_date",
        "end_date",
    )

    search_fields = (
        "client__name",
        "trainer__name",
        "name",
    )

    date_hierarchy = "start_date"
    list_per_page = 30