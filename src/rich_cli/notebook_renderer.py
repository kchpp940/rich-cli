import json
from typing import TYPE_CHECKING, List, Optional

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from .markdown import Markdown
from .resource_reader import read_resource

if TYPE_CHECKING:
    from .renderer_registry import RenderOptions


def render_ipynb(resource: str, opts: "RenderOptions") -> RenderableType:
    """Render resource as a Jupyter notebook."""
    notebook_str, _ = read_resource(resource, None)
    notebook_dict = json.loads(notebook_str)
    lexer = opts.lexer or notebook_dict.get("metadata", {}).get(
        "kernelspec", {}
    ).get("language", "")

    cells: List[RenderableType] = []
    new_line = True

    for cell in notebook_dict["cells"]:
        if new_line:
            cells.append("")

        if "execution_count" in cell:
            execution_count = cell["execution_count"] or " "
            cells.append(
                f"[green]In [[#66ff00]{execution_count}[/#66ff00]]:[/green]"
            )

        source = "".join(cell["source"])

        if cell["cell_type"] == "code":
            num_lines = len(source.splitlines())
            line_range = opts._line_range(num_lines)
            renderable = Panel(
                Syntax(
                    source,
                    lexer,
                    theme=opts.theme,
                    line_numbers=opts.line_numbers,
                    indent_guides=opts.guides,
                    word_wrap=not opts.no_wrap,
                    line_range=line_range,
                ),
                border_style="dim",
            )
        elif cell["cell_type"] == "markdown":
            renderable = Markdown(
                source, code_theme=opts.theme, hyperlinks=opts.hyperlinks
            )
        else:
            renderable = Text(source)

        new_line = True
        cells.append(renderable)

        for output in cell.get("outputs", []):
            output_type = output["output_type"]
            if output_type == "stream":
                renderable = Text.from_ansi("".join(output["text"]))
                new_line = False
            elif output_type == "error":
                renderable = Text.from_ansi("\n".join(output["traceback"]).rstrip())
                new_line = True
            elif output_type == "execute_result":
                execution_count = output.get("execution_count", " ") or " "
                renderable = Text.from_markup(
                    f"[red]Out[[#ee4b2b]{execution_count}[/#ee4b2b]]:[/red]\n"
                )
                data = output["data"].get("text/plain", "")
                if isinstance(data, list):
                    renderable += Text.from_ansi("".join(data))
                else:
                    renderable += Text.from_ansi(data)
                new_line = True
            else:
                continue

            cells.append(renderable)

    return Group(*cells)
