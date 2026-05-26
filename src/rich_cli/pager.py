from dataclasses import dataclass, field
from enum import auto
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

from rich.console import Console, ConsoleOptions, RenderResult, RenderableType
from rich.measure import Measurement
from rich.segment import Segment
from rich.text import Text
from rich.style import Style

from textual import events
from textual.app import App
from textual.widgets import ScrollView
from textual.widget import Widget


@dataclass
class PagerLine:
    """Single source of truth for a pager line.

    Attributes:
        segments: Rich rendered segments for display.
        plain_text: Plain text extracted from segments, used for search.
        source_line: Original source file line number (1-based), or None.
            For syntax-highlighted files, this is the actual code line number.
            For Markdown/plain text, this is the content line before wrapping.
    """
    segments: List[Segment] = field(default_factory=list)
    plain_text: str = ""
    source_line: Optional[int] = None

    @classmethod
    def from_segments(
        cls, segments: List[Segment], source_line: Optional[int] = None
    ) -> "PagerLine":
        """Create a PagerLine from rendered segments."""
        plain_text = "".join(seg.text for seg in segments)
        return cls(
            segments=list(segments),
            plain_text=plain_text,
            source_line=source_line,
        )

    def highlight_matches(
        self,
        matches: List[Tuple[int, int]],
        highlight_style: Style,
        current_match_style: Style,
        is_current_match: List[bool],
    ) -> List[Segment]:
        """Apply search highlighting to this line."""
        if not matches:
            return list(self.segments)

        result: List[Segment] = []
        pos = 0

        for seg in self.segments:
            seg_text = seg.text
            seg_len = len(seg_text)
            seg_start = pos
            seg_end = pos + seg_len

            seg_matches = [
                (max(m_start, seg_start) - seg_start, min(m_end, seg_end) - seg_start, mi)
                for mi, (m_start, m_end) in enumerate(matches)
                if m_start < seg_end and m_end > seg_start
            ]

            if not seg_matches:
                result.append(seg)
            else:
                last_end = 0
                for m_start_in_seg, m_end_in_seg, mi in seg_matches:
                    if last_end < m_start_in_seg:
                        pre_text = seg_text[last_end:m_start_in_seg]
                        result.append(Segment(pre_text, seg.style))

                    match_text = seg_text[m_start_in_seg:m_end_in_seg]
                    style = (
                        current_match_style
                        if mi < len(is_current_match) and is_current_match[mi]
                        else highlight_style
                    )
                    combined_style = style + seg.style if seg.style else style
                    result.append(Segment(match_text, combined_style))
                    last_end = m_end_in_seg

                if last_end < seg_len:
                    post_text = seg_text[last_end:]
                    result.append(Segment(post_text, seg.style))

            pos += seg_len

        return result


