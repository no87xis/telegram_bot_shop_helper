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

# Данные подключения к MySQL
DB_HOST = 'localhost'
DB_USER = 'chatbot_user'
DB_PASS = 'XRaRziqAq9Pf41pB'
DB_NAME = 'chatbot_db'
DB_PRFX = 'bot_'

BOT_TOKEN = "7824760453:AAGuV6vdRhNhvot3xIIgPK0WsnEE8KX5tHI"  # Подставьте ваш токен

# Инициализация базы данных
def init_db():
    c = None
    conn = None
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME
        )
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

# Состояния диалога (ConversationHandler)
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
    CONFIRM_ISSUE,
    ADDING_USER_TELEGRAM_ID,
    ADDING_USER_ROLE,
    SELECTING_REPORT_TYPE,
    REPORT_CHOICE_FORMAT,
    REPORT_DISPLAY_ORDERS,
    REPORT_DISPLAY_STOCK,
    REPORT_SEARCH_CLIENT,
    REPORT_DISPLAY_HISTORY,
    REPORT_DISPLAY_SALES_SUM,
    EDIT_PRODUCT_CHOICE,
    EDIT_PRODUCT_NAME,
    EDIT_PRODUCT_QTY,
    CLEAR_OLD_ORDERS_CHOICE,
    CLEAR_OLD_ORDERS_BY_PRODUCT_CHOICE,
    CLEAR_OLD_ORDERS_BY_CLIENT,
    CONFIRM_CLEAR_OLD_ORDERS,
    CHANGE_ORDER_STATUS,
    VIEWING_HISTORY_ORDERS,
    DELETE_ORDER_CONFIRM,
    ORDER_STATUS_CHANGE_CONFIRM,
    LIST_PRODUCTS_CHOICE,
    SELECTING_USER_ACTION,
) = range(32)

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

def add_user_db(telegram_id, role):
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"INSERT IGNORE INTO {DB_PRFX}users (telegram_id, role) VALUES (%s,%s)", (telegram_id, role))
        conn.commit()
        logger.info(f"Пользователь {telegram_id} добавлен с ролью {role}")
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при добавлении пользователя: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

def get_all_admin_ids():
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

def is_admin(telegram_id):
    return get_user_role(telegram_id) == "admin"
# --- Часть 2: Функции для работы с товарами, заказами и PDF ---

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
        logger.error(f"Ошибка при поиске заказа по последним 6 цифрам: {err}")
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

# Функции для PDF

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
# --- Часть 3: Вспомогательные функции, хэндлеры команд и основных функций ---

