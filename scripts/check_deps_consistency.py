#!/usr/bin/env python3
"""Check consistency of optional dependencies across code, pyproject.toml, and README.

Verifies that:
1. All extras used in require_extra() calls exist in pyproject.toml
2. All extras in pyproject.toml are documented in optional_dependencies.py
3. All extras have entries in the README table
4. The 'full' extra contains all other extras
"""

import ast
import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

ROOT = Path(__file__).parent.parent
OPTIONAL_DEPS_FILE = ROOT / "src" / "rich_cli" / "optional_dependencies.py"
PYPROJECT_FILE = ROOT / "pyproject.toml"
README_FILE = ROOT / "README.md"

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
NC = "\033[0m"


def error(msg: str) -> None:
    print(f"{RED}✗ {msg}{NC}", file=sys.stderr)


def success(msg: str) -> None:
    print(f"{GREEN}✓ {msg}{NC}")


def info(msg: str) -> None:
    print(f"{YELLOW}  {msg}{NC}")


def get_extras_from_code() -> set:
    """Extract all extra names used in require_extra() and _check_extra() calls."""
    extras = set()
    src_dir = ROOT / "src"

    for py_file in src_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    func_name = func.id
                elif isinstance(func, ast.Attribute):
                    func_name = func.attr
                else:
                    continue

                if func_name in ("require_extra", "_check_extra"):
                    if node.args:
                        arg = node.args[0]
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            extras.add(arg.value)

    return extras


def get_extras_from_optional_deps() -> dict:
    """Get extras metadata from optional_dependencies.py."""
    namespace = {}
    exec(OPTIONAL_DEPS_FILE.read_text(), namespace)
    return namespace.get("EXTRAS", {})


def get_extras_from_pyproject() -> dict:
    """Parse pyproject.toml for optional-dependencies."""
    with open(PYPROJECT_FILE, "rb") as f:
        data = tomllib.load(f)
    return data.get("project", {}).get("optional-dependencies", {})


def get_extras_from_readme() -> set:
    """Extract extras names from README table."""
    content = README_FILE.read_text()
    extras = set()

    in_table = False
    for line in content.splitlines():
        if "Optional Dependencies" in line:
            in_table = True
            continue
        if in_table:
            if line.strip().startswith("#"):
                break
            match = re.search(r'rich-cli\[(\w+)\]', line)
            if match:
                extras.add(match.group(1))

    return extras


def main() -> int:
    print(f"{YELLOW}========== 可选依赖一致性检查 =========={NC}")

    code_extras = get_extras_from_code()
    metadata_extras = get_extras_from_optional_deps()
    pyproject_extras = get_extras_from_pyproject()
    readme_extras = get_extras_from_readme()

    errors = []

    print("\n1. 检查代码中实际使用的 extras:")
    for extra in sorted(code_extras):
        info(f"- {extra}")

    print("\n2. 代码使用 vs optional_dependencies.py:")
    missing_in_metadata = code_extras - set(metadata_extras.keys())
    if missing_in_metadata:
        for extra in sorted(missing_in_metadata):
            error(f"代码使用了 {extra!r}，但 optional_dependencies.py 中没有定义")
            errors.append(f"EXTRAS 缺少: {extra}")
    else:
        success("所有代码使用的 extras 在 optional_dependencies.py 中都有定义")

    print("\n3. optional_dependencies.py vs pyproject.toml:")
    metadata_keys = set(k for k in metadata_extras.keys() if k != "full")
    pyproject_keys = set(k for k in pyproject_extras.keys() if k != "full")

    missing_in_pyproject = metadata_keys - pyproject_keys
    extra_in_pyproject = pyproject_keys - metadata_keys

    if missing_in_pyproject:
        for extra in sorted(missing_in_pyproject):
            error(f"optional_dependencies.py 有 {extra!r}，但 pyproject.toml 中没有定义")
            errors.append(f"pyproject 缺少: {extra}")
    if extra_in_pyproject:
        for extra in sorted(extra_in_pyproject):
            error(f"pyproject.toml 有 {extra!r}，但 optional_dependencies.py 中没有定义")
            errors.append(f"optional_dependencies 多余: {extra}")
    if not missing_in_pyproject and not extra_in_pyproject:
        success("optional_dependencies.py 与 pyproject.toml 定义一致")

    print("\n4. 检查 'full' extra 包含所有其他 extras:")
    if "full" in pyproject_extras:
        full_deps = pyproject_extras["full"]
        full_dep_names = set()
        for dep in full_deps:
            name = dep.split()[0].split("<")[0].split(">")[0].split("=")[0].split(";")[0].strip()
            full_dep_names.add(name)

        all_other_dep_names = set()
        for name, deps in pyproject_extras.items():
            if name != "full":
                for dep in deps:
                    dep_name = dep.split()[0].split("<")[0].split(">")[0].split("=")[0].split(";")[0].strip()
                    all_other_dep_names.add(dep_name)

        missing_in_full = all_other_dep_names - full_dep_names
        if missing_in_full:
            for dep in sorted(missing_in_full):
                error(f"'full' extra 缺少依赖: {dep}")
                errors.append(f"full extra 缺少: {dep}")
        else:
            success("'full' extra 包含了所有其他 extras 的依赖")
    else:
        error("pyproject.toml 中没有定义 'full' extra")
        errors.append("缺少 'full' extra")

    print("\n5. optional_dependencies.py vs README:")
    missing_in_readme = metadata_keys - readme_extras
    extra_in_readme = readme_extras - metadata_keys - {"full"}

    if missing_in_readme:
        for extra in sorted(missing_in_readme):
            error(f"optional_dependencies.py 有 {extra!r}，但 README 表格中没有文档")
            errors.append(f"README 缺少: {extra}")
    if extra_in_readme:
        for extra in sorted(extra_in_readme):
            error(f"README 表格有 {extra!r}，但 optional_dependencies.py 中没有定义")
            errors.append(f"README 多余: {extra}")
    if not missing_in_readme and not extra_in_readme:
        success("optional_dependencies.py 与 README 文档一致")

    if "full" in readme_extras:
        success("README 包含 'full' extra 说明")
    else:
        error("README 表格中缺少 'full' extra 说明")
        errors.append("README 缺少: full")

    print()
    if errors:
        error(f"发现 {len(errors)} 个不一致问题，请修复后重试！")
        return 1
    else:
        success("所有一致性检查通过！")
        return 0


if __name__ == "__main__":
    sys.exit(main())
