import shutil
import os
from typing import List
import ccxt
from fastapi import HTTPException
from fastapi import APIRouter, Request, Form, Depends, HTTPException, status, Response
from tortoise.transactions import in_transaction
from passlib.hash import bcrypt
from app.models import User, RefreshToken, ApiKey, ApiKeyIn_Pydantic, ApiKey_Pydantic, Containers, Bot_Pydantic, Bot, OTPCode
import random
import string
import aiohttp
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from app.security import create_access_token, verify_access_token
from datetime import datetime, timedelta, timezone
import secrets
from app.security import *
from tortoise.exceptions import IntegrityError, DoesNotExist
from app.celery_worker import create_freqtrade_container, add_strategy_to_container, start_user_strategy, stop_user_bot
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
import logging

logging.basicConfig(level=logging.DEBUG)



REFRESH_TOKEN_EXPIRE_DAYS = 1

auth_routes = APIRouter()
templates = Jinja2Templates(directory="templates")


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
    try:
        # Создаем объект биржи с переданными API ключами
        exchange_class = getattr(ccxt, exchange_name.lower())
        logging.debug(f" Привет1 ")
        exchange = exchange_class({
            'apiKey': api_key,
            'secret': secret_key,
            'enableRateLimit': True,
        })
        logging.debug(f" Привет2 ")
        # Используем fetch_balance для проверки подключения
        balance = exchange.fetch_balance()
        logging.debug(f" Привет3 ")
        usdt_balance = balance["total"].get("USDT", 0)
        logging.debug(f" Приве43 ")
        return usdt_balance

    except ccxt.AuthenticationError:
        raise HTTPException(status_code=400, detail="Невалидные токены API")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Ошибка при проверке токенов")


# 
def generate_one_time_password(length=6):
    """Генерирует одноразовый пароль из случайных цифр."""
    return ''.join(random.choices(string.digits, k=length))


# ------ Routes ------

# SPA_ROUTES = [
#     "/",
#     "/login",
#     "/register",
#     "/account"
# ]

# # Отдаём index.html для клиентских маршрутов (SPA).
# for route in SPA_ROUTES:
#     @auth_routes.get(route)
#     async def serve_react_app():
#         return FileResponse("dist/index.html")


# Register User
@auth_routes.post("/register")
async def post_register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), csrf_token: str = Form(...)):

    # Получаем CSRF-токен из сессии
    cookies_csrf_token = request.cookies.get("csrf_token")
    logging.debug(f"/register: Токен из cookies: {cookies_csrf_token}")
    logging.debug(f"/register: Токен из body: {csrf_token}")

    # Проверяем наличие токена и совпадение
    if not cookies_csrf_token or cookies_csrf_token != csrf_token:
        raise HTTPException(status_code=403, detail="CSRF-токен недействителен или отсутствует.")
    
    existing_email = await User.filter(email=email).first()
    
    if existing_email:
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует.")
    
    hashed_password = bcrypt.hash(password)
    try:
        user = await User.create(username=username, email=email, hashed_password=hashed_password)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Ошибка сохранения данных.")

    return JSONResponse(
            content={"message": "Пользователь успешно создан.", "user_id": user.email},
            status_code=200)

