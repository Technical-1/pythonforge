"""Tests for quickforge.upgrader module."""

from pathlib import Path

from quickforge.upgrader import (
    MigrationStep,
    MigrationType,
    SourceTool,
    UpgradeResult,
    create_backup,
    create_migration_plan,
    detect_source_tool,
    upgrade_project,
)


class TestDetectSourceTool:
    """Tests for detect_source_tool function."""

    def test_detect_poetry(self, tmp_path: Path) -> None:
        """Test detection of Poetry."""
        (tmp_path / "poetry.lock").touch()
        result = detect_source_tool(tmp_path)
        assert result == SourceTool.POETRY

    def test_detect_pip(self, tmp_path: Path) -> None:
        """Test detection of pip."""
        (tmp_path / "requirements.txt").write_text("requests>=2.0")
        result = detect_source_tool(tmp_path)
        assert result == SourceTool.PIP

    def test_detect_pipenv(self, tmp_path: Path) -> None:
        """Test detection of Pipenv."""
        (tmp_path / "Pipfile").touch()
        result = detect_source_tool(tmp_path)
        assert result == SourceTool.PIPENV

    def test_detect_setuptools(self, tmp_path: Path) -> None:
        """Test detection of setuptools."""
        (tmp_path / "setup.py").write_text("from setuptools import setup")
        result = detect_source_tool(tmp_path)
        assert result == SourceTool.SETUPTOOLS

    def test_detect_none(self, tmp_path: Path) -> None:
        """Test when no tool is detected."""
        result = detect_source_tool(tmp_path)
        assert result is None


class TestCreateBackup:
    """Tests for create_backup function."""

    def test_creates_backup_directory(self, tmp_path: Path) -> None:
        """Test that backup directory is created."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        (tmp_path / "requirements.txt").write_text("requests>=2.0")

        backup_path = create_backup(tmp_path)

        assert backup_path.exists()
        assert backup_path.name.startswith(".quickforge_backup_")
        assert (backup_path / "pyproject.toml").exists()
        assert (backup_path / "requirements.txt").exists()

    def test_backup_preserves_content(self, tmp_path: Path) -> None:
        """Test that backup preserves file content."""
        original_content = "[project]\nname = 'test'"
        (tmp_path / "pyproject.toml").write_text(original_content)

        backup_path = create_backup(tmp_path)

        assert (backup_path / "pyproject.toml").read_text() == original_content


class TestCreateMigrationPlan:
    """Tests for create_migration_plan function."""

    def test_poetry_migration_plan(self, tmp_path: Path) -> None:
        """Test migration plan for Poetry project."""
        (tmp_path / "poetry.lock").touch()
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.poetry]
name = "test"
version = "0.1.0"

[tool.black]
line-length = 88

[tool.mypy]
strict = true
""")

        steps = create_migration_plan(tmp_path)

        # Should have steps for: package manager, formatter, type checker
        assert len(steps) >= 1
        types = [s.migration_type for s in steps]
        assert MigrationType.PACKAGE_MANAGER in types

    def test_pip_migration_plan(self, tmp_path: Path) -> None:
        """Test migration plan for pip project."""
        (tmp_path / "requirements.txt").write_text("requests>=2.0")
        (tmp_path / ".flake8").write_text("[flake8]\nmax-line-length = 88")

        steps = create_migration_plan(tmp_path)

        assert len(steps) >= 1
        types = [s.migration_type for s in steps]
        assert MigrationType.PACKAGE_MANAGER in types
        assert MigrationType.LINTER in types

    def test_empty_plan_for_modern_project(self, tmp_path: Path) -> None:
        """Test that modern project has no migrations."""
        (tmp_path / "uv.lock").touch()
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[tool.ruff]
line-length = 88

[tool.basedpyright]
typeCheckingMode = "standard"
""")

        steps = create_migration_plan(tmp_path)

        # Should have no package manager migration (already using uv)
        pkg_steps = [
            s for s in steps if s.migration_type == MigrationType.PACKAGE_MANAGER
        ]
        assert len(pkg_steps) == 0


class TestUpgradeProject:
    """Tests for upgrade_project function."""

    def test_upgrade_poetry_to_uv(self, tmp_path: Path) -> None:
        """Test upgrading from Poetry to uv."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.poetry]