class SourceLineMapper:
    """Maps screen lines to source file lines using pre-built source_lines.

    The mapping is built from the original text (source_lines) and attached
    to rendered PagerLines. Line number display is purely a presentation
    option and does NOT affect the mapping semantics.

    Mapping strategies:
    1. Syntax files: Match screen line text to source line content.
       Works identically whether --line-numbers is on or off.
    2. Markdown/plain text: Progressive accumulation matching.
       Handles word-wrapping where one source line becomes multiple screen lines.
    3. Panel-wrapped: Border/decoration lines get source_line=None.
    """

    BORDER_CHARS = set("╔╗╚╝║═─│┌┐┘└├┤┬┴┼╠╣╦╩╬╭╮╯╰")
    CORNER_CHARS = set("╔╗╚╝╌┌┐┘└╭╮╯╰")

    @classmethod
    def is_border_line(cls, text: str) -> bool:
        """Check if a rendered line is a pure panel border (no content).

        Pure border lines are:
        - Top/bottom borders: ╭───╮, ╰───╯, etc.
        - Left-only borders: │ followed by only spaces
        - Lines where all non-space chars are border chars
        """
        stripped = text.rstrip("\n").rstrip()
        if not stripped:
            return False

        # Check if it starts with a corner character
        if stripped[0] in cls.CORNER_CHARS:
            return True

        # Check if it's a pure vertical border (│ followed by only spaces or another │)
        if stripped[0] in ('│', '║', '┃'):
            content_part = stripped[1:].strip()
            if not content_part or content_part in ('│', '║', '┃'):
                return True

        # Check if all non-space characters are border chars
        non_space = [c for c in stripped if c != ' ']
        if non_space and all(c in cls.BORDER_CHARS for c in non_space):
            return True

        return False

    @classmethod
    def extract_content(cls, text: str) -> str:
        """Extract content from a line, removing panel border characters.

        For lines like '│ print("Hello")        │', returns ' print("Hello")        '
        For lines like '  1 def hello():        ', returns '  1 def hello():        '
        """
        stripped = text.rstrip("\n")
        if not stripped:
            return stripped

        # Remove leading border character and optional trailing border character
        if stripped[0] in ('│', '║', '┃'):
            stripped = stripped[1:]
        if stripped and stripped[-1] in ('│', '║', '┃'):
            stripped = stripped[:-1]

        return stripped

    @classmethod
    def is_content_line(cls, text: str) -> bool:
        """Check if a rendered line contains actual content (not border/padding)."""
        stripped = text.rstrip("\n").strip()
        return bool(stripped) and not cls.is_border_line(text)

    @classmethod
    def build_from_source_lines(
        cls,
        pager_lines: List[PagerLine],
        source_lines: List[str],
    ) -> None:
        """Map screen lines to source lines using progressive text matching.

        This is the primary mapping method that works for ALL content types:
        Syntax (with or without line numbers), Markdown, plain text, etc.

        Algorithm:
        - Walk through screen lines and source lines in parallel
        - Skip empty source lines (they produce empty/padding screen lines)
        - Accumulate screen line text until it matches a source line
        - Mark all contributing screen lines with that source line number
        - Border/decoration lines get source_line=None

        Args:
            pager_lines: Rendered screen lines to annotate.
            source_lines: Original source text lines (from PreparedContent.source_lines).
        """
        if not source_lines:
            return

        source_idx = 0
        accumulated = ""

        for pager_line in pager_lines:
            screen_text = pager_line.plain_text.rstrip("\n")

            if cls.is_border_line(screen_text):
                pager_line.source_line = None
                continue

            if not cls.is_content_line(screen_text):
                if source_idx < len(source_lines):
                    pager_line.source_line = source_idx + 1
                else:
                    pager_line.source_line = None
                continue

            # Extract content for matching (strip panel borders)
            content_text = cls.extract_content(screen_text)

            # Skip empty source lines - they produce padding/empty screen lines
            while source_idx < len(source_lines) and not source_lines[source_idx].strip():
                source_idx += 1
                accumulated = ""

            if source_idx >= len(source_lines):
                pager_line.source_line = source_idx
                continue

            source_line = source_lines[source_idx]

            accumulated += content_text

            if len(accumulated) >= len(source_line):
                pager_line.source_line = source_idx + 1
                source_idx += 1
                accumulated = ""
            else:
                pager_line.source_line = source_idx + 1

    @classmethod
    def build_from_syntax(
        cls, pager_lines: List[PagerLine]
    ) -> None:
        """DEPRECATED: Use build_from_source_lines() instead.

        Kept for backward compatibility. Line numbers in the rendered output
        are a presentation detail and should not drive mapping semantics.
        """
        SYNTAX_LINE_RE = re.compile(r"^\s*(\d+)\s+\S")

        for pager_line in pager_lines:
            text = pager_line.plain_text.rstrip("\n")
            match = SYNTAX_LINE_RE.match(text)
            if match:
                pager_line.source_line = int(match.group(1))

    @classmethod
    def build_from_plain_text(
        cls,
        pager_lines: List[PagerLine],
        raw_text: str,
    ) -> None:
        """DEPRECATED: Use build_from_source_lines() instead.

        Kept for backward compatibility.
        """
        if not raw_text:
            return
        raw_lines = raw_text.splitlines()
        cls.build_from_source_lines(pager_lines, raw_lines)

    @classmethod
    def build_for_panel(
        cls,
        pager_lines: List[PagerLine],
    ) -> None:
        """Mark border lines as having no source_line.

        This is an additional pass that can be applied after build_from_source_lines
        to handle cases where panel borders might have been incorrectly mapped.
        """
        for pager_line in pager_lines:
            if cls.is_border_line(pager_line.plain_text):
                pager_line.source_line = None


