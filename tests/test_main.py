import click
from click import Command
from click.decorators import FC, Parameter
from click.testing import CliRunner


class DuplicateOptionsError(ValueError):
    pass


def test_duplicate_option_flags_raises_exception(monkeypatch):
    """Create a test that will monkeypatch the click.option decorators
    so that they fail noisily when options are duplicated for a command
    """

    def _param_memo_safe(f: FC, param: Parameter) -> None:
        if isinstance(f, Command):
            f.params.append(param)
        else:
            if not hasattr(f, "__click_params__"):
                f.__click_params__ = []  # type: ignore
            else:
                for opt in param.opts:
                    for preexisting_param in f.__click_params__:
                        if opt in preexisting_param.opts:
                            raise DuplicateOptionsError(
                                "Duplicate option added to command."
                                + " The following option appears more than once:\n"
                                + f"{opt} (used for {param.human_readable_name}"
                                + f" and {preexisting_param.human_readable_name})"
                            )

            f.__click_params__.append(param)  # type: ignore

    monkeypatch.setattr(click.decorators, "_param_memo", _param_memo_safe)

    # import here (after monkeypatch) because decorators are run on import
    from rich_cli.__main__ import main

    runner = CliRunner()
    runner.invoke(main)


def test_unified_export_options_registry():
    """ExportOptions should expose the full set of unified export fields."""
    from rich_cli.export import ExportOptions

    options = ExportOptions(
        title="t",
        theme="monokai",
        source_path="/tmp/foo.py",
        generated_at="2024-01-01T00:00:00+00:00",
        inline_styles=True,
    )
    assert options.has_metadata() is True
    assert options.title == "t"
    assert options.theme == "monokai"
    assert options.source_path == "/tmp/foo.py"
    assert options.generated_at == "2024-01-01T00:00:00+00:00"
    assert options.inline_styles is True

    empty = ExportOptions()
    assert empty.has_metadata() is False


def test_main_registers_new_export_options():
    """The CLI should register the new unified export option flags."""
    from rich_cli.__main__ import main

    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    help_text = result.output
    for flag in (
        "--export-meta",
        "--export-source",
        "--no-export-time",
        "--export-inline-styles",
    ):
        assert flag in help_text, f"Missing option flag in help: {flag}"


def test_export_metadata_renders_in_terminal_and_html(tmp_path):
    """With --export-meta the metadata should appear both in the terminal
    output and in the generated HTML export."""
    from rich_cli.__main__ import main

    html_path = tmp_path / "out.html"
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--print",
            "--export-meta",
            "--title",
            "Example",
            "--theme",
            "monokai",
            "--export-source",
            "/tmp/example.py",
            "--export-html",
            str(html_path),
            "Hello, [b]World[/b]!",
        ],
    )
    assert result.exit_code == 0, result.output
    # terminal output carries the metadata block
    assert "Example" in result.output
    assert "theme: monokai" in result.output
    assert "source: /tmp/example.py" in result.output
    assert "generated:" in result.output
    # HTML export captures the same metadata
    assert html_path.exists()
    html = html_path.read_text(encoding="utf-8")
    assert "Example" in html
    assert "theme: monokai" in html
    assert "source: /tmp/example.py" in html


def test_no_export_time_suppresses_timestamp():
    """--no-export-time should suppress the generated: line."""
    from rich_cli.__main__ import main

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--print",
            "--export-meta",
            "--no-export-time",
            "--title",
            "Only Title",
            "hi",
        ],
    )
    assert result.exit_code == 0
    assert "Only Title" in result.output
    assert "generated:" not in result.output


def test_export_meta_disabled_by_default():
    """Without --export-meta no metadata header should appear."""
    from rich_cli.__main__ import main

    runner = CliRunner()
    result = runner.invoke(main, ["--print", "--title", "Hidden", "hi"])
    assert result.exit_code == 0
    assert "Hidden" not in result.output  # only used as panel title
    assert "theme:" not in result.output
    assert "source:" not in result.output
    assert "generated:" not in result.output


def test_build_export_options_from_cli_args():
    """build_export_options should correctly map CLI flags to ExportOptions."""
    from rich_cli.export import build_export_options

    options = build_export_options(
        export_meta=True,
        title="My Title",
        theme="monokai",
        resource="/tmp/test.py",
        export_source="",
        no_export_time=False,
        export_inline_styles=True,
    )
    assert options.title == "My Title"
    assert options.theme == "monokai"
    assert options.source_path == "/tmp/test.py"
    assert options.generated_at is not None
    assert options.inline_styles is True
    assert options.has_metadata() is True


def test_build_export_options_disabled():
    """When export_meta is False, all metadata fields should be None."""
    from rich_cli.export import build_export_options

    options = build_export_options(
        export_meta=False,
        title="Ignored",
        theme="monokai",
        resource="/tmp/test.py",
        no_export_time=False,
        export_inline_styles=False,
    )
    assert options.title is None
    assert options.theme is None
    assert options.source_path is None
    assert options.generated_at is None
    assert options.inline_styles is False
    assert options.has_metadata() is False


def test_build_export_options_no_export_time():
    """no_export_time should suppress the generated_at field."""
    from rich_cli.export import build_export_options

    options = build_export_options(
        export_meta=True,
        title="T",
        no_export_time=True,
    )
    assert options.title == "T"
    assert options.generated_at is None


