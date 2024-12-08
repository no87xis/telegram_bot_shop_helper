import os
import sqlite3
import datetime
import random
import string
from io import BytesIO

from fpdf import FPDF
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters, ConversationHandler
)

BOT_TOKEN = "7824760453:AAGuV6vdRhNhvot3xIIgPK0WsnEE8KX5tHI"  # Подставьте ваш токен

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
    SELECTING_USER_ACTION,
    VIEWING_HISTORY_ORDERS,
    # TIMEOUT не является числовым состоянием, используется ConversationHandler.TIMEOUT
) = range(14)

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        role TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        quantity INTEGER
    )
    """)

    # Добавляем поле sum_paid для хранения суммы предоплаты за заказ
    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT UNIQUE,
        client_name TEXT,
        product_name TEXT,
        quantity INTEGER,
        date TEXT,
        status TEXT,
        sum_paid REAL
    )
    """)

    conn.commit()
    conn.close()

init_db()

def get_user_role(telegram_id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE telegram_id=?", (telegram_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def add_user(telegram_id, role):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (telegram_id, role) VALUES (?,?)", (telegram_id, role))
        conn.commit()
    except:
        pass
    conn.close()

def generate_order_id():
    now = datetime.datetime.now()
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    random_part = ''.join(random.choices(string.digits, k=6))
    return f"ORD{date_part}-{time_part}-{random_part}"

def add_product(name, qty):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO products (name, quantity) VALUES (?,?)", (name, qty))
        conn.commit()
    except:
        pass
    conn.close()

def update_product_quantity(name, qty):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("UPDATE products SET quantity=? WHERE name=?", (qty, name))
    conn.commit()
    conn.close()

def get_all_products():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT name, quantity FROM products")
    rows = c.fetchall()
    conn.close()
    return rows

