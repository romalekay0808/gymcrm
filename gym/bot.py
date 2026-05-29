import os
import django
import asyncio
from dotenv import load_dotenv
from asgiref.sync import sync_to_async
from datetime import date, timedelta, datetime
from decimal import Decimal, InvalidOperation
from django.db.models import Sum

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
)


load_dotenv()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gymcrm.settings")
django.setup()

from .models import Trainer, Client, Training, Settlement, Membership


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

CLIENT_NAME, TRAINING_TYPE, TRAINING_COUNT, AMOUNT, MONEY_LOCATION = range(5)
SUB_CLIENT_NAME, SUB_TYPE, SUB_AMOUNT, SUB_START_DATE, SUB_MONEY_LOCATION = range(5, 10)
SETTLEMENT_ACTION, SETTLEMENT_AMOUNT, SETTLEMENT_COMMENT = range(8, 11)
RENEW_TYPE, RENEW_AMOUNT, RENEW_START_DATE, RENEW_LOCATION = range(14, 18)


def to_decimal(value):
    return Decimal(str(value).replace(",", ".").strip())

def parse_date(value):
    return datetime.strptime(value.strip(), "%d.%m.%Y").date()

def money(value):
    return int(value) if value == int(value) else round(value, 2)


def main_menu():
    keyboard = [
        ["📊 Моя статистика"],
        ["🧾 Розрахунок з залом"],
        ["➕ Додати тренування"],
        ["💳 Продати абонемент"],
        ["👥 Мої клієнти"],
        ["🔔 Перевірити абонементи"],
        
        
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


@sync_to_async
def get_trainer_by_telegram_id(telegram_id):
    try:
        return Trainer.objects.get(telegram_id=telegram_id)
    except Trainer.DoesNotExist:
        return None


@sync_to_async
def create_training(
    telegram_id,
    client_name,
    training_type,
    amount,
    money_location,
    membership_start_date=None
):
    trainer = Trainer.objects.get(telegram_id=telegram_id)
    client, _ = Client.objects.get_or_create(name=client_name)

    payment_type = "card" if money_location == "gym_card" else "cash"
    amount_decimal = to_decimal(amount)

    Training.objects.create(
        client=client,
        trainer=trainer,
        training_type=training_type,
        payment_type=payment_type,
        money_location=money_location,
        amount=amount_decimal,
        date=date.today()
    )

    if training_type in ["membership", "ubd_membership"]:
        Membership.objects.create(
            client=client,
            trainer=trainer,
            name="Абонемент УБД" if training_type == "ubd_membership" else "Абонемент на місяць",
            price=amount_decimal,
            start_date=membership_start_date or date.today(),
            end_date=(membership_start_date or date.today()) + timedelta(days=30),
            status="active"
        )

@sync_to_async
def create_training_for_client_id(
    telegram_id,
    client_id,
    training_type,
    amount,
    money_location,
    membership_start_date=None
):
    trainer = Trainer.objects.get(telegram_id=telegram_id)
    client = Client.objects.get(id=client_id)

    payment_type = "card" if money_location == "gym_card" else "cash"
    amount_decimal = to_decimal(amount)

    Training.objects.create(
        client=client,
        trainer=trainer,
        training_type=training_type,
        payment_type=payment_type,
        money_location=money_location,
        amount=amount_decimal,
        date=date.today()
    )

    if training_type in ["membership", "ubd_membership"]:
        Membership.objects.filter(
            client=client,
            trainer=trainer,
            status="active"
        ).update(
            status="expired"
        )
        Membership.objects.create(
            client=client,
            trainer=trainer,
            name="Абонемент УБД" if training_type == "ubd_membership" else "Абонемент на місяць",
            price=amount_decimal,
            start_date=membership_start_date or date.today(),
            end_date=(membership_start_date or date.today()) + timedelta(days=30),
            status="active"
        )        

@sync_to_async
def create_settlement(telegram_id, settlement_type, amount, comment):
    trainer = Trainer.objects.get(telegram_id=telegram_id)

    Settlement.objects.create(
        trainer=trainer,
        settlement_type=settlement_type,
        amount=to_decimal(amount),
        date=date.today(),
        comment=comment
    )


@sync_to_async
def get_trainer_stats(telegram_id, days):
    trainer = Trainer.objects.get(telegram_id=telegram_id)
    start_date = date.today() - timedelta(days=days)

    trainings = Training.objects.filter(trainer=trainer, date__gte=start_date)

    total_income = trainings.aggregate(Sum("amount"))["amount__sum"] or 0
    trainer_salary = sum([training.trainer_income() for training in trainings])

    membership = trainings.filter(training_type="membership")
    ubd = trainings.filter(training_type="ubd_membership")
    personal = trainings.filter(training_type="personal")
    split = trainings.filter(training_type="split")
    single = trainings.filter(training_type="single")

    return {
        "income": total_income,
        "salary": trainer_salary,

        "membership_count": membership.count(),
        "membership_sum": membership.aggregate(Sum("amount"))["amount__sum"] or 0,

        "ubd_count": ubd.count(),
        "ubd_sum": ubd.aggregate(Sum("amount"))["amount__sum"] or 0,

        "personal_count": personal.count(),
        "personal_sum": personal.aggregate(Sum("amount"))["amount__sum"] or 0,

        "split_count": split.count(),
        "split_sum": split.aggregate(Sum("amount"))["amount__sum"] or 0,

        "single_count": single.count(),
        "single_sum": single.aggregate(Sum("amount"))["amount__sum"] or 0,
    }

@sync_to_async
def get_expiring_memberships(telegram_id):

    trainer = Trainer.objects.get(telegram_id=telegram_id)

    memberships = Membership.objects.filter(
        trainer=trainer
    ).order_by("client__name", "-end_date")

    expiring = []
    expired = []

    added_clients = set()

    for membership in memberships:

        if membership.client.id in added_clients:
            continue

        added_clients.add(membership.client.id)

        days_left = membership.days_left()

        item = {
            "client": membership.client.name,
            "name": membership.name,
            "end_date": membership.end_date.strftime("%d.%m.%Y"),
            "days_left": days_left,
        }

        if 0 <= days_left <= 5:
            expiring.append(item)

        elif days_left < 0:
            expired.append(item)

    return {
        "expiring": expiring,
        "expired": expired,
    }

@sync_to_async
def get_trainer_balance(telegram_id):
    trainer = Trainer.objects.get(telegram_id=telegram_id)

    trainings = Training.objects.filter(trainer=trainer)
    settlements = Settlement.objects.filter(trainer=trainer)

    total_sales = trainings.aggregate(Sum("amount"))["amount__sum"] or 0
    trainer_salary = sum([training.trainer_income() for training in trainings])
    gym_part = total_sales - trainer_salary

    money_in_trainer = trainings.filter(money_location="trainer")
    money_on_gym_card = trainings.filter(money_location="gym_card")

    trainer_should_give = sum([training.gym_income() for training in money_in_trainer])
    gym_should_give = sum([training.trainer_income() for training in money_on_gym_card])

    trainer_paid = settlements.filter(
        settlement_type="trainer_to_gym"
    ).aggregate(Sum("amount"))["amount__sum"] or 0

    gym_paid = settlements.filter(
        settlement_type="gym_to_trainer"
    ).aggregate(Sum("amount"))["amount__sum"] or 0

    trainer_debt = trainer_should_give - trainer_paid
    gym_debt = gym_should_give - gym_paid

    final_balance = gym_debt - trainer_debt

    return {
        "total_sales": total_sales,
        "trainer_salary": trainer_salary,
        "gym_part": gym_part,
        "trainer_should_give": trainer_should_give,
        "gym_should_give": gym_should_give,
        "trainer_paid": trainer_paid,
        "gym_paid": gym_paid,
        "final_balance": final_balance,
    }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = str(update.effective_user.id)
    trainer = await get_trainer_by_telegram_id(telegram_id)

    if trainer:
        await update.message.reply_text(
            f"Вітаю, {trainer.name}!",
            reply_markup=main_menu()
        )
    else:
        await update.message.reply_text(
            f"Ваш Telegram ID: {telegram_id}\n"
            f"Передайте цей ID адміністратору для доступу."
        )


async def add_training_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👤 Введіть ім’я клієнта:")
    return CLIENT_NAME


async def add_training_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["client_name"] = update.message.text

    keyboard = [
        ["Персональне тренування"],
        ["Спліт тренування"],
        ["Разове заняття"],
    ]

    await update.message.reply_text(
        "Оберіть тип тренування:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )

    return TRAINING_TYPE


async def add_training_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    types_map = {
        "Персональне тренування": "personal",
        "Спліт тренування": "split",
        "Разове заняття": "single",
    }

    text = update.message.text

    if text not in types_map:
        await update.message.reply_text("Оберіть тип з кнопок.")
        return TRAINING_TYPE

    context.user_data["training_type"] = types_map[text]

    await update.message.reply_text(
        "Введіть кількість тренувань:"
    )

    return TRAINING_COUNT

async def add_training_count(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        count = int(update.message.text)

        if count <= 0:
            raise ValueError

    except:
        await update.message.reply_text(
            "Введіть кількість числом. Наприклад: 10"
        )
        return TRAINING_COUNT

    context.user_data["training_count"] = count

    await update.message.reply_text(
        "Введіть суму за ОДНЕ тренування:"
    )

    return AMOUNT

async def add_training_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        to_decimal(update.message.text)
    except InvalidOperation:
        await update.message.reply_text("Введіть суму числом. Наприклад: 500")
        return AMOUNT

    context.user_data["amount"] = update.message.text

    keyboard = [
        ["👨‍🏫 У тренера"],
        ["💳 На карті залу"],
    ]

    await update.message.reply_text(
        "Де зараз кошти?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )

    return MONEY_LOCATION

async def add_training_money_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    locations = {
        "👨‍🏫 У тренера": "trainer",
        "💳 На карті залу": "gym_card",
    }

    text = update.message.text

    if text not in locations:
        await update.message.reply_text("Оберіть варіант з кнопок.")
        return MONEY_LOCATION

    count = context.user_data["training_count"]

    for _ in range(count):

        await create_training(
            telegram_id=str(update.effective_user.id),
            client_name=context.user_data["client_name"],
            training_type=context.user_data["training_type"],
            amount=context.user_data["amount"],
            money_location=locations[text],
        )

    await update.message.reply_text(
        f"✅ Додано тренувань: {count}",
        reply_markup=main_menu()
    )

    return ConversationHandler.END


async def sell_subscription_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👤 Введіть ім’я клієнта:")
    return SUB_CLIENT_NAME


async def sell_subscription_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sub_client_name"] = update.message.text

    keyboard = [
        ["Абонемент"],
        ["Абонемент УБД"],
    ]

    await update.message.reply_text(
        "Оберіть тип абонемента:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )

    return SUB_TYPE


async def sell_subscription_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    types_map = {
        "Абонемент": "membership",
        "Абонемент УБД": "ubd_membership",
    }

    text = update.message.text

    if text not in types_map:
        await update.message.reply_text("Оберіть тип з кнопок.")
        return SUB_TYPE

    context.user_data["sub_type"] = types_map[text]

    await update.message.reply_text("Введіть суму абонемента:")
    return SUB_AMOUNT


async def sell_subscription_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        to_decimal(update.message.text)
    except InvalidOperation:
        await update.message.reply_text("Введіть суму числом. Наприклад: 1300")
        return SUB_AMOUNT

    context.user_data["sub_amount"] = update.message.text

    await update.message.reply_text(
        "Введіть дату початку абонемента у форматі ДД.ММ.РРРР\n"
        "Наприклад: 28.05.2026"
    )

    return SUB_START_DATE

async def sell_subscription_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        start_date = parse_date(update.message.text)
    except ValueError:
        await update.message.reply_text(
            "Невірний формат дати. Введіть так: 28.05.2026"
        )
        return SUB_START_DATE

    context.user_data["sub_start_date"] = start_date

    keyboard = [
        ["👨‍🏫 У тренера"],
        ["💳 На карті залу"],
    ]

    await update.message.reply_text(
        "Де зараз кошти?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

    return SUB_MONEY_LOCATION

async def sell_subscription_money_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    locations = {
        "👨‍🏫 У тренера": "trainer",
        "💳 На карті залу": "gym_card",
    }

    text = update.message.text

    if text not in locations:
        await update.message.reply_text("Оберіть варіант з кнопок.")
        return SUB_MONEY_LOCATION


    await create_training(
        telegram_id=str(update.effective_user.id),
        client_name=context.user_data["sub_client_name"],
        training_type=context.user_data["sub_type"],
        amount=context.user_data["sub_amount"],
        money_location=locations[text],
        membership_start_date=context.user_data["sub_start_date"],
    )

    await update.message.reply_text(
        "✅ Абонемент успішно продано!",
        reply_markup=main_menu()
    )

    return ConversationHandler.END


async def settlement_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📊 Показати баланс"],
        ["⬆️ Я здав гроші залу"],
        ["⬇️ Зал виплатив мені"],
    ]

    await update.message.reply_text(
        "Оберіть дію:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )

    return SETTLEMENT_ACTION


async def settlement_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    telegram_id = str(update.effective_user.id)

    if text == "📊 Показати баланс":
        balance = await get_trainer_balance(telegram_id)
        final_balance = balance["final_balance"]

        if final_balance > 0:
            result_text = f"⬅️ Зал має виплатити вам: {money(final_balance)} грн"
        elif final_balance < 0:
            result_text = f"➡️ Ви маєте здати залу: {money(abs(final_balance))} грн"
        else:
            result_text = "✅ Ви повністю розраховані з залом"

        await update.message.reply_text(
            f"🧾 Баланс з залом\n\n"
            f"💰 Загальні продажі: {money(balance['total_sales'])} грн\n"
            f"👨‍🏫 Ваша зарплата: {money(balance['trainer_salary'])} грн\n"
            f"🏢 Частина залу: {money(balance['gym_part'])} грн\n\n"
            f"Ви мали здати залу: {money(balance['trainer_should_give'])} грн\n"
            f"Ви вже здали: {money(balance['trainer_paid'])} грн\n\n"
            f"Зал мав виплатити вам: {money(balance['gym_should_give'])} грн\n"
            f"Зал вже виплатив: {money(balance['gym_paid'])} грн\n\n"
            f"{result_text}",
            reply_markup=main_menu()
        )

        return ConversationHandler.END

    if text == "⬆️ Я здав гроші залу":
        context.user_data["settlement_type"] = "trainer_to_gym"
        await update.message.reply_text("Введіть суму, яку ви здали залу:")
        return SETTLEMENT_AMOUNT

    if text == "⬇️ Зал виплатив мені":
        context.user_data["settlement_type"] = "gym_to_trainer"
        await update.message.reply_text("Введіть суму, яку зал виплатив вам:")
        return SETTLEMENT_AMOUNT

    await update.message.reply_text("Оберіть дію з кнопок.")
    return SETTLEMENT_ACTION


async def settlement_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        to_decimal(update.message.text)
    except InvalidOperation:
        await update.message.reply_text("Введіть суму числом. Наприклад: 1000")
        return SETTLEMENT_AMOUNT

    context.user_data["settlement_amount"] = update.message.text

    await update.message.reply_text(
        "Напишіть коментар, за що розрахунок.\n"
        "Наприклад: персональні, абонемент, спліт.\n"
        "Або напишіть '-'"
    )

    return SETTLEMENT_COMMENT

async def settlement_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):

    comment = update.message.text

    if comment.lower() == "пропустити":
        comment = ""

    await create_settlement(
        telegram_id=str(update.effective_user.id),
        settlement_type=context.user_data["settlement_type"],
        amount=context.user_data["settlement_amount"],
        comment=comment,
    )

    await update.message.reply_text(
        "✅ Розрахунок збережено.",
        reply_markup=main_menu()
    )

    return ConversationHandler.END

@sync_to_async
def get_trainer_memberships(telegram_id):
    trainer = Trainer.objects.get(telegram_id=telegram_id)

    memberships = Membership.objects.filter(
        trainer=trainer
    ).order_by("client__name", "-end_date")

    result = []
    added_clients = set()

    for membership in memberships:
        if membership.client.id in added_clients:
            continue

        added_clients.add(membership.client.id)

        days_left = membership.days_left()

        if days_left < 0:
            status_text = f"🔴 Закінчився {abs(days_left)} дн. тому"
        elif days_left <= 5:
            status_text = f"🟡 Скоро закінчиться: {days_left} дн."
        else:
            status_text = f"🟢 Активний: {days_left} дн."

        result.append({
            "client_id": membership.client.id,
            "client": membership.client.name,
            "name": membership.name,
            "end_date": membership.end_date.strftime("%d.%m.%Y"),
            "status_text": status_text,
        })

    return result

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text
    telegram_id = str(update.effective_user.id)

    if text == "📊 Моя статистика":

        context.user_data["stats_mode"] = "stats"

        keyboard = [
            ["📅 Сьогодні"],
            ["📆 Тиждень"],
            ["🗓 Місяць"],
        ]

        await update.message.reply_text(
            "Оберіть період:",
            reply_markup=ReplyKeyboardMarkup(
                keyboard,
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )

    elif text == "👥 Мої клієнти":

        memberships = await get_trainer_memberships(telegram_id)

        if not memberships:

            await update.message.reply_text(
                "У вас поки немає абонементів.",
                reply_markup=main_menu()
            )

            return

        message = "👥 Ваші клієнти та абонементи:\n\n"

        for item in memberships:

            message += (
                f"👤 {item['client']}\n"
                f"🎫 {item['name']}\n"
                f"📅 До: {item['end_date']}\n"
                f"{item['status_text']}\n\n"
            )

        keyboard = []

        for item in memberships:

            if "🟡" in item["status_text"] or "🔴" in item["status_text"]:

                keyboard.append([
                    InlineKeyboardButton(
                        f"🔁 Продовжити: {item['client']}",
                        callback_data=f"renew_{item['client_id']}"
                    )
                ])

        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    elif text == "🔔 Перевірити абонементи":

        data = await get_expiring_memberships(telegram_id)

        expiring = data["expiring"]
        expired = data["expired"]

        if not expiring and not expired:

            await update.message.reply_text(
                "✅ Немає абонементів, які скоро закінчуються або вже закінчились.",
                reply_markup=main_menu()
            )

            return

        message = ""

        if expiring:

            message += "🟡 Скоро закінчуються:\n\n"

            for item in expiring:

                message += (
                    f"👤 {item['client']}\n"
                    f"🎫 {item['name']}\n"
                    f"📅 До: {item['end_date']}\n"
                    f"⏳ Залишилось: {item['days_left']} дн.\n\n"
                )

        if expired:

            message += "🔴 Вже закінчились:\n\n"

            for item in expired:

                message += (
                    f"👤 {item['client']}\n"
                    f"🎫 {item['name']}\n"
                    f"📅 До: {item['end_date']}\n"
                    f"❌ Закінчився {abs(item['days_left'])} дн. тому\n\n"
                )

        await update.message.reply_text(
            message,
            reply_markup=main_menu()
        )

        return



    elif text == "🔔 Перевірити абонементи":
        data = await get_expiring_memberships(telegram_id)

        expiring = data["expiring"]
        expired = data["expired"]

        if not expiring and not expired:
            await update.message.reply_text(
                "✅ Немає абонементів, які скоро закінчуються або вже закінчились.",
                reply_markup=main_menu()
            )
            return

        message = ""

        if expiring:
            message += "🟡 Скоро закінчуються:\n\n"

            for item in expiring:
                message += (
                    f"👤 {item['client']}\n"
                    f"🎫 {item['name']}\n"
                    f"📅 До: {item['end_date']}\n"
                    f"⏳ Залишилось: {item['days_left']} дн.\n\n"
                )

        if expired:
            message += "🔴 Вже закінчились:\n\n"

            for item in expired:
                message += (
                    f"👤 {item['client']}\n"
                    f"🎫 {item['name']}\n"
                    f"📅 До: {item['end_date']}\n"
                    f"❌ Закінчився {abs(item['days_left'])} дн. тому\n\n"
                )

        await update.message.reply_text(
            message,
            reply_markup=main_menu()
        )

    elif text in ["📅 Сьогодні", "📆 Тиждень", "🗓 Місяць"]:
        if text == "📅 Сьогодні":
            days = 0
            period_name = "сьогодні"
        elif text == "📆 Тиждень":
            days = 7
            period_name = "тиждень"
        else:
            days = 30
            period_name = "місяць"

        stats = await get_trainer_stats(telegram_id, days)

        if context.user_data.get("stats_mode") == "stats":
            await update.message.reply_text(
                f"📊 Статистика за {period_name}\n\n"
                f"💳 Абонементи: {stats['membership_count']} • {money(stats['membership_sum'])} грн\n"
                f"🪖 УБД: {stats['ubd_count']} • {money(stats['ubd_sum'])} грн\n"
                f"🏋️ Персональні: {stats['personal_count']} • {money(stats['personal_sum'])} грн\n"
                f"👥 Спліт: {stats['split_count']} • {money(stats['split_sum'])} грн\n"
                f"🎟 Разові: {stats['single_count']} • {money(stats['single_sum'])} грн\n\n"
                f"💰 Загальна сума: {money(stats['income'])} грн\n"
                f"👨‍🏫 Мій дохід: {money(stats['salary'])} грн",
                reply_markup=main_menu()
            )

        elif context.user_data.get("stats_mode") == "income":
            await update.message.reply_text(
                f"💰 Ваш дохід за {period_name}\n\n"
                f"Зароблено: {money(stats['salary'])} грн",
                reply_markup=main_menu()
            )

async def renew_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    client_id = query.data.replace("renew_", "")
    context.user_data["renew_client_id"] = client_id

    keyboard = [
        ["Абонемент"],
        ["Абонемент УБД"],
    ]

    await query.message.reply_text(
        "Оберіть тип абонемента:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

    return RENEW_TYPE


async def renew_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    types_map = {
        "Абонемент": "membership",
        "Абонемент УБД": "ubd_membership",
    }

    text = update.message.text

    if text not in types_map:
        await update.message.reply_text("Оберіть тип з кнопок.")
        return RENEW_TYPE

    context.user_data["renew_type"] = types_map[text]

    await update.message.reply_text("Введіть суму:")
    return RENEW_AMOUNT


async def renew_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        to_decimal(update.message.text)
    except InvalidOperation:
        await update.message.reply_text("Введіть суму числом. Наприклад: 1300")
        return RENEW_AMOUNT

    context.user_data["renew_amount"] = update.message.text

    await update.message.reply_text(
        "Введіть дату початку абонемента у форматі ДД.ММ.РРРР\n"
        "Наприклад: 28.05.2026"
    )

    return RENEW_START_DATE

async def renew_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        start_date = parse_date(update.message.text)
    except ValueError:
        await update.message.reply_text(
            "Невірний формат дати. Введіть так: 28.05.2026"
        )
        return RENEW_START_DATE

    context.user_data["renew_start_date"] = start_date

    keyboard = [
        ["👨‍🏫 У тренера"],
        ["💳 На карті залу"],
    ]

    await update.message.reply_text(
        "Де зараз кошти?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

    return RENEW_LOCATION

async def renew_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    locations = {
        "👨‍🏫 У тренера": "trainer",
        "💳 На карті залу": "gym_card",
    }

    text = update.message.text

    if text not in locations:
        await update.message.reply_text("Оберіть варіант з кнопок.")
        return RENEW_LOCATION

    await create_training_for_client_id(
        telegram_id=str(update.effective_user.id),
        client_id=context.user_data["renew_client_id"],
        training_type=context.user_data["renew_type"],
        amount=context.user_data["renew_amount"],
        money_location=locations[text],
        membership_start_date=context.user_data["renew_start_date"],
    )

    await update.message.reply_text(
        "✅ Абонемент продовжено!",
        reply_markup=main_menu()
    )

    return ConversationHandler.END

@sync_to_async
def get_memberships_for_notifications():
    result = []

    memberships = Membership.objects.select_related(
        "trainer",
        "client"
    ).all()

    for membership in memberships:
        days_left = membership.days_left()

        if days_left == 1 and membership.trainer.telegram_id:
            result.append({
                "telegram_id": membership.trainer.telegram_id,
                "client_name": membership.client.name,
                "end_date": membership.end_date.strftime("%d.%m.%Y"),
            })

    return result


async def check_memberships(context: ContextTypes.DEFAULT_TYPE):
    memberships = await get_memberships_for_notifications()

    for item in memberships:
        try:
            await context.bot.send_message(
                chat_id=item["telegram_id"],
                text=(
                    f"🔔 Нагадування\n\n"
                    f"У клієнта {item['client_name']} абонемент закінчується завтра.\n"
                    f"📅 Дата закінчення: {item['end_date']}"
                )
            )
        except Exception as e:
            print(e)

def run_bot():
    if not TOKEN:
        print("Помилка: TELEGRAM_BOT_TOKEN не знайдено у .env")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.job_queue.run_repeating(
        check_memberships,
        interval=86400,
        first=10,
    )

    add_training_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^➕ Додати тренування$"),
                add_training_start
            )
        ],
        states={
            CLIENT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_training_client)
            ],
            TRAINING_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_training_type)
            ],
            TRAINING_COUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_training_count)
            ],
            AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_training_amount)
            ],
            MONEY_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_training_money_location)
            ],
        },
        fallbacks=[],
    )

    sell_subscription_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^💳 Продати абонемент$"),
                sell_subscription_start
            )
        ],
        states={
            SUB_CLIENT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sell_subscription_client)
            ],
            SUB_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sell_subscription_type)
            ],
            SUB_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sell_subscription_amount)
            ],
            SUB_START_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sell_subscription_start_date)
            ],
            SUB_MONEY_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sell_subscription_money_location)
            ],
        },
        fallbacks=[],
    )

    settlement_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^🧾 Розрахунок з залом$"),
                settlement_start
            )
        ],
        states={
            SETTLEMENT_ACTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, settlement_action)
            ],
            SETTLEMENT_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, settlement_amount)
            ],
            SETTLEMENT_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, settlement_comment)
            ],
        },
        fallbacks=[],
    )

    renew_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(renew_callback, pattern="^renew_")
        ],
        states={
            RENEW_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, renew_type)
            ],
            RENEW_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, renew_amount)
            ],
            RENEW_START_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, renew_start_date)
            ],
            RENEW_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, renew_location)
            ],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(add_training_handler)
    app.add_handler(sell_subscription_handler)
    app.add_handler(settlement_handler)
    app.add_handler(renew_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, buttons))

    print("Telegram bot started...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app.run_polling()


if __name__ == "__main__":
    run_bot()