from tortoise import fields
from tortoise.models import Model

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

