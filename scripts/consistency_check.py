#!/usr/bin/env python3
"""Rich-CLI 发布前一致性检查工具。

检查以下维度的一致性：
1. 包版本 (pyproject.toml, __main__.py, CHANGELOG)
2. 入口命令 (pyproject.toml vs README)
3. CLI 选项 (代码定义 vs README 文档，双向检查)
4. 导出参数 (--export-html, --export-svg 等)
5. 环境变量配置 (如 RICH_THEME)
6. Profile 支持项 (面板样式等可配置选项枚举值)
"""

import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


PROJECT_ROOT = Path(__file__).parent.parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
MAIN_PATH = PROJECT_ROOT / "src" / "rich_cli" / "__main__.py"
README_PATH = PROJECT_ROOT / "README.md"
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"


ALLOWED_UNDOCUMENTED_OPTS: Set[str] = set()


@dataclass
class CheckResult:
    name: str
    passed: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def red(text: str) -> str:
    return f"\033[0;31m{text}\033[0m"


def green(text: str) -> str:
    return f"\033[0;32m{text}\033[0m"


def yellow(text: str) -> str:
    return f"\033[1;33m{text}\033[0m"


def cyan(text: str) -> str:
    return f"\033[0;36m{text}\033[0m"


def bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def check_versions() -> CheckResult:
    result = CheckResult("包版本一致性检查", True)

    with open(PYPROJECT_PATH, "rb") as f:
        pyproject = tomllib.load(f)
    pyproject_version = pyproject["project"]["version"]

    main_content = MAIN_PATH.read_text()
    version_match = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', main_content)
    if not version_match:
        result.add_error(f"在 {MAIN_PATH} 中未找到 VERSION 常量")
        return result
    main_version = version_match.group(1)

    changelog_content = CHANGELOG_PATH.read_text()
    changelog_versions = re.findall(
        r"##\s*\[([^\]]+)\]\s*-\s*\d{4}-\d{2}-\d{2}", changelog_content
    )
    latest_changelog_version = changelog_versions[0] if changelog_versions else None

    if pyproject_version != main_version:
        result.add_error(
            f"版本不一致: pyproject.toml={pyproject_version}, __main__.py={main_version}"
        )

    if latest_changelog_version and pyproject_version != latest_changelog_version:
        result.add_warning(
            f"最新 CHANGELOG 版本 ({latest_changelog_version}) 与包版本 ({pyproject_version}) 不一致"
        )
    elif not latest_changelog_version:
        result.add_warning("在 CHANGELOG.md 中未找到带日期的版本条目")

    return result


def check_entry_points() -> CheckResult:
    result = CheckResult("入口命令一致性检查", True)

    with open(PYPROJECT_PATH, "rb") as f:
        pyproject = tomllib.load(f)

    scripts = pyproject.get("project", {}).get("scripts", {})
    entry_points = pyproject.get("project", {}).get("entry-points", {})
    pipx_run = entry_points.get("pipx.run", {}) if isinstance(entry_points, dict) else {}

    all_commands: Set[str] = set()
    for name in scripts.keys():
        all_commands.add(name)
    for name in pipx_run.keys():
        all_commands.add(name)

    readme_content = README_PATH.read_text()

    for cmd in all_commands:
        if cmd not in readme_content:
            result.add_error(
                f"入口命令 '{cmd}' 在 pyproject.toml 中定义，但 README.md 中未提及"
            )

    documented_commands = re.findall(r"`(\w+)(?:\s+--\w+)*`", readme_content)
    documented_main_cmds = {c for c in documented_commands if c in {"rich", "rich-cli"}}

    for cmd in documented_main_cmds:
        if cmd not in all_commands:
            result.add_error(
                f"README 中提到的命令 '{cmd}' 在 pyproject.toml 中没有定义入口点"
            )

    return result


def extract_cli_options() -> Dict[str, str]:
    main_content = MAIN_PATH.read_text()
    options: Dict[str, str] = {}

    option_pattern = re.compile(
        r'@click\.option\(\s*"--([\w-]+)"(?:\s*,\s*"-(\w)")?',
        re.MULTILINE,
    )

    for match in option_pattern.finditer(main_content):
        long_opt = match.group(1)
        short_opt = match.group(2)
        options[long_opt] = short_opt or ""

    options["help"] = ""
    if "version" not in options:
        options["version"] = "V"

    return options


def extract_readme_options() -> Set[str]:
    readme_content = README_PATH.read_text()
    options: Set[str] = set()

    long_pattern = re.compile(r"`--([\w-]+)`")
    for match in long_pattern.finditer(readme_content):
        options.add(match.group(1))

    short_pattern = re.compile(r"`-(\w)`")
    for match in short_pattern.finditer(readme_content):
        options.add(match.group(1))

    code_block_pattern = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.DOTALL)
    for block_match in code_block_pattern.finditer(readme_content):
        block = block_match.group(1)
        for long_opt in re.findall(r"--([\w-]+)", block):
            options.add(long_opt)
        for short_opt in re.findall(r"(?<!\w)-(\w)(?!\w)", block):
            if short_opt.isalpha():
                options.add(short_opt)

    return options


