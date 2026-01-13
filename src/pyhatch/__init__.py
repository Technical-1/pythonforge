"""
pyhatch - Modern Python Project Bootstrapper
============================================

A CLI tool that creates production-ready Python projects with 2025's best
toolchain including uv, ruff, basedpyright, pytest, and pre-commit.

Features
--------
- **Zero Configuration**: Sensible defaults that just work
- **Modern Tooling**: uv for packages, ruff for linting, basedpyright for types
- **Project Types**: Library, CLI app, API service, or simple script
- **CI/CD Ready**: GitHub Actions workflows included
- **Editor Support**: VS Code settings pre-configured

Quick Start
-----------
```bash
# Install pyhatch
pip install pyhatch

# Create a new project interactively
pyhatch new myproject

# Or with options
pyhatch new myproject --type cli --python 3.12
```

Example
-------
>>> from pyhatch import create_project
>>> create_project("myproject", project_type="library")
Project 'myproject' created successfully!

Architecture
------------
The package is organized into these main modules:

- ``cli``: Typer-based command line interface
- ``generator``: Core project generation logic
- ``templates``: Jinja2 templates for generated files
- ``presets``: Configuration presets for different project types
- ``validators``: Post-creation validation checks
- ``auditor``: Analyze existing projects for improvements
- ``upgrader``: Migrate legacy projects to modern tooling
- ``models``: Pydantic models for configuration

License
-------
MIT License - see LICENSE file for details.
"""

# =============================================================================
# Package Metadata
# =============================================================================
__version__ = "0.1.0"
__author__ = "Technical-1"
__email__ = "jacobkanfer8@gmail.com"
__license__ = "MIT"

# =============================================================================
# Public API Exports
# =============================================================================
# These are the main functions/classes users should interact with when using
# pyhatch as a library (as opposed to the CLI)

from pyhatch.auditor import audit_project
from pyhatch.generator import create_project
from pyhatch.models import ProjectConfig, ProjectType
from pyhatch.upgrader import upgrade_project


__all__ = [
    # Configuration models
    "ProjectConfig",
    "ProjectType",
    "__author__",
    # Version info
    "__version__",
    "audit_project",
    # Core functions
    "create_project",
    "upgrade_project",
]
