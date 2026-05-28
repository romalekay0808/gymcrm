from django.db import models
from decimal import Decimal
from django.contrib.auth.models import User


class Trainer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)

    name = models.CharField("Ім'я тренера", max_length=255)
    phone = models.CharField("Телефон", max_length=50, blank=True)
    telegram_id = models.CharField("Telegram ID", max_length=100, blank=True)

    personal_percent = models.DecimalField("Відсоток персональних", max_digits=5, decimal_places=2, default=50)
    membership_percent = models.DecimalField("Відсоток абонементів", max_digits=5, decimal_places=2, default=20)
    split_percent = models.DecimalField("Відсоток спліт тренувань", max_digits=5, decimal_places=2, default=50)
    single_percent = models.DecimalField("Відсоток разових", max_digits=5, decimal_places=2, default=40)
    ubd_percent = models.DecimalField("Відсоток УБД", max_digits=5, decimal_places=2, default=0)

    def __str__(self):
        return self.name


class Client(models.Model):
    name = models.CharField("Ім'я клієнта", max_length=255)
    phone = models.CharField("Телефон", max_length=50, blank=True)
    created_at = models.DateTimeField("Дата додавання", auto_now_add=True)
    trainer = models.ForeignKey(
    Trainer,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    verbose_name="Тренер"
)

    def __str__(self):
        return self.name


class Training(models.Model):
    TRAINING_TYPES = (
        ("membership", "Абонемент"),
        ("personal", "Персональне тренування"),
        ("split", "Спліт тренування"),
        ("single", "Разове заняття"),
        ("ubd_membership", "Абонемент УБД"),
    )

    PAYMENT_TYPES = (
        ("cash", "Готівка"),
        ("card", "Карта"),
    )

    MONEY_LOCATIONS = (
        ("trainer", "У тренера"),
        
        ("gym_card", "На карті залу"),
    )

    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE, verbose_name="Тренер")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Клієнт")

    training_type = models.CharField("Тип", max_length=30, choices=TRAINING_TYPES)
    payment_type = models.CharField("Оплата", max_length=20, choices=PAYMENT_TYPES)
    money_location = models.CharField("Де зараз кошти", max_length=30, choices=MONEY_LOCATIONS, default="trainer")

    amount = models.DecimalField("Сума", max_digits=10, decimal_places=2)
    date = models.DateField("Дата")
    comment = models.TextField("Коментар", blank=True)

    def trainer_income(self):
        if self.training_type == "personal":
            percent = self.trainer.personal_percent
        elif self.training_type == "split":
            percent = self.trainer.split_percent
        elif self.training_type == "membership":
            percent = self.trainer.membership_percent
        elif self.training_type == "single":
            percent = self.trainer.single_percent
        elif self.training_type == "ubd_membership":
            percent = self.trainer.ubd_percent
        else:
            percent = Decimal("0")

        return self.amount * percent / Decimal("100")

    def gym_income(self):
        return self.amount - self.trainer_income()

    def __str__(self):
        return f"{self.client} — {self.amount} грн"


class Expense(models.Model):
    CATEGORIES = (
        ("rent", "Оренда"),
        ("salary", "Зарплати"),
        ("ads", "Реклама"),
        ("utilities", "Комунальні"),
        ("repair", "Ремонт"),
        ("equipment", "Обладнання"),
        ("other", "Інше"),
    )

    category = models.CharField("Категорія", max_length=50, choices=CATEGORIES)
    amount = models.DecimalField("Сума", max_digits=10, decimal_places=2)
    date = models.DateField("Дата")
    comment = models.TextField("Коментар", blank=True)

    def __str__(self):
        return f"{self.get_category_display()} — {self.amount} грн"


class Settlement(models.Model):
    SETTLEMENT_TYPES = (
        ("trainer_to_gym", "Тренер здав гроші залу"),
        ("gym_to_trainer", "Зал виплатив тренеру"),
    )

    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE, verbose_name="Тренер")
    settlement_type = models.CharField("Тип розрахунку", max_length=30, choices=SETTLEMENT_TYPES)
    amount = models.DecimalField("Сума", max_digits=10, decimal_places=2)
    date = models.DateField("Дата")
    comment = models.TextField("Коментар", blank=True)

    def __str__(self):
        return f"{self.trainer} — {self.amount} грн"
    
class TrainingGroup(models.Model):
    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE, verbose_name="Тренер")
    name = models.CharField("Назва групи", max_length=255)
    description = models.CharField("Опис / вік", max_length=255, blank=True)

    def __str__(self):
        return f"{self.name} — {self.trainer.name}"


class GroupSubscription(models.Model):
    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE, verbose_name="Тренер")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Клієнт")
    group = models.ForeignKey(TrainingGroup, on_delete=models.CASCADE, verbose_name="Група")

    start_date = models.DateField("Дата старту")
    end_date = models.DateField("Дата завершення")

    amount = models.DecimalField("Сума", max_digits=10, decimal_places=2)
    money_location = models.CharField(
        "Де кошти",
        max_length=30,
        choices=Training.MONEY_LOCATIONS,
        default="trainer"
    )

    is_notified = models.BooleanField("Нагадування відправлено", default=False)
    created_at = models.DateTimeField("Дата створення", auto_now_add=True)

    def __str__(self):
        return f"{self.client.name} — {self.group.name} до {self.end_date}"    

class Membership(models.Model):
    STATUS_CHOICES = (
        ("active", "Активний"),
        ("expired", "Закінчився"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Клієнт")
    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE, verbose_name="Тренер")

    name = models.CharField("Назва абонемента", max_length=255, default="Абонемент на місяць")
    price = models.DecimalField("Ціна", max_digits=10, decimal_places=2)

    start_date = models.DateField("Дата старту")
    end_date = models.DateField("Дата закінчення")

    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default="active")

    created_at = models.DateTimeField("Дата створення", auto_now_add=True)

    def days_left(self):
        from datetime import date
        return (self.end_date - date.today()).days

    def is_expiring_soon(self):
        return 0 <= self.days_left() <= 5

    def __str__(self):
        return f"{self.client} — {self.name}"    