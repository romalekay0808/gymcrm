from django import forms
from .models import Trainer, Expense, Client


class TrainerForm(forms.ModelForm):

    class Meta:
        model = Trainer

        fields = [
            "name",
            "phone",
            "telegram_id",
            "personal_percent",
            "split_percent",
            "membership_percent",
            "single_percent",
            "ubd_percent",
        ]


class ExpenseForm(forms.ModelForm):

    class Meta:
        model = Expense

        fields = [
            "category",
            "amount",
            "date",
            "comment",
        ]

        widgets = {
            "date": forms.DateInput(
                attrs={
                    "type": "date"
                }
            )
        }

class ClientForm(forms.ModelForm):

    class Meta:
        model = Client

        fields = [
            "name",
            "phone",
        ]        