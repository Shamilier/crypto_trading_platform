import docker
import os
import tarfile
from io import BytesIO
from celery import Celery
from tortoise.transactions import in_transaction

from tortoise import Tortoise
import asyncio
from app.models import Bot, ApiKey, User  # Импорт модели Bot
import subprocess
import shutil
import yaml
import logging
from freqtrade_client import FtRestClient
import secrets
import json



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

# Функция для копирования архива в контейнер
def copy_to_container(container, source_path, target_path):
    tar_archive = create_tar_archive(source_path)
    container.put_archive(target_path, tar_archive)

# Функция для получения следующего доступного порта
async def get_next_available_port():
    last_container = await Bot.all().order_by('-port').first()
    if last_container:
        return last_container.port + 1
    return 3000  # Начинаем с порта 3000, если нет записей в БД


def run_sync(func):
    """ Запускает асинхронную функцию в синхронном коде """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # Если нет запущенного event loop, создаем новый
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(func)


def create_password_for_freqtrade_api():
    return secrets.token_hex(16)

@celery.task
def create_freqtrade_container(user_id):
    return run_sync(_create_freqtrade_container(user_id))

async def _create_freqtrade_container(user_id):
    await init_db()
    try:
        async with in_transaction():

            user_directory = f"./user_data/user_{user_id}"

            if not os.path.exists(os.path.join(user_directory, "docker-compose.yml")):
                return f"Docker Compose file not found for user {user_id}."

            # Регистрируем проект без запуска контейнера
            subprocess.run(
                ["docker-compose", "-p", f"user_{user_id}", "config"],
                cwd=user_directory,
                check=True
            )
            container_name = f"user_{user_id}_placeholder"
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






def generate_secret_config(
    user_directory, strategy_name,deposit, is_dry_run,
    exchange, api_key, secret_key, is_telegram, tg_token, chat_id,
    username, password):
    """
    Генерирует секретный конфиг для стратегии на основе данных из БД.
    :param user_directory: директория пользователя (например, "./user_data/user_{user_id}")
    :param strategy_name: имя стратегии (например, "E0V1E")
    :param deposit: депозит или доступный капитал пользователя
    :param api_key_details: словарь с API-ключом и секретом, например: {"api_key": "...", "secret_key": "..."}
    :param is_dry_run: булево значение, демонстрационный режим или реальный запуск
    :return: путь к сгенерированному файлу (например, "./user_data/user_{user_id}/E0V1E_secret.json")
    """
    secret_config = {
        "available_capital": int(deposit),
        "dry_run": is_dry_run,  
        "exchange": {
            "name": exchange,
            "key": api_key,
            "secret": secret_key,
            "ccxt_config": {
                "enableRateLimit": True  
            },
            "ccxt_async_config": {
                "enableRateLimit": True,
                "rateLimit": 250
            }
        },
        "telegram": {
            "enabled": is_telegram,  
            "token": tg_token,
            "chat_id": chat_id
        },
        "api_server": {
            "enabled": True,
            "listen_ip_address": "0.0.0.0",
            "listen_port": 8888,
            "verbosity": "error",
            "jwt_secret_key": "",
            "ws_token": "",
            "CORS_origins": [],
            "username": username,
            "password": password
        },
        "bot_name": "freqtrade"
    }
    
    secret_config_filename = f"{strategy_name}_secret.json"
    secret_config_path = os.path.join(user_directory, secret_config_filename)
    
    with open(secret_config_path, "w") as f:
        json.dump(secret_config, f, indent=4)
    
    return secret_config_filename 



@celery.task
def add_strategy_to_container(user_id, strategy_name, deposit, api_key_name, is_dry_run):
    """Добавляет стратегию в контейнер пользователя"""
    return run_sync(_add_strategy_to_container(user_id, strategy_name, deposit, api_key_name, is_dry_run))


