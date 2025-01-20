# # Базовый образ
# FROM python:3.10-slim

# # Устанавливаем рабочую директорию
# WORKDIR /app

# # Копируем файл зависимостей и устанавливаем их
# COPY requirements.txt requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt

# # Копируем все файлы приложения
# COPY . .

# # Указываем порт, на котором будет работать FastAPI
# EXPOSE 8000

# # Команда для запуска приложения
# CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
# Базовый образ
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Установка необходимых зависимостей для docker-compose
RUN apt-get update && apt-get install -y \
    curl \
    && curl -L "https://github.com/docker/compose/releases/download/v2.21.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose \
    && chmod +x /usr/local/bin/docker-compose \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы приложения
COPY . .

# Указываем порт, на котором будет работать FastAPI
EXPOSE 8000

# Команда для запуска приложения
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
