from fastapi import FastAPI
from .routes import auth_routes
from .database import init, close
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

SECRET_KEY = "shamil-max"

app.include_router(auth_routes)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

@app.on_event("startup")
async def startup():
    await init()

@app.on_event("shutdown")
async def shutdown():
    await close()

@app.get("/")
async def read_root():
    return {"message": "Welcome to Crypto Trading Platform!"}
