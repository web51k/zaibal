import telebot
from telebot import types
import sqlite3

TOKEN = "5002271783:AAGh1w8WjXuKl9bk1gvZN5buDqXq2wfu0xE/test"
bot = telebot.TeleBot(TOKEN)

ADMIN_ID = 2200422849
ADMIN_WALLET = "dQ2200422849"
BURN_ADDRESS = "dQAAA"

states = {}

# ===== DATABASE FUNCTIONS =====
def create_db():
    with sqlite3.connect("darryl.db") as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS balances (
            wallet TEXT PRIMARY KEY,
            balance INTEGER
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
        """)

def save_user(user_id):
    with sqlite3.connect("darryl.db") as conn:
        conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))

def get_wallet(user_id: int) -> str:
    return f"dQ{user_id}"

def is_admin(user_id=None, wallet=None) -> bool:
    return user_id == ADMIN_ID or wallet == ADMIN_WALLET

def get_balance(wallet: str) -> int:
    if is_admin(wallet=wallet):
        return 9999999999999
    with sqlite3.connect("darryl.db") as conn:
        row = conn.execute("SELECT balance FROM balances WHERE wallet=?", (wallet,)).fetchone()
        return row[0] if row else 0

def set_balance(wallet: str, amount: int):
    if is_admin(wallet=wallet):
        return
    with sqlite3.connect("darryl.db") as conn:
        conn.execute(
            "INSERT INTO balances(wallet, balance) VALUES(?, ?) "
            "ON CONFLICT(wallet) DO UPDATE SET balance=?",
            (wallet, amount, amount)
        )

def wallet_exists(wallet: str) -> bool:
    if wallet in (ADMIN_WALLET, BURN_ADDRESS):
        return True
    if not wallet.startswith("dQ") or not wallet[2:].isdigit():
        return False
    uid = int(wallet[2:])
    with sqlite3.connect("darryl.db") as conn:
        row = conn.execute("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone()
        return row is not None

# ===== KEYBOARDS =====
def menu_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💸 Перевести D$")
    kb.add("➕ Пополнить баланс")
    kb.add("ℹ️ О нас")
    return kb

def menu_only_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⬅️ В меню")
    return kb

def amount_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("⬅️ Назад")
    kb.add("⬅️ В меню")
    return kb

def confirm_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Подтвердить")
    kb.add("❌ Отмена")
    return kb

# ===== MENU =====
def show_menu(chat_id, user_id):
    wallet = get_wallet(user_id)
    balance = get_balance(wallet)
    bot.send_message(
        chat_id,
        f"💰 Баланс: {balance} D$\n"
        f"🏦 Кошелёк: `{wallet}`",
        parse_mode="Markdown",
        reply_markup=menu_kb()
    )

# ===== START =====
@bot.message_handler(commands=["start"])
def start(msg):
    save_user(msg.from_user.id)
    show_menu(msg.chat.id, msg.from_user.id)

# ===== HANDLER =====
@bot.message_handler(func=lambda m: True)
def handler(msg):
    uid = msg.from_user.id
    chat_id = msg.chat.id
    text = msg.text.strip()

    save_user(uid)

    # ---- В МЕНЮ ----
    if text == "⬅️ В меню":
        states.pop(uid, None)
        show_menu(chat_id, uid)
        return

    # ---- ОТМЕНА ----
    if text == "❌ Отмена":
        states.pop(uid, None)
        bot.send_message(chat_id, "❌ Действие отменено", reply_markup=menu_only_kb())
        return

    # ---- ПЕРЕВОД ----
    if text == "💸 Перевести D$":
        states[uid] = {"step": "wallet"}
        bot.send_message(
            chat_id,
            "✍️ Введите адрес кошелька (dQ<user_id>):",
            reply_markup=menu_only_kb()
        )
        return

    # ---- ПОПОЛНИТЬ ----
    if text == "➕ Пополнить баланс":
        bot.send_message(
            chat_id,
            "➕ Напишите в бета Telegram:\n@aktve",
            reply_markup=menu_only_kb()
        )
        return

    # ---- О НАС ----
    if text == "ℹ️ О нас":
        bot.send_message(
            chat_id,
            "ℹ️ Darryl coin — внутренняя валюта для обмена D$.\n"
            "Создано просто так🔥",
            reply_markup=menu_only_kb()
        )
        return

    # ---- STATE ----
    if uid not in states:
        return

    state = states[uid]

    # ===== STEP: WALLET =====
    if state["step"] == "wallet":
        if not wallet_exists(text):
            bot.send_message(
                chat_id,
                "❌ Кошелёк не найден.\nПользователь ещё не писал боту.",
                reply_markup=menu_only_kb()
            )
            states.pop(uid)
            return

        state["to"] = text
        state["step"] = "amount"
        bot.send_message(
            chat_id,
            "💵 Введите сумму D$:",
            reply_markup=amount_kb()
        )
        return

    # ===== STEP: AMOUNT =====
    if state["step"] == "amount":
        if text == "⬅️ Назад":
            state["step"] = "wallet"
            bot.send_message(
                chat_id,
                "✍️ Введите адрес кошелька (dQ...):",
                reply_markup=menu_only_kb()
            )
            return

        if not text.isdigit() or int(text) <= 0:
            bot.send_message(chat_id, "❌ Введите корректную сумму", reply_markup=menu_only_kb())
            return

        amount = int(text)
        from_wallet = get_wallet(uid)

        if not is_admin(uid, from_wallet) and get_balance(from_wallet) < amount:
            bot.send_message(chat_id, "❌ Недостаточно средств", reply_markup=menu_only_kb())
            states.pop(uid)
            return

        state["amount"] = amount
        state["step"] = "confirm"

        bot.send_message(
            chat_id,
            f"⚠️ Подтвердите перевод:\n\n"
            f"➡️ Кошелёк: {state['to']}\n"
            f"💸 Сумма: {amount} D$",
            reply_markup=confirm_kb()
        )
        return

    # ===== STEP: CONFIRM =====
    if state["step"] == "confirm":
        if text == "❌ Отмена":
            states.pop(uid, None)
            bot.send_message(chat_id, "❌ Перевод отменён", reply_markup=menu_only_kb())
            return

        if text != "✅ Подтвердить":
            return

        from_wallet = get_wallet(uid)
        to_wallet = state["to"]
        amount = state["amount"]

        if not is_admin(uid, from_wallet):
            set_balance(from_wallet, get_balance(from_wallet) - amount)

        if to_wallet != BURN_ADDRESS:
            set_balance(to_wallet, get_balance(to_wallet) + amount)
            to_id = int(to_wallet[2:])
            bot.send_message(
                to_id,
                f"💰 Пополнение DC кошелька!\n"
                f"Сумма: {amount} D$\n"
                f"Отправитель: {from_wallet}"
            )

        bot.send_message(
            chat_id,
            f"✅ Перевод выполнен!\n{amount} D$ → {to_wallet}",
            reply_markup=menu_only_kb()
        )

        states.pop(uid)

# ===== RUN =====
create_db()
print("🔥 Darryl Coin Bot запущен (FIXED, CONFIRM ENABLED)")
bot.infinity_polling()
