# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**quickforge** is a Python CLI tool that bootstraps production-ready Python projects with modern 2025 tooling (uv, ruff, basedpyright, pytest, pre-commit). It generates complete project structures with a single command.

## Commands

```bash
# Install dependencies
uv sync --all-extras

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
quickforge new testproject --type cli --yes
```

## Architecture

```
src/quickforge/
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
- Context: `config` (ProjectConfig), `quickforge_version`, `year`
- Naming: `foo.j2` → `foo` (special: `gitignore.j2` → `.gitignore`)
- Conditionals: Some templates only render based on project type/features
- License files handled separately via `LICENSE_TEMPLATES` dict

Template mappings are defined in `generator.py:TEMPLATE_MAPPINGS`. Each mapping has a condition function that determines whether to render based on `ProjectConfig`.

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

Coverage requirement: 80% minimum (configured in pyproject.toml)
