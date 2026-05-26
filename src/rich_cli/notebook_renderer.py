"""Jupyter notebook rendering pipeline.

This module is organized as a four-layer pipeline operating on a shared
``Notebook`` data model so JSON structure lookups are not scattered across
the CLI layer:

    1. Parse         - json.loads -> Notebook (typed model)
    2. Filter        - cell type / cell index range selection
    3. Transform     - per-cell: lexer resolution, head/tail line range,
                       output preprocessing
    4. Render        - Notebook + RenderConfig -> Rich renderable

All layers raise structured exceptions derived from ``NotebookError`` so
callers can handle them uniformly without seeing raw JSON / Rich exceptions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Tuple

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from .markdown import Markdown

__all__ = [
    "NotebookError",
    "ParseError",
    "CellRangeError",
    "EmptyNotebookError",
    "UnknownCellTypeError",
    "UnknownOutputTypeError",
    "Notebook",
    "Cell",
    "Output",
    "RenderConfig",
    "FilterConfig",
    "TransformConfig",
    "parse_cell_range",
    "parse_cell_types",
    "parse_notebook",
    "filter_notebook",
    "transform_notebook",
    "render_notebook",
    "render_ipynb",
]


# ---------------------------------------------------------------------------
# 0. Structured exceptions
# ---------------------------------------------------------------------------


class NotebookError(Exception):
    """Base class for all notebook-related errors."""

    def __init__(self, message: str, *, cause: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class ParseError(NotebookError):
    """Raised when the notebook JSON is malformed or structurally invalid."""


class CellRangeError(NotebookError):
    """Raised when a cell range filter is invalid."""


class EmptyNotebookError(NotebookError):
    """Raised when filtering/parsing yields a notebook with no cells."""


class UnknownCellTypeError(NotebookError):
    """Raised (or warned) when an unknown ``cell_type`` is encountered."""


class UnknownOutputTypeError(NotebookError):
    """Raised (or warned) when an unknown ``output_type`` is encountered."""


# ---------------------------------------------------------------------------
# 1. Data model
# ---------------------------------------------------------------------------


@dataclass
class Output:
    """A single cell output."""

    output_type: str
    name: Optional[str] = None
    text: List[str] = field(default_factory=list)
    traceback: List[str] = field(default_factory=list)
    ename: Optional[str] = None
    evalue: Optional[str] = None
    execution_count: Optional[str] = None
    data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class Cell:
    """A single notebook cell."""

    cell_type: str
    source: List[str] = field(default_factory=list)
    execution_count: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    outputs: List[Output] = field(default_factory=list)
    cell_id: Optional[str] = None

    @property
    def source_text(self) -> str:
        return "".join(self.source)

    @property
    def source_lines(self) -> List[str]:
        return self.source_text.splitlines()


@dataclass
class Notebook:
    """A parsed Jupyter notebook."""

    nbformat: int = 4
    nbformat_minor: int = 5
    metadata: dict = field(default_factory=dict)
    cells: List[Cell] = field(default_factory=list)

    @property
    def language(self) -> str:
        """Best-effort language from notebook metadata."""
        try:
            return self.metadata["kernelspec"]["language"]
        except Exception:
            pass
        try:
            return self.metadata["language_info"]["name"]
        except Exception:
            pass
        return ""

    @property
    def is_empty(self) -> bool:
        return not self.cells


# ---------------------------------------------------------------------------
# 2. Parse layer
# ---------------------------------------------------------------------------


def _validate_notebook_structure(raw: dict) -> None:
    """Lightweight structural validation after JSON parse.

    Raises ``ParseError`` if the notebook is missing required top-level
    structure (``cells``, ``nbformat``, etc.).
    """
    if not isinstance(raw, dict):
        raise ParseError("notebook root must be a JSON object")
    if "cells" not in raw:
        raise ParseError("notebook is missing required 'cells' field")
    if not isinstance(raw["cells"], list):
        raise ParseError("notebook 'cells' field must be an array")
    for i, cell in enumerate(raw["cells"]):
        if not isinstance(cell, dict):
            raise ParseError(f"cell #{i} is not a JSON object")
        if "cell_type" not in cell:
            raise ParseError(f"cell #{i} is missing required 'cell_type' field")
        if "source" not in cell:
            raise ParseError(f"cell #{i} is missing required 'source' field")
        outputs = cell.get("outputs", [])
        if not isinstance(outputs, list):
            raise ParseError(f"cell #{i} 'outputs' field must be an array")
        for j, output in enumerate(outputs):
            if not isinstance(output, dict):
                raise ParseError(f"cell #{i} output #{j} is not a JSON object")
            if "output_type" not in output:
                raise ParseError(
                    f"cell #{i} output #{j} is missing required 'output_type' field"
                )


def parse_notebook(notebook_str: str) -> Notebook:
    """Parse a JSON-encoded notebook string into the ``Notebook`` model.

    Raises:
        ParseError: if the string is not valid JSON or lacks required
            notebook structure.
    """
    try:
        raw = json.loads(notebook_str)
    except json.JSONDecodeError as exc:
        raise ParseError(
            f"notebook is not valid JSON: line {exc.lineno}, column {exc.colno}"
        ) from exc

    _validate_notebook_structure(raw)

    cells: List[Cell] = []
    for raw_cell in raw["cells"]:
        outputs: List[Output] = []
        for raw_output in raw_cell.get("outputs", []) or []:
            outputs.append(
                Output(
                    output_type=raw_output.get("output_type", ""),
                    name=raw_output.get("name"),
                    text=list(raw_output.get("text", []) or []),
                    traceback=list(raw_output.get("traceback", []) or []),
                    ename=raw_output.get("ename"),
                    evalue=raw_output.get("evalue"),
                    execution_count=raw_output.get("execution_count"),
                    data=raw_output.get("data", {}) or {},
                    metadata=raw_output.get("metadata", {}) or {},
                )
            )

        execution_count = raw_cell.get("execution_count")
        cells.append(
            Cell(
                cell_type=raw_cell.get("cell_type", ""),
                source=list(raw_cell.get("source", []) or []),
                execution_count=str(execution_count)
                if execution_count is not None
                else None,
                metadata=raw_cell.get("metadata", {}) or {},
                outputs=outputs,
                cell_id=raw_cell.get("id"),
            )
        )

    return Notebook(
        nbformat=int(raw.get("nbformat", 4)),
        nbformat_minor=int(raw.get("nbformat_minor", 5)),
        metadata=raw.get("metadata", {}) or {},
        cells=cells,
    )


# ---------------------------------------------------------------------------
# 3. Filter layer
# ---------------------------------------------------------------------------


def parse_cell_range(
    range_str: Optional[str],
) -> Optional[Tuple[Optional[int], Optional[int]]]:
    """Parse a cell range string like "1-5", "3-", "-10" into (start, end).

    Returns ``None`` if ``range_str`` is ``None`` or empty.

    Raises:
        CellRangeError: if the range string is malformed or semantically
            invalid (e.g., start > end when both bounds are given).
    """
    if range_str is None:
        return None

    range_str = range_str.strip()
    if not range_str:
        return None

    parts = range_str.split("-")
    if len(parts) != 2:
        raise CellRangeError(
            f"invalid cell range {range_str!r}; expected format like '1-5', '3-', or '-10'"
        )

    start_str, end_str = parts[0].strip(), parts[1].strip()
    start: Optional[int] = None
    end: Optional[int] = None

    try:
        if start_str:
            start = int(start_str)
        if end_str:
            end = int(end_str)
    except ValueError:
        raise CellRangeError(
            f"invalid cell range {range_str!r}; bounds must be integers"
        )

    if start is None and end is None:
        raise CellRangeError(
            f"invalid cell range {range_str!r}; at least one bound must be specified"
        )

    if start is not None and end is not None and start > end:
        raise CellRangeError(
            f"invalid cell range {range_str!r}; start ({start}) must be <= end ({end})"
        )

    if start is not None and start < 1:
        raise CellRangeError(
            f"invalid cell range {range_str!r}; start must be >= 1"
        )
    if end is not None and end < 1:
        raise CellRangeError(
            f"invalid cell range {range_str!r}; end must be >= 1"
        )

    return (start, end)


def parse_cell_types(
    types_str: Optional[str],
) -> Optional[List[str]]:
    """Parse a comma-separated cell types string into a list.

    Returns ``None`` if ``types_str`` is ``None`` or empty. Whitespace around
    type names is stripped, and empty entries are omitted.
    """
    if types_str is None:
        return None

    types_str = types_str.strip()
    if not types_str:
        return None

    return [t.strip() for t in types_str.split(",") if t.strip()]


@dataclass
class FilterConfig:
    """Options for filtering cells in a notebook."""

    cell_types: Optional[Iterable[str]] = None
    cell_range: Optional[Tuple[Optional[int], Optional[int]]] = None
    include_outputs: bool = True
    allow_empty: bool = False

    @classmethod
    def from_cli(
        cls,
        cell_types: Optional[str] = None,
        cell_range: Optional[str] = None,
        include_outputs: bool = True,
        allow_empty: bool = False,
    ) -> "FilterConfig":
        """Create a ``FilterConfig`` from raw CLI string parameters.

        This is the recommended entry point for CLI usage: it handles parsing
        and validation of string-formatted cell types and ranges.

        Raises:
            CellRangeError: if the cell range string is invalid.
        """
        return cls(
            cell_types=parse_cell_types(cell_types),
            cell_range=parse_cell_range(cell_range),
            include_outputs=include_outputs,
            allow_empty=allow_empty,
        )


def _validate_cell_range(
    cell_range: Optional[Tuple[Optional[int], Optional[int]]],
    total_cells: int,
) -> None:
    """Validate a cell range against the total number of cells.

    Raises ``CellRangeError`` for clearly invalid ranges (e.g. start > end,
    both bounds out of range, etc.).
    """
    if cell_range is None:
        return
    start, end = cell_range
    if start is not None and start < 1:
        raise CellRangeError(
            f"cell range start must be >= 1 (got {start})"
        )
    if end is not None and end < 1:
        raise CellRangeError(
            f"cell range end must be >= 1 (got {end})"
        )
    if start is not None and end is not None and start > end:
        raise CellRangeError(
            f"cell range start ({start}) must be <= end ({end})"
        )
    if total_cells and start is not None and start > total_cells:
        raise CellRangeError(
            f"cell range start ({start}) exceeds total cells ({total_cells})"
        )
    if total_cells and end is not None and end > total_cells:
        raise CellRangeError(
            f"cell range end ({end}) exceeds total cells ({total_cells})"
        )


def filter_notebook(
    notebook: Notebook, config: FilterConfig
) -> Notebook:
    """Return a new ``Notebook`` with cells filtered according to ``config``.

    ``config.cell_range`` is an optional ``(start, end)`` tuple where both
    bounds are 1-based and inclusive. ``None`` means no limit on that end.

    Raises:
        CellRangeError: if the requested range is invalid.
        EmptyNotebookError: if filtering yields zero cells and
            ``config.allow_empty`` is False.
    """

    _validate_cell_range(config.cell_range, len(notebook.cells))

    allowed_types = set(config.cell_types) if config.cell_types else None
    start, end = config.cell_range or (None, None)
    start_int: int = start if start is not None else 1
    end_int: Optional[int] = end

    filtered_cells: List[Cell] = []
    for index, cell in enumerate(notebook.cells, start=1):
        if index < start_int:
            continue
        if end_int is not None and index > end_int:
            break
        if allowed_types is not None and cell.cell_type not in allowed_types:
            continue

        if not config.include_outputs:
            cell = Cell(
                cell_type=cell.cell_type,
                source=list(cell.source),
                execution_count=cell.execution_count,
                metadata=dict(cell.metadata),
                outputs=[],
                cell_id=cell.cell_id,
            )

        filtered_cells.append(cell)

    result = Notebook(
        nbformat=notebook.nbformat,
        nbformat_minor=notebook.nbformat_minor,
        metadata=dict(notebook.metadata),
        cells=filtered_cells,
    )

    if result.is_empty and not config.allow_empty:
        raise EmptyNotebookError(
            "notebook has no cells after filtering; check your cell type "
            "or range filters"
        )

    return result


# ---------------------------------------------------------------------------
# 4. Transform layer
# ---------------------------------------------------------------------------


@dataclass
class TransformConfig:
    """Options for transforming cells prior to rendering."""

    lexer: Optional[str] = None
    head: Optional[int] = None
    tail: Optional[int] = None
    line_numbers: bool = False
    guides: bool = False
    no_wrap: bool = True


def _resolve_lexer(notebook: Notebook, config: TransformConfig) -> str:
    if config.lexer:
        return config.lexer
    return notebook.language or "text"


def _line_range(
    head: Optional[int],
    tail: Optional[int],
    num_lines: int,
) -> Optional[Tuple[int, int]]:
    """Compute a (start, end) line range for head/tail filtering.

    Raises ``CellRangeError`` if both ``head`` and ``tail`` are specified.
    """
    if head and tail:
        raise CellRangeError("cannot specify both head and tail for line range")
    if head:
        return (1, head)
    if tail:
        start = num_lines - tail + 2
        finish = num_lines + 1
        return (start, finish)
    return None


def transform_notebook(
    notebook: Notebook,
    config: TransformConfig,
) -> Notebook:
    """Apply source-level transformations to every cell.

    This layer only records metadata / configuration on the ``Notebook`` and
    its cells (e.g. resolved lexer, per-cell line range). It does not build
    any Rich renderables - that is the job of the render layer.

    Raises:
        CellRangeError: if head/tail options are invalid.
    """

    lexer = _resolve_lexer(notebook, config)

    transformed_cells: List[Cell] = []
    for cell in notebook.cells:
        metadata = dict(cell.metadata)
        metadata["_lexer"] = lexer
        if cell.cell_type == "code":
            num_lines = len(cell.source_lines)
            line_range = _line_range(config.head, config.tail, num_lines)
            if line_range is not None:
                metadata["_line_range"] = line_range
        transformed_cells.append(
            Cell(
                cell_type=cell.cell_type,
                source=list(cell.source),
                execution_count=cell.execution_count,
                metadata=metadata,
                outputs=list(cell.outputs),
                cell_id=cell.cell_id,
            )
        )

    return Notebook(
        nbformat=notebook.nbformat,
        nbformat_minor=notebook.nbformat_minor,
        metadata=dict(notebook.metadata),
        cells=transformed_cells,
    )


# ---------------------------------------------------------------------------
# 5. Render layer
# ---------------------------------------------------------------------------


@dataclass
class RenderConfig:
    """Options that control the final Rich rendering step."""

    theme: str = "ansi_dark"
    hyperlinks: bool = False
    line_numbers: bool = False
    guides: bool = False
    no_wrap: bool = True
    strict: bool = False


KNOWN_CELL_TYPES = {"code", "markdown", "raw"}
KNOWN_OUTPUT_TYPES = {"stream", "error", "execute_result", "display_data"}


def _render_cell(
    cell: Cell, config: RenderConfig
) -> List[RenderableType]:
    """Render a single cell as a list of Rich renderables.

    Raises:
        UnknownCellTypeError: if ``config.strict`` is True and an unknown
            cell type is encountered.
        UnknownOutputTypeError: if ``config.strict`` is True and an unknown
            output type is encountered.
    """

    parts: List[RenderableType] = []
    parts.append("")

    if cell.execution_count is not None:
        exec_count = cell.execution_count or " "
        parts.append(
            Text.from_markup(
                f"[green]In [[#66ff00]{exec_count}[/#66ff00]]:[/green]"
            )
        )

    lexer = cell.metadata.get("_lexer") or "text"
    source = cell.source_text
    line_range = cell.metadata.get("_line_range")

    if cell.cell_type == "code":
        parts.append(
            Panel(
                Syntax(
                    source,
                    lexer,
                    theme=config.theme,
                    line_numbers=config.line_numbers,
                    indent_guides=config.guides,
                    word_wrap=not config.no_wrap,
                    line_range=line_range,
                ),
                border_style="dim",
            )
        )
    elif cell.cell_type == "markdown":
        parts.append(
            Markdown(
                source,
                code_theme=config.theme,
                hyperlinks=config.hyperlinks,
            )
        )
    elif cell.cell_type == "raw":
        parts.append(Text(source))
    else:
        if config.strict:
            raise UnknownCellTypeError(
                f"unknown cell type {cell.cell_type!r}; expected one of "
                f"{sorted(KNOWN_CELL_TYPES)}"
            )
        parts.append(Text(source))

    new_line = True
    for output in cell.outputs:
        if output.output_type == "stream":
            parts.append(Text.from_ansi("".join(output.text)))
            new_line = False
        elif output.output_type == "error":
            parts.append(
                Text.from_ansi("\n".join(output.traceback).rstrip())
            )
            new_line = True
        elif output.output_type == "execute_result":
            exec_count = (output.execution_count or " ") or " "
            header: RenderableType = Text.from_markup(
                f"[red]Out[[#ee4b2b]{exec_count}[/#ee4b2b]]:[/red]\n"
            )
            data = output.data.get("text/plain", "")
            if isinstance(data, list):
                renderable = Group(header, Text.from_ansi("".join(data)))
            else:
                renderable = Group(header, Text.from_ansi(data))
            parts.append(renderable)
            new_line = True
        elif output.output_type == "display_data":
            data = output.data.get("text/plain", "")
            if isinstance(data, list):
                parts.append(Text.from_ansi("".join(data)))
            else:
                parts.append(Text.from_ansi(data))
            new_line = True
        else:
            if config.strict:
                raise UnknownOutputTypeError(
                    f"unknown output type {output.output_type!r}; expected one of "
                    f"{sorted(KNOWN_OUTPUT_TYPES)}"
                )
            continue

    if not new_line:
        parts.append("")

    return parts


def render_notebook(
    notebook: Notebook, config: RenderConfig
) -> RenderableType:
    """Render a fully-filtered/transformed ``Notebook`` to Rich.

    Raises:
        EmptyNotebookError: if the notebook has no cells to render.
        UnknownCellTypeError: if ``config.strict`` is True and an unknown
            cell type is encountered.
        UnknownOutputTypeError: if ``config.strict`` is True and an unknown
            output type is encountered.
    """

    if notebook.is_empty:
        raise EmptyNotebookError(
            "cannot render a notebook with no cells; check your filters"
        )

    cells: List[RenderableType] = []
    for cell in notebook.cells:
        cells.extend(_render_cell(cell, config))
    return Group(*cells)


# ---------------------------------------------------------------------------
# Public convenience API (preserves the original CLI signature)
# ---------------------------------------------------------------------------


def render_ipynb(
    resource: str,
    theme: str,
    hyperlinks: bool,
    lexer: Optional[str] = None,
    head: Optional[int] = None,
    tail: Optional[int] = None,
    line_numbers: bool = False,
    guides: bool = False,
    no_wrap: bool = True,
    cell_types: Optional[str] = None,
    cell_range: Optional[str] = None,
    include_outputs: bool = True,
) -> RenderableType:
    """Render a Jupyter notebook resource as a Rich renderable.

    This is a thin convenience wrapper that drives the four-layer pipeline:

        parse_notebook -> filter_notebook -> transform_notebook -> render_notebook

    All lower-level exceptions are either caught and re-raised as structured
    ``NotebookError`` subclasses or allowed to propagate as ``NotebookError``
    so callers can handle errors uniformly.

    ``read_resource`` is imported lazily from ``__main__`` to avoid a circular
    import at module load time.

    Args:
        resource: Path to the notebook file.
        theme: Syntax highlighting theme for code cells.
        hyperlinks: Whether to render hyperlinks in Markdown cells.
        lexer: Override lexer for code cells (defaults to notebook language).
        head: Show first N lines of each code cell.
        tail: Show last N lines of each code cell.
        line_numbers: Show line numbers in code cells.
        guides: Show indentation guides in code cells.
        no_wrap: Disable word wrapping in code cells.
        cell_types: Comma-separated cell types to filter (e.g. "code,markdown").
        cell_range: Cell range string (1-based, inclusive, e.g. "1-5", "3-", "-10").
        include_outputs: If False, hide all cell outputs.
    """

    try:
        from . import __main__ as _main

        notebook_str, _ = _main.read_resource(resource, None)

        notebook = parse_notebook(notebook_str)

        notebook = filter_notebook(
            notebook,
            FilterConfig.from_cli(
                cell_types=cell_types,
                cell_range=cell_range,
                include_outputs=include_outputs,
            ),
        )

        notebook = transform_notebook(
            notebook,
            TransformConfig(
                lexer=lexer,
                head=head,
                tail=tail,
                line_numbers=line_numbers,
                guides=guides,
                no_wrap=no_wrap,
            ),
        )

        return render_notebook(
            notebook,
            RenderConfig(
                theme=theme,
                hyperlinks=hyperlinks,
                line_numbers=line_numbers,
                guides=guides,
                no_wrap=no_wrap,
            ),
        )
    except NotebookError:
        raise
    except Exception as exc:
        raise NotebookError(
            f"unexpected error while rendering notebook: {exc}", cause=exc
        ) from exc
