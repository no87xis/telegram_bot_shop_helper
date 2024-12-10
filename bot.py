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
DB_PRFX = 'bot_'

BOT_TOKEN = "7824760453:AAGuV6vdRhNhvot3xIIgPK0WsnEE8KX5tHI"

# Состояния диалогов
(
    CHOOSING_MAIN_MENU,
    ADDING_PRODUCT_NAME_STOCK,
    ADDING_PRODUCT_QTY_STOCK,
    ENTERING_CLIENT_NAME,
    SELECTING_PRODUCT_FOR_ORDER,
    ENTERING_ORDER_QTY,
    ENTERING_ORDER_SUM,
    CONFIRM_ORDER,
    ENTERING_SEARCH_ORDER_ID,
    ADDING_USER_TELEGRAM_ID,
    ADDING_USER_ROLE,
    SELECTING_REPORT_TYPE,
    ENTERING_REPORT_DATE_RANGE_START,
    ENTERING_REPORT_DATE_RANGE_END,
    VIEWING_HISTORY_ORDERS,
    CONFIRM_CLEAR_ORDERS
) = range(16)

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
        if c:
            c.close()
        if conn:
            conn.close()

# Инициализируем базу данных
init_db()

def generate_order_id():
    now = datetime.datetime.now()
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    random_part = ''.join(random.choices(string.digits, k=6))
    return f"ORD{date_part}-{time_part}-{random_part}"

def add_user_db(telegram_id, role):
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"INSERT INTO {DB_PRFX}users (telegram_id, role) VALUES (%s,%s)", (telegram_id, role))
        conn.commit()
        logger.info(f"Пользователь с telegram_id {telegram_id} добавлен с ролью {role}")
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при добавлении пользователя: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

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
        return None
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

def is_admin(telegram_id):
    role = get_user_role(telegram_id)
    return role == "admin"

