import os
import datetime
import random
import string
from io import BytesIO
import logging

import mysql.connector
from fpdf import FPDF
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaDocument
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters, ConversationHandler
)

# -------------------- ЛОГИРОВАНИЕ --------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------- КОНФИГ --------------------
DB_HOST = 'localhost'
DB_USER = 'chatbot_user'
DB_PASS = 'XRaRziqAq9Pf41pB'
DB_NAME = 'chatbot_db'
DB_PRFX = 'bot_'

BOT_TOKEN = "7824760453:AAGuV6vdRhNhvot3xIIgPK0WsnEE8KX5tHI"  # Подставьте ваш токен

# Состояния
(
    CHOOSING_MAIN_MENU,
    # Добавление товара
    ADDING_PRODUCT_NAME_STOCK,
    ADDING_PRODUCT_QTY_STOCK,
    # Предоплата (создание заказа)
    ENTERING_CLIENT_NAME,
    SELECTING_PRODUCT_FOR_ORDER,
    ENTERING_ORDER_QTY,
    ENTERING_ORDER_SUM,
    CONFIRM_ORDER,
    # Проверка заказа по ID (последние 6 цифр)
    ENTERING_SEARCH_ORDER_ID_LAST6,
    CONFIRM_ISSUE,
    # Добавление пользователя
    ADDING_USER_TELEGRAM_ID,
    ADDING_USER_ROLE,
    # Отчёты
    SELECTING_REPORT_TYPE,
    REPORT_CHOICE_FORMAT,      # выбор PDF или Telegram для отчетов
    REPORT_DISPLAY_ORDERS,     # показ заказов в telegram (инлайн)
    REPORT_DISPLAY_STOCK,      # показ товаров в telegram (инлайн)
    REPORT_SEARCH_CLIENT,      # ввод имени клиента для отчета по истории
    REPORT_DISPLAY_HISTORY,    # показ истории по клиенту (inline)
    REPORT_DISPLAY_SALES_SUM,  # показ сумм продаж (inline или pdf)
    # Редактирование товара из списка
    EDIT_PRODUCT_CHOICE,       # выбор: изменить название или количество
    EDIT_PRODUCT_NAME,
    EDIT_PRODUCT_QTY,
    # Очистка заказов
    CLEAR_OLD_ORDERS_CHOICE,
    CLEAR_OLD_ORDERS_BY_PRODUCT_CHOICE,
    CLEAR_OLD_ORDERS_BY_CLIENT,
    CONFIRM_CLEAR_OLD_ORDERS,
    # Изменение статуса заказа через проверку по ID
    CHANGE_ORDER_STATUS,
    # Отображение и удаление заказов из отчета по заказам
    VIEWING_HISTORY_ORDERS,
    DELETE_ORDER_CONFIRM,
    # Изменение статуса заказа при просмотре заказа
    ORDER_STATUS_CHANGE_CONFIRM,
    # Выбор товара из списка товаров для редактирования
    LIST_PRODUCTS_CHOICE,
    # История по клиенту - сначала вводим клиента
    SELECTING_USER_ACTION,
) = range(33)

# -------------------- ФУНКЦИИ БД --------------------
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
    except:
        pass
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return None

def add_user_db(telegram_id, role):
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"INSERT IGNORE INTO {DB_PRFX}users (telegram_id, role) VALUES (%s,%s)", (telegram_id, role))
        conn.commit()
        logger.info(f"Пользователь {telegram_id} добавлен с ролью {role}")
    except:
        pass
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

def is_admin(telegram_id):
    return get_user_role(telegram_id) == "admin"

def get_all_admin_ids():
    # Вернем список telegram_id всех админов
    c = None
    conn = None
    admins = []
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT telegram_id FROM {DB_PRFX}users WHERE role='admin'")
        rows = c.fetchall()
        for r in rows:
            admins.append(r[0])
    except:
        pass
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return admins

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

def get_all_products():
    c = None
    conn = None
    results = []
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT id, name, quantity FROM {DB_PRFX}products")
        results = c.fetchall()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении списка товаров: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return results

def get_product_by_id(pid):
    c = None
    conn = None
    product = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT id,name,quantity FROM {DB_PRFX}products WHERE id=%s", (pid,))
        product = c.fetchone()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении товара: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return product

