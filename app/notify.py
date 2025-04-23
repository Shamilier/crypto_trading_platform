# notify.py
import requests
import sys

BOT_TOKEN = 'NOTIFY_TKN'
CHAT_ID = '1297355532'  # получен от @userinfobot
MESSAGE = sys.argv[1] if len(sys.argv) > 1 else "Сервер перезагрузился"

def send_telegram_message():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": MESSAGE
    }
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
    except Exception as e:
        print(f"Ошибка отправки: {e}")

if __name__ == "__main__":
    send_telegram_message()