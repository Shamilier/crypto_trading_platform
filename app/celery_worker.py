import docker
import os
import tarfile
from io import BytesIO
from celery import Celery
from tortoise.transactions import in_transaction
from app.models import Containers  # Импорт модели Containers
from tortoise import Tortoise
import asyncio
from app.models import Bot  # Импорт модели Bot
import subprocess
import shutil
import yaml



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
            # Проверяем, существует ли уже контейнер для пользователя
            existing_container = await Containers.filter(user_id=user_id).first()
            if existing_container:
                return f"Container for user {user_id} already exists."

            user_directory = f"./user_data/user_{user_id}"

            # Проверяем существование docker-compose.yml
            if not os.path.exists(os.path.join(user_directory, "docker-compose.yml")):
                return f"Docker Compose file not found for user {user_id}."

            # Регистрируем проект без запуска контейнера
            subprocess.run(
                ["docker-compose", "-p", f"user_{user_id}", "config"],
                cwd=user_directory,
                check=True
            )

            # Создаём имя контейнера (placeholder)
            container_name = f"user_{user_id}_placeholder"

            # Сохраняем информацию о контейнере в базе данных
            await Containers.create(
                user_id=user_id,
                container_id=container_name,
                port=0,  # Заглушка не использует порт

                status="registered"  # Статус: зарегистрирован, но не запущен
            )

            return f"Project for user {user_id} successfully registered with placeholder container."
    finally:
        await close_db()


def run_docker_compose(user_directory):
    try:
        subprocess.run(
            ["docker-compose", "up", "-d"],
            cwd=user_directory,
            check=True
        )
    except subprocess.CalledProcessError as e:
        return f"Error running docker-compose: {str(e)}"








@celery.task
def add_strategy_to_container(user_id, strategy_name):
    """Добавляет стратегию в контейнер пользователя"""
    return run_sync(_add_strategy_to_container(user_id, strategy_name))


async def _add_strategy_to_container(user_id, strategy_name):
    """Асинхронная функция для добавления стратегии с созданием нового контейнера, но без запуска"""
    await init_db()
    try:
        # Основная логика добавления стратегии
        user_directory = f"./user_data/user_{user_id}"
        strategy_directory = os.path.join(user_directory, "strategies")
        json_file_path = os.path.abspath(f"./user_data/example/{strategy_name}.json")
        py_file_path = os.path.abspath(f"./user_data/example/strategies/{strategy_name}.py")

        # Проверяем наличие файлов стратегии
        if not os.path.exists(json_file_path) or not os.path.exists(py_file_path):
            return f"Error: Strategy files for {strategy_name} not found."

        # Создаем необходимые папки
        os.makedirs(strategy_directory, exist_ok=True)

        # Копируем файлы стратегии локально
        user_json_file_path = os.path.join(user_directory, f"{strategy_name}.json")
        user_py_file_path = os.path.join(strategy_directory, f"{strategy_name}.py")
        shutil.copy(json_file_path, user_json_file_path)
        shutil.copy(py_file_path, user_py_file_path)

        # Создаем новый контейнер
        container_name = f"freqtrade_user_{user_id}_strategy_{strategy_name}"
        next_port = await get_next_available_port()

        # Обновляем docker-compose.yml
        update_docker_compose(user_directory, container_name, next_port, strategy_name)

        # Подготавливаем контейнер, но не запускаем его
        subprocess.run(["docker-compose", "create", container_name], cwd=user_directory, check=True)

        # Получаем объект контейнера
        container = client.containers.get(container_name)

        # Копируем локальные файлы в контейнер
        copy_to_container(container, user_directory, "/freqtrade/user_data")

        # Сохраняем информацию о новом контейнере в базе данных
        await Containers.create(
            user_id=user_id,
            container_id=container_name,
            port=next_port,
            status="created"  # Контейнер создан, но не запущен
        )

        # Сохраняем информацию о стратегии
        await Bot.create(
            user_id=user_id,
            name=strategy_name,
            strategy=strategy_name,
            status="inactive",  # Статус стратегии: неактивна
            balance_used=-1.0,
            indicators=["-"],
            profit=0.0,
        )

        return f"Strategy {strategy_name} successfully added and container {container_name} created."
    except Exception as e:
        return f"Error occurred: {str(e)}"
    finally:
        await close_db()



def create_tar_archive_from_file(files: dict) -> BytesIO:
    """Создает tar-архив из переданных файлов"""
    tar_stream = BytesIO()
    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
        for file_name, file_data in files.items():
            tarinfo = tarfile.TarInfo(name=file_name)
            tarinfo.size = len(file_data)
            tar.addfile(tarinfo, BytesIO(file_data))
    tar_stream.seek(0)
    return tar_stream





