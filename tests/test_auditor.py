"""Tests for pyinit.auditor module."""

from pathlib import Path

import pytest

from pyhatch.auditor import (
    AuditCategory,
    AuditResult,
    Recommendation,
    Severity,
    analyze_type_coverage,
    audit_project,
    detect_ci,
    detect_formatter,
    detect_import_sorter,
    detect_linter,
    detect_package_manager,
    detect_pre_commit,
    detect_type_checker,
)


class TestDetectPackageManager:
    """Tests for detect_package_manager function."""

    def test_detect_uv(self, tmp_path: Path) -> None:
        """Test detection of uv via uv.lock."""
        (tmp_path / "uv.lock").touch()
        manager, info = detect_package_manager(tmp_path)
        assert manager == "uv"
        assert info == {"lock_file": "uv.lock"}

    def test_detect_poetry_lock(self, tmp_path: Path) -> None:
        """Test detection of Poetry via poetry.lock."""
        (tmp_path / "poetry.lock").touch()
        manager, info = detect_package_manager(tmp_path)
        assert manager == "poetry"
        assert info == {"lock_file": "poetry.lock"}

    def test_detect_poetry_pyproject(self, tmp_path: Path) -> None:
        """Test detection of Poetry via pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.poetry]
name = "test"
version = "0.1.0"
""")
        manager, info = detect_package_manager(tmp_path)
        assert manager == "poetry"

    def test_detect_pipenv(self, tmp_path: Path) -> None:
        """Test detection of Pipenv."""
        (tmp_path / "Pipfile").touch()
        manager, info = detect_package_manager(tmp_path)
        assert manager == "pipenv"

    def test_detect_pip(self, tmp_path: Path) -> None:
        """Test detection of pip via requirements.txt."""
        (tmp_path / "requirements.txt").write_text("requests>=2.0")
        manager, info = detect_package_manager(tmp_path)
        assert manager == "pip"
        assert "requirements" in info

    def test_detect_setuptools(self, tmp_path: Path) -> None:
        """Test detection of setuptools via setup.py."""
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()")
        manager, info = detect_package_manager(tmp_path)
        assert manager == "setuptools"

    def test_detect_none(self, tmp_path: Path) -> None:
        """Test when no package manager is detected."""
        manager, info = detect_package_manager(tmp_path)
        assert manager is None
        assert info == {}


class TestDetectLinter:
    """Tests for detect_linter function."""

    def test_detect_ruff(self, tmp_path: Path) -> None:
        """Test detection of ruff."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.ruff]
line-length = 88
""")
        linter, info = detect_linter(tmp_path)
        assert linter == "ruff"

    def test_detect_ruff_toml(self, tmp_path: Path) -> None:
        """Test detection of ruff via ruff.toml."""
        (tmp_path / "ruff.toml").write_text("line-length = 88")
        linter, info = detect_linter(tmp_path)
        assert linter == "ruff"

    def test_detect_flake8(self, tmp_path: Path) -> None:
        """Test detection of flake8."""
        (tmp_path / ".flake8").write_text("[flake8]\nmax-line-length = 88")
        linter, info = detect_linter(tmp_path)
        assert linter == "flake8"

    def test_detect_pylint(self, tmp_path: Path) -> None:
        """Test detection of pylint."""
        (tmp_path / ".pylintrc").touch()
        linter, info = detect_linter(tmp_path)
        assert linter == "pylint"


class TestDetectFormatter:
    """Tests for detect_formatter function."""

    def test_detect_ruff_format(self, tmp_path: Path) -> None:
        """Test detection of ruff format."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.ruff]
line-length = 88

[tool.ruff.format]
quote-style = "double"
""")
        formatter, info = detect_formatter(tmp_path)
        assert formatter == "ruff"

    def test_detect_black(self, tmp_path: Path) -> None:
        """Test detection of black."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.black]
line-length = 88
""")
        formatter, info = detect_formatter(tmp_path)
        assert formatter == "black"


class TestDetectTypeChecker:
    """Tests for detect_type_checker function."""

    def test_detect_basedpyright(self, tmp_path: Path) -> None:
        """Test detection of basedpyright."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.basedpyright]
typeCheckingMode = "standard"
""")
        checker, info = detect_type_checker(tmp_path)
        assert checker == "basedpyright"

    def test_detect_mypy(self, tmp_path: Path) -> None:
        """Test detection of mypy."""
        (tmp_path / "mypy.ini").write_text("[mypy]\nstrict = true")
        checker, info = detect_type_checker(tmp_path)
        assert checker == "mypy"

    def test_detect_pyright(self, tmp_path: Path) -> None:
        """Test detection of pyright."""
        (tmp_path / "pyrightconfig.json").write_text("{}")
        checker, info = detect_type_checker(tmp_path)
        assert checker == "pyright"


class TestDetectPreCommit:
    """Tests for detect_pre_commit function."""

    def test_has_pre_commit(self, tmp_path: Path) -> None:
        """Test when pre-commit is configured."""
        (tmp_path / ".pre-commit-config.yaml").touch()
        assert detect_pre_commit(tmp_path) is True

    def test_no_pre_commit(self, tmp_path: Path) -> None:
        """Test when pre-commit is not configured."""
        assert detect_pre_commit(tmp_path) is False


