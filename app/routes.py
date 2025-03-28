import shutil
import os
from typing import List
import ccxt
from fastapi import HTTPException
from fastapi import APIRouter, Request, Form, Depends, HTTPException, status, Response
from tortoise.transactions import in_transaction
from passlib.hash import bcrypt
from app.models import User, ApiKey, Bot, OTPCode, BotInfo
from app.models import Payment as PaymentModel
import random
import string
import aiohttp
from fastapi.responses import FileResponse, JSONResponse
from app.security import create_access_token, verify_access_token
from datetime import datetime, timedelta, timezone
import secrets
from app.security import *
from tortoise.exceptions import IntegrityError, DoesNotExist
from app.celery_worker import create_freqtrade_container, add_strategy_to_container, start_user_strategy
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
import logging
import base64
import os
import uuid
from yookassa import Configuration
from yookassa import Payment as yookassa_payment
from pydantic import BaseModel
import ipaddress

logging.basicConfig(level=logging.DEBUG)


load_dotenv()
auth_routes = APIRouter()



# ------ Utility Functions ------


def create_refresh_token():
    return secrets.token_hex(32)



def generate_csrf_token():
    return secrets.token_hex(32)



def create_user_directory(user_id):
    user_directory = f"./user_data/user_{user_id}"
    example_directory = "./user_data/init"
    
    if not os.path.exists(user_directory):
        os.makedirs(user_directory)
        shutil.copytree(example_directory, user_directory, dirs_exist_ok=True)
    
    return user_directory



def create_user_compose_yml(user_id):
    user_directory = f"./user_data/user_{user_id}"
    docker_compose_path = os.path.join(user_directory, "docker-compose.yml")
    
    # Создаем docker-compose.yml
    docker_compose_content = f"""
version: '3.8'
services:
  placeholder:
    image: scratch
    container_name: user_{user_id}_placeholder
    """
    
    # Записываем содержимое в файл
    with open(docker_compose_path, "w") as f:
        f.write(docker_compose_content)



async def validate_api_key(exchange_name: str, api_key: str, secret_key: str):
    # Создаем объект биржи с переданными API ключами
    exchange_class = getattr(ccxt, exchange_name.lower())
    exchange = exchange_class({
        'apiKey': api_key,
        'secret': secret_key,
        'enableRateLimit': True,
    })
    # Используем fetch_balance для проверки подключения
    balance = exchange.fetch_balance()
    usdt_balance = balance["total"].get("USDT", 0)
    return usdt_balance


def generate_one_time_password(length=6):
    """Генерирует одноразовый пароль из случайных цифр."""
    return ''.join(random.choices(string.digits, k=length))