async def notify_admins(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Отправляет сообщение всем админам."""
    admins = get_all_admin_ids()
    for admin_id in admins:
        try:
            await context.bot.send_message(chat_id=admin_id, text=message)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения админу {admin_id}: {e}")

def generate_order_id():
    now = datetime.datetime.now()
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    random_part = ''.join(random.choices(string.digits, k=6))
    return f"ORD{date_part}-{time_part}-{random_part}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = get_user_role(update.effective_user.id)
    if role is None:
        c = None
        conn = None
        count = 0
        try:
            conn = get_connection()
            c = conn.cursor()
            c.execute(f"SELECT COUNT(*) FROM {DB_PRFX}users")
            count = c.fetchone()[0]
        except:
            pass
        finally:
            if c:
                c.close()
            if conn:
                conn.close()

        if count == 0:
            add_user_db(update.effective_user.id,"admin")
            await update.message.reply_text("Вы стали админом, так как это первый запуск бота.")
        else:
            await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
            return ConversationHandler.END

    return await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text="Главное меню:"):
    role = get_user_role(update.effective_user.id)
    if role == "admin":
        keyboard = [
            [InlineKeyboardButton("Добавить товар", callback_data="add_product")],
            [InlineKeyboardButton("Сделать предоплату", callback_data="make_order")],
            [InlineKeyboardButton("Проверить заказ по ID (посл.6 цифр)", callback_data="check_order")],
            [InlineKeyboardButton("Отчёты", callback_data="reports")],
            [InlineKeyboardButton("Очистка заказов", callback_data="cleanup_orders")],
            [InlineKeyboardButton("Добавить пользователя", callback_data="add_user")],
            [InlineKeyboardButton("Список товаров", callback_data="list_products")]
        ]
    elif role == "viewer":
        keyboard = [
            [InlineKeyboardButton("Проверить заказ по ID (посл.6 цифр)", callback_data="check_order")]
        ]
    else:
        if update.message:
            await update.message.reply_text("Вы не авторизованы.")
        else:
            await update.callback_query.message.reply_text("Вы не авторизованы.")
        return ConversationHandler.END

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

    return CHOOSING_MAIN_MENU

# Ниже будут хэндлеры для добавления товара, создания предоплаты, проверки заказа по ID,
# изменения статуса заказа, отчетов, списка товаров, очистки заказов.
#
# Из-за большого объема кода, мы разобьем логику на дополнительные функции-хэндлеры.
# После реализации этих хэндлеров, мы в следующей части продолжим, чтобы не превышать лимит.

# Добавление товара (пример):
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.edit_message_text("У вас нет прав для добавления товаров.")
        return CHOOSING_MAIN_MENU

    await query.edit_message_text("Введите название товара:")
    return ADDING_PRODUCT_NAME_STOCK

async def add_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["product_name"] = update.message.text.strip()
    await update.message.reply_text("Введите количество товара:")
    return ADDING_PRODUCT_QTY_STOCK

async def add_product_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get("product_name")
    try:
        qty = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Количество должно быть числом. Введите снова:")
        return ADDING_PRODUCT_QTY_STOCK

    # Добавляем товар в БД
    add_product_db(name, qty)
    await update.message.reply_text(f"Товар '{name}' добавлен с количеством {qty}")
    return await show_main_menu(update, context)

# Создание предоплаты (заказ)
async def make_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите имя клиента:")
    return ENTERING_CLIENT_NAME

async def enter_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["client_name"] = update.message.text.strip()
    products = get_all_products()
    if not products:
        await update.message.reply_text("Нет доступных товаров для заказа.")
        return await show_main_menu(update, context)

    # Выводим список товаров кнопками
    keyboard = []
    for p in products:
        # p: (id, name, qty)
        keyboard.append([InlineKeyboardButton(f"{p[1]} ({p[2]} шт.)", callback_data=f"select_product_{p[0]}")])
    await update.message.reply_text("Выберите товар для заказа:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_PRODUCT_FOR_ORDER

async def select_product_for_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    product_id = data.split("_")[-1]
    product = get_product_by_id(product_id)
    if not product:
        await query.edit_message_text("Товар не найден.")
        return await show_main_menu(update, context)

    context.user_data["order_product"] = product[1]
    await query.edit_message_text(f"Вы выбрали: {product[1]}\nВведите количество:")
    return ENTERING_ORDER_QTY

async def enter_order_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Количество должно быть числом. Попробуйте снова:")
        return ENTERING_ORDER_QTY
    context.user_data["order_qty"] = qty

    product_name = context.user_data["order_product"]
    available_qty = get_product_quantity_by_name(product_name)
    if available_qty < qty:
        await update.message.reply_text(f"Недостаточно товара. В наличии: {available_qty}. Введите другое количество или /cancel для отмены:")
        return ENTERING_ORDER_QTY

    await update.message.reply_text("Введите сумму предоплаты:")
    return ENTERING_ORDER_SUM

async def enter_order_sum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sum_paid = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Сумма должна быть числом. Введите снова:")
        return ENTERING_ORDER_SUM

    context.user_data["order_sum"] = sum_paid
    client_name = context.user_data["client_name"]
    product_name = context.user_data["order_product"]
    qty = context.user_data["order_qty"]
    await update.message.reply_text(
        f"Подтвердите заказ:\nКлиент: {client_name}\nТовар: {product_name}\nКоличество: {qty}\nПредоплата: {sum_paid}\n\nОтправьте /yes для подтверждения или /no для отмены."
    )
    return CONFIRM_ORDER

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()
    if text == "/yes":
        order_id = generate_order_id()
        client_name = context.user_data["client_name"]
        product_name = context.user_data["order_product"]
        qty = context.user_data["order_qty"]
        sum_paid = context.user_data["order_sum"]
        status = "Оплачено" if sum_paid > 0 else "Не оплачено"
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        issuer_id = update.effective_user.id

        if not reduce_product_quantity(product_name, qty):
            await update.message.reply_text("Ошибка обновления количества товара.")
            return await show_main_menu(update, context)

        add_order_db(order_id, client_name, product_name, qty, date_str, status, sum_paid, None, None)
        # Отправляем чек в PDF
        order = get_order_by_id(order_id)
        pdf_buffer = generate_pdf_order_details(order)
        await update.message.reply_text(f"Заказ создан! ID: {order_id}")
        await update.message.reply_document(document=pdf_buffer, filename=f"order_{order_id}.pdf")

        # Уведомляем админов о новом заказе
        await notify_admins(context, f"Новый заказ: {order_id}\nКлиент: {client_name}\nТовар: {product_name}\nКоличество: {qty}\nСумма: {sum_paid}")
    else:
        await update.message.reply_text("Заказ отменён.")
    return await show_main_menu(update, context)

# Проверка заказа по ID (последние 6 цифр)
async def check_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите последние 6 цифр уникального ID заказа:")
    return ENTERING_SEARCH_ORDER_ID_LAST6

async def check_order_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    last6 = update.message.text.strip()
    order = get_order_by_last6(last6)
    if order is None:
        await update.message.reply_text("Заказ не найден по этим 6 цифрам.")
        return await show_main_menu(update, context)

    order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id = order
    msg = (f"Заказ: {order_id}\nКлиент: {client_name}\nТовар: {product_name} x {quantity}\n"
           f"Дата: {date}\nСтатус: {status}\nСумма: {sum_paid:.2f}")
    if issue_date:
        msg += f"\nВыдан: {issue_date}, Выдал пользователь ID: {issuer_id}"

    await update.message.reply_text(msg)

    # Позволяем изменить статус на "выдан"
    if status != "Выдан":
        keyboard = [
            [InlineKeyboardButton("Изменить статус на 'Выдан'", callback_data=f"issue_order_{order_id}")],
            [InlineKeyboardButton("Назад в меню", callback_data="main_menu")]
        ]
        await update.message.reply_text("Вы хотите изменить статус заказа на 'Выдан'?", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["current_order_id"] = order_id
        return CONFIRM_ISSUE
    else:
        return await show_main_menu(update, context)
# --- Часть 4: Продолжение хэндлеров (изменение статуса заказа, отчёты, список товаров, очистка заказов) ---

async def confirm_issue_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обрабатываем изменение статуса на "Выдан"
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("issue_order_"):
        order_id = data.split("_", 2)[2]
        issuer_id = update.effective_user.id
        update_order_issued(order_id, issuer_id)
        await query.edit_message_text("Статус заказа изменён на 'Выдан'.")
        # Уведомляем админов о смене статуса
        await notify_admins(context, f"Статус заказа {order_id} изменён на 'Выдан' пользователем {issuer_id}")
        return await show_main_menu(update, context)
    elif data == "main_menu":
        return await show_main_menu(update, context)

# Отчёты
async def reports_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Отчёт по заказам", callback_data="report_orders")],
        [InlineKeyboardButton("Отчёт по остаткам", callback_data="report_stock")],
        [InlineKeyboardButton("История по клиенту", callback_data="report_history")],
        [InlineKeyboardButton("Отчёт по суммам продаж", callback_data="report_sales_sum")],
        [InlineKeyboardButton("Назад", callback_data="main_menu")]
    ]
    await query.edit_message_text("Выберите тип отчёта:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_REPORT_TYPE

async def report_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    context.user_data["report_type"] = data

    # Для всех отчётов, кроме истории по клиенту, сразу предлагаем формат вывода (PDF или Telegram)
    if data == "report_history":
        await query.edit_message_text("Введите имя или данные клиента для поиска:")
        return REPORT_SEARCH_CLIENT
    else:
        # Выбор формата отчёта
        keyboard = [
            [InlineKeyboardButton("PDF", callback_data="format_pdf")],
            [InlineKeyboardButton("Телеграм (список)", callback_data="format_telegram")],
            [InlineKeyboardButton("Назад", callback_data="reports_back")]
        ]
        await query.edit_message_text("Выберите формат отчёта:", reply_markup=InlineKeyboardMarkup(keyboard))
        return REPORT_CHOICE_FORMAT

async def report_choice_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fmt = query.data
    report_type = context.user_data["report_type"]

    if fmt == "reports_back":
        return await reports_start(update, context)

    if report_type == "report_orders":
        if fmt == "format_pdf":
            # Генерируем PDF и отправляем
            buffer = generate_report_orders_pdf()
            await query.edit_message_text("Отчет по заказам (PDF):")
            await query.message.reply_document(document=buffer, filename="orders_report.pdf")
            return await show_main_menu(update, context)
        else:
            # Показать заказы списком в телеграме
            rows = get_all_orders()
            if not rows:
                await query.edit_message_text("Нет заказов.")
                return await show_main_menu(update, context)
            # inline-кнопки для каждого заказа
            keyboard = []
            for r in rows:
                order_id = r[0]
                keyboard.append([InlineKeyboardButton(order_id, callback_data=f"view_order_{order_id}")])
            keyboard.append([InlineKeyboardButton("Назад", callback_data="main_menu")])
            await query.edit_message_text("Список заказов:", reply_markup=InlineKeyboardMarkup(keyboard))
            return REPORT_DISPLAY_ORDERS

    elif report_type == "report_stock":
        if fmt == "format_pdf":
            buffer = generate_report_stock_pdf()
            await query.edit_message_text("Отчет по остаткам (PDF):")
            await query.message.reply_document(document=buffer, filename="stock_report.pdf")
            return await show_main_menu(update, context)
        else:
            # Показать товары списком с возможностью изменить их
            products = get_all_products()
            if not products:
                await query.edit_message_text("Нет товаров.")
                return await show_main_menu(update, context)
            keyboard = []
            for p in products:
                # p: (id, name, qty)
                keyboard.append([InlineKeyboardButton(f"{p[1]} ({p[2]} шт.)", callback_data=f"editstock_{p[0]}")])
            keyboard.append([InlineKeyboardButton("Назад", callback_data="main_menu")])
            await query.edit_message_text("Список товаров:", reply_markup=InlineKeyboardMarkup(keyboard))
            return REPORT_DISPLAY_STOCK

    elif report_type == "report_sales_sum":
        if fmt == "format_pdf":
            buffer = generate_report_sales_sum_pdf()
            await query.edit_message_text("Отчет по суммам продаж (PDF):")
            await query.message.reply_document(document=buffer, filename="sales_sum_report.pdf")
            return await show_main_menu(update, context)
        else:
            total_sum, product_sums = get_sales_summary()
            text = f"Общий объем продаж: {total_sum:.2f} руб.\n\nПо товарам:\n"
            for ps in product_sums:
                product_name, p_sum = ps
                text += f"{product_name}: {p_sum:.2f} руб.\n"
            await query.edit_message_text(text)
            return await show_main_menu(update, context)

    # Если для report_history, обработка будет после ввода имени клиента

async def report_search_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Пользователь ввел имя/данные клиента для отчета
    client_data = update.message.text.strip()
    context.user_data["history_client_data"] = client_data
    # Выбор формата отчёта
    keyboard = [
        [InlineKeyboardButton("PDF", callback_data="format_pdf")],
        [InlineKeyboardButton("Телеграм (список)", callback_data="format_telegram")],
        [InlineKeyboardButton("Назад", callback_data="reports_back")]
    ]
    await update.message.reply_text("Выберите формат отчёта:", reply_markup=InlineKeyboardMarkup(keyboard))
    return REPORT_CHOICE_FORMAT

async def report_history_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fmt = query.data
    if fmt == "reports_back":
        return await reports_start(update, context)
    client_data = context.user_data["history_client_data"]
    rows = search_orders_by_client(client_data)
    if not rows:
        await query.edit_message_text("Заказы не найдены.")
        return await show_main_menu(update, context)

    if fmt == "format_pdf":
        buffer = generate_report_history_pdf(client_data)
        await query.edit_message_text("История по клиенту (PDF):")
        await query.message.reply_document(document=buffer, filename="history_report.pdf")
        return await show_main_menu(update, context)
    else:
        # Показать заказы списком в telegram
        keyboard = []
        for r in rows:
            order_id = r[0]
            keyboard.append([InlineKeyboardButton(order_id, callback_data=f"history_order_{order_id}")])
        keyboard.append([InlineKeyboardButton("Назад", callback_data="main_menu")])
        await query.edit_message_text("Результаты поиска:", reply_markup=InlineKeyboardMarkup(keyboard))
        return REPORT_DISPLAY_HISTORY

# Просмотр заказа из отчета
async def view_order_from_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    # data: view_order_{order_id}
    # или history_order_{order_id}
    order_id = data.split("_",2)[2]
    order = get_order_by_id(order_id)
    if not order:
        await query.edit_message_text("Заказ не найден.")
        return await show_main_menu(update, context)
    order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id = order
    msg = (f"Заказ: {order_id}\nКлиент: {client_name}\nТовар: {product_name} x {quantity}\n"
           f"Дата: {date}\nСтатус: {status}\nСумма: {sum_paid:.2f}")
    if issue_date:
        msg += f"\nВыдан: {issue_date}, Выдал пользователь ID: {issuer_id}"

    # Предложим удалить заказ
    keyboard = [
        [InlineKeyboardButton("Удалить заказ", callback_data=f"delorder_{order_id}")],
        [InlineKeyboardButton("Назад в меню", callback_data="main_menu")]
    ]
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return VIEWING_HISTORY_ORDERS

async def delete_order_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    order_id = context.user_data["delete_order_id"]
    if text == "удалить безвозвратно":
        # Сначала получаем детали заказа
        order = get_order_by_id(order_id)
        if order:
            # order: order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id
            _, _, product_name, quantity, _, _, _, _, _ = order
            
            # Возвращаем количество товара на склад
            current_qty = get_product_quantity_by_name(product_name)
            new_qty = current_qty + quantity
            update_product_quantity(product_name, new_qty, by_id=False)
        
        # Теперь удаляем сам заказ
        delete_order(order_id)
        await update.message.reply_text(f"Заказ {order_id} удален, количество товара восстановлено.")
    else:
        await update.message.reply_text("Отмена удаления.")
    return await show_main_menu(update, context)


# Список товаров
async def list_products_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    products = get_all_products()
    if not products:
        await query.edit_message_text("Нет товаров.")
        return await show_main_menu(update, context)
    keyboard = []
    for p in products:
        keyboard.append([InlineKeyboardButton(f"{p[1]} ({p[2]} шт.)", callback_data=f"editproduct_{p[0]}")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="main_menu")])
    await query.edit_message_text("Список товаров:", reply_markup=InlineKeyboardMarkup(keyboard))
    return LIST_PRODUCTS_CHOICE

async def edit_product_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    # data: editproduct_{id}
    prod_id = data.split("_",1)[1]
    product = get_product_by_id(prod_id)
    if not product:
        await query.edit_message_text("Товар не найден.")
        return await show_main_menu(update, context)
    context.user_data["edit_product_id"] = prod_id
    name = product[1]
    qty = product[2]
    keyboard = [
        [InlineKeyboardButton("Изменить название", callback_data="edit_name")],
        [InlineKeyboardButton("Изменить количество", callback_data="edit_qty")],
        [InlineKeyboardButton("Назад", callback_data="main_menu")]
    ]
    await query.edit_message_text(f"Товар: {name} ({qty} шт.)", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_PRODUCT_CHOICE

async def edit_product_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "edit_name":
        await query.edit_message_text("Введите новое название товара:")
        return EDIT_PRODUCT_NAME
    elif data == "edit_qty":
        await query.edit_message_text("Введите новое количество товара:")
        return EDIT_PRODUCT_QTY
    elif data == "main_menu":
        return await show_main_menu(update, context)

async def edit_product_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    prod_id = context.user_data["edit_product_id"]
    update_product_name(prod_id, new_name)
    await update.message.reply_text("Название товара обновлено.")
    return await show_main_menu(update, context)

async def edit_product_qty_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_qty = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Количество должно быть числом. Введите снова:")
        return EDIT_PRODUCT_QTY
    prod_id = context.user_data["edit_product_id"]
    update_product_quantity(prod_id, new_qty, by_id=True)
    await update.message.reply_text("Количество товара обновлено.")
    return await show_main_menu(update, context)

# Очистка заказов
async def cleanup_orders_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Удалить за последний день", callback_data="clear_day")],
        [InlineKeyboardButton("Удалить заказы по товару", callback_data="clear_by_product")],
        [InlineKeyboardButton("Удалить заказы по клиенту", callback_data="clear_by_client")],
        [InlineKeyboardButton("Назад", callback_data="main_menu")]
    ]
    await query.edit_message_text("Выберите критерий очистки:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CLEAR_OLD_ORDERS_CHOICE

async def cleanup_orders_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "clear_day":
        # Сразу подтверждение
        await query.edit_message_text("Напишите 'удалить безвозвратно' для удаления заказов за последний день:")
        context.user_data["clear_type"] = "day"
        return CONFIRM_CLEAR_OLD_ORDERS

    elif data == "clear_by_product":
        products = get_all_products()
        if not products:
            await query.edit_message_text("Нет товаров.")
            return await show_main_menu(update, context)
        keyboard = []
        for p in products:
            keyboard.append([InlineKeyboardButton(p[1], callback_data=f"clearproduct_{p[1]}")])
        keyboard.append([InlineKeyboardButton("Назад", callback_data="main_menu")])
        await query.edit_message_text("Выберите товар для очистки заказов:", reply_markup=InlineKeyboardMarkup(keyboard))
        return CLEAR_OLD_ORDERS_BY_PRODUCT_CHOICE

    elif data == "clear_by_client":
        await query.edit_message_text("Введите имя клиента для удаления заказов:")
        context.user_data["clear_type"] = "client"
        return CLEAR_OLD_ORDERS_BY_CLIENT

    elif data == "main_menu":
        return await show_main_menu(update, context)

async def clear_orders_by_product_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    # data: clearproduct_{product_name}
    product_name = data.split("_",1)[1]
    context.user_data["clear_type"] = "product"
    context.user_data["clear_product"] = product_name
    await query.edit_message_text(f"Напишите 'удалить безвозвратно' для удаления заказов по товару {product_name}:")
    return CONFIRM_CLEAR_OLD_ORDERS

async def clear_orders_by_client_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client_data = update.message.text.strip()
    context.user_data["clear_type"] = "client_confirm"
    context.user_data["clear_client"] = client_data
    await update.message.reply_text(f"Напишите 'удалить безвозвратно' для удаления заказов по клиенту {client_data}:")
    return CONFIRM_CLEAR_OLD_ORDERS

async def confirm_clear_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    clear_type = context.user_data["clear_type"]

    if text == "удалить безвозвратно":
        if clear_type == "day":
            count = clear_orders_by_period(days=1)
        elif clear_type == "product":
            product_name = context.user_data["clear_product"]
            count = clear_orders_by_period(product_name=product_name)
        elif clear_type == "client_confirm":
            client_data = context.user_data["clear_client"]
            count = clear_orders_by_period(client_name=client_data)
        else:
            count = 0
        await update.message.reply_text(f"Удалено заказов: {count}")
    else:
        await update.message.reply_text("Отмена удаления.")

    return await show_main_menu(update, context)

# Отмена и выход в главное меню
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено, возвращаюсь в главное меню.")
    return await show_main_menu(update, context)
# --- Часть 5: Конфигурирование ConversationHandler и запуск бота ---

from telegram.ext import PicklePersistence  # Можно для сохранения состояний (по необходимости)

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_MAIN_MENU: [
                CallbackQueryHandler(add_product_start, pattern="^add_product$"),
                CallbackQueryHandler(make_order_start, pattern="^make_order$"),
                CallbackQueryHandler(check_order_start, pattern="^check_order$"),
                CallbackQueryHandler(reports_start, pattern="^reports$"),
                CallbackQueryHandler(cleanup_orders_start, pattern="^cleanup_orders$"),
                CallbackQueryHandler(list_products_start, pattern="^list_products$"),
                CallbackQueryHandler(add_user_start, pattern="^add_user$"),
            ],

            ADDING_PRODUCT_NAME_STOCK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_name)
            ],
            ADDING_PRODUCT_QTY_STOCK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_product_qty)
            ],

            ENTERING_CLIENT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_client_name)
            ],
            SELECTING_PRODUCT_FOR_ORDER: [
                CallbackQueryHandler(select_product_for_order, pattern="^select_product_")
            ],
            ENTERING_ORDER_QTY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_order_qty)
            ],
            ENTERING_ORDER_SUM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_order_sum)
            ],
            CONFIRM_ORDER: [
                MessageHandler(filters.Command(["yes","no"]), confirm_order)
            ],

            ENTERING_SEARCH_ORDER_ID_LAST6: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_order_id)
            ],
            CONFIRM_ISSUE: [
                CallbackQueryHandler(confirm_issue_handler, pattern="^issue_order_"),
                CallbackQueryHandler(show_main_menu, pattern="^main_menu$")
            ],

            # Добавление пользователя
            ADDING_USER_TELEGRAM_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, adding_user_telegram_id)
            ],
            ADDING_USER_ROLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, adding_user_role)
            ],

            SELECTING_REPORT_TYPE: [
                CallbackQueryHandler(report_type_selected, pattern="^(report_orders|report_stock|report_history|report_sales_sum)$"),
                CallbackQueryHandler(show_main_menu, pattern="^main_menu$")
            ],

            REPORT_CHOICE_FORMAT: [
                CallbackQueryHandler(report_choice_format, pattern="^(format_pdf|format_telegram|reports_back)$")
            ],
            REPORT_SEARCH_CLIENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, report_search_client)
            ],
            # После ввода клиента для report_history снова REPORT_CHOICE_FORMAT состояние,
            # но теперь мы знаем, что report_type == report_history
            REPORT_DISPLAY_HISTORY: [
                CallbackQueryHandler(view_order_from_report, pattern="^history_order_"),
                CallbackQueryHandler(show_main_menu, pattern="^main_menu$")
            ],

            REPORT_DISPLAY_ORDERS: [
                CallbackQueryHandler(view_order_from_report, pattern="^view_order_"),
                CallbackQueryHandler(show_main_menu, pattern="^main_menu$")
            ],

            REPORT_DISPLAY_STOCK: [
                CallbackQueryHandler(edit_product_from_stock_report, pattern="^editstock_"),
                CallbackQueryHandler(show_main_menu, pattern="^main_menu$")
            ],

            VIEWING_HISTORY_ORDERS: [
                CallbackQueryHandler(delete_order_confirm, pattern="^delorder_"),
                CallbackQueryHandler(show_main_menu, pattern="^main_menu$")
            ],
            DELETE_ORDER_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delete_order_execute)
            ],

            LIST_PRODUCTS_CHOICE: [
                CallbackQueryHandler(edit_product_choice, pattern="^editproduct_"),
                CallbackQueryHandler(show_main_menu, pattern="^main_menu$")
            ],
            EDIT_PRODUCT_CHOICE: [
                CallbackQueryHandler(edit_product_action, pattern="^(edit_name|edit_qty|main_menu)$")
            ],
            EDIT_PRODUCT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_product_name_handler)
            ],
            EDIT_PRODUCT_QTY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_product_qty_handler)
            ],

            CLEAR_OLD_ORDERS_CHOICE: [
                CallbackQueryHandler(cleanup_orders_choice, pattern="^(clear_day|clear_by_product|clear_by_client|main_menu)$")
            ],
            CLEAR_OLD_ORDERS_BY_PRODUCT_CHOICE: [
                CallbackQueryHandler(clear_orders_by_product_choice, pattern="^clearproduct_"),
                CallbackQueryHandler(show_main_menu, pattern="^main_menu$")
            ],
            CLEAR_OLD_ORDERS_BY_CLIENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, clear_orders_by_client_handler)
            ],
            CONFIRM_CLEAR_OLD_ORDERS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_clear_orders)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
        conversation_timeout=300  # Время ожидания (можно настроить)
    )

    # Хэндлеры для add_user_start, adding_user_telegram_id, adding_user_role, etc.
    application.add_handler(conv_handler)

    application.run_polling()

async def add_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.edit_message_text("У вас нет прав для добавления пользователей.")
        return CHOOSING_MAIN_MENU

    await query.edit_message_text("Введите Telegram ID нового пользователя:")
    return ADDING_USER_TELEGRAM_ID

async def adding_user_telegram_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Telegram ID должен быть числом. Введите снова:")
        return ADDING_USER_TELEGRAM_ID
    context.user_data["new_user_id"] = new_user_id
    await update.message.reply_text("Введите роль пользователя (admin или viewer):")
    return ADDING_USER_ROLE

async def adding_user_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = update.message.text.strip()
    if role not in ["admin", "viewer"]:
        await update.message.reply_text("Роль должна быть admin или viewer. Введите снова:")
        return ADDING_USER_ROLE

    new_user_id = context.user_data["new_user_id"]
    if get_user_role(new_user_id) is not None:
        await update.message.reply_text("Пользователь с таким Telegram ID уже существует.")
    else:
        add_user_db(new_user_id, role)
        await update.message.reply_text(f"Пользователь {new_user_id} добавлен с ролью {role}")

    return await show_main_menu(update, context)

async def edit_product_from_stock_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Аналогично edit_product_choice
    query = update.callback_query
    await query.answer()
    data = query.data
    prod_id = data.split("_",1)[1]
    product = get_product_by_id(prod_id)
    if not product:
        await query.edit_message_text("Товар не найден.")
        return await show_main_menu(update, context)
    context.user_data["edit_product_id"] = prod_id
    name = product[1]
    qty = product[2]
    keyboard = [
        [InlineKeyboardButton("Изменить название", callback_data="edit_name")],
        [InlineKeyboardButton("Изменить количество", callback_data="edit_qty")],
        [InlineKeyboardButton("Назад", callback_data="main_menu")]
    ]
    await query.edit_message_text(f"Товар: {name} ({qty} шт.)", reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_PRODUCT_CHOICE

async def timeout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message:
        await update.effective_message.reply_text("Время ожидания истекло. Возвращаюсь в главное меню.")
    return await show_main_menu(update, context)

if __name__ == "__main__":
    main()
