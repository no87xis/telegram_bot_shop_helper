import os
import subprocess
import time
import requests
from datetime import datetime

# Конфигурация
BOT_TOKEN = "7824760453:AAGuV6vdRhNhvot3xIIgPK0WsnEE8KX5tHI"  # Токен бота
BOT_PATH = "/var/www/telegram_bot_shop_helper/bot.py"  # Путь к файлу бота
CHECK_INTERVAL = 60  # Интервал проверки (в секундах)
MAX_RESTARTS = 5  # Лимит перезапусков

# Пути к логам
HEALTH_LOG = "/var/www/telegram_bot_shop_helper/logs/health_check.log"
BOT_LOG = "/var/www/telegram_bot_shop_helper/logs/bot.log"

restart_attempts = 0  # Счётчик перезапусков

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
            write_log(HEALTH_LOG, "Проверка бота: бот отвечает корректно.")
            return True
        else:
            write_log(HEALTH_LOG, f"Проверка бота: бот не отвечает, код состояния: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        write_log(HEALTH_LOG, f"Проверка бота: ошибка запроса - {e}")
        return False

def restart_bot():
    """Перезапуск бота с логированием."""
    global restart_attempts
    write_log(HEALTH_LOG, f"Бот завис. Перезапуск попытка {restart_attempts + 1}/{MAX_RESTARTS}.")

    # Завершаем старый процесс
    os.system("pkill -f bot.py")
    time.sleep(2)  # Даем время процессу завершиться

    # Проверяем, что процесс действительно завершён
    if "bot.py" not in os.popen("ps aux").read():
        write_log(HEALTH_LOG, "Старый процесс бота завершён успешно.")
    else:
        write_log(HEALTH_LOG, "Не удалось завершить старый процесс бота.")
        return  # Если процесс не завершился, выходим

    # Запускаем бот заново
    try:
        with open(BOT_LOG, "a") as log_file:
            subprocess.Popen(
                ["python3", BOT_PATH],
                stdout=log_file,
                stderr=log_file,
                preexec_fn=os.setsid
            )
        write_log(HEALTH_LOG, "Бот успешно перезапущен.")
    except Exception as e:
        write_log(HEALTH_LOG, f"Ошибка при перезапуске бота: {e}")

if __name__ == "__main__":
    write_log(HEALTH_LOG, "Запуск health_check.py для мониторинга бота.")
    while restart_attempts < MAX_RESTARTS:
        if not is_bot_alive():
            restart_attempts += 1
            restart_bot()
        else:
            restart_attempts = 0  # Сброс счётчика при успешной работе
            write_log(HEALTH_LOG, "Бот работает нормально.")
        time.sleep(CHECK_INTERVAL)

    write_log(HEALTH_LOG, "Достигнут лимит попыток перезапуска. Завершаю работу мониторинга.")
