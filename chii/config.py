import os
from pathlib import Path

from dotenv import dotenv_values

_env = {
    **os.environ,
    **dotenv_values(Path(__file__).parent.parent.resolve() / ".env"),
}

_bot_token = _env.get("BOT_TOKEN")
_bot_owner = _env.get("BOT_OWNER")

_test_mode = _env.get("TEST_MODE")
_test_guild = _env.get("TEST_GUILD")

if not _bot_token:
    _ = 'The `BOT_TOKEN` key is missing from the ".env" file'
    raise RuntimeError(_)


class Config:
    BOT_TOKEN: str = _bot_token
    BOT_OWNER: int | None = int(_bot_owner) if _bot_owner else None

    TEST_MODE: bool = (_test_mode or "false").lower() in ("1", "true", "yes")
    TEST_GUILD: int | None = int(_test_guild) if _test_guild else None

    DATA_PATH = Path(__file__).parent.resolve() / "data"