# Login User
@auth_routes.post("/login")
async def post_login(request: Request, email: str = Form(...), password: str = Form(...), csrf_token: str = Form(...)):

    # Получаем CSRF-токен из сессии
    cookies_csrf_token = request.cookies.get("csrf_token")
    logging.debug(f"/register: Токен из cookies: {cookies_csrf_token}")
    logging.debug(f"/register: Токен из body: {csrf_token}")

    # Проверяем наличие токена и совпадение
    if not cookies_csrf_token or cookies_csrf_token != csrf_token:
        raise HTTPException(status_code=403, detail="CSRF-токен недействителен или отсутствует.")
    
    try:
        user = await User.get(email=email)
    except DoesNotExist:
        raise HTTPException(status_code=403, detail="Пользователь не найден")

    if user and bcrypt.verify(password, user.hashed_password):
        access_token = create_access_token(data={"sub": email})
        refresh_token = await RefreshToken.filter(user=user).first()

        if refresh_token:
            refresh_token_value = refresh_token.token
            refresh_token.expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            await refresh_token.save()
        else:
            refresh_token_value = create_refresh_token()
            expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            await RefreshToken.create(token=refresh_token_value, user=user, expires_at=expires_at)
        
        response = JSONResponse({"message": "Вход успешно сделан"}, status_code=200)
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite='Lax')
        response.set_cookie(key="refresh_token", value=refresh_token_value, httponly=True, secure=False, samesite='Lax')
        
        return response
    else:
        raise HTTPException(status_code=401, detail="Неправильная почта или пароль")
    



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
        "Authorization": "OLRNu6KEGczDxm2FoE8KD6WRxSqATzlxb4av"
    }

    # Отправляем запрос в SMTP API
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.smtp.bz/v1/smtp/send", json=email_data, headers=headers) as response:
            if response.status != 200:
                logging.error(f"Ошибка отправки письма: {await response.text()}")
                raise HTTPException(status_code=500, detail="Ошибка при отправке письма")

    return JSONResponse({"message": "Одноразовый пароль отправлен на email"}, status_code=200)


@auth_routes.post("/check-otp")
async def check_otp(request: Request, email: str = Form(...), otp: str = Form(...), csrf_token: str = Form(...)):
    """
    Проверяет правильность одноразового пароля (OTP).
    Если код верный и не истёк — он удаляется, а пользователю выдаётся подтверждение.
    """
    # Получаем CSRF-токен из cookies
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

    if not user:
        try:
            user = await User.create(username=email, email=email, hashed_password=123)
        except IntegrityError:
            raise HTTPException(status_code=400, detail="Ошибка сохранения данных.")
    
    access_token = create_access_token(data={"sub": email})
    refresh_token = await RefreshToken.filter(user=user).first()

    if refresh_token:
        refresh_token_value = refresh_token.token
        refresh_token.expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        await refresh_token.save()
    else:
        refresh_token_value = create_refresh_token()
        expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        await RefreshToken.create(token=refresh_token_value, user=user, expires_at=expires_at)
        
    response = JSONResponse({"message": "Вход успешно сделан"}, status_code=200)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite='Lax')
    response.set_cookie(key="refresh_token", value=refresh_token_value, httponly=True, secure=False, samesite='Lax')
    
    return response

        
    # Если OTP валиден — удаляем его из базы (одноразовый пароль должен использоваться только 1 раз)

    return JSONResponse({"message": "OTP-код подтверждён"}, status_code=200)

# Отправка CSRF токена.
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

async def get_current_user(request: Request, response: Response):
    """
    Проверяет авторизацию пользователя и обновляет access_token при необходимости.
    """
    access_token = request.cookies.get("access_token")

    # Проверяем access_token
    if not access_token:
        raise HTTPException(status_code=403, detail="Доступ запрещён. Токен отсутствует.")

    user_data = verify_access_token(access_token)

    # Пользователь найден по access_token, возвращаем его.
    if user_data:
        user = await User.get(email=user_data["sub"])
        if not user:
            raise HTTPException(status_code=403, detail="Пользователь не найден.")
        return user

    # Если access_token истёк — проверяем refresh_token.
    refresh_token_value = request.cookies.get("refresh_token")

    if not refresh_token_value:
        raise HTTPException(status_code=403, detail="Доступ запрещён. Refresh-токен отсутствует.")

    refresh_token = await RefreshToken.filter(token=refresh_token_value).first()

    if not refresh_token:
        raise HTTPException(status_code=403, detail="Неверный refresh-токен.")

    # Проверяем, истёк ли refresh-токен
    if refresh_token.expires_at < datetime.now(timezone.utc):
        await refresh_token.delete()
        raise HTTPException(status_code=403, detail="Refresh-токен истёк.")

    # Получаем пользователя из refresh-токена.
    user = await refresh_token.user

    if not user:
        await refresh_token.delete()
        raise HTTPException(status_code=403, detail="Пользователь не найден.")

    # Обновляем access_token.
    new_access_token = create_access_token({"sub": user.email})

    # Обновляем refresh токен.
    await refresh_token.delete()
    new_refresh_token = create_refresh_token()
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    await RefreshToken.create(token=new_refresh_token, user=user, expires_at=expires_at)
    
    # Устанавливаем новые токены.
    response.set_cookie(key="access_token", value=new_access_token, httponly=True, secure=False, samesite='Lax')
    response.set_cookie(key="refresh_token", value=new_refresh_token, httponly=True, secure=False, samesite='Lax')
    logging.info(new_access_token)
    logging.info(new_refresh_token)
    return user 

