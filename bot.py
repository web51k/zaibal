import telebot
from telebot import types
import sqlite3
import time
import random
import string
from collections import defaultdict

TOKEN = "5002271783:AAGh1w8WjXuKl9bk1gvZN5buDqXq2wfu0xE/test"
bot = telebot.TeleBot(TOKEN)

# ===== CONSTANTS =====
ADMIN_ID = 2200422849
ADMIN_WALLET = "dQ2200422849"
BURN_ADDRESS = "dQAAA"

# ===== BLACKLIST =====
BLACKLIST = {
    2202454896,
    2202601626,
    2202739986,
    2202982402,
    5001009697,
    5001039850,
    5001100827,
    5001150488,
    5001308853,
    5001348754,
    5001440158,
    5001847871,
    5002134005,
    5002148246,
    5002207580,
    5002331057,
    2201001996,
    2201083969,
    2201288459,
    2201527853,
    2201750711,
    2202240391,
    2202834623,
    5001964465,
    5002486118,
    5002562544
}

def is_blacklisted(uid):
    return uid in BLACKLIST

# ===== DATABASE =====
def create_db():
    with sqlite3.connect("darryl.db") as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS balances (
            wallet TEXT PRIMARY KEY,
            balance INTEGER
        )
        """)

def save_user(uid):
    with sqlite3.connect("darryl.db") as conn:
        conn.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (uid,))

def get_wallet(uid):
    return f"dQ{uid}"

def is_admin(uid=None, wallet=None):
    return uid == ADMIN_ID or wallet == ADMIN_WALLET

def get_balance(wallet):
    if wallet == ADMIN_WALLET:
        return 999999999999999
    with sqlite3.connect("darryl.db") as conn:
        row = conn.execute("SELECT balance FROM balances WHERE wallet=?", (wallet,)).fetchone()
        return row[0] if row else 0

def set_balance(wallet, amount):
    if wallet == ADMIN_WALLET:
        return
    with sqlite3.connect("darryl.db") as conn:
        conn.execute("""
        INSERT INTO balances(wallet, balance)
        VALUES(?, ?)
        ON CONFLICT(wallet) DO UPDATE SET balance=?
        """, (wallet, amount, amount))

def wallet_exists(wallet):
    if wallet in (ADMIN_WALLET, BURN_ADDRESS):
        return True
    if not wallet.startswith("dQ") or not wallet[2:].isdigit():
        return False
    uid = int(wallet[2:])
    with sqlite3.connect("darryl.db") as conn:
        row = conn.execute("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone()
        return row is not None

# ===== ANTI-DDOS / ANTI-FLOOD =====
USER_MSG_COUNT = defaultdict(list)
BLOCKED = {}
BLOCK_TIME = 300  # 5 минут
ANTI_WINDOW = 6   # 6 секунд
ANTI_LIMIT = 40   # сообщений

FORCE_CAPTCHA = set()
CAPTCHA_PASSED = set()
CAPTCHA_DATA = {}
CAPTCHA_MAX_TRIES = 7

def anti_flood(uid):
    now = time.time()
    if uid in BLOCKED and now < BLOCKED[uid]:
        return False
    USER_MSG_COUNT[uid] = [t for t in USER_MSG_COUNT[uid] if now - t < ANTI_WINDOW]
    USER_MSG_COUNT[uid].append(now)
    if len(USER_MSG_COUNT[uid]) > ANTI_LIMIT:
        BLOCKED[uid] = now + BLOCK_TIME
        FORCE_CAPTCHA.add(uid)
        return False
    return True

def gen_captcha():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(6))

def send_captcha(chat_id, uid):
    code = gen_captcha()
    CAPTCHA_DATA[uid] = {"code": code, "tries": 0}
    bot.send_message(
        chat_id,
        f"🛡 Анти-бот проверка\nВведите код:\n`{code}`\nПопыток: {CAPTCHA_MAX_TRIES}",
        parse_mode="Markdown"
    )

# ===== STATES =====
states = {}

# ===== KEYBOARDS =====
def menu_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💸 Перевести D$")
    kb.add("📊 Статистика")
    kb.add("➕ Пополнить баланс")
    kb.add("ℹ️ О нас")
    return kb

def back_kb():
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
def show_menu(chat_id, uid):
    wallet = get_wallet(uid)
    bal = get_balance(wallet)
    bot.send_message(
        chat_id,
        f"💰 Баланс: {bal} D$\n🏦 Кошелёк: `{wallet}`",
        parse_mode="Markdown",
        reply_markup=menu_kb()
    )

# ===== START =====
@bot.message_handler(commands=["start"])
def start(msg):
    uid = msg.from_user.id
    if is_blacklisted(uid):
        return  # игнорим полностью
    if not anti_flood(uid):
        return
    save_user(uid)
    if uid not in CAPTCHA_PASSED or uid in FORCE_CAPTCHA:
        send_captcha(msg.chat.id, uid)
        return
    show_menu(msg.chat.id, uid)

# ===== HANDLER =====
@bot.message_handler(func=lambda m: True)
def handler(msg):
    uid = msg.from_user.id
    chat_id = msg.chat.id
    text = msg.text.strip() if msg.text else ""

    if is_blacklisted(uid):
        return  # молча игнорим

    if not anti_flood(uid):
        return
    save_user(uid)

    # ===== CAPTCHA =====
    if uid in CAPTCHA_DATA:
        data = CAPTCHA_DATA[uid]
        if text.upper() == data["code"]:
            CAPTCHA_PASSED.add(uid)
            FORCE_CAPTCHA.discard(uid)
            CAPTCHA_DATA.pop(uid, None)
            show_menu(chat_id, uid)
            return
        data["tries"] += 1
        if data["tries"] >= CAPTCHA_MAX_TRIES:
            BLOCKED[uid] = time.time() + BLOCK_TIME
            FORCE_CAPTCHA.add(uid)
            CAPTCHA_DATA.pop(uid, None)
            return
        bot.send_message(chat_id, f"❌ Неверно. Осталось попыток: {CAPTCHA_MAX_TRIES - data['tries']}")
        return

    # ===== BACK / MENU =====
    if text in ["⬅️ В меню", "⬅️ Назад"]:
        show_menu(chat_id, uid)
        states.pop(uid, None)
        return

    # ===== POPOLNIT BALANS =====
    if text == "➕ Пополнить баланс":
        bot.send_message(
            chat_id,
            "➕ Напишите в бета Telegram:\n@aktve",
            reply_markup=back_kb()
        )
        return

    # ===== O NAS =====
    if text == "ℹ️ О нас":
        bot.send_message(
            chat_id,
            "Darryl Coin просто токен для бота. Создан от скуки.",
            reply_markup=back_kb()
        )
        return

    # ===== STAT =====
    if text == "📊 Статистика":
        with sqlite3.connect("darryl.db") as conn:
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            wallets = conn.execute("SELECT COUNT(*) FROM balances").fetchone()[0]
        bot.send_message(
            chat_id,
            f"📊 Статистика Darryl Coin\n👤 Пользователей: {users}\n👛 Активных кошельков: {wallets}",
            reply_markup=back_kb()
        )
        return

    # ===== PEREVOD =====
    if text == "💸 Перевести D$":
        states[uid] = {"step": "wallet"}
        bot.send_message(chat_id, "Введите кошелёк (dQ<user_id>)", reply_markup=back_kb())
        return

    if uid in states:
        state = states[uid]

        if state["step"] == "wallet":
            if not wallet_exists(text):
                bot.send_message(chat_id, "❌ Кошелёк не найден", reply_markup=back_kb())
                states.pop(uid)
                return
            state["to"] = text
            state["step"] = "amount"
            bot.send_message(chat_id, "Введите сумму D$", reply_markup=back_kb())
            return

        if state["step"] == "amount":
            if text == "⬅️ Назад":
                state["step"] = "wallet"
                bot.send_message(chat_id, "Введите кошелёк (dQ<user_id>)", reply_markup=back_kb())
                return
            if not text.isdigit() or int(text) <= 0:
                bot.send_message(chat_id, "❌ Неверная сумма", reply_markup=back_kb())
                return
            state["amount"] = int(text)
            state["step"] = "comment"
            bot.send_message(chat_id, "Введите комментарий (можно пропустить):", reply_markup=back_kb())
            return

        if state["step"] == "comment":
            if text == "⬅️ Назад":
                state["step"] = "amount"
                bot.send_message(chat_id, "Введите сумму D$", reply_markup=back_kb())
                return
            state["comment"] = text if text else "нету"
            state["step"] = "confirm"
            bot.send_message(
                chat_id,
                f"⚠️ Подтвердите перевод:\n"
                f"➡ Кошелёк: {state['to']}\n"
                f"💸 Сумма: {state['amount']} D$\n"
                f"💬 Комментарий: {state['comment']}",
                reply_markup=confirm_kb()
            )
            return

        if state["step"] == "confirm":
            if text != "✅ Подтвердить":
                states.pop(uid)
                return
            from_wallet = get_wallet(uid)
            to_wallet = state["to"]
            amount = state["amount"]
            comment = state.get("comment", "нету")
            if not is_admin(uid, from_wallet):
                set_balance(from_wallet, get_balance(from_wallet) - amount)
            if to_wallet != BURN_ADDRESS:
                set_balance(to_wallet, get_balance(to_wallet) + amount)
                to_id = int(to_wallet[2:])
                try:
                    bot.send_message(
                        to_id,
                        f"💰 Пополнение DC кошелька\n"
                        f"Сумма: {amount} D$\n"
                        f"Отправитель: {from_wallet}\n"
                        f"Комментарий: {comment}",
                        reply_markup=back_kb()
                    )
                except:
                    pass
            bot.send_message(chat_id, f"✅ Перевод выполнен!\n{amount} D$ → {to_wallet}", reply_markup=back_kb())
            states.pop(uid)
            return

# ===== ADMIN BROADCAST =====
@bot.message_handler(commands=["broadcast"])
def broadcast(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    text = msg.text.partition(' ')[2]
    if not text:
        bot.send_message(msg.chat.id, "❌ Введите текст для рассылки")
        return
    with sqlite3.connect("darryl.db") as conn:
        users = conn.execute("SELECT user_id FROM users").fetchall()
    for (uid,) in users:
        try:
            bot.send_message(uid, f"📢 Сообщение от админа:\n{text}")
        except:
            pass
    bot.send_message(msg.chat.id, "✅ Рассылка выполнена")

# ===== RUN =====
create_db()
print("🔥 Darryl Coin Bot FINAL v4.4 с BLACKLIST запущен")
bot.infinity_polling()
