"""
Configuration and profile management for rich-cli.

Supports reading profiles from TOML configuration files in the following locations
(searched in order, later files override earlier ones):

1. System-wide: /etc/rich-cli/config.toml (Linux/macOS)
2. User-wide: ~/.config/rich-cli/config.toml (Linux/macOS)
           or ~/.rich-cli.toml (cross-platform)
3. Project-local: .rich-cli.toml in current working directory

Profiles are defined under [profiles.<name>] sections in the TOML file.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

import click

if TYPE_CHECKING:
    pass

try:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    HAS_TOML = True
except ImportError:
    HAS_TOML = False


PROFILE_BOOL_KEYS = {
    "print",
    "syntax",
    "rule",
    "json",
    "markdown",
    "rst",
    "csv",
    "ipynb",
    "inspect",
    "emoji",
    "left",
    "right",
    "center",
    "text_left",
    "text_right",
    "text_center",
    "text_full",
    "soft",
    "expand",
    "line_numbers",
    "guides",
    "hyperlinks",
    "no_wrap",
    "force_terminal",
    "pager",
}

PROFILE_INT_KEYS = {
    "width",
    "max_width",
    "head",
    "tail",
}

PROFILE_STR_KEYS = {
    "style",
    "rule_style",
    "rule_char",
    "padding",
    "panel",
    "panel_style",
    "theme",
    "lexer",
    "title",
    "caption",
    "export_html",
    "export_svg",
}

ALL_PROFILE_KEYS = PROFILE_BOOL_KEYS | PROFILE_INT_KEYS | PROFILE_STR_KEYS

CLICK_PARAM_TO_PROFILE_KEY = {
    "_print": "print",
    "no_wrap": "no_wrap",
}

PROFILE_KEY_TO_CLICK_PARAM = {v: k for k, v in CLICK_PARAM_TO_PROFILE_KEY.items()}

def get_effective_params(
    profile: Optional[Profile],
    param_values: Dict[str, Any],
    param_sources: Dict[str, "click.core.ParameterSource"],
) -> Dict[str, Any]:
    """
    Compute effective parameters by merging profile defaults with CLI params.

    Uses Click's parameter source tracking to reliably determine if a parameter
    was explicitly provided by the user vs. coming from a default value.

    Only parameters with source DEFAULT or DEFAULT_MAP (i.e., not from
    command line or environment) can be overridden by profile values.

    Args:
        profile: The loaded profile (if any).
        param_values: Dictionary of parameter values from Click context.
        param_sources: Dictionary mapping param names to their ParameterSource.

    Returns:
        Dictionary with effective parameter values.
    """
    from click.core import ParameterSource

    effective = dict(param_values)

    if profile is None:
        return effective

    for key, value in profile.options.items():
        click_param = PROFILE_KEY_TO_CLICK_PARAM.get(key, key)

        if click_param not in param_sources:
            continue

        source = param_sources[click_param]

        if source in (ParameterSource.DEFAULT, ParameterSource.DEFAULT_MAP):
            effective[click_param] = value

    return effective


@dataclass
class Profile:
    """A named profile containing CLI parameter defaults."""

    name: str
    options: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get an option value by key."""
        return self.options.get(key, default)


@dataclass
class Config:
    """Loaded configuration containing all profiles."""

    profiles: Dict[str, Profile] = field(default_factory=dict)
    source_files: list[Path] = field(default_factory=list)

    def get_profile(self, name: str) -> Optional[Profile]:
        """Get a profile by name, returning None if not found."""
        return self.profiles.get(name)

    def list_profiles(self) -> list[str]:
        """Return a sorted list of available profile names."""
        return sorted(self.profiles.keys())


def _get_config_paths() -> list[Path]:
    """Return a list of potential config file paths in order of precedence."""
    paths: list[Path] = []

    if sys.platform != "win32":
        paths.append(Path("/etc/rich-cli/config.toml"))
        xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        paths.append(Path(xdg_config) / "rich-cli" / "config.toml")

    paths.append(Path.home() / ".rich-cli.toml")
    paths.append(Path.cwd() / ".rich-cli.toml")

    return paths


def _normalize_key(key: str) -> str:
    """Normalize a key from TOML (kebab-case) to profile key (snake_case)."""
    return key.replace("-", "_")


