from datetime import datetime

from peewee import DateTimeField, Model

from chii.data.database import database_proxy


class BaseModel(Model):
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = database_proxy
