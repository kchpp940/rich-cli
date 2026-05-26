from dataclasses import dataclass, field
from operator import itemgetter
import csv
import io
import re
from typing import Any, Callable, List, Optional, Tuple

from rich.console import RenderableType
from rich import box
from rich.table import Table

is_number = re.compile(r"\-?[0-9]*?\.?[0-9]*?").fullmatch


def _get_on_error() -> Callable[..., Any]:
    from .__main__ import on_error
    return on_error


def _get_read_resource() -> Callable[..., Any]:
    from .__main__ import read_resource
    return read_resource


@dataclass
class CsvPipelineOptions:
    head: Optional[int] = None
    tail: Optional[int] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    columns: Optional[List[int]] = None
    sort_column: Optional[int] = None
    sort_reverse: bool = False
    filter_empty_columns: bool = True
    max_cell_width: Optional[int] = None


@dataclass
class CsvPipelineResult:
    header: List[str]
    rows: List[List[str]]
    numeric_columns: List[int] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def detect_dialect_and_header(
    csv_data: str, resource: str
) -> Tuple[Any, bool]:
    sniffer = csv.Sniffer()
    dialect: Any
    try:
        dialect = sniffer.sniff(csv_data[:1024], delimiters=",\t|;")
        has_header = sniffer.has_header(csv_data[:1024])
    except csv.Error as error:
        if resource.lower().endswith(".csv"):
            dialect = csv.get_dialect("excel")
            has_header = True
        elif resource.lower().endswith(".tsv"):
            dialect = csv.get_dialect("excel-tab")
            has_header = True
        else:
            _get_on_error()(str(error))
    return dialect, has_header


def parse_csv_data(
    csv_data: str, dialect: Any, has_header: bool
) -> Tuple[List[str], List[List[str]]]:
    csv_file = io.StringIO(csv_data)
    reader = csv.reader(csv_file, dialect=dialect)
    rows_iter = iter(reader)

    header: List[str] = []
    if has_header:
        try:
            header = next(rows_iter)
        except StopIteration:
            header = []

    rows: List[List[str]] = [row for row in rows_iter if row]
    return header, rows


def normalize_header(
    header: List[str], rows: List[List[str]]
) -> Tuple[List[str], List[List[str]]]:
    if not rows:
        return header, rows

    num_cols = max(len(header), max((len(row) for row in rows), default=0))

    if not header:
        header = [f"col{i}" for i in range(num_cols)]

    if len(header) < num_cols:
        header = header + [f"col{i}" for i in range(len(header), num_cols)]

    normalized_rows = [
        row + [""] * (num_cols - len(row)) if len(row) < num_cols else row
        for row in rows
    ]

    return header, normalized_rows


def filter_empty_columns(
    header: List[str], rows: List[List[str]]
) -> Tuple[List[str], List[List[str]]]:
    if not rows:
        return header, rows

    num_cols = max(len(header), max((len(row) for row in rows), default=0))
    non_empty_cols: List[int] = []

    for col_idx in range(num_cols):
        has_data = False
        if col_idx < len(header) and header[col_idx].strip():
            has_data = True
        else:
            for row in rows:
                if col_idx < len(row) and row[col_idx].strip():
                    has_data = True
                    break
        if has_data:
            non_empty_cols.append(col_idx)

    new_header = [header[i] if i < len(header) else "" for i in non_empty_cols]
    new_rows = [
        [row[i] if i < len(row) else "" for i in non_empty_cols] for row in rows
    ]
    return new_header, new_rows


def select_columns(
    header: List[str], rows: List[List[str]], columns: List[int]
) -> Tuple[List[str], List[List[str]]]:
    if not columns:
        return header, rows

    valid_cols = [
        c for c in columns if c >= 0 and (c < len(header) or any(c < len(row) for row in rows))
    ]
    if not valid_cols:
        return header, rows

    new_header = [header[c] if c < len(header) else f"col{c}" for c in valid_cols]
    new_rows = [[row[c] if c < len(row) else "" for c in valid_cols] for row in rows]
    return new_header, new_rows


