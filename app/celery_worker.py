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
                # Создаем контейнер но не запускаем
                container = client.containers.create(
                    "freqtradeorg/freqtrade:stable",
                    name=container_name,
                    detach=True,
                    ports={'8080/tcp': ('0.0.0.0', next_port)},  # Назначаем порт
                    command=[
                        "trade",
                        "-c",
                        "/freqtrade/user_data/f_scalp.json",
                        "--strategy",
                        "ScalpFutures"
                    ]
                )


                # Стартуем контейнер
                # container.start()

                # Копируем данные пользователя в контейнер
                copy_to_container(container, user_data_host_path, '/freqtrade/user_data')

                # Сохраняем информацию о контейнере в базе данных
                await Containers.create(
                    user_id=user_id,
                    container_id=container.id,
                    port=next_port,
                    status="created"
                )

                return f"Container {container_name} created on port {next_port} and user data copied."
            
            except docker.errors.ImageNotFound:
                return "Error: Image freqtradeorg/freqtrade:stable not found."
            
            except Exception as e:
                return f"Error occurred: {str(e)}"
    finally:
        await close_db()




@celery.task
def add_strategy_to_container(user_id, strategy_name):
    """Добавляет стратегию в контейнер пользователя"""
    # try:
    #     # Создаём новый событийный цикл в отдельном потоке
    #     loop = asyncio.new_event_loop()
    #     asyncio.set_event_loop(loop)
    #     result = loop.run_until_complete(_add_strategy_to_container(user_id, strategy_name))
    #     return result
    # finally:
    #     # Закрываем цикл после завершения
    #     loop.close()
    return run_sync(_add_strategy_to_container(user_id, strategy_name))


async def _add_strategy_to_container(user_id, strategy_name):
    """Асинхронная функция для добавления стратегии"""
    await init_db()
    try:
        # Основная логика добавления стратегии
        user_path = os.path.abspath(f"./user_data/user_{user_id}")
        user_strategies_path = os.path.join(user_path, "strategies")
        json_file_path = os.path.abspath(f"./user_data/example/{strategy_name}.json")
        py_file_path = os.path.abspath(f"./user_data/example/strategies/{strategy_name}.py")

        # Проверяем наличие файлов стратегии
        if not os.path.exists(json_file_path) or not os.path.exists(py_file_path):
            return f"Error: Strategy files for {strategy_name} not found."

        # Создаём необходимые папки
        os.makedirs(user_path, exist_ok=True)
        os.makedirs(user_strategies_path, exist_ok=True)

        # Копируем файлы
        user_json_file_path = os.path.join(user_path, f"{strategy_name}.json")
        user_py_file_path = os.path.join(user_strategies_path, f"{strategy_name}.py")

        with open(json_file_path, 'rb') as src_file:
            with open(user_json_file_path, 'wb') as dest_file:
                dest_file.write(src_file.read())

        with open(py_file_path, 'rb') as src_file:
            with open(user_py_file_path, 'wb') as dest_file:
                dest_file.write(src_file.read())

        # Монтируем файлы в контейнер
        container_info = await Containers.filter(user_id=user_id).first()
        if not container_info:
            return f"Error: Container for user {user_id} not found."

        container_name = container_info.container_id
        container = client.containers.get(container_name)

        # Монтируем JSON файл
        with open(user_json_file_path, "rb") as json_file:
            json_tar = create_tar_archive_from_file({f"{strategy_name}.json": json_file.read()})
            container.put_archive("/freqtrade/user_data", json_tar)

        # Монтируем Python файл
        with open(user_py_file_path, "rb") as py_file:
            py_tar = create_tar_archive_from_file({f"{strategy_name}.py": py_file.read()})
            container.put_archive("/freqtrade/user_data/strategies/", py_tar)

        await Bot.create(
            user_id=user_id,
            name=strategy_name,  # Название совпадает с названием стратегии
            strategy=strategy_name,  # Название стратегии
            status="inactive",  # Статус: неактивен
            balance_used=-1.0,  # Пока неизвестно, используем -1
            indicators=["-"],  # Пока пустые индикаторы
            profit=0.0,  # Начальная прибыль
        )

        return f"Strategy {strategy_name} successfully added to container {container_name} and database."
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



@celery.task
def start_user_strategy(user_id, bot_name, strategy_name):
    """Запускает стратегию как процесс в существующем контейнере."""
    return run_sync(_start_user_strategy(user_id, bot_name, strategy_name))

async def _start_user_strategy(user_id, bot_name, strategy_name):
    await init_db()
    try:
        # Получаем контейнер пользователя
        container_info = await Containers.filter(user_id=user_id).first()
        if not container_info:
            return f"Error: Container for user {user_id} not found."

        container_name = container_info.container_id
        container = client.containers.get(container_name)

        # Проверяем, активен ли контейнер
        if container.status != "running":
            container.start()

        # Формируем путь к конфигурации стратегии
        strategy_config_path = f"/freqtrade/user_data/{strategy_name}.json"

        # Запускаем стратегию как процесс в контейнере
        exec_result = container.exec_run([
            "trade",
            "-c",
            strategy_config_path,
            "--strategy",
            strategy_name
        ], detach=True)

        if exec_result.exit_code is not None and exec_result.exit_code != 0:
            return f"Error starting strategy {strategy_name}: {exec_result.output.decode('utf-8')}"

        # Обновляем статус бота
        bot = await Bot.filter(user_id=user_id, name=bot_name, strategy=strategy_name).first()
        if bot:
            bot.status = "active"
            await bot.save()

        return f"Strategy {strategy_name} started in container {container_name}."
    except Exception as e:
        return f"Error occurred: {str(e)}"
    finally:
        await close_db()

