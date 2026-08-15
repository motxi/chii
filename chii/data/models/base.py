from datetime import datetime

from peewee import DateTimeField, Model

from chii.data.database import database_proxy


class BaseModel(Model):
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = database_proxy

        # Only fields explicitly assigned in-memory are written on `save()`, so
        # two tasks that load, mutate, and save the same row concurrently don't
        # clobber each other's changes to unrelated fields.
        only_save_dirty = True
