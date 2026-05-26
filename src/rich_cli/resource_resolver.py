import csv
import json
import os.path
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

from pygments.util import ClassNotFound
from rich.console import Console
from rich.markup import escape
from rich.text import Text

console = Console()
error_console = Console(stderr=True)


class ResourceErrorKind(str, Enum):
    MISSING_RESOURCE = "missing_resource"
    FILE_NOT_FOUND = "file_not_found"
    FILE_READ_ERROR = "file_read_error"
    STDIN_READ_ERROR = "stdin_read_error"
    URL_READ_ERROR = "url_read_error"
    URL_NON_TEXT = "url_non_text"
    MIME_UNSUPPORTED = "mime_unsupported"
    READ_PERMISSION = "read_permission"
    UNKNOWN = "unknown"


@dataclass
class ResourceError(Exception):
    kind: ResourceErrorKind
    message: str
    original_error: Optional[Exception] = None
    source: Optional[str] = None
    hint: Optional[str] = None

    def __str__(self) -> str:
        return self.message

    def display(self, console: Console) -> None:
        error_text = Text(self.message)
        error_text.stylize("bold red")
        if self.original_error:
            error_text += ": "
            error_text += console.highlighter(str(self.original_error))
        if self.hint:
            error_text += Text(f"\n  hint: {self.hint}", style="dim")
        error_console.print(error_text)


COMMON_LEXERS = {
    "html": "html",
    "py": "python",
    "md": "markdown",
    "js": "javascript",
    "xml": "xml",
    "json": "json",
    "toml": "toml",
}

FORMAT_EXTENSIONS = {
    ".md": "markdown",
    ".json": "json",
    ".csv": "csv",
    ".tsv": "csv",
    ".rst": "rst",
    ".ipynb": "ipynb",
}

MIME_TYPE_MAP = {
    "application/json": "json",
    "text/csv": "csv",
    "text/tab-separated-values": "csv",
    "text/markdown": "markdown",
    "text/x-rst": "rst",
    "application/x-ipynb+json": "ipynb",
}

LEXER_FORMAT_MAP = {
    "json": "json",
    "markdown": "markdown",
    "csv": "csv",
    "rst": "rst",
    "ipython notebook": "ipynb",
}

FORMAT_SOURCE_EXTENSION = "extension"
FORMAT_SOURCE_MIME = "mime"
FORMAT_SOURCE_LEXER = "lexer"
FORMAT_SOURCE_CONTENT = "content"

MARKDOWN_PATTERNS = [
    re.compile(r"^#{1,6}\s+\S", re.MULTILINE),
    re.compile(r"\*\*[^*]+\*\*"),
    re.compile(r"`[^`]+`"),
    re.compile(r"\[[^\]]+\]\([^)]+\)"),
    re.compile(r"^>\s", re.MULTILINE),
    re.compile(r"^\s*[-*+]\s+\S", re.MULTILINE),
    re.compile(r"^\s*\d+\.\s+\S", re.MULTILINE),
]

RST_PATTERNS = [
    re.compile(r"^[^\n]+\n[=+\-~`'\"\^_*#]{4,}$", re.MULTILINE),
    re.compile(r"^\.\.\s\w+::", re.MULTILINE),
    re.compile(r":\w+:`[^`]+`"),
]


@dataclass
class FormatRecommendation:
    format: str
    source: str
    reason: str

    def __str__(self) -> str:
        return f"{self.format} (from {self.source}: {self.reason})"


@dataclass
class Resource:
    content: str
    source: str
    source_path: Optional[str]
    recommended_lexer: Optional[str]
    resource_type: str
    mime_type: Optional[str] = None
    format_recommendation: Optional[FormatRecommendation] = None

    @property
    def extension(self) -> Optional[str]:
        if not self.source_path:
            return None
        _, ext = os.path.splitext(self.source_path)
        return ext.lower() if ext else None

    @property
    def recommended_format(self) -> Optional[str]:
        if self.format_recommendation:
            return self.format_recommendation.format
        return None

    @property
    def recommended_format_source(self) -> Optional[str]:
        if self.format_recommendation:
            return self.format_recommendation.source
        return None


