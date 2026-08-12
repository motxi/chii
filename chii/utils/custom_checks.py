import typing

if typing.TYPE_CHECKING:
    from discord import Interaction

from chii import Config


class CustomChecks:
    @staticmethod
    def is_bot_owner(interaction: Interaction) -> bool:
        return interaction.user.id == Config.BOT_OWNER
