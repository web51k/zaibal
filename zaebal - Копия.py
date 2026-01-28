import telebot
from telebot import types
import json
import os
import random

BOT_TOKEN = "5002271783:AAGh1w8WjXuKl9bk1gvZN5buDqXq2wfu0xE/test"
DATA_FILE = "wallets.json"
BURN_ADDRESS = "dQAAA"
GOD_USERNAME = "aktve"
GOD_WALLET = "dQ34394875"

bot = telebot.TeleBot(BOT_TOKEN)

# ======== utils ========
def load():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_wallet(user):
    data = load()
    uid = str(user.id)

    if uid not in data:
        data[uid] = {
            "address": "dQ" + str(random.randint(10000000, 99999999)),
            "balance": 0
        }

    # MRVUDIK или конкретный кошелёк — огромный баланс
    if user.username == GOD_USERNAME or data[uid]["address"] == GOD_WALLET:
        data[uid]["balance"] = 999_999_999_999

    save(data)
    return data[uid]

user_state = {}

# ======== клавиатуры ========
def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 Мой баланс")
    kb.add("💸 Перевести D$")
    kb.add("➕ Пополнить баланс")
    kb.add("ℹ️ О нас")
    return kb

def nav_kb(step):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if step != "address":
        kb.add("🔙 Назад")
    if step == "comment":
        kb.add("⏭ Пропустить")
    kb.add("❌ Отмена")
    return kb

# ======== start / баланс ========
@bot.message_handler(commands=["start"])
def start(msg):
    w = get_wallet(msg.from_user)
    bot.send_message(
        msg.chat.id,
        f"💰 **Баланс:** {w['balance']} D$\n"
        f"📮 **Адрес кошелька:**\n`{w['address']}`",
        reply_markup=menu(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "💰 Мой баланс")
def my_balance(msg):
    w = get_wallet(msg.from_user)
    bot.send_message(
        msg.chat.id,
        f"💰 **Ваш баланс:** {w['balance']} D$\n"
        f"📮 **Адрес кошелька:**\n`{w['address']}`",
        reply_markup=menu(),
        parse_mode="Markdown"
    )

# ======== меню ========
@bot.message_handler(func=lambda m: m.text == "ℹ️ О нас")
def about(msg):
    bot.send_message(
        msg.chat.id,
        "ℹ️ **Darryl Coin** — для лёгкого и быстрого обмена D$.\n"
        "Если нравится — расскажи друзьям 😎",
        reply_markup=menu(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "➕ Пополнить баланс")
def topup(msg):
    bot.send_message(
        msg.chat.id,
        "➕ Для пополнения напиши в оригинальном Telegram:\n@mrVudik",
        reply_markup=menu()
    )

@bot.message_handler(func=lambda m: m.text == "💸 Перевести D$")
def transfer_start(msg):
    user_state[msg.from_user.id] = {"step": "address"}
    bot.send_message(
        msg.chat.id,
        "✍️ Введите адрес кошелька получателя:",
        reply_markup=nav_kb("address")
    )

# ======== перевод ========
@bot.message_handler(func=lambda m: m.from_user.id in user_state)
def transfer_flow(msg):
    uid = msg.from_user.id
    text = msg.text.strip()
    state = user_state[uid]
    data = load()
    wallet = get_wallet(msg.from_user)

    # ❌ Отмена
    if text == "❌ Отмена":
        user_state.pop(uid)
        bot.send_message(msg.chat.id, "❌ Перевод отменён.", reply_markup=menu())
        return

    # 🔙 Назад
    if text == "🔙 Назад":
        if state["step"] == "amount":
            state["step"] = "address"
            bot.send_message(msg.chat.id, "✍️ Введите адрес кошелька:", reply_markup=nav_kb("address"))
            return
        if state["step"] == "comment":
            state["step"] = "amount"
            bot.send_message(msg.chat.id, "💸 Введите сумму D$:", reply_markup=nav_kb("amount"))
            return

    # ===== шаги =====
    if state["step"] == "address":
        state["to"] = text
        state["step"] = "amount"
        bot.send_message(msg.chat.id, "💸 Введите сумму D$:", reply_markup=nav_kb("amount"))
        return

    if state["step"] == "amount":
        if not text.isdigit() or int(text) <= 0:
            bot.send_message(msg.chat.id, "❗ Введите корректное число 😅", reply_markup=nav_kb("amount"))
            return
        state["amount"] = int(text)
        state["step"] = "comment"
        bot.send_message(msg.chat.id, "📝 Введите комментарий к переводу:", reply_markup=nav_kb("comment"))
        return

    if state["step"] == "comment":
        comment = "" if text == "⏭ Пропустить" else text
        to = state["to"]
        amount = state["amount"]

        # проверка баланса
        if wallet["balance"] < amount and msg.from_user.username != GOD_USERNAME:
            bot.send_message(msg.chat.id, "❌ Недостаточно средств 😬", reply_markup=menu())
            user_state.pop(uid)
            return

        receiver_id = None
        for k, v in data.items():
            if v["address"] == to:
                receiver_id = k
                break

        if to != BURN_ADDRESS and receiver_id is None:
            bot.send_message(msg.chat.id, "❌ **Кошёлек не найден!** 🧐", reply_markup=menu(), parse_mode="Markdown")
            user_state.pop(uid)
            return

        # списание и начисление
        if msg.from_user.username != GOD_USERNAME:
            wallet["balance"] -= amount

        if to != BURN_ADDRESS:
            data[receiver_id]["balance"] += amount
            bot.send_message(
                int(receiver_id),
                f"📥 **Пополнение Darryl Coin!**\n\n💰 Сумма: {amount} D$\n📮 Отправитель: `{wallet['address']}`\n📝 Комментарий: {comment or '—'}",
                parse_mode="Markdown"
            )

        save(data)

        bot.send_message(
            msg.chat.id,
            f"✅ **Перевод выполнен!**\n💸 {amount} D$ → `{to}` 😎",
            reply_markup=menu(),
            parse_mode="Markdown"
        )
        user_state.pop(uid)

# ======== запуск ========
print("🚀 Darryl Coin bot запущен")
bot.infinity_polling()