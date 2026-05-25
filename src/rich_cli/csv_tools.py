from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import csv
import io
import re


IS_NUMBER_RE = re.compile(r"\-?[0-9]*?\.?[0-9]*?").fullmatch


class CsvError(Exception):
    """Base class for CSV processing errors."""

    pass


class CsvParameterError(CsvError):
    """Raised when CSV parameters are invalid."""

    pass


@dataclass
class CsvData:
    """Container for parsed CSV data."""

    header: Optional[List[str]] = None
    rows: List[List[str]] = field(default_factory=list)

    @property
    def num_cols(self) -> int:
        if self.header is not None:
            header_cols = len(self.header)
        else:
            header_cols = 0
        if self.rows:
            row_cols = max(len(row) for row in self.rows)
        else:
            row_cols = 0
        return max(header_cols, row_cols)

    @property
    def has_header(self) -> bool:
        return self.header is not None


def truncate(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    if max_len <= 3:
        return value[:max_len]
    return value[: max_len - 3] + "..."


def _parse_col_spec_to_indices(
    spec: str, csv_data: CsvData
) -> List[int]:
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    indices: List[int] = []
    name_to_idx = {}
    if csv_data.header is not None:
        name_to_idx = {name.lower(): i for i, name in enumerate(csv_data.header)}
    num_cols = csv_data.num_cols
    for part in parts:
        if part.isdigit():
            idx = int(part)
            if 0 <= idx < num_cols:
                indices.append(idx)
            else:
                raise CsvParameterError(
                    f"column index {idx} out of range (0-{num_cols - 1})"
                )
        else:
            if csv_data.header is None:
                raise CsvParameterError(
                    f"cannot use column name '{part}' — CSV has no header row"
                )
            idx = name_to_idx.get(part.lower())
            if idx is None:
                raise CsvParameterError(
                    f"column '{part}' not found; available columns: {', '.join(csv_data.header)}"
                )
            indices.append(idx)
    return indices


def load_csv_data(
    resource: str,
    resource_name: str,
    csv_data_reader,
) -> CsvData:
    csv_text, _ = csv_data_reader(resource, "csv")
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(csv_text[:1024], delimiters=",\t|;")
        has_header = sniffer.has_header(csv_text[:1024])
    except csv.Error as error:
        name_lower = resource_name.lower()
        if name_lower.endswith(".csv"):
            dialect = csv.get_dialect("excel")
            has_header = True
        elif name_lower.endswith(".tsv"):
            dialect = csv.get_dialect("excel-tab")
            has_header = True
        else:
            raise CsvError(str(error))

    csv_file = io.StringIO(csv_text)
    reader = csv.reader(csv_file, dialect=dialect)
    rows_iter = iter(reader)

    header: Optional[List[str]] = None
    if has_header:
        try:
            header = next(rows_iter)
        except StopIteration:
            header = None

    rows = [row for row in rows_iter if row]
    return CsvData(header=header, rows=rows)


def select_columns(csv_data: CsvData, col_spec: str) -> List[int]:
    return _parse_col_spec_to_indices(col_spec, csv_data)


def detect_empty_columns(csv_data: CsvData) -> List[int]:
    num_cols = csv_data.num_cols
    non_empty: List[int] = []
    for col_idx in range(num_cols):
        has_value = False
        for row in csv_data.rows:
            if col_idx < len(row) and row[col_idx].strip():
                has_value = True
                break
        if has_value:
            non_empty.append(col_idx)
    return non_empty


def sort_rows(
    csv_data: CsvData,
    sort_spec: str,
) -> Tuple[List[List[str]], int]:
    reverse = False
    col_ident = sort_spec
    if col_ident.startswith("~"):
        reverse = True
        col_ident = col_ident[1:]

    sort_idx: Optional[int] = None
    if col_ident.isdigit():
        sort_idx = int(col_ident)
        num_cols = csv_data.num_cols
        if not (0 <= sort_idx < num_cols):
            raise CsvParameterError(
                f"sort column index {sort_idx} out of range (0-{num_cols - 1})"
            )
    else:
        if csv_data.header is None:
            raise CsvParameterError(
                f"cannot use column name '{col_ident}' — CSV has no header row"
            )
        name_to_idx = {name.lower(): i for i, name in enumerate(csv_data.header)}
        sort_idx = name_to_idx.get(col_ident.lower())
        if sort_idx is None:
            raise CsvParameterError(
                f"sort column '{col_ident}' not found; available columns: {', '.join(csv_data.header)}"
            )

    def _sort_key(row: List[str]) -> Tuple[int, str]:
        value = row[sort_idx] if sort_idx < len(row) else ""
        stripped = value.strip()
        if IS_NUMBER_RE(stripped):
            try:
                return (0, f"{float(stripped):030.10f}")
            except ValueError:
                pass
        return (1, stripped)

    sorted_rows = sorted(csv_data.rows, key=_sort_key, reverse=reverse)
    return sorted_rows, sort_idx


def truncate_rows(
    rows: List[List[str]],
    col_indices: List[int],
    max_col_width: int,
) -> List[List[str]]:
    result: List[List[str]] = []
    for row in rows:
        new_row: List[str] = []
        for idx in col_indices:
            if idx < len(row):
                cell = truncate(row[idx], max_col_width)
            else:
                cell = ""
            new_row.append(cell)
        result.append(new_row)
    return result


def is_numeric_column(csv_data: CsvData, col_idx: int) -> bool:
    for row in csv_data.rows:
        try:
            if col_idx < len(row):
                value = row[col_idx]
                if value and not IS_NUMBER_RE(value):
                    return False
        except Exception:
            return False
    return True


def apply_head_tail(
    rows: List[List[str]],
    head: Optional[int],
    tail: Optional[int],
) -> List[List[str]]:
    if head is not None:
        return rows[:head]
    elif tail is not None:
        return rows[-tail:]
    return rows


@dataclass
class CsvView:
    """Prepared view data ready for rendering."""

    header: Optional[List[str]] = None
    rows: List[List[str]] = field(default_factory=list)
    numeric_cols: List[int] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def prepare_csv_view(
    csv_data: CsvData,
    head: Optional[int] = None,
    tail: Optional[int] = None,
    csv_cols: Optional[str] = None,
    csv_max_col_width: Optional[int] = None,
    csv_hide_empty: bool = False,
    csv_sort: Optional[str] = None,
) -> CsvView:
    working_data = CsvData(header=csv_data.header, rows=list(csv_data.rows))

    if csv_sort is not None:
        sorted_rows, _sort_idx = sort_rows(csv_data, csv_sort)
        working_data.rows = sorted_rows

    keep_indices: Optional[List[int]] = None

    if csv_cols is not None:
        keep_indices = select_columns(csv_data, csv_cols)

    if csv_hide_empty:
        non_empty = detect_empty_columns(csv_data)
        if keep_indices is None:
            keep_indices = non_empty
        else:
            keep_indices = [i for i in keep_indices if i in non_empty]

    if keep_indices is None:
        keep_indices = list(range(csv_data.num_cols))

    working_data.rows = apply_head_tail(working_data.rows, head, tail)

    numeric_cols: List[int] = []
    for display_idx, data_idx in enumerate(keep_indices):
        if is_numeric_column(csv_data, data_idx):
            numeric_cols.append(display_idx)

    max_width = (
        csv_max_col_width
        if (csv_max_col_width is not None and csv_max_col_width > 0)
        else None
    )

    if max_width is not None:
        display_rows = truncate_rows(working_data.rows, keep_indices, max_width)
    else:
        display_rows = []
        for row in working_data.rows:
            display_row = []
            for idx in keep_indices:
                display_row.append(row[idx] if idx < len(row) else "")
            display_rows.append(display_row)

    display_header: Optional[List[str]] = None
    if csv_data.header is not None:
        display_header = [
            csv_data.header[i] if i < len(csv_data.header) else "" for i in keep_indices
        ]

    return CsvView(
        header=display_header,
        rows=display_rows,
        numeric_cols=numeric_cols,
        warnings=[],
    )
