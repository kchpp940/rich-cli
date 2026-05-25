import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
CONFIG_DIR = XDG_CONFIG_HOME / "rich-cli"
PROFILES_FILE = CONFIG_DIR / "config.toml"


PARAM_TO_CLI = {
    "theme": ("--theme", str),
    "hyperlinks": ("--hyperlinks", bool),
    "line_numbers": ("--line-numbers", bool),
    "guides": ("--guides", bool),
    "no_wrap": ("--no-wrap", bool),
    "ipynb_cell_type": ("--ipynb-cell-type", str),
    "ipynb_cell_range": ("--ipynb-cell-range", str),
    "ipynb_no_output": ("--ipynb-no-output", bool),
}


CONFIGURABLE_PARAMS = set(PARAM_TO_CLI.keys())


def _check_tomllib() -> None:
    if tomllib is None:
        from .__main__ import on_error
        on_error(
            "TOML support is required for profiles. "
            "Install with: pip install tomli (Python < 3.11) or use Python >= 3.11"
        )


def load_config() -> Dict[str, Any]:
    """Load the configuration file.

    Returns:
        Dictionary with the full config data, empty dict if no config file exists.
    """
    _check_tomllib()

    if not PROFILES_FILE.exists():
        return {}

    try:
        with open(PROFILES_FILE, "rb") as f:
            return tomllib.load(f)
    except Exception as error:
        from .__main__ import on_error
        on_error(f"failed to read config file {PROFILES_FILE}: {error}")

    return {}


def get_profiles() -> Dict[str, Dict[str, Any]]:
    """Get all profiles from the config file.

    Returns:
        Dictionary mapping profile names to their parameter dictionaries.
    """
    config = load_config()
    profiles = config.get("profiles", {})
    return profiles


def get_profile(name: str) -> Optional[Dict[str, Any]]:
    """Get a single profile by name.

    Args:
        name: Profile name to look up.

    Returns:
        Filtered profile parameter dictionary, or None if not found.
    """
    profiles = get_profiles()
    profile = profiles.get(name)
    if profile is None:
        return None

    filtered = {k: v for k, v in profile.items() if k in CONFIGURABLE_PARAMS}
    return filtered


def profile_to_cli_args(profile: Dict[str, Any]) -> List[str]:
    """Convert a profile's parameters to equivalent CLI arguments.

    Args:
        profile: Profile parameter dictionary.

    Returns:
        List of CLI argument strings.
    """
    args: List[str] = []
    for key, value in profile.items():
        if key not in PARAM_TO_CLI:
            continue
        flag, param_type = PARAM_TO_CLI[key]
        if param_type is bool:
            if value:
                args.append(flag)
        else:
            args.extend([flag, str(value)])
    return args


def format_profiles_list() -> str:
    """Format all profiles as a readable string.

    Returns:
        Formatted string with all profiles and their parameters.
    """
    profiles = get_profiles()

    if not profiles:
        return (
            "No profiles found.\n"
            f"Create one by editing: {PROFILES_FILE}\n\n"
            "Example:\n"
            "[profiles.my-profile]\n"
            'theme = "dracula"\n'
            "line_numbers = true"
        )

    lines = []
    lines.append(f"Config file: {PROFILES_FILE}")
    lines.append("")
    lines.append("Available profiles:")
    lines.append("")

    for name in sorted(profiles.keys()):
        profile = profiles[name]
        lines.append(f"  [bold]{name}[/bold]")
        for key in sorted(profile.keys()):
            if key in CONFIGURABLE_PARAMS:
                value = profile[key]
                lines.append(f"    {key} = {value!r}")
        lines.append("")

    return "\n".join(lines)
