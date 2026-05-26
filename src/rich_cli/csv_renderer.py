import csv
import io
import re
from operator import itemgetter
from typing import TYPE_CHECKING

from rich import box
from rich.console import RenderableType
from rich.table import Table

from .renderer_registry import on_error
from .resource_reader import read_resource

if TYPE_CHECKING:
    from .renderer_registry import RenderOptions


def render_csv(resource: str, opts: "RenderOptions") -> RenderableType:
    """Render resource as a CSV table."""
    is_number = re.compile(r"\-?[0-9]*?\.?[0-9]*?").fullmatch

    csv_data, _ = read_resource(resource, "csv")
    sniffer = csv.Sniffer()
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
            on_error(str(error))

    csv_file = io.StringIO(csv_data)
    reader = csv.reader(csv_file, dialect=dialect)

    table = Table(
        show_header=has_header,
        box=box.HEAVY_HEAD if has_header else box.SQUARE,
        border_style="blue",
        title=opts.title or None,
        caption=opts.caption or None,
        caption_justify="right",
    )
    rows = iter(reader)
    if has_header:
        header = next(rows)
        for column in header:
            table.add_column(column)

    table_rows = [row for row in rows if row]
    if opts.head is not None:
        table_rows = table_rows[: opts.head]
    elif opts.tail is not None:
        table_rows = table_rows[-opts.tail :]
    for row in table_rows:
        if row:
            table.add_row(*row)

    for index, table_column in enumerate(table.columns):
        get_index = itemgetter(index)
        for row in table_rows:
            try:
                value = get_index(row)
                if value and not is_number(value):
                    break
            except Exception:
                break
        else:
            table_column.justify = "right"
            table_column.style = "bold green"
            table_column.header_style = "bold green"

    return table