name = "testproject"
version = "0.1.0"
description = "A test project"
authors = ["Test Author <test@example.com>"]

[tool.poetry.dependencies]
python = "^3.11"
requests = "^2.28"
flask = ">=2.0"
click = "~8.0"
pydantic = {version = "^2.0"}
attrs = {version = ">=23.0"}
simple = "*"

[tool.poetry.group.dev.dependencies]
pytest = "^7.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
""")
        (tmp_path / "poetry.lock").touch()

        result = upgrade_project(tmp_path, backup=True)

        assert result.success
        assert result.backup_path is not None
        assert len(result.changes_made) > 0

        # Check pyproject.toml was updated
        content = pyproject.read_text()
        assert "[project]" in content
        assert "name = " in content
        # Poetry section should be removed
        assert "[tool.poetry]" not in content

    def test_upgrade_requirements_to_uv(self, tmp_path: Path) -> None:
        """Test upgrading from requirements.txt to uv."""
        req = tmp_path / "requirements.txt"
        req.write_text("""
requests>=2.28
flask>=2.0
""")

        result = upgrade_project(tmp_path, backup=True)

        assert result.success

        # Check pyproject.toml was created
        pyproject = tmp_path / "pyproject.toml"
        assert pyproject.exists()
        content = pyproject.read_text()
        assert "requests" in content

    def test_upgrade_requirements_with_dev(self, tmp_path: Path) -> None:
        """Test upgrading from requirements.txt with requirements-dev.txt."""
        req = tmp_path / "requirements.txt"
        req.write_text("requests>=2.28\nflask>=2.0")
        req_dev = tmp_path / "requirements-dev.txt"
        req_dev.write_text("pytest>=7.0\nruff>=0.1.0")

        result = upgrade_project(tmp_path, backup=False)

        assert result.success

        # Check pyproject.toml has both regular and dev dependencies
        pyproject = tmp_path / "pyproject.toml"
        content = pyproject.read_text()
        assert "requests" in content
        assert "pytest" in content

    def test_dry_run_makes_no_changes(self, tmp_path: Path) -> None:
        """Test that dry run doesn't modify files."""
        pyproject = tmp_path / "pyproject.toml"
        original_content = """
[tool.poetry]
name = "test"
version = "0.1.0"
"""
        pyproject.write_text(original_content)
        (tmp_path / "poetry.lock").touch()

        upgrade_project(tmp_path, dry_run=True)

        # File should be unchanged
        assert pyproject.read_text() == original_content
        # poetry.lock should still exist
        assert (tmp_path / "poetry.lock").exists()

    def test_upgrade_black_to_ruff(self, tmp_path: Path) -> None:
        """Test migrating Black config to ruff."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[tool.black]
line-length = 100
target-version = ["py311"]
""")

        result = upgrade_project(tmp_path, backup=False)

        assert result.success
        content = pyproject.read_text()
        assert "[tool.ruff]" in content
        assert "[tool.black]" not in content

    def test_upgrade_mypy_to_basedpyright(self, tmp_path: Path) -> None:
        """Test migrating mypy to basedpyright."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[tool.mypy]
strict = true
python_version = "3.11"
""")

        result = upgrade_project(tmp_path, backup=False)

        assert result.success
        content = pyproject.read_text()
        assert "[tool.basedpyright]" in content
        assert "[tool.mypy]" not in content

    def test_upgrade_mypy_standard_mode(self, tmp_path: Path) -> None:
        """Test migrating mypy with warn_return_any to basedpyright standard."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[tool.mypy]
warn_return_any = true
ignore_missing_imports = true
""")

        result = upgrade_project(tmp_path, backup=False)

        assert result.success
        content = pyproject.read_text()
        assert "[tool.basedpyright]" in content
        assert "standard" in content

    def test_upgrade_mypy_basic_mode(self, tmp_path: Path) -> None:
        """Test migrating basic mypy to basedpyright basic."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[tool.mypy]
python_version = "3.11"
""")

        result = upgrade_project(tmp_path, backup=False)

        assert result.success
        content = pyproject.read_text()
        assert "[tool.basedpyright]" in content
        assert "basic" in content

    def test_upgrade_flake8_to_ruff(self, tmp_path: Path) -> None:
        """Test migrating flake8 to ruff."""
        (tmp_path / ".flake8").write_text("""
[flake8]
max-line-length = 100
ignore = E501,W503
exclude = .git,__pycache__
""")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'")

        result = upgrade_project(tmp_path, backup=False)

        assert result.success
        # .flake8 should be removed
        assert not (tmp_path / ".flake8").exists()
        # ruff config should be in pyproject.toml
        content = pyproject.read_text()
        assert "[tool.ruff]" in content

    def test_upgrade_isort_to_ruff(self, tmp_path: Path) -> None:
        """Test migrating isort to ruff."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[tool.isort]
known_first_party = ["mypackage"]
force_single_line = true
""")

        result = upgrade_project(tmp_path, backup=False)

        assert result.success
        content = pyproject.read_text()
        # isort config should be migrated to ruff.lint.isort
        assert "[tool.ruff.lint.isort]" in content
        # Original isort section should be removed
        assert "[tool.isort]" not in content

    def test_upgrade_pipenv_to_uv(self, tmp_path: Path) -> None:
        """Test upgrading from Pipenv to uv."""
        pipfile = tmp_path / "Pipfile"
        pipfile.write_text("""
[packages]
requests = "*"
flask = ">=2.0"

[dev-packages]
pytest = "*"

[requires]
python_version = "3.11"
""")
        (tmp_path / "Pipfile.lock").touch()

        result = upgrade_project(tmp_path, backup=False)

        assert result.success

        # Check pyproject.toml was created
        pyproject = tmp_path / "pyproject.toml"
        assert pyproject.exists()
        content = pyproject.read_text()
        assert "requests" in content
        assert "flask" in content

    def test_upgrade_setuptools_to_uv(self, tmp_path: Path) -> None:
        """Test upgrading from setup.cfg to uv."""
        setup_cfg = tmp_path / "setup.cfg"
        setup_cfg.write_text("""
[metadata]
name = testproject
version = 0.1.0
description = A test project
author = Test Author
author_email = test@example.com

[options]
packages = find:
python_requires = >=3.11
install_requires =
    requests>=2.0
    flask>=2.0
""")
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()")

        result = upgrade_project(tmp_path, backup=False)

        assert result.success

        # Check pyproject.toml was created/updated
        pyproject = tmp_path / "pyproject.toml"
        assert pyproject.exists()
        content = pyproject.read_text()
        assert "testproject" in content or "requests" in content

    def test_upgrade_nonexistent_path(self, tmp_path: Path) -> None:
        """Test upgrading non-existent path."""
        result = upgrade_project(tmp_path / "nonexistent")
        assert not result.success
        assert len(result.errors) > 0

    def test_no_migrations_needed(self, tmp_path: Path) -> None:
        """Test when project already uses modern tooling."""
        (tmp_path / "uv.lock").touch()
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[tool.ruff]
line-length = 88

[tool.basedpyright]
typeCheckingMode = "standard"
""")

        result = upgrade_project(tmp_path, backup=False)

        assert result.success
        assert (
            "No migrations needed" in result.changes_made[0]
            or len(result.migration_steps) == 0
        )


class TestMigrationStep:
    """Tests for MigrationStep dataclass."""

    def test_creation(self) -> None:
        """Test creating a migration step."""
        step = MigrationStep(
            migration_type=MigrationType.PACKAGE_MANAGER,
            description="Migrate from Poetry to uv",
            source="poetry",
            target="uv",
            files_affected=[Path("pyproject.toml")],
        )

        assert step.migration_type == MigrationType.PACKAGE_MANAGER
        assert step.source == "poetry"
        assert step.target == "uv"
        assert step.reversible is True


class TestUpgradeResult:
    """Tests for UpgradeResult dataclass."""

    def test_creation(self) -> None:
        """Test creating an upgrade result."""
        result = UpgradeResult(
            success=True,
            project_path=Path(),
            changes_made=["Change 1", "Change 2"],
            backup_path=Path(".backup"),
        )

        assert result.success
        assert len(result.changes_made) == 2
        assert result.backup_path is not None
        assert len(result.errors) == 0
