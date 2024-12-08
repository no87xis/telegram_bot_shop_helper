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
    ADDING_PRODUCT_NAME,
    ADDING_PRODUCT_QTY,
    SELECTING_PRODUCT_FOR_ORDER,
    ENTERING_CLIENT_NAME,
    ENTERING_ORDER_QTY,
    CONFIRM_ORDER,
    ENTERING_SEARCH_ORDER_ID,
    ADDING_USER_TELEGRAM_ID,
    ADDING_USER_ROLE,
    SELECTING_REPORT_TYPE,
    SELECTING_USER_ACTION,
    VIEWING_HISTORY_ORDERS,  # Новое состояние для просмотра и удаления заказов клиента
) = range(13)

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
    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT UNIQUE,
        client_name TEXT,
        product_name TEXT,
        quantity INTEGER,
        date TEXT,
        status TEXT
    )
    """)
    # Обратите внимание: убрали client_phone из таблицы orders
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

def create_order(client_name, product_name, quantity):
    order_id = generate_order_id()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO orders (order_id, client_name, product_name, quantity, date, status)
        VALUES (?,?,?,?,?,?)
    """, (order_id, client_name, product_name, quantity, now, "Оплачено"))
    conn.commit()
    conn.close()
    products = dict(get_all_products())
    new_qty = products.get(product_name,0) - quantity
    update_product_quantity(product_name, new_qty)
    return order_id

def get_order_by_id(order_id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT order_id, client_name, product_name, quantity, date, status FROM orders WHERE order_id=?", (order_id,))
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
    # Поиск по имени клиента
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("""
        SELECT order_id, client_name, product_name, quantity, date, status 
        FROM orders 
        WHERE client_name LIKE ?
        ORDER BY date DESC
    """, (f"%{client_data}%",))
    rows = c.fetchall()
    conn.close()
    return rows

def setup_unicode_pdf(pdf, size=10):
    # Добавляем шрифт DejaVu для поддержки Unicode
    pdf.add_font("DejaVu", "", "DejaVuSansCondensed.ttf", uni=True)
    pdf.set_font("DejaVu", "", size)

def generate_pdf_order_details(order):
    # order: order_id, client_name, product_name, quantity, date, status
    buffer = BytesIO()
    pdf = FPDF()
    pdf.add_page()
    setup_unicode_pdf(pdf, 12)
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 10, 8, 33)
    pdf.ln(20)
    pdf.cell(0, 10, f"ID заказа: {order[0]}", 0, 1)
    pdf.cell(0, 10, f"Дата оплаты: {order[4]}", 0, 1)
    pdf.cell(0, 10, f"Имя клиента: {order[1]}", 0, 1)
    pdf.cell(0, 10, f"Товар: {order[2]}", 0, 1)
    pdf.cell(0, 10, f"Количество: {order[3]}", 0, 1)
    pdf.cell(0, 10, f"Статус: {order[5]}", 0, 1)
    pdf.output(buffer, 'F')
    buffer.seek(0)
    return buffer

def generate_report_orders():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT order_id, client_name, product_name, quantity, date, status FROM orders")
    rows = c.fetchall()
    conn.close()

    buffer = BytesIO()
    pdf = FPDF()
    pdf.add_page()
    setup_unicode_pdf(pdf, 10)
    if os.path.exists("logo.png"):
        pdf.image("logo.png", 10, 8, 33)
    pdf.ln(20)
    pdf.cell(0,10,"Отчет по заказам",0,1)
    pdf.ln(5)
    for row in rows:
        pdf.cell(0,8,f"ID: {row[0]} | {row[1]} - {row[2]} x {row[3]} | Дата: {row[4]} | Статус: {row[5]}",0,1)
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
    pdf.cell(0,10,"Отчет по остаткам",0,1)
    pdf.ln(5)
    for p in products:
        pdf.cell(0,8,f"Товар: {p[0]} | Остаток: {p[1]}",0,1)
    pdf.output(buffer,'F')
    buffer.seek(0)
    return buffer

