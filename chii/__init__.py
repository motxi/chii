import pathlib

import discord
from discord.ext import commands

from chii.config import Config
from chii.database import Database


class Chii(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()

        super().__init__(
            owner_id=Config.BOT_OWNER,
            command_prefix="!",
            intents=intents,
        )

        self.database = Database()

    async def on_ready(self) -> None:
        if self.user:
            print(f"Logged in as {self.user.id} ({self.user})")
        else:
            print("Could not get bot user")

        if Config.TEST_MODE and Config.TEST_GUILD:
            print("Testing mode is enabled")

            guild = discord.Object(id=Config.TEST_GUILD)

            self.tree.copy_global_to(guild=guild)

            await self.tree.sync(guild=guild)
            print(f"Synced application commands to guild {Config.TEST_GUILD}")
        else:
            await self.tree.sync()
            print("Synced application commands globally")

        print("Bot is ready!")

    async def setup_hook(self) -> None:
        await self.database.connect()
        await self.load_cogs()

    async def load_cogs(self) -> None:
        cogs = pathlib.Path(__file__).parent.resolve() / "cogs"

        for cog in cogs.rglob("*.py"):
            if cog.name == "__init__.py":
                continue

            await self.load_extension(f"chii.cogs.{cog.stem}")
            print("Extensions loaded")

    async def close(self) -> None:
        await self.database.close()
        await super().close()


async def main() -> None:
    async with Chii() as bot:
        print("Starting bot")
        await bot.start(Config.BOT_TOKEN, reconnect=True)
