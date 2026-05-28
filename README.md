# ⚡ quickforge

<div align="center">

[![PyPI](https://img.shields.io/pypi/v/quickforge?style=for-the-badge&color=blue&cacheSeconds=0)](https://pypi.org/project/quickforge/)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
[![License](https://img.shields.io/github/license/Technical-1/quickforge?style=for-the-badge)](LICENSE)

**Modern Python project bootstrapper with 2025's best toolchain.**

Zero Config • Modern Tools • One Command

[Installation](#-installation) • [Quick Start](#-quick-start) • [Project Types](#-project-types) • [Commands](#-commands)

</div>

---

## ✨ What quickforge Does

One command creates a complete Python project with modern tooling:

```bash
quickforge new myproject
```

That's it! Your project is ready with all the best practices built in.

### ⚡ **Modern Toolchain**
- **[uv](https://docs.astral.sh/uv/)** - Blazing fast package manager (10-100x faster than pip)
- **[ruff](https://docs.astral.sh/ruff/)** - Linting & formatting (replaces black, isort, flake8)
- **[basedpyright](https://docs.basedpyright.com/)** - Strict type checking
- **[pytest](https://docs.pytest.org/)** - Testing with coverage
- **[pre-commit](https://pre-commit.com/)** - Automated code quality

### 📦 **Everything Configured**
- ✅ Proper package structure (src layout)
- ✅ `pyproject.toml` with all tools configured
- ✅ Pre-commit hooks ready to go
- ✅ GitHub Actions CI/CD
- ✅ VS Code settings optimized
- ✅ Type checking enabled from day one
- ✅ Test skeleton with pytest + coverage
- ✅ Full-text `LICENSE` file for any of six licenses (MIT, Apache-2.0, GPL-3.0, BSD-3-Clause, Unlicense, Proprietary)

### 🔄 **Migration Tools**
- Upgrade legacy projects to modern tooling
- Migrate from Poetry, pip, pipenv, or setuptools
- Convert black/isort/flake8/mypy to ruff/basedpyright

---

## 📦 Installation

```bash
# Using uv (recommended)
uv tool install quickforge
```

```bash
# Using pip
pip install quickforge
```

```bash
# Using pipx
pipx install quickforge
```

---

## 🚀 Quick Start

### Interactive Mode (Default)

```bash
quickforge new myproject
```

Prompts you for project type, Python version, license, author info, and features.

### Non-Interactive Mode

```bash
# Quick library with defaults
quickforge new mylib --type library --yes

# CLI with strict type checking
quickforge new mycli --type cli --strict

# FastAPI project
quickforge new myapi --type api --yes

# Specify everything
quickforge new myproject \
    --type library \
    --python 3.12 \
    --license MIT \
    --author "Jane Doe" \
    --email "jane@example.com"
```

### After Creating a Project

```bash
cd myproject
uv sync                    # Install dependencies
uv run pytest              # Run tests
uv run ruff check .        # Lint code
uv run ruff format .       # Format code
uv run basedpyright        # Type check
uv run pre-commit install  # Setup git hooks
```

---

## 📁 Project Types

| Type | Description | Use Case |
|------|-------------|----------|
| **library** | PyPI-publishable package | Reusable code, open source packages |
| **cli** | Command-line tool with Typer | Terminal applications, dev tools |
| **api** | FastAPI web service | REST APIs, microservices |
| **app** | Standalone application | Scripts that need structure |
| **script** | Single-file with inline deps | Quick automation, one-off tasks |

---

## 📂 Generated Structure

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
│       └── ci.yml             # GitHub Actions
├── .vscode/
│   ├── settings.json
│   └── extensions.json
├── pyproject.toml             # All configuration
├── .pre-commit-config.yaml
├── .gitignore
├── README.md
└── LICENSE
```

---

## 🛠️ Commands

### `quickforge new`

Create a new project:

```bash
quickforge new myproject [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--type` | `-t` | Project type: library, app, cli, api, script |
| `--python` | `-p` | Python version: 3.11, 3.12, 3.13 |
| `--license` | `-l` | License: MIT, Apache-2.0, GPL-3.0-only, BSD-3-Clause, Unlicense, Proprietary |
| `--author` | `-a` | Author name |
| `--email` | `-e` | Author email |
| `--output` | `-o` | Output directory |
| `--strict` | | Enable strict type checking |
| `--yes` | `-y` | Skip prompts, use defaults |
| `--no-git` | | Skip git initialization |
| `--no-github-actions` | | Skip GitHub Actions |
| `--no-pre-commit` | | Skip pre-commit config |
| `--no-vscode` | | Skip VS Code settings |
| `--with-docker` | | Include Docker configuration |
| `--with-docs` | | Include MkDocs documentation |

### `quickforge audit`

Analyze existing projects for modernization opportunities:

```bash
quickforge audit ./my-project
```

Shows detected tooling, project health score, and recommendations.

### `quickforge upgrade`

Migrate from legacy tooling to modern stack:

```bash
quickforge upgrade .              # Auto-detect and upgrade
quickforge upgrade . --from poetry  # Specify source tool
quickforge upgrade . --dry-run      # Preview changes
```

| Migration | From | To |
|-----------|------|-----|
| Package Manager | Poetry, pip, pipenv, setuptools | uv |
| Formatter | black | ruff format |
| Import Sorting | isort | ruff (I rules) |
| Linter | flake8 | ruff lint |
| Type Checker | mypy | basedpyright |

### `quickforge add`

Add features to existing projects:

```bash
quickforge add github-actions   # CI/CD workflow
quickforge add docker           # Dockerfile + docker-compose.yml
quickforge add docs             # MkDocs with Material theme
quickforge add pre-commit       # Pre-commit hooks
quickforge add vscode           # VS Code settings
quickforge add devcontainer     # Dev container config
```

---

## ⚡ Why These Tools?

### uv over pip/poetry/pipenv

| Metric | pip | poetry | uv |
|--------|-----|--------|-----|
| Install Speed | 1x | 2x | **10-100x** |
| Written In | Python | Python | Rust |
| Lockfile | ❌ | ✅ | ✅ |
| Workspaces | ❌ | ❌ | ✅ |

### ruff over black/isort/flake8

| Metric | black + isort + flake8 | ruff |
|--------|------------------------|------|
| Speed | 1x | **10-100x** |
| Config Files | 3 | 1 |
| Rules | ~500 | **800+** |
| Auto-fix | Limited | Extensive |

### basedpyright over mypy

| Metric | mypy | basedpyright |
|--------|------|--------------|
| Speed | 1x | **3-5x** |
| Error Messages | Basic | Detailed |
| VSCode Integration | Good | Excellent |
| Strictness | Configurable | Stricter defaults |

---

## 🧪 Development

```bash
# Clone and setup
git clone https://github.com/Technical-1/quickforge.git
cd quickforge
uv sync --extra dev
uv run pre-commit install

# Run tests
uv run pytest

# Run linters
uv run ruff check .
uv run ruff format .
uv run basedpyright
```

---

## 💡 Philosophy

1. **Convention over configuration** - Sensible defaults for 90% of projects
2. **Modern by default** - 2025's best tools, not legacy compatibility
3. **Type-safe** - Full type annotations from day one
4. **Fast** - Rust-based tools for instant feedback
5. **Single source of truth** - All config in pyproject.toml

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**Made by [Jacob Kanfer](https://jacobkanfer.com)**

</div>
