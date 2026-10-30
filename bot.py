import logging
import random
import string
import os
import datetime
from supabase import create_client, Client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# --- БЕЗОПАСНЫЕ НАСТРОЙКИ (Данные берутся только из GitHub Secrets) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID_STR = os.environ.get("ADMIN_ID", "0")
ADMIN_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR.isdigit() else 0

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
APP_DOWNLOAD_LINK = "https://t.me/StimmeVpn_bot"

# Проверка: если ключей нет, бот выдаст понятную ошибку, а не сломается
if not BOT_TOKEN or not SUPABASE_URL or not SUPABASE_KEY:
    print("ОШИБКА: Не все секреты добавлены в GitHub!")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def generate_unique_code(prefix):
    while True:
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        code = f"{prefix}-{random_str}"
        response = supabase.table('users').select('code').eq('code', code).execute()
        if not response.data:
            return code

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("💳 Купить подписку", callback_data='menu_buy')],
        [InlineKeyboardButton("👤 О подписке", callback_data='menu_info')],
        [InlineKeyboardButton("📖 Информация", callback_data='menu_about')],
        [InlineKeyboardButton("🆘 Поддержка", callback_data='menu_support')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- КОМАНДА /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Добро пожаловать в *Stimme VPN*!\n\n"
        "Здесь вы можете купить быстрый и безопасный VPN, а также управлять своей подпиской.",
        reply_markup=get_main_menu(),
        parse_mode='Markdown'
    )

