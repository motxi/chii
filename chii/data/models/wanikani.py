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

    # Message IDs are tracked separately per task, since the hourly update and
    # the daily summary are distinct messages that shouldn't delete each other.
    last_update_message_id = IntegerField(null=True)
    last_daily_message_id = IntegerField(null=True)

    current_streak = IntegerField(default=0)
    longest_streak = IntegerField(default=0)

    # -------
    # Reviews
    # -------

    total_reviews = IntegerField(default=0)

    # Snapshot of `total_reviews` as of the last daily summary, so that task can
    # derive "reviews done today" (total_reviews - total_reviews_day_start)
    # without re-querying the WaniKani API.
    total_reviews_day_start = IntegerField(default=0)

    # Cursor tracking what's already been notified about by the hourly task.
    last_review_notified_at = DateTimeField(null=True)

    # Kept up to date by the hourly task (whenever new reviews are found) but it
    # is left separate. It's read-only for the daily task, which uses it to
    # recap the day rather than to decide what's new.
    last_review_at = DateTimeField(null=True)

    # -------
    # Lessons
    # -------

    total_lessons = IntegerField(default=0)
    total_lessons_day_start = IntegerField(default=0)
    last_lesson_notified_at = DateTimeField(null=True)
    last_lesson_at = DateTimeField(null=True)

    class Meta:
        table_name = "wanikani_stats"
