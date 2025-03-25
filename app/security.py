# app/security.py

import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException
import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import logging
from app.models import User

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY").encode()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 0.2

# Создание access_token.
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
    
# Проверка access_token.
def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Токен истёк.
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Invalid access token")
    
    
    

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY").encode()
fernet = Fernet(ENCRYPTION_KEY)

def encrypt_data(data: str) -> str:
    return fernet.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    return fernet.decrypt(encrypted_data.encode()).decode()
