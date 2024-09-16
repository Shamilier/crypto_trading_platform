
import shutil
import os
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from tortoise.transactions import in_transaction
from passlib.hash import bcrypt
from app.models import User, RefreshToken
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from app.security import create_access_token, verify_token
from datetime import datetime, timedelta, timezone
import secrets
from app.dependencies import get_current_user
from tortoise.exceptions import IntegrityError
from tortoise.exceptions import DoesNotExist
from app.celery_worker import create_freqtrade_container
# from fastapi import APIRouter, Request, Depends, HTTPException
# from starlette.responses import RedirectResponse
# from app.dependencies import get_current_user  # Проверка токенов
from app.models import Containers


REFRESH_TOKEN_EXPIRE_DAYS = 7

auth_routes = APIRouter()
templates = Jinja2Templates(directory="templates")


# ------

def create_refresh_token():
    # Генерация случайного токена для безопасности
    return secrets.token_hex(32)


def generate_csrf_token():
    return secrets.token_hex(32)


def create_user_directory(user_id):
    # Путь к директории пользователя
    user_directory = f"./user_data/user_{user_id}"
    
    # Путь к папке example, откуда мы будем копировать файлы
    example_directory = "./user_data/example"
    
    # Если директория для пользователя не существует, создаем её и копируем файлы
    if not os.path.exists(user_directory):
        os.makedirs(user_directory)
        shutil.copytree(example_directory, user_directory, dirs_exist_ok=True)
    
    return user_directory


# -----

# Обработчик для GET-запроса на страницу регистрации
@auth_routes.get("/register", response_class=HTMLResponse)
async def get_register(request: Request):
    csrf_token = generate_csrf_token()
    request.session["csrf_token"] = csrf_token  # или можно использовать куки
    return templates.TemplateResponse("register.html", {"request": request, "csrf_token": csrf_token})



# Обработчик для POST-запроса для регистрации пользователя
@auth_routes.post("/register", response_class=HTMLResponse)
async def post_register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...), csrf_token: str = Form(...)):
    print(f"Received: username={username}, email={email}, password={password}")
    
    # Проверка, существует ли уже пользователь с таким именем или почтой
    existing_user = await User.filter(username=username).first()
    existing_email = await User.filter(email=email).first()
    
    if existing_user:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Пользователь с таким именем уже существует."
        })

    if existing_email:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Пользователь с таким email уже существует."
        })
    
    # Если пользователя нет, то создаем нового
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




# Обработчик для GET-запроса на страницу логина
@auth_routes.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    csrf_token = generate_csrf_token()
    request.session["csrf_token"] = csrf_token  # или можно использовать куки
    return templates.TemplateResponse("login.html", {"request": request, "csrf_token": csrf_token})




@auth_routes.post("/refresh")
async def refresh_token(request: Request):
    refresh_token_value = request.cookies.get("refresh_token")
    
    if not refresh_token_value:
        raise HTTPException(status_code=401, detail="Refresh токен отсутствует")

    # Проверка токена в базе данных
    refresh_token = await RefreshToken.get(token=refresh_token_value).first()
    
    if not refresh_token or refresh_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh токен недействителен или истек")

    # Генерация нового Access токена
    access_token = create_access_token(data={"sub": refresh_token.user.username})

    # Обновление Access токена в cookies
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite='Lax')
    return response




# Обработчик для POST-запроса для логина пользователя
@auth_routes.post("/login")
async def post_login(request: Request, username: str = Form(...), password: str = Form(...), csrf_token: str = Form(...)):
    try:
        # Поиск пользователя в базе данных по имени
        user = await User.get(username=username)
    except DoesNotExist:
        # Возвращаем сообщение об ошибке, если пользователь не найден
        return templates.TemplateResponse("login.html", {"request": request, "error": "Пользователь не найден"})

    # Проверка, что пользователь найден, и пароль совпадает
    if user and bcrypt.verify(password, user.hashed_password):
        access_token = create_access_token(data={"sub": username})
        
        # Проверяем, существует ли уже Refresh токен для пользователя
        refresh_token = await RefreshToken.filter(user=user).first()

        if refresh_token:
            # Обновляем срок действия существующего Refresh токена
            refresh_token_value = refresh_token.token
            refresh_token.expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            await refresh_token.save()
        else:
            # Создаем новый Refresh токен, если его нет
            refresh_token_value = create_refresh_token()
            expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
            await RefreshToken.create(token=refresh_token_value, user=user, expires_at=expires_at)
        
        # Устанавливаем токены в cookies
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite='Lax')
        response.set_cookie(key="refresh_token", value=refresh_token_value, httponly=True, secure=False, samesite='Lax')
        
        return response
    else:
        # Неправильный пароль
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неправильное имя пользователя или пароль"})


@auth_routes.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    token = request.cookies.get("access_token")
    
    # Если токен существует и валиден, показываем кнопку "Личный кабинет"
    if token:
        try:
            verify_token(token)
            return templates.TemplateResponse("main_page.html", {"request": request, "is_authenticated": True})
        except HTTPException:
            # Если Access токен истек, проверяем наличие Refresh токена
            refresh_token_value = request.cookies.get("refresh_token")
            if not refresh_token_value:
                return templates.TemplateResponse("main_page.html", {"request": request, "is_authenticated": False})

            # Проверяем валидность Refresh токена
            refresh_token = await RefreshToken.filter(token=refresh_token_value).first()
            if not refresh_token or refresh_token.expires_at < datetime.now(timezone.utc):
                return templates.TemplateResponse("main_page.html", {"request": request, "is_authenticated": False})

            # Генерируем новый Access токен
            user = await refresh_token.user
            new_access_token = create_access_token(data={"sub": user.username})

            # Обновляем Access токен в cookies
            response = RedirectResponse(url="/", status_code=302)
            response.set_cookie(key="access_token", value=new_access_token, httponly=True)
            return response

    # Если токена нет или он недействителен, показываем кнопки входа и регистрации
    return templates.TemplateResponse("main_page.html", {"request": request, "is_authenticated": False})



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



@auth_routes.get("/dashboard/user_{user_id:int}")
async def user_dashboard(user_id: int, request: Request, current_user: User = Depends(get_current_user)):
    # Проверка токена и прав доступа
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    # Получение информации о контейнере пользователя
    try:
        # Используем filter, чтобы избежать MultipleObjectsReturned
        container = await Containers.filter(user_id=user_id).first()
        
        if not container:
            raise HTTPException(status_code=404, detail="Контейнер не найден")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сервера: {str(e)}")

    # Перенаправление пользователя на Freqtrade UI, используя порт из базы данных
    public_url = f"http://hse-monopoly.online/account/user_{user_id}" # Используем публичный домен
    return RedirectResponse(public_url)