def update_docker_compose(user_directory, container_name, next_port, strategy_name):
    """Добавляет новый сервис в docker-compose.yml без перезаписи существующего."""
    docker_compose_path = os.path.join(user_directory, "docker-compose.yml")

    # Загружаем существующий docker-compose.yml
    compose_data = {"version": "3.8", "services": {}}
    if os.path.exists(docker_compose_path):
        with open(docker_compose_path, "r") as file:
            try:
                compose_data = yaml.safe_load(file) or compose_data
            except yaml.YAMLError:
                # Если YAML содержит ошибки, используем пустую структуру
                pass

    # Убедимся, что секция services существует
    if "services" not in compose_data:
        compose_data["services"] = {}

    # Проверяем, добавлялся ли уже сервис
    if container_name in compose_data["services"]:
        print(f"Сервис {container_name} уже существует в docker-compose.yml")
        return
    
    if "freqtrade" in compose_data["services"]:
        compose_data["services"]["freqtrade"]["restart"] = "no"

    # Добавляем новый сервис
    compose_data["services"][container_name] = {
        "image": "freqtradeorg/freqtrade:stable",
        "container_name": container_name,
        "restart": "unless-stopped",
        "volumes": [
            f"{user_directory}:/freqtrade/user_data"
        ],
        "ports": [
            f"{next_port}"
        ],
        "command": f"trade --db-url sqlite:////freqtrade/user_data/trades.sqlite --config /freqtrade/user_data/{strategy_name}.json --strategy {strategy_name}",
        "logging": {
            "driver": "json-file",
            "options": {
                "max-size": "256m",
                "max-file": "30"
            }
        }

    }

    # Сохраняем обновленный файл
    with open(docker_compose_path, "w") as file:
        yaml.dump(compose_data, file, default_flow_style=False, sort_keys=False)

    print(f"Сервис {container_name} добавлен в docker-compose.yml")





@celery.task
def start_user_strategy(user_id, bot_name, strategy_name):
    """Запускает стратегию в отдельном контейнере."""
    return run_sync(_start_user_strategy(user_id, bot_name, strategy_name))

async def _start_user_strategy(user_id, bot_name, strategy_name):
    await init_db()
    try:
        # Получаем информацию о контейнере стратегии
        container_info = await Containers.filter(user_id=user_id, container_id=f"freqtrade_user_{user_id}_strategy_{strategy_name}").first()
        if not container_info:
            return f"Error: Container for strategy {strategy_name} not found."

        container_name = container_info.container_id
        container = client.containers.get(container_name)

        # Проверяем, активен ли контейнер
        if container.status != "running":
            container.start()

        # Убедимся, что контейнер запущен и активен
        if container.status != "running":
            return f"Error: Failed to start container {container_name}."

        # Обновляем статус бота
        bot = await Bot.filter(user_id=user_id, name=bot_name, strategy=strategy_name).first()
        if bot:
            bot.status = "active"
            await bot.save()

        # Обновляем статус контейнера
        container_info.status = "running"
        await container_info.save()

        return f"Strategy {strategy_name} started in container {container_name}."
    except Exception as e:
        return f"Error occurred while starting strategy {strategy_name}: {str(e)}"
    finally:
        await close_db()






@celery.task
def stop_user_bot(user_id, strategy_name):
    """Останавливает контейнер для указанной стратегии."""
    return run_sync(_stop_user_bot(user_id, strategy_name))


async def _stop_user_bot(user_id, strategy_name):
    await init_db()
    try:
        # Получаем информацию о контейнере стратегии

        container_info = await Containers.filter(user_id=user_id, container_id=f"freqtrade_user_{user_id}_strategy_{strategy_name}").first()
        if not container_info:
            return f"Error: Container for strategy {strategy_name} not found."
        container_name = container_info.container_id
        container = client.containers.get(container_name)

        # Проверяем, активен ли контейнер
        if container.status != "running":
            return f"Container {container_name} is not running."

        # Останавливаем контейнер
        container.stop()

        # Обновляем статус контейнера
        container_info.status = "stopped"
        await container_info.save()

        # Обновляем статус бота
        bot = await Bot.filter(user_id=user_id, strategy=strategy_name).first()
        if bot:
            bot.status = "inactive"
            await bot.save()

        return f"Container {container_name} stopped successfully."
    except Exception as e:
        return f"Error occurred while stopping strategy {strategy_name}: {str(e)}"
    finally:
        await close_db()
