import logging
import pathlib

import discord
from discord.ext import commands

from chii import Config
from chii.data import Database
from chii.utils import LogHandler

logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=Config.BOT_PREFIX, owner_id=Config.BOT_OWNER, intents=intents)


@bot.event
async def on_ready() -> None:
    if bot.user:
        logger.info(f"Logged in as {bot.user} ({bot.user.id})")
    else:
        logger.error("Could not get bot user")

    if Config.TEST_MODE and Config.TEST_GUILD:
        logger.warning("Testing mode is enabled")

        guild = discord.Object(id=Config.TEST_GUILD)

        bot.tree.copy_global_to(guild=guild)

        logger.info(f"Syncing application commands to guild {Config.TEST_GUILD}")
        await bot.tree.sync(guild=guild)
        logger.info(f"Synced application commands to guild {Config.TEST_GUILD}")
    else:
        logger.info("Syncing application commands globally")
        await bot.tree.sync()
        logger.info("Synced application commands globally")

    logger.info("Bot is ready!")


async def load_cogs() -> None:
    logger.info("Loading cogs")
    cogs = pathlib.Path(__file__).parent.resolve() / "cogs"

    for cog in cogs.rglob("*.py"):
        if cog.name == "__init__.py":
            continue

        logger.info(f"Loading Cog: {cog.name}")
        await bot.load_extension(f"chii.cogs.{cog.stem}")
        logger.info(f"Loaded Cog: {cog.name}")

    logger.info("Cogs loaded!")


async def main() -> None:
    LogHandler.initialize_logger()

    logger.info("Starting bot main loop")

    async with bot:
        await load_cogs()

        Database.initialize()
        Database.create_tables()

        logger.info("Starting bot")

        try:
            await bot.start(Config.BOT_TOKEN, reconnect=True)
        except Exception:
            logger.exception("Bot crashed")
            raise

        # Everything below this line is essentially no-op.
