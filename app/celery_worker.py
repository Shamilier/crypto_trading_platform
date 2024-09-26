import docker
import os
import tarfile
from io import BytesIO
from celery import Celery
from tortoise.transactions import in_transaction
from app.models import Containers  # Импорт модели Containers
from tortoise import Tortoise
import asyncio

celery = Celery(
    'crypto_trading_app',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0'
)

client = docker.from_env()

async def init_db():
    await Tortoise.init(
        db_url='postgres://postgres:password@db:5432/trading_db',
        modules={'models': ['app.models']}
    )
    await Tortoise.generate_schemas()

# Функция для закрытия соединений с базой данных
async def close_db():
    await Tortoise.close_connections()


# Функция для создания tar-архива из папки пользователя
def create_tar_archive(source_dir):
    tar_stream = BytesIO()
    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=source_dir)
                tar.add(file_path, arcname=arcname)
    tar_stream.seek(0)
    return tar_stream

# Функция для копирования архива в контейнер
def copy_to_container(container, source_path, target_path):
    tar_archive = create_tar_archive(source_path)
    container.put_archive(target_path, tar_archive)

# Функция для получения следующего доступного порта
async def get_next_available_port():
    # sourcery skip: assign-if-exp, reintroduce-else
    last_container = await Containers.all().order_by('-port').first()
    if last_container:
        return last_container.port + 1
    return 3001  # Начинаем с порта 3000


def run_sync(func):
    """ Запускает асинхронную функцию в синхронном коде """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # Если нет запущенного event loop, создаем новый
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(func)


@celery.task
def create_freqtrade_container(user_id):
    return run_sync(_create_freqtrade_container(user_id))

async def _create_freqtrade_container(user_id):
    await init_db()
    try:
        async with in_transaction():
            existing_container = await Containers.filter(user_id=user_id).first()
            if existing_container:
                return f"Container for user {user_id} already exists on port {existing_container.port}"

            container_name = f"freqtrade_user_{user_id}"

            # Путь к папке с данными пользователя
            user_data_host_path = os.path.abspath(f"./user_data/user_{user_id}")

            # Проверка наличия папки
            if not os.path.exists(user_data_host_path):
                return f"Error: directory {user_data_host_path} does not exist"
            
            # Получаем следующий доступный порт
            next_port = await get_next_available_port()

            try:
                # Создаем контейнер
                container = client.containers.create(
                    "freqtradeorg/freqtrade:stable",
                    name=container_name,
                    detach=True,
                    ports={'8080/tcp': ('0.0.0.0', next_port)},  # Назначаем порт
                    command=["trade", "-c", "/freqtrade/user_data/config.json", "--strategy", "ScalpFutures", "--api-server.basepath", f"/user_{user_id}/dashboard"]
                )


                # Стартуем контейнер
                container.start()

                # Копируем данные пользователя в контейнер
                copy_to_container(container, user_data_host_path, '/freqtrade/user_data')

                # Сохраняем информацию о контейнере в базе данных
                await Containers.create(
                    user_id=user_id,
                    container_id=container.id,
                    port=next_port,
                    status="running"
                )

                return f"Container {container_name} created on port {next_port} and user data copied."
            
            except docker.errors.ImageNotFound:
                return "Error: Image freqtradeorg/freqtrade:stable not found."
            
            except Exception as e:
                return f"Error occurred: {str(e)}"
    finally:
        await close_db()