# Логика защищенных путей.
# Проверка авторизации пользователя, обновление токенов доступа.
async def get_current_user(request: Request, response: Response):

    access_token = request.cookies.get("access_token")

    # Проверяем access_token
    if not access_token:
        raise HTTPException(status_code=403, detail="Access отсутствует в куках.")

    user_data = verify_access_token(access_token)

    # Пользователь найден по access_token, возвращаем его.
    if user_data:
        user = await User.filter(email=user_data["sub"]).first()
        if not user:
            raise HTTPException(status_code=403, detail="Пользователь не найден по email из jwt payload.")
        return user

    # Если access_token истёк — проверяем refresh_token.
    refresh_token_value = request.cookies.get("refresh_token")

    if not refresh_token_value:
        raise HTTPException(status_code=403, detail="Refresh-токен отсутствует в куках.")

    # Ищем пользователя по refresh токену.
    user = await User.filter(refresh_token=refresh_token_value).first()

    if not user:
        raise HTTPException(status_code=403, detail="Пользователь не найден по Refresh-токен.")

    # Проверяем, истёк ли refresh-токен
    if user.refresh_token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="Refresh-токен истёк.")

    # Обновляем access_token.
    new_access_token = create_access_token({"sub": user.email})

    # Обновляем refresh токен.
    new_refresh_token = create_refresh_token()
    user.refresh_token = new_refresh_token
    user.refresh_token_expires_at = datetime.utcnow() + timedelta(days=int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS')))
    await user.save()

    # Устанавливаем новые токены.
    response.set_cookie(key="access_token", value=new_access_token, httponly=True, secure=False, samesite='Lax')
    response.set_cookie(key="refresh_token", value=new_refresh_token, httponly=True, secure=False, samesite='Lax')
    return user 




# ------ Routes ------

SPA_ROUTES = [
    "/",
    "/login",
    "/register",
    "/account"
]

# Отдаём index.html для клиентских маршрутов (SPA).
for route in SPA_ROUTES:
    @auth_routes.get(route)
    async def serve_react_app():
        return FileResponse("dist/index.html")





# ------ Api ------

# Api (не защищенный путь).
# Отравка сообщения для проверки почты.
@auth_routes.post("/send-message")
async def send_message(request: Request, email: str = Form(...), csrf_token: str = Form(...)):
   
    cookies_csrf_token = request.cookies.get("csrf_token")
    # Проверяем наличие токена и совпадение
    if not cookies_csrf_token or cookies_csrf_token != csrf_token:
        raise HTTPException(status_code=403, detail="CSRF-токен недействителен или отсутствует.")

    # Генерируем одноразовый пароль.
    await OTPCode.filter(email=email).delete()
    otp_entry = await OTPCode.create(email=email, otp=generate_one_time_password(), expires_at=datetime.utcnow() + timedelta(minutes=1))

    # Формируем HTML-письмо
    email_body = f"""
    <html>
    <body>
        <h1>Одноразовый пароль</h1>
        <p>Ваш код для входа: <strong>{otp_entry.otp}</strong></p>
    </body>
    </html>
    """

    # Подготавливаем данные для отправки запроса
    email_data = {
        "from": "info@eazy-trade.ru",
        "subject": "Вход Eazy Trade",
        "to": email,
        "html": email_body,
    }

    headers = {
        "Authorization": os.getenv('SMTP_KEY')
    }

    # Отправляем запрос в SMTP API
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.smtp.bz/v1/smtp/send", json=email_data, headers=headers) as response:
            if response.status != 200:
                logging.error(f"Ошибка отправки письма: {await response.text()}")
                raise HTTPException(status_code=500, detail="Ошибка при отправке письма")

    return JSONResponse({"message": "Одноразовый пароль отправлен на email"}, status_code=200)





# Api (не защищенный путь).
# Проверка OTP и авторизация/регистрация пользователя.
@auth_routes.post("/check-otp")
async def check_otp(request: Request, email: str = Form(...), otp: str = Form(...), csrf_token: str = Form(...)):

    cookies_csrf_token = request.cookies.get("csrf_token")

    # Проверяем валидность CSRF-токена
    if not cookies_csrf_token or cookies_csrf_token != csrf_token:
        raise HTTPException(status_code=403, detail="CSRF-токен недействителен или отсутствует.")

    if (len(otp) != 6):
        raise HTTPException(status_code=400, detail="Неверный одноразовый пароль.")

    # Проверяем наличие OTP-кода в БД
    otp_entry = await OTPCode.filter(email=email, otp=otp).first()

    if not otp_entry:
        raise HTTPException(status_code=400, detail="Неверный одноразовый пароль.")

    # Проверяем срок действия OTP
    if otp_entry.expires_at < datetime.now(timezone.utc):
        await otp_entry.delete()
        raise HTTPException(status_code=400, detail="Одноразовый пароль истёк.")
    
    await otp_entry.delete()

    user = await User.filter(email=email).first()

    access_token = create_access_token(data={"sub": email})
    refresh_token = create_refresh_token()
    refresh_token_expires_at = datetime.utcnow() + timedelta(days=int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS')))

    if not user:
        user = await User.create(email=email,
                                refresh_token=refresh_token,
                                refresh_token_expires_at=refresh_token_expires_at,
                                is_trial = True,
                                subscription_expires_at = datetime.utcnow() + timedelta(days=2))
    else:
        user.refresh_token = refresh_token
        user.refresh_token_expires_at = refresh_token_expires_at
        await user.save()
    
    response = JSONResponse({"message": "Вход успешно сделан"}, status_code=200)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite='Lax')
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite='Lax')
    
    return response





