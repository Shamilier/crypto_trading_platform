import docker
import os
import tarfile
from io import BytesIO
from celery import Celery

celery = Celery(
    'crypto_trading_app',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0'
)

client = docker.from_env()

def create_tar_archive(source_dir):
    tar_stream = BytesIO()
    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=source_dir)  # Убираем пути папок
                print(f"Adding {file_path} as {arcname} to archive.")  # Отладка: выводим путь к файлу
                tar.add(file_path, arcname=arcname)
    tar_stream.seek(0)
    return tar_stream

def copy_to_container(container, source_path, target_path):
    tar_archive = create_tar_archive(source_path)
    result = container.put_archive(target_path, tar_archive)
    print(f"Copy to container result: {result}")  # Отладка: выводим результат копирования

@celery.task
def create_freqtrade_container(user_id):
    container_name = f"freqtrade_user_{user_id}"

    # Путь к папке с данными пользователя
    user_data_host_path = os.path.abspath(f"./user_data/user_{user_id}")

    # Проверка наличия папки
    if not os.path.exists(user_data_host_path):
        return f"Error: directory {user_data_host_path} does not exist"
    
    print(f"Host user data path: {user_data_host_path}")

    try:
        # Создаем контейнер с правильным путем к конфигурации
        container = client.containers.create(
            "freqtradeorg/freqtrade:stable",
            name=container_name,
            detach=True,
            command=["trade", "-c", "/freqtrade/user_data/config.json", "--strategy", "ScalpFutures"]
        )

        # Стартуем контейнер
        container.start()

        # Копируем только содержимое папки user_1 без самой папки
        copy_to_container(container, user_data_host_path, '/freqtrade/user_data')

        # Отладка: проверяем содержимое контейнера
        exec_result = container.exec_run("ls -la /freqtrade/user_data")
        print(f"Container content after copy:\n{exec_result.output.decode()}")  # Выводим содержимое папки в контейнере

        return f"Container {container_name} created and user data copied."
    
    except docker.errors.ImageNotFound:
        return f"Error: Image freqtradeorg/freqtrade:stable not found."
    
    except Exception as e:
        return f"Error occurred: {str(e)}"
