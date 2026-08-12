import importlib
import typing

if typing.TYPE_CHECKING:
    from chii.data import AniListUser

    from .custom_checks import CustomChecks
    from .env_parser import EnvParser
    from .log_handler import Logger, LogHandler
    from .simple_utils import SimpleUtils

type T_Json = dict[str, typing.Any]
type T_Activity_Batch = tuple[T_Json | None, dict[str, AniListUser]]

__all__ = [
    "CustomChecks",
    "EnvParser",
    "LogHandler",
    "Logger",
    "SimpleUtils",
]


def __getattr__(name: str) -> object:
    lazy_attributes = {
        "CustomChecks": ".custom_checks",
        "EnvParser": ".env_parser",
        "Logger": ".log_handler",
        "LogHandler": ".log_handler",
        "SimpleUtils": ".simple_utils",
    }

    module_name = lazy_attributes.get(name)

    if module_name is None:
        message = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(message)

    module = importlib.import_module(module_name, __name__)
    value = getattr(module, name)

    globals()[name] = value

    return value
