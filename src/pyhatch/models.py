"""
pyhatch.models - Pydantic Models for Project Configuration
==========================================================

This module defines all the data models used throughout pyhatch. We use Pydantic
for several key benefits:

1. **Validation**: Automatic validation of user input with clear error messages
2. **Serialization**: Easy conversion to/from TOML, JSON, and dictionaries
3. **Type Safety**: Full type hints that work with basedpyright/pyright
4. **Documentation**: Models are self-documenting with field descriptions

Architecture Notes
------------------
The models are organized in a hierarchy:

    ProjectConfig (main)
    ├── ProjectType (enum)
    ├── PythonVersion (enum)
    ├── License (enum)
    ├── ToolingConfig
    │   ├── linter: str
    │   ├── formatter: str
    │   └── type_checker: str
    └── FeaturesConfig
        ├── github_actions: bool
        ├── docker: bool
        └── docs: bool

Usage Example
-------------
>>> from pyhatch.models import ProjectConfig, ProjectType
>>> config = ProjectConfig(
...     name="myproject",
...     project_type=ProjectType.LIBRARY,
...     python_version="3.12",
... )
>>> config.get_src_path()
PosixPath('src/myproject')
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# Enumerations
# =============================================================================

class ProjectType(str, Enum):
    """
    Supported project types that determine the generated structure.

    Each type has different defaults for dependencies, entry points,
    and configuration. The CLI presents these as interactive choices.

    Attributes
    ----------
    LIBRARY : str
        A publishable PyPI package with src layout. Includes packaging
        configuration for wheel/sdist builds.

    APP : str
        A standalone application not intended for PyPI. Uses flat layout
        with a main.py entry point.

    CLI : str
        A command-line tool using Typer. Includes CLI entry point
        configuration and rich terminal output.

    API : str
        A web API service. Includes FastAPI or Flask as a dependency
        with basic route structure.

    SCRIPT : str
        A single-file script with PEP 723 inline dependencies.
        Minimal structure for quick automation tasks.

    Examples
    --------
    >>> ProjectType.LIBRARY.value
    'library'
    >>> ProjectType.CLI.description
    'Command-line tool with Typer'
    """

    LIBRARY = "library"
    APP = "app"
    CLI = "cli"
    API = "api"
    SCRIPT = "script"

    @property
    def description(self) -> str:
        """
        Human-readable description for CLI prompts.

        Returns
        -------
        str
            A short description explaining what this project type creates.
        """
        descriptions = {
            ProjectType.LIBRARY: "Publishable PyPI package with src layout",
            ProjectType.APP: "Standalone application",
            ProjectType.CLI: "Command-line tool with Typer",
            ProjectType.API: "Web API service (FastAPI/Flask)",
            ProjectType.SCRIPT: "Single-file script with inline deps (PEP 723)",
        }
        return descriptions[self]

    @property
    def uses_src_layout(self) -> bool:
        """
        Whether this project type uses the src/ layout.

        The src layout (src/packagename/) is recommended for libraries
        to prevent accidental imports of the local package during testing.

        Returns
        -------
        bool
            True if project uses src/ directory structure.
        """
        return self in {ProjectType.LIBRARY, ProjectType.CLI, ProjectType.API}


class PythonVersion(str, Enum):
    """
    Supported Python versions for project configuration.

    We only support actively maintained Python versions as of 2025.
    Python 3.10 is the minimum to leverage modern features like
    pattern matching and improved type hints.

    Note
    ----
    Python 3.9 and earlier are intentionally excluded as they
    lack critical features for modern development (e.g., PEP 604
    union syntax, structural pattern matching).
    """

    PY311 = "3.11"
    PY312 = "3.12"
    PY313 = "3.13"

    @property
    def requires_python(self) -> str:
        """
        Generate the requires-python specifier for pyproject.toml.

        Returns
        -------
        str
            A PEP 440 version specifier like '>=3.11'.
        """
        return f">={self.value}"


class License(str, Enum):
    """
    Common open-source licenses for project configuration.

    These are the most popular licenses for Python packages based on
    PyPI statistics. Each license has different implications for
    commercial use, modification, and distribution.

    References
    ----------
    - https://choosealicense.com/ for license comparison
    - https://spdx.org/licenses/ for SPDX identifiers
    """

    MIT = "MIT"
    APACHE2 = "Apache-2.0"
    GPL3 = "GPL-3.0-only"
    BSD3 = "BSD-3-Clause"
    UNLICENSE = "Unlicense"
    PROPRIETARY = "Proprietary"

    @property
    def spdx_id(self) -> str:
        """
        SPDX license identifier for pyproject.toml.

        SPDX identifiers are standardized short names for licenses
        that tools can parse unambiguously.

        Returns
        -------
        str
            The SPDX identifier (same as enum value for most).
        """
        return self.value


class TypeCheckingMode(str, Enum):
    """
    Type checking strictness levels for basedpyright/pyright.

    These map directly to pyright's typeCheckingMode configuration.
    Stricter modes catch more potential bugs but may require more
    type annotations in your code.

    Attributes
    ----------
    OFF : str
        No type checking (not recommended).

    BASIC : str
        Minimal checking for obvious errors only.

    STANDARD : str
        Balanced checking suitable for most projects.
        This is the recommended default.

    STRICT : str
        Maximum strictness, requires explicit type annotations.
        Good for libraries and production code.

    ALL : str
        Enable every possible check. Very strict, may be noisy.
    """

    OFF = "off"
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"
    ALL = "all"


# =============================================================================
# Configuration Sub-Models
# =============================================================================

class ToolingConfig(BaseModel):
    """
    Configuration for development tools.

    This model defines which tools are used for linting, formatting,
    and type checking. While pyhatch defaults to modern 2025 tools,
    this allows customization for teams with existing preferences.

    Attributes
    ----------
    linter : str
        Linting tool. Default is 'ruff' (replaces flake8, pylint).

    formatter : str
        Code formatting tool. Default is 'ruff' (replaces black).

    type_checker : str
        Static type checker. Default is 'basedpyright'.
        Alternative: 'pyright', 'mypy'.

    type_checking_mode : TypeCheckingMode
        Strictness level for type checking.

    Examples
    --------
    >>> config = ToolingConfig()
    >>> config.linter
    'ruff'
    >>> config = ToolingConfig(type_checker='mypy')
    >>> config.type_checker
    'mypy'
    """

    linter: str = Field(
        default="ruff",
        description="Linting tool to use (ruff, flake8, pylint)",
    )
    formatter: str = Field(
        default="ruff",
        description="Code formatting tool (ruff, black)",
    )
    type_checker: str = Field(
        default="basedpyright",
        description="Static type checker (basedpyright, pyright, mypy)",
    )
    type_checking_mode: TypeCheckingMode = Field(
        default=TypeCheckingMode.STANDARD,
        description="Type checking strictness level",
    )

    @field_validator("linter", "formatter", "type_checker")
    @classmethod
    def validate_tool_names(cls, v: str) -> str:
        """
        Normalize tool names to lowercase.

        This ensures consistent comparison regardless of user input case.
        """
        return v.lower().strip()


class FeaturesConfig(BaseModel):
    """
    Optional features to include in the generated project.

    These are add-ons that enhance the project but aren't required
    for basic functionality. Each feature adds files/configuration
    to the generated project.

    Attributes
    ----------
    github_actions : bool
        Include GitHub Actions CI/CD workflows for testing,
        linting, and optional PyPI publishing.

    docker : bool
        Include Dockerfile and docker-compose.yml for containerized
        development and deployment.

    devcontainer : bool
        Include VS Code devcontainer configuration for consistent
        development environments.

    docs : bool
        Include MkDocs documentation setup with material theme.

    pre_commit : bool
        Include pre-commit hooks configuration for automated
        code quality checks on commit.

    vscode : bool
        Include VS Code workspace settings configured for
        the project's tooling.

    Examples
    --------
    >>> features = FeaturesConfig(github_actions=True, docker=True)
    >>> features.enabled_features
    ['github_actions', 'docker']
    """

    github_actions: bool = Field(
        default=True,
        description="Include GitHub Actions CI/CD workflows",
    )
    docker: bool = Field(
        default=False,
        description="Include Docker configuration",
    )
    devcontainer: bool = Field(
        default=False,
        description="Include VS Code devcontainer",
    )
    docs: bool = Field(
        default=False,
        description="Include MkDocs documentation setup",
    )
    pre_commit: bool = Field(
        default=True,
        description="Include pre-commit hooks configuration",
    )
    vscode: bool = Field(
        default=True,
        description="Include VS Code workspace settings",
    )

    @property
    def enabled_features(self) -> list[str]:
        """
        List of feature names that are enabled.

        Returns
        -------
        list[str]
            Names of features set to True.
        """
        return [
            name for name, value in self.model_dump().items()
            if value is True
        ]


class AuthorInfo(BaseModel):
    """
    Author information for project metadata.

    This information is used in pyproject.toml's [project.authors]
    section and can also populate LICENSE files and documentation.

    Attributes
    ----------
    name : str
        Author's full name or organization name.

    email : str | None
        Author's email address (optional but recommended).

    Note
    ----
    If email is not provided, pyhatch will attempt to read from
    git config during project creation.
    """

    name: str = Field(
        description="Author's name",
        min_length=1,
        max_length=100,
    )
    email: str | None = Field(
        default=None,
        description="Author's email address",
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        """
        Basic email format validation.

        We use a simple regex rather than strict RFC 5322 compliance
        to avoid rejecting valid but unusual email addresses.
        """
        if v is None:
            return None

        # Simple email pattern - allows most valid addresses
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            msg = f"Invalid email format: {v}"
            raise ValueError(msg)
        return v


# =============================================================================
# Main Configuration Model
# =============================================================================

class ProjectConfig(BaseModel):
    """
    Complete configuration for a pyhatch project.

    This is the main model that holds all settings for project generation.
    It combines project metadata, tooling preferences, and feature flags
    into a single validated configuration object.

    The configuration can be:
    - Built interactively via CLI prompts
    - Loaded from a pyhatch.toml file
    - Constructed programmatically via the Python API

    Attributes
    ----------
    name : str
        Project name. Must be a valid Python package name (lowercase,
        underscores allowed, no hyphens in import name).

    description : str
        Short project description for pyproject.toml and README.

    project_type : ProjectType
        Type of project to generate (library, cli, app, etc.).

    python_version : PythonVersion
        Minimum Python version to support.

    license : License
        Open-source license for the project.

    author : AuthorInfo
        Author information for project metadata.

    tooling : ToolingConfig
        Development tool preferences.

    features : FeaturesConfig
        Optional features to include.

    output_dir : Path
        Directory where the project will be created.

    Examples
    --------
    >>> config = ProjectConfig(
    ...     name="my-awesome-lib",
    ...     description="A library that does awesome things",
    ...     project_type=ProjectType.LIBRARY,
    ...     author=AuthorInfo(name="Jane Doe", email="jane@example.com"),
    ... )
    >>> config.package_name
    'my_awesome_lib'
    >>> config.get_src_path()
    PosixPath('src/my_awesome_lib')

    See Also
    --------
    create_project : Function that uses this config to generate projects.
    """

    # -------------------------------------------------------------------------
    # Required Fields
    # -------------------------------------------------------------------------
    name: Annotated[str, Field(
        description="Project name (used in pyproject.toml)",
        min_length=1,
        max_length=100,
    )]

    # -------------------------------------------------------------------------
    # Fields with Defaults
    # -------------------------------------------------------------------------
    description: str = Field(
        default="A Python project",
        description="Short project description",
        max_length=500,
    )
    project_type: ProjectType = Field(
        default=ProjectType.LIBRARY,
        description="Type of project to generate",
    )
    python_version: PythonVersion = Field(
        default=PythonVersion.PY312,
        description="Minimum Python version to support",
    )
    license: License = Field(
        default=License.MIT,
        description="Project license",
    )
    author: AuthorInfo = Field(
        default_factory=lambda: AuthorInfo(name="Your Name"),
        description="Author information",
    )
    tooling: ToolingConfig = Field(
        default_factory=ToolingConfig,
        description="Development tool preferences",
    )
    features: FeaturesConfig = Field(
        default_factory=FeaturesConfig,
        description="Optional features to include",
    )
    output_dir: Path = Field(
        default_factory=Path.cwd,
        description="Directory where project will be created",
    )

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------

    @field_validator("name")
    @classmethod
    def validate_project_name(cls, v: str) -> str:
        """
        Validate and normalize the project name.

        Project names must follow Python package naming conventions:
        - Start with a letter
        - Contain only letters, numbers, hyphens, and underscores
        - Not be a Python reserved word

        Parameters
        ----------
        v : str
            The project name to validate.

        Returns
        -------
        str
            The normalized project name (lowercase, stripped).

        Raises
        ------
        ValueError
            If the name doesn't meet the requirements.
        """
        # Normalize: lowercase and strip whitespace
        v = v.lower().strip()

        # Check for valid characters
        if not re.match(r"^[a-z][a-z0-9_-]*$", v):
            msg = (
                f"Invalid project name '{v}'. Names must start with a letter "
                "and contain only letters, numbers, hyphens, and underscores."
            )
            raise ValueError(msg)

        # Check against Python reserved words
        reserved = {
            "and", "as", "assert", "async", "await", "break", "class",
            "continue", "def", "del", "elif", "else", "except", "finally",
            "for", "from", "global", "if", "import", "in", "is", "lambda",
            "nonlocal", "not", "or", "pass", "raise", "return", "try",
            "while", "with", "yield", "True", "False", "None",
        }
        if v in reserved:
            msg = f"'{v}' is a Python reserved word and cannot be used as a project name."
            raise ValueError(msg)

        return v

    @model_validator(mode="after")
    def validate_config_consistency(self) -> ProjectConfig:
        """
        Validate that the configuration is internally consistent.

        This checks for logical inconsistencies like enabling features
        that don't make sense for certain project types.
        """
        # Script type shouldn't have complex features
        if self.project_type == ProjectType.SCRIPT:
            if self.features.docker:
                msg = "Docker is not applicable for single-file scripts."
                raise ValueError(msg)
            if self.features.docs:
                msg = "Documentation setup is not applicable for single-file scripts."
                raise ValueError(msg)

        return self

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------

    @property
    def package_name(self) -> str:
        """
        Convert project name to valid Python package name.

        Hyphens are replaced with underscores since Python import
        statements don't allow hyphens.

        Returns
        -------
        str
            Package name suitable for `import package_name`.

        Examples
        --------
        >>> config = ProjectConfig(name="my-cool-project")
        >>> config.package_name
        'my_cool_project'
        """
        return self.name.replace("-", "_")

    @property
    def project_dir(self) -> Path:
        """
        Full path to the project directory.

        Returns
        -------
        Path
            output_dir / project_name
        """
        return self.output_dir / self.name

    def get_src_path(self) -> Path:
        """
        Get the path to the source code directory.

        The path depends on whether the project uses src layout:
        - src layout: src/{package_name}/
        - flat layout: {package_name}/

        Returns
        -------
        Path
            Relative path to the source directory.

        Examples
        --------
        >>> config = ProjectConfig(name="mylib", project_type=ProjectType.LIBRARY)
        >>> config.get_src_path()
        PosixPath('src/mylib')
        >>> config = ProjectConfig(name="myapp", project_type=ProjectType.APP)
        >>> config.get_src_path()
        PosixPath('myapp')
        """
        if self.project_type.uses_src_layout:
            return Path("src") / self.package_name
        return Path(self.package_name)

    def get_test_path(self) -> Path:
        """
        Get the path to the tests directory.

        Returns
        -------
        Path
            Relative path to tests directory (always 'tests/').
        """
        return Path("tests")

    # -------------------------------------------------------------------------
    # Serialization Methods
    # -------------------------------------------------------------------------

    def to_toml_dict(self) -> dict:
        """
        Convert config to a dictionary suitable for TOML serialization.

        This is used when saving the configuration to a pyhatch.toml file
        for later reference or modification.

        Returns
        -------
        dict
            Configuration as a nested dictionary with TOML-compatible types.
        """
        data = self.model_dump(mode="json")
        # Convert Path to string for TOML
        data["output_dir"] = str(data["output_dir"])
        return data

    @classmethod
    def from_toml(cls, path: Path) -> ProjectConfig:
        """
        Load configuration from a TOML file.

        Parameters
        ----------
        path : Path
            Path to the TOML configuration file.

        Returns
        -------
        ProjectConfig
            Validated configuration object.

        Raises
        ------
        FileNotFoundError
            If the config file doesn't exist.
        ValidationError
            If the config file has invalid values.
        """
        import tomli

        with open(path, "rb") as f:
            data = tomli.load(f)

        return cls(**data)