def _validate_and_convert(key: str, value: Any) -> Any:
    """Validate and convert a profile value to the expected type."""
    norm_key = _normalize_key(key)

    if norm_key not in ALL_PROFILE_KEYS:
        raise ValueError(f"Unknown profile option: '{key}'")

    if norm_key in PROFILE_BOOL_KEYS:
        if not isinstance(value, bool):
            raise TypeError(
                f"Profile option '{key}' must be a boolean, got {type(value).__name__}"
            )
    elif norm_key in PROFILE_INT_KEYS:
        if not isinstance(value, int):
            raise TypeError(
                f"Profile option '{key}' must be an integer, got {type(value).__name__}"
            )
    elif norm_key in PROFILE_STR_KEYS:
        if not isinstance(value, str):
            raise TypeError(
                f"Profile option '{key}' must be a string, got {type(value).__name__}"
            )

    return value


def _parse_profile_data(
    profile_name: str, profile_data: Dict[str, Any], source_file: Path
) -> Profile:
    """Parse raw TOML profile data into a Profile object."""
    options: Dict[str, Any] = {}
    errors: list[str] = []

    for key, value in profile_data.items():
        norm_key = _normalize_key(key)
        try:
            converted_value = _validate_and_convert(norm_key, value)
            options[norm_key] = converted_value
        except ValueError as exc:
            errors.append(
                f"Profile '{profile_name}' in {source_file}: "
                f"unknown option '{key}'. Use 'rich --list-profiles' to see valid options."
            )
        except TypeError as exc:
            errors.append(
                f"Profile '{profile_name}' in {source_file}: "
                f"invalid type for option '{key}': {exc}"
            )

    if errors:
        raise ValueError("\n".join(errors))

    return Profile(name=profile_name, options=options)


@dataclass
class ProfileLoadResult:
    """Result of parsing profiles from a config file."""

    profiles: Dict[str, Profile] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _parse_toml_config(content: str, source_file: Path) -> ProfileLoadResult:
    """Parse TOML content and extract profiles with per-profile error handling."""
    result = ProfileLoadResult()

    if not HAS_TOML:
        result.errors.append(
            "TOML support requires Python 3.11+ or the 'tomli' package. "
            "Install with 'pip install tomli' for Python 3.9/3.10."
        )
        return result

    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        result.errors.append(f"Failed to parse TOML: {exc}")
        return result

    profiles_data = data.get("profiles", {})

    if not isinstance(profiles_data, dict):
        result.errors.append("'profiles' must be a table")
        return result

    for profile_name, profile_data in profiles_data.items():
        if not isinstance(profile_data, dict):
            result.errors.append(
                f"Profile '{profile_name}': must be a table, got {type(profile_data).__name__}"
            )
            continue

        try:
            profile = _parse_profile_data(profile_name, profile_data, source_file)
            result.profiles[profile_name] = profile
        except ValueError as exc:
            result.errors.append(str(exc))

    return result


def load_config() -> Config:
    """
    Load configuration from all available config files.

    Later config files override values from earlier ones for profiles
    with the same name. Options within a profile are merged.

    Invalid profile options are reported as errors but do not prevent
    loading of other valid profiles.
    """
    config = Config()

    if not HAS_TOML:
        return config

    for config_path in _get_config_paths():
        if not config_path.is_file():
            continue

        try:
            content = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            click.echo(
                f"Warning: Cannot read config {config_path}: {exc}",
                err=True,
            )
            continue

        result = _parse_toml_config(content, config_path)

        for error in result.errors:
            click.echo(f"Error in {config_path}: {error}", err=True)

        if not result.profiles and not result.errors:
            continue

        config.source_files.append(config_path)

        for profile_name, profile in result.profiles.items():
            if profile_name in config.profiles:
                config.profiles[profile_name].options.update(profile.options)
            else:
                config.profiles[profile_name] = profile

    return config


def apply_profile_defaults(
    ctx: click.Context, param: click.Parameter, profile_name: Optional[str]
) -> Optional[str]:
    """
    Click callback to apply profile defaults before other parameters are processed.

    This modifies ctx.default_map so that profile values act as defaults
    that can be overridden by explicit command-line arguments.
    """
    if not profile_name:
        return profile_name

    config = load_config()
    profile = config.get_profile(profile_name)

    if profile is None:
        available = ", ".join(config.list_profiles())
        if available:
            raise click.BadParameter(
                f"profile '{profile_name}' not found. Available profiles: {available}"
            )
        else:
            raise click.BadParameter(
                f"profile '{profile_name}' not found. No profiles configured."
            )

    if ctx.default_map is None:
        ctx.default_map = {}

    for key, value in profile.options.items():
        click_param = PROFILE_KEY_TO_CLICK_PARAM.get(key, key)
        if click_param not in ctx.default_map:
            ctx.default_map[click_param] = value

    return profile_name
