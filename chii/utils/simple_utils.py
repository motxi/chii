import typing

from discord import TextChannel

from chii.data import BotSettings

if typing.TYPE_CHECKING:
    from discord.ext import commands


class SimpleUtils:
    @staticmethod
    def get_bot_settings() -> BotSettings:
        bot_settings: BotSettings
        bot_settings, _ = BotSettings.get_or_create(id=1)

        return bot_settings

    @staticmethod
    def get_channel(bot: commands.Bot, channel_id: int | None) -> TextChannel | None:
        if not channel_id:
            return None

        channel = bot.get_channel(channel_id)

        if not isinstance(channel, TextChannel):
            return None

        return channel
