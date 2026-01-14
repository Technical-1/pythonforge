"""
quickforge.auditor - Project Audit Module
======================================

This module provides functionality to audit existing Python projects
and identify opportunities for modernization and improvement.

Features
--------
1. **Tooling Analysis**
   - Detect current package manager (pip, poetry, pipenv)
   - Identify linters and formatters in use
   - Check type checker configuration

2. **Configuration Audit**
   - Validate pyproject.toml structure
   - Check for missing recommended sections
   - Identify deprecated configuration patterns

3. **Dependency Analysis**
   - Check for outdated packages
   - Identify security vulnerabilities
   - Find unused dependencies

4. **Code Quality Metrics**
   - Type annotation coverage
   - Test coverage
   - Cyclomatic complexity

Usage
-----
>>> from quickforge.auditor import audit_project
>>> from pathlib import Path
>>>
>>> result = audit_project(Path("./myproject"))
>>> print(result.recommendations)
[
    Recommendation(
        category="tooling",
        message="Consider migrating from black to ruff",
        severity="info",
    ),
    ...
]

See Also
--------
- upgrader.py: Module for applying audit recommendations
- cli.py: Command-line interface for audit command
"""

from __future__ import annotations

import ast
import configparser
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]


class AuditCategory(str, Enum):
    """
    Categories of audit findings.

    Used to organize recommendations by area of concern.
    """

    TOOLING = "tooling"
    CONFIGURATION = "configuration"
    DEPENDENCIES = "dependencies"
    SECURITY = "security"
    CODE_QUALITY = "code_quality"


class Severity(str, Enum):
    """
    Severity levels for audit findings.

    Helps users prioritize which issues to address first.
    """

    INFO = "info"  # Nice to have
    WARNING = "warning"  # Should fix eventually
    ERROR = "error"  # Should fix soon
    CRITICAL = "critical"  # Fix immediately


@dataclass
class Recommendation:
    """
    A single audit recommendation.

    Attributes
    ----------
    category : AuditCategory
        The area this recommendation relates to.

    message : str
        Human-readable description of the recommendation.

    severity : Severity
        How important this recommendation is.

    file_path : Path | None
        Specific file this relates to, if applicable.

    action : str | None
        Specific action to take (e.g., command to run).
    """

    category: AuditCategory
    message: str
    severity: Severity
    file_path: Path | None = None
    action: str | None = None


