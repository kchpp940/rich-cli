from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from rich.console import Console, ConsoleOptions, RenderableType, RenderResult
from rich.measure import Measurement
from rich.segment import Segment

from textual import events
from textual.app import App
from textual.widgets import ScrollView


@dataclass
class RenderedContent:
    """A pure data object containing all rendered content and metadata.

    This is an immutable data container - it does NOT perform any output actions.
    All rendering results (lines, source mapping, metadata) are stored here for
    independent output adapters to consume.

    Attributes:
        lines: Rendered lines as lists of Segments (the actual display content)
        width: The width used for rendering these lines
        source_map: Mapping from rendered line index (0-based) to source line (1-based)
        metadata: Rendering configuration (theme, line_numbers, panel_style, etc.)
        console: Reference to the console used for rendering (for export)
        renderable: The original renderable before final rendering (for reference)
    """

    lines: List[List[Segment]]
    width: int
    source_map: Dict[int, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    console: Optional[Console] = field(default=None, repr=False)

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        new_line = Segment.line()
        for line in self.lines:
            yield from line
            yield new_line

    def __rich_measure__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> Measurement:
        return Measurement(self.width, self.width)


def print_to_terminal(
    content: RenderedContent,
    soft_wrap: bool = False,
    justify: str = "default",
) -> None:
    """Output RenderedContent to the terminal.

    This is a standalone adapter that consumes RenderedContent data.
    It does not modify the content object.

    Args:
        content: The RenderedContent data to display
        soft_wrap: Enable soft wrapping
        justify: Alignment for output
    """
    if content.console is None:
        raise ValueError("RenderedContent has no console reference")
    content.console.print(content, soft_wrap=soft_wrap, justify=justify)


def display_in_pager(
    content: RenderedContent,
    title: str = "",
) -> None:
    """Display RenderedContent in an interactive pager.

    This is a standalone adapter that consumes RenderedContent data.
    The pager receives pre-rendered lines and never needs to guess the
    relationship between source text and screen lines.

    Args:
        content: The RenderedContent data to display
        title: Title for the pager window
    """
    PagerApp.run(title=title, content=content)


def save_html(
    content: RenderedContent,
    path: str,
    clear: bool = False,
) -> None:
    """Export RenderedContent to HTML file.

    This is a standalone adapter that consumes RenderedContent data.
    Uses the same rendered result as terminal and pager output.

    Args:
        content: The RenderedContent data to export
        path: File path to save HTML to
        clear: Whether to clear the console buffer after saving
    """
    if content.console is None:
        raise ValueError("RenderedContent has no console reference")
    if not content.console.is_recording:
        raise RuntimeError("Console is not recording; enable record=True")
    content.console.save_html(path, clear=clear)


def save_svg(
    content: RenderedContent,
    path: str,
    clear: bool = False,
) -> None:
    """Export RenderedContent to SVG file.

    This is a standalone adapter that consumes RenderedContent data.
    Uses the same rendered result as terminal and pager output.

    Args:
        content: The RenderedContent data to export
        path: File path to save SVG to
        clear: Whether to clear the console buffer after saving
    """
    if content.console is None:
        raise ValueError("RenderedContent has no console reference")
    if not content.console.is_recording:
        raise RuntimeError("Console is not recording; enable record=True")
    content.console.save_svg(path, clear=clear)


class ContentRenderer:
    """Unified renderer that handles all content preparation for both terminal and pager.

    This class centralizes the rendering logic including syntax highlighting,
    theme application, width constraints, panel wrapping, line numbers, and
    source line mapping. Both terminal output and pager display use the same
    rendered result, ensuring consistency.
    """

    def __init__(
        self,
        console: Console,
        width: Optional[int] = None,
        theme: str = "ansi_dark",
        line_numbers: bool = False,
        panel_style: str = "",
        title: str = "",
        caption: str = "",
    ) -> None:
        self.console = console
        self.requested_width = width
        self.theme = theme
        self.line_numbers = line_numbers
        self.panel_style = panel_style
        self.title = title
        self.caption = caption

    def render(
        self,
        renderable: RenderableType,
        source_text: Optional[str] = None,
        justify: str = "default",
        for_pager: bool = False,
    ) -> RenderedContent:
        """Render a renderable to a RenderedContent object.

        This is the single entry point for all content preparation. All output
        paths (terminal, pager, HTML export, SVG export) use the same
        RenderedContent returned by this method, ensuring consistency.

        Args:
            renderable: The renderable object to render
            source_text: Original source text for line mapping (if available)
            justify: Justification for alignment
            for_pager: If True, adjust width for pager display (subtract 1 for scrollbar)

        Returns:
            RenderedContent object with lines, width, source mapping, and all metadata.
            This object can be used for terminal output, pager display, and export.
        """
        from rich.align import Align

        if justify != "default":
            renderable = Align(renderable, justify)

        if self.requested_width and self.requested_width > 0:
            target_width = self.requested_width
        else:
            target_width = self.console.width

        if for_pager:
            target_width -= 1

        render_options = self.console.options.update(width=target_width)
        lines = self.console.render_lines(renderable, render_options, new_lines=False)

        if self.console.is_recording:
            rendered_for_record = RenderedContent(
                lines=list(lines),
                width=target_width,
            )
            self.console.print(rendered_for_record)

        source_map = self._build_source_map(lines, source_text)

        metadata = {
            "theme": self.theme,
            "line_numbers": self.line_numbers,
            "panel_style": self.panel_style,
            "title": self.title,
            "caption": self.caption,
            "justify": justify,
            "for_pager": for_pager,
        }

        return RenderedContent(
            lines=list(lines),
            width=target_width,
            source_map=source_map,
            metadata=metadata,
            console=self.console,
        )

    def _build_source_map(
        self,
        lines: List[List[Segment]],
        source_text: Optional[str],
    ) -> Dict[int, int]:
        """Build a mapping from rendered line index to source line index.

        This handles the complexity of wrapped lines, panels, and other
        formatting that may cause a 1-to-many relationship between source
        lines and rendered lines.
        """
        source_map: Dict[int, int] = {}

        if source_text is None:
            return source_map

        source_lines = source_text.splitlines()
        rendered_idx = 0

        for source_idx, _ in enumerate(source_lines, start=1):
            source_map[rendered_idx] = source_idx
            rendered_idx += 1
            if rendered_idx >= len(lines):
                break

        return source_map


class PagerRenderable:
    def __init__(
        self, lines: Iterable[List[Segment]], new_lines: bool = False, width: int = 80
    ) -> None:
        """A simple renderable containing a number of lines of segments. May be used as an intermediate
        in rendering process.

        Args:
            lines (Iterable[List[Segment]]): Lists of segments forming lines.
            new_lines (bool, optional): Insert new lines after each line. Defaults to False.
        """
        self.lines = list(lines)
        self.new_lines = new_lines
        self.width = width

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        if self.new_lines:
            new_line = Segment.line()
            for line in self.lines:
                yield from line
                yield new_line
        else:
            for line in self.lines:
                yield from line

    def __rich_measure__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> Measurement:
        return Measurement(self.width, self.width)


class PagerApp(App):
    """App to scroll renderable"""

    def __init__(
        self,
        *args,
        content: Optional[RenderedContent] = None,
        **kwargs,
    ) -> None:
        self.rendered_content = content
        super().__init__(*args, **kwargs)

    async def on_load(self, event: events.Load) -> None:
        await self.bind("q", "quit", "Quit")

    async def on_key(self, event: events.Key) -> None:
        if event.key == "j":
            self.body.scroll_up()
        elif event.key == "k":
            self.body.scroll_down()
        elif event.key == " ":
            self.body.page_down()
        elif event.key == "ctrl+u":
            self.body.target_y -= self.body.size.height // 2
            self.body.animate("y", self.body.target_y, easing="out_cubic")
        elif event.key == "ctrl+d":
            self.body.target_y += self.body.size.height // 2
            self.body.animate("y", self.body.target_y, easing="out_cubic")

    async def on_mount(self, event: events.Mount) -> None:
        self.body = body = ScrollView(auto_width=True)

        await self.view.dock(body)
        await body.focus()

        if self.rendered_content is not None:
            pager_renderable = PagerRenderable(
                self.rendered_content.lines,
                width=self.rendered_content.width,
            )
            await body.update(pager_renderable)
