"""Unified export strategy for rich-cli.

This module is the single source of truth for export-related data and
behaviour.  Terminal rendering and every export format (HTML, SVG, and any
future formats) share the same :class:`ExportOptions` dataclass and the same
metadata wrapper :class:`ExportMetadata`.  The :func:`save_exports` entry
point routes to the appropriate Rich ``Console.save_*`` method so that the
main entry point only needs to call one function regardless of which export
formats are enabled.

Export targets are expressed as a list of :class:`ExportTarget` instances so
that adding a new format does not change the public signature of
:func:`save_exports`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, TYPE_CHECKING

from rich.console import Console, RenderableType
from rich.text import Text

if TYPE_CHECKING:
    from rich.console import ConsoleOptions, RenderResult
    from rich.measure import Measurement


@dataclass
class ExportOptions:
    """Unified export options shared by terminal rendering and all export
    formats (HTML, SVG, and any future formats).

    Attributes:
        title: Title displayed on the exported artifact (tab title for SVG,
            document title for HTML). Falls back to the resource panel title.
        theme: Name of the syntax theme used when rendering the resource.
        source_path: Path or URL the resource was read from.
        generated_at: ISO-8601 timestamp of when the export was generated.
        inline_styles: Whether HTML should emit styles inline (``True``) or
            embed them in a ``<style>`` tag (``False``). SVG currently ignores
            this setting.
    """

    title: Optional[str] = None
    theme: Optional[str] = None
    source_path: Optional[str] = None
    generated_at: Optional[str] = None
    inline_styles: bool = False

    def has_metadata(self) -> bool:
        """Return True when any of the metadata fields are populated."""
        return bool(
            self.title or self.theme or self.source_path or self.generated_at
        )


@dataclass
class ExportTarget:
    """A single export destination: format identifier + output path.

    The main entry point builds a list of these from CLI flags and hands it
    to :func:`save_exports`.  Because the list is open-ended, adding a new
    export format does not require changing the call signature of
    :func:`save_exports`.

    Attributes:
        format: Short identifier for the export format, e.g. ``"html"`` or
            ``"svg"``.  Matches keys in the internal dispatch table.
        path: File system path to write the output to.
    """

    format: str
    path: str


def build_export_options(
    *,
    export_meta: bool = False,
    title: str = "",
    theme: str = "",
    resource: str = "",
    export_source: str = "",
    no_export_time: bool = False,
    export_inline_styles: bool = False,
) -> ExportOptions:
    """Build an :class:`ExportOptions` instance from raw CLI arguments.

    The main entry point calls this helper *after* it has finished shaping the
    renderable.  All knowledge about how CLI flags map onto export semantics
    lives here so the main entry stays agnostic.
    """
    return ExportOptions(
        title=title if export_meta and title else None,
        theme=theme if export_meta and theme else None,
        source_path=(
            export_source
            if export_meta and export_source
            else resource
            if export_meta and resource and resource != "-"
            else None
        ),
        generated_at=(
            None
            if (not export_meta) or no_export_time
            else datetime.now().astimezone().isoformat(timespec="seconds")
        ),
        inline_styles=export_inline_styles,
    )


def build_export_targets(
    *,
    export_html: str = "",
    export_svg: str = "",
) -> List[ExportTarget]:
    """Build a list of :class:`ExportTarget` from CLI export paths.

    Each non-empty path becomes one target.  The main entry point calls this
    so it never has to know the mapping between CLI flags and format
    identifiers – that knowledge lives here alongside the dispatch table in
    :func:`save_exports`.
    """
    targets: List[ExportTarget] = []
    if export_html:
        targets.append(ExportTarget(format="html", path=export_html))
    if export_svg:
        targets.append(ExportTarget(format="svg", path=export_svg))
    return targets


class ExportMetadata:
    """Renderable that emits a small header block of export metadata.

    The block is prepended to terminal/export output when any of
    :class:`ExportOptions` metadata fields are set. Because the wrapper
    participates in the standard Rich rendering pipeline, the same metadata
    appears in terminal output, HTML export, and SVG export.
    """

    def __init__(
        self,
        renderable: "RenderableType",
        options: ExportOptions,
    ) -> None:
        self.renderable = renderable
        self.options = options

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        if self.options.has_metadata():
            from rich.rule import Rule

            if self.options.title:
                yield Text(self.options.title, style="bold")
            meta_lines: List[str] = []
            if self.options.theme:
                meta_lines.append(f"theme: {self.options.theme}")
            if self.options.source_path:
                meta_lines.append(f"source: {self.options.source_path}")
            if self.options.generated_at:
                meta_lines.append(f"generated: {self.options.generated_at}")
            if meta_lines:
                yield Text("\n".join(meta_lines), style="dim")
            yield Rule(style="dim")
        yield self.renderable

    def __rich_measure__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "Measurement":
        from rich.measure import Measurement

        child = console.measure(self.renderable, options)
        return Measurement(child.minimum, child.maximum)


def _save_html(console: Console, path: str, options: ExportOptions) -> None:
    """Save recorded console contents as HTML without clearing the record buffer.

    ``clear`` is always ``False`` here – see :func:`save_exports` for the
    overall buffer-lifecycle contract.
    """
    console.save_html(
        path,
        clear=False,
        inline_styles=options.inline_styles,
    )


def _save_svg(console: Console, path: str, options: ExportOptions) -> None:
    """Save recorded console contents as SVG without clearing the record buffer.

    ``clear`` is always ``False`` here – see :func:`save_exports` for the
    overall buffer-lifecycle contract.
    """
    console.save_svg(
        path,
        clear=False,
        title=options.title or "Rich",
    )


def _clear_record_buffer(console: Console) -> None:
    """Clear the console's record buffer after all exports are saved.

    Rich's ``Console`` does not expose a dedicated public method for clearing
    the record buffer, so we call ``export_html`` with ``clear=True`` and
    discard the returned string.  This is the cheapest public-API way to
    reset the buffer.
    """
    console.export_html(clear=True)


#: Dispatch table mapping format identifier → save function.
#: Adding a new export format only requires registering a new entry here
#: and adding a matching CLI flag + :func:`build_export_targets` entry.
#:
#: **Buffer-lifecycle contract**: every saver in this table MUST pass
#: ``clear=False`` to the underlying Rich ``save_*`` call.  The buffer is
#: cleared exactly once at the end of :func:`save_exports`, so that every
#: target receives the same recorded content.
_EXPORT_DISPATCH: Dict[str, object] = {
    "html": _save_html,
    "svg": _save_svg,
}


def save_exports(
    console: Console,
    options: ExportOptions,
    targets: List[ExportTarget],
) -> None:
    """Dispatch exports using a single :class:`ExportOptions` and a list of
    :class:`ExportTarget`.

    **Buffer-lifecycle**

    Rich's ``Console.save_html`` / ``save_svg`` clear the record buffer by
    default (``clear=True``).  If we let that happen between targets, a
    subsequent save would see an empty buffer and produce an empty file.

    To guarantee that every target gets the **same** rendered content,
    :func:`save_exports` enforces a simple contract:

    1. Every saver in :data:`_EXPORT_DISPATCH` passes ``clear=False`` to the
       underlying Rich call, so the record buffer is preserved across
       targets.
    2. After **all** targets have been saved (or if an error occurs), the
       buffer is cleared exactly once via :func:`_clear_record_buffer` in a
       ``finally`` block.

    **Extending with a new format**

    Adding a new export format only requires:

    1. Writing a small ``_save_*`` helper (it *must* pass ``clear=False``).
    2. Registering it in :data:`_EXPORT_DISPATCH`.
    3. Updating :func:`build_export_targets` to recognise the new CLI flag.

    The call site in ``__main__.py``, the public signature of this function,
    and the buffer-lifecycle logic all stay unchanged.
    """
    from .__main__ import on_error

    if not targets:
        return

    try:
        for target in targets:
            saver = _EXPORT_DISPATCH.get(target.format)
            if saver is None:
                on_error(f"unknown export format: {target.format}")
            try:
                saver(console, target.path, options)  # type: ignore[operator]
            except Exception as error:
                on_error(f"failed to save {target.format}", error)
    finally:
        _clear_record_buffer(console)
