from fpdf import FPDF

pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", size=12)
pdf.cell(200, 10, txt="Тестовый PDF", ln=True, align="C")

pdf.output("/var/www/telegram_bot_shop_helper/logs/test.pdf")
print("PDF успешно создан!")
