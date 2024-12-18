from fpdf import FPDF

def generate_pdf(filename, client_name, product_name, quantity, prepayment):
    """Генерация PDF-файла с поддержкой UTF-8."""
    pdf = FPDF()
    pdf.add_page()

    # Добавляем шрифт с поддержкой кириллицы
    pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', uni=True)
    pdf.set_font('DejaVu', size=12)

    # Добавляем текст
    pdf.cell(200, 10, txt="Подтверждение заказа", ln=True, align='C')
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Клиент: {client_name}", ln=True)
    pdf.cell(200, 10, txt=f"Товар: {product_name}", ln=True)
    pdf.cell(200, 10, txt=f"Количество: {quantity}", ln=True)
    pdf.cell(200, 10, txt=f"Предоплата: {prepayment}", ln=True)

    # Сохранение PDF
    pdf.output(filename)
    print(f"PDF-файл сохранён: {filename}")

# Тестовая генерация PDF
generate_pdf('/var/www/telegram_bot_shop_helper/logs/test.pdf',
             "Малика", "Miele Blizzard CX1 Cat&Dog Powerline", 1, "39000.0")
