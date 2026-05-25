from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from rich.console import RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from .markdown import Markdown


class NotebookError(Exception):
    """Base exception for notebook-related errors."""


class InvalidNotebookError(NotebookError):
    """Raised when the notebook data is invalid or malformed."""


class MissingCellsError(InvalidNotebookError):
    """Raised when the notebook is missing the required 'cells' field."""


class InvalidCellRangeError(NotebookError):
    """Raised when a cell range string is invalid."""


class CellRangeOutOfBoundsError(NotebookError):
    """Raised when a cell range exceeds the number of cells in the notebook."""


class NoCellsFoundError(NotebookError):
    """Raised when filtering results in no cells to display."""


@dataclass
class CellOutput:
    output_type: str
    content: str
    execution_count: Optional[str] = None


@dataclass
class NotebookCell:
    cell_type: str
    source: str
    execution_count: Optional[str] = None
    outputs: List[CellOutput] = field(default_factory=list)


@dataclass
class Notebook:
    cells: List[NotebookCell]
    language: str = ""


def parse_cell_range(cell_range: str) -> Tuple[int, int]:
    """Parse cell range string like '3' or '2-5' into (start, end) indices (1-based, inclusive).

    Args:
        cell_range: Range string, e.g. '3' for first 3 cells, '2-5' for cells 2-5.

    Returns:
        Tuple of (start_index, end_index) 1-based, inclusive.

    Raises:
        InvalidCellRangeError: If the range string is malformed.
    """
    if "-" in cell_range:
        parts = cell_range.split("-", 1)
        try:
            start = int(parts[0])
            end = int(parts[1])
        except ValueError:
            raise InvalidCellRangeError(
                f"invalid cell range: {cell_range!r} (expected format 'N' or 'M-N', e.g. '3' or '2-5')"
            )
    else:
        try:
            end = int(cell_range)
            start = 1
        except ValueError:
            raise InvalidCellRangeError(
                f"invalid cell range: {cell_range!r} (expected format 'N' or 'M-N', e.g. '3' or '2-5')"
            )
    if start < 1:
        raise InvalidCellRangeError(
            f"invalid cell range: {cell_range!r} (start index must be >= 1)"
        )
    if end < start:
        raise InvalidCellRangeError(
            f"invalid cell range: {cell_range!r} (end index must be >= start index)"
        )
    return start, end


def parse_notebook(notebook_dict: Dict[str, Any]) -> Notebook:
    """Parse a notebook dictionary into a Notebook data structure.

    Args:
        notebook_dict: Parsed JSON dictionary from .ipynb file.

    Returns:
        Notebook object with parsed cells and metadata.

    Raises:
        MissingCellsError: If the notebook dict has no 'cells' field.
        InvalidNotebookError: If cell data is malformed.
    """
    if "cells" not in notebook_dict:
        raise MissingCellsError(
            "notebook is missing required 'cells' field (not a valid .ipynb file)"
        )

    if not isinstance(notebook_dict["cells"], list):
        raise InvalidNotebookError(
            "'cells' field must be a list (not a valid .ipynb file)"
        )

    language = notebook_dict.get("metadata", {}).get("kernelspec", {}).get("language", "")

    cells: List[NotebookCell] = []
    for cell_idx, cell_data in enumerate(notebook_dict["cells"], start=1):
        if not isinstance(cell_data, dict):
            raise InvalidNotebookError(
                f"cell {cell_idx} is not a valid object (not a valid .ipynb file)"
            )

        if "cell_type" not in cell_data:
            raise InvalidNotebookError(
                f"cell {cell_idx} is missing required 'cell_type' field"
            )

        if "source" not in cell_data:
            raise InvalidNotebookError(
                f"cell {cell_idx} is missing required 'source' field"
            )

        cell_type = cell_data["cell_type"]
        source_data = cell_data["source"]

        if isinstance(source_data, list):
            source = "".join(source_data)
        elif isinstance(source_data, str):
            source = source_data
        else:
            raise InvalidNotebookError(
                f"cell {cell_idx}: 'source' must be a string or list of strings"
            )

        execution_count = cell_data.get("execution_count")
        if execution_count is not None:
            execution_count = str(execution_count)

        outputs: List[CellOutput] = []
        cell_outputs = cell_data.get("outputs", [])

        if not isinstance(cell_outputs, list):
            raise InvalidNotebookError(
                f"cell {cell_idx}: 'outputs' must be a list"
            )

        for output_data in cell_outputs:
            if not isinstance(output_data, dict):
                continue
            if "output_type" not in output_data:
                continue

            output_type = output_data["output_type"]
            try:
                if output_type == "stream":
                    text_data = output_data.get("text", "")
                    if isinstance(text_data, list):
                        content = "".join(text_data)
                    else:
                        content = str(text_data)
                    outputs.append(CellOutput(output_type=output_type, content=content))
                elif output_type == "error":
                    traceback_data = output_data.get("traceback", [])
                    if isinstance(traceback_data, list):
                        content = "\n".join(traceback_data).rstrip()
                    else:
                        content = str(traceback_data)
                    outputs.append(CellOutput(output_type=output_type, content=content))
                elif output_type == "execute_result":
                    exec_count = output_data.get("execution_count", " ") or " "
                    data_field = output_data.get("data", {})
                    if not isinstance(data_field, dict):
                        data_field = {}
                    plain_data = data_field.get("text/plain", "")
                    if isinstance(plain_data, list):
                        content = "".join(plain_data)
                    else:
                        content = str(plain_data)
                    outputs.append(
                        CellOutput(
                            output_type=output_type,
                            content=content,
                            execution_count=str(exec_count),
                        )
                    )
            except Exception:
                continue

        cells.append(
            NotebookCell(
                cell_type=cell_type,
                source=source,
                execution_count=execution_count,
                outputs=outputs,
            )
        )

    return Notebook(cells=cells, language=language)