def check_cli_options() -> CheckResult:
    result = CheckResult("CLI 选项一致性检查", True)

    code_options = extract_cli_options()
    readme_options = extract_readme_options()

    code_long_opts = set(code_options.keys())
    code_short_opts = {v for v in code_options.values() if v}

    documented_long = {o for o in readme_options if len(o) > 1}
    documented_short = {o for o in readme_options if len(o) == 1}

    for opt in sorted(code_long_opts - documented_long):
        result.add_error(
            f"CLI 选项 '--{opt}' 在代码中定义，但 README 中未说明"
        )

    for opt in sorted(documented_long - code_long_opts):
        result.add_error(
            f"README 中提到的选项 '--{opt}' 在代码中未定义"
        )

    for short in sorted(code_short_opts - documented_short):
        long_opt = next((k for k, v in code_options.items() if v == short), None)
        if long_opt and long_opt not in documented_long:
            result.add_error(
                f"CLI 短选项 '-{short}' (--{long_opt}) 在代码中定义，但 README 中未说明"
            )

    for short in sorted(documented_short - code_short_opts):
        result.add_error(
            f"README 中提到的短选项 '-{short}' 在代码中未定义"
        )

    return result


def check_export_options() -> CheckResult:
    result = CheckResult("导出参数一致性检查", True)

    code_options = extract_cli_options()
    export_opts = {k: v for k, v in code_options.items() if "export" in k.lower()}

    readme_options = extract_readme_options()
    readme_content = README_PATH.read_text()

    for long_opt, short_opt in export_opts.items():
        if long_opt not in readme_options and (not short_opt or short_opt not in readme_options):
            result.add_error(
                f"导出选项 '--{long_opt}' ('-{short_opt}') 在代码中定义，但 README 中未说明"
            )

    documented_exports = re.findall(r"`(--export-[\w-]+)`", readme_content)
    for opt in documented_exports:
        opt_name = opt.lstrip("-")
        if opt_name not in export_opts:
            result.add_error(
                f"README 中提到的导出选项 '{opt}' 在代码中未定义"
            )

    return result


def check_env_vars() -> CheckResult:
    result = CheckResult("环境变量配置检查", True)

    main_content = MAIN_PATH.read_text()
    env_var_pattern = re.compile(r'envvar\s*=\s*["\']([^"\']+)["\']')
    code_env_vars = set(env_var_pattern.findall(main_content))

    readme_content = README_PATH.read_text()
    readme_env_vars: Set[str] = set()
    for match in re.findall(r"`([A-Z_][A-Z0-9_]*)`", readme_content):
        if len(match) > 3:
            readme_env_vars.add(match)

    for env_var in sorted(code_env_vars):
        if env_var not in readme_content:
            result.add_error(
                f"环境变量 '{env_var}' 在代码中支持，但 README 中未说明"
            )

    for env_var in sorted(readme_env_vars & {"RICH_THEME"}):
        if env_var not in code_env_vars:
            result.add_error(
                f"README 中提到的环境变量 '{env_var}' 在代码中未支持"
            )

    return result


def check_profile_support() -> CheckResult:
    result = CheckResult("Profile 支持项检查", True)

    main_content = MAIN_PATH.read_text()

    theme_option = re.search(r'--theme.*?default\s*=\s*["\']([^"\']+)["\']', main_content)
    if theme_option:
        default_theme = theme_option.group(1)
        result.add_warning(
            f"默认语法主题: '{default_theme}'。请确认 README 中主题相关说明与实际支持一致"
        )

    boxes_match = re.search(r"BOXES\s*=\s*\[([^\]]+)\]", main_content)
    if boxes_match:
        boxes = [b.strip().strip('"').strip("'") for b in boxes_match.group(1).split(",") if b.strip()]
        result.add_warning(
            f"支持的面板样式 (--panel): {', '.join(boxes)}。请确认 README 中说明一致"
        )

    return result


def run_all_checks() -> List[CheckResult]:
    checks = [
        check_versions(),
        check_entry_points(),
        check_cli_options(),
        check_export_options(),
        check_env_vars(),
        check_profile_support(),
    ]
    return checks


def print_results(results: List[CheckResult]) -> None:
    print(bold(cyan("=" * 60)))
    print(bold(cyan("Rich-CLI 发布前一致性检查报告")))
    print(bold(cyan("=" * 60)))
    print()

    total_errors = 0
    total_warnings = 0

    for result in results:
        status = green("✓ 通过") if result.passed else red("✗ 失败")
        print(f"{bold(result.name)}: {status}")

        for error in result.errors:
            print(f"  {red('✗')} {error}")
            total_errors += 1

        for warning in result.warnings:
            print(f"  {yellow('!')} {warning}")
            total_warnings += 1

        if not result.errors and not result.warnings:
            print(f"  {green('✓')} 无问题")

        print()

    print(bold(cyan("=" * 60)))
    summary_parts = []
    if total_errors > 0:
        summary_parts.append(red(f"{total_errors} 个错误"))
    if total_warnings > 0:
        summary_parts.append(yellow(f"{total_warnings} 个警告"))

    if total_errors == 0 and total_warnings == 0:
        print(green(bold("所有检查通过！")))
    else:
        print("发现: " + ", ".join(summary_parts))
    print(bold(cyan("=" * 60)))


def main() -> int:
    results = run_all_checks()
    print_results(results)

    has_errors = any(not r.passed for r in results)
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
