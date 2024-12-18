import os
import subprocess
import time
import requests

BOT_TOKEN = "7824760453:AAGuV6vdRhNhvot3xIIgPK0WsnEE8KX5tHI"  # Замените на ваш токен
CHAT_ID = "1867417929"  # Замените на ID чата, куда можно отправить сообщение

BOT_PATH = "/var/www/telegram_bot_shop_helper/bot.py"  # Путь к вашему боту
CHECK_INTERVAL = 60  # Интервал проверки (в секундах)

def is_bot_alive():
    """Проверка ответа от бота."""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        params = {"chat_id": CHAT_ID, "text": "/ping"}
        response = requests.get(url, params=params, timeout=10)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def restart_bot():
    """Перезапуск бота."""
    print("Бот завис. Перезапускаю...")
    # Убиваем текущий процесс бота
    os.system("pkill -f bot.py")
    time.sleep(2)
    # Запускаем бот заново
    subprocess.Popen(["python3", BOT_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Бот успешно перезапущен.")

if __name__ == "__main__":
    while True:
        if not is_bot_alive():
            restart_bot()
        else:
            print("Бот работает нормально.")
        time.sleep(CHECK_INTERVAL)
