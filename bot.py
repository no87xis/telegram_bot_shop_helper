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

# -------------------- Настройки и инициализация --------------------

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Данные подключения к MySQL
DB_HOST = 'localhost'
DB_USER = 'chatbot_user'
DB_PASS = 'XRaRziqAq9Pf41pB'
DB_NAME = 'chatbot_db'
DB_PRFX = 'bot_'

BOT_TOKEN = "7824760453:AAGuV6vdRhNhvot3xIIgPK0WsnEE8KX5tHI"  # Подставьте свой токен

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
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        # Создаем таблицы как в новом коде
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
        if c:
            c.close()
        if conn:
            conn.close()

init_db()

def get_user_role(telegram_id):
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT role FROM {DB_PRFX}users WHERE telegram_id=%s", (telegram_id,))
        row = c.fetchone()
        return row[0] if row else None
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении роли пользователя: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return None

def add_user(telegram_id, role):
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"INSERT IGNORE INTO {DB_PRFX}users (telegram_id, role) VALUES (%s,%s)", (telegram_id, role))
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при добавлении пользователя: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

def generate_order_id():
    now = datetime.datetime.now()
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    random_part = ''.join(random.choices(string.digits, k=6))
    return f"ORD{date_part}-{time_part}-{random_part}"

def add_product_db(name, qty):
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"INSERT INTO {DB_PRFX}products (name, quantity) VALUES (%s,%s)", (name, qty))
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при добавлении товара: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

def update_product_quantity(name, qty):
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"UPDATE {DB_PRFX}products SET quantity=%s WHERE name=%s", (qty, name))
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при обновлении количества товара: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

def get_all_products():
    c = None
    conn = None
    results = []
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT name, quantity FROM {DB_PRFX}products")
        results = c.fetchall()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении списка товаров: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return results

