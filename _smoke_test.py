"""Quick smoke test of key functionality."""

from rich_cli.__main__ import render_ipynb, _parse_ipynb_cell_range
from rich_cli.notebook_renderer import CellRangeError, EmptyNotebookError
from rich.console import Console
import subprocess
import sys

# Test _parse_ipynb_cell_range
assert _parse_ipynb_cell_range('1-5') == (1, 5)
assert _parse_ipynb_cell_range('3-') == (3, None)
assert _parse_ipynb_cell_range('-10') == (None, 10)
print('✓ Cell range parsing works')

# Test invalid ranges
try:
    _parse_ipynb_cell_range('5-3')
    print('✗ Should have raised CellRangeError')
except CellRangeError:
    print('✓ Correctly rejects start > end')

try:
    _parse_ipynb_cell_range('abc')
    print('✗ Should have raised CellRangeError')
except CellRangeError:
    print('✓ Correctly rejects non-integer bounds')

# Test with actual notebook - code only
r = render_ipynb('test_data/notebook.ipynb', 'ansi_dark', False, '', None, None, False, False, True,
                 ipynb_cell_types='code', ipynb_no_outputs=True)
c = Console(width=80, force_terminal=True)
output = str(c.render_str(r))
assert 'Jupyter Notebook' not in output
assert 'print' in output
print('✓ Code-only filter works')

# Test with actual notebook - markdown only
r = render_ipynb('test_data/notebook.ipynb', 'ansi_dark', False, '', None, None, False, False, True,
                 ipynb_cell_types='markdown')
output = str(c.render_str(r))
assert 'print' not in output
assert 'Jupyter Notebook' in output
print('✓ Markdown-only filter works')

# Test empty after filter raises error
result = subprocess.run(
    [sys.executable, '-m', 'rich_cli', '--ipynb', 'test_data/notebook.ipynb', '--ipynb-cell-types', 'nonexistent'],
    capture_output=True, text=True,
)
assert result.returncode != 0
assert 'empty notebook' in result.stderr.lower() or 'no cells' in result.stderr.lower()
print('✓ Empty notebook error surfaced correctly')

# Test cell range
r = render_ipynb('test_data/notebook.ipynb', 'ansi_dark', False, '', None, None, False, False, True,
                 ipynb_cell_range='1-2')
output = str(c.render_str(r))
assert 'Jupyter Notebook' in output  # cell 1 is markdown
assert 'Introduction' in output  # cell 2 is markdown
assert 'In [' not in output  # no code cells in range 1-2
print('✓ Cell range 1-2 works (only markdown cells)')

print()
print('All smoke tests passed! ✓')
