"""Command line option metadata and documentation generation for rich-cli.

This module contains ONLY option documentation metadata and documentation
generation logic. It should NOT contain any runtime constants or CLI
execution logic. Runtime constants live in constants.py.
"""

OPTION_GROUPS = [
    {
        "name": "输入来源",
        "description": "控制输入数据的来源和解析方式",
        "options": [
            "lexer",
            "force_terminal",
        ],
    },
    {
        "name": "渲染格式",
        "description": "指定内容的渲染格式",
        "options": [
            "_print",
            "syntax",
            "json",
            "markdown",
            "rst",
            "rule",
            "inspect",
        ],
    },
    {
        "name": "显示样式",
        "description": "控制输出的外观和布局",
        "options": [
            "emoji",
            "left",
            "right",
            "center",
            "text_left",
            "text_right",
            "text_center",
            "text_full",
            "soft",
            "expand",
            "width",
            "max_width",
            "style",
            "rule_style",
            "rule_char",
            "padding",
            "panel",
            "panel_style",
            "title",
            "caption",
            "theme",
            "line_numbers",
            "guides",
            "hyperlinks",
            "no_wrap",
        ],
    },
    {
        "name": "Notebook",
        "description": "Jupyter notebook 相关选项",
        "options": [
            "ipynb",
        ],
    },
    {
        "name": "CSV",
        "description": "CSV/TSV 表格相关选项",
        "options": [
            "csv",
            "head",
            "tail",
        ],
    },
    {
        "name": "导出",
        "description": "导出输出内容到文件",
        "options": [
            "export_html",
            "export_svg",
        ],
    },
    {
        "name": "Pager",
        "description": "分页显示相关选项",
        "options": [
            "pager",
        ],
    },
    {
        "name": "其他",
        "description": "其他杂项选项",
        "options": [
            "version",
        ],
    },
]