async def _add_strategy_to_container(user_id, strategy_name, deposit, api_key_name, is_dry_run):
    """Асинхронная функция для добавления стратегии с созданием нового контейнера, но без запуска"""
    await init_db()
    try:
        logging.error(f"add_strategy_to_container 3")
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

        api_key_curr = await ApiKey.filter(name=api_key_name).first()
        if not api_key_curr:
            return f"Error: API key {api_key_name} not found."
        # Собираем данные API в словарь (расшифровываем при необходимости)
        api_key =  api_key_curr.api_key
        secret_key = api_key_curr.secret_key
        exchange =  api_key_curr.exchange

        is_telegram = False
        tg_token = "123"
        chat_id = "123"
        username = "freqtrader"
        password = create_password_for_freqtrade_api()
        

        secret_config_filename = generate_secret_config(
            user_directory, strategy_name,deposit, is_dry_run,
            exchange, api_key, secret_key, is_telegram, tg_token, chat_id,
            username, password
        )

        # Создаем новый контейнер
        container_name = f"freqtrade_user_{user_id}_strategy_{strategy_name}"
        next_port = await get_next_available_port()

        # Обновляем docker-compose.yml
        # update_docker_compose(user_directory, container_name, next_port, strategy_name)
        update_docker_compose(user_directory, container_name, next_port, strategy_name, secret_config_filename=secret_config_filename)

        # Подготавливаем контейнер, но не запускаем его
        subprocess.run(["docker-compose", "create", container_name], cwd=user_directory, check=True)
        # subprocess.run(["docker-compose", "up", "-d", container_name], cwd=user_directory, check=True)

        # Получаем объект контейнера
        container = client.containers.get(container_name)
        container.restart()

        # print(user_directory)
        # print("Полный список файлов и директорий в", user_directory)
        # for root, dirs, files in os.walk(user_directory):
        #     for filename in files:
        #         full_path = os.path.join(root, filename)
        #         print(" -", full_path)

        # Копируем локальные файлы в контейнер
        copy_to_container(container, user_directory, "/freqtrade/user_data")

        
        user_curr = await User.filter(id = user_id).first()
        api_key_curr = await ApiKey.filter(name = api_key_name).first()
        await Bot.create(
            name = strategy_name,
            password = password,
            status = "started",
            available_capital = deposit,
            is_dry_run = is_dry_run,
            user = user_curr,
            api_key = api_key_curr,
            port = next_port,
            container_id = container_name
        )


        return f"Strategy {strategy_name} successfully added and container {container_name} created."
    except Exception as e:
        raise Exception(f"Error occurred: {str(e)}")
    finally:
        await close_db()




