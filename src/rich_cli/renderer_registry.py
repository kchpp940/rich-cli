import sys
from dataclasses import dataclass
from typing import Callable, Dict, Optional, TYPE_CHECKING

from rich.console import Console, RenderableType
from rich.json import JSON as RichJSON
from rich.rule import Rule
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text

from .markdown import Markdown
from .resource_reader import detect_format_from_extension, read_resource

if TYPE_CHECKING:
    from rich.console import Console as ConsoleType

AUTO = 0
SYNTAX = 1
PRINT = 2
MARKDOWN = 3
RST = 4
JSON = 5
RULE = 6
INSPECT = 7
CSV = 8
IPYNB = 9

error_console = Console(stderr=True)


def on_error(message: str, error: Optional[Exception] = None, code: int = -1) -> None:
    """Render an error message then exit the app."""
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


@dataclass
class RenderOptions:
    """Options for rendering a resource."""
    theme: str = "ansi_dark"
    hyperlinks: bool = False
    lexer: Optional[str] = None
    head: Optional[int] = None
    tail: Optional[int] = None
    line_numbers: bool = False
    guides: bool = False
    no_wrap: bool = True
    emoji: bool = False
    text_justify: str = "default"
    rule_style: str = "bright_green"
    rule_char: str = "─"
    title: str = ""
    caption: str = ""

    def _line_range(self, num_lines: int) -> Optional[tuple[int, int]]:
        if self.head and self.tail:
            on_error("cannot specify both head and tail")
        if self.head:
            return (1, self.head)
        elif self.tail:
            return (num_lines - self.tail + 2, num_lines + 1)
        return None


def determine_format(
    resource: str,
    _print: bool = False,
    syntax: bool = False,
    rule: bool = False,
    json: bool = False,
    markdown: bool = False,
    rst: bool = False,
    csv: bool = False,
    ipynb: bool = False,
    inspect: bool = False,
) -> int:
    """Determine the format type based on CLI flags and resource extension."""
    if _print:
        return PRINT
    elif syntax:
        return SYNTAX
    elif json:
        return JSON
    elif markdown:
        return MARKDOWN
    elif rule:
        return RULE
    elif inspect:
        return INSPECT
    elif csv:
        return CSV
    elif rst:
        return RST
    elif ipynb:
        return IPYNB

    if "." in resource:
        detected_format = detect_format_from_extension(resource)
        if detected_format is not None:
            return detected_format

    return SYNTAX


def get_format_name(format_type: int) -> str:
    """Get the name of a format type for debugging."""
    names = {
        SYNTAX: "syntax",
        PRINT: "print",
        MARKDOWN: "markdown",
        RST: "rst",
        JSON: "json",
        RULE: "rule",
        INSPECT: "inspect",
        CSV: "csv",
        IPYNB: "ipynb",
    }
    return names.get(format_type, "unknown")


def _render_print(resource: str, opts: RenderOptions) -> RenderableType:
    try:
        if resource == "-":
            renderable = Text.from_markup(
                sys.stdin.read(), justify=opts.text_justify, emoji=opts.emoji
            )
        else:
            renderable = Text.from_markup(
                resource, justify=opts.text_justify, emoji=opts.emoji
            )
        renderable.no_wrap = opts.no_wrap
        return renderable
    except Exception as error:
        on_error("unable to parse console markup", error)


def _render_rule(resource: str, opts: RenderOptions) -> RenderableType:
    try:
        rule_style = Style.parse(opts.rule_style)
    except Exception as error:
        on_error("unable to parse rule style", error)

    align = "center" if opts.text_justify in ("full", "default") else opts.text_justify
    return Rule(
        resource,
        style=rule_style,
        characters=opts.rule_char or "─",
        align=align,
    )


def _render_json(resource: str, opts: RenderOptions) -> RenderableType:
    json_data, _ = read_resource(resource, opts.lexer)
    try:
        return RichJSON(json_data)
    except Exception as error:
        on_error("unable to read json", error)


def _render_markdown(resource: str, opts: RenderOptions) -> RenderableType:
    markdown_data, _ = read_resource(resource, opts.lexer)
    return Markdown(markdown_data, code_theme=opts.theme, hyperlinks=opts.hyperlinks)


def _render_rst(resource: str, opts: RenderOptions) -> RenderableType:
    from rich_rst import RestructuredText

    rst_data, _ = read_resource(resource, opts.lexer)
    return RestructuredText(
        rst_data,
        code_theme=opts.theme,
        default_lexer=opts.lexer or "python",
        show_errors=False,
    )


def _render_inspect(
    resource: str, opts: RenderOptions, console: "ConsoleType"
) -> RenderableType:
    from rich._inspect import Inspect

    try:
        inspect_data = eval(resource)
    except Exception:
        console.print_exception()
        on_error(f"unable to eval {resource!r}")

    return Inspect(inspect_data, help=False, dunder=False, all=False, methods=True)


def _render_syntax(
    resource: str, opts: RenderOptions, console: "ConsoleType"
) -> RenderableType:
    if not resource:
        console.print(
            r"Usage: [b]rich [OPTIONS][/b] [b cyan]<PATH,TEXT,URL, or '-'>[/]"
        )
        console.print("See [bold green]rich --help[/] for options")
        console.print()
        sys.exit(0)

    try:
        if resource == "-":
            code = sys.stdin.read()
            lexer = opts.lexer
        else:
            code, lexer = read_resource(resource, opts.lexer)

        num_lines = len(code.splitlines())
        line_range = opts._line_range(num_lines)

        return Syntax(
            code,
            lexer or "text",
            theme=opts.theme,
            line_numbers=opts.line_numbers,
            indent_guides=opts.guides,
            word_wrap=not opts.no_wrap,
            line_range=line_range,
        )
    except Exception as error:
        on_error("unable to read file", error)


def render(
    resource: str,
    format_type: int,
    opts: RenderOptions,
    console: "ConsoleType",
) -> RenderableType:
    """Unified render entry point. Dispatches to the appropriate renderer."""
    if format_type == PRINT:
        return _render_print(resource, opts)
    elif format_type == RULE:
        return _render_rule(resource, opts)
    elif format_type == JSON:
        return _render_json(resource, opts)
    elif format_type == MARKDOWN:
        return _render_markdown(resource, opts)
    elif format_type == RST:
        return _render_rst(resource, opts)
    elif format_type == INSPECT:
        return _render_inspect(resource, opts, console)
    elif format_type == CSV:
        from .csv_renderer import render_csv

        return render_csv(resource, opts)
    elif format_type == IPYNB:
        from .notebook_renderer import render_ipynb

        return render_ipynb(resource, opts)
    else:
        return _render_syntax(resource, opts, console)
