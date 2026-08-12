import os
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Callable


class EnvParser:
    @staticmethod
    def read_env[T](cast: Callable[[str], T], key: str) -> T:
        try:
            value = os.environ[key]
            return EnvParser._safe_cast(cast, value)

        except KeyError as e:
            message = f"Missing required environment variable: {key}"
            raise RuntimeError(message) from e

        except ValueError as e:
            message = f"Invalid value for environment variable {key}: {e}"
            raise RuntimeError(message) from e

    @staticmethod
    def read_env_nullable[T](cast: Callable[[str], T], key: str) -> T | None:
        if value := os.environ.get(key):
            return EnvParser._safe_cast(cast, value)

        return None

    @staticmethod
    def _parse_bool(value: str) -> bool:
        value = value.strip().lower()

        if value in ("1", "true", "yes", "on"):
            return True
        if value in ("0", "false", "no", "off"):
            return False

        message = f"Invalid boolean found in config: {value or None}"
        raise ValueError(message)

    @staticmethod
    def _safe_cast[T](cast: Callable[[str], T], value: str) -> T:

        if cast is bool:
            return typing.cast("T", EnvParser._parse_bool(value))

        return cast(value)
