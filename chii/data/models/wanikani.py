from peewee import CharField, DateTimeField, ForeignKeyField, IntegerField

from chii.data.models.base import BaseModel
from chii.data.models.bot import BotUser


class WaniKaniAuth(BaseModel):
    bot_user = ForeignKeyField(
        BotUser,
        backref="wanikani_authorization",
        unique=True,
        on_delete="CASCADE",
    )

    authorized_by = IntegerField()

    class Meta:
        table_name = "wanikani_authorization"


class WaniKaniUser(BaseModel):
    bot_user = ForeignKeyField(
        BotUser,
        backref="wanikani_user",
        unique=True,
        on_delete="CASCADE",
    )

    # WaniKani user IDs are UUIDs, not integers.
    wanikani_id = CharField(primary_key=True)
    username = CharField()

    api_token = CharField()

    class Meta:
        table_name = "wanikani_user"


class WaniKaniStats(BaseModel):
    wanikani_user = ForeignKeyField(
        WaniKaniUser,
        unique=True,
        backref="stats",
        on_delete="CASCADE",
    )

    last_message_id = IntegerField(null=True)

    review_current_streak = IntegerField(default=0)
    review_longest_streak = IntegerField(default=0)

    total_reviews = IntegerField(default=0)

    # Cursor for the hourly task, tracking what's already been notified about.
    # Separate from `last_review_at`, which the daily task owns.
    last_review_notified_at = DateTimeField(null=True)
    last_review_at = DateTimeField(null=True)

    lesson_current_streak = IntegerField(default=0)
    lesson_longest_streak = IntegerField(default=0)

    total_lessons = IntegerField(default=0)

    last_lesson_notified_at = DateTimeField(null=True)
    last_lesson_at = DateTimeField(null=True)

    class Meta:
        table_name = "wanikani_stats"