class PagerRenderable:
    """Renderable backed by PagerLine objects with source line mapping."""

    def __init__(
        self,
        lines: Iterable[PagerLine],
        new_lines: bool = False,
        width: int = 80,
    ) -> None:
        self.pager_lines = list(lines)
        self.new_lines = new_lines
        self.width = width
        self._source_line_index: Optional[Dict[int, int]] = None

    @property
    def lines(self) -> List[List[Segment]]:
        """Legacy property: returns segments for each line."""
        return [pl.segments for pl in self.pager_lines]

    @property
    def plain_lines(self) -> List[str]:
        """Returns plain text for each line."""
        return [pl.plain_text for pl in self.pager_lines]

    @property
    def total_lines(self) -> int:
        """Total number of screen lines."""
        return len(self.pager_lines)

    @property
    def max_source_line(self) -> int:
        """Maximum source line number (for status bar display)."""
        max_line = 0
        for pl in self.pager_lines:
            if pl.source_line is not None and pl.source_line > max_line:
                max_line = pl.source_line
        return max_line

    def _build_source_index(self) -> Dict[int, int]:
        """Build a mapping from source_line to first screen_line index.

        Returns:
            Dict mapping source_line_number -> screen_line_index (0-based).
        """
        index: Dict[int, int] = {}
        for i, pl in enumerate(self.pager_lines):
            if pl.source_line is not None and pl.source_line not in index:
                index[pl.source_line] = i
        return index

    def source_line_to_screen_line(self, source_line: int) -> Optional[int]:
        """Convert a source file line number to a screen line index.

        Args:
            source_line: 1-based source file line number.

        Returns:
            0-based screen line index, or None if not found.
        """
        if self._source_line_index is None:
            self._source_line_index = self._build_source_index()
        return self._source_line_index.get(source_line)

    def screen_line_to_source_line(self, screen_line: int) -> Optional[int]:
        """Get the source line number for a given screen line.

        Args:
            screen_line: 0-based screen line index.

        Returns:
            1-based source line number, or None if not mapped.
        """
        if 0 <= screen_line < len(self.pager_lines):
            return self.pager_lines[screen_line].source_line
        return None

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        if self.new_lines:
            new_line = Segment.line()
            for pager_line in self.pager_lines:
                yield from pager_line.segments
                yield new_line
        else:
            for pager_line in self.pager_lines:
                yield from pager_line.segments

    def __rich_measure__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> Measurement:
        return Measurement(self.width, self.width)

    def with_highlighted_lines(
        self,
        highlighted_segments: List[List[Segment]],
    ) -> "PagerRenderable":
        """Create a new PagerRenderable with highlighted segments.

        Preserves source_line mapping from original lines.
        """
        new_lines: List[PagerLine] = []
        for i, new_segs in enumerate(highlighted_segments):
            if i < len(self.pager_lines):
                new_line = PagerLine(
                    segments=new_segs,
                    plain_text=self.pager_lines[i].plain_text,
                    source_line=self.pager_lines[i].source_line,
                )
            else:
                new_line = PagerLine.from_segments(new_segs)
            new_lines.append(new_line)
        result = PagerRenderable(new_lines, new_lines=self.new_lines, width=self.width)
        result._source_line_index = self._source_line_index
        return result


