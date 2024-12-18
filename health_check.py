import os
import subprocess
import time
import requests
from datetime import datetime

BOT_TOKEN = "7824760453:AAGuV6vdRhNhvot3xIIgPK0WsnEE8KX5tHI"  # Замените на ваш токен
CHAT_ID = "1867417929"  # Замените на ID чата, куда можно отправить сообщение

BOT_PATH = "/var/www/telegram_bot_shop_helper/bot.py"  # Путь к вашему боту
CHECK_INTERVAL = 60  # Интервал проверки (в секундах)
LOG_FILE = "/var/www/telegram_bot_shop_helper/logs/health_check.log"  # Путь к логам

def write_log(message):
    """Запись сообщения в лог-файл."""
    with open(LOG_FILE, "a") as log_file:
        log_file.write(f"{datetime.now()} - {message}\n")

def is_bot_alive():
    """Проверка ответа от бота."""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        params = {"chat_id": CHAT_ID, "text": "/ping"}
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return True
        else:
            write_log(f"Ответ от сервера не 200: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        write_log(f"Ошибка при запросе: {e}")
        return False

def restart_bot():
    """Перезапуск бота."""
    write_log("Бот завис. Перезапускаю...")
    # Убиваем текущий процесс бота безопасно
    os.system("pkill -f bot.py")
    time.sleep(2)
    # Запускаем бот заново и логируем его перезапуск
    subprocess.Popen(["python3", BOT_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    write_log("Бот успешно перезапущен.")

if __name__ == "__main__":
    write_log("Запуск health_check.py для мониторинга бота.")
    while True:
        if not is_bot_alive():
            restart_bot()
        else:
            write_log("Бот работает нормально.")
        time.sleep(CHECK_INTERVAL)