def update_product_quantity(id_or_name, qty, by_id=False):
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        if by_id:
            c.execute(f"UPDATE {DB_PRFX}products SET quantity=%s WHERE id=%s", (qty, id_or_name))
        else:
            c.execute(f"UPDATE {DB_PRFX}products SET quantity=%s WHERE name=%s", (qty, id_or_name))
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при обновлении количества товара: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

def update_product_name(prod_id, new_name):
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"UPDATE {DB_PRFX}products SET name=%s WHERE id=%s",(new_name, prod_id))
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при изменении названия товара: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

def get_product_quantity_by_name(name):
    c = None
    conn = None
    qty = 0
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT quantity FROM {DB_PRFX}products WHERE name=%s", (name,))
        row = c.fetchone()
        if row:
            qty = row[0]
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении количества товара: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return qty

def reduce_product_quantity(name, qty):
    available_qty = get_product_quantity_by_name(name)
    if available_qty >= qty:
        new_qty = available_qty - qty
        update_product_quantity(name, new_qty, by_id=False)
        return True
    return False

def add_order_db(order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id):
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"""
            INSERT INTO {DB_PRFX}orders (order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id))
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при добавлении заказа: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

def get_order_by_last6(last6):
    c = None
    conn = None
    result = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id FROM {DB_PRFX}orders WHERE order_id LIKE %s", (f"%{last6}",))
        row = c.fetchone()
        if row:
            result = row
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при поиске заказа: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return result

def get_order_by_id(order_id):
    c = None
    conn = None
    result = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id FROM {DB_PRFX}orders WHERE order_id=%s",(order_id,))
        result = c.fetchone()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении заказа по ID: {err}")
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
        logger.error(f"Ошибка обновления статуса заказа: {err}")
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
        c.execute(f"DELETE FROM {DB_PRFX}orders WHERE order_id=%s", (order_id,))
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

def get_all_orders():
    c = None
    conn = None
    rows = []
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id FROM {DB_PRFX}orders")
        rows = c.fetchall()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении всех заказов: {err}")
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

def clear_orders_by_period(days=1, product_name=None, client_name=None):
    # Удаляем заказы в зависимости от выбранного критерия
    c = None
    conn = None
    count = 0
    try:
        conn = get_connection()
        c = conn.cursor()
        if product_name:
            c.execute(f"DELETE FROM {DB_PRFX}orders WHERE product_name=%s", (product_name,))
        elif client_name:
            c.execute(f"DELETE FROM {DB_PRFX}orders WHERE client_name LIKE %s", (f"%{client_name}%",))
        else:
            cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            c.execute(f"DELETE FROM {DB_PRFX}orders WHERE date < %s", (cutoff,))
        count = c.rowcount
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при очистке заказов: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return count

# -------------------- Генерация PDF --------------------
def setup_unicode_pdf(pdf, size=10):
    if os.path.exists("DejaVuSansCondensed.ttf"):
        pdf.add_font("DejaVu", "", "DejaVuSansCondensed.ttf", uni=True)
        pdf.set_font("DejaVu", "", size)
    else:
        pdf.set_font("Arial", "", size)

def generate_pdf_order_details(order):
    order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id = order
    quantity = int(quantity)
    price_per_item = sum_paid / quantity if quantity > 0 else 0

    buffer = BytesIO()
    pdf = FPDF()
    pdf.add_page()
    setup_unicode_pdf(pdf, 10)

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

def generate_report_orders_pdf():
    rows = get_all_orders()
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

def generate_report_stock_pdf():
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
        pdf.cell(0,8,f"Товар: {p[1]} | Остаток: {p[2]}",0,1)
    pdf.output(buffer,'F')
    buffer.seek(0)
    return buffer

def generate_report_history_pdf(client_data):
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
        pdf.cell(0,8,f"ID: {order_id} | {client_name} - {product_name} x {quantity} | {date} | Статус: {status} | Сумма: {sum_paid:.2f}",0,1)
    pdf.output(buffer,'F')
    buffer.seek(0)
    return buffer

def generate_report_sales_sum_pdf():
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
    pd