class TestDetectCI:
    """Tests for detect_ci function."""

    def test_detect_github_actions(self, tmp_path: Path) -> None:
        """Test detection of GitHub Actions."""
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").touch()
        ci, info = detect_ci(tmp_path)
        assert ci == "github-actions"

    def test_detect_gitlab_ci(self, tmp_path: Path) -> None:
        """Test detection of GitLab CI."""
        (tmp_path / ".gitlab-ci.yml").touch()
        ci, info = detect_ci(tmp_path)
        assert ci == "gitlab-ci"

    def test_detect_no_ci(self, tmp_path: Path) -> None:
        """Test when no CI is configured."""
        ci, info = detect_ci(tmp_path)
        assert ci is None


class TestAnalyzeTypeCoverage:
    """Tests for analyze_type_coverage function."""

    def test_fully_typed(self, tmp_path: Path) -> None:
        """Test analysis of fully typed code."""
        (tmp_path / "typed.py").write_text("""
def add(a: int, b: int) -> int:
    return a + b

def greet(name: str) -> str:
    return f"Hello, {name}"
""")
        coverage, typed, total = analyze_type_coverage(tmp_path)
        assert coverage == 100.0
        assert typed == 2
        assert total == 2

    def test_partially_typed(self, tmp_path: Path) -> None:
        """Test analysis of partially typed code."""
        (tmp_path / "partial.py").write_text("""
def typed_func(x: int) -> int:
    return x

def untyped_func(x):
    return x
""")
        coverage, typed, total = analyze_type_coverage(tmp_path)
        assert coverage == 50.0
        assert typed == 1
        assert total == 2

    def test_untyped(self, tmp_path: Path) -> None:
        """Test analysis of untyped code."""
        (tmp_path / "untyped.py").write_text("""
def func1(x):
    return x

def func2(a, b):
    return a + b
""")
        coverage, typed, total = analyze_type_coverage(tmp_path)
        assert coverage == 0.0
        assert typed == 0
        assert total == 2

    def test_empty_project(self, tmp_path: Path) -> None:
        """Test analysis of empty project."""
        coverage, typed, total = analyze_type_coverage(tmp_path)
        assert coverage == 100.0
        assert typed == 0
        assert total == 0


class TestAuditProject:
    """Tests for audit_project function."""

    def test_audit_modern_project(self, tmp_path: Path) -> None:
        """Test auditing a modern project."""
        # Create a modern project
        (tmp_path / "uv.lock").touch()
        (tmp_path / ".pre-commit-config.yaml").touch()
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").touch()

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[tool.ruff]
line-length = 88

[tool.basedpyright]
typeCheckingMode = "standard"
""")

        result = audit_project(tmp_path)
        assert result.score >= 80
        assert result.tooling_detected["package_manager"] == "uv"
        assert result.tooling_detected["linter"] == "ruff"
        assert result.tooling_detected["type_checker"] == "basedpyright"

    def test_audit_legacy_project(self, tmp_path: Path) -> None:
        """Test auditing a legacy project."""
        # Create a legacy project
        (tmp_path / "requirements.txt").write_text("requests>=2.0")
        (tmp_path / ".flake8").write_text("[flake8]\nmax-line-length = 88")
        (tmp_path / "mypy.ini").write_text("[mypy]\nstrict = true")

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[tool.black]
line-length = 88

[tool.isort]
profile = "black"
""")

        result = audit_project(tmp_path)
        # Legacy project still scores reasonably because it has tooling (just not modern)
        # The key is that it has recommendations for modernization
        assert len(result.recommendations) > 0

        # Check for expected recommendations
        messages = [r.message for r in result.recommendations]
        assert any("pip" in m.lower() or "requirements" in m.lower() for m in messages)
        assert any("flake8" in m.lower() or "ruff" in m.lower() for m in messages)
        assert any("mypy" in m.lower() or "basedpyright" in m.lower() for m in messages)

    def test_audit_nonexistent_path(self, tmp_path: Path) -> None:
        """Test auditing a non-existent path."""
        with pytest.raises(FileNotFoundError):
            audit_project(tmp_path / "nonexistent")

    def test_audit_file_not_directory(self, tmp_path: Path) -> None:
        """Test auditing a file instead of directory."""
        file = tmp_path / "file.txt"
        file.touch()
        with pytest.raises(NotADirectoryError):
            audit_project(file)


class TestAuditResult:
    """Tests for AuditResult class."""

    def test_severity_counts(self) -> None:
        """Test severity count properties."""
        result = AuditResult(
            project_path=Path("."),
            recommendations=[
                Recommendation(AuditCategory.TOOLING, "test1", Severity.CRITICAL),
                Recommendation(AuditCategory.TOOLING, "test2", Severity.CRITICAL),
                Recommendation(AuditCategory.TOOLING, "test3", Severity.ERROR),
                Recommendation(AuditCategory.TOOLING, "test4", Severity.WARNING),
                Recommendation(AuditCategory.TOOLING, "test5", Severity.INFO),
                Recommendation(AuditCategory.TOOLING, "test6", Severity.INFO),
            ],
        )
        assert result.critical_count == 2
        assert result.error_count == 1
        assert result.warning_count == 1
        assert result.info_count == 2
