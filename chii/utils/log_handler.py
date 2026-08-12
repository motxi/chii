import logging
import logging.handlers
import pathlib
import sys

from chii import Config

LOGS_PATH = pathlib.Path(__file__).parents[1].resolve() / "logs"

CHII_LOGS_PATH = LOGS_PATH / "chii"
DISCORD_LOGS_PATH = LOGS_PATH / "discord"


class Logger:
    def __init_subclass__(cls) -> None:
        cls.logger = logging.getLogger(f"{cls.__module__}.{cls.__qualname__}")


class LogHandler(Logger):
    @classmethod
    def initialize_logger(cls) -> None:
        cls.logger.debug("Initializing logger")

        for path in LOGS_PATH.rglob("*.log"):
            path.unlink(missing_ok=True)

        for path in (LOGS_PATH, CHII_LOGS_PATH, DISCORD_LOGS_PATH):
            path.mkdir(parents=True, exist_ok=True)

            if Config.ENABLE_CONSOLE_LOGGING:
                cls.console_handler = logging.StreamHandler(sys.stdout)
            else:
                cls.console_handler = None

        formatter = logging.Formatter(Config.LOGS_FORMAT)

        chii_handler = logging.handlers.RotatingFileHandler(
            filename=CHII_LOGS_PATH / "chii.log",
            maxBytes=Config.LOGS_MAX_SIZE,
            backupCount=3,
            mode="w",
        )

        discord_base_file_handler = logging.handlers.RotatingFileHandler(
            filename=DISCORD_LOGS_PATH / "discord_base.log",
            maxBytes=Config.LOGS_MAX_SIZE,
            backupCount=3,
            encoding="utf-8",
            mode="w",
        )

        discord_http_file_handler = logging.handlers.RotatingFileHandler(
            filename=DISCORD_LOGS_PATH / "discord_http.log",
            maxBytes=Config.LOGS_MAX_SIZE,
            backupCount=3,
            encoding="utf-8",
            mode="w",
        )

        # Only records from `chii.*` loggers should reach chii.log and the
        # console.
        #
        # Other libraries logging to the root logger (e.g. via# `basicConfig`)
        # would otherwise leak in.
        chii_only_filter = logging.Filter(name="chii")

        chii_handler.addFilter(chii_only_filter)
        chii_handler.setFormatter(formatter)

        discord_base_file_handler.setFormatter(formatter)
        discord_http_file_handler.setFormatter(formatter)

        root_logger = logging.getLogger()
        discord_base_logger = logging.getLogger("discord")
        discord_http_logger = logging.getLogger("discord.http")

        # Prevent discord logs from appearing in the main log files.
        discord_base_logger.propagate = False
        discord_http_logger.propagate = False

        root_logger.setLevel(logging.DEBUG)
        discord_base_logger.setLevel(logging.INFO)
        discord_http_logger.setLevel(logging.INFO)

        root_logger.addHandler(chii_handler)
        discord_base_logger.addHandler(discord_base_file_handler)
        discord_http_logger.addHandler(discord_http_file_handler)

        if cls.console_handler:
            cls.console_handler.addFilter(chii_only_filter)
            cls.console_handler.setFormatter(formatter)

            root_logger.addHandler(cls.console_handler)

        cls.logger.info(f"{cls.__class__.__name__} initialized")