@dataclass
class AuditResult:
    """
    Result of a project audit.

    Attributes
    ----------
    project_path : Path
        Path to the audited project.

    recommendations : list[Recommendation]
        List of recommendations from the audit.

    score : int
        Overall project health score (0-100).

    tooling_detected : dict[str, str]
        Detected tools and their versions.
    """

    project_path: Path
    recommendations: list[Recommendation] = field(default_factory=list)
    score: int = 100
    tooling_detected: dict[str, str] = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        """Number of critical severity recommendations."""
        return sum(1 for r in self.recommendations if r.severity == Severity.CRITICAL)

    @property
    def error_count(self) -> int:
        """Number of error severity recommendations."""
        return sum(1 for r in self.recommendations if r.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        """Number of warning severity recommendations."""
        return sum(1 for r in self.recommendations if r.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        """Number of info severity recommendations."""
        return sum(1 for r in self.recommendations if r.severity == Severity.INFO)


# =============================================================================
# Detection Functions
# =============================================================================


def _read_toml(path: Path) -> dict | None:
    """Read a TOML file and return its contents."""
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except Exception:
        return None


def _read_ini(path: Path) -> configparser.ConfigParser | None:
    """Read an INI-style config file."""
    if not path.exists():
        return None
    try:
        config = configparser.ConfigParser()
        config.read(path)
        return config
    except Exception:
        return None


def detect_package_manager(path: Path) -> tuple[str | None, dict[str, str]]:
    """
    Detect the package manager used by a project.

    Parameters
    ----------
    path : Path
        Path to the project root.

    Returns
    -------
    tuple[str | None, dict[str, str]]
        Tuple of (package_manager_name, extra_info).
        Returns (None, {}) if no package manager detected.
    """
    info: dict[str, str] = {}

    # Check for uv (modern)
    if (path / "uv.lock").exists():
        return "uv", {"lock_file": "uv.lock"}

    # Check for Poetry
    if (path / "poetry.lock").exists():
        info["lock_file"] = "poetry.lock"
        return "poetry", info

    pyproject = _read_toml(path / "pyproject.toml")
    if pyproject:
        # Check for Poetry in pyproject.toml
        if "tool" in pyproject and "poetry" in pyproject["tool"]:
            return "poetry", {"config": "pyproject.toml"}

        # Check for PDM
        if "tool" in pyproject and "pdm" in pyproject["tool"]:
            return "pdm", {"config": "pyproject.toml"}

        # Check for Hatch
        if "tool" in pyproject and "hatch" in pyproject["tool"]:
            return "hatch", {"config": "pyproject.toml"}

        # Check for Flit
        if "tool" in pyproject and "flit" in pyproject["tool"]:
            return "flit", {"config": "pyproject.toml"}

    # Check for Pipenv
    if (path / "Pipfile").exists() or (path / "Pipfile.lock").exists():
        return "pipenv", {"config": "Pipfile"}

    # Check for pip/requirements.txt
    if (path / "requirements.txt").exists():
        info["requirements"] = "requirements.txt"
        # Check for additional requirements files
        for req_file in path.glob("requirements*.txt"):
            if req_file.name != "requirements.txt":
                info[req_file.name] = str(req_file.name)
        return "pip", info

    # Check for setup.py (legacy setuptools)
    if (path / "setup.py").exists():
        return "setuptools", {"config": "setup.py"}

    # Check for setup.cfg
    if (path / "setup.cfg").exists():
        return "setuptools", {"config": "setup.cfg"}

    return None, {}


def detect_linter(path: Path) -> tuple[str | None, dict[str, str]]:
    """
    Detect the linter used by a project.

    Parameters
    ----------
    path : Path
        Path to the project root.

    Returns
    -------
    tuple[str | None, dict[str, str]]
        Tuple of (linter_name, extra_info).
    """
    info: dict[str, str] = {}

    pyproject = _read_toml(path / "pyproject.toml")

    # Check for ruff (modern)
    if (path / "ruff.toml").exists():
        return "ruff", {"config": "ruff.toml"}
    if pyproject and "tool" in pyproject and "ruff" in pyproject["tool"]:
        return "ruff", {"config": "pyproject.toml"}

    # Check for flake8
    if (path / ".flake8").exists():
        return "flake8", {"config": ".flake8"}
    setup_cfg = _read_ini(path / "setup.cfg")
    if setup_cfg and setup_cfg.has_section("flake8"):
        return "flake8", {"config": "setup.cfg"}

    # Check for pylint
    if (path / ".pylintrc").exists():
        return "pylint", {"config": ".pylintrc"}
    if (path / "pylintrc").exists():
        return "pylint", {"config": "pylintrc"}
    if pyproject and "tool" in pyproject and "pylint" in pyproject["tool"]:
        return "pylint", {"config": "pyproject.toml"}

    return None, info


def detect_formatter(path: Path) -> tuple[str | None, dict[str, str]]:
    """
    Detect the formatter used by a project.

    Parameters
    ----------
    path : Path
        Path to the project root.

    Returns
    -------
    tuple[str | None, dict[str, str]]
        Tuple of (formatter_name, extra_info).
    """
    info: dict[str, str] = {}

    pyproject = _read_toml(path / "pyproject.toml")

    # Check for ruff format (modern)
    if pyproject and "tool" in pyproject and "ruff" in pyproject["tool"]:
        ruff_config = pyproject["tool"]["ruff"]
        if "format" in ruff_config or "line-length" in ruff_config:
            return "ruff", {"config": "pyproject.toml"}

    # Check for Black
    if pyproject and "tool" in pyproject and "black" in pyproject["tool"]:
        return "black", {"config": "pyproject.toml"}

    # Check for autopep8
    if pyproject and "tool" in pyproject and "autopep8" in pyproject["tool"]:
        return "autopep8", {"config": "pyproject.toml"}
    setup_cfg = _read_ini(path / "setup.cfg")
    if setup_cfg and setup_cfg.has_section("autopep8"):
        return "autopep8", {"config": "setup.cfg"}

    # Check for yapf
    if (path / ".style.yapf").exists():
        return "yapf", {"config": ".style.yapf"}
    if pyproject and "tool" in pyproject and "yapf" in pyproject["tool"]:
        return "yapf", {"config": "pyproject.toml"}

    return None, info


def detect_import_sorter(path: Path) -> tuple[str | None, dict[str, str]]:
    """
    Detect the import sorter used by a project.

    Parameters
    ----------
    path : Path
        Path to the project root.

    Returns
    -------
    tuple[str | None, dict[str, str]]
        Tuple of (sorter_name, extra_info).
    """
    pyproject = _read_toml(path / "pyproject.toml")

    # Check for ruff isort (modern)
    if pyproject and "tool" in pyproject and "ruff" in pyproject["tool"]:
        ruff_config = pyproject["tool"]["ruff"]
        if "lint" in ruff_config and "isort" in ruff_config.get("lint", {}):
            return "ruff", {"config": "pyproject.toml"}
        # Check if isort rules are enabled
        if "lint" in ruff_config:
            select = ruff_config.get("lint", {}).get("select", [])
            if "I" in select or any(
                s.startswith("I") for s in select if isinstance(s, str)
            ):
                return "ruff", {"config": "pyproject.toml"}

    # Check for isort
    if (path / ".isort.cfg").exists():
        return "isort", {"config": ".isort.cfg"}
    if pyproject and "tool" in pyproject and "isort" in pyproject["tool"]:
        return "isort", {"config": "pyproject.toml"}
    setup_cfg = _read_ini(path / "setup.cfg")
    if setup_cfg and setup_cfg.has_section("isort"):
        return "isort", {"config": "setup.cfg"}

    return None, {}


def detect_type_checker(path: Path) -> tuple[str | None, dict[str, str]]:
    """
    Detect the type checker used by a project.

    Parameters
    ----------
    path : Path
        Path to the project root.

    Returns
    -------
    tuple[str | None, dict[str, str]]
        Tuple of (type_checker_name, extra_info).
    """
    pyproject = _read_toml(path / "pyproject.toml")

    # Check for basedpyright (modern)
    if pyproject and "tool" in pyproject and "basedpyright" in pyproject["tool"]:
        return "basedpyright", {"config": "pyproject.toml"}

    # Check for pyright
    if (path / "pyrightconfig.json").exists():
        return "pyright", {"config": "pyrightconfig.json"}
    if pyproject and "tool" in pyproject and "pyright" in pyproject["tool"]:
        return "pyright", {"config": "pyproject.toml"}

    # Check for mypy
    if (path / "mypy.ini").exists():
        return "mypy", {"config": "mypy.ini"}
    if (path / ".mypy.ini").exists():
        return "mypy", {"config": ".mypy.ini"}
    if pyproject and "tool" in pyproject and "mypy" in pyproject["tool"]:
        return "mypy", {"config": "pyproject.toml"}
    setup_cfg = _read_ini(path / "setup.cfg")
    if setup_cfg and setup_cfg.has_section("mypy"):
        return "mypy", {"config": "setup.cfg"}

    # Check for pytype
    if (path / "pytype.cfg").exists():
        return "pytype", {"config": "pytype.cfg"}

    return None, {}


def detect_pre_commit(path: Path) -> bool:
    """Check if pre-commit is configured."""
    return (path / ".pre-commit-config.yaml").exists()


def detect_ci(path: Path) -> tuple[str | None, dict[str, str]]:
    """
    Detect CI/CD configuration.

    Parameters
    ----------
    path : Path
        Path to the project root.

    Returns
    -------
    tuple[str | None, dict[str, str]]
        Tuple of (ci_name, extra_info).
    """
    # GitHub Actions
    gh_workflows = path / ".github" / "workflows"
    if gh_workflows.exists() and any(gh_workflows.glob("*.yml")):
        workflows = list(gh_workflows.glob("*.yml"))
        return "github-actions", {"workflows": str(len(workflows))}

    # GitLab CI
    if (path / ".gitlab-ci.yml").exists():
        return "gitlab-ci", {"config": ".gitlab-ci.yml"}

    # Travis CI
    if (path / ".travis.yml").exists():
        return "travis-ci", {"config": ".travis.yml"}

    # CircleCI
    if (path / ".circleci" / "config.yml").exists():
        return "circleci", {"config": ".circleci/config.yml"}

    # Azure Pipelines
    if (path / "azure-pipelines.yml").exists():
        return "azure-pipelines", {"config": "azure-pipelines.yml"}

    return None, {}


def analyze_type_coverage(path: Path) -> tuple[float, int, int]:
    """
    Analyze type annotation coverage in Python files.

    Parameters
    ----------
    path : Path
        Path to the project root.

    Returns
    -------
    tuple[float, int, int]
        Tuple of (coverage_percentage, typed_functions, total_functions).
    """
    total_functions = 0
    typed_functions = 0

    # Find Python files
    python_files = list(path.glob("**/*.py"))

    # Exclude common non-source directories
    exclude_patterns = {
        "venv",
        ".venv",
        "env",
        ".env",
        "node_modules",
        "__pycache__",
        ".git",
        "build",
        "dist",
    }

    for py_file in python_files:
        # Skip excluded directories
        if any(part in exclude_patterns for part in py_file.parts):
            continue

        try:
            with py_file.open(encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total_functions += 1

                    # Check if function has return annotation or any parameter annotations
                    has_annotation = False

                    if node.returns is not None:
                        has_annotation = True
                    else:
                        for arg in (
                            node.args.args
                            + node.args.posonlyargs
                            + node.args.kwonlyargs
                        ):
                            if arg.annotation is not None:
                                has_annotation = True
                                break

                    if has_annotation:
                        typed_functions += 1

        except (SyntaxError, UnicodeDecodeError):
            continue

    if total_functions == 0:
        return 100.0, 0, 0

    coverage = (typed_functions / total_functions) * 100
    return coverage, typed_functions, total_functions


# =============================================================================
# Recommendation Generation
# =============================================================================


def _generate_tooling_recommendations(
    result: AuditResult,
    pkg_manager: str | None,
    linter: str | None,
    formatter: str | None,
    import_sorter: str | None,
    type_checker: str | None,
    has_pre_commit: bool,
    ci_system: str | None,
) -> None:
    """Generate recommendations for tooling improvements."""

    # Package manager recommendations
    if pkg_manager == "poetry":
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="Consider migrating from Poetry to uv for faster dependency resolution",
                severity=Severity.INFO,
                action="quickforge upgrade . --from poetry",
            )
        )
    elif pkg_manager == "pip":
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="Consider migrating from pip/requirements.txt to uv with pyproject.toml",
                severity=Severity.INFO,
                action="quickforge upgrade . --from pip",
            )
        )
    elif pkg_manager == "pipenv":
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="Consider migrating from Pipenv to uv for better performance",
                severity=Severity.INFO,
                action="quickforge upgrade . --from pipenv",
            )
        )
    elif pkg_manager == "setuptools":
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="Consider migrating from setup.py to pyproject.toml (PEP 621)",
                severity=Severity.WARNING,
                action="quickforge upgrade . --from setuptools",
            )
        )
    elif pkg_manager is None:
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="No package manager detected. Consider adding a pyproject.toml",
                severity=Severity.WARNING,
            )
        )

    # Linter recommendations
    if linter == "flake8":
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="Consider migrating from flake8 to ruff for better performance",
                severity=Severity.INFO,
                action="quickforge upgrade . (will migrate flake8 to ruff)",
            )
        )
    elif linter == "pylint":
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="Consider migrating from pylint to ruff for better performance",
                severity=Severity.INFO,
                action="quickforge upgrade . (will migrate pylint to ruff)",
            )
        )
    elif linter is None and formatter != "ruff":
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="No linter detected. Consider adding ruff for code quality",
                severity=Severity.WARNING,
                action="quickforge add pre-commit (includes ruff)",
            )
        )

    # Formatter recommendations
    if formatter == "black":
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="Consider migrating from black to ruff format for better performance",
                severity=Severity.INFO,
                action="quickforge upgrade . (will migrate black to ruff)",
            )
        )
    elif formatter == "autopep8":
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="Consider migrating from autopep8 to ruff format",
                severity=Severity.INFO,
            )
        )
    elif formatter == "yapf":
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="Consider migrating from yapf to ruff format",
                severity=Severity.INFO,
            )
        )

    # Import sorter recommendations
    if import_sorter == "isort":
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="Consider migrating from isort to ruff (handles import sorting)",
                severity=Severity.INFO,
                action="quickforge upgrade . (will migrate isort to ruff)",
            )
        )

    # Type checker recommendations
    if type_checker == "mypy":
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="Consider migrating from mypy to basedpyright for stricter checking",
                severity=Severity.INFO,
                action="quickforge upgrade . (will migrate mypy to basedpyright)",
            )
        )
    elif type_checker == "pytype":
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="Consider migrating from pytype to basedpyright",
                severity=Severity.INFO,
            )
        )
    elif type_checker is None:
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="No type checker detected. Consider adding basedpyright",
                severity=Severity.WARNING,
            )
        )

    # Pre-commit recommendations
    if not has_pre_commit:
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="No pre-commit hooks detected. Consider adding pre-commit",
                severity=Severity.INFO,
                action="quickforge add pre-commit",
            )
        )

    # CI recommendations
    if ci_system is None:
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.TOOLING,
                message="No CI/CD configuration detected. Consider adding GitHub Actions",
                severity=Severity.INFO,
                action="quickforge add github-actions",
            )
        )


