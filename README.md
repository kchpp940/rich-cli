# Rich-CLI

Rich-CLI is a command line toolbox for fancy output in the terminal, built with [Rich](https://github.com/Textualize/rich).

Use the `rich` command to highlight a variety of file types in the terminal, with specialized rendering for Markdown and JSON files. Additionally you can markup and format text from the command line.

![splash image](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/rich-cli-splash.jpg)

## Installation

There are a few options for installing Rich-CLI.

### Windows / Linux

You can install Rich-CLI with [pipx](https://pypa.github.io/pipx/).

```
pipx install rich-cli
```

### MacOS

You can install Rich-CLI with [Homebrew](https://brew.sh/).

```
brew install rich
```

### Universal

Rich-CLI may be installed as a Python package, either using `pip`:

```
python -m pip install rich-cli
```

Or using `conda` or `mamba`:

```
mamba install -c conda-forge rich-cli
```

## Rich command

Once installed you should have the `rich` command in your path. Run the following to see usage / help:

```
rich --help
```

## Syntax highlighting

To syntax highlight a file enter `rich` followed by a path. Many file formats are supported.

```
rich loop.py
```

![syntax1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/syntax1.png)

Add the `--line-number` or `-n` switch to enable line numbers. Add `--guides` or `-g` to enable indentation guides.

```
rich loop.py -n -g
```

![syntax2](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/syntax2.png)

You can specify a [theme](https://pygments.org/styles/) with `--theme`.

```
rich loop.py --theme dracula
```

You can set the default theme via the `RICH_THEME` environment variable. So the following is equivalent to the above command:

```
RICH_THEME=dracula rich loop.py
```

![syntax3](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/syntax3.png)

By default, `rich` will wrap lines if they don't fit within the available width. You can disable this behavior with `--no-wrap`.

`Rich` will try to deduce the format of the via from the filename. If you want to override the auto-detected _lexer_ you can explicitly set it with the `--lexer` or `-x` switch.

## Markdown

You can request markdown rendering by adding the `--markdown` switch or `-m`. If the file ends with `.md` markdown will be auto-detected.

```
rich README.md
```

![markdown1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/markdown1.png)

If your terminal supports hyperlinks, you can add `--hyperlinks` or `-y` which will output hyperlinks rather than full URLs.

```
rich README.md --hyperlinks
```

## Jupyter notebook

You can request Jupyter notebook rendering by adding the `--ipynb` switch. If the file ends with `.ipynb` Jupyter notebook will be auto-detected.

```
rich notebook.ipynb
```

All options that apply to syntax highlighting can be applied to code cells, and all options that apply to Markdown can be
applied to Markdown cells.

## JSON

You can request JSON pretty formatting and highlighting with the `--json` or `-J` switches. If the file ends with `.json` then JSON will be auto-detected.

```
rich cats.json
```

![json1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/json1.png)

## CSV

Rich can display the contents of a CSV (or TSV) as a table. If the file ends with `.csv` or `.tsv` then CSV will be auto-detected.

```
rich deniro.csv
```

![csv1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/csv1.png)

### Rules

You can render a horizontal rule with `--rule` or `-u`. Specify a rule style with `--rule-style`. Set the character(s) to render the line with `--rule-char`.

```
rich "Hello [b]World[/b]!" --rule
rich "Hello [b]World[/b]!" --rule --rule-style "red"
rich "Hello [b]World[/b]!" --rule --rule-style "red" --rule-char "="
```

![syntax1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/rules1.png)

## Pager

Add `--pager` to display the content with a built in pager application.

Scroll the pager with cursor keys, page up/down, home, end. Alternatively use the scrollbar which will be visible to the right of the terminal. Or use the vi navigation (j, k, ctrl-d, ctrl-u).

```
rich __main__.py -n -g --theme monokai --pager
```

![pager](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/pager1.png)

## Network

The `rich` command can read files from the internet you give it a URL starting with `http://` or `https://`.

```
rich https://raw.githubusercontent.com/Textualize/rich-cli/main/README.md --markdown
```

![network](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/network1.png)

## Exporting

In addition to rendering to the console, `rich` can write an HTML file. This works with any command. Add `--export-html` or `-o` followed by the output path.

```
rich README.md -o readme.html
```

After running this command you should find a "readme.html" in your current working directory.

## Rich Printing

If you add the `--print` or `--p` option then Rich will treat the first argument as [console markup](https://rich.readthedocs.io/en/latest/markup.html) which allows you to insert styles with a markup similar in design to bbcode.

```
rich "Hello, [bold magenta]World[/]!" --print
```

![printing1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/printing1.png)

### Soft wrapping

Rich will word wrap your text by default by inserting newlines where appropriate. If you don't want this behavior you can enable _soft_ wrapping with `--soft`.

## Reading from Stdin

Where `rich` accepts a path, you can enter `-` which reads the content from stdin. You may want this if you are piping output from another process.

Note that when rich isn't writing directly to the terminal it will disable ansi color codes, so you may want to add `--force-terminal` or `-F` to tell `rich` you want to keep ansi codes in the output.

```
cat README.md | rich - --markdown --force-terminal
```

<!-- BEGIN OPTIONS -->

## 命令行选项参考

Rich CLI 的命令行选项按以下类别组织，方便快速查找：

### 输入来源

控制输入数据的来源和解析方式。

| 选项 | 短选项 | 说明 |
|------|--------|------|
| `<PATH or TEXT or '-'>` | - | 输入文件路径、文本、URL 或 '-'（从标准输入读取） |
| `--lexer` `LEXER` | `-x` | 指定语法高亮的词法分析器。参见 [Pygments lexers](https://pygments.org/docs/lexers/) |
| `--force-terminal` | - | 即使输出不是终端，也强制使用终端格式输出 |

### 渲染格式

指定内容的渲染格式。

| 选项 | 短选项 | 说明 |
|------|--------|------|
| `--print` | `-p` | 解析并渲染 [控制台标记](https://rich.readthedocs.io/en/latest/markup.html) |
| `--syntax` | - | 启用语法高亮 |
| `--json` | `-J` | 以 JSON 格式显示 |
| `--markdown` | `-m` | 以 Markdown 格式显示 |
| `--rst` | - | 以 reStructuredText 格式显示 |
| `--rule` | `-u` | 显示水平分隔线 |
| `--inspect` | - | 检查 Python 对象 |

### 显示样式

控制输出的外观和布局。

| 选项 | 短选项 | 说明 |
|------|--------|------|
| `--emoji` | `-j` | 启用表情符号代码，例如 `:sparkle:` |
| `--left` | `-l` | 整体内容左对齐 |
| `--right` | `-r` | 整体内容右对齐 |
| `--center` | `-c` | 整体内容居中 |
| `--text-left` | `-L` | 文本内容左对齐 |
| `--text-right` | `-R` | 文本内容右对齐 |
| `--text-center` | `-C` | 文本内容居中 |
| `--text-full` | `-F` | 文本内容两端对齐 |
| `--soft` | - | 启用软换行（需要 `--print`） |
| `--expand` | `-e` | 展开到全宽（需要 `--panel`） |
| `--width` `SIZE` | `-w` | 设置输出宽度为 SIZE 字符 |
| `--max-width` `SIZE` | `-W` | 设置最大宽度为 SIZE 字符 |
| `--style` `STYLE` | `-s` | 设置文本样式，参见 [Rich 样式语法](https://rich.readthedocs.io/en/latest/style.html) |
| `--rule-style` `STYLE` | - | 设置分隔线样式 |
| `--rule-char` `CHARACTER` | - | 设置分隔线使用的字符 |
| `--padding` `TOP,RIGHT,BOTTOM,LEFT` | `-d` | 设置输出内边距，1、2 或 4 个逗号分隔的整数，例如 `2,4` |
| `--panel` `BOX` | `-a` | 设置面板边框样式：`ascii`, `ascii2`, `double`, `heavy`, `none`, `rounded`, `square` |
| `--panel-style` `STYLE` | `-S` | 设置面板样式（需要 `--panel`） |
| `--title` `TEXT` | - | 设置面板标题 |
| `--caption` `TEXT` | - | 设置面板说明文字 |
| `--theme` `THEME` | - | 设置语法高亮主题，参见 [Pygments 主题](https://pygments.org/styles/)。也可通过环境变量 `RICH_THEME` 设置 |
| `--line-numbers` | `-n` | 显示行号 |
| `--guides` | `-g` | 显示缩进参考线 |
| `--hyperlinks` | `-y` | 在 Markdown 中渲染超链接 |
| `--no-wrap` | - | 禁用语法高亮文件的自动换行 |

### Notebook

Jupyter notebook 相关选项。

| 选项 | 短选项 | 说明 |
|------|--------|------|
| `--ipynb` | - | 以 Jupyter notebook 格式显示。如果文件以 `.ipynb` 结尾会自动检测。支持所有语法高亮和 Markdown 相关选项 |

### CSV

CSV/TSV 表格相关选项。

| 选项 | 短选项 | 说明 |
|------|--------|------|
| `--csv` | - | 以表格形式显示 CSV。如果文件以 `.csv` 或 `.tsv` 结尾会自动检测 |
| `--head` `LINES` | `-h` | 只显示前 LINES 行（需要 `--syntax` 或 `--csv`） |
| `--tail` `LINES` | `-t` | 只显示后 LINES 行（需要 `--syntax` 或 `--csv`） |

### 导出

导出输出内容到文件。

| 选项 | 短选项 | 说明 |
|------|--------|------|
| `--export-html` `PATH` | `-o` | 将输出导出为 HTML 文件 |
| `--export-svg` `PATH` | - | 将输出导出为 SVG 文件 |

### Pager

分页显示相关选项。

| 选项 | 短选项 | 说明 |
|------|--------|------|
| `--pager` | - | 在交互式分页器中显示内容。支持光标键、PageUp/PageDown、Home/End 以及 vi 风格的 j/k/ctrl-d/ctrl-u 导航 |

### 其他

其他杂项选项。

| 选项 | 短选项 | 说明 |
|------|--------|------|
| `--version` | `-v` | 显示版本信息并退出 |


<!-- END OPTIONS -->

## 通用选项使用示例

以下是一些常用选项的使用示例：

### Style

You can set a style to apply to the output with `--style` or `-s`. The styles are specified with [this syntax](https://rich.readthedocs.io/en/latest/style.html).

```
rich "Hello, [b]World[/b]!" --print --style "on blue"
```

![style1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/style1.png)

### Alignment

You can align output to the left, center, or right with the `--left`, `--center`, or `--right` options, or their single letter counterparts: `-l`, `-c`, or `-r`.

```
rich "Hello [b]World[/b]!" --print --center
```

![alignment1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/alignment1.png)

### Width

You can set the width of the output with `--width` or `-w` and the desired width. Note that the default behavior is to wrap text.

```
rich "I must not fear. Fear is the mind-killer. Fear is the little-death that brings total obliteration." -p -w 40
```

![width](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/width1.png)

### Text Justify

You can set how `rich` will justify text with `--text-left`, `--text-right`, `--text-center`, and `--text-full`; or the single letter equivalents: `-L`, `-R`, `-C`, and `-F`.

The difference between `--left` and `--text-left` may not be obvious unless you specify the width of the output. The `--left`, `--center`, and `--right` options will center the block of text within the terminal dimensions. Whereas, the `--text-left`, `--text-center`, and `--text-right` options define how text is rendered _within_ that block.

In the following examples, we specify a width of 40 (`-w 40`) which is center aligned with the `-c` switch. Note how the `-R`, `-C` and `-F` apply the text justification within the 40 character block:

```
rich "I must not fear. Fear is the mind-killer. Fear is the little-death that brings total obliteration." -p -w 40 -c -L
rich "I must not fear. Fear is the mind-killer. Fear is the little-death that brings total obliteration." -p -w 40 -c -R
rich "I must not fear. Fear is the mind-killer. Fear is the little-death that brings total obliteration." -p -w 40 -c -C
rich "I must not fear. Fear is the mind-killer. Fear is the little-death that brings total obliteration." -p -w 40 -c -F
```

### Padding

You can apply _padding_ around the output with `--padding` or `-d`.

```
rich "Hello [b]World[/b]!" -p -c --padding 3 --style "on blue"
```

![padding1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/padding1.png)

### Panel

You can draw a _panel_ around content with `--panel` or `-a`, which takes one of a number of [styles](https://rich.readthedocs.io/en/latest/appendix/box.html).

```
rich "Hello, [b]World[/b]!" -p -a heavy
```

![panel1](https://raw.githubusercontent.com/Textualize/rich-cli/main/imgs/panel1.png)