def test_build_export_options_stdin_resource():
    """resource='-' should not appear as source_path."""
    from rich_cli.export import build_export_options

    options = build_export_options(
        export_meta=True,
        resource="-",
        title="stdin",
    )
    assert options.source_path is None
    assert options.title == "stdin"


def test_save_exports_dispatch(tmp_path):
    """save_exports should route to the correct Console.save_* methods."""
    from rich.console import Console
    from rich_cli.export import ExportOptions, ExportTarget, save_exports

    console = Console(record=True)
    console.print("hello")

    html_path = tmp_path / "out.html"
    svg_path = tmp_path / "out.svg"

    options = ExportOptions(title="T", inline_styles=True)
    targets = [
        ExportTarget(format="html", path=str(html_path)),
        ExportTarget(format="svg", path=str(svg_path)),
    ]
    save_exports(console, options, targets)

    assert html_path.exists()
    assert svg_path.exists()
    html = html_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    svg = svg_path.read_text(encoding="utf-8")
    assert '<svg class="rich-terminal"' in svg


def test_build_export_targets_no_paths():
    """build_export_targets should return empty list when no paths given."""
    from rich_cli.export import build_export_targets

    targets = build_export_targets()
    assert targets == []


def test_build_export_targets_html_only():
    """build_export_targets should return html target when only html path given."""
    from rich_cli.export import build_export_targets

    targets = build_export_targets(export_html="/tmp/out.html")
    assert len(targets) == 1
    assert targets[0].format == "html"
    assert targets[0].path == "/tmp/out.html"


def test_build_export_targets_svg_only():
    """build_export_targets should return svg target when only svg path given."""
    from rich_cli.export import build_export_targets

    targets = build_export_targets(export_svg="/tmp/out.svg")
    assert len(targets) == 1
    assert targets[0].format == "svg"
    assert targets[0].path == "/tmp/out.svg"


def test_build_export_targets_both():
    """build_export_targets should return both targets when both paths given."""
    from rich_cli.export import build_export_targets

    targets = build_export_targets(
        export_html="/tmp/out.html", export_svg="/tmp/out.svg"
    )
    assert len(targets) == 2
    formats = {t.format for t in targets}
    assert formats == {"html", "svg"}


def test_save_exports_unknown_format_raises():
    """save_exports should error on unknown format but still clear buffer."""
    from rich.console import Console
    from rich_cli.export import ExportOptions, ExportTarget, save_exports

    console = Console(record=True)
    console.print("hello")

    content_before = console.export_html(clear=False)

    options = ExportOptions()
    targets = [ExportTarget(format="pdf", path="/tmp/out.pdf")]

    try:
        save_exports(console, options, targets)
        assert False, "Should have raised an error for unknown format"
    except SystemExit:
        pass

    # After the error path (which goes through finally), the buffer should
    # be cleared: the HTML wrapper is the same but with no content inside.
    content_after = console.export_html(clear=False)
    assert len(content_after) < len(content_before)


def test_save_exports_no_targets_is_noop():
    """save_exports with no targets should not crash and not touch the buffer."""
    from rich.console import Console
    from rich_cli.export import ExportOptions, save_exports

    console = Console(record=True)
    console.print("hello")

    content_before = console.export_html(clear=False)
    save_exports(console, ExportOptions(), [])
    content_after = console.export_html(clear=False)

    # Buffer should be untouched (no targets → early return before clearing)
    assert content_before == content_after
    assert content_before != ""


def test_save_exports_clears_buffer_after_all_targets(tmp_path):
    """After save_exports completes, the record buffer should be empty."""
    from rich.console import Console
    from rich_cli.export import ExportOptions, ExportTarget, save_exports

    console = Console(record=True)
    console.print("hello")

    content_before = console.export_html(clear=False)

    html_path = tmp_path / "out.html"
    svg_path = tmp_path / "out.svg"

    options = ExportOptions(title="T", inline_styles=True)
    targets = [
        ExportTarget(format="html", path=str(html_path)),
        ExportTarget(format="svg", path=str(svg_path)),
    ]
    save_exports(console, options, targets)

    assert html_path.exists()
    assert svg_path.exists()
    # Buffer should be empty after all saves
    content_after = console.export_html(clear=False)
    assert len(content_after) < len(content_before)


def test_save_exports_error_still_clears_buffer(tmp_path):
    """If a save raises, the record buffer should still be cleared."""
    from unittest.mock import patch
    from rich.console import Console
    from rich_cli.export import ExportOptions, ExportTarget, save_exports

    console = Console(record=True)
    console.print("hello")

    content_before = console.export_html(clear=False)

    bad_path = tmp_path / "nonexistent" / "out.html"

    options = ExportOptions()
    targets = [ExportTarget(format="html", path=str(bad_path))]

    try:
        with patch(
            "rich_cli.export._save_html",
            side_effect=OSError("disk full"),
        ):
            save_exports(console, options, targets)
        assert False, "Should have raised SystemExit from on_error"
    except SystemExit:
        pass

    # Buffer should be empty even after the error (finally block ran)
    content_after = console.export_html(clear=False)
    assert len(content_after) < len(content_before)