def main_menu_keyboard():
    # Главное меню
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
    if update.message:
        await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())
    else:
        await update.callback_query.edit_message_text("Главное меню:", reply_markup=main_menu_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = None
    conn = None
    user_id = update.effective_user.id
    role = get_user_role(user_id)
    if role is None:
        try:
            conn = get_connection()
            c = conn.cursor()
            c.execute(f"SELECT COUNT(*) FROM {DB_PRFX}users")
            count = c.fetchone()[0]
            if count == 0:
                # Первый пользователь становится админом
                add_user_db(user_id, "admin")
                await update.message.reply_text("Вы стали админом, так как это первый запуск бота.")
            else:
                await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
                return
        except mysql.connector.Error as err:
            logger.error(f"Ошибка при проверке пользователей: {err}")
        finally:
            if c:
                c.close()
            if conn:
                conn.close()
    await show_main_menu(update, context)

# Добавление товара (только админ)
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.answer("У вас нет прав для добавления товаров.")
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
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT id FROM {DB_PRFX}products WHERE name=%s", (name,))
        if c.fetchone():
            await update.message.reply_text("Товар с таким названием уже существует!")
        else:
            c.execute(f"INSERT INTO {DB_PRFX}products (name, quantity) VALUES (%s, %s)", (name, qty))
            conn.commit()
            await update.message.reply_text(f"Товар '{name}' добавлен с количеством {qty}")
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при добавлении товара: {err}")
        await update.message.reply_text("Ошибка при добавлении товара, попробуйте позже.")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

    await show_main_menu(update, context)
    return CHOOSING_MAIN_MENU

# Создание заказа (предоплата)
async def make_payment_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text("Введите имя клиента:")
    return ENTERING_CLIENT_NAME

async def enter_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["client_name"] = update.message.text.strip()
    # Показать список товаров
    products = get_all_products()
    if not products:
        await update.message.reply_text("Нет доступных товаров для заказа.")
        await show_main_menu(update, context)
        return CHOOSING_MAIN_MENU

    keyboard = [[InlineKeyboardButton(p[1], callback_data=f"select_product_{p[0]}")] for p in products]
    await update.message.reply_text("Выберите товар для заказа:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_PRODUCT_FOR_ORDER

def get_all_products():
    c = None
    conn = None
    products = []
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT id, name, quantity FROM {DB_PRFX}products")
        products = c.fetchall()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении списка товаров: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return products

async def select_product_for_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    product_id = data.split("_")[-1]
    # Получим имя товара
    product = get_product_by_id(product_id)
    if not product:
        await query.answer("Товар не найден.")
        await show_main_menu(update, context)
        return CHOOSING_MAIN_MENU

    context.user_data["order_product"] = product[1]
    await query.edit_message_text(f"Вы выбрали: {product[1]}\nВведите количество:")
    return ENTERING_ORDER_QTY

def get_product_by_id(pid):
    c = None
    conn = None
    product = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT id, name, quantity FROM {DB_PRFX}products WHERE id=%s", (pid,))
        product = c.fetchone()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении товара: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return product

async def enter_order_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Количество должно быть числом. Попробуйте снова:")
        return ENTERING_ORDER_QTY
    context.user_data["order_qty"] = qty
    # Проверим остатки
    product_name = context.user_data["order_product"]
    available_qty = get_product_quantity(product_name)
    if available_qty < qty:
        await update.message.reply_text(f"Недостаточно товара. В наличии: {available_qty}. Введите другое количество или /cancel для отмены:")
        return ENTERING_ORDER_QTY

    await update.message.reply_text("Введите сумму предоплаты:")
    return ENTERING_ORDER_SUM

def get_product_quantity(name):
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
        # Сохраняем заказ
        order_id = generate_order_id()
        client_name = context.user_data["client_name"]
        product_name = context.user_data["order_product"]
        qty = context.user_data["order_qty"]
        sum_paid = context.user_data["order_sum"]
        status = "paid" if sum_paid > 0 else "unpaid"
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        issuer_id = update.effective_user.id

        # Обновить количество товара
        if not reduce_product_quantity(product_name, qty):
            await update.message.reply_text("Ошибка обновления количества товара.")
            await show_main_menu(update, context)
            return CHOOSING_MAIN_MENU

        add_order_db(order_id, client_name, product_name, qty, date_str, status, sum_paid, date_str, issuer_id)

        await update.message.reply_text(f"Заказ создан. ID заказа: {order_id}")
    else:
        await update.message.reply_text("Заказ отменён.")

    await show_main_menu(update, context)
    return CHOOSING_MAIN_MENU

def reduce_product_quantity(name, qty):
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"SELECT quantity FROM {DB_PRFX}products WHERE name=%s", (name,))
        row = c.fetchone()
        if row and row[0] >= qty:
            new_qty = row[0] - qty
            c.execute(f"UPDATE {DB_PRFX}products SET quantity=%s WHERE name=%s", (new_qty, name))
            conn.commit()
            return True
        return False
    except mysql.connector.Error as err:
        logger.error(f"Ошибка уменьшения количества товара: {err}")
        return False
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

def add_order_db(order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id):
    c = None
    conn = None
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute(f"""
            INSERT INTO {DB_PRFX}orders (order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (order_id, client_name, product_name, quantity, date, status, sum_paid, issue_date, issuer_id))
        conn.commit()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при добавлении заказа: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()

# Проверка заказа по ID
async def check_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text("Введите ID заказа для проверки:")
    return ENTERING_SEARCH_ORDER_ID

async def check_order_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_id = update.message.text.strip()
    order = get_order_by_id(order_id)
    if not order:
        await update.message.reply_text("Заказ не найден.")
    else:
        client_name = order["client_name"]
        product_name = order["product_name"]
        quantity = order["quantity"]
        date = order["date"]
        status = order["status"]
        sum_paid = order["sum_paid"]
        await update.message.reply_text(
            f"Информация по заказу {order_id}:\n"
            f"Клиент: {client_name}\n"
            f"Товар: {product_name}\n"
            f"Количество: {quantity}\n"
            f"Дата: {date}\n"
            f"Статус: {status}\n"
            f"Сумма предоплаты: {sum_paid}"
        )
    await show_main_menu(update, context)
    return CHOOSING_MAIN_MENU

def get_order_by_id(order_id):
    c = None
    conn = None
    result = None
    try:
        conn = get_connection()
        c = conn.cursor(dictionary=True)
        c.execute(f"SELECT * FROM {DB_PRFX}orders WHERE order_id=%s", (order_id,))
        result = c.fetchone()
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при получении заказа: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return result

# Отчёты
async def reports_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("Отчёт по складу", callback_data="report_stock")],
        [InlineKeyboardButton("Отчёт по заказам", callback_data="report_orders")],
        [InlineKeyboardButton("Назад", callback_data="main_menu")]
    ]
    await query.edit_message_text("Выберите тип отчёта:", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECTING_REPORT_TYPE

async def report_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    products = get_all_products()
    if not products:
        await query.edit_message_text("Склад пуст.")
        await show_main_menu(update, context)
        return CHOOSING_MAIN_MENU

    text = "Отчёт по складу:\n"
    for p in products:
        text += f"{p[1]}: {p[2]}\n"
    await query.edit_message_text(text)
    await show_main_menu(update, context)
    return CHOOSING_MAIN_MENU

async def report_orders_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text("Введите начальную дату (формат YYYY-MM-DD):")
    return ENTERING_REPORT_DATE_RANGE_START

async def report_orders_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_date = update.message.text.strip()
    # Примитивная проверка
    try:
        datetime.datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Неверный формат даты, введите заново:")
        return ENTERING_REPORT_DATE_RANGE_START
    context.user_data["report_start_date"] = start_date
    await update.message.reply_text("Введите конечную дату (формат YYYY-MM-DD):")
    return ENTERING_REPORT_DATE_RANGE_END

async def report_orders_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    end_date = update.message.text.strip()
    try:
        datetime.datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Неверный формат даты, введите заново:")
        return ENTERING_REPORT_DATE_RANGE_END
    context.user_data["report_end_date"] = end_date

    start_date = context.user_data["report_start_date"]
    orders_info = get_orders_report(start_date, end_date)
    total_orders = orders_info["total_orders"]
    total_sum = orders_info["total_sum"]

    await update.message.reply_text(
        f"Отчёт по заказам с {start_date} по {end_date}:\n"
        f"Количество заказов: {total_orders}\n"
        f"Общая сумма предоплат: {total_sum}"
    )

    await show_main_menu(update, context)
    return CHOOSING_MAIN_MENU

def get_orders_report(start_date, end_date):
    c = None
    conn = None
    result = {"total_orders": 0, "total_sum": 0.0}
    try:
        conn = get_connection()
        c = conn.cursor()
        query = f"SELECT COUNT(*), SUM(sum_paid) FROM {DB_PRFX}orders WHERE date BETWEEN %s AND %s"
        c.execute(query, (start_date + " 00:00:00", end_date + " 23:59:59"))
        row = c.fetchone()
        if row:
            result["total_orders"] = row[0] if row[0] else 0
            result["total_sum"] = row[1] if row[1] else 0.0
    except mysql.connector.Error as err:
        logger.error(f"Ошибка при формировании отчёта по заказам: {err}")
    finally:
        if c:
            c.close()
        if conn:
            conn.close()
    return result

# Очистка старых заказов
async def clear_orders_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.answer("У вас нет прав для очистки заказов.")
        return CHOOSING_MAIN_MENU

    await query.edit_message_text("Удалить заказы старше 30 дней? /yes для подтверждения, /no для отмены.")
    return CONFIRM_CLEAR_ORDERS

async def confirm_clear_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()
    if text == "/yes":
        cleared = clear_old_orders()
        await update.message.reply_text(f"Удалено заказов: {cleared}")
    else:
        await update.message.reply_text("Очистка отменена.")

    await show_main_menu(update, context)
    return CHOOSING_MAIN_MENU

def clear_old_orders():
    c = None
    conn = None
    count = 0
    try:
        conn = get_connection()
        c = conn.cursor()
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
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

# Добавление пользователя (админ)
async def add_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await query.answer("У вас нет прав для добавления пользователей.")
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
    await update.message.reply_text("Введите роль пользователя (admin или user):")
    return ADDING_USER_ROLE

async def adding_user_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = update.message.text.strip()
    if role not in ["admin", "user"]:
        await update.message.reply_text("Роль должна быть admin или user. Введите снова:")
        return ADDING_USER_ROLE

    new_user_id = context.user_data["new_user_id"]
    # Добавляем в БД
    # Проверяем, есть ли уже пользователь
    if get_user_role(new_user_id) is not None:
        await update.message.reply_text("Пользователь с таким Telegram ID уже существует.")
    else:
        add_user_db(new_user_id, role)
        await update.message.reply_text(f"Пользователь {new_user_id} добавлен с ролью {role}")

    await show_main_menu(update, context)
    return CHOOSING_MAIN_MENU

# Список товаров
async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    products = get_all_products()
    if not products:
        await query.edit_message_text("Нет товаров.")
    else:
        text = "Список товаров:\n"
        for p in products:
            text += f"{p[1]}: {p[2]}\n"
        await query.edit_message_text(text)

    await show_main_menu(update, context)
    return CHOOSING_MAIN_MENU

async def main_menu_return(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context)
    return CHOOSING_MAIN_MENU

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.")
    await show_main_menu(update, context)
    return CHOOSING_MAIN_MENU

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_MAIN_MENU: [
                CallbackQueryHandler(add_product_start, pattern="^add_product$"),
                CallbackQueryHandler(make_payment_start, pattern="^make_payment$"),
                CallbackQueryHandler(check_order_start, pattern="^check_order$"),
                CallbackQueryHandler(reports_start, pattern="^reports$"),
                CallbackQueryHandler(clear_orders_start, pattern="^clear_orders$"),
                CallbackQueryHandler(add_user_start, pattern="^add_user$"),
                CallbackQueryHandler(list_products, pattern="^list_products$"),
                CallbackQueryHandler(main_menu_return, pattern="^main_menu$")
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
            ENTERING_SEARCH_ORDER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_order_id)
            ],
            SELECTING_REPORT_TYPE: [
                CallbackQueryHandler(report_stock, pattern="^report_stock$"),
                CallbackQueryHandler(report_orders_start, pattern="^report_orders$"),
                CallbackQueryHandler(main_menu_return, pattern="^main_menu$")
            ],
            ENTERING_REPORT_DATE_RANGE_START: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, report_orders_start_date)
            ],
            ENTERING_REPORT_DATE_RANGE_END: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, report_orders_end_date)
            ],
            ADDING_USER_TELEGRAM_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, adding_user_telegram_id)
            ],
            ADDING_USER_ROLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, adding_user_role)
            ],
            CONFIRM_CLEAR_ORDERS: [
                MessageHandler(filters.Command(["yes","no"]), confirm_clear_orders)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