def sort_rows(
    header: List[str], rows: List[List[str]], sort_column: int, reverse: bool = False
) -> List[List[str]]:
    if not rows or sort_column < 0:
        return rows

    max_col = max((len(row) for row in rows), default=0)
    if sort_column >= max(len(header), max_col):
        return rows

    get_index = itemgetter(sort_column)

    def sort_key(row: List[str]) -> str:
        return get_index(row) if sort_column < len(row) else ""

    sorted_rows = sorted(rows, key=sort_key, reverse=reverse)
    return sorted_rows


def truncate_cell_width(
    header: List[str], rows: List[List[str]], max_width: int
) -> Tuple[List[str], List[List[str]]]:
    if max_width is None or max_width <= 0:
        return header, rows

    truncate: Callable[[str], str] = lambda s: s[:max_width] + "..." if len(s) > max_width else s
    new_header = [truncate(h) for h in header]
    new_rows = [[truncate(cell) for cell in row] for row in rows]
    return new_header, new_rows


def apply_head_tail(
    rows: List[List[str]], head: Optional[int], tail: Optional[int]
) -> List[List[str]]:
    if head is not None:
        rows = rows[:head]
    elif tail is not None:
        rows = rows[-tail:]
    return rows


def detect_numeric_columns(
    header: List[str], rows: List[List[str]]
) -> List[int]:
    if not rows:
        return []

    num_cols = max(len(header), max((len(row) for row in rows), default=0))
    numeric_cols: List[int] = []

    for col_idx in range(num_cols):
        is_numeric = True
        for row in rows:
            if col_idx < len(row):
                value = row[col_idx]
                if value and not is_number(value):
                    is_numeric = False
                    break
        if is_numeric:
            numeric_cols.append(col_idx)

    return numeric_cols


def run_csv_pipeline(
    csv_data: str, resource: str, options: CsvPipelineOptions,
) -> CsvPipelineResult:
    dialect, has_header = detect_dialect_and_header(csv_data, resource)

    header, rows = parse_csv_data(csv_data, dialect, has_header)

    header, rows = normalize_header(header, rows)

    if options.sort_column is not None:
        rows = sort_rows(header, rows, options.sort_column, options.sort_reverse)

    if options.columns:
        header, rows = select_columns(header, rows, options.columns)

    if options.filter_empty_columns:
        header, rows = filter_empty_columns(header, rows)

    rows = apply_head_tail(rows, options.head, options.tail)

    numeric_columns = detect_numeric_columns(header, rows)

    if options.max_cell_width is not None:
        header, rows = truncate_cell_width(header, rows, options.max_cell_width)

    return CsvPipelineResult(
        header=header,
        rows=rows,
        numeric_columns=numeric_columns,
    )


def render_csv_table(
    result: CsvPipelineResult,
    has_header: bool = True,
    title: Optional[str] = None,
    caption: Optional[str] = None,
) -> Table:
    table = Table(
        show_header=has_header,
        box=box.HEAVY_HEAD if has_header else box.SQUARE,
        border_style="blue",
        title=title,
        caption=caption,
        caption_justify="right",
    )

    for column in result.header:
        table.add_column(column)

    for row in result.rows:
        table.add_row(*row)

    for col_idx in result.numeric_columns:
        if col_idx < len(table.columns):
            table_column = table.columns[col_idx]
            table_column.justify = "right"
            table_column.style = "bold green"
            table_column.header_style = "bold green"

    return table


def render_csv(
    resource: str,
    head: Optional[int] = None,
    tail: Optional[int] = None,
    title: Optional[str] = None,
    caption: Optional[str] = None,
) -> RenderableType:
    csv_data, _ = _get_read_resource()(resource, "csv")
    options = CsvPipelineOptions(
        head=head,
        tail=tail,
    )
    result = run_csv_pipeline(csv_data, resource, options)

    _dialect, has_header = detect_dialect_and_header(csv_data, resource)

    return render_csv_table(result, has_header=has_header, title=title, caption=caption)
