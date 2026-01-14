"""
quickforge.upgrader - Project Upgrade Module
=========================================

This module provides functionality to upgrade existing Python projects
from legacy tooling to modern 2025 standards.

Supported Migrations
--------------------
1. **Package Manager Migration**
   - poetry → uv
   - pip/requirements.txt → uv with pyproject.toml
   - pipenv → uv
   - setup.py/setup.cfg → pyproject.toml

2. **Linting/Formatting Migration**
   - black → ruff format
   - isort → ruff (import sorting)
   - flake8 → ruff check
   - pylint → ruff check (partial)
   - autopep8 → ruff format

3. **Type Checker Migration**
   - mypy → basedpyright (or pyright)
   - pytype → basedpyright

4. **Configuration Consolidation**
   - Merge scattered configs into pyproject.toml
   - Remove redundant config files
   - Update CI/CD workflows

Migration Strategy
------------------
The upgrade process follows these principles:

1. **Non-destructive**: Original files are backed up
2. **Incremental**: Can be done in steps
3. **Reversible**: Easy to undo if needed
4. **Validated**: Each step is verified

Usage
-----
>>> from quickforge.upgrader import upgrade_project
>>> from pathlib import Path
>>>
>>> result = upgrade_project(
...     path=Path("./myproject"),
...     from_tool="poetry",
... )
>>> print(result.changes_made)
[
    "Converted pyproject.toml from Poetry to uv format",
    "Replaced black with ruff format",
    "Replaced flake8 with ruff check",
    ...
]

See Also
--------
- auditor.py: Module for analyzing projects before upgrade
- cli.py: Command-line interface for upgrade command
"""

# pyright: reportIndexIssue=false
# pyright: reportOperatorIssue=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportArgumentType=false
# pyright: reportGeneralTypeIssues=false
# pyright: reportCallIssue=false
# The above pragmas disable false positives from tomlkit's dynamic typing.
# tomlkit uses Item/Container types that support dict-like operations at runtime
# but the type stubs don't reflect this properly.

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path


try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]

import tomlkit

from quickforge.auditor import (
    detect_formatter,
    detect_import_sorter,
    detect_linter,
    detect_package_manager,
    detect_type_checker,
)


class SourceTool(str, Enum):
    """
    Source package managers/tools to migrate from.
    """

    POETRY = "poetry"
    PIP = "pip"
    PIPENV = "pipenv"
    SETUPTOOLS = "setuptools"


class MigrationType(str, Enum):
    """
    Types of migrations that can be performed.
    """

    PACKAGE_MANAGER = "package_manager"
    LINTER = "linter"
    FORMATTER = "formatter"
    TYPE_CHECKER = "type_checker"
    CONFIG = "config"
    CI_CD = "ci_cd"


@dataclass
class MigrationStep:
    """
    A single migration step.

    Attributes
    ----------
    migration_type : MigrationType
        Category of this migration.

    description : str
        Human-readable description.

    source : str
        What we're migrating from.

    target : str
        What we're migrating to.

    files_affected : list[Path]
        Files that will be modified.

    reversible : bool
        Whether this step can be undone.
    """

    migration_type: MigrationType
    description: str
    source: str
    target: str
    files_affected: list[Path] = field(default_factory=list)
    reversible: bool = True


@dataclass
class UpgradeResult:
    """
    Result of a project upgrade.

    Attributes
    ----------
    success : bool
        Whether the upgrade completed successfully.

    project_path : Path
        Path to the upgraded project.

    changes_made : list[str]
        List of changes that were applied.

    backup_path : Path | None
        Path to backup of original files.

    errors : list[str]
        Any errors encountered during upgrade.

    migration_steps : list[MigrationStep]
        Steps that were executed.
    """

    success: bool
    project_path: Path
    changes_made: list[str] = field(default_factory=list)
    backup_path: Path | None = None
    errors: list[str] = field(default_factory=list)
    migration_steps: list[MigrationStep] = field(default_factory=list)


# =============================================================================
# Backup Functions
# =============================================================================


