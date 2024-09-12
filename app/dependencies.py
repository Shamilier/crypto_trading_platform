from datetime import datetime, timezone
from fastapi import Request, HTTPException
from app.models import RefreshToken
from app.security import verify_token, create_access_token
from fastapi.responses import RedirectResponse
from app.models import User


import logging

async def get_current_user(request: Request):
    logging.info("Проверка Access токена")
    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            # Проверка Access токена
            payload = verify_token(access_token)
            logging.info("Access токен валиден")
            username = payload["sub"]
            # Возвращаем объект пользователя
            user = await User.get(username=username)
            return user
        except HTTPException:
            logging.info("Access токен истек, проверка Refresh токена")
            refresh_token_value = request.cookies.get("refresh_token")
            if not refresh_token_value:
                raise HTTPException(status_code=401, detail="Refresh токен отсутствует")

            # Проверяем Refresh токен в базе данных
            refresh_token = await RefreshToken.filter(token=refresh_token_value).first()
            if not refresh_token or refresh_token.expires_at < datetime.now(timezone.utc):
                raise HTTPException(status_code=401, detail="Refresh токен недействителен или истек")

            # Генерация нового Access токена
            user = await refresh_token.user
            new_access_token = create_access_token(data={"sub": user.username})
            logging.info("Создан новый Access токен")

            # Обновляем Access токен в cookies
            response = RedirectResponse(url="/", status_code=302)
            response.set_cookie(key="access_token", value=new_access_token, httponly=True)
            return user

    raise HTTPException(status_code=401, detail="Требуется авторизация")
