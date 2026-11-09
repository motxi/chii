from typing import TYPE_CHECKING

import aiosqlite

from chii.config import Config

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any


class Database:
    def __init__(self, database: str = "chii.db") -> None:
        self.database = str(Config.DATA_PATH / "db" / database)
        self._connection: aiosqlite.Connection | None = None

        (Config.DATA_PATH / "db").mkdir(parents=True, exist_ok=True)

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            _ = "Database is not connected. Call connect() first."
            raise RuntimeError(_)

        return self._connection

    async def connect(self) -> None:
        if self._connection is not None:
            return

        self._connection = await aiosqlite.connect(self.database)
        self._connection.row_factory = aiosqlite.Row

        schema = (Config.DATA_PATH / "schema.sql").read_text(encoding="utf-8")

        await self._connection.executescript(schema)
        await self._connection.commit()

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()

            self._connection = None

    async def execute(self, query: str, params: Sequence[Any] = ()) -> bool:
        async with self.connection.execute(query, params) as cursor:
            changed = cursor.rowcount > 0

        await self.connection.commit()

        return changed

    async def fetch(self, query: str, params: Sequence[Any] = ()) -> aiosqlite.Row | None:
        async with self.connection.execute(query, params) as cursor:
            return await cursor.fetchone() or None
