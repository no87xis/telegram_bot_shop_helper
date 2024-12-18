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
        data = response.json()  # Конвертируем ответ в JSON
        if response.status_code == 200 and data.get("ok"):
            write_log(HEALTH_LOG, "API Telegram: Бот работает нормально.")
            return True
        else:
            write_log(HEALTH_LOG, f"API Telegram: Бот не отвечает. Статус: {response.status_code}, Ответ: {data}")
            return False
    except requests.exceptions.RequestException as e:
        write_log(HEALTH_LOG, f"Ошибка при запросе к API Telegram: {e}")
        return False


def restart_bot():
    """Перезапуск бота с логированием."""
    write_log(HEALTH_LOG, "Бот завис. Перезапускаю...")
    
    # Завершаем процесс бота
    os.system("pkill -f bot.py")
    time.sleep(2)
    
    # Проверка, что процесс завершён
    if "bot.py" in os.popen("ps aux").read():
        write_log(HEALTH_LOG, "Не удалось завершить старый процесс бота.")
        return
    write_log(HEALTH_LOG, "Старый процесс бота завершён успешно.")

    # Запускаем новый процесс
    try:
        with open(BOT_LOG, "a") as log_file:
            subprocess.Popen(["python3", BOT_PATH], stdout=log_file, stderr=log_file, preexec_fn=os.setsid)
        time.sleep(5)  # Ждём несколько секунд перед проверкой
        if "bot.py" in os.popen("ps aux").read():
            write_log(HEALTH_LOG, "Бот успешно перезапущен и работает.")
        else:
            write_log(HEALTH_LOG, "Ошибка: Бот не запустился.")
    except Exception as e:
        write_log(HEALTH_LOG, f"Ошибка при запуске бота: {e}")


if __name__ == "__main__":
    write_log(HEALTH_LOG, "Запуск health_check.py для мониторинга бота.")
    while True:
        if not is_bot_alive():
            restart_bot()
        else:
            write_log(HEALTH_LOG, "Бот работает нормально.")
        time.sleep(CHECK_INTERVAL)