class SearchHighlighter:
    """Handles search functionality and match highlighting.

    Search is always performed on the rendered PagerLine.plain_text,
    ensuring matches align exactly with what is displayed on screen.
    """

    def __init__(self) -> None:
        self.pattern: Optional[str] = None
        self.regex: Optional[re.Pattern] = None
        self.matches: List[Tuple[int, int, int]] = []  # (line_idx, start, end)
        self.current_match_index: int = -1
        self.case_sensitive: bool = False

    def set_pattern(self, pattern: str, case_sensitive: bool = False) -> bool:
        """Set search pattern and compile regex."""
        if not pattern:
            self.pattern = None
            self.regex = None
            self.matches = []
            self.current_match_index = -1
            return False

        self.pattern = pattern
        self.case_sensitive = case_sensitive
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            self.regex = re.compile(pattern, flags)
            return True
        except re.error:
            self.regex = None
            self.matches = []
            return False

    def search_pager_lines(self, pager_lines: List[PagerLine]) -> None:
        """Search through rendered PagerLines for pattern matches."""
        self.matches = []
        if not self.regex:
            return

        for line_idx, pager_line in enumerate(pager_lines):
            for match in self.regex.finditer(pager_line.plain_text):
                self.matches.append((line_idx, match.start(), match.end()))

        if self.matches:
            self.current_match_index = 0
        else:
            self.current_match_index = -1

    def next_match(self) -> Optional[Tuple[int, int, int]]:
        """Get next match."""
        if not self.matches:
            return None
        self.current_match_index = (self.current_match_index + 1) % len(self.matches)
        return self.matches[self.current_match_index]

    def prev_match(self) -> Optional[Tuple[int, int, int]]:
        """Get previous match."""
        if not self.matches:
            return None
        self.current_match_index = (self.current_match_index - 1) % len(self.matches)
        return self.matches[self.current_match_index]

    def highlight_pager_lines(
        self, pager_lines: List[PagerLine]
    ) -> List[List[Segment]]:
        """Apply search highlighting to all pager lines."""
        if not self.matches:
            return [pl.segments for pl in pager_lines]

        highlight_style = Style(bgcolor="yellow", color="black", bold=True)
        current_match_style = Style(bgcolor="red", color="white", bold=True)

        line_matches: Dict[int, List[Tuple[int, int, int]]] = {}
        for global_idx, (line_idx, start, end) in enumerate(self.matches):
            if line_idx not in line_matches:
                line_matches[line_idx] = []
            line_matches[line_idx].append((start, end, global_idx))

        highlighted: List[List[Segment]] = []
        for line_idx, pager_line in enumerate(pager_lines):
            if line_idx not in line_matches:
                highlighted.append(list(pager_line.segments))
                continue

            matches_for_line = line_matches[line_idx]
            matches_pos = [(s, e) for s, e, _ in matches_for_line]
            is_current = [
                global_idx == self.current_match_index
                for _, _, global_idx in matches_for_line
            ]

            highlighted_segs = pager_line.highlight_matches(
                matches_pos,
                highlight_style,
                current_match_style,
                is_current,
            )
            highlighted.append(highlighted_segs)

        return highlighted


class TerminalState:
    """Manages terminal state saving and restoring."""

    @staticmethod
    def save() -> None:
        """Save terminal state and switch to alternate screen buffer."""
        if sys.stdout.isatty():
            sys.stdout.write("\x1b[?1049h")
            sys.stdout.flush()

    @staticmethod
    def restore() -> None:
        """Restore terminal state from alternate screen buffer."""
        if sys.stdout.isatty():
            sys.stdout.write("\x1b[?1049l")
            sys.stdout.flush()


