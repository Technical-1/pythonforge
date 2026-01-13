"""
Tests for pyinit.cli
=====================

This module contains tests for the command-line interface.
Tests use Typer's CliRunner for testing CLI commands.

Test Organization
-----------------
- TestVersionCommand: Tests for --version flag
- TestNewCommand: Tests for the new command
- TestHelpOutput: Tests for help text
"""

import pytest
from pathlib import Path
from typer.testing import CliRunner

from pyhatch.cli import app
from pyhatch import __version__


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for test output."""
    return tmp_path


# =============================================================================
# Version Command Tests
# =============================================================================

class TestVersionCommand:
    """Tests for the --version flag."""
    
    def test_version_flag(self, runner: CliRunner) -> None:
        """Test that --version shows version."""
        result = runner.invoke(app, ["--version"])
        
        assert result.exit_code == 0
        assert __version__ in result.stdout
    
    def test_version_short_flag(self, runner: CliRunner) -> None:
        """Test that -V shows version."""
        result = runner.invoke(app, ["-V"])
        
        assert result.exit_code == 0
        assert __version__ in result.stdout


# =============================================================================
# Help Output Tests
# =============================================================================

class TestHelpOutput:
    """Tests for help text."""
    
    def test_main_help(self, runner: CliRunner) -> None:
        """Test main help output."""
        result = runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "pyinit" in result.stdout.lower()
        assert "new" in result.stdout
    
    def test_new_help(self, runner: CliRunner) -> None:
        """Test new command help output."""
        result = runner.invoke(app, ["new", "--help"])
        
        assert result.exit_code == 0
        assert "Create a new Python project" in result.stdout
        assert "--type" in result.stdout
        assert "--python" in result.stdout
    
    def test_audit_help(self, runner: CliRunner) -> None:
        """Test audit command help output."""
        result = runner.invoke(app, ["audit", "--help"])
        
        assert result.exit_code == 0
        assert "Audit" in result.stdout
    
    def test_upgrade_help(self, runner: CliRunner) -> None:
        """Test upgrade command help output."""
        result = runner.invoke(app, ["upgrade", "--help"])
        
        assert result.exit_code == 0
        assert "Upgrade" in result.stdout
    
    def test_add_help(self, runner: CliRunner) -> None:
        """Test add command help output."""
        result = runner.invoke(app, ["add", "--help"])
        
        assert result.exit_code == 0
        assert "Add" in result.stdout


# =============================================================================
# New Command Tests
# =============================================================================

class TestNewCommand:
    """Tests for the new command."""
    
    def test_new_with_defaults(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test creating a project with defaults."""
        result = runner.invoke(
            app,
            ["new", "testproject", "--yes", "--output", str(temp_dir), "--no-git"],
        )
        
        assert result.exit_code == 0
        assert (temp_dir / "testproject").exists()
        assert (temp_dir / "testproject" / "pyproject.toml").exists()
    
    def test_new_library_type(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test creating a library project."""
        result = runner.invoke(
            app,
            [
                "new", "mylib",
                "--type", "library",
                "--yes",
                "--output", str(temp_dir),
                "--no-git",
            ],
        )
        
        assert result.exit_code == 0
        assert (temp_dir / "mylib" / "src" / "mylib" / "__init__.py").exists()
    
    def test_new_cli_type(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test creating a CLI project."""
        result = runner.invoke(
            app,
            [
                "new", "mycli",
                "--type", "cli",
                "--yes",
                "--output", str(temp_dir),
                "--no-git",
            ],
        )
        
        assert result.exit_code == 0
        assert (temp_dir / "mycli" / "src" / "mycli" / "cli.py").exists()
    
    def test_new_api_type(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test creating an API project."""
        result = runner.invoke(
            app,
            [
                "new", "myapi",
                "--type", "api",
                "--yes",
                "--output", str(temp_dir),
                "--no-git",
            ],
        )
        
        assert result.exit_code == 0
        assert (temp_dir / "myapi" / "src" / "myapi" / "main.py").exists()
    
    def test_new_with_python_version(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test specifying Python version."""
        result = runner.invoke(
            app,
            [
                "new", "testproject",
                "--python", "3.11",
                "--yes",
                "--output", str(temp_dir),
                "--no-git",
            ],
        )
        
        assert result.exit_code == 0
        
        # Check pyproject.toml contains correct version
        pyproject = (temp_dir / "testproject" / "pyproject.toml").read_text()
        assert "3.11" in pyproject
    
    def test_new_with_author(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test specifying author information."""
        result = runner.invoke(
            app,
            [
                "new", "testproject",
                "--author", "Jane Doe",
                "--email", "jane@example.com",
                "--yes",
                "--output", str(temp_dir),
                "--no-git",
            ],
        )
        
        assert result.exit_code == 0
        
        pyproject = (temp_dir / "testproject" / "pyproject.toml").read_text()
        assert "Jane Doe" in pyproject
        assert "jane@example.com" in pyproject
    
    def test_new_with_strict_mode(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test creating project with strict type checking."""
        result = runner.invoke(
            app,
            [
                "new", "testproject",
                "--strict",
                "--yes",
                "--output", str(temp_dir),
                "--no-git",
            ],
        )
        
        assert result.exit_code == 0
        
        pyproject = (temp_dir / "testproject" / "pyproject.toml").read_text()
        assert "strict" in pyproject.lower()
    
    def test_new_without_github_actions(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test creating project without GitHub Actions."""
        result = runner.invoke(
            app,
            [
                "new", "testproject",
                "--no-github-actions",
                "--yes",
                "--output", str(temp_dir),
                "--no-git",
            ],
        )
        
        assert result.exit_code == 0
        assert not (temp_dir / "testproject" / ".github").exists()
    
    def test_new_without_precommit(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test creating project without pre-commit."""
        result = runner.invoke(
            app,
            [
                "new", "testproject",
                "--no-pre-commit",
                "--yes",
                "--output", str(temp_dir),
                "--no-git",
            ],
        )
        
        assert result.exit_code == 0
        assert not (temp_dir / "testproject" / ".pre-commit-config.yaml").exists()
    
    def test_new_without_vscode(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test creating project without VS Code settings."""
        result = runner.invoke(
            app,
            [
                "new", "testproject",
                "--no-vscode",
                "--yes",
                "--output", str(temp_dir),
                "--no-git",
            ],
        )
        
        assert result.exit_code == 0
        assert not (temp_dir / "testproject" / ".vscode").exists()
    
    def test_new_invalid_project_type(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test error handling for invalid project type."""
        result = runner.invoke(
            app,
            [
                "new", "testproject",
                "--type", "invalid",
                "--yes",
                "--output", str(temp_dir),
            ],
        )
        
        assert result.exit_code == 1
        assert "Invalid project type" in result.stdout
    
    def test_new_invalid_python_version(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test error handling for invalid Python version."""
        result = runner.invoke(
            app,
            [
                "new", "testproject",
                "--python", "2.7",
                "--yes",
                "--output", str(temp_dir),
            ],
        )
        
        assert result.exit_code == 1
        assert "Invalid Python version" in result.stdout
    
    def test_new_existing_directory(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test error when directory already exists."""
        # Create directory first
        (temp_dir / "existingproject").mkdir()
        
        result = runner.invoke(
            app,
            [
                "new", "existingproject",
                "--yes",
                "--output", str(temp_dir),
                "--no-git",
            ],
        )
        
        assert result.exit_code == 1
    
    def test_new_hyphenated_name(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test creating project with hyphenated name."""
        result = runner.invoke(
            app,
            [
                "new", "my-cool-project",
                "--yes",
                "--output", str(temp_dir),
                "--no-git",
            ],
        )
        
        assert result.exit_code == 0
        
        # Directory uses original name
        assert (temp_dir / "my-cool-project").exists()
        
        # Package uses underscores
        assert (temp_dir / "my-cool-project" / "src" / "my_cool_project").exists()


# =============================================================================
# Placeholder Command Tests
# =============================================================================

class TestPhase3Commands:
    """Tests for Phase 3 implemented commands."""

    def test_audit_runs(self, runner: CliRunner, temp_dir: Path) -> None:
        """Test audit command runs on a directory."""
        # Create a minimal project to audit
        project_dir = temp_dir / "project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text("[project]\nname = 'test'")

        result = runner.invoke(app, ["audit", str(project_dir)])

        assert result.exit_code == 0
        # Should show audit results (score, detected tooling, etc.)
        assert "Auditing" in result.stdout or "Score" in result.stdout or "Detected" in result.stdout

    def test_upgrade_no_migrations(
        self, runner: CliRunner, temp_dir: Path
    ) -> None:
        """Test upgrade command when no migrations needed."""
        # Create a modern project that doesn't need migration
        project_dir = temp_dir / "project"
        project_dir.mkdir()
        (project_dir / "uv.lock").touch()
        (project_dir / "pyproject.toml").write_text("""
[project]
name = "test"

[tool.ruff]
line-length = 88

[tool.basedpyright]
typeCheckingMode = "standard"
""")

        result = runner.invoke(app, ["upgrade", str(project_dir)])

        assert result.exit_code == 0
        assert "No migrations needed" in result.stdout or "All Good" in result.stdout

    def test_add_requires_pyproject(self, runner: CliRunner, temp_dir: Path) -> None:
        """Test add command requires pyproject.toml."""
        # Create empty directory without pyproject.toml
        project_dir = temp_dir / "project"
        project_dir.mkdir()

        result = runner.invoke(app, ["add", "github-actions", "--path", str(project_dir)])

        assert result.exit_code == 1
        assert "pyproject.toml" in result.stdout or "Error" in result.stdout
