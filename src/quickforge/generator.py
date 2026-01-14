"""
quickforge.generator - Core Project Generation Logic
==================================================

This module contains the main logic for generating Python projects.
It orchestrates template rendering, file creation, and post-creation
validation to ensure users get working projects out of the box.

Architecture
------------
The generator follows a pipeline pattern:

    1. Validate configuration (via Pydantic models)
    2. Create directory structure
    3. Render templates with Jinja2
    4. Write files to disk
    5. Initialize git repository
    6. Run post-creation validation

The pipeline is designed to be:
- **Idempotent**: Running twice produces the same result
- **Atomic-ish**: If something fails, we clean up partial work
- **Verbose**: Users see what's happening at each step

Template System
---------------
Templates are Jinja2 files in the `templates/` directory. Each template
receives a context dict containing:

    - config: The ProjectConfig object
    - quickforge_version: Version of quickforge for attribution
    - year: Current year for licenses

File naming conventions:
- `*.j2` extension for all templates
- Output filename = template name without `.j2`
- Special templates like `gitignore.j2` → `.gitignore`

Usage Example
-------------
>>> from quickforge.generator import create_project
>>> from quickforge.models import ProjectConfig, ProjectType
>>>
>>> config = ProjectConfig(
...     name="myproject",
...     project_type=ProjectType.CLI,
... )
>>> result = create_project(config)
>>> print(result.project_path)
PosixPath('/current/dir/myproject')

See Also
--------
- models.py: Configuration data models
- templates/: Jinja2 template files
- validators.py: Post-creation validation
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, PackageLoader, select_autoescape
from rich.console import Console
from rich.panel import Panel

from quickforge import __version__
from quickforge.models import (
    AuthorInfo,
    FeaturesConfig,
    License,
    ProjectConfig,
    ProjectType,
    PythonVersion,
    ToolingConfig,
    TypeCheckingMode,
)


if TYPE_CHECKING:
    from collections.abc import Callable

    from rich.progress import Progress


# =============================================================================
# Module-Level Configuration
# =============================================================================

# Console for rich output
console = Console()

# Template file mappings: template_name -> (output_path, condition_func)
# The condition_func determines if the template should be rendered
TEMPLATE_MAPPINGS: dict[str, tuple[str, Callable[[ProjectConfig], bool] | None]] = {
    # Core files (always generated)
    "pyproject.toml.j2": ("pyproject.toml", None),
    "README.md.j2": ("README.md", None),
    "gitignore.j2": (".gitignore", None),
    # Package files
    "package_init.py.j2": ("{src_path}/__init__.py", None),
    # Conditional files based on project type
    "cli.py.j2": ("{src_path}/cli.py", lambda c: c.project_type == ProjectType.CLI),
    "main.py.j2": (
        "{src_path}/main.py",
        lambda c: c.project_type in {ProjectType.APP, ProjectType.API},
    ),
    # Test files
    "test_main.py.j2": ("tests/test_main.py", None),
    # Feature-based files
    "pre-commit-config.yaml.j2": (
        ".pre-commit-config.yaml",
        lambda c: c.features.pre_commit,
    ),
    "github_ci.yml.j2": (
        ".github/workflows/ci.yml",
        lambda c: c.features.github_actions,
    ),
    "vscode_settings.json.j2": (
        ".vscode/settings.json",
        lambda c: c.features.vscode,
    ),
    "vscode_extensions.json.j2": (
        ".vscode/extensions.json",
        lambda c: c.features.vscode,
    ),
}

# License template mappings
LICENSE_TEMPLATES: dict[License, str] = {
    License.MIT: "LICENSE_MIT.j2",
    # Add more licenses as templates are created
}


# =============================================================================
# Result Data Classes
# =============================================================================


@dataclass
class GenerationResult:
    """
    Result of a project generation operation.

    This dataclass captures the outcome of project generation, including
    success status, the created project path, and any warnings or errors
    that occurred during the process.

    Attributes
    ----------
    success : bool
        Whether the project was created successfully.

    project_path : Path
        Absolute path to the created project directory.

    files_created : list[Path]
        List of all files that were created.

    warnings : list[str]
        Non-fatal warnings that occurred during generation.

    errors : list[str]
        Errors that occurred (only populated if success=False).

    validation_passed : bool
        Whether post-creation validation succeeded.

    Examples
    --------
    >>> result = GenerationResult(
    ...     success=True,
    ...     project_path=Path("/home/user/myproject"),
    ... )
    >>> if result.success:
    ...     print(f"Project created at {result.project_path}")
    """

    success: bool
    project_path: Path
    files_created: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_passed: bool = False


# =============================================================================
# Template Engine Setup
# =============================================================================


def create_jinja_env() -> Environment:
    """
    Create and configure the Jinja2 template environment.

    The environment is configured with:
    - Package-based template loading from quickforge.templates
    - Autoescaping disabled (we're generating code, not HTML)
    - Trim blocks and lstrip_blocks for cleaner output
    - Custom filters for common transformations

    Returns
    -------
    Environment
        Configured Jinja2 environment ready for template rendering.

    Notes
    -----
    We disable autoescaping because we're generating Python code and
    configuration files, not HTML. Template authors must be careful
    not to introduce injection vulnerabilities in user-facing strings.
    """
    env = Environment(
        loader=PackageLoader("quickforge", "templates"),
        autoescape=select_autoescape([]),  # Disable for code generation
        trim_blocks=True,  # Remove first newline after block tags
        lstrip_blocks=True,  # Strip leading whitespace before block tags
        keep_trailing_newline=True,  # Preserve trailing newlines in templates
    )

    # Add custom filters
    env.filters["snake_case"] = lambda s: s.replace("-", "_").lower()

    return env


# =============================================================================
# Directory Structure Creation
# =============================================================================


def create_directory_structure(config: ProjectConfig) -> list[Path]:
    """
    Create the project directory structure.

    This function creates all necessary directories for the project,
    including the source directory, tests directory, and any optional
    directories based on enabled features.

    Parameters
    ----------
    config : ProjectConfig
        Project configuration specifying the structure.

    Returns
    -------
    list[Path]
        List of directories that were created.

    Raises
    ------
    FileExistsError
        If the project directory already exists.
    OSError
        If directory creation fails due to permissions or other OS errors.

    Notes
    -----
    Directory structure varies by project type:

    Library/CLI/API (src layout):
        project/
        ├── src/
        │   └── package_name/
        ├── tests/
        └── ...

    App (flat layout):
        project/
        ├── package_name/
        ├── tests/
        └── ...
    """
    project_dir = config.project_dir
    created_dirs: list[Path] = []

    # Check if project directory already exists
    if project_dir.exists():
        raise FileExistsError(
            f"Directory '{project_dir}' already exists. "
            "Use a different name or remove the existing directory."
        )

    # Create project root
    project_dir.mkdir(parents=True)
    created_dirs.append(project_dir)

    # Create source directory based on layout
    src_path = project_dir / config.get_src_path()
    src_path.mkdir(parents=True)
    created_dirs.append(src_path)

    # Create tests directory
    tests_path = project_dir / config.get_test_path()
    tests_path.mkdir(parents=True)
    created_dirs.append(tests_path)

    # Create optional directories based on features
    if config.features.github_actions:
        github_dir = project_dir / ".github" / "workflows"
        github_dir.mkdir(parents=True)
        created_dirs.append(github_dir)

    if config.features.vscode:
        vscode_dir = project_dir / ".vscode"
        vscode_dir.mkdir(parents=True)
        created_dirs.append(vscode_dir)

    if config.features.docs:
        docs_dir = project_dir / "docs"
        docs_dir.mkdir(parents=True)
        created_dirs.append(docs_dir)

    if config.features.docker:
        # Docker files go in project root, no separate dir needed
        pass

    return created_dirs


# =============================================================================
# Template Rendering
# =============================================================================


def render_template(
    env: Environment,
    template_name: str,
    config: ProjectConfig,
) -> str:
    """
    Render a single template with the project configuration.

    Parameters
    ----------
    env : Environment
        The Jinja2 environment to use for rendering.

    template_name : str
        Name of the template file (e.g., "pyproject.toml.j2").

    config : ProjectConfig
        Project configuration to pass to the template.

    Returns
    -------
    str
        The rendered template content.

    Raises
    ------
    jinja2.TemplateNotFound
        If the template file doesn't exist.
    jinja2.TemplateSyntaxError
        If the template has syntax errors.

    Notes
    -----
    The template context includes:
    - config: The full ProjectConfig object
    - quickforge_version: For attribution in generated files
    - year: Current year for license files
    """
    template = env.get_template(template_name)

    # Build template context
    context = {
        "config": config,
        "quickforge_version": __version__,
        "year": datetime.now(UTC).year,
    }

    return template.render(**context)


def get_output_path(
    template_path: str,
    config: ProjectConfig,
) -> Path:
    """
    Convert a template output path pattern to an actual path.

    Template paths can contain placeholders like {src_path} that
    need to be resolved based on the project configuration.

    Parameters
    ----------
    template_path : str
        The output path pattern (e.g., "{src_path}/__init__.py").

    config : ProjectConfig
        Project configuration for resolving placeholders.

    Returns
    -------
    Path
        The resolved output path relative to project root.

    Examples
    --------
    >>> config = ProjectConfig(name="mylib", project_type=ProjectType.LIBRARY)
    >>> get_output_path("{src_path}/__init__.py", config)
    PosixPath('src/mylib/__init__.py')
    """
    # Replace placeholders
    path_str = template_path.format(
        src_path=config.get_src_path(),
        package_name=config.package_name,
        test_path=config.get_test_path(),
    )

    return Path(path_str)


def render_all_templates(
    config: ProjectConfig,
    progress: Progress | None = None,
) -> dict[Path, str]:
    """
    Render all applicable templates for the project.

    This function iterates through TEMPLATE_MAPPINGS, checks conditions,
    and renders templates that apply to the given configuration.

    Parameters
    ----------
    config : ProjectConfig
        Project configuration.

    progress : Progress | None
        Optional Rich progress bar for status updates.

    Returns
    -------
    dict[Path, str]
        Mapping of output paths (relative to project root) to rendered content.

    Notes
    -----
    Templates are skipped if:
    - Their condition function returns False
    - The template file doesn't exist (logged as warning)
    """
    env = create_jinja_env()
    rendered: dict[Path, str] = {}

    for template_name, (output_pattern, condition) in TEMPLATE_MAPPINGS.items():
        # Check if this template should be rendered
        if condition is not None and not condition(config):
            continue

        # Update progress if provided
        if progress:
            progress.console.print(f"  Rendering {template_name}...")

        try:
            # Render the template
            content = render_template(env, template_name, config)

            # Get the output path
            output_path = get_output_path(output_pattern, config)

            rendered[output_path] = content

        except Exception as e:
            console.print(f"[yellow]Warning: Failed to render {template_name}: {e}[/]")

    # Handle license file separately (different template based on license type)
    license_template = LICENSE_TEMPLATES.get(config.license)
    if license_template:
        try:
            content = render_template(env, license_template, config)
            rendered[Path("LICENSE")] = content
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to render LICENSE: {e}[/]")

    return rendered


# =============================================================================
# File Writing
# =============================================================================


def write_files(
    project_dir: Path,
    files: dict[Path, str],
    progress: Progress | None = None,
) -> list[Path]:
    """
    Write rendered files to the project directory.

    Parameters
    ----------
    project_dir : Path
        Root directory of the project.

    files : dict[Path, str]
        Mapping of relative paths to file contents.

    progress : Progress | None
        Optional Rich progress bar for status updates.

    Returns
    -------
    list[Path]
        List of absolute paths to created files.

    Raises
    ------
    OSError
        If file writing fails.
    """
    created_files: list[Path] = []

    for relative_path, content in files.items():
        full_path = project_dir / relative_path

        # Ensure parent directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        full_path.write_text(content, encoding="utf-8")
        created_files.append(full_path)

        if progress:
            progress.console.print(f"  Created {relative_path}")

    return created_files


def create_py_typed(config: ProjectConfig) -> None:
    """
    Create the py.typed marker file for PEP 561 compliance.

    This marker file indicates that the package supports type checking
    and includes inline type annotations or stub files.

    Parameters
    ----------
    config : ProjectConfig
        Project configuration.

    Notes
    -----
    PEP 561 (https://peps.python.org/pep-0561/) defines how packages
    can indicate they support type checking. The py.typed file is an
    empty marker that type checkers look for.
    """
    py_typed_path = config.project_dir / config.get_src_path() / "py.typed"
    py_typed_path.touch()


def create_test_init(config: ProjectConfig) -> None:
    """
    Create an empty __init__.py in the tests directory.

    This file is required for pytest to properly discover tests
    in the tests/ directory when using src layout.

    Parameters
    ----------
    config : ProjectConfig
        Project configuration.
    """
    test_init_path = config.project_dir / config.get_test_path() / "__init__.py"
    test_init_path.write_text(
        f'"""Tests for the {config.name} package."""\n',
        encoding="utf-8",
    )


# =============================================================================
# Git Initialization
# =============================================================================


def init_git_repository(project_dir: Path) -> bool:
    """
    Initialize a git repository in the project directory.

    This function runs `git init` and creates an initial commit with
    all generated files.

    Parameters
    ----------
    project_dir : Path
        Root directory of the project.

    Returns
    -------
    bool
        True if git initialization succeeded, False otherwise.

    Notes
    -----
    If git is not available or the commands fail, this function
    returns False but does not raise an exception. The project
    is still usable without git.
    """
    try:
        # Check if git is available
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=True,
        )

        # Initialize repository
        subprocess.run(
            ["git", "init"],
            cwd=project_dir,
            capture_output=True,
            check=True,
        )

        # Add all files
        subprocess.run(
            ["git", "add", "."],
            cwd=project_dir,
            capture_output=True,
            check=True,
        )

        # Create initial commit
        subprocess.run(
            ["git", "commit", "-m", "Initial commit (generated by quickforge)"],
            cwd=project_dir,
            capture_output=True,
            check=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "quickforge",
                "GIT_AUTHOR_EMAIL": "quickforge@example.com",
                "GIT_COMMITTER_NAME": "quickforge",
                "GIT_COMMITTER_EMAIL": "quickforge@example.com",
            },
        )

        return True

    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# =============================================================================
# Post-Creation Validation
# =============================================================================


def validate_project(config: ProjectConfig) -> tuple[bool, list[str]]:
    """
    Validate that the generated project is correctly set up.

    This function performs several checks to ensure the project
    was generated correctly and is ready for development.

    Parameters
    ----------
    config : ProjectConfig
        Project configuration.

    Returns
    -------
    tuple[bool, list[str]]
        A tuple of (success, issues) where success is True if all
        validations passed, and issues is a list of any problems found.

    Checks Performed
    ----------------
    1. All expected files exist
    2. pyproject.toml is valid TOML
    3. Package __init__.py is importable syntax
    4. .gitignore exists and has content
    """
    issues: list[str] = []
    project_dir = config.project_dir

    # Check essential files exist
    essential_files = [
        "pyproject.toml",
        "README.md",
        ".gitignore",
        config.get_src_path() / "__init__.py",
        config.get_src_path() / "py.typed",
        config.get_test_path() / "__init__.py",
    ]

    for file_path in essential_files:
        full_path = project_dir / file_path
        if not full_path.exists():
            issues.append(f"Missing essential file: {file_path}")

    # Validate pyproject.toml is valid TOML
    pyproject_path = project_dir / "pyproject.toml"
    if pyproject_path.exists():
        try:
            import tomli

            with pyproject_path.open("rb") as f:
                tomli.load(f)
        except Exception as e:
            issues.append(f"Invalid pyproject.toml: {e}")

    # Check Python syntax of generated files
    python_files = list(project_dir.rglob("*.py"))
    for py_file in python_files:
        try:
            content = py_file.read_text(encoding="utf-8")
            compile(content, py_file, "exec")
        except SyntaxError as e:
            issues.append(f"Syntax error in {py_file.relative_to(project_dir)}: {e}")

    return len(issues) == 0, issues


# =============================================================================
# Main Generation Function
# =============================================================================


def create_project(
    config: ProjectConfig,
    *,
    verbose: bool = True,
    init_git: bool = True,
    validate: bool = True,
) -> GenerationResult:
    """
    Create a new Python project from the given configuration.

    This is the main entry point for project generation. It orchestrates
    the entire generation pipeline: directory creation, template rendering,
    file writing, git initialization, and validation.

    Parameters
    ----------
    config : ProjectConfig
        Complete project configuration.

    verbose : bool, default=True
        If True, display progress information to the console.

    init_git : bool, default=True
        If True, initialize a git repository in the project.

    validate : bool, default=True
        If True, run post-creation validation checks.

    Returns
    -------
    GenerationResult
        Result object containing success status and details.

    Raises
    ------
    FileExistsError
        If the project directory already exists.

    Examples
    --------
    >>> from quickforge.models import ProjectConfig, ProjectType
    >>> config = ProjectConfig(
    ...     name="myproject",
    ...     project_type=ProjectType.LIBRARY,
    ... )
    >>> result = create_project(config)
    >>> print(f"Created: {result.project_path}")
    Created: /path/to/myproject

    Notes
    -----
    The generation process is designed to be as atomic as possible.
    If an error occurs partway through, the partially created project
    directory is removed to avoid leaving broken state.

    See Also
    --------
    ProjectConfig : Configuration model for projects.
    GenerationResult : Result container for generation outcome.
    """
    result = GenerationResult(
        success=False,
        project_path=config.project_dir,
    )

    try:
        # Display header
        if verbose:
            console.print()
            console.print(
                Panel(
                    f"[bold blue]Creating project:[/] [green]{config.name}[/]\n"
                    f"[dim]Type: {config.project_type.value} | "
                    f"Python: {config.python_version.value} | "
                    f"License: {config.license.value}[/]",
                    title="[bold]quickforge[/]",
                    border_style="blue",
                )
            )
            console.print()

        # Step 1: Create directory structure
        if verbose:
            console.print("[bold]📁 Creating directory structure...[/]")

        created_dirs = create_directory_structure(config)

        if verbose:
            for d in created_dirs:
                console.print(f"  Created {d.relative_to(config.output_dir)}/")

        # Step 2: Render templates
        if verbose:
            console.print()
            console.print("[bold]📝 Rendering templates...[/]")

        rendered_files = render_all_templates(config)

        # Step 3: Write files
        if verbose:
            console.print()
            console.print("[bold]💾 Writing files...[/]")

        written_files = write_files(config.project_dir, rendered_files)
        result.files_created.extend(written_files)

        # Step 4: Create additional files
        create_py_typed(config)
        result.files_created.append(
            config.project_dir / config.get_src_path() / "py.typed"
        )

        create_test_init(config)
        result.files_created.append(
            config.project_dir / config.get_test_path() / "__init__.py"
        )

        if verbose:
            console.print(f"  Created {config.get_src_path()}/py.typed")
            console.print(f"  Created {config.get_test_path()}/__init__.py")

        # Step 5: Initialize git repository
        if init_git:
            if verbose:
                console.print()
                console.print("[bold]🔧 Initializing git repository...[/]")

            git_success = init_git_repository(config.project_dir)

            if git_success:
                if verbose:
                    console.print("  [green]✓[/] Git repository initialized")
            else:
                result.warnings.append(
                    "Git initialization failed (git may not be installed)"
                )
                if verbose:
                    console.print("  [yellow]⚠[/] Git initialization skipped")

        # Step 6: Validate project
        if validate:
            if verbose:
                console.print()
                console.print("[bold]✅ Validating project...[/]")

            validation_success, validation_issues = validate_project(config)
            result.validation_passed = validation_success

            if validation_success:
                if verbose:
                    console.print("  [green]✓[/] All validations passed")
            else:
                result.warnings.extend(validation_issues)
                if verbose:
                    for issue in validation_issues:
                        console.print(f"  [yellow]⚠[/] {issue}")

        # Success!
        result.success = True

        if verbose:
            console.print()
            console.print(
                Panel(
                    f"[bold green]✨ Project created successfully![/]\n\n"
                    f"[dim]Location:[/] {config.project_dir}\n\n"
                    f"[bold]Next steps:[/]\n"
                    f"  cd {config.name}\n"
                    f"  uv sync\n"
                    f"  uv run pytest",
                    title="[bold green]Success[/]",
                    border_style="green",
                )
            )

    except FileExistsError as e:
        result.errors.append(str(e))
        if verbose:
            console.print(f"\n[bold red]Error:[/] {e}")
        raise

    except Exception as e:
        result.errors.append(str(e))

        # Clean up partial project
        if config.project_dir.exists():
            shutil.rmtree(config.project_dir)
            result.warnings.append("Partial project directory was cleaned up")

        if verbose:
            console.print(f"\n[bold red]Error:[/] {e}")
            console.print("[dim]Partial project directory was removed.[/]")

        raise

    return result


# =============================================================================
# Add Feature to Existing Project
# =============================================================================

# Feature to template mapping
FEATURE_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "github-actions": [
        ("github_ci.yml.j2", ".github/workflows/ci.yml"),
    ],
    "pre-commit": [
        ("pre-commit-config.yaml.j2", ".pre-commit-config.yaml"),
    ],
    "vscode": [
        ("vscode_settings.json.j2", ".vscode/settings.json"),
        ("vscode_extensions.json.j2", ".vscode/extensions.json"),
    ],
    "docker": [
        ("Dockerfile.j2", "Dockerfile"),
        ("docker-compose.yml.j2", "docker-compose.yml"),
    ],
    "docs": [
        ("mkdocs.yml.j2", "mkdocs.yml"),
        ("docs_index.md.j2", "docs/index.md"),
    ],
    "devcontainer": [
        ("devcontainer.json.j2", ".devcontainer/devcontainer.json"),
    ],
}


def load_project_config(path: Path) -> ProjectConfig:
    """
    Load configuration from an existing project's pyproject.toml.

    Parameters
    ----------
    path : Path
        Path to the project root.

    Returns
    -------
    ProjectConfig
        Configuration loaded from the project.

    Raises
    ------
    FileNotFoundError
        If pyproject.toml doesn't exist.
    ValueError
        If the project configuration is invalid.
    """
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[import-not-found]

    pyproject_path = path / "pyproject.toml"
    if not pyproject_path.exists():
        raise FileNotFoundError(f"No pyproject.toml found at {path}")

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    project = data.get("project", {})
    tool = data.get("tool", {})

    # Extract name
    name = project.get("name", path.name)

    # Extract description
    description = project.get("description", "A Python project")

    # Detect project type
    project_type = ProjectType.LIBRARY
    scripts = project.get("scripts", {})
    if scripts:
        project_type = ProjectType.CLI

    # Extract Python version
    requires_python = project.get("requires-python", ">=3.12")
    if "3.13" in requires_python:
        python_version = PythonVersion.PY313
    elif "3.11" in requires_python:
        python_version = PythonVersion.PY311
    else:
        python_version = PythonVersion.PY312

    # Extract license
    license_info = project.get("license", {})
    license_text = (
        license_info.get("text", "MIT")
        if isinstance(license_info, dict)
        else str(license_info)
    )
    try:
        license_enum = License(license_text)
    except ValueError:
        license_enum = License.MIT

    # Extract author
    authors = project.get("authors", [])
    if authors:
        author = authors[0]
        author_name = (
            author.get("name", "Unknown") if isinstance(author, dict) else str(author)
        )
        author_email = author.get("email") if isinstance(author, dict) else None
        author_info = AuthorInfo(name=author_name, email=author_email)
    else:
        author_info = AuthorInfo(name="Unknown")

    # Detect type checking mode
    basedpyright = tool.get("basedpyright", {})
    pyright = tool.get("pyright", {})
    type_mode_str = basedpyright.get("typeCheckingMode") or pyright.get(
        "typeCheckingMode", "standard"
    )
    try:
        type_mode = TypeCheckingMode(type_mode_str)
    except ValueError:
        type_mode = TypeCheckingMode.STANDARD

    # Detect existing features
    features = FeaturesConfig(
        github_actions=(path / ".github" / "workflows").exists(),
        pre_commit=(path / ".pre-commit-config.yaml").exists(),
        vscode=(path / ".vscode" / "settings.json").exists(),
        docker=(path / "Dockerfile").exists(),
        docs=(path / "mkdocs.yml").exists(),
        devcontainer=(path / ".devcontainer" / "devcontainer.json").exists(),
    )

    return ProjectConfig(
        name=name,
        description=description,
        project_type=project_type,
        python_version=python_version,
        license=license_enum,
        author=author_info,
        tooling=ToolingConfig(type_checking_mode=type_mode),
        features=features,
        output_dir=path.parent,
    )


def add_feature_to_project(
    path: Path,
    feature: str,
    force: bool = False,
) -> list[Path]:
    """
    Add a feature to an existing project.

    Parameters
    ----------
    path : Path
        Path to the project root.

    feature : str
        Feature to add (github-actions, docker, docs, pre-commit, vscode, devcontainer).

    force : bool, default=False
        If True, overwrite existing files.

    Returns
    -------
    list[Path]
        List of files that were created.

    Raises
    ------
    ValueError
        If the feature is unknown.
    FileExistsError
        If files exist and force=False.
    """
    path = path.resolve()

    if feature not in FEATURE_TEMPLATES:
        valid = ", ".join(FEATURE_TEMPLATES.keys())
        raise ValueError(f"Unknown feature '{feature}'. Valid features: {valid}")

    # Load project configuration
    config = load_project_config(path)

    # Get templates for this feature
    templates = FEATURE_TEMPLATES[feature]

    # Check for existing files
    if not force:
        existing = []
        for _, output_path in templates:
            full_path = path / output_path
            if full_path.exists():
                existing.append(str(output_path))

        if existing:
            raise FileExistsError(
                f"Files already exist: {', '.join(existing)}. Use --force to overwrite."
            )

    # Create Jinja environment
    env = create_jinja_env()

    # Build context
    context = {
        "config": config,
        "quickforge_version": __version__,
        "year": datetime.now(UTC).year,
    }

    # Render and write templates
    created_files = []

    for template_name, output_path in templates:
        try:
            # Render template
            template = env.get_template(template_name)
            content = template.render(**context)

            # Ensure parent directory exists
            full_path = path / output_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            full_path.write_text(content)
            created_files.append(full_path)

        except Exception as e:
            # Clean up any files we've created
            for f in created_files:
                if f.exists():
                    f.unlink()
            raise RuntimeError(f"Failed to create {output_path}: {e}") from e

    return created_files