OPTION_METADATA = {
    "resource": {
        "long_opt": "<PATH or TEXT or '-'>",
        "short_opt": "",
        "metavar": "",
        "group": "输入来源",
        "description_cn": "输入文件路径、文本、URL 或 '-'（从标准输入读取）",
        "description_rich": "",
        "notes": "",
    },
    "lexer": {
        "long_opt": "--lexer",
        "short_opt": "-x",
        "metavar": "LEXER",
        "group": "输入来源",
        "description_cn": "指定语法高亮的词法分析器。参见 [Pygments lexers](https://pygments.org/docs/lexers/)",
        "description_rich": "Use [b]LEXER[/b] for syntax highlighting. [dim]See https://pygments.org/docs/lexers/",
        "notes": "",
    },
    "force_terminal": {
        "long_opt": "--force-terminal",
        "short_opt": "",
        "metavar": "",
        "group": "输入来源",
        "description_cn": "即使输出不是终端，也强制使用终端格式输出",
        "description_rich": "Force terminal output when not writing to a terminal.",
        "notes": "",
    },
    "_print": {
        "long_opt": "--print",
        "short_opt": "-p",
        "metavar": "",
        "group": "渲染格式",
        "description_cn": "解析并渲染 [控制台标记](https://rich.readthedocs.io/en/latest/markup.html)",
        "description_rich": "Print [u]console markup[/u]. [dim]See https://rich.readthedocs.io/en/latest/markup.html",
        "notes": "",
    },
    "syntax": {
        "long_opt": "--syntax",
        "short_opt": "",
        "metavar": "",
        "group": "渲染格式",
        "description_cn": "启用语法高亮",
        "description_rich": "[u]Syntax[/u] highlighting.",
        "notes": "",
    },
    "json": {
        "long_opt": "--json",
        "short_opt": "-J",
        "metavar": "",
        "group": "渲染格式",
        "description_cn": "以 JSON 格式显示",
        "description_rich": "Display as [u]JSON[/u].",
        "notes": "",
    },
    "markdown": {
        "long_opt": "--markdown",
        "short_opt": "-m",
        "metavar": "",
        "group": "渲染格式",
        "description_cn": "以 Markdown 格式显示",
        "description_rich": "Display as [u]markdown[/u].",
        "notes": "",
    },
    "rst": {
        "long_opt": "--rst",
        "short_opt": "",
        "metavar": "",
        "group": "渲染格式",
        "description_cn": "以 reStructuredText 格式显示",
        "description_rich": "Display [u]restructured text[/u].",
        "notes": "",
    },
    "rule": {
        "long_opt": "--rule",
        "short_opt": "-u",
        "metavar": "",
        "group": "渲染格式",
        "description_cn": "显示水平分隔线",
        "description_rich": "Display a horizontal [u]rule[/u].",
        "notes": "",
    },
    "inspect": {
        "long_opt": "--inspect",
        "short_opt": "",
        "metavar": "",
        "group": "渲染格式",
        "description_cn": "检查 Python 对象",
        "description_rich": "[u]Inspect[/u] a python object.",
        "notes": "",
    },
    "emoji": {
        "long_opt": "--emoji",
        "short_opt": "-j",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "启用表情符号代码，例如 `:sparkle:`",
        "description_rich": "Enable emoji code. [dim]e.g. :sparkle:",
        "notes": "",
    },
    "left": {
        "long_opt": "--left",
        "short_opt": "-l",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "整体内容左对齐",
        "description_rich": "Align to left.",
        "notes": "",
    },
    "right": {
        "long_opt": "--right",
        "short_opt": "-r",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "整体内容右对齐",
        "description_rich": "Align to right.",
        "notes": "",
    },
    "center": {
        "long_opt": "--center",
        "short_opt": "-c",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "整体内容居中",
        "description_rich": "Align to center.",
        "notes": "",
    },
    "text_left": {
        "long_opt": "--text-left",
        "short_opt": "-L",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "文本内容左对齐",
        "description_rich": "Justify text to left.",
        "notes": "",
    },
    "text_right": {
        "long_opt": "--text-right",
        "short_opt": "-R",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "文本内容右对齐",
        "description_rich": "Justify text to right.",
        "notes": "",
    },
    "text_center": {
        "long_opt": "--text-center",
        "short_opt": "-C",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "文本内容居中",
        "description_rich": "Justify text to center.",
        "notes": "",
    },
    "text_full": {
        "long_opt": "--text-full",
        "short_opt": "-F",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "文本内容两端对齐",
        "description_rich": "Justify text to both left and right edges.",
        "notes": "",
    },
    "soft": {
        "long_opt": "--soft",
        "short_opt": "",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "启用软换行（需要 `--print`）",
        "description_rich": "Enable soft wrapping of text (requires --print).",
        "notes": "",
    },
    "expand": {
        "long_opt": "--expand",
        "short_opt": "-e",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "展开到全宽（需要 `--panel`）",
        "description_rich": "Expand to full width (requires --panel).",
        "notes": "",
    },
    "width": {
        "long_opt": "--width",
        "short_opt": "-w",
        "metavar": "SIZE",
        "group": "显示样式",
        "description_cn": "设置输出宽度为 SIZE 字符",
        "description_rich": "Fit output to [b]SIZE[/] characters.",
        "notes": "",
    },
    "max_width": {
        "long_opt": "--max-width",
        "short_opt": "-W",
        "metavar": "SIZE",
        "group": "显示样式",
        "description_cn": "设置最大宽度为 SIZE 字符",
        "description_rich": "Set maximum width to [b]SIZE[/] characters.",
        "notes": "",
    },
    "style": {
        "long_opt": "--style",
        "short_opt": "-s",
        "metavar": "STYLE",
        "group": "显示样式",
        "description_cn": "设置文本样式，参见 [Rich 样式语法](https://rich.readthedocs.io/en/latest/style.html)",
        "description_rich": "Set text style to [b]STYLE[/b].",
        "notes": "",
    },
    "rule_style": {
        "long_opt": "--rule-style",
        "short_opt": "",
        "metavar": "STYLE",
        "group": "显示样式",
        "description_cn": "设置分隔线样式",
        "description_rich": "Set rule style to [b]STYLE[/b].",
        "notes": "",
    },
    "rule_char": {
        "long_opt": "--rule-char",
        "short_opt": "",
        "metavar": "CHARACTER",
        "group": "显示样式",
        "description_cn": "设置分隔线使用的字符",
        "description_rich": "Use [b]CHARACTER[/b] to generate a line with --rule.",
        "notes": "",
    },
    "padding": {
        "long_opt": "--padding",
        "short_opt": "-d",
        "metavar": "TOP,RIGHT,BOTTOM,LEFT",
        "group": "显示样式",
        "description_cn": "设置输出内边距，1、2 或 4 个逗号分隔的整数，例如 `2,4`",
        "description_rich": "Padding around output. [dim]1, 2 or 4 comma separated integers, e.g. 2,4",
        "notes": "",
    },
    "panel": {
        "long_opt": "--panel",
        "short_opt": "-a",
        "metavar": "BOX",
        "group": "显示样式",
        "description_cn": "设置面板边框样式：`ascii`, `ascii2`, `double`, `heavy`, `none`, `rounded`, `square`",
        "description_rich": "Set panel type to [b]BOX[/b]. [dim]ascii, ascii2, double, heavy, none, rounded, square",
        "notes": "",
    },
    "panel_style": {
        "long_opt": "--panel-style",
        "short_opt": "-S",
        "metavar": "STYLE",
        "group": "显示样式",
        "description_cn": "设置面板样式（需要 `--panel`）",
        "description_rich": "Set the panel style to [b]STYLE[/b] (requires --panel).",
        "notes": "",
    },
    "title": {
        "long_opt": "--title",
        "short_opt": "",
        "metavar": "TEXT",
        "group": "显示样式",
        "description_cn": "设置面板标题",
        "description_rich": "Set panel title to [b]TEXT[/b].",
        "notes": "",
    },
    "caption": {
        "long_opt": "--caption",
        "short_opt": "",
        "metavar": "TEXT",
        "group": "显示样式",
        "description_cn": "设置面板说明文字",
        "description_rich": "Set panel caption to [b]TEXT[/b].",
        "notes": "",
    },
    "theme": {
        "long_opt": "--theme",
        "short_opt": "",
        "metavar": "THEME",
        "group": "显示样式",
        "description_cn": "设置语法高亮主题，参见 [Pygments 主题](https://pygments.org/styles/)。也可通过环境变量 `RICH_THEME` 设置",
        "description_rich": "Set syntax theme to [b]THEME[/b]. [dim]See https://pygments.org/styles/",
        "notes": "",
    },
    "line_numbers": {
        "long_opt": "--line-numbers",
        "short_opt": "-n",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "显示行号",
        "description_rich": "Enable line number in syntax.",
        "notes": "",
    },
    "guides": {
        "long_opt": "--guides",
        "short_opt": "-g",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "显示缩进参考线",
        "description_rich": "Enable indentation guides in syntax highlighting",
        "notes": "",
    },
    "hyperlinks": {
        "long_opt": "--hyperlinks",
        "short_opt": "-y",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "在 Markdown 中渲染超链接",
        "description_rich": "Render hyperlinks in markdown.",
        "notes": "",
    },
    "no_wrap": {
        "long_opt": "--no-wrap",
        "short_opt": "",
        "metavar": "",
        "group": "显示样式",
        "description_cn": "禁用语法高亮文件的自动换行",
        "description_rich": "Don't word wrap syntax highlighted files.",
        "notes": "",
    },
    "ipynb": {
        "long_opt": "--ipynb",
        "short_opt": "",
        "metavar": "",
        "group": "Notebook",
        "description_cn": "以 Jupyter notebook 格式显示。如果文件以 `.ipynb` 结尾会自动检测",
        "description_rich": "Display [u]Jupyter notebook[/u].",
        "notes": "支持所有语法高亮和 Markdown 相关选项",
    },
    "csv": {
        "long_opt": "--csv",
        "short_opt": "",
        "metavar": "",
        "group": "CSV",
        "description_cn": "以表格形式显示 CSV。如果文件以 `.csv` 或 `.tsv` 结尾会自动检测",
        "description_rich": "Display [u]CSV[/u] as a table.",
        "notes": "",
    },
    "head": {
        "long_opt": "--head",
        "short_opt": "-h",
        "metavar": "LINES",
        "group": "CSV",
        "description_cn": "只显示前 LINES 行（需要 `--syntax` 或 `--csv`）",
        "description_rich": "Display first [b]LINES[/] of the file (requires --syntax or --csv).",
        "notes": "",
    },
    "tail": {
        "long_opt": "--tail",
        "short_opt": "-t",
        "metavar": "LINES",
        "group": "CSV",
        "description_cn": "只显示后 LINES 行（需要 `--syntax` 或 `--csv`）",
        "description_rich": "Display last [b]LINES[/] of the file (requires --syntax or --csv).",
        "notes": "",
    },
    "export_html": {
        "long_opt": "--export-html",
        "short_opt": "-o",
        "metavar": "PATH",
        "group": "导出",
        "description_cn": "将输出导出为 HTML 文件",
        "description_rich": "Write HTML to [b]PATH[/b].",
        "notes": "",
    },
    "export_svg": {
        "long_opt": "--export-svg",
        "short_opt": "",
        "metavar": "PATH",
        "group": "导出",
        "description_cn": "将输出导出为 SVG 文件",
        "description_rich": "Write SVG to [b]PATH[/b].",
        "notes": "",
    },
    "pager": {
        "long_opt": "--pager",
        "short_opt": "",
        "metavar": "",
        "group": "Pager",
        "description_cn": "在交互式分页器中显示内容。支持光标键、PageUp/PageDown、Home/End 以及 vi 风格的 j/k/ctrl-d/ctrl-u 导航",
        "description_rich": "Display in an interactive pager.",
        "notes": "",
    },
    "version": {
        "long_opt": "--version",
        "short_opt": "-v",
        "metavar": "",
        "group": "其他",
        "description_cn": "显示版本信息并退出",
        "description_rich": "Print version and exit.",
        "notes": "",
    },
}


