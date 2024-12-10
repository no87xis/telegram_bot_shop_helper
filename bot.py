import os
import datetime
import random
import string
from io import BytesIO
import logging

import mysql.connector
from fpdf import FPDF
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters, ConversationHandler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Данные для подключения к MySQL
DB_HOST = 'localhost'
DB_USER = 'chatbot_user'
DB_PASS = 'XRaRziqAq9Pf41pB'
DB_NAME = 'chatbot_db'
DB_PRFX = 'bot_'  # Префикс таблиц

BOT_TOKEN = "7824760453:AAGuV6vdRhNhvot3xIIgPK0WsnEE8KX5tHI"

(
    CHOOSING_MAIN_MENU,
    ADDING_PRODUCT_NAME_STOCK,
    ADDING_PRODUCT_QTY_STOCK,
    ENTERING_CLIENT_NAME,
    SELECTING_PRODUCT_FOR_ORDER,
    ENTERING_ORDER_QTY,
    ENTERING_ORDER_SUM,
    CONFIRM_ORDER,
    ENTERING_SEARCH_ORDER_ID_LAST6,
    ADDING_USER_TELEGRAM_ID,
    ADDING_USER_ROLE,
    SELECTING_REPORT_TYPE,
    SELECTING_USER_ACTION,
    VIEWING_HISTORY_ORDERS,
    CONFIRM_ISSUE
) = range(15)

def get_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME
        )
        logger.info("Успешное подключение к базе данных")
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Ошибка подключения к базе данных: {err}")
        raise

def init_db():
    try:
        conn = get_connection()
        c = conn.cursor()

        # Создаем таблицы
        c.execute(f"""
        CREATE TABLE IF NOT EXISTS {DB_PRFX}users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            telegram_id BIGINT UNIQUE,
            role VARCHAR(50)
        )
        """)

        c.execute(f"""
        CREATE TABLE IF NOT EXISTS {DB_PRFX}products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE,
            quantity INT
        )
        """)

        c.execute(f"""
        CREATE TABLE IF NOT EXISTS {DB_PRFX}orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id VARCHAR(255) UNIQUE,
            client_name VARCHAR(255),
            product_name VARCHAR(255),
            quantity INT,
            date VARCHAR(255),
            status VARCHAR(50),
            sum_paid DOUBLE,
            issue_date VARCHAR(255),
            issuer_id BIGINT
        )
        """)

        conn.commit()
        logger.info("Таблицы успешно инициализированы")
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при инициализации базы данных: {err}")
    finally:
        c.close()
        conn.close()

# Инициализируем базу данных
init_db()

def generate_order_id():
    now = datetime.datetime.now()
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    random_part = ''.join(random.choices(string.digits, k=6))
    return f"ORD{date_part}-{time_part}-{random_part}"

def add_user(telegram_id, role):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"INSERT INTO {DB_PRFX}users (telegram_id, role) VALUES (%s,%s)", (telegram_id, role))
        conn.commit()
        logger.info(f"Пользователь с telegram_id {telegram_id} добавлен с ролью {role}")
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при добавлении пользователя: {err}")
    finally:
        c.close()
        conn.close()

def get_user_role(telegram_id):
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT role FROM {DB_PRFX}users WHERE telegram_id=%s", (telegram_id,))
        row = c.fetchone()
        return row[0] if row else None
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении роли пользователя: {err}")
        return None
    finally:
        c.close()
        conn.close()

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("Добавить товар", callback_data="add_product")],
        [InlineKeyboardButton("Сделать предоплату", callback_data="make_payment")],
        [InlineKeyboardButton("Проверить заказ по ID", callback_data="check_order")],
        [InlineKeyboardButton("Отчёты", callback_data="reports")],
        [InlineKeyboardButton("Очистка старых заказов", callback_data="clear_orders")],
        [InlineKeyboardButton("Добавить пользователя", callback_data="add_user")],
        [InlineKeyboardButton("Список товаров", callback_data="list_products")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = get_user_role(update.effective_user.id)
    if role is None:
        try:
            conn = get_connection()
            c = conn.cursor()
            c.execute(f"SELECT COUNT(*) FROM {DB_PRFX}users")
            count = c.fetchone()[0]
            if count == 0:
                add_user(update.effective_user.id, "admin")
                await update.message.reply_text("Вы стали админом, так как это первый запуск бота.")
            else:
                await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
                return ConversationHandler.END
        except mysql.connector.Error as err:
            logger.error(f"Ошибка при проверке пользователей: {err}")
        finally:
            c.close()
            conn.close()
    await show_main_menu(update, context)

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()

if __name__ == "__main__":
    main()
