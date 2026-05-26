"""Runtime constants for rich-cli.

These constants are used by the CLI runtime logic and should not be
mixed with documentation metadata in options.py.
"""

VERSION = "1.8.0"

BOXES = [
    "none",
    "ascii",
    "ascii2",
    "square",
    "rounded",
    "heavy",
    "double",
]

BOX_TEXT = ", ".join(sorted(BOXES))

AUTO = 0
SYNTAX = 1
PRINT = 2
MARKDOWN = 3
RST = 4
JSON = 5
RULE = 6
INSPECT = 7
CSV = 8
IPYNB = 9

COMMON_LEXERS = {
    "html": "html",
    "py": "python",
    "md": "markdown",
    "js": "javascript",
    "xml": "xml",
    "json": "json",
    "toml": "toml",
}
