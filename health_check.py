import os
import subprocess
import time
import requests
from datetime import datetime

# Конфигурация
BOT_TOKEN = "7824760453:AAGuV6vdRhNhvot3xIIgPK0WsnEE8KX5tHI"  # Токен бота
BOT_PATH = "/var/www/telegram_bot_shop_helper/bot.py"  # Путь к файлу бота
CHECK_INTERVAL = 60  # Интервал проверки (в секундах)

# Пути к логам
HEALTH_LOG = "/var/www/telegram_bot_shop_helper/logs/health_check.log"
BOT_LOG = "/var/www/telegram_bot_shop_helper/logs/bot.log"

def write_log(log_file, message):
    """Функция записи логов."""
    with open(log_file, "a") as f:
        f.write(f"{datetime.now()} - {message}\n")

def is_bot_alive():
    """Проверка доступности бота через API Telegram."""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return True
        else:
            write_log(HEALTH_LOG, f"Бот не отвечает. Код состояния: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        write_log(HEALTH_LOG, f"Ошибка при проверке бота: {e}")
        return False

def restart_bot():
    """Перезапуск бота."""
    write_log(HEALTH_LOG, "Перезапуск бота...")
    os.system("pkill -f bot.py")  # Останавливаем процесс бота
    time.sleep(2)  # Ждем перед перезапуском

    try:
        with open(BOT_LOG, "a") as log_file:
            subprocess.Popen(
                ["python3", BOT_PATH],
                stdout=log_file,
                stderr=log_file
            )
        write_log(HEALTH_LOG, "Бот успешно перезапущен.")
    except Exception as e:
        write_log(HEALTH_LOG, f"Ошибка при перезапуске бота: {e}")

if __name__ == "__main__":
    write_log(HEALTH_LOG, "Запуск health_check.py для мониторинга бота.")
    while True:
        if not is_bot_alive():
            restart_bot()
        else:
            write_log(HEALTH_LOG, "Бот работает нормально.")
        time.sleep(CHECK_INTERVAL)