def _detect_format_from_content(content: str) -> Optional[str]:
    if not content or not content.strip():
        return None

    stripped = content.strip()

    if stripped.startswith("{") or stripped.startswith("["):
        try:
            json.loads(stripped)
            return "json"
        except (json.JSONDecodeError, ValueError):
            pass

    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(stripped[:4096], delimiters=",\t|;")
        if dialect:
            has_header = sniffer.has_header(stripped[:4096])
            if has_header or len(stripped.splitlines()) >= 2:
                reader = csv.reader(stripped.splitlines()[:1], dialect=dialect)
                for row in reader:
                    if len(row) >= 2:
                        return "csv"
    except (csv.Error, StopIteration):
        pass

    md_matches = sum(
        1 for pattern in MARKDOWN_PATTERNS if pattern.search(content)
    )
    if md_matches >= 2:
        return "markdown"

    rst_matches = sum(
        1 for pattern in RST_PATTERNS if pattern.search(content)
    )
    if rst_matches >= 1:
        return "rst"

    return None


class ResourceResolver:
    def __init__(self, lexer_hint: Optional[str] = None) -> None:
        self.lexer_hint = lexer_hint

    def resolve(self, resource: str) -> Resource:
        if not resource:
            raise ResourceError(
                kind=ResourceErrorKind.MISSING_RESOURCE,
                message="missing path or URL",
            )

        if resource == "-":
            return self._resolve_stdin()
        elif resource.startswith(("http://", "https://")):
            return self._resolve_url(resource)
        else:
            return self._resolve_file(resource)

    def compute_format_recommendation(
        self,
        resource: Resource,
    ) -> Optional[FormatRecommendation]:
        if resource.mime_type and resource.mime_type in MIME_TYPE_MAP:
            fmt = MIME_TYPE_MAP[resource.mime_type]
            return FormatRecommendation(
                format=fmt,
                source=FORMAT_SOURCE_MIME,
                reason=f"MIME type {resource.mime_type}",
            )

        if (
            resource.recommended_lexer
            and resource.recommended_lexer.lower() in LEXER_FORMAT_MAP
        ):
            fmt = LEXER_FORMAT_MAP[resource.recommended_lexer.lower()]
            return FormatRecommendation(
                format=fmt,
                source=FORMAT_SOURCE_LEXER,
                reason=f"lexer detected as {resource.recommended_lexer}",
            )

        ext = resource.extension
        if ext in FORMAT_EXTENSIONS:
            fmt = FORMAT_EXTENSIONS[ext]
            return FormatRecommendation(
                format=fmt,
                source=FORMAT_SOURCE_EXTENSION,
                reason=f"file extension {ext}",
            )

        content_fmt = _detect_format_from_content(resource.content)
        if content_fmt:
            return FormatRecommendation(
                format=content_fmt,
                source=FORMAT_SOURCE_CONTENT,
                reason=f"content analysis identified {content_fmt}",
            )

        return None

    def _resolve_stdin(self) -> Resource:
        try:
            content = sys.stdin.read()
            resource = Resource(
                content=content,
                source="-",
                source_path=None,
                recommended_lexer=self.lexer_hint,
                resource_type="stdin",
            )
            resource.format_recommendation = self.compute_format_recommendation(resource)
            return resource
        except Exception as error:
            raise ResourceError(
                kind=ResourceErrorKind.STDIN_READ_ERROR,
                message="unable to read stdin",
                original_error=error,
                source="-",
                hint="ensure stdin is connected to a pipe or input stream",
            )

    def _resolve_url(self, url: str) -> Resource:
        try:
            import requests

            response = requests.get(url)
            content = response.text

            mime_type = self._extract_mime_type(response.headers)

            if mime_type and not self._is_text_mime(mime_type):
                raise ResourceError(
                    kind=ResourceErrorKind.URL_NON_TEXT,
                    message=f"URL returned non-text content type: {mime_type}",
                    source=url,
                    hint="use --syntax or specify a different resource",
                )

            lexer = self.lexer_hint
            if not lexer:
                lexer = self._infer_lexer_from_url(url)
            if not lexer and mime_type:
                lexer = self._infer_lexer_from_mime_type(mime_type)
            if not lexer:
                lexer = self._infer_lexer_from_content(url, content)

            source_path = self._extract_url_path(url)

            resource = Resource(
                content=content,
                source=url,
                source_path=source_path,
                recommended_lexer=lexer,
                resource_type="url",
                mime_type=mime_type,
            )
            resource.format_recommendation = self.compute_format_recommendation(resource)
            return resource
        except ResourceError:
            raise
        except Exception as error:
            raise ResourceError(
                kind=ResourceErrorKind.URL_READ_ERROR,
                message=f"unable to read {escape(url)}",
                original_error=error,
                source=url,
                hint="check the URL and network connectivity",
            )

    def _resolve_file(self, path: str) -> Resource:
        if not os.path.exists(path):
            raise ResourceError(
                kind=ResourceErrorKind.FILE_NOT_FOUND,
                message=f"file not found: {escape(path)}",
                source=path,
                hint="check the file path and ensure the file exists",
            )
        if not os.access(path, os.R_OK):
            raise ResourceError(
                kind=ResourceErrorKind.READ_PERMISSION,
                message=f"permission denied reading {escape(path)}",
                source=path,
                hint="check file permissions",
            )
        try:
            with open(path, "rt", encoding="utf8", errors="replace") as f:
                content = f.read()

            lexer = self.lexer_hint
            if not lexer:
                lexer = self._infer_lexer_from_extension(path)
            if not lexer:
                lexer = self._infer_lexer_from_content(path, content)

            resource = Resource(
                content=content,
                source=path,
                source_path=path,
                recommended_lexer=lexer,
                resource_type="file",
            )
            resource.format_recommendation = self.compute_format_recommendation(resource)
            return resource
        except ResourceError:
            raise
        except Exception as error:
            raise ResourceError(
                kind=ResourceErrorKind.FILE_READ_ERROR,
                message=f"unable to read {escape(path)}",
                original_error=error,
                source=path,
            )

    def _is_text_mime(self, mime_type: str) -> bool:
        if mime_type.startswith("text/"):
            return True
        if mime_type in MIME_TYPE_MAP:
            return True
        if mime_type in ("application/json", "application/xml"):
            return True
        if mime_type.startswith("application/") and (
            "+xml" in mime_type or "+json" in mime_type or "+text" in mime_type
        ):
            return True
        return False

    def _extract_mime_type(self, headers: dict) -> Optional[str]:
        try:
            mime_type: str = headers["Content-Type"]
            if ";" in mime_type:
                mime_type = mime_type.split(";", 1)[0]
            return mime_type.strip()
        except KeyError:
            return None

    def _infer_lexer_from_extension(self, path: str) -> Optional[str]:
        _, dot, ext = path.rpartition(".")
        if dot and ext:
            ext = ext.lower()
            return COMMON_LEXERS.get(ext, None)
        return None

    def _infer_lexer_from_url(self, url: str) -> Optional[str]:
        path = self._extract_url_path(url)
        if path:
            return self._infer_lexer_from_extension(path)
        return None

    def _infer_lexer_from_mime_type(self, mime_type: str) -> Optional[str]:
        from pygments.lexers import get_lexer_for_mimetype

        try:
            return get_lexer_for_mimetype(mime_type).name
        except Exception:
            return None

    def _infer_lexer_from_content(self, path: str, content: str) -> Optional[str]:
        from pygments.lexers import guess_lexer_for_filename

        try:
            return guess_lexer_for_filename(path, content).name
        except ClassNotFound:
            return "text"

    def _extract_url_path(self, url: str) -> Optional[str]:
        try:
            return urlparse(url).path
        except Exception:
            return None
