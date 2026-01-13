# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**pyhatch** is a Python CLI tool that bootstraps production-ready Python projects with modern 2025 tooling (uv, ruff, basedpyright, pytest, pre-commit). It generates complete project structures with a single command.

## Commands

```bash
# Install dependencies
uv sync --dev

# Run tests (with coverage)
uv run pytest

# Run single test file
uv run pytest tests/test_models.py

# Run single test
uv run pytest tests/test_models.py::test_project_type_description -v

# Run without coverage (faster)
uv run pytest --no-cov

# Linting and formatting
uv run ruff check .
uv run ruff format .
uv run basedpyright

# Install CLI locally for testing
uv pip install -e .
pyhatch new testproject --type cli --yes
```

## Architecture

```
src/pyhatch/
├── cli.py          # Typer CLI app - commands: new, audit, upgrade, add
├── models.py       # Pydantic models - ProjectConfig, enums, validation
├── generator.py    # Core logic - template rendering, file writing, git init, add_feature
├── auditor.py      # Project analysis - detect tooling, generate recommendations
├── upgrader.py     # Migration engine - poetry/pip/black/mypy to modern tools
└── templates/      # Jinja2 templates (*.j2) for generated files
```

### Key Data Flow

1. **CLI** (`cli.py`) parses args/prompts → builds `ProjectConfig`
2. **Generator** (`generator.py`) receives config → renders templates → writes files
3. **Models** (`models.py`) provide validation and computed properties

### Template System

Templates in `templates/` use Jinja2 with:
- Context: `config` (ProjectConfig), `pyhatch_version`, `year`
- Naming: `foo.j2` → `foo` (special: `gitignore.j2` → `.gitignore`)
- Conditionals: Some templates only render based on project type/features

Template mappings are defined in `generator.py:TEMPLATE_MAPPINGS`.

### Project Types

| Type | Layout | Entry Point |
|------|--------|-------------|
| `library` | src layout | Package import |
| `cli` | src layout | CLI entry point (Typer) |
| `api` | src layout | FastAPI/Flask main |
| `app` | flat layout | `__main__.py` |
| `script` | single file | PEP 723 inline deps |

## Testing

Tests use pytest with fixtures in `conftest.py`:
- `temp_project_dir` - temporary directory for project generation tests
- `sample_pyproject` - sample TOML content
- `sample_python_file` - sample Python code

Coverage requirement: 80% minimum (configured in pyproject.toml).

## Implementation Status

- **Phase 1-2 (Complete)**: `new` command fully functional
- **Phase 3 (Complete)**: `audit`, `upgrade`, `add` commands fully implemented

### Phase 3 Commands

**`pyhatch audit`** - Analyze existing Python projects:
- Detects package manager (uv, poetry, pip, pipenv, setuptools)
- Detects linter, formatter, type checker, CI system
- Analyzes type annotation coverage
- Generates recommendations with severity levels
- Calculates project health score (0-100)

**`pyhatch upgrade`** - Migrate to modern tooling:
- Migrates poetry → uv (converts pyproject.toml)
- Migrates pip/requirements.txt → uv
- Migrates black/isort/flake8 → ruff
- Migrates mypy → basedpyright
- Supports `--dry-run` and `--no-backup` flags
- Creates timestamped backups

**`pyhatch add`** - Add features to existing projects:
- `github-actions` - CI/CD workflow
- `docker` - Dockerfile and docker-compose.yml
- `docs` - MkDocs documentation setup
- `pre-commit` - Pre-commit hooks
- `vscode` - VS Code settings and extensions
- `devcontainer` - Dev container configuration
- Supports `--force` to overwrite existing files