def filter_cells(
    notebook: Notebook,
    cell_type: str = "all",
    cell_range: Optional[str] = None,
) -> List[NotebookCell]:
    """Filter notebook cells by type and/or range.

    Args:
        notebook: The notebook to filter.
        cell_type: Filter by cell type: 'all', 'code', or 'markdown'.
        cell_range: Optional range string like '3' or '2-5'.

    Returns:
        List of filtered NotebookCell objects.

    Raises:
        CellRangeOutOfBoundsError: If the range exceeds the number of cells.
        InvalidCellRangeError: If the range string is malformed.
    """
    cells = notebook.cells
    total_cells = len(cells)

    if cell_range is not None:
        start_idx, end_idx = parse_cell_range(cell_range)
        if total_cells == 0:
            raise CellRangeOutOfBoundsError(
                f"cell range {cell_range!r} is out of bounds: notebook has no cells"
            )
        if start_idx > total_cells:
            raise CellRangeOutOfBoundsError(
                f"cell range {cell_range!r} is out of bounds: "
                f"notebook has {total_cells} cell{'s' if total_cells != 1 else ''}"
            )
        if end_idx > total_cells:
            raise CellRangeOutOfBoundsError(
                f"cell range {cell_range!r} is out of bounds: "
                f"notebook has {total_cells} cell{'s' if total_cells != 1 else ''}, "
                f"end index {end_idx} is too large"
            )
        cells = [
            cell
            for idx, cell in enumerate(cells, start=1)
            if start_idx <= idx <= end_idx
        ]

    if cell_type != "all":
        cells = [cell for cell in cells if cell.cell_type == cell_type]

    return cells


def _line_range(
    head: Optional[int], tail: Optional[int], num_lines: int
) -> Optional[Tuple[int, int]]:
    """Calculate line range for syntax highlighting within a cell.

    Args:
        head: Number of lines to show from the start.
        tail: Number of lines to show from the end.
        num_lines: Total number of lines in the cell.

    Returns:
        Tuple of (start_line, end_line) or None if no range is specified.

    Raises:
        ValueError: If both head and tail are specified.
    """
    if head and tail:
        raise ValueError("cannot specify both head and tail")
    if head:
        line_range = (1, head)
    elif tail:
        start_line = num_lines - tail + 2
        finish_line = num_lines + 1
        line_range = (start_line, finish_line)
    else:
        line_range = None
    return line_range


