from tortoise import fields
from tortoise.models import Model
from decimal import Decimal                # пригодится в коде




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

# Оплата.
class Payment(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="payments", on_delete=fields.CASCADE)
    yookassa_id = fields.CharField(max_length=50)
    paid = fields.BooleanField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "payments"

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
    port = fields.IntField()
    container_id = fields.CharField(max_length=255)
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



# ========  НОВОЕ ============================================================

# …app/models.py
class Trade(Model):
    id = fields.IntField(pk=True)

    bot_info = fields.ForeignKeyField(          # ← вместо Bot
        "models.BotInfo",
        related_name="trades",
        on_delete=fields.CASCADE,
    )

    pair         = fields.CharField(max_length=32)
    stake_amount = fields.DecimalField(max_digits=20, decimal_places=8)
    open_date    = fields.DatetimeField()
    close_date   = fields.DatetimeField()
    profit_abs   = fields.DecimalField(max_digits=20, decimal_places=8)
    profit_ratio = fields.DecimalField(max_digits=12, decimal_places=6)
    trade_duration = fields.IntField()
    exit_reason  = fields.CharField(max_length=64, null=True)
    is_short     = fields.BooleanField()

    class Meta:
        table = "trades"
        unique_together = (("bot_info", "open_date", "pair"),)
        indexes = (("bot_info_id", "open_date"),)


class DailyBreakdown(Model):
    id = fields.IntField(pk=True)

    bot_info = fields.ForeignKeyField(          # ← вместо Bot
        "models.BotInfo",
        related_name="daily_breakdowns",
        on_delete=fields.CASCADE,
    )

    date          = fields.DateField()
    profit_abs    = fields.DecimalField(max_digits=20, decimal_places=8)
    wins          = fields.IntField()
    losses        = fields.IntField()
    trades_count  = fields.IntField()
    profit_factor = fields.DecimalField(max_digits=14, decimal_places=6)

    class Meta:
        table = "daily_breakdowns"
        unique_together = (("bot_info", "date"),)
        indexes = (("bot_info_id", "date"),)