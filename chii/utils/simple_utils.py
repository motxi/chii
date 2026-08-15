import asyncio
import contextlib
import typing

from discord import Embed, TextChannel

from chii.data import BotSettings

if typing.TYPE_CHECKING:
    import logging

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

    @staticmethod
    async def replace_tracked_message(logger: logging.Logger, channel: TextChannel, old_message_id: int | None, embed: Embed, description: str) -> int:
        logger.debug(f"Sending new {description} message to #{channel.name}")

        async def delete_old() -> None:
            if not old_message_id:
                return

            logger.debug(f"Deleting previous {description} message {old_message_id}")

            with contextlib.suppress(Exception):
                await channel.get_partial_message(old_message_id).delete()
                logger.debug(f"Deleted previous {description} message {old_message_id}")

        _, message = await asyncio.gather(delete_old(), channel.send(embed=embed))

        logger.debug(f"Sent new {description} message {message.id} to #{channel.name}")

        return message.id
