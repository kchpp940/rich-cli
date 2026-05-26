import sys
from typing import TYPE_CHECKING, List, NoReturn, Optional, Tuple

import click
from pygments.util import ClassNotFound
from rich.align import Align
from rich.console import Console, RenderableType
from rich.highlighter import RegexHighlighter
from rich.padding import Padding
from rich.panel import Panel
from rich.style import Style
from rich.styled import Styled
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from .renderer_registry import (
    AUTO,
    CSV,
    INSPECT,
    IPYNB,
    JSON,
    MARKDOWN,
    PRINT,
    RST,
    RULE,
    SYNTAX,
    RenderOptions,
    determine_format,
    render,
)
from .resource_reader import read_resource

console = Console()
error_console = Console(stderr=True)

if TYPE_CHECKING:
    from rich.console import ConsoleOptions, RenderResult
    from rich.measure import Measurement

VERSION = "1.8.0"

BOXES = [
    "none",
    "ascii",
    "ascii2",
    "square",
    "rounded",
    "heavy",
    "double",
]

BOX_TEXT = ", ".join(sorted(BOXES))


def on_error(message: str, error: Optional[Exception] = None, code: int = -1) -> NoReturn:
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


class ForceWidth:
    """Force a renderable to a given width."""

    def __init__(self, renderable: "RenderableType", width: int = 80) -> None:
        self.renderable = renderable
        self.width = width

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        child_options = options.update_width(self.width)
        yield from console.render(self.renderable, child_options)

    def __rich_measure__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "Measurement":
        from rich.measure import Measurement

        return Measurement(self.width, self.width)


def blend_text(
    message: str, color1: Tuple[int, int, int], color2: Tuple[int, int, int]
) -> Text:
    """Blend text from one color to another."""
    text = Text(message)
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    dr = r2 - r1
    dg = g2 - g1
    db = b2 - b1
    size = len(text)
    for index in range(size):
        blend = index / size
        color = f"#{int(r1 + dr * blend):02X}{int(g1 + dg * blend):02X}{int(b1 + db * blend):02X}"
        text.stylize(color, index, index + 1)
    return text


class RichCommand(click.Command):
    """Override Clicks help with a Richer version."""

    def format_help(self, ctx, formatter):
        class OptionHighlighter(RegexHighlighter):
            highlights = [
                r"(?P<switch>\-\w)",
                r"(?P<option>\-\-[\w\-]+)",
            ]

        highlighter = OptionHighlighter()

        console = Console(
            theme=Theme(
                {
                    "option": "bold cyan",
                    "switch": "bold green",
                }
            ),
            highlighter=highlighter,
        )

        console.print(
            f"[b]Rich CLI[/b] [magenta]v{VERSION}[/] 🤑\n\n[dim]Rich text and formatting in the terminal\n",
            justify="center",
        )

        console.print("Usage: [b]rich[/b] [b][OPTIONS][/] [b cyan]<PATH,TEXT,URL, or '-'>\n")

        options_table = Table(highlight=True, box=None, show_header=False)

        for param in self.get_params(ctx)[1:]:
            if len(param.opts) == 2:
                opt1 = highlighter(param.opts[1])
                opt2 = highlighter(param.opts[0])
            else:
                opt2 = highlighter(param.opts[0])
                opt1 = Text("")

            if param.metavar:
                opt2 += Text(f" {param.metavar}", style="bold yellow")

            help_record = param.get_help_record(ctx)
            help = (
                ""
                if help_record is None
                else Text.from_markup(param.get_help_record(ctx)[-1], emoji=False)
            )

            options_table.add_row(opt1, opt2, highlighter(help))

        console.print(
            Panel(
                options_table, border_style="dim", title="Options", title_align="left"
            )
        )

        from rich.color import Color

        console.print(
            blend_text(
                "♥ https://www.textualize.io",
                Color.parse("#b169dd").triplet,
                Color.parse("#542c91").triplet,
            ),
            justify="left",
            style="bold",
        )