# Api (не защищенный путь).
# Отравка csrf токена.
@auth_routes.get("/api/csrf-token")
async def get_csrf_token(request: Request):
    csrf_token = generate_csrf_token()
    response = JSONResponse({"message": "CSRF токен создан"}, status_code=200)
    response.set_cookie(key="csrf_token",
                        value=csrf_token,
                        httponly=False, # False, чтобы в js коде можно было достать.
                        secure=False, # При деплое поменят на True.
                        )
    return response





# Api (Защищенный путь).
# Проверка авторизации пользователя при попытке войти в ЛК.
@auth_routes.get("/api/account")
async def get_account(request: Request, response: Response, current_user: User = Depends(get_current_user)):

    user_id = current_user.id
    existing_bots = await current_user.fetch_related("bots")
    
    if not existing_bots:
        user_directory = create_user_directory(user_id)
        create_yml = create_user_compose_yml(user_id)
        create_freqtrade_container.delay(user_id)
    
    # Добавляем JSON-контент в response, НЕ создавая новый объект.
    # Это нужно, чтобы обновлять токены в куках (если это требуется).
    # В защищенных путях надо всегда отправлять ответ в таком виде.
    response_data = {"message": "Доступ разрешён", "user": current_user.email}
    return JSONResponse(content=response_data, headers=response.headers, status_code=200)





# Api (Защищенный путь).
# Получение email пользователя.
@auth_routes.get("/api/get-email")
async def get_account(request: Request, response: Response, current_user: User = Depends(get_current_user)):
    response_data = {"email": current_user.email}
    return JSONResponse(content=response_data, headers=response.headers, status_code=200)





# Api (Защищенный путь).
# Получение данных о подписке пользователя.
@auth_routes.get("/api/get-subscription")
async def get_account(request: Request, response: Response, current_user: User = Depends(get_current_user)):
    response_data = {"subscription_expires_at": current_user.subscription_expires_at.strftime("%H:%M %d.%m.%Y"),
                     "is_trial": current_user.is_trial}
    return JSONResponse(content=response_data, headers=response.headers, status_code=200)



class Amount(BaseModel):
    value: str
    currency: str

class Payment(BaseModel):
    id: str
    status: str
    amount: Amount
    created_at: str
    paid: bool
    
class YooKassaNotification(BaseModel):
    type: str
    event: str
    object: Payment


# Допустимые отдельные IP-адреса
ALLOWED_IPS = [
    "77.75.156.11",
    "77.75.156.35"
]

# Допустимые подсети
ALLOWED_NETWORKS = [
    ipaddress.ip_network("185.71.76.0/27"),
    ipaddress.ip_network("185.71.77.0/27"),
    ipaddress.ip_network("77.75.153.0/25"),
    ipaddress.ip_network("77.75.154.128/25"),
    ipaddress.ip_network("2a02:5180::/32"),
]

def is_ip_allowed(ip: str) -> bool:
    try:
        ip_addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    # Проверка по отдельным IP
    if ip in ALLOWED_IPS:
        return True
    # Проверка по подсетям
    for net in ALLOWED_NETWORKS:
        if ip_addr in net:
            return True
    return False


