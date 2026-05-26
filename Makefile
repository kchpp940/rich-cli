.PHONY: help format format-check typecheck typecheck-strict build smoke clean fix check verify deps-check deps-sync

RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
NC = \033[0m

TMPDIR = $(shell mktemp -d)

help:
	@echo "Rich-CLI 开发入口脚本"
	@echo ""
	@echo "主要入口:"
	@echo "  make check   - 日常检查（格式检查 + 依赖一致性 + 构建 + 冒烟）"
	@echo "  make verify  - 完整验证（格式检查 + 类型检查 + 依赖一致性 + 构建 + 冒烟）"
	@echo "  make fix     - 自动修复（格式化代码）"
	@echo ""
	@echo "细分命令:"
	@echo "  make format          - 格式化代码 (black)，会修改文件"
	@echo "  make format-check    - 格式检查 (black --check)，不改文件"
	@echo "  make typecheck       - 类型检查 (mypy)"
	@echo "  make typecheck-strict- 严格类型检查 (同 typecheck，预留扩展)"
	@echo "  make build           - 打包构建"
	@echo "  make smoke           - 冒烟测试"
	@echo "  make deps-check      - 可选依赖一致性检查"
	@echo "  make deps-sync       - 同步可选依赖到 README"
	@echo "  make clean           - 清理临时产物"
	@echo ""

format:
	@printf "\n$(YELLOW)========== 格式化代码 ==========$(NC)\n"
	@poetry run black src/ tests/ || (printf "$(RED)✗ 错误发生在: 格式化代码$(NC)\n" && exit 1)
	@printf "$(GREEN)✓ 格式化代码 完成$(NC)\n"

format-check:
	@printf "\n$(YELLOW)========== 格式检查 ==========$(NC)\n"
	@poetry run black --check src/ tests/ || (printf "$(RED)✗ 错误发生在: 格式检查 - 请运行 'make fix' 自动修复$(NC)\n" && exit 1)
	@printf "$(GREEN)✓ 格式检查 完成$(NC)\n"

typecheck:
	@printf "\n$(YELLOW)========== 类型检查 ==========$(NC)\n"
	@printf "$(YELLOW)注意: 当前会暴露项目遗留的类型问题$(NC)\n"
	@poetry run mypy src/ || (printf "$(RED)✗ 错误发生在: 类型检查$(NC)\n" && exit 1)
	@printf "$(GREEN)✓ 类型检查 完成$(NC)\n"

typecheck-strict: typecheck

build:
	@printf "\n$(YELLOW)========== 打包构建 ==========$(NC)\n"
	@poetry build || (printf "$(RED)✗ 错误发生在: 打包构建$(NC)\n" && exit 1)
	@printf "$(GREEN)✓ 打包构建 完成$(NC)\n"

smoke:
	@printf "\n$(YELLOW)========== 冒烟测试 ==========$(NC)\n"
	@echo "测试 1: rich --help"
	@poetry run rich --help > /dev/null || (printf "$(RED)✗ 错误发生在: 冒烟测试 - rich --help$(NC)\n" && exit 1)
	@echo "测试 2: 渲染 Markdown 文件"
	@poetry run rich README.md > /dev/null || (printf "$(RED)✗ 错误发生在: 冒烟测试 - 渲染 Markdown$(NC)\n" && exit 1)
	@echo "测试 3: 渲染 CSV 文件"
	@poetry run rich test_data/deniro.csv > /dev/null || (printf "$(RED)✗ 错误发生在: 冒烟测试 - 渲染 CSV$(NC)\n" && exit 1)
	@echo "测试 4: 带 --print 选项的文本渲染"
	@poetry run rich "Hello [b]World[/b]!" --print > /dev/null || (printf "$(RED)✗ 错误发生在: 冒烟测试 - 文本渲染$(NC)\n" && exit 1)
	@echo "测试 5: 语法高亮 (带行号)"
	@poetry run rich src/rich_cli/__main__.py -n > /dev/null || (printf "$(RED)✗ 错误发生在: 冒烟测试 - 语法高亮$(NC)\n" && exit 1)
	@echo "测试 6: 导出 HTML 到临时目录"
	@poetry run rich README.md --export-html $(TMPDIR)/test_export.html > /dev/null || (printf "$(RED)✗ 错误发生在: 冒烟测试 - 导出 HTML$(NC)\n" && rm -rf $(TMPDIR) && exit 1)
	@rm -rf $(TMPDIR)
	@printf "$(GREEN)✓ 冒烟测试 完成$(NC)\n"

deps-check:
	@printf "\n$(YELLOW)========== 可选依赖一致性检查 ==========$(NC)\n"
	@python3 scripts/check_deps_consistency.py || (printf "$(RED)✗ 错误发生在: 可选依赖一致性检查$(NC)\n" && exit 1)
	@printf "$(GREEN)✓ 可选依赖一致性检查 完成$(NC)\n"

deps-sync:
	@printf "\n$(YELLOW)========== 同步可选依赖到 README ==========$(NC)\n"
	@python3 scripts/generate_readme_table.py || (printf "$(RED)✗ 错误发生在: 同步可选依赖到 README$(NC)\n" && exit 1)
	@printf "$(GREEN)✓ 同步可选依赖到 README 完成$(NC)\n"

clean:
	@printf "\n$(YELLOW)========== 清理临时产物 ==========$(NC)\n"
	@rm -rf dist/
	@rm -rf build/
	@rm -rf *.egg-info
	@rm -rf src/*.egg-info
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .mypy_cache/
	@printf "$(GREEN)✓ 清理临时产物 完成$(NC)\n"

fix: format
	@echo ""
	@echo "$(GREEN)========================================$(NC)"
	@echo "$(GREEN)✓ 自动修复完成$(NC)"
	@echo "$(GREEN)========================================$(NC)"

check: format-check deps-check build smoke
	@rm -rf dist/ build/ *.egg-info src/*.egg-info
	@echo ""
	@echo "$(GREEN)========================================$(NC)"
	@echo "$(GREEN)✓ 所有日常检查通过！$(NC)"
	@echo "$(GREEN)========================================$(NC)"

verify: format-check typecheck deps-check build smoke
	@rm -rf dist/ build/ *.egg-info src/*.egg-info
	@echo ""
	@echo "$(GREEN)========================================$(NC)"
	@echo "$(GREEN)✓ 所有验证通过！$(NC)"
	@echo "$(GREEN)========================================$(NC)"