def create_order(client_name, product_name, quantity, sum_paid):
    order_id = generate_order_id()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO orders (order_id, client_name, product_name, quantity, date, status, sum_paid)
        VALUES (?,?,?,?,?,?,?)
    """, (order_id, client_name, product_name, quantity, now, "Оплачено", sum_paid))
    conn.commit()
    conn.close()
    products = dict(get_all_products())
    new_qty = products.get(product_name,0) - quantity
    update_product_quantity(product_name, new_qty)
    return order_id

def get_order_by_id(order_id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT order_id, client_name, product_name, quantity, date, status, sum_paid FROM orders WHERE order_id=?", (order_id,))
    row = c.fetchone()
    conn.close()
    return row

def delete_order(order_id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("DELETE FROM orders WHERE order_id=?", (order_id,))
    conn.commit()
    conn.close()

def search_orders_by_client(client_data):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("""
        SELECT order_id, client_name, product_name, quantity, date, status, sum_paid
        FROM orders
        WHERE client_name LIKE ?
        ORDER BY date DESC
    """, (f"%{client_data}%",))
    rows = c.fetchall()
    conn.close()
    return rows

def get_sales_summary():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT SUM(sum_paid) FROM orders")
    total_sum = c.fetchone()[0]
    if total_sum is None:
        total_sum = 0.0

    c.execute("""
        SELECT product_name, SUM(sum_paid)
        FROM orders
        GROUP BY product_name
    """)
    product_sums = c.fetchall()
    conn.close()
    return total_sum, product_sums

def setup_unicode_pdf(pdf, size=10):
    pdf.add_font("DejaVu", "", "DejaVuSansCondensed.ttf", uni=True)
    pdf.set_font("DejaVu", "", size)

def generate_pdf_order_details(order):
    order_id, client_name, product_name, quantity, date, status, sum_paid = order
    quantity = int(quantity)
    price_per_item = sum_paid / quantity if quantity > 0 else 0

    buffer = BytesIO()
    pdf = FPDF()
    pdf.add_page()

    setup_unicode_pdf(pdf, 10)

    # Шапка и водяной знак (упрощаем водяной знак, просто ставим логотип фоново)
    if os.path.exists("logo.png"):
        # водяной знак: можно просто большой светлый логотип в центре (в реальности нужно заранее сделать бледный логотип)
        # Здесь для упрощения пропускаем реальную прозрачность
        pass

    # Шапка документа
    pdf.set_xy(10,10)
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 10, 10, 20)
    pdf.set_xy(35,10)
    pdf.set_font("DejaVu", "", 14)
    pdf.cell(0,10,"SIRIUS TRADE", ln=1)
    pdf.set_font("DejaVu","",8)
    pdf.set_x(35)
    pdf.cell(0,5,"г. Примерск, ул. Примера, д.1", ln=1)
    pdf.set_x(35)
    pdf.cell(0,5,"Телефон: +7(999)999-99-99", ln=1)
    pdf.ln(5)
    pdf.set_draw_color(150,150,150)
    pdf.set_line_width(0.5)
    pdf.line(10,pdf.get_y(),200,pdf.get_y())
    pdf.ln(5)

    # Заголовок
    pdf.set_font("DejaVu","",16)
    pdf.cell(0,10,"Счёт / Квитанция об оплате", ln=1, align='C')
    pdf.ln(5)

    pdf.set_font("DejaVu","",10)

    def table_row(label, value):
        pdf.set_x(20)
        pdf.set_draw_color(200,200,200)
        pdf.cell(50,8,label, border=0)
        pdf.cell(0,8,str(value), border=0, ln=1)

    table_row("ID заказа:", order_id)
    table_row("Дата оплаты:", date)
    table_row("Имя клиента:", client_name)
    table_row("Товар:", product_name)
    table_row("Количество:", quantity)
    table_row("Сумма оплачена:", f"{sum_paid:.2f} руб.")
    table_row("Цена за штуку:", f"{price_per_item:.2f} руб.")
    table_row("Статус:", status)

    pdf.ln(10)
    pdf.cell(0,5,"Данный документ подтверждает факт предоплаты по заказу. Для получения товара",ln=1)
    pdf.cell(0,5,"предъявите уникальный номер заказа.",ln=1)

    pdf.ln(5)
    pdf.set_draw_color(150,150,150)
    pdf.line(10,pdf.get_y(),200,pdf.get_y())
    pdf.ln(5)

    pdf.set_font("DejaVu","",9)
    pdf.cell(0,5,"Спасибо за ваш выбор! SIRIUS TRADE ©", align='C', ln=1)

    pdf.output(buffer, 'F')
    buffer.seek(0)
    return buffer

def generate_report_orders():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT order_id, client_name, product_name, quantity, date, status, sum_paid FROM orders")
    rows = c.fetchall()
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
        order_id, client_name, product_name, quantity, date, status, sum_paid = row
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
        order_id, client_name, product_name, quantity, date, status, sum_paid = row
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
        # Добавить товар: спросим название
        await query.message.reply_text("Введите название товара:")
        context.user_data["current_state"] = ADDING_PRODUCT_NAME_STOCK
        return ADDING_PRODUCT_NAME_STOCK

    if data == "make_order":
        if role not in ["admin","viewer"]:
            await query.message.reply_text("Недостаточно прав.")
            return CHOOSING_MAIN_MENU
        # Сделать предоплату: сперва имя клиента
        await query.message.reply_text("Введите имя клиента:")
        context.user_data["current_state"] = ENTERING_CLIENT_NAME
        return ENTERING_CLIENT_NAME

    if data == "check_order":
        if role not in ["admin","viewer"]:
            await query.message.reply_text("Недостаточно прав.")
            return CHOOSING_MAIN_MENU
        await query.message.reply_text("Введите уникальный ID заказа:")
        context.user_data["current_state"] = ENTERING_SEARCH_ORDER_ID
        return ENTERING_SEARCH_ORDER_ID

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
        cleanup_old_orders()
        await query.message.reply_text("Старые записи старше 6 месяцев удалены.")
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

    if data.startswith("product_"):
        # Это выбор товара при предоплате
        product_name = data.split("_",1)[1]
        context.user_data["order_product_name"] = product_name
        await query.message.reply_text(f"Вы выбрали: {product_name}. Введите количество:")
        context.user_data["current_state"] = ENTERING_ORDER_QTY
        return ENTERING_ORDER_QTY

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

    return CHOOSING_MAIN_MENU

def history_orders_markup(rows):
    keyboard = []
    for r in rows:
        order_id, client_name, product_name, quantity, date, status, sum_paid = r
        kb_line = [InlineKeyboardButton(f"Удалить {product_name} ({quantity} шт.) {date} (ID:{order_id})", callback_data=f"delorder_{order_id}")]
        keyboard.append(kb_line)
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_history")])
    return InlineKeyboardMarkup(keyboard)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = get_user_role(update.effective_user.id)
    if role is None:
        await update.message.reply_text("Вы не авторизованы.")
        return ConversationHandler.END

    current_state = context.user_data.get("current_state")

    # Добавить товар в наличии
    if current_state == ADDING_PRODUCT_NAME_STOCK:
        context.user_data["stock_product_name"] = update.message.text
        await update.message.reply_text("Введите количество для этого товара:")
        context.user_data["current_state"] = ADDING_PRODUCT_QTY_STOCK
        return ADDING_PRODUCT_QTY_STOCK

    if current_state == ADDING_PRODUCT_QTY_STOCK:
        qty = int(update.message.text)
        name = context.user_data["stock_product_name"]
        add_product(name, qty)
        await update.message.reply_text(f"Товар {name} добавлен с остатком {qty} шт.")
        context.user_data["current_state"] = CHOOSING_MAIN_MENU
        return await show_main_menu(update, context)

    # Сделать предоплату
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

    if current_state == ENTERING_SEARCH_ORDER_ID:
        order_id = update.message.text
        order = get_order_by_id(order_id)
        if order:
            o_id, c_name, p_name, q, d, st, sp = order
            await update.message.reply_text(
                f"Заказ: {o_id}\nКлиент: {c_name}\nТовар: {p_name} x {q}\nДата: {d}\nСтатус: {st}\nСумма: {sp:.2f}"
            )
        else:
            await update.message.reply_text("Заказ не найден.")
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

    # Неизвестная команда
    await update.message.reply_text("Неизвестная команда, возвращаюсь в главное меню.")
    context.user_data["current_state"] = CHOOSING_MAIN_MENU
    return await show_main_menu(update, context)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = get_user_role(update.effective_user.id)
    if role is None:
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        count = c.fetchone()[0]
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

            ENTERING_SEARCH_ORDER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            ADDING_USER_TELEGRAM_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            ADDING_USER_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            SELECTING_REPORT_TYPE: [CallbackQueryHandler(button_handler)],
            SELECTING_USER_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            VIEWING_HISTORY_ORDERS: [CallbackQueryHandler(button_handler)],

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
