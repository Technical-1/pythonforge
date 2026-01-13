"""
pyhatch.cli - Command Line Interface
====================================

This module provides the command-line interface for pyhatch using Typer.
Typer was chosen for its excellent type hint integration, automatic help
generation, and rich terminal output support.

Architecture
------------
The CLI is structured around Typer's app pattern:

    app (main entry point)
    ├── new      - Create a new project
    ├── audit    - Audit an existing project (Phase 3)
    ├── upgrade  - Upgrade project to modern tooling (Phase 3)
    └── add      - Add features to existing project (Phase 3)

Commands are designed to be both interactive (with prompts) and
scriptable (with flags). The --yes flag skips all prompts for CI usage.

Usage Examples
--------------
Interactive mode (prompts for options):
    $ pyhatch new myproject

Non-interactive mode (all options specified):
    $ pyhatch new myproject --type cli --python 3.12 --yes

Show help:
    $ pyhatch --help
    $ pyhatch new --help

See Also
--------
- generator.py: Core project generation logic
- models.py: Configuration data models
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pyhatch import __version__
from pyhatch.auditor import AuditCategory, Severity, audit_project
from pyhatch.generator import FEATURE_TEMPLATES, add_feature_to_project, create_project
from pyhatch.upgrader import create_migration_plan, upgrade_project
from pyhatch.models import (
    AuthorInfo,
    FeaturesConfig,
    License,
    ProjectConfig,
    ProjectType,
    PythonVersion,
    ToolingConfig,
    TypeCheckingMode,
)


# =============================================================================
# CLI Application Setup
# =============================================================================

# Create the main Typer application
app = typer.Typer(
    name="pyhatch",
    help="Modern Python project bootstrapper with 2025's best toolchain.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    add_completion=True,
)

# Console for rich output
console = Console()


# =============================================================================
# Version Callback
# =============================================================================

def version_callback(value: bool) -> None:
    """
    Display version information and exit.

    Shows the pyhatch version along with information about the
    toolchain versions it uses.

    Parameters
    ----------
    value : bool
        True if --version was passed.
    """
    if value:
        console.print(Panel(
            f"[bold green]pyhatch[/] version [cyan]{__version__}[/]\n\n"
            f"[dim]Modern Python project bootstrapper[/]\n"
            f"[dim]Toolchain: uv + ruff + basedpyright + pytest[/]",
            border_style="green",
        ))
        raise typer.Exit()


# =============================================================================
# Interactive Prompts
# =============================================================================

def prompt_project_type() -> ProjectType:
    """
    Interactively prompt the user to select a project type.

    Displays a list of available project types with descriptions
    and returns the selected type.

    Returns
    -------
    ProjectType
        The selected project type enum value.
    """
    choices = [
        questionary.Choice(
            title=f"{pt.value:<10} - {pt.description}",
            value=pt,
        )
        for pt in ProjectType
    ]

    result = questionary.select(
        "What type of project?",
        choices=choices,
        default=ProjectType.LIBRARY,
    ).ask()

    if result is None:
        raise typer.Abort()

    return result


def prompt_python_version() -> PythonVersion:
    """
    Interactively prompt for Python version selection.

    Returns
    -------
    PythonVersion
        The selected Python version.
    """
    choices = [
        questionary.Choice(
            title=f"Python {pv.value}",
            value=pv,
        )
        for pv in PythonVersion
    ]

    result = questionary.select(
        "Minimum Python version?",
        choices=choices,
        default=PythonVersion.PY312,
    ).ask()

    if result is None:
        raise typer.Abort()

    return result


def prompt_license() -> License:
    """
    Interactively prompt for license selection.

    Returns
    -------
    License
        The selected license.
    """
    choices = [
        questionary.Choice(
            title=lic.value,
            value=lic,
        )
        for lic in License
    ]

    result = questionary.select(
        "License?",
        choices=choices,
        default=License.MIT,
    ).ask()

    if result is None:
        raise typer.Abort()

    return result


def prompt_author() -> AuthorInfo:
    """
    Interactively prompt for author information.

    Attempts to read defaults from git config if available.

    Returns
    -------
    AuthorInfo
        Author name and optional email.
    """
    import subprocess

    # Try to get defaults from git config
    default_name = "Your Name"
    default_email = ""

    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            check=False, capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            default_name = result.stdout.strip()

        result = subprocess.run(
            ["git", "config", "user.email"],
            check=False, capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            default_email = result.stdout.strip()
    except FileNotFoundError:
        pass  # Git not installed

    name = questionary.text(
        "Author name:",
        default=default_name,
    ).ask()

    if name is None:
        raise typer.Abort()

    email = questionary.text(
        "Author email (optional):",
        default=default_email,
    ).ask()

    return AuthorInfo(
        name=name,
        email=email if email else None,
    )


def prompt_features() -> FeaturesConfig:
    """
    Interactively prompt for optional features.

    Returns
    -------
    FeaturesConfig
        Configuration of enabled features.
    """
    features = questionary.checkbox(
        "Include optional features:",
        choices=[
            questionary.Choice("GitHub Actions CI/CD", value="github_actions", checked=True),
            questionary.Choice("Pre-commit hooks", value="pre_commit", checked=True),
            questionary.Choice("VS Code settings", value="vscode", checked=True),
            questionary.Choice("Docker configuration", value="docker", checked=False),
            questionary.Choice("Documentation (MkDocs)", value="docs", checked=False),
            questionary.Choice("Dev Container", value="devcontainer", checked=False),
        ],
    ).ask()

    if features is None:
        raise typer.Abort()

    return FeaturesConfig(
        github_actions="github_actions" in features,
        pre_commit="pre_commit" in features,
        vscode="vscode" in features,
        docker="docker" in features,
        docs="docs" in features,
        devcontainer="devcontainer" in features,
    )


def prompt_description() -> str:
    """
    Prompt for project description.

    Returns
    -------
    str
        Project description.
    """
    result = questionary.text(
        "Project description:",
        default="A Python project",
    ).ask()

    if result is None:
        raise typer.Abort()

    return result


def prompt_type_checking_mode() -> TypeCheckingMode:
    """
    Prompt for type checking strictness level.

    Returns
    -------
    TypeCheckingMode
        Selected strictness level.
    """
    choices = [
        questionary.Choice(
            title="standard - Balanced checking (recommended)",
            value=TypeCheckingMode.STANDARD,
        ),
        questionary.Choice(
            title="strict   - Maximum strictness, requires annotations",
            value=TypeCheckingMode.STRICT,
        ),
        questionary.Choice(
            title="basic    - Minimal checking",
            value=TypeCheckingMode.BASIC,
        ),
    ]

    result = questionary.select(
        "Type checking strictness?",
        choices=choices,
        default=TypeCheckingMode.STANDARD,
    ).ask()

    if result is None:
        raise typer.Abort()

    return result


# =============================================================================
# Main Application Callback
# =============================================================================

@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """
    [bold]pyhatch[/] - Modern Python project bootstrapper.

    Create production-ready Python projects with 2025's best toolchain:
    [cyan]uv[/] + [cyan]ruff[/] + [cyan]basedpyright[/] + [cyan]pytest[/]

    [bold]Quick Start:[/]

        pyhatch new myproject

    [bold]Non-interactive:[/]

        pyhatch new myproject --type cli --python 3.12 --yes
    """
    pass


# =============================================================================
# New Command - Create a New Project
# =============================================================================

@app.command()
def new(
    name: Annotated[
        str,
        typer.Argument(
            help="Name of the project to create",
        ),
    ],
    # Project type
    project_type: Annotated[
        str | None,
        typer.Option(
            "--type",
            "-t",
            help="Project type: library, app, cli, api, script",
        ),
    ] = None,
    # Python version
    python: Annotated[
        str | None,
        typer.Option(
            "--python",
            "-p",
            help="Minimum Python version: 3.11, 3.12, 3.13",
        ),
    ] = None,
    # License
    license_: Annotated[
        str | None,
        typer.Option(
            "--license",
            "-l",
            help="License: MIT, Apache-2.0, GPL-3.0-only, BSD-3-Clause",
        ),
    ] = None,
    # Description
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            "-d",
            help="Short project description",
        ),
    ] = None,
    # Author
    author: Annotated[
        str | None,
        typer.Option(
            "--author",
            "-a",
            help="Author name",
        ),
    ] = None,
    email: Annotated[
        str | None,
        typer.Option(
            "--email",
            "-e",
            help="Author email",
        ),
    ] = None,
    # Output directory
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Directory to create project in (default: current directory)",
        ),
    ] = None,
    # Type checking mode
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Use strict type checking mode",
        ),
    ] = False,
    # Features
    no_git: Annotated[
        bool,
        typer.Option(
            "--no-git",
            help="Skip git initialization",
        ),
    ] = False,
    no_github_actions: Annotated[
        bool,
        typer.Option(
            "--no-github-actions",
            help="Skip GitHub Actions workflow",
        ),
    ] = False,
    no_pre_commit: Annotated[
        bool,
        typer.Option(
            "--no-pre-commit",
            help="Skip pre-commit configuration",
        ),
    ] = False,
    no_vscode: Annotated[
        bool,
        typer.Option(
            "--no-vscode",
            help="Skip VS Code settings",
        ),
    ] = False,
    with_docker: Annotated[
        bool,
        typer.Option(
            "--with-docker",
            help="Include Docker configuration",
        ),
    ] = False,
    with_docs: Annotated[
        bool,
        typer.Option(
            "--with-docs",
            help="Include MkDocs documentation setup",
        ),
    ] = False,
    # Interactive mode control
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Skip all prompts, use defaults",
        ),
    ] = False,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help="Force interactive mode even with options",
        ),
    ] = False,
) -> None:
    """
    Create a new Python project.

    Creates a complete project structure with modern tooling:

    - [cyan]uv[/] for package management
    - [cyan]ruff[/] for linting and formatting
    - [cyan]basedpyright[/] for type checking
    - [cyan]pytest[/] for testing

    [bold]Examples:[/]

        # Interactive mode (prompts for all options)
        pyhatch new myproject

        # Quick library with defaults
        pyhatch new mylib --type library --yes

        # CLI tool with strict type checking
        pyhatch new mycli --type cli --strict

        # API project with Docker
        pyhatch new myapi --type api --with-docker
    """
    # Determine if we should prompt for missing values
    should_prompt = interactive or (not yes and project_type is None)

    # Resolve project type
    resolved_type: ProjectType
    if project_type:
        try:
            resolved_type = ProjectType(project_type.lower())
        except ValueError:
            valid = ", ".join(pt.value for pt in ProjectType)
            rprint(f"[red]Error:[/] Invalid project type '{project_type}'. Valid: {valid}")
            raise typer.Exit(1)
    elif should_prompt:
        resolved_type = prompt_project_type()
    else:
        resolved_type = ProjectType.LIBRARY

    # Resolve Python version
    resolved_python: PythonVersion
    if python:
        try:
            resolved_python = PythonVersion(python)
        except ValueError:
            valid = ", ".join(pv.value for pv in PythonVersion)
            rprint(f"[red]Error:[/] Invalid Python version '{python}'. Valid: {valid}")
            raise typer.Exit(1)
    elif should_prompt:
        resolved_python = prompt_python_version()
    else:
        resolved_python = PythonVersion.PY312

    # Resolve license
    resolved_license: License
    if license_:
        try:
            resolved_license = License(license_)
        except ValueError:
            valid = ", ".join(lic.value for lic in License)
            rprint(f"[red]Error:[/] Invalid license '{license_}'. Valid: {valid}")
            raise typer.Exit(1)
    elif should_prompt:
        resolved_license = prompt_license()
    else:
        resolved_license = License.MIT

    # Resolve author
    resolved_author: AuthorInfo
    if author:
        resolved_author = AuthorInfo(name=author, email=email)
    elif should_prompt:
        resolved_author = prompt_author()
    else:
        resolved_author = AuthorInfo(name="Your Name", email=email)

    # Resolve description
    resolved_description: str
    if description:
        resolved_description = description
    elif should_prompt:
        resolved_description = prompt_description()
    else:
        resolved_description = "A Python project"

    # Resolve features
    resolved_features: FeaturesConfig
    if should_prompt and not yes:
        resolved_features = prompt_features()
    else:
        resolved_features = FeaturesConfig(
            github_actions=not no_github_actions,
            pre_commit=not no_pre_commit,
            vscode=not no_vscode,
            docker=with_docker,
            docs=with_docs,
            devcontainer=False,
        )

    # Resolve type checking mode
    resolved_mode: TypeCheckingMode
    if strict:
        resolved_mode = TypeCheckingMode.STRICT
    elif should_prompt:
        resolved_mode = prompt_type_checking_mode()
    else:
        resolved_mode = TypeCheckingMode.STANDARD

    # Build the configuration
    try:
        config = ProjectConfig(
            name=name,
            description=resolved_description,
            project_type=resolved_type,
            python_version=resolved_python,
            license=resolved_license,
            author=resolved_author,
            tooling=ToolingConfig(
                type_checking_mode=resolved_mode,
            ),
            features=resolved_features,
            output_dir=output_dir or Path.cwd(),
        )
    except ValueError as e:
        rprint(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    # Show configuration summary if in interactive mode
    if should_prompt and not yes:
        console.print()
        table = Table(title="Project Configuration", show_header=False)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Name", config.name)
        table.add_row("Type", config.project_type.value)
        table.add_row("Python", config.python_version.value)
        table.add_row("License", config.license.value)
        table.add_row("Author", config.author.name)
        table.add_row("Type Checking", config.tooling.type_checking_mode.value)
        table.add_row("Features", ", ".join(config.features.enabled_features) or "none")

        console.print(table)
        console.print()

        if not questionary.confirm("Create project with these settings?", default=True).ask():
            raise typer.Abort()

    # Create the project
    try:
        result = create_project(
            config,
            verbose=True,
            init_git=not no_git,
            validate=True,
        )

        if not result.success:
            raise typer.Exit(1)

    except FileExistsError:
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]Error:[/] {e}")
        raise typer.Exit(1)


# =============================================================================
# Audit Command (Phase 3 - Placeholder)
# =============================================================================

@app.command()
def audit(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to project to audit",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("."),
) -> None:
    """
    Audit an existing project for improvements.

    Analyzes a Python project and suggests modernization opportunities:

    - Outdated tooling (e.g., black → ruff)
    - Missing type annotations
    - Configuration improvements
    - Security best practices

    [bold]Example:[/]

        pyhatch audit ./myproject
        pyhatch audit .
    """
    try:
        result = audit_project(path)
    except FileNotFoundError as e:
        rprint(f"[red]Error:[/] {e}")
        raise typer.Exit(1)
    except NotADirectoryError as e:
        rprint(f"[red]Error:[/] {e}")
        raise typer.Exit(1)

    # Display project path
    console.print()
    console.print(f"[bold]Auditing:[/] {result.project_path}")
    console.print()

    # Display detected tooling
    if result.tooling_detected:
        tooling_table = Table(title="Detected Tooling", show_header=True)
        tooling_table.add_column("Category", style="cyan")
        tooling_table.add_column("Tool", style="green")

        tool_names = {
            "package_manager": "Package Manager",
            "linter": "Linter",
            "formatter": "Formatter",
            "import_sorter": "Import Sorter",
            "type_checker": "Type Checker",
            "pre_commit": "Pre-commit",
            "ci": "CI/CD",
            "type_coverage": "Type Coverage",
            "status": "Status",
        }

        for key, value in result.tooling_detected.items():
            display_name = tool_names.get(key, key)
            if value == "modern":
                tooling_table.add_row(display_name, f"[bold green]{value}[/]")
            else:
                tooling_table.add_row(display_name, value)

        console.print(tooling_table)
        console.print()

    # Display score
    score_color = "green" if result.score >= 80 else "yellow" if result.score >= 60 else "red"
    console.print(Panel(
        f"[bold {score_color}]{result.score}/100[/]",
        title="[bold]Project Health Score[/]",
        border_style=score_color,
    ))
    console.print()

    # Display recommendations
    if result.recommendations:
        rec_table = Table(title="Recommendations", show_header=True)
        rec_table.add_column("Severity", style="bold", width=10)
        rec_table.add_column("Category", style="cyan", width=15)
        rec_table.add_column("Message")
        rec_table.add_column("Action", style="dim")

        # Sort by severity (critical first)
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.ERROR: 1,
            Severity.WARNING: 2,
            Severity.INFO: 3,
        }
        sorted_recs = sorted(result.recommendations, key=lambda r: severity_order[r.severity])

        for rec in sorted_recs:
            severity_colors = {
                Severity.CRITICAL: "red",
                Severity.ERROR: "red",
                Severity.WARNING: "yellow",
                Severity.INFO: "blue",
            }
            severity_style = severity_colors.get(rec.severity, "white")

            rec_table.add_row(
                f"[{severity_style}]{rec.severity.value}[/]",
                rec.category.value.replace("_", " "),
                rec.message,
                rec.action or "",
            )

        console.print(rec_table)
    else:
        console.print(Panel(
            "[bold green]Your project is already using modern tooling![/]\n\n"
            "No recommendations at this time.",
            title="[bold]All Good[/]",
            border_style="green",
        ))

    # Summary
    if result.recommendations:
        console.print()
        summary_parts = []
        if result.critical_count:
            summary_parts.append(f"[red]{result.critical_count} critical[/]")
        if result.error_count:
            summary_parts.append(f"[red]{result.error_count} errors[/]")
        if result.warning_count:
            summary_parts.append(f"[yellow]{result.warning_count} warnings[/]")
        if result.info_count:
            summary_parts.append(f"[blue]{result.info_count} info[/]")

        console.print(f"[bold]Summary:[/] {', '.join(summary_parts)}")
        console.print()
        console.print("[dim]Run 'pyhatch upgrade .' to apply recommended changes[/]")


# =============================================================================
# Upgrade Command (Phase 3 - Placeholder)
# =============================================================================

@app.command()
def upgrade(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to project to upgrade",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("."),
    from_tool: Annotated[
        str | None,
        typer.Option(
            "--from",
            help="Source package manager to migrate from: poetry, pip, pipenv, setuptools",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be done without making changes",
        ),
    ] = False,
    no_backup: Annotated[
        bool,
        typer.Option(
            "--no-backup",
            help="Skip creating a backup of original files",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes", "-y",
            help="Skip confirmation prompt",
        ),
    ] = False,
) -> None:
    """
    Upgrade a project to modern tooling.

    Migrates an existing project from legacy tools to modern 2025 tooling:

    - poetry → uv
    - pip/requirements.txt → uv
    - black + isort + flake8 → ruff
    - mypy → basedpyright

    [bold]Examples:[/]

        pyhatch upgrade .
        pyhatch upgrade . --from poetry
        pyhatch upgrade ./myproject --dry-run
    """
    console.print()

    if dry_run:
        console.print("[yellow]DRY RUN - No changes will be made[/]")
        console.print()

    # Show migration plan first
    steps = create_migration_plan(path, from_tool)

    if not steps:
        console.print(Panel(
            "[green]No migrations needed![/]\n\n"
            "Your project may already be using modern tooling.\n"
            "Run 'pyhatch audit .' to check.",
            title="[bold]All Good[/]",
            border_style="green",
        ))
        return

    # Display migration plan
    plan_table = Table(title="Migration Plan", show_header=True)
    plan_table.add_column("#", style="dim", width=3)
    plan_table.add_column("Type", style="cyan", width=15)
    plan_table.add_column("Migration", width=40)
    plan_table.add_column("From → To", style="green")

    for i, step in enumerate(steps, 1):
        plan_table.add_row(
            str(i),
            step.migration_type.value.replace("_", " "),
            step.description,
            f"{step.source} → {step.target}",
        )

    console.print(plan_table)
    console.print()

    if dry_run:
        console.print("[dim]Run without --dry-run to apply these changes[/]")
        return

    # Confirm before proceeding
    if not yes:
        if not questionary.confirm(
            "Proceed with migration?",
            default=True,
        ).ask():
            raise typer.Abort()

    console.print()

    # Execute upgrade
    result = upgrade_project(
        path,
        from_tool=from_tool,
        dry_run=False,
        backup=not no_backup,
    )

    # Display results
    if result.backup_path:
        console.print(f"[dim]Backup created at: {result.backup_path}[/]")
        console.print()

    if result.changes_made:
        changes_table = Table(title="Changes Made", show_header=False)
        changes_table.add_column("Change", style="green")

        for change in result.changes_made:
            changes_table.add_row(f"✓ {change}")

        console.print(changes_table)
        console.print()

    if result.errors:
        error_table = Table(title="Errors", show_header=False)
        error_table.add_column("Error", style="red")

        for error in result.errors:
            error_table.add_row(f"✗ {error}")

        console.print(error_table)
        console.print()

    if result.success:
        console.print(Panel(
            "[bold green]Upgrade complete![/]\n\n"
            "Next steps:\n"
            "1. Run 'uv sync' to install dependencies\n"
            "2. Run 'uv run ruff check .' to lint\n"
            "3. Run 'uv run basedpyright' to type check",
            title="[bold]Success[/]",
            border_style="green",
        ))
    else:
        console.print(Panel(
            "[bold red]Upgrade completed with errors[/]\n\n"
            f"Check the backup at {result.backup_path} if you need to restore.",
            title="[bold]Partial Success[/]",
            border_style="yellow",
        ))
        raise typer.Exit(1)


# =============================================================================
# Add Command (Phase 3 - Placeholder)
# =============================================================================

@app.command()
def add(
    feature: Annotated[
        str,
        typer.Argument(
            help="Feature to add: github-actions, docker, docs, pre-commit, vscode, devcontainer",
        ),
    ],
    path: Annotated[
        Path,
        typer.Option(
            "--path",
            "-p",
            help="Path to project",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path("."),
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite existing files",
        ),
    ] = False,
) -> None:
    """
    Add a feature to an existing project.

    Adds configuration files for additional features:

    - github-actions: CI/CD workflow
    - docker: Dockerfile and docker-compose.yml
    - docs: MkDocs documentation setup
    - pre-commit: Pre-commit hooks configuration
    - vscode: VS Code settings and extensions
    - devcontainer: Dev container configuration

    [bold]Examples:[/]

        pyhatch add github-actions
        pyhatch add docker --path ./myproject
        pyhatch add docs --force
    """
    # Validate feature
    if feature not in FEATURE_TEMPLATES:
        valid = ", ".join(FEATURE_TEMPLATES.keys())
        rprint(f"[red]Error:[/] Unknown feature '{feature}'")
        rprint(f"[dim]Valid features: {valid}[/]")
        raise typer.Exit(1)

    # Resolve path early to avoid /tmp vs /private/tmp issues on macOS
    path = path.resolve()

    # Check for pyproject.toml
    if not (path / "pyproject.toml").exists():
        rprint(f"[red]Error:[/] No pyproject.toml found at {path}")
        rprint("[dim]Run 'pyhatch new' to create a new project first.[/]")
        raise typer.Exit(1)

    console.print()
    console.print(f"[bold]Adding {feature} to {path}[/]")
    console.print()

    # Show what will be created
    templates = FEATURE_TEMPLATES[feature]
    files_table = Table(title="Files to Create", show_header=True)
    files_table.add_column("File", style="cyan")
    files_table.add_column("Status", style="dim")

    for _, output_path in templates:
        full_path = path / output_path
        if full_path.exists():
            if force:
                files_table.add_row(output_path, "[yellow]will overwrite[/]")
            else:
                files_table.add_row(output_path, "[red]exists (use --force)[/]")
        else:
            files_table.add_row(output_path, "[green]will create[/]")

    console.print(files_table)
    console.print()

    # Try to add the feature
    try:
        created_files = add_feature_to_project(path, feature, force=force)

        console.print(Panel(
            f"[bold green]Added {feature}![/]\n\n"
            f"Created {len(created_files)} file(s):\n" +
            "\n".join(f"  - {f.relative_to(path)}" for f in created_files),
            title="[bold]Success[/]",
            border_style="green",
        ))

        # Show next steps based on feature
        if feature == "docker":
            console.print()
            console.print("[dim]Next steps:[/]")
            console.print("  docker compose build")
            console.print("  docker compose up")
        elif feature == "docs":
            console.print()
            console.print("[dim]Next steps:[/]")
            console.print("  uv add --dev mkdocs mkdocs-material mkdocstrings[python]")
            console.print("  uv run mkdocs serve")
        elif feature == "pre-commit":
            console.print()
            console.print("[dim]Next steps:[/]")
            console.print("  uv run pre-commit install")
            console.print("  uv run pre-commit run --all-files")
        elif feature == "github-actions":
            console.print()
            console.print("[dim]Next steps:[/]")
            console.print("  git add .github/")
            console.print("  git commit -m 'Add GitHub Actions CI'")

    except FileExistsError as e:
        rprint(f"[red]Error:[/] {e}")
        raise typer.Exit(1)
    except FileNotFoundError as e:
        rprint(f"[red]Error:[/] {e}")
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]Error:[/] {e}")
        raise typer.Exit(1)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    app()
