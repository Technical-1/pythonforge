# pyhatch

> Modern Python project bootstrapper with 2025's best toolchain

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**pyhatch** creates production-ready Python projects with zero configuration. One command gives you a complete project with modern tooling:

- ⚡ **[uv](https://docs.astral.sh/uv/)** - Blazing fast package manager (10-100x faster than pip)
- 🧹 **[ruff](https://docs.astral.sh/ruff/)** - Linting and formatting (replaces black, isort, flake8)
- 🔍 **[basedpyright](https://docs.basedpyright.com/)** - Strict type checking
- ✅ **[pytest](https://docs.pytest.org/)** - Testing with coverage
- 🔧 **[pre-commit](https://pre-commit.com/)** - Automated code quality checks

## Installation

```bash
# Using uv (recommended)
uv tool install pyhatch

# Using pip
pip install pyhatch

# Using pipx
pipx install pyhatch
```

## Quick Start

```bash
# Create a new project interactively
pyhatch new myproject

# Create with options (non-interactive)
pyhatch new myproject --type cli --python 3.12 --yes
```

That's it! Your project is ready with:
- ✅ Proper package structure (src layout)
- ✅ pyproject.toml with all tools configured
- ✅ Pre-commit hooks
- ✅ GitHub Actions CI/CD
- ✅ VS Code settings
- ✅ Type checking enabled
- ✅ Test skeleton with pytest

## Project Types

pyhatch supports different project types optimized for their use case:

| Type | Description | Entry Point |
|------|-------------|-------------|
| `library` | PyPI-publishable package | `from package import ...` |
| `cli` | Command-line tool | `$ mycommand --help` |
| `api` | FastAPI web service | `uvicorn app:main` |
| `app` | Standalone application | `python -m package` |
| `script` | Single-file with inline deps | `uv run script.py` |

## Generated Structure

```
myproject/
├── src/
│   └── myproject/
│       ├── __init__.py
│       ├── py.typed           # PEP 561 marker
│       └── main.py            # or cli.py for CLI projects
├── tests/
│   ├── __init__.py
│   └── test_main.py
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions workflow
├── .vscode/
│   ├── settings.json          # Editor settings
│   └── extensions.json        # Recommended extensions
├── pyproject.toml             # All configuration
├── .pre-commit-config.yaml    # Pre-commit hooks
├── .gitignore
├── README.md
└── LICENSE
```

## Usage

### Interactive Mode (Default)

```bash
pyhatch new myproject
```

Prompts for:
- Project type
- Python version
- License
- Author info
- Optional features

### Non-Interactive Mode

```bash
# Quick library with defaults
pyhatch new mylib --type library --yes

# CLI with strict type checking
pyhatch new mycli --type cli --strict

# API project
pyhatch new myapi --type api --yes

# Specify all options
pyhatch new myproject \
    --type library \
    --python 3.12 \
    --license MIT \
    --author "Jane Doe" \
    --email "jane@example.com"
```

### Command Reference

```bash
# Show help
pyhatch --help
pyhatch new --help

# Show version
pyhatch --version
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--type` | `-t` | Project type: library, app, cli, api, script |
| `--python` | `-p` | Python version: 3.11, 3.12, 3.13 |
| `--license` | `-l` | License: MIT, Apache-2.0, GPL-3.0-only, BSD-3-Clause |
| `--author` | `-a` | Author name |
| `--email` | `-e` | Author email |
| `--output` | `-o` | Output directory (default: current) |
| `--strict` | | Enable strict type checking |
| `--yes` | `-y` | Skip prompts, use defaults |
| `--no-git` | | Skip git initialization |
| `--no-github-actions` | | Skip GitHub Actions |
| `--no-pre-commit` | | Skip pre-commit config |
| `--no-vscode` | | Skip VS Code settings |

> **Tip:** Use `pyhatch add docker` or `pyhatch add docs` after project creation to add Docker or documentation support.

## After Creating a Project

```bash
cd myproject

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run linter
uv run ruff check .

# Run formatter
uv run ruff format .

# Run type checker
uv run basedpyright

# Install pre-commit hooks
uv run pre-commit install
```

## Why These Tools?

### uv over pip/poetry/pipenv

- **10-100x faster** than pip for installs
- Written in Rust for maximum performance
- Built-in virtual environment management
- Lockfile support for reproducible builds
- Drop-in replacement for pip commands

### ruff over black/isort/flake8

- **10-100x faster** than traditional Python linters
- Single tool replaces black, isort, flake8, and more
- 800+ lint rules from popular linters
- Automatic fixes for most issues
- Configuration in pyproject.toml

### basedpyright over mypy

- **Faster** type checking
- Better error messages
- Stricter defaults catch more bugs
- Better VSCode/Pylance integration
- Drop-in replacement for pyright

## Configuration

All configuration lives in `pyproject.toml`. No more scattered config files!

```toml
# Ruff configuration
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "SIM", "RUF"]

# Type checking
[tool.basedpyright]
typeCheckingMode = "standard"
pythonVersion = "3.12"

# Testing
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["-v", "--cov"]
```

## Additional Commands

### `pyhatch audit`

Analyze existing projects for modernization opportunities:

```bash
pyhatch audit ./my-project

# Output shows:
# - Detected tooling (package manager, linter, formatter, type checker)
# - Project health score (0-100)
# - Recommendations for modernization
```

### `pyhatch upgrade`

Migrate from legacy tooling to modern 2025 stack:

```bash
# Auto-detect source tool
pyhatch upgrade .

# Specify source tool
pyhatch upgrade . --from poetry

# Preview changes without applying
pyhatch upgrade . --dry-run
```

Supported migrations:
- Poetry → uv
- pip/requirements.txt → uv
- black → ruff format
- isort → ruff
- flake8 → ruff lint
- mypy → basedpyright

### `pyhatch add`

Add features to existing projects:

```bash
pyhatch add github-actions   # CI/CD workflow
pyhatch add docker           # Dockerfile + docker-compose.yml
pyhatch add docs             # MkDocs with Material theme
pyhatch add pre-commit       # Pre-commit hooks
pyhatch add vscode           # VS Code settings
pyhatch add devcontainer     # Dev container config
```

## Development

### Setup

```bash
git clone https://github.com/Technical-1/pyhatch.git
cd pyhatch
uv sync --dev
uv run pre-commit install
```

### Running Tests

```bash
uv run pytest
```

### Running Linters

```bash
uv run ruff check .
uv run ruff format .
uv run basedpyright
```

## Philosophy

1. **Convention over configuration** - Sensible defaults that work for 90% of projects
2. **Modern by default** - Use 2025's best tools, not legacy compatibility
3. **Type-safe** - Full type annotations from day one
4. **Fast** - Rust-based tools for instant feedback
5. **Single source of truth** - All config in pyproject.toml

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

---

Made with ❤️ by developers who were tired of project setup boilerplate.
