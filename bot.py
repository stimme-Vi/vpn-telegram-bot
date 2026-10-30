import logging
import random
import string
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- НАСТРОЙКИ ---
# Токен будет браться из настроек GitHub (мы добавим его туда позже)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
APP_DOWNLOAD_LINK = "https://t.me/stimmeVpn"

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("vpn_users.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, plan TEXT, code TEXT, paid BOOLEAN)''')
    conn.commit()
    return conn

def generate_unique_code(prefix):
    conn = init_db()
    c = conn.cursor()
    while True:
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        code = f"{prefix}-{random_str}"
        c.execute("SELECT code FROM users WHERE code=?", (code,))
        if not c.fetchone():
            conn.close()
            return code

# --- КОМАНДА /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT plan, code, paid FROM users WHERE user_id=?", (user_id,))
    user_data = c.fetchone()
    conn.close()

    if user_data and user_data[2]:
        plan, code, _ = user_data
        await update.message.reply_text(
            f"👋 С возвращением!\n\n"
            f"Ваш тариф: *{plan}*\n"
            f"Ваш код доступа: `{code}`\n\n"
            f"📲 Скачайте приложение: {APP_DOWNLOAD_LINK}\n"
            f"Введите этот код в приложении.",
            parse_mode='Markdown'
        )
    else:
        keyboard = [
            [InlineKeyboardButton("Обычный (300₽)", callback_data='buy_basic')],
            [InlineKeyboardButton("Премиум (500₽)", callback_data='buy_prem')],
            [InlineKeyboardButton("Лучший (800₽)", callback_data='buy_best')],
            [InlineKeyboardButton("📲 Скачать приложение", url=APP_DOWNLOAD_LINK)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Добро пожаловать в *Stimme VPN*! 🚀\n\n"
            "Выберите тариф для покупки:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# --- ОБРАБОТКА КНОПОК ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith('buy_'):
        plan_type = data.split('_')[1]
        
        if plan_type == 'basic':
            plan_name, price, prefix = "Обычный", 300, "BASIC"
        elif plan_type == 'prem':
            plan_name, price, prefix = "Премиум", 500, "PREM"
        else:
            plan_name, price, prefix = "Лучший", 800, "BEST"

        new_code = generate_unique_code(prefix)

        conn = init_db()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (user_id, plan, code, paid) VALUES (?, ?, ?, ?)", 
                  (user_id, plan_name, new_code, False))
        conn.commit()
        conn.close()

        # Ссылка на оплату (пока тестовая)
        payment_url = "https://t.me/stimmeVpn"

        text = (
            f"Вы выбрали: *{plan_name}*\n"
            f"Сумма: *{price} ₽*\n\n"
            f"👇 Оплатите подписку по кнопке ниже.\n"
            f"После оплаты нажмите «Проверить оплату»."
        )
        
        keyboard = [
            [InlineKeyboardButton(f"💳 Оплатить {price} ₽", url=payment_url)],
            [InlineKeyboardButton("✅ Я оплатил (Проверить)", callback_data='check_payment')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    elif data == 'check_payment':
        conn = init_db()
        c = conn.cursor()
        c.execute("UPDATE users SET paid=True WHERE user_id=?", (user_id,))
        conn.commit()
        
        c.execute("SELECT plan, code FROM users WHERE user_id=?", (user_id,))
        plan, code = c.fetchone()
        conn.close()

        await query.edit_message_text(
            f"✅ Оплата подтверждена!\n\n"
            f"Тариф: *{plan}*\n"
            f"Ваш код доступа: `{code}`\n\n"
            f"📲 Скачайте приложение: {APP_DOWNLOAD_LINK}\n"
            f"Введите код в приложении, чтобы начать.",
            parse_mode='Markdown'
        )

# --- ЗАПУСК (Адаптирован для работы на серверах GitHub) ---
if __name__ == '__main__':
    if not BOT_TOKEN:
        print("ОШИБКА: Токен не найден!")
        exit(1)
        
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("Бот успешно запущен на GitHub!")
    
    # drop_pending_updates=True очищает старые сообщения, чтобы бот не завис
    application.run_polling(drop_pending_updates=True)