@auth_routes.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):

    # client_ip = request.client.host
    # if not is_ip_allowed(client_ip):
    #     raise HTTPException(status_code=403, detail="IP not allowed")
    
    try:
        data = await request.json()
        notification = YooKassaNotification.parse_obj(data)
        
        logging.error(f"Type: {notification.type}")
        logging.error(f"Event: {notification.event}")
        logging.error(f"Payment ID: {notification.object.id}")

        if (notification.event == "payment.succeeded"):
            payment_model = await PaymentModel.filter(yookassa_id=notification.object.id).first()
            if (payment_model.paid == False):
                payment_model.paid = True
                await payment_model.save()

                await payment_model.fetch_related("user")
                user = payment_model.user
                user.subscription_expires_at = datetime.utcnow() + timedelta(days=30)
                if (user.is_trial):
                    user.is_trial = False
                await user.save()

    except Exception as e:
        logging.error("YooKassa webhook exception: " + str(e))
        
    return {"status": "ok"}



# Api (Защищенный путь).
# Получение данных о подписке пользователя.
@auth_routes.get("/api/get-pay-link")
async def get_account(request: Request, response: Response, current_user: User = Depends(get_current_user)):

    if (current_user.subscription_expires_at > datetime.now(timezone.utc)):
        if (current_user.is_trial == False):
            raise HTTPException(status_code=400, headers=response.headers, detail="Ваша подписка ещё действительна")
        
    Configuration.account_id = os.getenv('YOOKASSA_SHOP_ID')
    Configuration.secret_key = os.getenv('YOOKASSA_SECRET_KEY')

    try:
        idempotence_key  = str(uuid.uuid4())
        payment = yookassa_payment.create({
                    "amount": {
                        "value": "100.00",
                        "currency": "RUB"
                    },
                    "confirmation": {
                        "type": "redirect",
                        "return_url": "https://eazy-trade.ru/account",
                    },
                    "capture": True,
                    "description": "Заказ №1"
                }, idempotence_key )
        
        await PaymentModel.create(user=current_user, yookassa_id=payment.id, paid=False)

        response_data = {"confirmation_url": payment.confirmation.confirmation_url}
        return JSONResponse(content=response_data, headers=response.headers, status_code=200)
    except Exception as e:
        logging.error("get-pay-link error" + str(e))
        raise HTTPException(status_code=500, headers=response.headers, detail="Ошибка при формировании payment")
   








# Api (Защищенный путь).
# Получение всех статегий из каталога.
@auth_routes.get("/api/get-strategies")
async def get_strategies(request: Request, response: Response, current_user: User = Depends(get_current_user)):
    
    all_bots = await BotInfo.all()

    # Формируем список словарей с данными о ботах
    bots_list = [
        {
            "id": bot.id,
            "name": bot.name,
            "type": bot.type,
            "pnl": bot.pnl,
            "crypto_pairs": bot.crypto_pairs,
            "description": bot.description,
        }
        for bot in all_bots
    ]    

    response_data = {"bots": bots_list}
    return JSONResponse(content=response_data, headers=response.headers, status_code=200)





# Api (Защищенный путь).
# Получение API ключей пользователя.
@auth_routes.get("/api/user-api-keys")
async def get_api_keys(request: Request, response: Response, user: User = Depends(get_current_user)):

    user_api_keys = await ApiKey.filter(user=user)

    api_keys_list = [
        {
            "id": api_key.id,
            "name": api_key.name,
            "exchange": api_key.exchange,
            "api_key": api_key.api_key,
        }
        for api_key in user_api_keys
    ]    

    response_data = {"api_keys": api_keys_list}
    return JSONResponse(content=response_data, headers=response.headers, status_code=200)





# Api (Защищенный путь).
# Добавление API ключа к пользователю.
@auth_routes.post("/api/add-api-key")
async def create_api_key(request: Request, response: Response, name: str = Form(...), exchange_name: str = Form(...), api_key: str = Form(...), secret_key: str = Form(...), user: User = Depends(get_current_user)):
        
    try:
        await validate_api_key(exchange_name, api_key, secret_key)
    except ccxt.AuthenticationError:
        raise HTTPException(status_code=400, headers=response.headers, detail="Невалидные токены API")
    except Exception as e:
        raise HTTPException(status_code=500, headers=response.headers, detail="Ошибка при проверке токенов")

    # Если токены валидны, шифруем и сохраняем в базу данных
    encrypted_api_key = encrypt_data(api_key)
    encrypted_secret_key = encrypt_data(secret_key)

    await ApiKey.create(
        name=name,
        user=user,
        exchange=exchange_name,
        api_key=encrypted_api_key,
        secret_key=encrypted_secret_key,
    )
    response_data = {"message": "Ключ добавлен"}
    return JSONResponse(content=response_data, headers=response.headers, status_code=200)