class PagerStatusBar(Widget):
    """Status bar widget for pager."""

    def __init__(
        self,
        total_lines: int = 0,
        max_source_line: int = 0,
        search_pattern: Optional[str] = None,
        match_count: int = 0,
        current_match: int = -1,
        goto_mode: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.total_lines = total_lines
        self.max_source_line = max_source_line
        self.current_line = 1
        self.current_source_line: Optional[int] = None
        self.search_pattern = search_pattern
        self.match_count = match_count
        self.current_match = current_match
        self.goto_mode = goto_mode
        self.goto_input = ""
        self.search_mode = False
        self.search_input = ""
        self.height = 1

    def render(self) -> RenderableType:
        status_parts: List[RenderableType] = []

        if self.goto_mode:
            prompt = Text(f" :{self.goto_input}", style="bold green")
            cursor = Text("█", style="reverse green")
            status_parts.append(prompt)
            status_parts.append(cursor)
        elif self.search_mode:
            prompt = Text(f" /{self.search_input}", style="bold magenta")
            cursor = Text("█", style="reverse magenta")
            status_parts.append(prompt)
            status_parts.append(cursor)
        elif self.search_pattern:
            match_info = Text(
                f" /{self.search_pattern}"
                + (
                    f"  [{self.current_match + 1}/{self.match_count}]"
                    if self.match_count > 0
                    else "  [no matches]"
                ),
                style="dim",
            )
            status_parts.append(match_info)

        if self.current_source_line is not None and self.max_source_line > 0:
            position_info = Text(
                f" src:{self.current_source_line}/{self.max_source_line}",
                style="bold yellow",
            )
            screen_info = Text(
                f" screen:{self.current_line}/{self.total_lines} ",
                style="bold cyan",
            )
        else:
            position_info = Text(
                f" {self.current_line}/{self.total_lines} ",
                style="bold cyan",
            )
            screen_info = Text("")

        help_text = Text(
            " q:quit  /:search  n:next  N:prev  :goto  ↑↓:scroll",
            style="dim",
        )

        bar = Text()
        for part in status_parts:
            bar += part
        bar += " "
        bar += help_text
        bar += screen_info
        bar += position_info
        bar += Text(" " * max(0, self.size.width - len(bar)))
        bar.stylize("on grey23")

        return bar

    def update_status(
        self,
        current_line: int,
        total_lines: Optional[int] = None,
        current_source_line: Optional[int] = None,
        max_source_line: Optional[int] = None,
        search_pattern: Optional[str] = None,
        match_count: Optional[int] = None,
        current_match: Optional[int] = None,
        goto_mode: Optional[bool] = None,
        goto_input: Optional[str] = None,
        search_mode: Optional[bool] = None,
        search_input: Optional[str] = None,
    ) -> None:
        """Update status bar information."""
        self.current_line = current_line
        if total_lines is not None:
            self.total_lines = total_lines
        if current_source_line is not None:
            self.current_source_line = current_source_line
        if max_source_line is not None:
            self.max_source_line = max_source_line
        if search_pattern is not None:
            self.search_pattern = search_pattern
        if match_count is not None:
            self.match_count = match_count
        if current_match is not None:
            self.current_match = current_match
        if goto_mode is not None:
            self.goto_mode = goto_mode
        if goto_input is not None:
            self.goto_input = goto_input
        if search_mode is not None:
            self.search_mode = search_mode
        if search_input is not None:
            self.search_input = search_input
        self.refresh(layout=True)


class PagerContent(ScrollView):
    """Custom ScrollView with search highlighting and source line mapping.

    All operations use the unified PagerLine model to ensure
    display, search, and navigation are always in sync.
    """

    def __init__(self, content: PagerRenderable, **kwargs: Any) -> None:
        super().__init__(auto_width=True, **kwargs)
        self._content = content
        self._search_highlighter = SearchHighlighter()

    async def update(self, renderable: PagerRenderable) -> None:
        """Update content with a PagerRenderable."""
        self._content = renderable
        await super().update(renderable)

    def set_search_pattern(self, pattern: str, case_sensitive: bool = False) -> bool:
        """Set search pattern and find matches in rendered lines."""
        success = self._search_highlighter.set_pattern(pattern, case_sensitive)
        if success:
            self._search_highlighter.search_pager_lines(self._content.pager_lines)
        return success

    def clear_search(self) -> None:
        """Clear search pattern."""
        self._search_highlighter.set_pattern("")

    def next_match(self) -> Optional[Tuple[int, int, int]]:
        """Get next search match."""
        return self._search_highlighter.next_match()

    def prev_match(self) -> Optional[Tuple[int, int, int]]:
        """Get previous search match."""
        return self._search_highlighter.prev_match()

    @property
    def match_count(self) -> int:
        """Number of search matches."""
        return len(self._search_highlighter.matches)

    @property
    def current_match_index(self) -> int:
        """Current match index."""
        return self._search_highlighter.current_match_index

    @property
    def search_pattern(self) -> Optional[str]:
        """Current search pattern."""
        return self._search_highlighter.pattern

    @property
    def current_match(self) -> Optional[Tuple[int, int, int]]:
        """Current search match."""
        matches = self._search_highlighter.matches
        idx = self._search_highlighter.current_match_index
        if matches and idx >= 0:
            return matches[idx]
        return None

    @property
    def renderable(self) -> PagerRenderable:
        """Access the underlying PagerRenderable."""
        return self._content

    def render(self) -> RenderableType:
        """Render content with search highlighting."""
        if not self._search_highlighter.matches:
            return self._content

        highlighted_segments = self._search_highlighter.highlight_pager_lines(
            self._content.pager_lines
        )

        return self._content.with_highlighted_lines(highlighted_segments)


class PagerApp(App):
    """Enhanced interactive pager app with unified line model and source mapping.

    All features (display, search, navigation) operate on the same set of
    rendered PagerLine objects, with source_line mapping for meaningful
    line number navigation.
    """

    def __init__(
        self,
        *args: Any,
        content: Optional["PreparedContent"] = None,
        console: Optional[Console] = None,
        width: int = 80,
        **kwargs: Any,
    ) -> None:
        self._content = content
        self._console = console or Console()
        self._width = width
        self._pager_renderable: Optional[PagerRenderable] = None
        self._total_lines: int = 0
        super().__init__(*args, **kwargs)

    async def on_load(self, event: events.Load) -> None:
        await self.bind("q", "quit", "Quit")

    def _prepare_content(self) -> PagerRenderable:
        """Render content into unified PagerLine model with source mapping.

        This is the ONLY place where rendering and source mapping happen.

        Source line mapping uses the original text (source_lines) from
        PreparedContent, NOT the rendered line numbers. This ensures :120
        always jumps to source file line 120, regardless of whether
        --line-numbers is enabled.
        """
        console = self._console
        width = self._width

        # Get source_lines from the well-defined PreparedContent object
        source_lines: List[str] = self._content.source_lines if self._content else []

        # Get renderable from PreparedContent
        renderable = self._content.renderable if self._content else ""

        render_options = console.options.update(width=width - 1)
        segment_lines = console.render_lines(
            renderable, render_options, new_lines=True
        )

        pager_lines: List[PagerLine] = []
        for seg_line in segment_lines:
            pager_lines.append(PagerLine.from_segments(seg_line))

        # Use the unified mapping method that works from source_lines,
        # NOT from rendered line numbers.
        if source_lines:
            SourceLineMapper.build_from_source_lines(pager_lines, source_lines)

        # Additional pass to clean up any incorrectly mapped panel borders
        SourceLineMapper.build_for_panel(pager_lines)

        return PagerRenderable(pager_lines, new_lines=True, width=width)

    async def on_mount(self, event: events.Mount) -> None:
        """Set up terminal state and mount UI."""
        TerminalState.save()

        self._pager_renderable = self._prepare_content()
        self._total_lines = self._pager_renderable.total_lines

        self.body = body = PagerContent(self._pager_renderable)
        self.status = PagerStatusBar(
            total_lines=self._total_lines,
            max_source_line=self._pager_renderable.max_source_line,
        )

        await self.view.dock(self.status, edge="bottom", size=1)
        await self.view.dock(body, edge="top")

        await self.body.update(self._pager_renderable)
        await self.body.focus()

    async def on_shutdown_request(self, event: events.ShutdownRequest) -> None:
        """Restore terminal state on shutdown request."""
        TerminalState.restore()

    async def action_quit(self) -> None:
        """Quit the app."""
        TerminalState.restore()
        await super().action_quit()

    def _get_current_source_line(self) -> Optional[int]:
        """Get the source line number for the current screen position."""
        if self._pager_renderable is None:
            return None
        screen_line = int(self.body.y)
        return self._pager_renderable.screen_line_to_source_line(screen_line)

    def _update_status(self) -> None:
        """Update status bar with current state."""
        current_screen_line = int(self.body.y) + 1
        current_screen_line = min(max(current_screen_line, 1), self._total_lines)
        current_source = self._get_current_source_line()

        self.status.update_status(
            current_line=current_screen_line,
            total_lines=self._total_lines,
            current_source_line=current_source,
            max_source_line=self._pager_renderable.max_source_line if self._pager_renderable else 0,
            search_pattern=self.body.search_pattern,
            match_count=self.body.match_count,
            current_match=self.body.current_match_index,
        )

    async def _scroll_to_line(self, line_number: int) -> None:
        """Scroll to specific source line number.

        If source_line mapping exists, jumps to the source file line.
        Otherwise, falls back to screen line number.
        """
        if self._total_lines == 0 or self._pager_renderable is None:
            return

        # Try source line mapping first
        screen_idx = self._pager_renderable.source_line_to_screen_line(line_number)
        if screen_idx is not None:
            target_y = screen_idx
        else:
            # Fall back to screen line
            target_y = max(0, min(line_number - 1, self._total_lines - 1))

        self.body.target_y = target_y
        self.body.animate("y", target_y, easing="out_cubic")
        self._update_status()

    async def _scroll_to_match(self, match: Tuple[int, int, int]) -> None:
        """Scroll to a search match (by screen line index)."""
        line_idx, _, _ = match
        target_y = max(0, min(line_idx, self._total_lines - 1))
        self.body.target_y = target_y
        self.body.animate("y", target_y, easing="out_cubic")
        self._update_status()

    async def on_key(self, event: events.Key) -> None:
        if self.status.goto_mode:
            await self._handle_goto_key(event)
            return

        if self.status.search_mode:
            await self._handle_search_key(event)
            return

        key = event.key

        if key == "j" or key == "down":
            self.body.scroll_up()
            self._update_status()
        elif key == "k" or key == "up":
            self.body.scroll_down()
            self._update_status()
        elif key == " ":
            self.body.page_down()
            self._update_status()
        elif key == "ctrl+u":
            self.body.target_y -= self.body.size.height // 2
            self.body.target_y = max(0, self.body.target_y)
            self.body.animate("y", self.body.target_y, easing="out_cubic")
            self._update_status()
        elif key == "ctrl+d":
            self.body.target_y += self.body.size.height // 2
            self.body.target_y = min(
                self._total_lines - 1, self.body.target_y
            )
            self.body.animate("y", self.body.target_y, easing="out_cubic")
            self._update_status()
        elif key == "g":
            if self._pager_renderable and self._pager_renderable.max_source_line > 0:
                await self._scroll_to_line(1)
            else:
                await self._scroll_to_line(1)
        elif key == "G":
            if self._pager_renderable and self._pager_renderable.max_source_line > 0:
                await self._scroll_to_line(self._pager_renderable.max_source_line)
            else:
                await self._scroll_to_line(self._total_lines)
        elif key == "/":
            self.status.update_status(
                current_line=int(self.body.y) + 1,
                search_mode=True,
                search_input="",
            )
        elif key == "n":
            if self.body.match_count > 0:
                match = self.body.next_match()
                if match:
                    await self._scroll_to_match(match)
        elif key == "N":
            if self.body.match_count > 0:
                match = self.body.prev_match()
                if match:
                    await self._scroll_to_match(match)
        elif key == ":":
            self.status.update_status(
                current_line=int(self.body.y) + 1,
                goto_mode=True,
                goto_input="",
            )
        elif key == "escape":
            self.body.clear_search()
            self.body.refresh()
            self._update_status()

    async def _handle_goto_key(self, event: events.Key) -> None:
        """Handle keys in goto mode."""
        key = event.key

        if key == "escape":
            self.status.update_status(
                current_line=int(self.body.y) + 1,
                goto_mode=False,
                goto_input="",
            )
        elif key == "enter":
            try:
                line_num = int(self.status.goto_input)
                await self._scroll_to_line(line_num)
            except ValueError:
                pass
            self.status.update_status(
                current_line=int(self.body.y) + 1,
                goto_mode=False,
                goto_input="",
            )
        elif key == "backspace":
            new_input = self.status.goto_input[:-1]
            self.status.update_status(
                current_line=int(self.body.y) + 1,
                goto_input=new_input,
            )
        elif len(key) == 1 and key.isdigit():
            new_input = self.status.goto_input + key
            self.status.update_status(
                current_line=int(self.body.y) + 1,
                goto_input=new_input,
            )

    async def _handle_search_key(self, event: events.Key) -> None:
        """Handle keys in search mode."""
        key = event.key

        if key == "escape":
            self.status.update_status(
                current_line=int(self.body.y) + 1,
                search_mode=False,
                search_input="",
            )
        elif key == "enter":
            pattern = self.status.search_input
            if pattern:
                self.body.set_search_pattern(pattern)
                self.body.refresh()
                if self.body.match_count > 0:
                    match = self.body.current_match
                    if match:
                        await self._scroll_to_match(match)
            self.status.update_status(
                current_line=int(self.body.y) + 1,
                search_mode=False,
                search_input="",
                search_pattern=self.body.search_pattern,
                match_count=self.body.match_count,
                current_match=self.body.current_match_index,
            )
        elif key == "backspace":
            new_input = self.status.search_input[:-1]
            self.status.update_status(
                current_line=int(self.body.y) + 1,
                search_input=new_input,
            )
        elif len(key) == 1:
            new_input = self.status.search_input + key
            self.status.update_status(
                current_line=int(self.body.y) + 1,
                search_input=new_input,
            )

    async def action_scroll_up(self) -> None:
        await super().action_scroll_up()
        self._update_status()

    async def action_scroll_down(self) -> None:
        await super().action_scroll_down()
        self._update_status()

    async def action_page_up(self) -> None:
        await super().action_page_up()
        self._update_status()

    async def action_page_down(self) -> None:
        await super().action_page_down()
        self._update_status()


# Import PreparedContent for type hints, placed at bottom to avoid circular import
from rich_cli.__main__ import PreparedContent  # noqa: E402