@auth_routes.get("/api/account")
async def get_account(request: Request, response: Response, current_user: User = Depends(get_current_user)):

    user_id = current_user.id
    existing_container = await Containers.filter(user_id=user_id, status="running").first()
    
    if not existing_container:
        user_directory = create_user_directory(user_id)
        create_yml = create_user_compose_yml(user_id)
        create_freqtrade_container.delay(user_id)
    
    response_data = {"message": "Доступ разрешён", "user": current_user.email}

    logging.info(response.headers)
    # Добавляем JSON-контент в response, НЕ создавая новый объект
    return JSONResponse(content=response_data, headers=response.headers, status_code=200)



@auth_routes.get("/api/get-email")
async def get_account(request: Request, response: Response, current_user: User = Depends(get_current_user)):
    return JSONResponse({"email": current_user.email})


@auth_routes.get("/api/get-strategies")
async def get_strategies(request: Request, response: Response, current_user: User = Depends(get_current_user)):
    strategies_path = os.path.abspath("./user_data/example/strategies")
    # Получаем список только `.py` файлов
    strategies = [
        os.path.splitext(name)[0]  # Убираем расширение `.py`
        for name in os.listdir(strategies_path)
        if name.endswith(".py")
    ]
    return JSONResponse({"strategies": strategies})


# Получение API ключей пользователя.
@auth_routes.get("/api/api-keys")
async def get_api_keys(user: User = Depends(get_current_user)):
    user_api_keys = ApiKey.filter(user=user)
    return await ApiKey_Pydantic.from_queryset(user_api_keys)



# Добавление API ключа к пользователю.
@auth_routes.post("/api/add-api-key")
async def create_api_key(request: Request, response: Response, name: str = Form(...), exchange_name: str = Form(...), api_key: str = Form(...), secret_key: str = Form(...), user: User = Depends(get_current_user)):
        await validate_api_key(exchange_name, api_key, secret_key)

        # Если токены валидны, шифруем и сохраняем в базу данных
        encrypted_api_key = encrypt_data(api_key)
        encrypted_secret_key = encrypt_data(secret_key)

        new_api_key = await ApiKey.create(
            name=name,
            user=user,
            exchange=exchange_name,
            api_key=encrypted_api_key,
            secret_key=encrypted_secret_key,
        )
        response_data = {"message": "Ключ добавлен"}
        return JSONResponse(content=response_data, headers=response.headers, status_code=200)



