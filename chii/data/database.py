from pathlib import Path

from peewee import DatabaseProxy, SqliteDatabase

from chii import Config

default_database_name = "chii.dev.db" if Config.TEST_MODE else "chii.db"
database_path = Path(Config.DB_PATH) if (Config.USE_DB_PATH and Config.DB_PATH) else Path(__file__).parent / "files" / default_database_name

database_proxy = DatabaseProxy()
database = SqliteDatabase(str(database_path), pragmas={"foreign_keys": 1})


class Database:
    @classmethod
    def initialize(cls) -> None:
        database_proxy.initialize(database)

    @classmethod
    def create_tables(cls) -> None:
        from chii.data import (
            AniListTracker,
            AniListUser,
            BotSettings,
            BotUser,
            WaniKaniStats,
            WaniKaniUser,
        )

        # Table creation order matters.
        #
        # Peewee creates foreign-key constraints, so it's good practice to
        # create parent tables before child tables.
        database.create_tables(
            [
                BotUser,
                BotSettings,
                AniListUser,
                AniListTracker,
                WaniKaniUser,
                WaniKaniStats,
            ]
        )