def generate_readme_options_table() -> str:
    """Generate README format option tables from OPTION_METADATA.

    Returns:
        str: README format option reference documentation
    """
    lines = []
    lines.append("## 命令行选项参考")
    lines.append("")
    lines.append("Rich CLI 的命令行选项按以下类别组织，方便快速查找：")
    lines.append("")

    for group in OPTION_GROUPS:
        group_name = group["name"]
        group_desc = group["description"]
        group_options = group["options"]

        lines.append(f"### {group_name}")
        lines.append("")
        lines.append(f"{group_desc}。")
        lines.append("")
        lines.append("| 选项 | 短选项 | 说明 |")
        lines.append("|------|--------|------|")

        if group_name == "输入来源":
            meta = OPTION_METADATA["resource"]
            opt_str = f"`{meta['long_opt']}`"
            short_str = "-" if not meta["short_opt"] else f"`{meta['short_opt']}`"
            desc = meta["description_cn"]
            if meta.get("notes"):
                desc += f"。{meta['notes']}"
            lines.append(f"| {opt_str} | {short_str} | {desc} |")

        for opt_name in group_options:
            if opt_name in OPTION_METADATA:
                meta = OPTION_METADATA[opt_name]
                opt_str = f"`{meta['long_opt']}`"
                if meta["metavar"]:
                    opt_str += f" `{meta['metavar']}`"
                short_str = "-" if not meta["short_opt"] else f"`{meta['short_opt']}`"
                desc = meta["description_cn"]
                if meta.get("notes"):
                    desc += f"。{meta['notes']}"
                lines.append(f"| {opt_str} | {short_str} | {desc} |")

        lines.append("")

    return "\n".join(lines)