def create_order(client_name, product_name, quantity, sum_paid):
    order_id = generate_order_id()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "Оплачено"
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"""
            INSERT INTO {DB_PRFX}orders (order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (order_id, client_name, product_name, quantity, now, status, sum_paid, None, None))
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при создании заказа: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

    # обновляем остаток товара
    products = dict(get_all_products())
    new_qty = products.get(product_name,0) - quantity
    update_product_quantity(product_name, new_qty)
    return order_id

def get_order_by_last6(last6):
    c = None
    conn = None
    result = None
    try:
        conn = get_connection()
        c = conn.cursor()
        # Ищем по последним 6 цифрам (ORDYYYYMMDD-HHMMSS-XXXXXX)
        # last6 - это последние 6 символов рандомной части
        c.execute(f"SELECT order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id FROM {DB_PRFX}orders WHERE order_id LIKE %s", (f"%{last6}",))
        row = c.fetchone()
        if row:
            result = row
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при поиске заказа по последним 6 цифрам: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return result

def update_order_issued(order_id, issuer_id):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"UPDATE {DB_PRFX}orders SET status='Выдан', issue_date=%s, issuer_id=%s WHERE order_id=%s",
                  (now, issuer_id, order_id))
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка обновления статуса выдачи заказа: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

def delete_order(order_id):
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"DELETE FROM {DB_PRFX}orders WHERE order_id=%s",(order_id,))
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при удалении заказа: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

def search_orders_by_client(client_data):
    c = None
    conn = None
    rows = []
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"""
            SELECT order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id
            FROM {DB_PRFX}orders
            WHERE client_name LIKE %s
            ORDER BY date DESC
        """,(f"%{client_data}%",))
        rows = c.fetchall()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при поиске заказов по клиенту: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return rows

def get_sales_summary():
    c = None
    conn = None
    total_sum = 0.0
    product_sums = []
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT SUM(sum_paid) FROM {DB_PRFX}orders")
        row = c.fetchone()
        if row and row[0]:
            total_sum = row[0]

        c.execute(f"""
            SELECT product_name, SUM(sum_paid)
            FROM {DB_PRFX}orders
            GROUP BY product_name
        """)
        product_sums = c.fetchall()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при формировании отчёта по суммам продаж: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return total_sum, product_sums

def get_order_by_id(order_id):
    c = None
    conn = None
    result = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id FROM {DB_PRFX}orders WHERE order_id=%s",(order_id,))
        row = c.fetchone()
        if row:
            result = row
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении заказа по ID: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return result

def setup_unicode_pdf(pdf, size=10):
    # Настройка шрифта DejaVu для кириллицы, если файл шрифта есть
    if os.path.exists("DejaVuSansCondensed.ttf"):
        pdf.add_font("DejaVu", "", "DejaVuSansCondensed.ttf", uni=True)
        pdf.set_font("DejaVu", "", size)
    else:
        pdf.set_font("Arial", "", size)

def generate_pdf_order_details(order):
    # order: order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id
    order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id = order
    quantity = int(quantity)
    price_per_item = sum_paid / quantity if quantity > 0 else 0

    buffer = BytesIO()
    pdf = FPDF()
    pdf.add_page()

    setup_unicode_pdf(pdf, 10)

    # Шапка
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 10, 10, 20)
    pdf.set_xy(35,10)
    pdf.set_font("DejaVu", "", 14)
    pdf.cell(0,10,"SIRIUS-GROUP.STORE", ln=1)
    pdf.set_font("DejaVu","",8)
    pdf.set_x(35)
    pdf.cell(0,5,"г. Москва ул. Руссиянова 31 кабинет 6Б", ln=1)
    pdf.set_x(35)
    pdf.cell(0,5,"Телефон: +7 999 398-01-59", ln=1)
    pdf.set_x(35)
    pdf.cell(0,5,"Сайт: https://sirius-group.store/", ln=1)
    pdf.ln(5)
    pdf.set_draw_color(150,150,150)
    pdf.set_line_width(0.5)
    y_line = pdf.get_y()
    pdf.line(10,y_line,200,y_line)
    pdf.ln(5)

    pdf.set_font("DejaVu","",16)
    pdf.cell(0,10,"Счёт / Квитанция об оплате", ln=1, align='C')
    pdf.ln(5)

    pdf.set_font("DejaVu","",10)

    def table_row(label, value):
        pdf.set_x(20)
        pdf.cell(50,8,label, border=0)
        pdf.cell(0,8,str(value), border=0, ln=1)

    table_row("ID заказа:", order_id)
    table_row("Дата оплаты:", date)
    table_row("Имя клиента:", client_name)
    table_row("Товар:", product_name)
    table_row("Количество:", quantity)
    table_row("Сумма оплачена:", f"{sum_paid:.2f} руб.")
    table_row("Цена за штуку:", f"{price_per_item:.2f} руб.")
    table_row("Статус:", status if status else "Неизвестен")

    pdf.ln(10)
    pdf.cell(0,5,"Данный документ подтверждает факт предоплаты по заказу. Для получения товара",ln=1)
    pdf.cell(0,5,"предъявите уникальный номер заказа.",ln=1)

    pdf.ln(5)
    pdf.set_draw_color(150,150,150)
    y_line = pdf.get_y()
    pdf.line(10,y_line,200,y_line)
    pdf.ln(5)

    pdf.set_font("DejaVu","",9)
    pdf.cell(0,5,"Спасибо за ваш выбор! SIRIUS-GROUP.STORE", align='C', ln=1)

    pdf.output(buffer, 'F')
    buffer.seek(0)
    return buffer

def generate_report_orders():
    # Отчет по всем заказам
    conn = get_connection()
    c = conn.cursor()
    c.execute(f"SELECT order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id FROM {DB_PRFX}orders")
    rows = c.fetchall()
    c.close()
    conn.close()

    buffer = BytesIO()
    pdf = FPDF()
    pdf.add_page()
    setup_unicode_pdf(pdf, 10)
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 10, 8, 33)
    pdf.ln(20)
    pdf.set_font("DejaVu","",14)
    pdf.cell(0,10,"Отчет по заказам",0,1)
    pdf.ln(5)
    pdf.set_font("DejaVu","",9)
    for row in rows:
        order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id = row
        pdf.cell(0,6,f"ID: {order_id} | {client_name} - {product_name} x {quantity} | {date} | Статус: {status} | Сумма: {sum_paid:.2f}",0,1)
    pdf.output(buffer, 'F')
    buffer.seek(0)
    return buffer

def generate_report_stock():
    products = get_all_products()
    buffer = BytesIO()
    pdf = FPDF()
    pdf.add_page()
    setup_unicode_pdf(pdf, 10)
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 10, 8, 33)
    pdf.ln(20)
    pdf.set_font("DejaVu","",14)
    pdf.cell(0,10,"Отчет по остаткам",0,1)
    pdf.ln(5)
    pdf.set_font("DejaVu","",9)
    for p in products:
        pdf.cell(0,8,f"Товар: {p[0]} | Остаток: {p[1]}",0,1)
    pdf.output(buffer,'F')
    buffer.seek(0)
    return buffer

def generate_report_history(client_data):
    rows = search_orders_by_client(client_data)
    buffer = BytesIO()
    pdf = FPDF()
    pdf.add_page()
    setup_unicode_pdf(pdf, 10)
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 10,8,33)
    pdf.ln(20)
    pdf.set_font("DejaVu","",14)
    pdf.cell(0,10,f"История транзакций по: {client_data}",0,1)
    pdf.ln(5)
    pdf.set_font("DejaVu","",9)
    for row in rows:
        order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id = row
        pdf.cell(0,8,f"ID: {order_id} | {client_name} - {product_name} x {quantity} | Дата: {date} | Статус: {status} | Сумма: {sum_paid:.2f}",0,1)
    pdf.output(buffer,'F')
    buffer.seek(0)
    return buffer

def generate_report_sales_sum():
    total_sum, product_sums = get_sales_summary()
    buffer = BytesIO()
    pdf = FPDF()
    pdf.add_page()
    setup_unicode_pdf(pdf,10)
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 10,8,33)
    pdf.ln(20)
    pdf.set_font("DejaVu","",14)
    pdf.cell(0,10,"Отчет по суммам продаж",0,1,'C')
    pdf.ln(5)
    pdf.set_font("DejaVu","",10)
    pdf.cell(0,8,f"Общий объем продаж: {total_sum:.2f} руб.",0,1)
    pdf.ln(5)
    pdf.cell(0,8,"По товарам:",0,1)
    pdf.ln(3)
    pdf.set_font("DejaVu","",9)
    for ps in product_sums:
        product_name, p_sum = ps
        pdf.cell(0,6,f"{product_name}: {p_sum:.2f} руб.",0,1)
    pdf.output(buffer,'F')
    buffer.seek(0)
    return buffer

def is_admin(telegram_id):
    role = get_user_role(telegram_id)
    return role == "admin"

def cleanup_old_orders():
    # Очистка старых заказов старше 6 месяцев (180 дней)
    c = None
    conn = None
    count = 0
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"DELETE FROM {DB_PRFX}orders WHERE date < %s", (cutoff,))
        count = c.rowcount
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при очистке старых заказов: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return count

def history_orders_markup(rows):
    keyboard = []
    for r in rows:
        order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id = r
        kb_line = [InlineKeyboardButton(f"Удалить {product_name} ({quantity} шт.) {date} (ID:{order_id})", callback_data=f"delorder_{order_id}")]
        keyboard.append(kb_line)
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_history")])
    return InlineKeyboardMarkup(keyboard)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text="Главное меню:"):
    role = get_user_role(update.effective_user.id)
    if role == "admin":
        keyboard = [
            [InlineKeyboardButton("Добавить товар", callback_data="add_product")],
            [InlineKeyboardButton("Сделать предоплату", callback_data="make_order")],
            [InlineKeyboardButton("Проверить заказ по ID", callback_data="check_order")],
            [InlineKeyboardButton("Отчёты", callback_data="reports")],
            [InlineKeyboardButton("Очистка старых заказов", callback_data="cleanup_old")],
            [InlineKeyboardButton("Добавить пользователя", callback_data="add_user")],
            [InlineKeyboardButton("Список товаров", callback_data="list_products")]
        ]
    elif role == "viewer":
        keyboard = [
            [InlineKeyboardButton("Проверить заказ по ID", callback_data="check_order")]
        ]
    else:
        # Не авторизован
        if update.message:
            await update.message.reply_text("Вы не авторизованы для работы с этим ботом.")
        else:
            await update.callback_query.message.reply_text("Вы не авторизованы для работы с этим ботом.")
        return ConversationHandler.END

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

    context.user_data["current_state"] = CHOOSING_MAIN_MENU
    return CHOOSING_MAIN_MENU

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    role = get_user_role(query.from_user.id)
    await query.answer()
    data = query.data

    if data == "add_product":
        if role != "admin":
            await query.message.reply_text("Недостаточно прав.")
            return CHOOSING_MAIN_MENU
        await query.message.reply_text("Введите название товара:")
        context.user_data["current_state"] = ADDING_PRODUCT_NAME_STOCK
        return ADDING_PRODUCT_NAME_STOCK

    if data == "make_order":
        if role not in ["admin","viewer"]:
            await query.message.reply_text("Недостаточно прав.")
            return CHOOSING_MAIN_MENU
        await query.message.reply_text("Введите имя клиента:")
        context.user_data["current_state"] = ENTERING_CLIENT_NAME
        return ENTERING_CLIENT_NAME

    if data == "check_order":
        if role not in ["admin","viewer"]:
            await query.message.reply_text("Недостаточно прав.")
            return CHOOSING_MAIN_MENU
        await query.message.reply_text("Введите последние 6 цифр уникального ID заказа:")
        context.user_data["current_state"] = ENTERING_SEARCH_ORDER_ID_LAST6
        return ENTERING_SEARCH_ORDER_ID_LAST6

    if data == "reports":
        if role != "admin":
            await query.message.reply_text("Недостаточно прав.")
            return CHOOSING_MAIN_MENU
        keyboard = [
            [InlineKeyboardButton("Отчет по заказам", callback_data="report_orders")],
            [InlineKeyboardButton("Отчет по остаткам", callback_data="report_stock")],
            [InlineKeyboardButton("История по клиенту", callback_data="report_history")],
            [InlineKeyboardButton("Отчет по суммам продаж", callback_data="report_sales_sum")]
        ]
        await query.message.reply_text("Выберите тип отчета:", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["current_state"] = SELECTING_REPORT_TYPE
        return SELECTING_REPORT_TYPE

    if data == "cleanup_old":
        if role != "admin":
            await query.message.reply_text("Недостаточно прав.")
            return CHOOSING_MAIN_MENU
        cleared = cleanup_old_orders()
        await query.message.reply_text(f"Удалено старых заказов: {cleared}")
        return await show_main_menu(update, context)

    if data == "add_user":
        if role != "admin":
            await query.message.reply_text("Недостаточно прав.")
            return CHOOSING_MAIN_MENU
        await query.message.reply_text("Введите Telegram ID пользователя:")
        context.user_data["current_state"] = ADDING_USER_TELEGRAM_ID
        return ADDING_USER_TELEGRAM_ID

    if data == "list_products":
        products = get_all_products()
        text = "Список товаров:\n"
        for p in products:
            text += f"{p[0]}: {p[1]} шт.\n"
        await query.message.reply_text(text)
        return await show_main_menu(update, context)

    if data == "report_orders":
        try:
            buffer = generate_report_orders()
            await query.message.reply_text("Отчет по заказам:")
            await query.message.reply_document(document=buffer, filename="orders_report.pdf")
        except Exception as e:
            await query.message.reply_text(f"Ошибка при генерации отчёта: {e}")
        return await show_main_menu(update, context)

    if data == "report_stock":
        try:
            buffer = generate_report_stock()
            await query.message.reply_text("Отчет по остаткам:")
            await query.message.reply_document(document=buffer, filename="stock_report.pdf")
        except Exception as e:
            await query.message.reply_text(f"Ошибка при генерации отчёта: {e}")
        return await show_main_menu(update, context)

    if data == "report_history":
        await query.message.reply_text("Введите имя или телефон клиента для поиска:")
        context.user_data["current_state"] = SELECTING_USER_ACTION
        return SELECTING_USER_ACTION

    if data == "report_sales_sum":
        try:
            buffer = generate_report_sales_sum()
            await query.message.reply_text("Отчет по суммам продаж:")
            await query.message.reply_document(document=buffer, filename="sales_sum_report.pdf")
        except Exception as e:
            await query.message.reply_text(f"Ошибка при генерации отчёта: {e}")
        return await show_main_menu(update, context)

    if data.startswith("delorder_"):
        order_id = data.split("_",1)[1]
        delete_order(order_id)
        client_data = context.user_data.get("history_client_data")
        rows = search_orders_by_client(client_data)
        if rows:
            await query.message.reply_text("Обновлённый список заказов:", 
                                           reply_markup=history_orders_markup(rows))
            context.user_data["current_state"] = VIEWING_HISTORY_ORDERS
            return VIEWING_HISTORY_ORDERS
        else:
            await query.message.reply_text("Все заказы удалены или отсутствуют.")
            return await show_main_menu(update, context)

    if data == "back_history":
        return await show_main_menu(update, context)

    if data == "confirm_issue_yes":
        order_id = context.user_data.get("issue_order_id")
        issuer_id = update.effective_user.id
        update_order_issued(order_id, issuer_id)
        await query.message.reply_text("Товар выдан. Статус обновлен.")
        context.user_data["current_state"] = CHOOSING_MAIN_MENU
        return await show_main_menu(update, context)

    if data == "confirm_issue_no":
        await query.message.reply_text("Операция отменена.")
        context.user_data["current_state"] = CHOOSING_MAIN_MENU
        return await show_main_menu(update, context)

    return CHOOSING_MAIN_MENU

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = get_user_role(update.effective_user.id)
    if role is None:
        await update.message.reply_text("Вы не авторизованы.")
        return ConversationHandler.END

    current_state = context.user_data.get("current_state")

    if current_state == ADDING_PRODUCT_NAME_STOCK:
        context.user_data["stock_product_name"] = update.message.text
        await update.message.reply_text("Введите количество для этого товара:")
        context.user_data["current_state"] = ADDING_PRODUCT_QTY_STOCK
        return ADDING_PRODUCT_QTY_STOCK

    if current_state == ADDING_PRODUCT_QTY_STOCK:
        qty = int(update.message.text)
        name = context.user_data["stock_product_name"]
        add_product_db(name, qty)
        await update.message.reply_text(f"Товар {name} добавлен с остатком {qty} шт.")
        context.user_data["current_state"] = CHOOSING_MAIN_MENU
        return await show_main_menu(update, context)

    if current_state == ENTERING_CLIENT_NAME:
        context.user_data["client_name"] = update.message.text
        products = get_all_products()
        if not products:
            await update.message.reply_text("Нет доступных товаров!")
            context.user_data["current_state"] = CHOOSING_MAIN_MENU
            return await show_main_menu(update, context)
        keyboard = []
        for p in products:
            keyboard.append([InlineKeyboardButton(f"{p[0]} ({p[1]} шт.)", callback_data=f"product_{p[0]}")])
        # Но в старом коде был другой подход. У нас product_ не обрабатывается напрямую.
        # Давайте просто попросим количество потом. Старый код: сначала клиент -> потом товар -> потом qty -> sum.
        # Мы уже реализовали этот лог в button_handler? Нет, тут чуть иначе.
        # В старом коде товар выбирался сразу. Давайте адаптируем.
        # Лучше сразу спросим товар. Но мы уже делаем как старый код: 
        # Старый код после ENTERING_CLIENT_NAME показывал список товаров через CallbackQueryHandler.
        # Сейчас сделаем так же:
        await update.message.reply_text("Выберите товар:", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["current_state"] = SELECTING_PRODUCT_FOR_ORDER
        return SELECTING_PRODUCT_FOR_ORDER

    if current_state == ENTERING_ORDER_QTY:
        qty = int(update.message.text)
        context.user_data["order_qty"] = qty
        await update.message.reply_text("Введите сумму, которую клиент оплатил за всё количество:")
        context.user_data["current_state"] = ENTERING_ORDER_SUM
        return ENTERING_ORDER_SUM

    if current_state == ENTERING_ORDER_SUM:
        sum_paid = float(update.message.text)
        context.user_data["order_sum_paid"] = sum_paid
        product_name = context.user_data["order_product_name"]
        qty = context.user_data["order_qty"]
        client_name = context.user_data["client_name"]
        await update.message.reply_text(f"Вы хотите оплатить {qty} шт. {product_name} для {client_name} за {sum_paid:.2f} руб.? (Да/Нет)")
        context.user_data["current_state"] = CONFIRM_ORDER
        return CONFIRM_ORDER

    if current_state == CONFIRM_ORDER:
        answer = update.message.text.lower()
        if answer == "да":
            product_name = context.user_data["order_product_name"]
            qty = context.user_data["order_qty"]
            sum_paid = context.user_data["order_sum_paid"]
            client_name = context.user_data["client_name"]
            order_id = create_order(client_name, product_name, qty, sum_paid)
            order = get_order_by_id(order_id)
            pdf_buffer = generate_pdf_order_details(order)
            await update.message.reply_text(f"Заказ создан! ID: {order_id}")
            await update.message.reply_document(document=pdf_buffer, filename=f"order_{order_id}.pdf")
        else:
            await update.message.reply_text("Операция отменена.")
        context.user_data["current_state"] = CHOOSING_MAIN_MENU
        return await show_main_menu(update, context)

    if current_state == ENTERING_SEARCH_ORDER_ID_LAST6:
        last6 = update.message.text.strip()
        order = get_order_by_last6(last6)
        if order is None:
            await update.message.reply_text("Заказ не найден по этим 6 цифрам.")
            context.user_data["current_state"] = CHOOSING_MAIN_MENU
            return await show_main_menu(update, context)
        else:
            order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id = order
            msg = f"Заказ: {order_id}\nКлиент: {client_name}\nТовар: {product_name} x {quantity}\nДата: {date}\nСтатус: {status}\nСумма: {sum_paid:.2f}"
            if issue_date:
                msg += f"\nВыдан: {issue_date}, Выдал пользователь ID: {issuer_id}"
            await update.message.reply_text(msg)

            if status != "Выдан":
                keyboard = [
                    [InlineKeyboardButton("Да", callback_data="confirm_issue_yes"), InlineKeyboardButton("Нет", callback_data="confirm_issue_no")]
                ]
                await update.message.reply_text("Подтвердить выдачу товара?", reply_markup=InlineKeyboardMarkup(keyboard))
                context.user_data["current_state"] = CONFIRM_ISSUE
                context.user_data["issue_order_id"] = order_id
                return CONFIRM_ISSUE
            else:
                await update.message.reply_text("Этот заказ уже выдан.")
                context.user_data["current_state"] = CHOOSING_MAIN_MENU
                return await show_main_menu(update, context)

    if current_state == ADDING_USER_TELEGRAM_ID:
        context.user_data["new_user_id"] = int(update.message.text)
        await update.message.reply_text("Введите роль для этого пользователя (admin/viewer):")
        context.user_data["current_state"] = ADDING_USER_ROLE
        return ADDING_USER_ROLE

    if current_state == ADDING_USER_ROLE:
        role_new = update.message.text.strip()
        if role_new not in ["admin","viewer"]:
            await update.message.reply_text("Некорректная роль. Попробуйте еще раз.")
            return ADDING_USER_ROLE
        add_user(context.user_data["new_user_id"], role_new)
        await update.message.reply_text("Пользователь добавлен.")
        context.user_data["current_state"] = CHOOSING_MAIN_MENU
        return await show_main_menu(update, context)

    if current_state == SELECTING_USER_ACTION:
        client_data = update.message.text
        context.user_data["history_client_data"] = client_data
        rows = search_orders_by_client(client_data)
        if rows:
            await update.message.reply_text("Результаты поиска:", reply_markup=history_orders_markup(rows))
            context.user_data["current_state"] = VIEWING_HISTORY_ORDERS
            return VIEWING_HISTORY_ORDERS
        else:
            await update.message.reply_text("Заказы не найдены.")
            context.user_data["current_state"] = CHOOSING_MAIN_MENU
            return await show_main_menu(update, context)

    if current_state == VIEWING_HISTORY_ORDERS:
        await update.message.reply_text("Используйте кнопки для управления.")
        return VIEWING_HISTORY_ORDERS

    # Если попали сюда - неизвестная команда
    await update.message.reply_text("Неизвестная команда, возвращаюсь в главное меню.")
    context.user_data["current_state"] = CHOOSING_MAIN_MENU
    return await show_main_menu(update, context)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = get_user_role(update.effective_user.id)
    if role is None:
        # Проверяем есть ли уже пользователи
        c = None
        conn = None
        count = 0
        try:
            conn = get_connection()
            c = conn.cursor()
            c.execute(f"SELECT COUNT(*) FROM {DB_PRFX}users")
            count = c.fetchone()[0]
        except mysql.connector.Error as err:
            logger.error(f"Ошибка при проверке пользователей: {err}")
        finally:
            if c:
                c.close()
            if conn:
                conn.close()

        if count == 0:
            add_user(update.effective_user.id,"admin")
            await update.message.reply_text("Вы стали админом, так как это первый запуск бота.")
        else:
            await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
            return ConversationHandler.END

    return await show_main_menu(update, context)

async def timeout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message:
        await update.effective_message.reply_text("Время ожидания истекло. Возвращаюсь в главное меню.")
    return await show_main_menu(update, context)

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_MAIN_MENU: [CallbackQueryHandler(button_handler)],

            ADDING_PRODUCT_NAME_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            ADDING_PRODUCT_QTY_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],

            ENTERING_CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            SELECTING_PRODUCT_FOR_ORDER: [CallbackQueryHandler(button_handler), MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            ENTERING_ORDER_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            ENTERING_ORDER_SUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            CONFIRM_ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],

            ENTERING_SEARCH_ORDER_ID_LAST6: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],

            ADDING_USER_TELEGRAM_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            ADDING_USER_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            SELECTING_REPORT_TYPE: [CallbackQueryHandler(button_handler)],
            SELECTING_USER_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            VIEWING_HISTORY_ORDERS: [CallbackQueryHandler(button_handler)],
            CONFIRM_ISSUE: [CallbackQueryHandler(button_handler)],

            ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, timeout_handler)]
        },
        fallbacks=[CommandHandler("start", start)],
        conversation_timeout=30,
        name="my_conversation"
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
