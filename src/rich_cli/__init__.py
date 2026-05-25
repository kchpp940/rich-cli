from __future__ import annotations

import re
from pathlib import Path

try:
    from importlib.metadata import version as _metadata_version
except ImportError:
    from importlib_metadata import version as _metadata_version  # type: ignore[no-redef]


def get_version() -> str:
    """Return the rich-cli version.

    Resolution order:
    1. Installed package metadata (via ``importlib.metadata``) — covers
       normal ``pip install`` / ``pipx`` / editable installs.
    2. ``pyproject.toml`` in the source tree — covers running from source
       without installation (e.g. ``python -m rich_cli`` from a checkout).

    Raises:
        RuntimeError: If the version cannot be determined from either source.
            This indicates a broken installation or a missing ``pyproject.toml``.
    """
    try:
        return _metadata_version("rich-cli")
    except Exception:
        pass

    pyproject = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    if pyproject.is_file():
        try:
            match = re.search(
                r'^version\s*=\s*"([^"]+)"',
                pyproject.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
            if match:
                return match.group(1)
        except Exception:
            pass

    raise RuntimeError(
        "Unable to determine rich-cli version. "
        "The package metadata is missing and pyproject.toml could not be read "
        f"from {pyproject}. Reinstall the package or run from a valid source checkout."
    )


def __getattr__(name):
    if name == "__version__":
        return get_version()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