def update_readme_with_options(readme_path: str) -> None:
    """Update README.md with auto-generated option tables.

    Looks for markers <!-- BEGIN OPTIONS --> and <!-- END OPTIONS -->
    and replaces content between them.

    Args:
        readme_path (str): Path to README.md file
    """
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    begin_marker = "<!-- BEGIN OPTIONS -->"
    end_marker = "<!-- END OPTIONS -->"

    generated_content = generate_readme_options_table()

    if begin_marker in content and end_marker in content:
        before = content.split(begin_marker)[0]
        after = content.split(end_marker)[1]
        new_content = before + begin_marker + "\n\n" + generated_content + "\n\n" + end_marker + after

        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    else:
        raise ValueError(
            f"Markers {begin_marker} and {end_marker} not found in {readme_path}"
        )


def check_readme_options(readme_path: str) -> bool:
    """Check if README.md option tables are in sync with metadata.

    Args:
        readme_path (str): Path to README.md file

    Returns:
        bool: True if in sync, False if needs update
    """
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    begin_marker = "<!-- BEGIN OPTIONS -->"
    end_marker = "<!-- END OPTIONS -->"

    if begin_marker not in content or end_marker not in content:
        print(f"Error: Markers not found in {readme_path}")
        return False

    generated_content = generate_readme_options_table()

    before = content.split(begin_marker)[0]
    after = content.split(end_marker)[1]
    expected_content = before + begin_marker + "\n\n" + generated_content + "\n\n" + end_marker + after

    return content == expected_content


if __name__ == "__main__":
    import argparse
    import os
    import sys

    parser = argparse.ArgumentParser(
        description="Sync README.md option tables with metadata"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if README is in sync with metadata",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Update README with generated option tables",
    )
    parser.add_argument(
        "--readme",
        type=str,
        default=None,
        help="Path to README.md (default: auto-detect)",
    )

    args = parser.parse_args()

    if args.readme:
        readme_path = args.readme
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir))
        readme_path = os.path.join(project_root, "README.md")

    if not os.path.exists(readme_path):
        print(f"Error: {readme_path} not found")
        sys.exit(1)

    if args.check:
        if check_readme_options(readme_path):
            print("README is in sync with metadata")
            sys.exit(0)
        else:
            print("README needs update. Run with --write to update.")
            sys.exit(1)
    elif args.write:
        try:
            update_readme_with_options(readme_path)
            print(f"Updated {readme_path}")
            sys.exit(0)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        parser.print_help()
        print()
        print("Examples:")
        print("  python -m rich_cli.options --check")
        print("  python -m rich_cli.options --write")
        print("  python -m rich_cli.options --check --readme /path/to/README.md")
