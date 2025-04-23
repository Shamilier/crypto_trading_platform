from fastapi import FastAPI
from .routes import auth_routes
from .database import init, close
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from fastapi.responses import Response




load_dotenv()

app = FastAPI()

@app.on_event("startup")
async def startup():
    await init()

@app.on_event("shutdown")
async def shutdown():
    await close()
    
app.add_middleware(
    CORSMiddleware,
    # allow_origins=["http://localhost:3000"],  # Указываем точный адрес фронтенда
    # allow_origins=["http://45.93.201.231:8000"],
    allow_origins=["https://eazy-trade.ru"],
    allow_credentials=True,  # Разрешаем куки
    allow_methods=["*"],  # Разрешаем все методы (GET, POST и т.д.)
    allow_headers=["*"],  # Разрешаем все заголовки
)

app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

app.include_router(auth_routes)
app.add_middleware(SessionMiddleware, secret_key=os.getenv('SECRET_KEY'))


@app.on_event("shutdown")
async def shutdown():
    await close()
