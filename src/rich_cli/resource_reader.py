import sys
from typing import Optional, Tuple

from pygments.util import ClassNotFound
from rich.markup import escape

COMMON_LEXERS = {
    "html": "html",
    "py": "python",
    "md": "markdown",
    "js": "javascript",
    "xml": "xml",
    "json": "json",
    "toml": "toml",
}


def _on_error(message: str, error: Optional[Exception] = None, code: int = -1):
    from rich.console import Console
    from rich.text import Text

    error_console = Console(stderr=True)
    if error:
        error_text = Text(message)
        error_text.stylize("bold red")
        error_text += ": "
        error_text += error_console.highlighter(str(error))
        error_console.print(error_text)
    else:
        error_text = Text(message, style="bold red")
        error_console.print(error_text)
    sys.exit(code)


def read_resource(path: str, lexer: Optional[str]) -> Tuple[str, Optional[str]]:
    """Read a resource from a file, URL, or stdin."""
    if not path:
        _on_error("missing path or URL")

    if path.startswith(("http://", "https://")):
        return _read_url(path, lexer)
    return _read_file(path, lexer)


def _read_url(url: str, lexer: Optional[str]) -> Tuple[str, Optional[str]]:
    import requests

    response = requests.get(url)
    text = response.text

    if not lexer:
        _, dot, ext = url.rpartition(".")
        if dot and ext:
            ext = ext.lower()
            lexer = COMMON_LEXERS.get(ext, None)

        if lexer is None:
            try:
                mime_type: str = response.headers["Content-Type"]
                if ";" in mime_type:
                    mime_type = mime_type.split(";", 1)[0]
                from pygments.lexers import get_lexer_for_mimetype

                lexer = get_lexer_for_mimetype(mime_type).name
            except (KeyError, Exception):
                pass

    return (text, lexer)


def _read_file(path: str, lexer: Optional[str]) -> Tuple[str, Optional[str]]:
    try:
        if path == "-":
            return (sys.stdin.read(), None)

        with open(path, "rt", encoding="utf8", errors="replace") as resource_file:
            text = resource_file.read()

        if not lexer:
            _, dot, ext = path.rpartition(".")
            if dot and ext:
                ext = ext.lower()
                lexer = COMMON_LEXERS.get(ext, None)

        if not lexer:
            from pygments.lexers import guess_lexer_for_filename

            try:
                lexer = guess_lexer_for_filename(path, text).name
            except ClassNotFound:
                return (text, "text")

        return (text, lexer)
    except Exception as error:
        _on_error(f"unable to read {escape(path)}", error)


def detect_format_from_extension(path: str) -> Optional[int]:
    import os.path

    from .renderer_registry import CSV, IPYNB, JSON, MARKDOWN, RST

    ext = ""
    if path.startswith(("http://", "https://")):
        from urllib.parse import urlparse

        try:
            url_path = urlparse(path).path
            ext = os.path.splitext(url_path)[-1].lower()
        except Exception:
            return None
    else:
        ext = os.path.splitext(path)[-1].lower()

    if ext == ".md":
        return MARKDOWN
    elif ext == ".json":
        return JSON
    elif ext in (".csv", ".tsv"):
        return CSV
    elif ext == ".rst":
        return RST
    elif ext == ".ipynb":
        return IPYNB
    return None