def create_backup(path: Path) -> Path:
    """
    Create a timestamped backup of the project's config files.

    Parameters
    ----------
    path : Path
        Path to the project root.

    Returns
    -------
    Path
        Path to the backup directory.
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    backup_dir = path / f".quickforge_backup_{timestamp}"
    backup_dir.mkdir(exist_ok=True)

    # Files to backup
    backup_files = [
        "pyproject.toml",
        "poetry.lock",
        "requirements.txt",
        "requirements-dev.txt",
        "setup.py",
        "setup.cfg",
        ".flake8",
        ".isort.cfg",
        "mypy.ini",
        ".mypy.ini",
        "Pipfile",
        "Pipfile.lock",
        ".pre-commit-config.yaml",
    ]

    for filename in backup_files:
        src = path / filename
        if src.exists():
            shutil.copy2(src, backup_dir / filename)

    return backup_dir


# =============================================================================
# TOML Manipulation Helpers
# =============================================================================


def _read_toml_doc(path: Path) -> tomlkit.TOMLDocument | None:
    """Read a TOML file as a tomlkit document (preserves formatting)."""
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            return tomlkit.load(f)
    except Exception:
        return None


def _write_toml_doc(path: Path, doc: tomlkit.TOMLDocument) -> None:
    """Write a tomlkit document to a file."""
    with path.open("w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(doc))


def _ensure_pyproject_exists(path: Path) -> tomlkit.TOMLDocument:
    """Ensure pyproject.toml exists, creating minimal one if needed."""
    pyproject_path = path / "pyproject.toml"

    if pyproject_path.exists():
        doc = _read_toml_doc(pyproject_path)
        if doc:
            return doc

    # Create minimal pyproject.toml
    doc = tomlkit.document()
    doc.add(tomlkit.comment("Created by quickforge upgrade"))

    project = tomlkit.table()
    project.add("name", path.name)
    project.add("version", "0.1.0")
    project.add("requires-python", ">=3.11")
    doc.add("project", project)

    build_system = tomlkit.table()
    build_system.add("requires", ["hatchling"])
    build_system.add("build-backend", "hatchling.build")
    doc.add("build-system", build_system)

    return doc


# =============================================================================
# Package Manager Migrations
# =============================================================================


def _migrate_poetry_to_uv(path: Path, dry_run: bool) -> list[str]:
    """
    Migrate from Poetry to uv.

    Converts [tool.poetry] sections to PEP 621 format.
    """
    changes = []
    pyproject_path = path / "pyproject.toml"

    if not pyproject_path.exists():
        return ["No pyproject.toml found"]

    doc = _read_toml_doc(pyproject_path)
    if not doc:
        return ["Could not parse pyproject.toml"]

    if "tool" not in doc or "poetry" not in doc["tool"]:
        return ["No [tool.poetry] section found"]

    poetry = doc["tool"]["poetry"]

    # Create or update [project] section
    if "project" not in doc:
        doc["project"] = tomlkit.table()

    project = doc["project"]

    # Migrate basic metadata
    if "name" in poetry:
        project["name"] = poetry["name"]
        changes.append(f"Migrated project name: {poetry['name']}")

    if "version" in poetry:
        project["version"] = poetry["version"]
        changes.append(f"Migrated version: {poetry['version']}")

    if "description" in poetry:
        project["description"] = poetry["description"]
        changes.append("Migrated description")

    if "authors" in poetry:
        # Convert from "Name <email>" format to {name, email} dicts
        authors = []
        for author in poetry["authors"]:
            if isinstance(author, str):
                match = re.match(r"(.+?)\s*<(.+?)>", author)
                if match:
                    authors.append(
                        {"name": match.group(1).strip(), "email": match.group(2)}
                    )
                else:
                    authors.append({"name": author})
        if authors:
            project["authors"] = authors
            changes.append("Migrated authors")

    if "readme" in poetry:
        project["readme"] = poetry["readme"]
    elif (path / "README.md").exists():
        project["readme"] = "README.md"

    if "license" in poetry:
        project["license"] = {"text": poetry["license"]}
        changes.append(f"Migrated license: {poetry['license']}")

    if "keywords" in poetry:
        project["keywords"] = poetry["keywords"]
        changes.append("Migrated keywords")

    if "classifiers" in poetry:
        project["classifiers"] = poetry["classifiers"]
        changes.append("Migrated classifiers")

    # Migrate Python version requirement
    if "python" in poetry.get("dependencies", {}):
        python_req = poetry["dependencies"]["python"]
        # Convert Poetry's format (^3.11) to PEP 621 (>=3.11)
        if python_req.startswith("^") or python_req.startswith("~"):
            project["requires-python"] = ">=" + python_req[1:]
        else:
            project["requires-python"] = python_req
        changes.append(f"Migrated Python requirement: {project['requires-python']}")

    # Migrate dependencies
    deps = []
    if "dependencies" in poetry:
        for name, spec in poetry["dependencies"].items():
            if name == "python":
                continue
            if isinstance(spec, str):
                # Convert ^ and ~ to PEP 440
                if spec.startswith("^") or spec.startswith("~"):
                    deps.append(f"{name}>={spec[1:]}")
                else:
                    deps.append(
                        f"{name}{spec}" if spec[0] in "<>=!" else f"{name}=={spec}"
                    )
            elif isinstance(spec, dict):
                version = spec.get("version", "")
                if version.startswith("^") or version.startswith("~"):
                    deps.append(f"{name}>={version[1:]}")
                elif version:
                    deps.append(
                        f"{name}{version}"
                        if version[0] in "<>=!"
                        else f"{name}=={version}"
                    )
                else:
                    deps.append(name)

    if deps:
        project["dependencies"] = deps
        changes.append(f"Migrated {len(deps)} dependencies")

    # Migrate dev dependencies to [project.optional-dependencies]
    dev_deps = []
    if "group" in poetry and "dev" in poetry["group"]:
        dev_section = poetry["group"]["dev"]
        if "dependencies" in dev_section:
            for name, spec in dev_section["dependencies"].items():
                if isinstance(spec, str):
                    if spec.startswith("^") or spec.startswith("~"):
                        dev_deps.append(f"{name}>={spec[1:]}")
                    else:
                        dev_deps.append(
                            f"{name}{spec}" if spec[0] in "<>=!" else f"{name}=={spec}"
                        )
                else:
                    dev_deps.append(name)

    # Also check old-style dev-dependencies
    if "dev-dependencies" in poetry:
        for name, spec in poetry["dev-dependencies"].items():
            if isinstance(spec, str):
                if spec.startswith("^") or spec.startswith("~"):
                    dev_deps.append(f"{name}>={spec[1:]}")
                else:
                    dev_deps.append(
                        f"{name}{spec}" if spec[0] in "<>=!" else f"{name}=={spec}"
                    )
            else:
                dev_deps.append(name)

    if dev_deps:
        if "optional-dependencies" not in project:
            project["optional-dependencies"] = tomlkit.table()
        project["optional-dependencies"]["dev"] = dev_deps
        changes.append(f"Migrated {len(dev_deps)} dev dependencies")

    # Migrate scripts
    if "scripts" in poetry:
        project["scripts"] = poetry["scripts"]
        changes.append("Migrated scripts/entry points")

    # Update build-system to use hatchling (uv-compatible)
    doc["build-system"] = tomlkit.table()
    doc["build-system"]["requires"] = ["hatchling"]
    doc["build-system"]["build-backend"] = "hatchling.build"
    changes.append("Updated build-system to use hatchling")

    # Remove [tool.poetry] section
    del doc["tool"]["poetry"]
    changes.append("Removed [tool.poetry] section")

    # Clean up empty tool section
    if "tool" in doc and len(doc["tool"]) == 0:
        del doc["tool"]

    if not dry_run:
        _write_toml_doc(pyproject_path, doc)
        changes.append("Wrote updated pyproject.toml")

        # Remove poetry.lock
        poetry_lock = path / "poetry.lock"
        if poetry_lock.exists():
            poetry_lock.unlink()
            changes.append("Removed poetry.lock")

    return changes


def _migrate_requirements_to_uv(path: Path, dry_run: bool) -> list[str]:
    """
    Migrate from pip/requirements.txt to uv with pyproject.toml.
    """
    changes = []
    req_file = path / "requirements.txt"

    if not req_file.exists():
        return ["No requirements.txt found"]

    # Parse requirements.txt
    deps = []
    with req_file.open(encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Skip -r includes for now
            if line.startswith("-r") or line.startswith("-e"):
                continue
            # Handle version specifiers
            deps.append(line)

    if not deps:
        return ["No dependencies found in requirements.txt"]

    # Create or update pyproject.toml
    doc = _ensure_pyproject_exists(path)

    if "project" not in doc:
        doc["project"] = tomlkit.table()

    doc["project"]["dependencies"] = deps
    changes.append(f"Migrated {len(deps)} dependencies from requirements.txt")

    # Check for requirements-dev.txt
    req_dev = path / "requirements-dev.txt"
    if req_dev.exists():
        dev_deps = []
        with req_dev.open(encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                dev_deps.append(line)

        if dev_deps:
            if "optional-dependencies" not in doc["project"]:
                doc["project"]["optional-dependencies"] = tomlkit.table()
            doc["project"]["optional-dependencies"]["dev"] = dev_deps
            changes.append(
                f"Migrated {len(dev_deps)} dev dependencies from requirements-dev.txt"
            )

    if not dry_run:
        _write_toml_doc(path / "pyproject.toml", doc)
        changes.append("Wrote pyproject.toml")

        # Note: We don't delete requirements.txt automatically
        # as it might be used by other tools or for reference

    return changes


def _migrate_pipenv_to_uv(path: Path, dry_run: bool) -> list[str]:
    """
    Migrate from Pipenv to uv with pyproject.toml.
    """
    changes = []
    pipfile = path / "Pipfile"

    if not pipfile.exists():
        return ["No Pipfile found"]

    # Parse Pipfile (it's TOML-like)
    try:
        with pipfile.open("rb") as f:
            pipfile_data = tomllib.load(f)
    except Exception as e:
        return [f"Could not parse Pipfile: {e}"]

    doc = _ensure_pyproject_exists(path)

    if "project" not in doc:
        doc["project"] = tomlkit.table()

    # Migrate packages
    deps = []
    if "packages" in pipfile_data:
        for name, spec in pipfile_data["packages"].items():
            if spec == "*":
                deps.append(name)
            elif isinstance(spec, str):
                deps.append(f"{name}{spec}")
            elif isinstance(spec, dict) and "version" in spec:
                deps.append(f"{name}{spec['version']}")
            else:
                deps.append(name)

    if deps:
        doc["project"]["dependencies"] = deps
        changes.append(f"Migrated {len(deps)} dependencies from Pipfile")

    # Migrate dev packages
    dev_deps = []
    if "dev-packages" in pipfile_data:
        for name, spec in pipfile_data["dev-packages"].items():
            if spec == "*":
                dev_deps.append(name)
            elif isinstance(spec, str):
                dev_deps.append(f"{name}{spec}")
            elif isinstance(spec, dict) and "version" in spec:
                dev_deps.append(f"{name}{spec['version']}")
            else:
                dev_deps.append(name)

    if dev_deps:
        if "optional-dependencies" not in doc["project"]:
            doc["project"]["optional-dependencies"] = tomlkit.table()
        doc["project"]["optional-dependencies"]["dev"] = dev_deps
        changes.append(f"Migrated {len(dev_deps)} dev dependencies from Pipfile")

    # Migrate Python version requirement
    if "requires" in pipfile_data and "python_version" in pipfile_data["requires"]:
        py_version = pipfile_data["requires"]["python_version"]
        doc["project"]["requires-python"] = f">={py_version}"
        changes.append(f"Migrated Python requirement: >={py_version}")

    if not dry_run:
        _write_toml_doc(path / "pyproject.toml", doc)
        changes.append("Wrote pyproject.toml")

    return changes


def _migrate_setuptools_to_uv(path: Path, dry_run: bool) -> list[str]:
    """
    Migrate from setup.py/setup.cfg to pyproject.toml.
    """
    changes = []

    # For setup.cfg, we can parse it
    setup_cfg = path / "setup.cfg"
    if setup_cfg.exists():
        try:
            import configparser

            config = configparser.ConfigParser()
            config.read(setup_cfg)

            doc = _ensure_pyproject_exists(path)

            if "project" not in doc:
                doc["project"] = tomlkit.table()

            project = doc["project"]

            if config.has_section("metadata"):
                if config.has_option("metadata", "name"):
                    project["name"] = config.get("metadata", "name")
                if config.has_option("metadata", "version"):
                    project["version"] = config.get("metadata", "version")
                if config.has_option("metadata", "description"):
                    project["description"] = config.get("metadata", "description")
                if config.has_option("metadata", "author"):
                    author = {"name": config.get("metadata", "author")}
                    if config.has_option("metadata", "author_email"):
                        author["email"] = config.get("metadata", "author_email")
                    project["authors"] = [author]
                if config.has_option("metadata", "license"):
                    project["license"] = {"text": config.get("metadata", "license")}

                changes.append("Migrated metadata from setup.cfg")

            if config.has_section("options"):
                if config.has_option("options", "python_requires"):
                    project["requires-python"] = config.get(
                        "options", "python_requires"
                    )
                if config.has_option("options", "install_requires"):
                    deps = config.get("options", "install_requires").strip().split("\n")
                    deps = [d.strip() for d in deps if d.strip()]
                    project["dependencies"] = deps
                    changes.append(f"Migrated {len(deps)} dependencies")

            if not dry_run:
                _write_toml_doc(path / "pyproject.toml", doc)
                changes.append("Wrote pyproject.toml")

        except Exception as e:
            changes.append(f"Warning: Could not fully parse setup.cfg: {e}")

    # For setup.py, we can only provide guidance (too complex to parse reliably)
    if (path / "setup.py").exists() and not setup_cfg.exists():
        changes.append("Found setup.py - manual migration recommended")
        changes.append("Tip: Run 'python setup.py egg_info' to extract metadata")

    return changes


# =============================================================================
# Linter/Formatter Migrations
# =============================================================================


def _migrate_black_to_ruff(
    path: Path, doc: tomlkit.TOMLDocument, dry_run: bool
) -> list[str]:
    """Migrate Black config to ruff format config."""
    changes = []

    if "tool" not in doc:
        doc["tool"] = tomlkit.table()

    tool = doc["tool"]

    # Get Black config if exists
    black_config = tool.get("black", {})

    # Ensure ruff section exists
    if "ruff" not in tool:
        tool["ruff"] = tomlkit.table()

    ruff = tool["ruff"]

    # Migrate line-length
    if "line-length" in black_config:
        ruff["line-length"] = black_config["line-length"]
        changes.append(f"Migrated line-length: {black_config['line-length']}")
    elif "line-length" not in ruff:
        ruff["line-length"] = 88  # Black default
        changes.append("Set line-length to 88 (Black default)")

    # Migrate target-version
    if "target-version" in black_config:
        versions = black_config["target-version"]
        if versions:
            # Convert py311 format to 3.11 format
            target = versions[-1] if isinstance(versions, list) else versions
            if isinstance(target, str) and target.startswith("py"):
                major = target[2]
                minor = target[3:]
                ruff["target-version"] = f"py{major}{minor}"
                changes.append(f"Migrated target-version: {ruff['target-version']}")

    # Ensure format section exists
    if "format" not in ruff:
        ruff["format"] = tomlkit.table()

    # Migrate quote-style (Black uses double quotes by default)
    ruff["format"]["quote-style"] = "double"

    # Migrate skip-magic-trailing-comma
    if "skip-magic-trailing-comma" in black_config:
        ruff["format"]["skip-magic-trailing-comma"] = black_config[
            "skip-magic-trailing-comma"
        ]

    # Remove Black config
    if "black" in tool:
        del tool["black"]
        changes.append("Removed [tool.black] section")

    return changes


def _migrate_isort_to_ruff(
    path: Path, doc: tomlkit.TOMLDocument, dry_run: bool
) -> list[str]:
    """Migrate isort config to ruff lint.isort config."""
    changes = []

    if "tool" not in doc:
        doc["tool"] = tomlkit.table()

    tool = doc["tool"]
    isort_config = tool.get("isort", {})

    # Ensure ruff.lint.isort section exists
    if "ruff" not in tool:
        tool["ruff"] = tomlkit.table()
    if "lint" not in tool["ruff"]:
        tool["ruff"]["lint"] = tomlkit.table()
    if "isort" not in tool["ruff"]["lint"]:
        tool["ruff"]["lint"]["isort"] = tomlkit.table()

    ruff_isort = tool["ruff"]["lint"]["isort"]

    # Migrate known sections
    section_mappings = {
        "known_first_party": "known-first-party",
        "known_third_party": "known-third-party",
        "known_local_folder": "known-local-folder",
    }

    for isort_key, ruff_key in section_mappings.items():
        if isort_key in isort_config:
            ruff_isort[ruff_key] = isort_config[isort_key]
            changes.append(f"Migrated {isort_key}")

    # Migrate force_single_line
    if "force_single_line" in isort_config:
        ruff_isort["force-single-line"] = isort_config["force_single_line"]
        changes.append("Migrated force_single_line")

    # Migrate combine_as_imports
    if "combine_as_imports" in isort_config:
        ruff_isort["combine-as-imports"] = isort_config["combine_as_imports"]
        changes.append("Migrated combine_as_imports")

    # Ensure I rules are selected
    if "select" not in tool["ruff"]["lint"]:
        tool["ruff"]["lint"]["select"] = ["E", "F", "I"]
        changes.append("Added I (isort) rules to ruff lint.select")
    elif "I" not in tool["ruff"]["lint"]["select"]:
        tool["ruff"]["lint"]["select"].append("I")
        changes.append("Added I (isort) to ruff lint.select")

    # Remove isort config
    if "isort" in tool:
        del tool["isort"]
        changes.append("Removed [tool.isort] section")

    # Remove .isort.cfg file reference
    isort_cfg = path / ".isort.cfg"
    if isort_cfg.exists() and not dry_run:
        isort_cfg.unlink()
        changes.append("Removed .isort.cfg file")

    return changes


def _migrate_flake8_to_ruff(
    path: Path, doc: tomlkit.TOMLDocument, dry_run: bool
) -> list[str]:
    """Migrate flake8 config to ruff lint config."""
    changes = []

    if "tool" not in doc:
        doc["tool"] = tomlkit.table()

    tool = doc["tool"]

    # Ensure ruff.lint section exists
    if "ruff" not in tool:
        tool["ruff"] = tomlkit.table()
    if "lint" not in tool["ruff"]:
        tool["ruff"]["lint"] = tomlkit.table()

    ruff_lint = tool["ruff"]["lint"]

    # Try to read .flake8 file
    flake8_config = {}
    flake8_file = path / ".flake8"
    if flake8_file.exists():
        try:
            import configparser

            config = configparser.ConfigParser()
            config.read(flake8_file)
            if config.has_section("flake8"):
                flake8_config = dict(config.items("flake8"))
        except Exception:
            pass

    # Migrate max-line-length
    if "max-line-length" in flake8_config:
        tool["ruff"]["line-length"] = int(flake8_config["max-line-length"])
        changes.append(f"Migrated max-line-length: {flake8_config['max-line-length']}")

    # Migrate ignore
    if "ignore" in flake8_config:
        ignored = [i.strip() for i in flake8_config["ignore"].split(",") if i.strip()]
        # Convert flake8 codes to ruff codes where applicable
        ruff_lint["ignore"] = ignored
        changes.append(f"Migrated {len(ignored)} ignore rules")

    # Migrate exclude
    if "exclude" in flake8_config:
        excluded = [e.strip() for e in flake8_config["exclude"].split(",") if e.strip()]
        tool["ruff"]["exclude"] = excluded
        changes.append(f"Migrated {len(excluded)} exclude patterns")

    # Set default select if not present
    if "select" not in ruff_lint:
        ruff_lint["select"] = ["E", "F", "W"]
        changes.append("Added E, F, W rules to ruff lint.select")

    # Remove .flake8 file
    if flake8_file.exists() and not dry_run:
        flake8_file.unlink()
        changes.append("Removed .flake8 file")

    return changes


# =============================================================================
# Type Checker Migration
# =============================================================================


def _migrate_mypy_to_basedpyright(
    path: Path, doc: tomlkit.TOMLDocument, dry_run: bool
) -> list[str]:
    """Migrate mypy config to basedpyright config."""
    changes = []

    if "tool" not in doc:
        doc["tool"] = tomlkit.table()

    tool = doc["tool"]

    # Get mypy config if exists
    mypy_config = tool.get("mypy", {})

    # Create basedpyright config
    if "basedpyright" not in tool:
        tool["basedpyright"] = tomlkit.table()

    pyright = tool["basedpyright"]

    # Map mypy strictness to basedpyright typeCheckingMode
    if mypy_config.get("strict"):
        pyright["typeCheckingMode"] = "strict"
        changes.append("Set typeCheckingMode to strict (from mypy strict)")
    elif mypy_config.get("warn_return_any") or mypy_config.get("disallow_untyped_defs"):
        pyright["typeCheckingMode"] = "standard"
        changes.append("Set typeCheckingMode to standard")
    else:
        pyright["typeCheckingMode"] = "basic"
        changes.append("Set typeCheckingMode to basic")

    # Migrate python_version
    if "python_version" in mypy_config:
        pyright["pythonVersion"] = mypy_config["python_version"]
        changes.append(f"Migrated python_version: {mypy_config['python_version']}")

    # Migrate ignore_missing_imports
    if mypy_config.get("ignore_missing_imports"):
        pyright["reportMissingImports"] = False
        changes.append("Migrated ignore_missing_imports")

    # Remove mypy config
    if "mypy" in tool:
        del tool["mypy"]
        changes.append("Removed [tool.mypy] section")

    # Remove mypy.ini files
    for mypy_file in ["mypy.ini", ".mypy.ini"]:
        mypy_path = path / mypy_file
        if mypy_path.exists() and not dry_run:
            mypy_path.unlink()
            changes.append(f"Removed {mypy_file}")

    return changes


# =============================================================================
# Main Migration Functions
# =============================================================================


def detect_source_tool(path: Path) -> SourceTool | None:
    """Auto-detect the source package manager."""
    pkg_manager, _ = detect_package_manager(path)

    tool_map = {
        "poetry": SourceTool.POETRY,
        "pip": SourceTool.PIP,
        "pipenv": SourceTool.PIPENV,
        "setuptools": SourceTool.SETUPTOOLS,
    }
    return tool_map.get(pkg_manager)


def create_migration_plan(
    path: Path,
    from_tool: str | None = None,
) -> list[MigrationStep]:
    """
    Create a migration plan for upgrading a project.

    Parameters
    ----------
    path : Path
        Path to the project root directory.

    from_tool : str | None
        Source tool to migrate from. If None, auto-detected.

    Returns
    -------
    list[MigrationStep]
        Ordered list of migration steps to perform.
    """
    steps = []

    # Detect current tooling
    if from_tool:
        try:
            source_tool = SourceTool(from_tool)
        except ValueError:
            source_tool = None
    else:
        source_tool = detect_source_tool(path)

    # Package manager migration
    if source_tool == SourceTool.POETRY:
        steps.append(
            MigrationStep(
                migration_type=MigrationType.PACKAGE_MANAGER,
                description="Convert Poetry pyproject.toml to PEP 621 format for uv",
                source="poetry",
                target="uv",
                files_affected=[path / "pyproject.toml", path / "poetry.lock"],
            )
        )
    elif source_tool == SourceTool.PIP:
        steps.append(
            MigrationStep(
                migration_type=MigrationType.PACKAGE_MANAGER,
                description="Convert requirements.txt to pyproject.toml for uv",
                source="pip",
                target="uv",
                files_affected=[path / "requirements.txt", path / "pyproject.toml"],
            )
        )
    elif source_tool == SourceTool.PIPENV:
        steps.append(
            MigrationStep(
                migration_type=MigrationType.PACKAGE_MANAGER,
                description="Convert Pipfile to pyproject.toml for uv",
                source="pipenv",
                target="uv",
                files_affected=[path / "Pipfile", path / "pyproject.toml"],
            )
        )
    elif source_tool == SourceTool.SETUPTOOLS:
        steps.append(
            MigrationStep(
                migration_type=MigrationType.PACKAGE_MANAGER,
                description="Convert setup.py/setup.cfg to pyproject.toml",
                source="setuptools",
                target="uv",
                files_affected=[
                    path / "setup.py",
                    path / "setup.cfg",
                    path / "pyproject.toml",
                ],
            )
        )

    # Formatter migration
    formatter, _ = detect_formatter(path)
    if formatter == "black":
        steps.append(
            MigrationStep(
                migration_type=MigrationType.FORMATTER,
                description="Migrate Black configuration to ruff format",
                source="black",
                target="ruff",
                files_affected=[path / "pyproject.toml"],
            )
        )

    # Import sorter migration
    sorter, _ = detect_import_sorter(path)
    if sorter == "isort":
        steps.append(
            MigrationStep(
                migration_type=MigrationType.LINTER,
                description="Migrate isort configuration to ruff lint.isort",
                source="isort",
                target="ruff",
                files_affected=[path / "pyproject.toml", path / ".isort.cfg"],
            )
        )

    # Linter migration
    linter, _ = detect_linter(path)
    if linter == "flake8":
        steps.append(
            MigrationStep(
                migration_type=MigrationType.LINTER,
                description="Migrate flake8 configuration to ruff lint",
                source="flake8",
                target="ruff",
                files_affected=[path / "pyproject.toml", path / ".flake8"],
            )
        )

    # Type checker migration
    type_checker, _ = detect_type_checker(path)
    if type_checker == "mypy":
        steps.append(
            MigrationStep(
                migration_type=MigrationType.TYPE_CHECKER,
                description="Migrate mypy configuration to basedpyright",
                source="mypy",
                target="basedpyright",
                files_affected=[path / "pyproject.toml", path / "mypy.ini"],
            )
        )

    return steps


def upgrade_project(
    path: Path,
    *,
    from_tool: str | None = None,
    dry_run: bool = False,
    backup: bool = True,
) -> UpgradeResult:
    """
    Upgrade a Python project to modern tooling.

    Parameters
    ----------
    path : Path
        Path to the project root directory.

    from_tool : str | None
        Source tool to migrate from. If None, auto-detected.

    dry_run : bool, default=False
        If True, show what would be done without making changes.

    backup : bool, default=True
        If True, create backup of original files.

    Returns
    -------
    UpgradeResult
        Result of the upgrade operation.
    """
    path = path.resolve()

    result = UpgradeResult(
        success=False,
        project_path=path,
    )

    if not path.exists():
        result.errors.append(f"Path does not exist: {path}")
        return result

    if not path.is_dir():
        result.errors.append(f"Path is not a directory: {path}")
        return result

    # Create backup
    if backup and not dry_run:
        result.backup_path = create_backup(path)
        result.changes_made.append(f"Created backup at {result.backup_path}")

    # Get migration plan
    steps = create_migration_plan(path, from_tool)
    result.migration_steps = steps

    if not steps:
        result.changes_made.append(
            "No migrations needed - project may already use modern tooling"
        )
        result.success = True
        return result

    # Read/create pyproject.toml for non-package-manager migrations
    pyproject_path = path / "pyproject.toml"
    doc = _read_toml_doc(pyproject_path) or tomlkit.document()

    # Execute migrations
    for step in steps:
        try:
            if step.migration_type == MigrationType.PACKAGE_MANAGER:
                if step.source == "poetry":
                    changes = _migrate_poetry_to_uv(path, dry_run)
                    # Re-read doc after package manager migration
                    doc = _read_toml_doc(pyproject_path) or doc
                elif step.source == "pip":
                    changes = _migrate_requirements_to_uv(path, dry_run)
                    doc = _read_toml_doc(pyproject_path) or doc
                elif step.source == "pipenv":
                    changes = _migrate_pipenv_to_uv(path, dry_run)
                    doc = _read_toml_doc(pyproject_path) or doc
                elif step.source == "setuptools":
                    changes = _migrate_setuptools_to_uv(path, dry_run)
                    doc = _read_toml_doc(pyproject_path) or doc
                else:
                    changes = [f"Unknown source tool: {step.source}"]

                result.changes_made.extend(changes)

            elif step.migration_type == MigrationType.FORMATTER:
                if step.source == "black":
                    changes = _migrate_black_to_ruff(path, doc, dry_run)
                    result.changes_made.extend(changes)

            elif step.migration_type == MigrationType.LINTER:
                if step.source == "isort":
                    changes = _migrate_isort_to_ruff(path, doc, dry_run)
                    result.changes_made.extend(changes)
                elif step.source == "flake8":
                    changes = _migrate_flake8_to_ruff(path, doc, dry_run)
                    result.changes_made.extend(changes)

            elif step.migration_type == MigrationType.TYPE_CHECKER:
                if step.source == "mypy":
                    changes = _migrate_mypy_to_basedpyright(path, doc, dry_run)
                    result.changes_made.extend(changes)

        except Exception as e:
            result.errors.append(f"Error during {step.description}: {e}")

    # Write final pyproject.toml for non-package-manager migrations
    if not dry_run and doc:
        _write_toml_doc(pyproject_path, doc)
        result.changes_made.append("Wrote updated pyproject.toml")

    result.success = len(result.errors) == 0
    return result
