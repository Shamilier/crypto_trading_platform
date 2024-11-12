import shutil
import os
from typing import List
import ccxt
from fastapi import HTTPException
from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from tortoise.transactions import in_transaction
from passlib.hash import bcrypt
from app.models import User, RefreshToken, ApiKey, ApiKeyIn_Pydantic, ApiKey_Pydantic, Containers
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from app.security import create_access_token, verify_token
from datetime import datetime, timedelta, timezone
import secrets
from app.security import *
from app.dependencies import get_current_user
from tortoise.exceptions import IntegrityError, DoesNotExist
from app.celery_worker import create_freqtrade_container
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())


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
    example_directory = "./user_data/example"
    
    if not os.path.exists(user_directory):
        os.makedirs(user_directory)
        shutil.copytree(example_directory, user_directory, dirs_exist_ok=True)
    
    return user_directory


async def validate_api_key(exchange_name: str, api_key: str, secret_key: str):
    try:
        # Создаем объект биржи с переданными API ключами
        exchange_class = getattr(ccxt, exchange_name.lower())
        exchange = exchange_class({
            'apiKey': api_key,
            'secret': secret_key,
            'enableRateLimit': True,
        })

        # Используем fetch_balance для проверки подключения
        balance = exchange.fetch_balance()
        print("API ключи валидны, получен баланс:", balance)
        return True

    except ccxt.AuthenticationError:
        print("Ошибка аутентификации: Невалидные токены API")
        raise HTTPException(status_code=400, detail="Невалидные токены API")
    except Exception as e:
        print("Неизвестная ошибка при проверке токенов:", e)
        raise HTTPException(status_code=500, detail="Ошибка при проверке токенов")
# ------ Routes ------

# Register Page
@auth_routes.get("/register", response_class=HTMLResponse)
async def get_register(request: Request):
    csrf_token = generate_csrf_token()
    request.session["csrf_token"] = csrf_token
    return templates.TemplateResponse("register.html", {"request": request, "csrf_token": csrf_token})


# Register User
@auth_routes.post("/register", response_class=HTMLResponse)
async def post_register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), csrf_token: str = Form(...)):
    existing_user = await User.filter(username=username).first()
    existing_email = await User.filter(email=email).first()
    
    if existing_user or existing_email:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Пользователь с таким именем или email уже существует."
        })
    
    hashed_password = bcrypt.hash(password)
    try:
        user = await User.create(username=username, email=email, hashed_password=hashed_password)
    except IntegrityError:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Ошибка создания пользователя."
        })

    return templates.TemplateResponse("register.html", {
        "request": request,
        "success": f"Пользователь {username} успешно зарегистрирован!"
    })


# Login Page
@auth_routes.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    csrf_token = generate_csrf_token()
    request.session["csrf_token"] = csrf_token
    return templates.TemplateResponse("login.html", {"request": request, "csrf_token": csrf_token})


# Refresh Token Endpoint
@auth_routes.post("/refresh")
async def refresh_token(request: Request):
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        raise HTTPException(status_code=401, detail="Refresh токен отсутствует")

    refresh_token = await RefreshToken.get(token=refresh_token_value).first()
    if not refresh_token or refresh_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh токен недействителен или истек")

    access_token = create_access_token(data={"sub": refresh_token.user.username})
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite='Lax')
    return response


# Login User
@auth_routes.post("/login")
async def post_login(request: Request, username: str = Form(...), password: str = Form(...), csrf_token: str = Form(...)):
    try:
        user = await User.get(username=username)
    except DoesNotExist:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Пользователь не найден"})

    if user and bcrypt.verify(password, user.hashed_password):
        access_token = create_access_token(data={"sub": username})
        refresh_token = await RefreshToken.filter(user=user).first()

        if refresh_token:
            refresh_token_value = refresh_token.token
            refresh_token.expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            await refresh_token.save()
        else:
            refresh_token_value = create_refresh_token()
            expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            await RefreshToken.create(token=refresh_token_value, user=user, expires_at=expires_at)
        
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite='Lax')
        response.set_cookie(key="refresh_token", value=refresh_token_value, httponly=True, secure=False, samesite='Lax')
        
        return response
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неправильное имя пользователя или пароль"})


# Main Page
@auth_routes.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    token = request.cookies.get("access_token")
    
    if token:
        try:
            verify_token(token)
            return templates.TemplateResponse("main_page.html", {"request": request, "is_authenticated": True})
        except HTTPException:
            refresh_token_value = request.cookies.get("refresh_token")
            if not refresh_token_value:
                return templates.TemplateResponse("main_page.html", {"request": request, "is_authenticated": False})

            refresh_token = await RefreshToken.filter(token=refresh_token_value).first()
            if not refresh_token or refresh_token.expires_at < datetime.now(timezone.utc):
                return templates.TemplateResponse("main_page.html", {"request": request, "is_authenticated": False})

            user = await refresh_token.user
            new_access_token = create_access_token(data={"sub": user.username})

            response = RedirectResponse(url="/", status_code=302)
            response.set_cookie(key="access_token", value=new_access_token, httponly=True)
            return response

    return templates.TemplateResponse("main_page.html", {"request": request, "is_authenticated": False})


# Account Page
@auth_routes.get("/account", response_class=HTMLResponse)
async def account_page(request: Request, current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    existing_container = await Containers.filter(user_id=user_id, status="running").first()
    
    if not existing_container:
        user_directory = create_user_directory(user_id)
        create_freqtrade_container.delay(user_id)
    
    return templates.TemplateResponse("account_page.html", {
        "request": request,
        "username": current_user.username,
        "user_id": current_user.id
    })


# Add API Key to Database
@auth_routes.post("/api-keys", response_model=ApiKey_Pydantic)
async def create_api_key(api_key_data: ApiKeyIn_Pydantic, user: User = Depends(get_current_user)):
    try:
        # Проверка валидности токенов
        print(api_key_data.exchange.split('_')[0])
        await validate_api_key(api_key_data.exchange.split('_')[0], api_key_data.api_key, api_key_data.secret_key)

        # Если токены валидны, шифруем и сохраняем в базу данных
        encrypted_api_key = encrypt_data(api_key_data.api_key)
        encrypted_secret_key = encrypt_data(api_key_data.secret_key)

        new_api_key = await ApiKey.create(
            user=user,
            exchange=api_key_data.exchange,
            api_key=encrypted_api_key,
            secret_key=encrypted_secret_key,
        )
        return await ApiKey_Pydantic.from_tortoise_orm(new_api_key)

    except HTTPException as http_exc:
        print("HTTP ошибка:", http_exc.detail)
        raise http_exc
    except Exception as e:
        print("Неизвестная ошибка при сохранении API ключа:", e)
        raise HTTPException(status_code=500, detail="Ошибка при сохранении API ключа")
    
    
@auth_routes.get("/api-keys", response_model=List[ApiKey_Pydantic])
async def get_api_keys(user: User = Depends(get_current_user)):
    user_api_keys = ApiKey.filter(user=user)
    if not user_api_keys:
        print("Нет API ключей для пользователя")
    else:
        print("API ключи для пользователя:", user_api_keys)
    return await ApiKey_Pydantic.from_queryset(user_api_keys)


# bDUy4wOelVKWS53ico
# Gj7v51T7JyVzH2nX2CjIgkPWp3nhkVn6Aa1h