# Удаление API ключа у пользователя.
@auth_routes.delete("/api/delete-api-key/{api_key_id}")
async def delete_api_key(request: Request, response: Response, api_key_id: int, user: User = Depends(get_current_user)):
    try:
        # Проверяем, существует ли ключ и принадлежит ли он текущему пользователю
        api_key = await ApiKey.get_or_none(id=api_key_id, user=user)
        if not api_key:
            raise HTTPException(status_code=404, detail="API ключ не найден или вы не являетесь владельцем")

        # Удаляем ключ из базы данных
        await api_key.delete()

        return {"message": "API ключ успешно удалён"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении API ключа: {str(e)}")
    


# Получение баланса по API ключу.
@auth_routes.get("/api/get-api-key-balance/{api_key_id}")
async def get_balance(request: Request, response: Response, api_key_id: int, user: User = Depends(get_current_user)):
    try:
        # Проверяем, существует ли ключ и принадлежит ли он текущему пользователю
        api_key = await ApiKey.get_or_none(id=api_key_id, user=user)
        if not api_key:
            raise HTTPException(status_code=404, detail="API ключ не найден или вы не являетесь владельцем")

        usdt_balance = await validate_api_key(api_key.exchange, decrypt_data(api_key.api_key), decrypt_data(api_key.secret_key))

        response_data = {"message": "Баланс успешно выявлен", "balance": usdt_balance}
        return JSONResponse(content=response_data, headers=response.headers, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении API ключа: {str(e)}")





@auth_routes.post("/api/add_strategy")
async def add_strategy(request: Request, response: Response, strategy_name: str = Form(...), user: User = Depends(get_current_user)):
    # Передаём ID пользователя и название стратегии в Celery задачу
    result = add_strategy_to_container.delay(user.id, strategy_name)
    response_data = {"message": "Бот успешно добавлен"}
    return JSONResponse(content=response_data, headers=response.headers, status_code=200)



@auth_routes.get("/api/user-strategies")
async def get_user_strategies(request: Request, response: Response, user: User = Depends(get_current_user)):
    try:
        # Получаем список ботов текущего пользователя
        strategies = await Bot.filter(user=user)

        # Формируем список словарей с данными о ботах
        bots_list = [
            {
                "id": bot.id,
                "name": bot.name,
                "strategy": bot.strategy,
                "status": bot.status,
                "balance_used": bot.balance_used,
                "indicators": bot.indicators,
                "profit": bot.profit,
                "created_at": bot.created_at.isoformat(),
                "updated_at": bot.updated_at.isoformat(),
            }
            for bot in strategies
        ]

        # Возвращаем данные в формате JSON
        return JSONResponse(content={"bots": bots_list}, status_code=200)
    
    except Exception as e:
        return JSONResponse(content={"error": f"Ошибка сервера: {str(e)}"}, status_code=500)

    

@auth_routes.post("/start-bot/{bot_name}/{strategy_name}")
async def start_bot(bot_name: str, strategy_name: str, user: User = Depends(get_current_user)):
    task = start_user_strategy.delay(user.id, bot_name, strategy_name)
    return {"message": f"Task to start bot {bot_name} with strategy {strategy_name} created.", "task_id": task.id}

@auth_routes.post("/stop-bot/{bot_id}")
async def stop_bot(bot_id: int, user: User = Depends(get_current_user)):
    # Получаем стратегию по bot_id
    bot = await Bot.filter(id=bot_id, user=user).first()
    if not bot:
        return {"error": "Bot not found or does not belong to the user."}

    task = stop_user_bot.delay(user.id, bot.strategy)
    return {"message": f"Task to stop bot {bot_id} with strategy {bot.strategy} created.", "task_id": task.id}





    




# # ДЛЯ КАТАЛОГА:
# @auth_routes.get("/strategies", response_class=HTMLResponse)
# async def get_strategies(request: Request):
#     strategies_path = os.path.abspath("./user_data/example/strategies")
#     # Получаем список только `.py` файлов
#     strategies = [
#         os.path.splitext(name)[0]  # Убираем расширение `.py`
#         for name in os.listdir(strategies_path)
#         if name.endswith(".py")
#     ]

#     return templates.TemplateResponse("strategies.html", {
#         "request": request,
#         "strategies": strategies
#     })

# @auth_routes.post("/add_strategy")
# async def add_strategy(strategy_name: str = Form(...), user: User = Depends(get_current_user)):
#     # Передаём ID пользователя и название стратегии в Celery задачу
#     result = add_strategy_to_container.delay(user.id, strategy_name)



# @auth_routes.get("/user-strategies", response_model=List[Bot_Pydantic])
# async def get_user_strategies(user: User = Depends(get_current_user)):
#     strategies = await Bot.filter(user=user)
#     return await Bot_Pydantic.from_queryset(strategies)


# Получение ботов пользователя.
# @auth_routes.get("/user-bots", response_model=List[Bot_Pydantic])
# async def get_user_bots(user: User = Depends(get_current_user)):
#     try:
#         # Получаем QuerySet
#         bots = Bot.filter(user=user)
#         # Преобразуем QuerySet в Pydantic-модель
#         return await Bot_Pydantic.from_queryset(bots)
#     except Exception as e:
#         logging.error(f"Ошибка при получении ботов: {e}")
#         raise HTTPException(status_code=500, detail="Ошибка сервера")
    
