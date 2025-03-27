from tortoise import fields
from tortoise.models import Model



# Пользователь.
class User(Model):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True)
    refresh_token = fields.CharField(max_length=255, unique=True)
    refresh_token_expires_at = fields.DatetimeField()
    is_trial = fields.BooleanField()
    subscription_expires_at = fields.DatetimeField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"

# Api ключ.
class ApiKey(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50)
    user = fields.ForeignKeyField("models.User", related_name="api_keys", on_delete=fields.CASCADE)
    exchange = fields.CharField(max_length=50)
    api_key = fields.TextField()
    secret_key = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "api_keys"

# Бот.
class Bot(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)  # Название бота (для freqtrade api)
    password = fields.CharField(max_length=255) # Пароль (для freqtrade api)
    status = fields.CharField(max_length=50, default="inactive")  # Статус бота (активен/неактивен и т.д.)
    available_capital = fields.FloatField() # Доступный капитал.
    is_dry_run = fields.BooleanField() # Демо или реальный запуск.
    user = fields.ForeignKeyField("models.User", related_name="bots", on_delete=fields.CASCADE)
    api_key = fields.ForeignKeyField("models.ApiKey", related_name="bots", on_delete=fields.CASCADE) #TODO подумать про это поле
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "bots"

# Одноразовый пароль для проверки email.
class OTPCode(Model):
    id = fields.IntField(pk=True)
    email = fields.CharField(max_length=255, unique=True)
    otp = fields.CharField(max_length=6)  # 6-значный одноразовый пароль
    expires_at = fields.DatetimeField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "otp_codes"

# Информация о ботах (для каталога).
class BotInfo(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255) 
    type = fields.CharField(max_length=50) # Spot/Futures.
    pnl = fields.FloatField() # PNL в год.
    crypto_pairs = fields.TextField() # Криптовалютные пары.
    description = fields.TextField() # Описание.
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "bots_info"
