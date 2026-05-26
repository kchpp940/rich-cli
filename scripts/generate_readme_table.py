#!/usr/bin/env python3
"""Generate the optional dependencies table in README.md from EXTRAS metadata.

Ensures README documentation stays in sync with the code.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
OPTIONAL_DEPS_FILE = ROOT / "src" / "rich_cli" / "optional_dependencies.py"
README_FILE = ROOT / "README.md"


def get_extras_metadata() -> dict:
    namespace = {}
    exec(OPTIONAL_DEPS_FILE.read_text(), namespace)
    return namespace.get("EXTRAS", {})


def generate_table(extras: dict) -> str:
    lines = [
        "| Feature | Installation Command |",
        "|---------|---------------------|",
    ]

    for name in sorted(extras.keys()):
        extra = extras[name]
        lines.append(f"| {extra['description']} | `{extra['install_command']}` |")

    lines.append("| All optional features | `pip install rich-cli[full]` |")

    return "\n".join(lines)


def main() -> int:
    extras = get_extras_metadata()
    table = generate_table(extras)

    readme_content = README_FILE.read_text()

    start_marker = "### Optional Dependencies"
    end_marker = "## Rich command"

    if start_marker not in readme_content or end_marker not in readme_content:
        print("Error: Could not find table markers in README.md", file=sys.stderr)
        return 1

    start_idx = readme_content.index(start_marker) + len(start_marker)
    end_idx = readme_content.index(end_marker)

    # Find the table section (between start marker and end marker)
    section_before = readme_content[:start_idx]
    section_after = readme_content[end_idx:]

    new_content = f"""{section_before}

Rich-CLI has optional dependencies for additional features. Install them with:

{table}

For pipx users, use the `--pip-args` flag:

```
pipx install rich-cli --pip-args "rich-cli[full]"
```

When a feature requiring an optional dependency is used without it being installed, Rich-CLI will provide a clear error message with the installation command.

{section_after}"""

    README_FILE.write_text(new_content)
    print(f"✓ Updated README.md with {len(extras)} optional dependencies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