# Api (Защищенный путь).
# Удаление API ключа у пользователя.
@auth_routes.delete("/api/delete-api-key/{api_key_id}")
async def delete_api_key(request: Request, response: Response, api_key_id: int, user: User = Depends(get_current_user)):
    
    # Проверяем, существует ли ключ и принадлежит ли он текущему пользователю
    api_key = await ApiKey.filter(id=api_key_id, user=user).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API ключ не найден или вы не являетесь владельцем")

    # Удаляем ключ из базы данных
    await api_key.delete()

    response_data = {"message": "API ключ успешно удалён"}
    return JSONResponse(content=response_data, headers=response.headers, status_code=200)





# Api (Защищенный путь).
# Получение баланса по API ключу.
@auth_routes.get("/api/get-api-key-balance/{api_key_id}")
async def get_balance(request: Request, response: Response, api_key_id: int, user: User = Depends(get_current_user)):

    # Проверяем, существует ли ключ и принадлежит ли он текущему пользователю
    api_key = await ApiKey.filter(id=api_key_id, user=user).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API ключ не найден или вы не являетесь владельцем")

    try:
        usdt_balance = await validate_api_key(api_key.exchange, decrypt_data(api_key.api_key), decrypt_data(api_key.secret_key))
        response_data = {"message": "Баланс успешно выявлен", "balance": usdt_balance}
        return JSONResponse(content=response_data, headers=response.headers, status_code=200)
    except ccxt.AuthenticationError:
        raise HTTPException(status_code=400, headers=response.headers, detail="Невалидные токены API")
    except Exception as e:
        raise HTTPException(status_code=500, headers=response.headers, detail="Ошибка при проверке токенов")





# Api (Защищенный путь).
# Добавление стратегии к пользователю.
@auth_routes.post("/api/add-strategy")
async def add_strategy(request: Request, response: Response, strategy_name: str = Form(...), deposit: str = Form(...), api_key_name: str = Form(...), is_dry_run: bool = Form(...),  user: User = Depends(get_current_user)):
    # api_key_FK = await ApiKey.filter(name=api_key_name, user = user).first()
    result = add_strategy_to_container.delay(user.id, strategy_name, deposit, api_key_name, is_dry_run)
    response_data = {"message": "Бот успешно добавлен"}
    return JSONResponse(content=response_data, headers=response.headers, status_code=200)




# Api (Защищенный путь).
# Получение добавленных стратегий пользователя.
@auth_routes.get("/api/user-strategies")
async def get_user_strategies(request: Request, response: Response, user: User = Depends(get_current_user)):
        
    # Получаем список ботов текущего пользователя
    bots = await Bot.filter(user=user).prefetch_related("api_key")
    # Формируем список словарей с данными о ботах
    bots_list = [
        {
            "id": bot.id,
            "name": bot.name,
            "status": bot.status,
            "available_capital": bot.available_capital,
            "is_dry_run": bot.is_dry_run,
            "api_key_name": bot.api_key.name,
        }
        for bot in bots
    ]

    response_data = {"bots": bots_list}
    return JSONResponse(content=response_data, headers=response.headers, status_code=200)





# Api (Защищенный путь).
# Запуск бота.
@auth_routes.post("/api/start-bot")
async def start_bot(request: Request, response: Response, bot_name: str = Form(...), strategy_name: str = Form(...), user: User = Depends(get_current_user)):
    task = start_user_strategy.delay(user.id, bot_name, strategy_name)
    return {"message": f"Task to start bot {bot_name} with strategy {strategy_name} created.", "task_id": task.id}
