from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from discord import Interaction


async def reply(interaction: Interaction, content: str, **params) -> None:
    params.setdefault("ephemeral", True)

    if interaction.response.is_done():
        await interaction.followup.send(content, **params)
    else:
        await interaction.response.send_message(content, **params)
