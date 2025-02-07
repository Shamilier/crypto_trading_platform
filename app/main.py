from fastapi import FastAPI
from .routes import auth_routes
from .database import init, close
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

@app.on_event("startup")
async def startup():
    await init()

@app.on_event("shutdown")
async def shutdown():
    await close()
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Указываем точный адрес фронтенда
    allow_credentials=True,  # Разрешаем куки
    allow_methods=["*"],  # Разрешаем все методы (GET, POST и т.д.)
    allow_headers=["*"],  # Разрешаем все заголовки
)

app.mount("/static", StaticFiles(directory="build/static"), name="static")

SECRET_KEY = "shamil-max"

app.include_router(auth_routes)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)


@app.on_event("shutdown")
async def shutdown():
    await close()

@app.get("/")
async def read_root():
    return {"message": "Welcome to Crypto Trading Platform!"}