def update_docker_compose(user_directory, container_name, next_port, strategy_name, secret_config_filename):
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
    base_cmd = (
        f"trade "
        f"--db-url sqlite:////freqtrade/user_data/trades.sqlite "
        f"--config /freqtrade/user_data/{strategy_name}.json"
    )
    if secret_config_filename:
        base_cmd += f" --config /freqtrade/user_data/{secret_config_filename}"
    base_cmd += f" --strategy {strategy_name}"

    # Добавляем новый сервис
    compose_data["services"][container_name] = {
        "image": "freqtradeorg/freqtrade:stable",
        "container_name": container_name,
        "restart": "unless-stopped",
        "volumes": [
            f"{user_directory}:/freqtrade/user_data"
        ],
        "ports": [
            f"{next_port}:8888"
        ],
        "command": base_cmd,
        "logging": {
            "driver": "json-file",
            "options": {
                "max-size": "16m",
                "max-file": "3"
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
        user = await User.filter(id = user_id).first()
        container_info = await Bot.filter(user=user, container_id=f"freqtrade_user_{user_id}_strategy_{bot_name}").first()
        if not container_info:
            return f"Error: Container for strategy {bot_name} not found."

        container_name = container_info.container_id
        container = client.containers.get(container_name)

        # Проверяем, активен ли контейнер
        if container.status != "running":
            container.restart()

        # Убедимся, что контейнер запущен и активен
        if container.status != "running":
            return f"Error: Failed to start container {container_name}."

        # Обновляем статус бота
        bot = await Bot.filter(user=user, container_id=f"freqtrade_user_{user_id}_strategy_{bot_name}" ).first()
        if bot:
            bot.status = "active"
            await bot.save()

        # Обновляем статус контейнера
        container_info.status = "running"
        await container_info.save()

        return f"Strategy {bot_name} started in container {container_name}."
    except Exception as e:
        return f"Error occurred while starting strategy {bot_name}: {str(e)}"
    finally:
        await close_db()


@celery.task
def start_user_strategy(user_id, bot_name, strategy_name):
    """
    Задача, которая должна:
      1. Найти нужный бот в БД
      2. Вызвать вторую задачу (api_interface_no_param), чтобы 
         отдать команду Freqtrade (start).
    """
    return run_sync(_start_user_strategy(user_id, bot_name, strategy_name))


async def _start_user_strategy(user_id, bot_name, strategy_name):
    await init_db()
    try:
        async with in_transaction():
            # 1) Ищем, есть ли бот
            user = await User.filter(id = user_id).first()
            port = await get_next_available_port() - 1
            print(bot_name, port, user_id)
            bot_record = await Bot.filter(user=user, name=bot_name, port = port).first()
            if not bot_record:
                return f"!!!!!!!!!Error: Bot {bot_name} not found in DB for user_id={user_id}!!!!!!!!!!!!"

            container_port = bot_record.port 
            password = bot_record.password
            logging.info(f"Will send 'start' command to Freqtrade on port {container_port}")

            # 2) Вызываем вторую задачу Celery, которая реально пойдёт в Freqtrade API
            #    get_command='start' – значит, будем делать client.start().
            result = api_interface_no_param.delay(
                get_command='start',
                username='freqtrader',
                password=password,
                port=container_port
            )

            # 3) Обновляем локально статус бота, что дескать он "запускается".
            bot_record.status = "trading"
            await bot_record.save()

            # Мы вернём task_id, например
            return f"Launched start command for {bot_name}, check task {result.id}"
    finally:
        await close_db()


@celery.task
def api_interface_no_param(get_command, username, password, port):
    """
    Вторая задача, которая чисто ходит в Freqtrade API
    """
    return run_sync(_api_interface_no_param(get_command, username, password, port))


async def _api_interface_no_param(get_command, username, password, port):

    try:
        # 1) Создаём клиента Freqtrade
        client = FtRestClient(f"http://host.docker.internal:{port}", username, password)
        exchange_class = getattr(client, get_command.lower(), None)
        if not exchange_class:
            return {"error": f"Unknown command '{get_command}' for FtRestClient"}

        # 3) Вызываем метод
        ping = exchange_class()  # например client.start() или client.stop()
        logging.info(f"Command '{get_command}' result: {ping}")

        return {"info": ping, "command": get_command}

    finally:
        pass


# @celery.task
# def stop_user_bot(user_id, strategy_name):
#     """Останавливает контейнер для указанной стратегии."""
#     return run_sync(_stop_user_bot(user_id, strategy_name))


# async def _stop_user_bot(user_id, strategy_name):
#     await init_db()
#     try:
#         # Получаем информацию о контейнере стратегии

#         container_info = await Bot.filter(container_id=f"freqtrade_user_{user_id}_strategy_{strategy_name}" ).first()
#         if not container_info:
#             return f"Error: Container for strategy {strategy_name} not found."
#         container_name = container_info.container_id
#         container = client.containers.get(container_name)

#         # Проверяем, активен ли контейнер
#         if container.status != "running":
#             return f"Container {container_name} is not running."

#         # Останавливаем контейнер
#         container.stop()

#         # Обновляем статус контейнера
#         container_info.status = "stopped"
#         await container_info.save()

#         # Обновляем статус бота
#         bot = await Bot.filter(container_id=f"freqtrade_user_{user_id}_strategy_{strategy_name}" ).first()
#         if bot:
#             bot.status = "inactive"
#             await bot.save()

#         return f"Container {container_name} stopped successfully."
#     except Exception as e:
#         return f"Error occurred while stopping strategy {strategy_name}: {str(e)}"
#     finally:
#         await close_db()