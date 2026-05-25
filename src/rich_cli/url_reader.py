"""Fetch a URL and return a structured result describing the outcome.

This module is deliberately free of any ``sys.exit`` / console rendering
coupling. Callers decide how to present errors or render a successful
response. The surface of the module is intentionally small:

* :func:`fetch_url` returns a :class:`FetchResult`.
* :func:`describe_error` turns a :class:`FetchError` into a
  ``(message, detail)`` pair ready to hand off to an
  application-level error handler.

All HTTP concerns (timeouts, status codes, MIME inspection, lexer
inference) live here so ``__main__.py`` only orchestrates dispatch.
"""
from __future__ import annotations

import os.path
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Mapping, Optional, Tuple
from urllib.parse import urlparse

DEFAULT_REQUEST_TIMEOUT = 15

TEXT_BASED_MIME_PREFIXES: Tuple[str, ...] = (
    "text/",
    "application/json",
    "application/xml",
    "application/xhtml+xml",
    "application/x-yaml",
    "application/yaml",
    "application/javascript",
    "application/x-javascript",
    "application/ecmascript",
    "application/toml",
    "application/problem+json",
    "application/problem+xml",
)


class FetchErrorKind(str, Enum):
    """Category of URL fetch failure."""

    TIMEOUT = "timeout"
    CONNECTION = "connection"
    REQUEST = "request"
    HTTP_ERROR = "http_error"
    MISSING_CONTENT_TYPE = "missing_content_type"
    NON_TEXT_CONTENT_TYPE = "non_text_content_type"


class LexerSource(str, Enum):
    """Where the lexer on a :class:`FetchSuccess` came from."""

    MIME = "mime"
    URL_SUFFIX = "url_suffix"
    NONE = "none"


@dataclass(frozen=True)
class FetchError:
    """Structured description of a failed URL fetch."""

    kind: FetchErrorKind
    message: str
    detail: Optional[str] = None

    def as_exception(self) -> Exception:
        """Return an :class:`Exception` whose ``str`` is the detail text.

        Paired with :func:`describe_error`, callers can do
        ``on_error(message, error.as_exception())`` to produce a single
        line ``<message>: <detail>`` without duplication.
        """
        return RuntimeError(self.detail or "")


@dataclass(frozen=True)
class FetchSuccess:
    """Structured description of a successful URL fetch.

    Attributes:
        text: The decoded response body.
        lexer: The lexer name chosen for syntax highlighting, or ``None``
            if no suitable lexer could be determined.
        lexer_source: Which signal produced ``lexer`` —
            :attr:`LexerSource.MIME` when the Content-Type header resolved
            it, :attr:`LexerSource.URL_SUFFIX` when the URL path extension
            was used as a fallback, or :attr:`LexerSource.NONE` if no
            lexer was inferred at all.
        raw_content_type: The verbatim ``Content-Type`` header as received
            from the server (e.g. ``"text/markdown; charset=utf-8"``).
        mime_type: The normalized MIME type — parameters stripped and
            lowercased (e.g. ``"text/markdown"``).
    """

    text: str
    lexer: Optional[str]
    lexer_source: LexerSource
    raw_content_type: str
    mime_type: str


FetchResult = Tuple[Optional[FetchSuccess], Optional[FetchError]]


def _normalize_mime(raw: str) -> str:
    """Strip parameters and whitespace from a Content-Type value."""
    return raw.split(";", 1)[0].strip().lower()


def _is_text_based_mime(mime_type: str) -> bool:
    """Return True if the MIME type indicates text-like content.

    The caller is expected to pass a value already run through
    :func:`_normalize_mime` (parameters stripped, lowercased).
    """
    if not mime_type:
        return False
    for prefix in TEXT_BASED_MIME_PREFIXES:
        if mime_type.startswith(prefix):
            return True
    return False


def _infer_lexer_from_url(
    url: str, common_lexers: Mapping[str, str]
) -> Optional[str]:
    """Infer a lexer name from a URL's path extension."""
    try:
        path = urlparse(url).path
    except Exception:
        return None
    ext = os.path.splitext(path)[-1].lower().lstrip(".")
    if not ext:
        return None
    return common_lexers.get(ext)


