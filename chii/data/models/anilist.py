from peewee import BooleanField, CharField, CompositeKey, DateTimeField, ForeignKeyField, IntegerField

from chii.data.models.base import BaseModel
from chii.data.models.bot import BotUser


class AniListUser(BaseModel):
    bot_user = ForeignKeyField(
        BotUser,
        backref="anilist_user",
        unique=True,
        on_delete="CASCADE",
    )

    anilist_id = IntegerField(primary_key=True)
    username = CharField()

    synced = BooleanField(default=False)

    last_message_id = IntegerField(null=True)

    last_activity_id = IntegerField(null=True)
    last_activity_at = DateTimeField(null=True)

    current_streak = IntegerField(default=0)
    longest_streak = IntegerField(default=0)

    class Meta:
        table_name = "anilist_user"


class AniListTracker(BaseModel):
    anilist_user = ForeignKeyField(
        AniListUser,
        backref="tracked_media",
        on_delete="CASCADE",
    )

    media_id = IntegerField()

    type = CharField()
    title = CharField()
    progress = IntegerField(default=0)

    class Meta:
        table_name = "anilist_tracker"
        primary_key = CompositeKey("anilist_user", "media_id")