def _generate_code_quality_recommendations(
    result: AuditResult,
    type_coverage: float,
    typed_functions: int,
    total_functions: int,
) -> None:
    """Generate recommendations for code quality improvements."""

    if total_functions == 0:
        return

    if type_coverage < 25:
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.CODE_QUALITY,
                message=f"Low type annotation coverage ({type_coverage:.0f}%). "
                f"Only {typed_functions}/{total_functions} functions have type hints",
                severity=Severity.WARNING,
            )
        )
    elif type_coverage < 50:
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.CODE_QUALITY,
                message=f"Moderate type annotation coverage ({type_coverage:.0f}%). "
                f"{typed_functions}/{total_functions} functions have type hints",
                severity=Severity.INFO,
            )
        )
    elif type_coverage < 80:
        result.recommendations.append(
            Recommendation(
                category=AuditCategory.CODE_QUALITY,
                message=f"Good type annotation coverage ({type_coverage:.0f}%). "
                f"Consider improving to 80%+",
                severity=Severity.INFO,
            )
        )


def _calculate_score(result: AuditResult) -> int:
    """Calculate overall project health score."""
    score = 100

    for rec in result.recommendations:
        if rec.severity == Severity.CRITICAL:
            score -= 20
        elif rec.severity == Severity.ERROR:
            score -= 10
        elif rec.severity == Severity.WARNING:
            score -= 5
        elif rec.severity == Severity.INFO:
            score -= 1

    return max(0, min(100, score))


