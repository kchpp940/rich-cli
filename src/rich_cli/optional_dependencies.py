from typing import Dict, Callable, Optional, NoReturn

EXTRAS: Dict[str, Dict[str, str]] = {
    "http": {
        "package": "requests",
        "description": "URL support (http/https)",
        "install_command": "pip install rich-cli[http]",
    },
    "pager": {
        "package": "textual",
        "description": "Interactive pager (--pager)",
        "install_command": "pip install rich-cli[pager]",
    },
    "rst": {
        "package": "rich_rst",
        "description": "RST rendering (--rst)",
        "install_command": "pip install rich-cli[rst]",
    },
}


class MissingOptionalDependencyError(Exception):
    def __init__(self, extra_name: str):
        if extra_name not in EXTRAS:
            raise ValueError(f"Unknown extra: {extra_name!r}")
        self.extra_name = extra_name
        self.extra = EXTRAS[extra_name]
        super().__init__(
            f"missing optional dependency {self.extra['package']!r} "
            f"for {self.extra['description']}. "
            f"Install with: {self.extra['install_command']}"
        )


def require_extra(extra_name: str) -> None:
    if extra_name not in EXTRAS:
        raise ValueError(f"Unknown extra: {extra_name!r}")

    extra = EXTRAS[extra_name]
    package = extra["package"]

    try:
        __import__(package)
    except ImportError:
        raise MissingOptionalDependencyError(extra_name) from None


def require_extra_or_exit(
    extra_name: str,
    exit_func: Callable[[str], NoReturn],
) -> None:
    try:
        require_extra(extra_name)
    except MissingOptionalDependencyError as error:
        exit_func(str(error))
