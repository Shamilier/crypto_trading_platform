import subprocess
import time
import requests
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv('NOTIFY_TKN')
CHAT_ID = os.getenv('DI_TAHC')
CONTAINER_NAME = 'crypto_trading_app'

def send_alert(msg):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    requests.post(url, data={'chat_id': CHAT_ID, 'text': msg})

def is_container_running():
    result = subprocess.run(
        ['docker', 'inspect', '-f', '{{.State.Running}}', CONTAINER_NAME],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return result.stdout.strip() == 'true'

def main():
    msg = f"Проверка идет"
    send_alert(msg)
    was_running = True
    while True:
        if not is_container_running() and was_running:
            msg = f"⚠ Контейнер {CONTAINER_NAME} остановлен!"
            send_alert(msg)
            was_running = False
        elif is_container_running():
            was_running = True
        time.sleep(30)  # Проверять каждые 30 секунд

if __name__ == '__main__':
    main()