# --- ОБРАБОТКА КНОПОК ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == 'menu_back':
        await query.edit_message_text("👋 Главное меню:\nВыберите действие:", reply_markup=get_main_menu(), parse_mode='Markdown')

    elif data == 'menu_buy':
        keyboard = [
            [InlineKeyboardButton("Обычный — 1 мес (300 ₽)", callback_data='buy_basic_1')],
            [InlineKeyboardButton("Обычный — 6 мес (500 ₽)", callback_data='buy_basic_6')],
            [InlineKeyboardButton("Обычный — 1 год (800 ₽)", callback_data='buy_basic_12')],
            [InlineKeyboardButton("Премиум — 1 мес (500 ₽)", callback_data='buy_prem_1')],
            [InlineKeyboardButton("Премиум — 6 мес (700 ₽)", callback_data='buy_prem_6')],
            [InlineKeyboardButton("Премиум — 1 год (1000 ₽)", callback_data='buy_prem_12')],
            [InlineKeyboardButton("Лучший — 1 мес (800 ₽)", callback_data='buy_best_1')],
            [InlineKeyboardButton("Лучший — 6 мес (1000 ₽)", callback_data='buy_best_6')],
            [InlineKeyboardButton("Лучший — 1 год (1400 ₽)", callback_data='buy_best_12')],
            [InlineKeyboardButton("🔙 Назад", callback_data='menu_back')]
        ]
        await query.edit_message_text("Выберите тариф и срок подписки:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == 'menu_info':
        response = supabase.table('users').select('*').eq('user_id', user_id).execute()
        
        if not response.data:
            await query.edit_message_text("У вас пока нет активной подписки. Купите её в меню.", reply_markup=get_main_menu())
            return

        user_data = response.data[0]
        plan = user_data['plan']
        code = user_data['code']
        
        expire_date_str = user_data['expire_date'].replace('Z', '+00:00')
        expire_date = datetime.datetime.fromisoformat(expire_date_str).replace(tzinfo=None)
        now = datetime.datetime.utcnow()

        if now > expire_date:
            text = f"❌ *Подписка истекла!*\n\nТариф: *{plan}*\nКод: `{code}` (больше не работает)\nИстекла: {expire_date.strftime('%d.%m.%Y')}\n\nКупите новую подписку в меню."
        else:
            status = "✅ Активна"
            days_left = (expire_date - now).days
            text = f"👤 *Ваша подписка*\n\nТариф: *{plan}*\nКод: `{code}`\nСтатус: {status}\nДействует до: *{expire_date.strftime('%d.%m.%Y %H:%M')}*\nОсталось дней: *{days_left}*"

        await query.edit_message_text(text, reply_markup=get_main_menu(), parse_mode='Markdown')

    elif data == 'menu_about':
        text = "📖 *О сервисе Stimme VPN*\n\nНаш VPN обеспечивает максимальную скорость и безопасность.\n\n✅ Доступ к 80 серверам\n✅ Поддержка в играх и стриминге\n✅ Полное скрытие вашего IP-адреса"
        await query.edit_message_text(text, reply_markup=get_main_menu(), parse_mode='Markdown')

    elif data == 'menu_support':
        context.user_data['awaiting_support'] = True
        await query.edit_message_text("🆘 *Служба поддержки*\n\nНапишите ваш вопрос одним сообщением, и мы скоро ответим!", parse_mode='Markdown')

    elif data.startswith('buy_'):
        parts = data.split('_')
        plan_type, months = parts[1], int(parts[2])

        if plan_type == 'basic':
            plan_name, prefix, prices = "Обычный", "BASIC", {1: 300, 6: 500, 12: 800}
        elif plan_type == 'prem':
            plan_name, prefix, prices = "Премиум", "PREM", {1: 500, 6: 700, 12: 1000}
        else:
            plan_name, prefix, prices = "Лучший", "BEST", {1: 800, 6: 1000, 12: 1400}

        price = prices[months]
        new_code = generate_unique_code(prefix)
        
        days_to_add = months * 30
        expire_date = (datetime.datetime.utcnow() + datetime.timedelta(days=days_to_add)).isoformat()

        supabase.table('users').upsert({
            'user_id': user_id,
            'plan': plan_name,
            'code': new_code,
            'expire_date': expire_date
        }).execute()

        text = f"Вы выбрали: *{plan_name}*\nСумма: *{price} ₽*\nСрок: *{days_to_add} дней*\n\n👇 Оплатите и нажмите 'Я оплатил'."
        
        keyboard = [
            [InlineKeyboardButton(f"💳 Оплатить {price} ₽", url="https://t.me/StimmeVpn_bot")],
            [InlineKeyboardButton("✅ Я оплатил", callback_data='check_payment')],
            [InlineKeyboardButton("🔙 Назад", callback_data='menu_buy')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data == 'check_payment':
        response = supabase.table('users').select('*').eq('user_id', user_id).execute()
        user_data = response.data[0]
        
        expire_date_str = user_data['expire_date'].replace('Z', '+00:00')
        expire_dt = datetime.datetime.fromisoformat(expire_date_str).replace(tzinfo=None)

        text = f"✅ *Оплата принята!*\n\nТариф: *{user_data['plan']}*\nВаш код: `{user_data['code']}`\nАктивна до: *{expire_dt.strftime('%d.%m.%Y')}*\n\n📲 Скачайте приложение: {APP_DOWNLOAD_LINK}"
        await query.edit_message_text(text, reply_markup=get_main_menu(), parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if context.user_data.get('awaiting_support'):
        context.user_data['awaiting_support'] = False
        await update.message.reply_text("✅ Сообщение отправлено в поддержку!", reply_markup=get_main_menu())
        if ADMIN_ID != 0:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🆘 *Поддержка*\nОт: `{user_id}`\n\n{text}", parse_mode='Markdown')

    elif user_id == ADMIN_ID:
        try:
            target_id, reply_text = text.split(' ', 1)
            await context.bot.send_message(chat_id=int(target_id), text=f"✉️ *Ответ поддержки:*\n\n{reply_text}", parse_mode='Markdown')
            await update.message.reply_text("✅ Ответ отправлен клиенту.")
        except ValueError:
            await update.message.reply_text("❌ Ошибка. Напишите: ID_КЛИЕНТА Текст ответа")

if __name__ == '__main__':
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен!")
    application.run_polling(drop_pending_updates=True)