def _infer_lexer_from_mime(mime_type: str) -> Optional[str]:
    """Infer a lexer name from an HTTP Content-Type value."""
    from pygments.lexers import get_lexer_for_mimetype

    try:
        return get_lexer_for_mimetype(mime_type).name
    except Exception:
        return None


def fetch_url(
    url: str,
    common_lexers: Mapping[str, str],
    timeout: int = DEFAULT_REQUEST_TIMEOUT,
) -> FetchResult:
    """Fetch ``url`` and return a structured result.

    This function never raises or exits. It returns either
    ``(FetchSuccess, None)`` or ``(None, FetchError)``. The caller is
    responsible for turning a :class:`FetchError` into user-facing output.

    Args:
        url: The URL to fetch.
        common_lexers: Mapping of lowercase file extensions to lexer names,
            used when inferring a lexer from the URL path.
        timeout: Request timeout in seconds.

    Returns:
        A tuple ``(success, error)`` where exactly one is ``None``.
    """
    import requests

    try:
        response = requests.get(url, timeout=timeout)
    except requests.exceptions.Timeout as error:
        return (
            None,
            FetchError(
                kind=FetchErrorKind.TIMEOUT,
                message=f"request timed out for {url}",
                detail=str(error),
            ),
        )
    except requests.exceptions.ConnectionError as error:
        return (
            None,
            FetchError(
                kind=FetchErrorKind.CONNECTION,
                message=f"unable to connect to {url}",
                detail=str(error),
            ),
        )
    except requests.exceptions.RequestException as error:
        return (
            None,
            FetchError(
                kind=FetchErrorKind.REQUEST,
                message=f"request failed for {url}",
                detail=str(error),
            ),
        )

    if not response.ok:
        status_code = response.status_code
        reason = (getattr(response, "reason", "") or "").strip()
        detail = f"HTTP {status_code}"
        if reason and reason.lower() != "unknown":
            detail += f" {reason}"
        return (
            None,
            FetchError(
                kind=FetchErrorKind.HTTP_ERROR,
                message=f"received error response from {url}",
                detail=detail,
            ),
        )

    try:
        raw_content_type: str = response.headers["Content-Type"]
    except KeyError:
        return (
            None,
            FetchError(
                kind=FetchErrorKind.MISSING_CONTENT_TYPE,
                message=f"response from {url} is missing Content-Type",
                detail="refusing to render response of unknown type",
            ),
        )

    mime_type = _normalize_mime(raw_content_type)

    if not _is_text_based_mime(mime_type):
        return (
            None,
            FetchError(
                kind=FetchErrorKind.NON_TEXT_CONTENT_TYPE,
                message=f"response from {url} has non-text Content-Type",
                detail=(
                    f"normalized {mime_type!r} "
                    f"(raw {raw_content_type!r}); "
                    f"refusing to render binary response"
                ),
            ),
        )

    text = response.text
    lexer = _infer_lexer_from_mime(mime_type)
    if lexer is not None:
        lexer_source = LexerSource.MIME
    else:
        lexer = _infer_lexer_from_url(url, common_lexers)
        lexer_source = LexerSource.URL_SUFFIX if lexer is not None else LexerSource.NONE

    return (
        FetchSuccess(
            text=text,
            lexer=lexer,
            lexer_source=lexer_source,
            raw_content_type=raw_content_type,
            mime_type=mime_type,
        ),
        None,
    )


def describe_error(error: FetchError) -> Tuple[str, str]:
    """Return ``(message, detail)`` for presentation to the user.

    ``message`` is the one-line headline; ``detail`` is the elaboration
    (HTTP status, OS error text, MIME value, etc.). Callers typically
    pass ``message`` to their error handler and append ``detail`` as
    contextual information.
    """
    if error.detail:
        return (f"{error.message} ({error.detail})", error.detail)
    return (error.message, "")


# Re-export so ``__main__.py`` has a single import surface.
__all__ = [
    "DEFAULT_REQUEST_TIMEOUT",
    "TEXT_BASED_MIME_PREFIXES",
    "FetchError",
    "FetchErrorKind",
    "FetchResult",
    "FetchSuccess",
    "LexerSource",
    "describe_error",
    "fetch_url",
]

# Prevent pytest from collecting module-level functions as tests.
__test__ = False
