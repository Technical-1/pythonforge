"""
pyhatch.templates - Jinja2 Template Files
=========================================

This package contains Jinja2 template files used to generate project files.
Templates use the .j2 extension and are rendered by the generator module.

Template Naming Convention
--------------------------
- Templates end with `.j2` extension
- Output filename = template name without `.j2`
- Exception: `gitignore.j2` → `.gitignore` (special handling)

Available Templates
-------------------
Core:
    - pyproject.toml.j2: Project configuration
    - README.md.j2: Project readme
    - gitignore.j2: Git ignore patterns

Source Files:
    - package_init.py.j2: Package __init__.py
    - cli.py.j2: CLI entry point (for CLI projects)
    - main.py.j2: Main module (for app/api projects)

Tests:
    - test_main.py.j2: Test file template

Configuration:
    - pre-commit-config.yaml.j2: Pre-commit hooks
    - github_ci.yml.j2: GitHub Actions workflow
    - vscode_settings.json.j2: VS Code settings
    - vscode_extensions.json.j2: VS Code extension recommendations

Licenses:
    - LICENSE_MIT.j2: MIT license text

Template Context
----------------
All templates receive a context dictionary containing:

    config : ProjectConfig
        Full project configuration object

    pyhatch_version : str
        Version of pyhatch for attribution

    year : int
        Current year (for licenses)

Usage
-----
Templates are loaded via Jinja2's PackageLoader:

>>> from jinja2 import Environment, PackageLoader
>>> env = Environment(loader=PackageLoader("pyhatch", "templates"))
>>> template = env.get_template("pyproject.toml.j2")
>>> output = template.render(config=config, pyhatch_version="0.1.0", year=2025)

See Also
--------
- generator.py: Module that renders these templates
- models.py: ProjectConfig model passed to templates
"""

# This file intentionally left mostly empty.
# Templates are loaded dynamically by Jinja2's PackageLoader.
