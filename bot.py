import logging
import random
import string
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- НАСТРОЙКИ ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
APP_DOWNLOAD_LINK = "https://t.me/StimmeVpn_bot"

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("vpn_users.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, plan TEXT, duration TEXT, code TEXT, paid BOOLEAN)''')
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

# --- ФУНКЦИЯ ДЛЯ ПОКАЗА МЕНЮ (Вызывается при /start и при возврате) ---
async def show_menu(update_or_query, is_edit=False):
    keyboard = [
        # Обычный
        [InlineKeyboardButton("Обычный — 1 мес (300 ₽)", callback_data='buy_basic_1')],
        [InlineKeyboardButton("Обычный — 6 мес (500 ₽)", callback_data='buy_basic_6')],
        [InlineKeyboardButton("Обычный — 1 год (800 ₽)", callback_data='buy_basic_12')],
        # Премиум
        [InlineKeyboardButton("Премиум — 1 мес (500 ₽)", callback_data='buy_prem_1')],
        [InlineKeyboardButton("Премиум — 6 мес (700 ₽)", callback_data='buy_prem_6')],
        [InlineKeyboardButton("Премиум — 1 год (1000 ₽)", callback_data='buy_prem_12')],
        # Лучший
        [InlineKeyboardButton("Лучший — 1 мес (800 ₽)", callback_data='buy_best_1')],
        [InlineKeyboardButton("Лучший — 6 мес (1000 ₽)", callback_data='buy_best_6')],
        [InlineKeyboardButton("Лучший — 1 год (1400 ₽)", callback_data='buy_best_12')],
        # Скачивание
        [InlineKeyboardButton("📲 Скачать приложение", url=APP_DOWNLOAD_LINK)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "🛒 *Магазин Stimme VPN*\n\n"
        "Выберите тариф и срок подписки. После оплаты вы сразу получите код доступа:"
    )
    
    if is_edit:
        await update_or_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update_or_query.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

# --- КОМАНДА /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT plan, duration, code, paid FROM users WHERE user_id=?", (user_id,))
    user_data = c.fetchone()
    conn.close()

    # Если у клиента уже есть оплаченная подписка
    if user_data and user_data[3]:
        plan, duration, code, _ = user_data
        await update.message.reply_text(
            f"👋 С возвращением!\n\n"
            f"Ваш тариф: *{plan}* ({duration})\n"
            f"Ваш код доступа: `{code}`\n\n"
            f"📲 Скачайте приложение: {APP_DOWNLOAD_LINK}\n"
            f"Введите этот код в приложении.",
            parse_mode='Markdown'
        )
    else:
        # Если нет — показываем магазин
        await show_menu(update, is_edit=False)

# --- ОБРАБОТКА КНОПОК ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # Если нажали "Назад"
    if data == 'back_to_menu':
        await show_menu(query, is_edit=True)
        return

    # Если выбрали тариф и срок
    if data.startswith('buy_'):
        parts = data.split('_')
        plan_type = parts[1]
        months = int(parts[2])

        if plan_type == 'basic':
            plan_name, prefix = "Обычный", "BASIC"
            prices = {1: 300, 6: 500, 12: 800}
        elif plan_type == 'prem':
            plan_name, prefix = "Премиум", "PREM"
            prices = {1: 500, 6: 700, 12: 1000}
        else:
            plan_name, prefix = "Лучший", "BEST"
            prices = {1: 800, 6: 1000, 12: 1400}

        price = prices[months]
        duration_text = f"{months} мес." if months < 12 else "1 год"
        
        new_code = generate_unique_code(prefix)

        # Сохраняем в базу
        conn = init_db()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (user_id, plan, duration, code, paid) VALUES (?, ?, ?, ?, ?)", 
                  (user_id, plan_name, duration_text, new_code, False))
        conn.commit()
        conn.close()

        payment_url = "https://t.me/StimmeVpn_bot" # Сюда потом вставим ссылку Robokassa

        text = (
            f"Вы выбрали: *{plan_name}* на *{duration_text}*\n"
            f"Сумма к оплате: *{price} ₽*\n\n"
            f"👇 Нажмите «Оплатить» и переведите средства.\n"
            f"После оплаты нажмите «Я оплатил»."
        )
        
        keyboard = [
            [InlineKeyboardButton(f"💳 Оплатить {price} ₽", url=payment_url)],
            [InlineKeyboardButton("✅ Я оплатил (Проверить)", callback_data='check_payment')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    # Проверка оплаты
    elif data == 'check_payment':
        conn = init_db()
        c = conn.cursor()
        c.execute("UPDATE users SET paid=True WHERE user_id=?", (user_id,))
        conn.commit()
        
        c.execute("SELECT plan, duration, code FROM users WHERE user_id=?", (user_id,))
        plan, duration, code = c.fetchone()
        conn.close()

        await query.edit_message_text(
            f"✅ Оплата подтверждена!\n\n"
            f"Тариф: *{plan}*\n"
            f"Срок: *{duration}*\n"
            f"Ваш код доступа: `{code}`\n\n"
            f"📲 Скачайте приложение: {APP_DOWNLOAD_LINK}\n"
            f"Введите код в приложении, чтобы начать.",
            parse_mode='Markdown'
        )

# --- ЗАПУСК ---
if __name__ == '__main__':
    if not BOT_TOKEN:
        print("ОШИБКА: Токен не найден!")
        exit(1)
        
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("Бот успешно обновлен и запущен!")
    application.run_polling(drop_pending_updates=True)
