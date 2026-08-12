from discord import Activity, ActivityType, Interaction, app_commands
from discord.ext import commands

from chii import Config
from chii.utils import CustomChecks, Logger


class ClientCog(Logger, commands.GroupCog, group_name="client"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot

    @app_commands.command(name="activity", description="Set the bot's activity with a custom message.")
    @app_commands.describe(activity_type="The type of the activity.", activity_message="The activity status message.")
    @app_commands.check(predicate=CustomChecks.is_bot_owner)
    async def client_activity(self, interaction: Interaction, activity_type: str, activity_message: str) -> None:
        if interaction.user.id != Config.BOT_OWNER:
            await interaction.response.send_message("You don't have permissions to use this command.", ephemeral=True)
            return

        activity_type = activity_type.lower()

        match activity_type:
            case "playing":
                activity = Activity(type=ActivityType.playing, name=activity_message)
            case "watching":
                activity = Activity(type=ActivityType.playing, name=activity_message)
            case "listening":
                activity = Activity(type=ActivityType.listening, name=activity_message)
            case _:
                await interaction.response.send_message("Invalid activity type.", ephemeral=True)
                return

        await self.bot.change_presence(activity=activity)
        await interaction.response.send_message(f"Status changed to: {activity_type.title()} **{activity_message}**.")

        self.logger.info(f"Bot's status has been changed to: {activity_type.title()} {activity_message}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ClientCog(bot))
