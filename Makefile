# HAFiscal Development Makefile
# Works with any Python package manager

TEX_FILES := HAFiscal.tex HAFiscal-Slides.tex HAFiscal-online-appendix.tex

.PHONY: help setup sync test clean pdf-short pdf-medium pdf-complete pdf-full pdf-all versions status clean-pdf
.PHONY: cursor-indexing-ignore pdf-candidate promote-tables test-locked

help:
	@echo "HAFiscal Development Commands"
	@echo "=============================="
	@echo "Python Environment:"
	@echo "  setup      - Set up development environment"
	@echo "  sync       - Sync all dependency files from pyproject.toml"
	@echo "  test       - Run tests"
	@echo "  clean      - Clean up generated files"
	@echo ""
	@echo "Cursor AI:"
	@echo "  cursor-indexing-ignore - Generate .cursorindexingignore from .gitignore (SST)"
	@echo ""
	@echo "LaTeX Document Versions:"
	@echo "  pdf-short    - Compile short version (for build debugging)"
	@echo "  pdf-medium   - Compile medium version"
	@echo "  pdf-complete - Compile complete version"
	@echo "  pdf-full     - Compile full version"
	@echo "  pdf-all    - Compile all versions"
	@echo "  versions   - List available versions"
	@echo "  status     - Show current version status"
	@echo "  clean-pdf  - Clean LaTeX build files"
	@echo ""
	@echo "QE-Baseline Freeze (frozen results + candidates):"
	@echo "  pdf-candidate  - Build HAFiscal.pdf reading _candidate tables/figures"
	@echo "  promote-tables - Review + promote _candidate files to frozen status"
	@echo "  test-locked    - Verify frozen files match LOCKED_TABLES.manifest"

setup:
	@bash reproduce/reproduce_environment_comp_uv.sh

sync:
	@UV_PE=$$(bash reproduce/uv_platform_venv_path.sh); \
	echo "Syncing dependency files from pyproject.toml (UV_PROJECT_ENVIRONMENT=$$UV_PE)..."; \
	env -u VIRTUAL_ENV UV_PROJECT_ENVIRONMENT="$$UV_PE" uv sync --all-groups; \
	if [ -d .venv ] && [ ! -L .venv ]; then echo "Replacing stray .venv directory with symlink -> $$UV_PE"; rm -rf .venv; fi; \
	ln -sfn "$$UV_PE" .venv; \
	echo "✓ All dependency files synchronized (.venv -> $$UV_PE)"

# NOTE (B9, doc-only): this recipe points at a nonexistent `tests/` directory,
# so `make test` currently fails. The real test invocation is
# `pytest Code/ reproduce/` (per CLAUDE.md). Fixing the recipe is a QUEUED logic
# change (not done here); see Code/HA-Models/docs/COMMENT_AUDIT_FINDINGS.md row (j).
test:
	pytest Code/ reproduce/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache

cursor-indexing-ignore:
	@echo "Generating .cursorindexingignore from .gitignore (SST)..."
	@bash @resources/scripts/generate-cursorindexingignore.sh

# LaTeX Version Management Targets
# =================================

# Individual version targets
pdf-short: HAFiscal-short.pdf
pdf-medium: HAFiscal-medium.pdf  
pdf-complete: HAFiscal-complete.pdf
pdf-full: HAFiscal-full.pdf

HAFiscal-short.pdf: HAFiscal.tex
	@echo "Building short version..."
	@echo "⚠️  Version management script not available - target disabled"
	@echo "   (scripts/manage-versions.sh is missing)"

HAFiscal-medium.pdf: HAFiscal.tex
	@echo "Building medium version..."
	@echo "⚠️  Version management script not available - target disabled"
	@echo "   (scripts/manage-versions.sh is missing)"

HAFiscal-complete.pdf: HAFiscal.tex
	@echo "Building complete version..."
	@echo "⚠️  Version management script not available - target disabled"
	@echo "   (scripts/manage-versions.sh is missing)"

HAFiscal-full.pdf: HAFiscal.tex
	@echo "Building full version..."
	@echo "⚠️  Version management script not available - target disabled"
	@echo "   (scripts/manage-versions.sh is missing)"

# Build all versions
pdf-all: pdf-short pdf-medium pdf-complete pdf-full
	@echo "✓ All versions compiled successfully"

# Version management commands (disabled - scripts/manage-versions.sh not available)
versions:
	@echo "⚠️  Version management not available"
	@echo "   (scripts/manage-versions.sh is missing)"

status:
	@echo "⚠️  Version status check not available"
	@echo "   (scripts/manage-versions.sh is missing)"

# Clean LaTeX build files
clean-pdf:
	@echo "Cleaning LaTeX build files..."
	@rm -f *.aux *.bbl *.blg *.fdb_latexmk *.fls *.log *.out *.toc *.synctex.gz
	@rm -f HAFiscal-*.pdf
	@echo "✓ LaTeX build files cleaned"

# QE-Baseline Freeze targets
# ===========================
# (plans/20260611_qe-baseline-freeze-and-candidate-lock_plan.md)

# Build the paper reading `_candidate` siblings of frozen tables/figures
# (falls back to frozen for any table without a candidate). The flag file is
# gitignored and removed after the build, so the default build stays frozen.
pdf-candidate:
	@echo "Building HAFiscal.pdf from _candidate tables/figures..."
	@printf '%s\n' '\usecandidatetablestrue' > @local/use-candidate-tables.ltx
	@latexmk HAFiscal.tex || { rm -f @local/use-candidate-tables.ltx; exit 1; }
	@rm -f @local/use-candidate-tables.ltx
	@echo "✓ Candidate-preview build complete (flag file removed; default build stays frozen)"

# The one deliberate path that changes frozen result numbers.
promote-tables:
	@python3 reproduce/promote_candidates.py

test-locked:
	@pytest Code/HA-Models/test_locked_tables.py -q

# Legacy compatibility (these will be generated by the template above)
# pdf-short and pdf-long are automatically created by the VERSION_TEMPLATE

# Convenience targets for common workflows
debug: pdf-short
	@echo "✓ Debug build (short version) completed"

test-build: pdf-short
	@echo "✓ Build infrastructure test completed"

journal: pdf-complete
	@echo "✓ Journal submission version completed"

working-paper: pdf-medium
	@echo "✓ Working paper version completed" 