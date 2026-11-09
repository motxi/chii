from typing import TYPE_CHECKING

import discord
from discord import Interaction, app_commands
from discord.ext import commands

from chii.utils import reply

if TYPE_CHECKING:
    from chii import Chii


class CustomRoles(commands.GroupCog, name="role"):
    def __init__(self, bot: Chii) -> None:
        self.bot = bot

        super().__init__()

    @app_commands.command(name="set", description="Create or edit your custom role")
    @app_commands.describe(name="Your role name", color="Your role color (hexadecimal)")
    @app_commands.guild_only()
    async def role_set(self, interaction: Interaction, name: str | None = None, color: str | None = None) -> None:
        guild = interaction.guild
        user = interaction.user

        if guild is None or not isinstance(user, discord.Member):
            return

        row = await self.bot.database.fetch("SELECT role_id FROM custom_roles WHERE user_id = ?", (user.id,))
        role = guild.get_role(row["role_id"]) if row else None
        created = role is None

        # Role doesn't exist.
        if role is None:
            if name is None or color is None:
                await reply(interaction, "You don't have a custom role yet. Provide both a name and a color")
                return

            role_name = name
            hex_color = color.lstrip("#")

        # Role exists.
        else:
            if name is None and color is None:
                await reply(interaction, "Provide a new name and/or color to change your role")
                return

            role_name = name if name is not None else role.name
            hex_color = color.lstrip("#") if color is not None else f"{role.color.value:06x}"

        try:
            role_color = discord.Color(int(hex_color, 16))
        except ValueError:
            await reply(interaction, "Invalid color. Use a valid hexadecimal code like `#ff8800`")
            return

        role_position = max(1, guild.me.top_role.position - 1)

        await interaction.response.defer(ephemeral=True)

        try:
            # Edit the role if it already exists.
            if role:
                await role.edit(
                    name=role_name,
                    color=role_color,
                    reason=f"Custom role updated by {user}",
                )

            # Create a new one if not.
            else:
                role = await guild.create_role(
                    name=role_name,
                    color=role_color,
                    reason=f"Custom role for {user}",
                )

            await user.add_roles(role)
            await role.edit(position=role_position)

        except discord.Forbidden:
            await reply(interaction, "I don't have permission to manage roles")
            return

        except discord.HTTPException:
            await reply(interaction, "Something went wrong while saving your role")
            return

        await self.bot.database.execute(
            """
            INSERT INTO custom_roles (user_id, role_id, role_name, role_color)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                role_id = excluded.role_id,
                role_name = excluded.role_name,
                role_color = excluded.role_color
            """,
            (user.id, role.id, role_name, f"#{hex_color.lower()}"),
        )

        status = "Created" if created else "Updated"

        await reply(interaction, f"{status} your custom role: {role.mention}")


async def setup(bot: Chii) -> None:
    await bot.add_cog(CustomRoles(bot))
