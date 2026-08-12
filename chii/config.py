import dotenv

from chii.utils import EnvParser

dotenv.load_dotenv()


class Config:
    BOT_TOKEN = EnvParser.read_env(str, "BOT_TOKEN")
    BOT_PREFIX = EnvParser.read_env_nullable(str, "BOT_PREFIX") or "!"
    BOT_OWNER = EnvParser.read_env_nullable(int, "BOT_OWNER")

    COMMAND_TIMEOUT_SECONDS = EnvParser.read_env_nullable(float, "COMMAND_TIMEOUT_SECONDS") or 10.0
    ANILIST_UPDATE_LOOP_TIME_SECONDS = EnvParser.read_env_nullable(float, "ANILIST_CHECK_LOOP_TIME") or 600.0

    ENABLE_CONSOLE_LOGGING = EnvParser.read_env_nullable(bool, "ENABLE_CONSOLE_LOGGING") or False
    LOGS_FORMAT = EnvParser.read_env_nullable(str, "LOGS_FORMAT") or "%(asctime)s %(levelname)s %(name)s @%(funcName)s: %(message)s"
    LOGS_MAX_SIZE = EnvParser.read_env(int, "LOGS_MAX_SIZE") * 1024 * 1024

    TEST_MODE = EnvParser.read_env_nullable(bool, "TEST_MODE") or False
    TEST_GUILD = EnvParser.read_env_nullable(int, "TEST_GUILD")

    USE_DB_PATH = EnvParser.read_env_nullable(bool, "USE_DB_PATH") or False
    DB_PATH = EnvParser.read_env_nullable(str, "DB_PATH")