# =============================================================================
# Main Audit Function
# =============================================================================


def audit_project(path: Path) -> AuditResult:
    """
    Audit a Python project for modernization opportunities.

    Parameters
    ----------
    path : Path
        Path to the project root directory.

    Returns
    -------
    AuditResult
        Audit findings and recommendations.

    Raises
    ------
    FileNotFoundError
        If the path does not exist.
    NotADirectoryError
        If the path is not a directory.
    """
    path = path.resolve()

    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {path}")

    result = AuditResult(project_path=path)

    # Detect tooling
    pkg_manager, _pkg_info = detect_package_manager(path)
    linter, _linter_info = detect_linter(path)
    formatter, _formatter_info = detect_formatter(path)
    import_sorter, _sorter_info = detect_import_sorter(path)
    type_checker, _tc_info = detect_type_checker(path)
    has_pre_commit = detect_pre_commit(path)
    ci_system, _ci_info = detect_ci(path)

    # Record detected tools
    if pkg_manager:
        result.tooling_detected["package_manager"] = pkg_manager
    if linter:
        result.tooling_detected["linter"] = linter
    if formatter:
        result.tooling_detected["formatter"] = formatter
    if import_sorter:
        result.tooling_detected["import_sorter"] = import_sorter
    if type_checker:
        result.tooling_detected["type_checker"] = type_checker
    if has_pre_commit:
        result.tooling_detected["pre_commit"] = "configured"
    if ci_system:
        result.tooling_detected["ci"] = ci_system

    # Analyze type coverage
    type_coverage, typed_functions, total_functions = analyze_type_coverage(path)
    result.tooling_detected["type_coverage"] = f"{type_coverage:.0f}%"

    # Check if already using modern tooling
    is_modern = (
        pkg_manager == "uv"
        and linter == "ruff"
        and type_checker in ("basedpyright", "pyright")
        and has_pre_commit
    )

    if is_modern:
        result.tooling_detected["status"] = "modern"
    else:
        # Generate recommendations
        _generate_tooling_recommendations(
            result,
            pkg_manager,
            linter,
            formatter,
            import_sorter,
            type_checker,
            has_pre_commit,
            ci_system,
        )

        _generate_code_quality_recommendations(
            result,
            type_coverage,
            typed_functions,
            total_functions,
        )

    # Calculate score
    result.score = _calculate_score(result)

    return result