@click.command(cls=RichCommand)
@click.argument("resource", metavar="<PATH or TEXT or '-'>", default="")
@click.option(
    "--print",
    "-p",
    "_print",
    is_flag=True,
    help="Print [u]console markup[/u]. [dim]See https://rich.readthedocs.io/en/latest/markup.html",
)
@click.option("--rule", "-u", is_flag=True, help="Display a horizontal [u]rule[/u].")
@click.option("--json", "-J", is_flag=True, help="Display as [u]JSON[/u].")
@click.option("--markdown", "-m", is_flag=True, help="Display as [u]markdown[/u].")
@click.option("--rst", is_flag=True, help="Display [u]restructured text[/u].")
@click.option("--csv", is_flag=True, help="Display [u]CSV[/u] as a table.")
@click.option("--ipynb", is_flag=True, help="Display [u]Jupyter notebook[/u].")
@click.option("--syntax", is_flag=True, help="[u]Syntax[/u] highlighting.")
@click.option("--inspect", is_flag=True, help="[u]Inspect[/u] a python object.")
@click.option(
    "--head",
    "-h",
    type=click.IntRange(min=1),
    metavar="LINES",
    default=None,
    help="Display first [b]LINES[/] of the file (requires --syntax or --csv).",
)
@click.option(
    "--tail",
    "-t",
    type=click.IntRange(min=1),
    metavar="LINES",
    default=None,
    help="Display last [b]LINES[/] of the file (requires --syntax or --csv).",
)
@click.option(
    "--emoji", "-j", is_flag=True, help="Enable emoji code. [dim]e.g. :sparkle:"
)
@click.option("--left", "-l", is_flag=True, help="Align to left.")
@click.option("--right", "-r", is_flag=True, help="Align to right.")
@click.option("--center", "-c", is_flag=True, help="Align to center.")
@click.option("--text-left", "-L", is_flag=True, help="Justify text to left.")
@click.option("--text-right", "-R", is_flag=True, help="Justify text to right.")
@click.option("--text-center", "-C", is_flag=True, help="Justify text to center.")
@click.option(
    "--text-full", "-F", is_flag=True, help="Justify text to both left and right edges."
)
@click.option(
    "--soft", is_flag=True, help="Enable soft wrapping of text (requires --print)."
)
@click.option(
    "--expand", "-e", is_flag=True, help="Expand to full width (requires --panel)."
)
@click.option(
    "--width",
    "-w",
    metavar="SIZE",
    type=int,
    help="Fit output to [b]SIZE[/] characters.",
    default=-1,
)
@click.option(
    "--max-width",
    "-W",
    metavar="SIZE",
    type=int,
    help="Set maximum width to [b]SIZE[/] characters.",
    default=-1,
)
@click.option(
    "--style", "-s", metavar="STYLE", help="Set text style to [b]STYLE[/b].", default=""
)
@click.option(
    "--rule-style",
    metavar="STYLE",
    help="Set rule style to [b]STYLE[/b].",
    default="bright_green",
)
@click.option(
    "--rule-char",
    metavar="CHARACTER",
    default="─",
    help="Use [b]CHARACTER[/b] to generate a line with --rule.",
)
@click.option(
    "--padding",
    "-d",
    metavar="TOP,RIGHT,BOTTOM,LEFT",
    help="Padding around output. [dim]1, 2 or 4 comma separated integers, e.g. 2,4",
)
@click.option(
    "--panel",
    "-a",
    default="none",
    type=click.Choice(BOXES),
    metavar="BOX",
    help=f"Set panel type to [b]BOX[/b]. [dim]{BOX_TEXT}",
)
@click.option(
    "--panel-style",
    "-S",
    default="",
    metavar="STYLE",
    help="Set the panel style to [b]STYLE[/b] (requires --panel).",
)
@click.option(
    "--theme",
    metavar="THEME",
    help="Set syntax theme to [b]THEME[/b]. [dim]See https://pygments.org/styles/",
    default="ansi_dark",
    envvar="RICH_THEME",
)
@click.option(
    "--line-numbers", "-n", is_flag=True, help="Enable line number in syntax."
)
@click.option(
    "--guides",
    "-g",
    is_flag=True,
    help="Enable indentation guides in syntax highlighting",
)
@click.option(
    "--lexer",
    "-x",
    metavar="LEXER",
    default=None,
    help="Use [b]LEXER[/b] for syntax highlighting. [dim]See https://pygments.org/docs/lexers/",
)
@click.option("--hyperlinks", "-y", is_flag=True, help="Render hyperlinks in markdown.")
@click.option(
    "--no-wrap", is_flag=True, help="Don't word wrap syntax highlighted files."
)
@click.option(
    "--title", metavar="TEXT", default="", help="Set panel title to [b]TEXT[/]."
)
@click.option(
    "--caption", metavar="TEXT", default="", help="Set panel caption to [b]TEXT[/]."
)
@click.option(
    "--force-terminal",
    is_flag=True,
    help="Force terminal output when not writing to a terminal.",
)
@click.option(
    "--export-html",
    "-o",
    metavar="PATH",
    default="",
    help="Write HTML to [b]PATH[/b].",
)
@click.option(
    "--export-svg", metavar="PATH", default="", help="Write SVG to [b]PATH[/b]."
)
@click.option("--pager", is_flag=True, help="Display in an interactive pager.")
@click.option("--version", "-v", is_flag=True, help="Print version and exit.")
def main(
    resource: str,
    version: bool = False,
    _print: bool = False,
    syntax: bool = False,
    rule: bool = False,
    rule_char: Optional[str] = None,
    json: bool = False,
    markdown: bool = False,
    rst: bool = False,
    csv: bool = False,
    ipynb: bool = False,
    inspect: bool = True,
    emoji: bool = False,
    left: bool = False,
    right: bool = False,
    center: bool = False,
    text_left: bool = False,
    text_right: bool = False,
    text_center: bool = False,
    soft: bool = False,
    head: Optional[int] = None,
    tail: Optional[int] = None,
    text_full: bool = False,
    expand: bool = False,
    width: int = -1,
    max_width: int = -1,
    style: str = "",
    rule_style: str = "",
    no_wrap: bool = True,
    padding: str = "",
    panel: str = "",
    panel_style: str = "",
    title: str = "",
    caption: str = "",
    theme: str = "",
    line_numbers: bool = False,
    guides: bool = False,
    lexer: str = "",
    hyperlinks: bool = False,
    force_terminal: bool = False,
    export_html: str = "",
    export_svg: str = "",
    pager: bool = False,
):
    """Rich toolbox for console output."""
    if version:
        sys.stdout.write(f"{VERSION}\n")
        return

    console = Console(
        emoji=emoji,
        record=bool(export_html or export_svg),
        force_terminal=force_terminal if force_terminal else None,
    )

    if width > 0:
        expand = True

    print_padding: List[int] = []
    if padding:
        try:
            print_padding = [int(pad) for pad in padding.split(",")]
        except Exception:
            on_error("padding should be 1, 2 or 4 integers separated by commas")
        else:
            if len(print_padding) not in (1, 2, 4):
                on_error("padding should be 1, 2 or 4 integers separated by commas")

    text_justify = "default"
    if text_left:
        text_justify = "left"
    elif text_right:
        text_justify = "right"
    elif text_center:
        text_justify = "center"
    elif text_full:
        text_justify = "full"

    resource_format = determine_format(
        resource=resource,
        _print=_print,
        syntax=syntax,
        rule=rule,
        json=json,
        markdown=markdown,
        rst=rst,
        csv=csv,
        ipynb=ipynb,
        inspect=inspect,
    )

    render_opts = RenderOptions(
        theme=theme,
        hyperlinks=hyperlinks,
        lexer=lexer if lexer else None,
        head=head,
        tail=tail,
        line_numbers=line_numbers,
        guides=guides,
        no_wrap=no_wrap,
        emoji=emoji,
        text_justify=text_justify,
        rule_style=rule_style,
        rule_char=rule_char or "─",
        title=title,
        caption=caption,
    )

    renderable = render(resource, resource_format, render_opts, console)

    if print_padding:
        renderable = Padding(renderable, tuple(print_padding), expand=expand)

    if panel != "none":
        from rich import box

        try:
            render_border_style = Style.parse(panel_style) if panel_style else None
        except Exception as error:
            on_error("unable to parse panel style", error)

        renderable = Panel(
            renderable,
            getattr(box, panel.upper()),
            expand=expand,
            title=title or None,
            subtitle=caption or None,
            border_style=render_border_style,
        )

    if style:
        try:
            text_style = Style.parse(style)
        except Exception as error:
            on_error("unable to parse style", error)
        else:
            renderable = Styled(renderable, text_style)

    if width > 0 and not pager:
        renderable = ForceWidth(renderable, width=width)

    justify = "default"
    if left:
        justify = "left"
    elif right:
        justify = "right"
    elif center:
        justify = "center"

    if pager:
        from .pager import PagerApp, PagerRenderable

        if justify != "default":
            renderable = Align(renderable, justify)

        if width < 0:
            width = console.width
        render_options = console.options.update_width(width - 1)
        lines = console.render_lines(renderable, render_options, new_lines=True)
        PagerApp.run(title=resource, content=PagerRenderable(lines, width=width))

    else:
        try:
            console.print(
                renderable,
                width=None if max_width <= 0 else max_width,
                soft_wrap=soft,
                justify=justify,
            )
        except Exception as error:
            on_error("failed to print resource", error)

    if export_html:
        try:
            console.save_html(export_html, clear=False)
        except Exception as error:
            on_error("failed to save HTML", error)

    if export_svg:
        try:
            console.save_svg(export_svg, clear=False)
        except Exception as error:
            on_error("failed to save SVG", error)


def run():
    main()


if __name__ == "__main__":
    run()