def render_cell(
    cell: NotebookCell,
    theme: str,
    hyperlinks: bool,
    lexer: str,
    head: Optional[int],
    tail: Optional[int],
    line_numbers: bool,
    guides: bool,
    no_wrap: bool,
    no_output: bool,
) -> List[RenderableType]:
    """Render a single notebook cell to renderables.

    Args:
        cell: The notebook cell to render.
        theme: Syntax theme for code cells.
        hyperlinks: Whether to render hyperlinks in Markdown cells.
        lexer: Lexer for code cell syntax highlighting.
        head: Display first `head` lines of each cell.
        tail: Display last `tail` lines of each cell.
        line_numbers: Enable line number in code cells.
        guides: Enable indentation guides in code cell syntax highlighting.
        no_wrap: Don't word wrap syntax highlighted cells.
        no_output: Hide execution outputs.

    Returns:
        List of renderable elements for this cell.
    """
    renderables: List[RenderableType] = []

    if cell.execution_count is not None:
        execution_count = cell.execution_count or " "
        renderables.append(f"[green]In [[#66ff00]{execution_count}[/#66ff00]]:[/green]")

    source = cell.source
    if cell.cell_type == "code":
        num_lines = len(source.splitlines())
        try:
            line_range = _line_range(head, tail, num_lines)
        except ValueError:
            line_range = None
        renderable = Panel(
            Syntax(
                source,
                lexer,
                theme=theme,
                line_numbers=line_numbers,
                indent_guides=guides,
                word_wrap=not no_wrap,
                line_range=line_range,
            ),
            border_style="dim",
        )
    elif cell.cell_type == "markdown":
        renderable = Markdown(source, code_theme=theme, hyperlinks=hyperlinks)
    else:
        renderable = Text(source)

    renderables.append(renderable)

    if not no_output:
        for output in cell.outputs:
            if output.output_type == "stream":
                renderables.append(Text.from_ansi(output.content))
            elif output.output_type == "error":
                renderables.append(Text.from_ansi(output.content))
            elif output.output_type == "execute_result":
                exec_count = output.execution_count or " "
                out_renderable = Text.from_markup(
                    f"[red]Out[[#ee4b2b]{exec_count}[/#ee4b2b]]:[/red]\n"
                )
                out_renderable += Text.from_ansi(output.content)
                renderables.append(out_renderable)

    return renderables


def render_notebook(
    notebook: Notebook,
    theme: str,
    hyperlinks: bool,
    lexer: str,
    head: Optional[int],
    tail: Optional[int],
    line_numbers: bool,
    guides: bool,
    no_wrap: bool,
    cell_type: str = "all",
    cell_range: Optional[str] = None,
    no_output: bool = False,
) -> RenderableType:
    """Render a notebook to a renderable.

    Args:
        notebook: The notebook to render.
        theme: Syntax theme for code cells.
        hyperlinks: Whether to render hyperlinks in Markdown cells.
        lexer: Lexer for code cell syntax highlighting (if no language set in notebook).
        head: Display first `head` lines of each cell.
        tail: Display last `tail` lines of each cell.
        line_numbers: Enable line number in code cells.
        guides: Enable indentation guides in code cell syntax highlighting.
        no_wrap: Don't word wrap syntax highlighted cells.
        cell_type: Filter cells by type ('all', 'code', 'markdown').
        cell_range: Optional cell range to display, e.g. '3' or '2-5'.
        no_output: Hide execution outputs.

    Returns:
        RenderableType: Notebook as a Group renderable.

    Raises:
        NoCellsFoundError: If filtering results in no cells to display.
        CellRangeOutOfBoundsError: If the range exceeds the number of cells.
        InvalidCellRangeError: If the range string is malformed.
    """
    from rich.console import Group

    lexer = lexer or notebook.language

    filtered_cells = filter_cells(notebook, cell_type, cell_range)

    if not filtered_cells:
        total = len(notebook.cells)
        range_info = f" in range {cell_range!r}" if cell_range else ""
        type_info = f" of type {cell_type!r}" if cell_type != "all" else ""
        raise NoCellsFoundError(
            f"no cells to display{range_info}{type_info}; "
            f"notebook has {total} cell{'s' if total != 1 else ''} total"
        )

    all_renderables: List[RenderableType] = []
    new_line = True
    for cell in filtered_cells:
        if new_line:
            all_renderables.append("")
        cell_renderables = render_cell(
            cell,
            theme,
            hyperlinks,
            lexer,
            head,
            tail,
            line_numbers,
            guides,
            no_wrap,
            no_output,
        )
        all_renderables.extend(cell_renderables)
        new_line = bool(cell.outputs) and not no_output and cell.outputs[-1].output_type in ("error", "execute_result")

    return Group(*all_renderables)