def cleanup_old_orders():
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=180)).strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("DELETE FROM orders WHERE date < ?", (cutoff,))
    conn.commit()
    conn.close()

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
        await update.message.reply_text("Вы не авторизованы для работы с этим ботом.")
        return ConversationHandler.END

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
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
            await query.edit_message_text("Недостаточно прав.")
            return CHOOSING_MAIN_MENU
        await query.edit_message_text("Введите название товара:")
        context.user_data["current_state"] = ADDING_PRODUCT_NAME
        return ADDING_PRODUCT_NAME

    if data == "make_order":
        await query.edit_message_text("Введите имя клиента:")
        context.user_data["current_state"] = ENTERING_CLIENT_NAME
        return ENTERING_CLIENT_NAME

    if data == "check_order":
        await query.edit_message_text("Введите уникальный ID заказа:")
        context.user_data["current_state"] = ENTERING_SEARCH_ORDER_ID
        return ENTERING_SEARCH_ORDER_ID

    if data == "reports":
        if role != "admin":
            await query.edit_message_text("Недостаточно прав.")
            return CHOOSING_MAIN_MENU
        keyboard = [
            [InlineKeyboardButton("Отчет по заказам", callback_data="report_orders")],
            [InlineKeyboardButton("Отчет по остаткам", callback_data="report_stock")],
            [InlineKeyboardButton("История по клиенту (управление данными)", callback_data="report_history")]
        ]
        await query.edit_message_text("Выберите тип отчета:", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["current_state"] = SELECTING_REPORT_TYPE
        return SELECTING_REPORT_TYPE

    if data == "cleanup_old":
        if role != "admin":
            await query.edit_message_text("Недостаточно прав.")
            return CHOOSING_MAIN_MENU
        cleanup_old_orders()
        return await show_main_menu(update, context, text="Старые записи старше 6 месяцев удалены.\nГлавное меню:")

    if data == "add_user":
        if role != "admin":
            await query.edit_message_text("Недостаточно прав.")
            return CHOOSING_MAIN_MENU
        await query.edit_message_text("Введите Telegram ID пользователя, которого хотите добавить:")
        context.user_data["current_state"] = ADDING_USER_TELEGRAM_ID
        return ADDING_USER_TELEGRAM_ID

    if data == "list_products":
        products = get_all_products()
        text = "Список товаров:\n"
        for p in products:
            text += f"{p[0]}: {p[1]} шт.\n"
        return await show_main_menu(update, context, text=text)

    if data == "report_orders":
        try:
            buffer = generate_report_orders()
            await query.edit_message_text("Отчет по заказам:")
            await query.message.reply_document(document=buffer, filename="orders_report.pdf")
        except Exception as e:
            await query.edit_message_text(f"Ошибка при генерации отчёта: {e}")
        return await show_main_menu(update, context)

    if data == "report_stock":
        try:
            buffer = generate_report_stock()
            await query.edit_message_text("Отчет по остаткам:")
            await query.message.reply_document(document=buffer, filename="stock_report.pdf")
        except Exception as e:
            await query.edit_message_text(f"Ошибка при генерации отчёта: {e}")
        return await show_main_menu(update, context)

    if data == "report_history":
        await query.edit_message_text("Введите имя клиента для поиска:")
        context.user_data["current_state"] = SELECTING_USER_ACTION
        return SELECTING_USER_ACTION

    # Обработка нажатий для удаления заказов:
    if data.startswith("delorder_"):
        order_id = data.split("_",1)[1]
        delete_order(order_id)
        # Обновим список
        client_data = context.user_data.get("history_client_data")
        rows = search_orders_by_client(client_data)
        if rows:
            await query.edit_message_text("Обновлённый список заказов:", 
                                          reply_markup=history_orders_markup(rows))
            context.user_data["current_state"] = VIEWING_HISTORY_ORDERS
            return VIEWING_HISTORY_ORDERS
        else:
            # Нет заказов
            return await show_main_menu(update, context, text="Все заказы удалены или отсутствуют.\nГлавное меню:")

    if data == "back_history":
        return await show_main_menu(update, context)

    return CHOOSING_MAIN_MENU

def history_orders_markup(rows):
    # Генерируем клавиатуру для просмотра заказов
    # Каждая строка: Товар, Дата, Количество, кнопка Удалить
    keyboard = []
    for r in rows:
        # r: order_id, client_name, product_name, quantity, date, status
        text = f"{r[2]} x {r[3]} | {r[4]} | Статус: {r[5]} (ID:{r[0]})"
        # Кнопка удаления
        kb_line = [InlineKeyboardButton("Удалить", callback_data=f"delorder_{r[0]}")]
        keyboard.append(kb_line)
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_history")])
    return InlineKeyboardMarkup(keyboard)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = get_user_role(update.effective_user.id)
    if role is None:
        await update.message.reply_text("Вы не авторизованы.")
        return ConversationHandler.END

    current_state = context.user_data.get("current_state")

    if current_state == ADDING_PRODUCT_NAME:
        context.user_data["new_product_name"] = update.message.text
        await update.message.reply_text("Введите количество для этого товара:")
        context.user_data["current_state"] = ADDING_PRODUCT_QTY
        return ADDING_PRODUCT_QTY

    if current_state == ADDING_PRODUCT_QTY:
        qty = int(update.message.text)
        name = context.user_data["new_product_name"]
        add_product(name, qty)
        await update.message.reply_text(f"Товар {name} добавлен с остатком {qty} шт.")
        context.user_data["current_state"] = CHOOSING_MAIN_MENU
        return await show_main_menu(update, context)

    if current_state == ENTERING_CLIENT_NAME:
        context.user_data["client_name"] = update.message.text
        # Сразу выводим список товаров, пропускаем ввод телефона
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
        context.user_data["order_quantity"] = qty
        product_name = context.user_data["selected_product"]
        client_name = context.user_data["client_name"]
        await update.message.reply_text(f"Вы хотите оплатить {qty} шт. {product_name} для {client_name}? (Да/Нет)")
        context.user_data["current_state"] = CONFIRM_ORDER
        return CONFIRM_ORDER

    if current_state == CONFIRM_ORDER:
        answer = update.message.text.lower()
        if answer == "да":
            product_name = context.user_data["selected_product"]
            qty = context.user_data["order_quantity"]
            client_name = context.user_data["client_name"]
            order_id = create_order(client_name, product_name, qty)
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
            await update.message.reply_text(
                f"Заказ: {order[0]}\nКлиент: {order[1]}\nТовар: {order[2]} x {order[3]}\nДата: {order[4]}\nСтатус: {order[5]}"
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
        # В теории, сюда текст не должен попадать, т.к. мы работаем через кнопки.
        await update.message.reply_text("Используйте кнопки для управления.")
        return VIEWING_HISTORY_ORDERS

    # Если мы дошли сюда, значит текст не подходит ни под одно состояние
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
    # Вызывается при таймауте (30 секунд бездействия)
    if update.effective_message:
        await update.effective_message.reply_text("Время ожидания истекло. Возвращаюсь в главное меню.")
    return await show_main_menu(update, context)

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_MAIN_MENU: [CallbackQueryHandler(button_handler)],
            ADDING_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            ADDING_PRODUCT_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            SELECTING_PRODUCT_FOR_ORDER: [CallbackQueryHandler(button_handler), MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            ENTERING_CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            ENTERING_ORDER_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            CONFIRM_ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            ENTERING_SEARCH_ORDER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            ADDING_USER_TELEGRAM_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            ADDING_USER_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            SELECTING_REPORT_TYPE: [CallbackQueryHandler(button_handler)],
            SELECTING_USER_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)],
            VIEWING_HISTORY_ORDERS: [CallbackQueryHandler(button_handler)],
        },
        fallbacks=[CommandHandler("start", start)],
        conversation_timeout=30,
        # При таймауте вызывается fallback TIMEOUT
        name="my_conversation"
    )
    # В PTB 20 при таймауте ConversationHandler вызывает TIMEOUT fallback, нужно прописать его
    # Но PTB 20 требует отдельный способ. Если нет прямой поддержки, можно ловить с помощью error_handler
    # или использовать run_async. Для простоты используем fallback на start.
    # Альтернативно, можно в ветке PTB ловить таймаут через on_timeout, но это требует PTB 20.3+.
    # Предположим, что fallback CommandHandler("start", start) сработает после TIMEOUT.
    # Если это не сработает, можно добавить TIMEOUT: [MessageHandler(filters.ALL, timeout_handler)] в fallbacks.
    #
    # В PTB 20:
    # TIMEOUT fallback можно добавить как:
    # fallbacks=[CommandHandler("start", start)],
    # и: 
    # conversation_timeout=30
    # Согласно документации, когда время истечет, state = TIMEOUT. Можно добавить:
    # TIMEOUT: [MessageHandler(filters.ALL, timeout_handler)]
    #
    # Добавим TIMEOUT вручную:
    conv_handler.TIMEOUT = [MessageHandler(filters.ALL, timeout_handler)]

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
