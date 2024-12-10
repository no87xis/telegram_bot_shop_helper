import os
import datetime
import random
import string
from io import BytesIO

import mysql.connector
from fpdf import FPDF
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters, ConversationHandler
)

# Данные для подключения к MySQL
DB_HOST = 'localhost'
DB_USER = 'chatbot_user'
DB_PASS = 'XRaRziqAq9Pf41pB'
DB_NAME = 'chatbot_db'
DB_PRFX = 'bot_'  # Префикс таблиц

BOT_TOKEN = "YOUR_BOT_TOKEN"

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
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )

def init_db():
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
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(f"INSERT INTO {DB_PRFX}users (telegram_id, role) VALUES (%s,%s)", (telegram_id, role))
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    c.close()
    conn.close()

def get_user_role(telegram_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(f"SELECT role FROM {DB_PRFX}users WHERE telegram_id=%s", (telegram_id,))
    row = c.fetchone()
    c.close()
    conn.close()
    if row:
        return row[0]
    return None

def add_product(name, qty):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(f"INSERT INTO {DB_PRFX}products (name, quantity) VALUES (%s,%s)", (name, qty))
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    c.close()
    conn.close()

def get_all_products():
    conn = get_connection()
    c = conn.cursor()
    c.execute(f"SELECT name, quantity FROM {DB_PRFX}products")
    rows = c.fetchall()
    c.close()
    conn.close()
    return rows

def create_order(client_name, product_name, quantity, sum_paid):
    order_id = generate_order_id()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute(f"""
            INSERT INTO {DB_PRFX}orders (order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (order_id, client_name, product_name, quantity, now, "Оплачено", sum_paid, None, None))
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    c.close()
    conn.close()
    return order_id

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = get_user_role(update.effective_user.id)
    if role is None:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT COUNT(*) FROM {DB_PRFX}users")
        count = c.fetchone()[0]
        c.close()
        conn.close()
        if count == 0:
            add_user(update.effective_user.id, "admin")
            await update.message.reply_text("Вы стали админом, так как это первый запуск бота.")
        else:
            await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
            return ConversationHandler.END
    return await update.message.reply_text("Добро пожаловать в бота!")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()

if __name__ == "__main__":
    main()
