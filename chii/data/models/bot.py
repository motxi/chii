from peewee import CharField, IntegerField

from chii.data.models.base import BaseModel


class BotUser(BaseModel):
    discord_id = IntegerField(primary_key=True)
    username = CharField()

    class Meta:
        table_name = "bot_user"


class BotSettings(BaseModel):
    anilist_channel_id = IntegerField(null=True)
    wanikani_channel_id = IntegerField(null=True)

    class Meta:
        table_name = "bot_settings"
