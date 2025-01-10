from tortoise import fields
from tortoise.models import Model
from tortoise.contrib.pydantic import pydantic_model_creator


class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    hashed_password = fields.CharField(max_length=128)
    email = fields.CharField(max_length=255, unique=True)

    class Meta:
        table = "users"


class RefreshToken(Model):
    id = fields.IntField(pk=True)
    token = fields.CharField(max_length=255, unique=True)
    user = fields.ForeignKeyField("models.User", related_name="refresh_tokens")
    expires_at = fields.DatetimeField()


class Containers(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="containers")
    container_id = fields.CharField(max_length=255)
    port = fields.IntField()
    status = fields.CharField(max_length=50, default="running")
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "containers"
        
class ApiKey(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="api_keys", on_delete=fields.CASCADE)
    exchange = fields.CharField(max_length=50)
    api_key = fields.TextField()
    secret_key = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "api_keys"

# Pydantic-схемы для ApiKey
ApiKey_Pydantic = pydantic_model_creator(ApiKey, name="ApiKey")
ApiKeyIn_Pydantic = pydantic_model_creator(ApiKey, name="ApiKeyIn", exclude_readonly=True)


class Bot(Model):
    id = fields.IntField(pk=True)  # Уникальный идентификатор бота
    user = fields.ForeignKeyField("models.User", related_name="bots", on_delete=fields.CASCADE)  # Ссылка на пользователя
    name = fields.CharField(max_length=255)  # Название бота
    strategy = fields.CharField(max_length=255)  # Стратегия, используемая ботом
    status = fields.CharField(max_length=50, default="inactive")  # Статус бота (активен/неактивен и т.д.)
    balance_used = fields.FloatField(default=0.0)  # Используемый баланс (по дефолту 0)
    indicators = fields.JSONField(default=[])  # Индикаторы (по дефолту пустой список)
    profit = fields.FloatField(default=0.0)  # Прибыль (по дефолту 0)
    created_at = fields.DatetimeField(auto_now_add=True)  # Дата и время создания
    updated_at = fields.DatetimeField(auto_now=True)  # Дата и время последнего обновления

    class Meta:
        table = "bots"

# Pydantic-схемы для Bot
Bot_Pydantic = pydantic_model_creator(Bot, name="Bot")
BotIn_Pydantic = pydantic_model_creator(Bot, name="BotIn", exclude_readonly=True)
