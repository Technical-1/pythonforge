"""
Tests for pyinit.generator
===========================

This module contains tests for the project generation logic.
Tests cover directory creation, template rendering, file writing,
and end-to-end project generation.

Test Organization
-----------------
- TestDirectoryStructure: Tests for directory creation
- TestTemplateRendering: Tests for Jinja2 template rendering
- TestFileWriting: Tests for file writing operations
- TestGitInitialization: Tests for git repo setup
- TestProjectValidation: Tests for post-creation validation
- TestCreateProject: End-to-end generation tests
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from pyhatch.models import (
    AuthorInfo,
    FeaturesConfig,
    ProjectConfig,
    ProjectType,
    PythonVersion,
    ToolingConfig,
    TypeCheckingMode,
)
from pyhatch.generator import (
    create_directory_structure,
    create_jinja_env,
    render_template,
    get_output_path,
    render_all_templates,
    write_files,
    create_py_typed,
    create_test_init,
    init_git_repository,
    validate_project,
    create_project,
    GenerationResult,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for test output."""
    return tmp_path


@pytest.fixture
def basic_config(temp_dir: Path) -> ProjectConfig:
    """Create a basic library project configuration."""
    return ProjectConfig(
        name="testproject",
        description="A test project",
        project_type=ProjectType.LIBRARY,
        python_version=PythonVersion.PY312,
        author=AuthorInfo(name="Test Author", email="test@example.com"),
        output_dir=temp_dir,
    )


@pytest.fixture
def cli_config(temp_dir: Path) -> ProjectConfig:
    """Create a CLI project configuration."""
    return ProjectConfig(
        name="testcli",
        description="A test CLI",
        project_type=ProjectType.CLI,
        python_version=PythonVersion.PY312,
        author=AuthorInfo(name="Test Author"),
        output_dir=temp_dir,
    )


@pytest.fixture
def api_config(temp_dir: Path) -> ProjectConfig:
    """Create an API project configuration."""
    return ProjectConfig(
        name="testapi",
        description="A test API",
        project_type=ProjectType.API,
        python_version=PythonVersion.PY312,
        author=AuthorInfo(name="Test Author"),
        output_dir=temp_dir,
    )


@pytest.fixture
def minimal_features_config(temp_dir: Path) -> ProjectConfig:
    """Create a config with minimal features."""
    return ProjectConfig(
        name="minimal",
        project_type=ProjectType.LIBRARY,
        features=FeaturesConfig(
            github_actions=False,
            pre_commit=False,
            vscode=False,
        ),
        output_dir=temp_dir,
    )


# =============================================================================
# Directory Structure Tests
# =============================================================================

class TestDirectoryStructure:
    """Tests for create_directory_structure function."""
    
    def test_creates_project_root(self, basic_config: ProjectConfig) -> None:
        """Test that project root directory is created."""
        create_directory_structure(basic_config)
        assert basic_config.project_dir.exists()
        assert basic_config.project_dir.is_dir()
    
    def test_creates_src_layout(self, basic_config: ProjectConfig) -> None:
        """Test src layout structure for library projects."""
        create_directory_structure(basic_config)
        
        src_path = basic_config.project_dir / basic_config.get_src_path()
        assert src_path.exists()
        assert "src" in str(src_path)
    
    def test_creates_tests_directory(self, basic_config: ProjectConfig) -> None:
        """Test that tests directory is created."""
        create_directory_structure(basic_config)
        
        tests_path = basic_config.project_dir / "tests"
        assert tests_path.exists()
    
    def test_creates_github_directory(self, basic_config: ProjectConfig) -> None:
        """Test GitHub Actions directory creation."""
        create_directory_structure(basic_config)
        
        github_path = basic_config.project_dir / ".github" / "workflows"
        assert github_path.exists()
    
    def test_creates_vscode_directory(self, basic_config: ProjectConfig) -> None:
        """Test VS Code directory creation."""
        create_directory_structure(basic_config)
        
        vscode_path = basic_config.project_dir / ".vscode"
        assert vscode_path.exists()
    
    def test_skips_github_when_disabled(
        self, minimal_features_config: ProjectConfig
    ) -> None:
        """Test GitHub directory is skipped when feature disabled."""
        create_directory_structure(minimal_features_config)
        
        github_path = minimal_features_config.project_dir / ".github"
        assert not github_path.exists()
    
    def test_fails_if_directory_exists(self, basic_config: ProjectConfig) -> None:
        """Test that existing directory raises FileExistsError."""
        # Create directory first
        basic_config.project_dir.mkdir(parents=True)
        
        with pytest.raises(FileExistsError):
            create_directory_structure(basic_config)
    
    def test_returns_created_directories(self, basic_config: ProjectConfig) -> None:
        """Test that function returns list of created directories."""
        created = create_directory_structure(basic_config)
        
        assert isinstance(created, list)
        assert len(created) > 0
        assert all(isinstance(d, Path) for d in created)


# =============================================================================
# Template Rendering Tests
# =============================================================================

class TestTemplateRendering:
    """Tests for template rendering functions."""
    
    def test_create_jinja_env(self) -> None:
        """Test Jinja2 environment creation."""
        env = create_jinja_env()
        
        assert env is not None
        assert env.trim_blocks is True
        assert env.lstrip_blocks is True
    
    def test_render_pyproject_template(self, basic_config: ProjectConfig) -> None:
        """Test rendering pyproject.toml template."""
        env = create_jinja_env()
        content = render_template(env, "pyproject.toml.j2", basic_config)
        
        assert "testproject" in content
        assert "[project]" in content
        assert "[build-system]" in content
    
    def test_render_readme_template(self, basic_config: ProjectConfig) -> None:
        """Test rendering README.md template."""
        env = create_jinja_env()
        content = render_template(env, "README.md.j2", basic_config)
        
        assert "testproject" in content
        assert "A test project" in content
    
    def test_render_cli_template(self, cli_config: ProjectConfig) -> None:
        """Test rendering CLI template."""
        env = create_jinja_env()
        content = render_template(env, "cli.py.j2", cli_config)
        
        assert "typer" in content.lower()
        assert "testcli" in content
    
    def test_get_output_path_with_placeholders(
        self, basic_config: ProjectConfig
    ) -> None:
        """Test output path resolution with placeholders."""
        path = get_output_path("{src_path}/__init__.py", basic_config)
        
        assert path == Path("src/testproject/__init__.py")
    
    def test_get_output_path_without_placeholders(
        self, basic_config: ProjectConfig
    ) -> None:
        """Test output path resolution without placeholders."""
        path = get_output_path("pyproject.toml", basic_config)
        
        assert path == Path("pyproject.toml")
    
    def test_render_all_templates_library(
        self, basic_config: ProjectConfig
    ) -> None:
        """Test rendering all templates for a library."""
        rendered = render_all_templates(basic_config)
        
        assert Path("pyproject.toml") in rendered
        assert Path("README.md") in rendered
        assert Path(".gitignore") in rendered
        assert Path("src/testproject/__init__.py") in rendered
        
        # CLI template should not be rendered
        assert Path("src/testproject/cli.py") not in rendered
    
    def test_render_all_templates_cli(self, cli_config: ProjectConfig) -> None:
        """Test rendering all templates for a CLI project."""
        rendered = render_all_templates(cli_config)
        
        # CLI-specific file should be included
        assert Path("src/testcli/cli.py") in rendered
    
    def test_render_all_templates_api(self, api_config: ProjectConfig) -> None:
        """Test rendering all templates for an API project."""
        rendered = render_all_templates(api_config)
        
        # API-specific file should be included
        assert Path("src/testapi/main.py") in rendered


# =============================================================================
# File Writing Tests
# =============================================================================

class TestFileWriting:
    """Tests for file writing functions."""
    
    def test_write_files(self, basic_config: ProjectConfig) -> None:
        """Test writing files to disk."""
        # Create project directory first
        basic_config.project_dir.mkdir(parents=True)
        
        files = {
            Path("test.txt"): "Hello, World!",
            Path("subdir/nested.txt"): "Nested content",
        }
        
        created = write_files(basic_config.project_dir, files)
        
        assert len(created) == 2
        assert (basic_config.project_dir / "test.txt").read_text() == "Hello, World!"
        assert (basic_config.project_dir / "subdir/nested.txt").read_text() == "Nested content"
    
    def test_create_py_typed(self, basic_config: ProjectConfig) -> None:
        """Test py.typed marker file creation."""
        # Create directories first
        create_directory_structure(basic_config)
        
        create_py_typed(basic_config)
        
        py_typed = basic_config.project_dir / basic_config.get_src_path() / "py.typed"
        assert py_typed.exists()
    
    def test_create_test_init(self, basic_config: ProjectConfig) -> None:
        """Test tests/__init__.py creation."""
        # Create directories first
        create_directory_structure(basic_config)
        
        create_test_init(basic_config)
        
        test_init = basic_config.project_dir / "tests" / "__init__.py"
        assert test_init.exists()
        assert "testproject" in test_init.read_text()


# =============================================================================
# Git Initialization Tests
# =============================================================================

class TestGitInitialization:
    """Tests for git repository initialization."""
    
    def test_init_git_success(self, basic_config: ProjectConfig) -> None:
        """Test successful git initialization."""
        # Create project with some files
        create_directory_structure(basic_config)
        (basic_config.project_dir / "test.txt").write_text("test")
        
        result = init_git_repository(basic_config.project_dir)
        
        # Check if git init worked (depends on git being installed)
        if result:
            git_dir = basic_config.project_dir / ".git"
            assert git_dir.exists()
    
    def test_init_git_handles_missing_git(
        self, basic_config: ProjectConfig
    ) -> None:
        """Test graceful handling when git is not installed."""
        create_directory_structure(basic_config)
        
        # Mock subprocess to simulate git not found
        with patch("pyinit.generator.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = init_git_repository(basic_config.project_dir)
        
        assert result is False


# =============================================================================
# Project Validation Tests
# =============================================================================

class TestProjectValidation:
    """Tests for post-creation project validation."""
    
    def test_validate_complete_project(self, basic_config: ProjectConfig) -> None:
        """Test validation of a complete project."""
        # Create complete project structure
        create_directory_structure(basic_config)
        rendered = render_all_templates(basic_config)
        write_files(basic_config.project_dir, rendered)
        create_py_typed(basic_config)
        create_test_init(basic_config)
        
        success, issues = validate_project(basic_config)
        
        assert success is True
        assert len(issues) == 0
    
    def test_validate_missing_files(self, basic_config: ProjectConfig) -> None:
        """Test validation catches missing files."""
        # Create incomplete project
        create_directory_structure(basic_config)
        # Don't create any files
        
        success, issues = validate_project(basic_config)
        
        assert success is False
        assert len(issues) > 0
    
    def test_validate_invalid_python_syntax(
        self, basic_config: ProjectConfig
    ) -> None:
        """Test validation catches Python syntax errors."""
        create_directory_structure(basic_config)
        
        # Write invalid Python
        bad_py = basic_config.project_dir / basic_config.get_src_path() / "bad.py"
        bad_py.write_text("def broken(\n")
        
        success, issues = validate_project(basic_config)
        
        assert success is False
        assert any("Syntax error" in issue for issue in issues)


# =============================================================================
# End-to-End Generation Tests
# =============================================================================

class TestCreateProject:
    """End-to-end tests for project generation."""
    
    def test_create_basic_library(self, basic_config: ProjectConfig) -> None:
        """Test creating a basic library project."""
        result = create_project(basic_config, verbose=False, init_git=False)
        
        assert result.success is True
        assert result.project_path == basic_config.project_dir
        assert basic_config.project_dir.exists()
        
        # Check key files exist
        assert (basic_config.project_dir / "pyproject.toml").exists()
        assert (basic_config.project_dir / "README.md").exists()
        assert (basic_config.project_dir / ".gitignore").exists()
    
    def test_create_cli_project(self, cli_config: ProjectConfig) -> None:
        """Test creating a CLI project."""
        result = create_project(cli_config, verbose=False, init_git=False)
        
        assert result.success is True
        
        # Check CLI-specific file exists
        cli_file = cli_config.project_dir / cli_config.get_src_path() / "cli.py"
        assert cli_file.exists()
        assert "typer" in cli_file.read_text().lower()
    
    def test_create_api_project(self, api_config: ProjectConfig) -> None:
        """Test creating an API project."""
        result = create_project(api_config, verbose=False, init_git=False)
        
        assert result.success is True
        
        # Check API-specific file exists
        main_file = api_config.project_dir / api_config.get_src_path() / "main.py"
        assert main_file.exists()
        assert "fastapi" in main_file.read_text().lower()
    
    def test_create_project_with_features(self, temp_dir: Path) -> None:
        """Test creating a project with all features enabled."""
        config = ProjectConfig(
            name="fullproject",
            features=FeaturesConfig(
                github_actions=True,
                pre_commit=True,
                vscode=True,
            ),
            output_dir=temp_dir,
        )
        
        result = create_project(config, verbose=False, init_git=False)
        
        assert result.success is True
        
        # Check feature files exist
        assert (config.project_dir / ".github" / "workflows" / "ci.yml").exists()
        assert (config.project_dir / ".pre-commit-config.yaml").exists()
        assert (config.project_dir / ".vscode" / "settings.json").exists()
    
    def test_create_project_fails_if_exists(
        self, basic_config: ProjectConfig
    ) -> None:
        """Test that creation fails if directory exists."""
        # Create directory first
        basic_config.project_dir.mkdir(parents=True)
        
        with pytest.raises(FileExistsError):
            create_project(basic_config, verbose=False)
    
    def test_create_project_result_files(
        self, basic_config: ProjectConfig
    ) -> None:
        """Test that result contains list of created files."""
        result = create_project(basic_config, verbose=False, init_git=False)
        
        assert len(result.files_created) > 0
        assert all(isinstance(f, Path) for f in result.files_created)
    
    def test_create_project_validates(self, basic_config: ProjectConfig) -> None:
        """Test that validation runs and passes."""
        result = create_project(
            basic_config,
            verbose=False,
            init_git=False,
            validate=True,
        )
        
        assert result.validation_passed is True
    
    def test_generated_pyproject_is_valid_toml(
        self, basic_config: ProjectConfig
    ) -> None:
        """Test that generated pyproject.toml is valid TOML."""
        import tomli
        
        create_project(basic_config, verbose=False, init_git=False)
        
        pyproject_path = basic_config.project_dir / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomli.load(f)
        
        assert "project" in data
        assert data["project"]["name"] == "testproject"
    
    def test_generated_python_files_have_valid_syntax(
        self, cli_config: ProjectConfig
    ) -> None:
        """Test that all generated Python files have valid syntax."""
        create_project(cli_config, verbose=False, init_git=False)
        
        python_files = list(cli_config.project_dir.rglob("*.py"))
        assert len(python_files) > 0
        
        for py_file in python_files:
            content = py_file.read_text()
            # This will raise SyntaxError if invalid
            compile(content, py_file, "exec")


# =============================================================================
# GenerationResult Tests
# =============================================================================

class TestGenerationResult:
    """Tests for the GenerationResult dataclass."""
    
    def test_default_values(self) -> None:
        """Test GenerationResult default values."""
        result = GenerationResult(
            success=True,
            project_path=Path("/test"),
        )
        
        assert result.files_created == []
        assert result.warnings == []
        assert result.errors == []
        assert result.validation_passed is False
    
    def test_with_files(self) -> None:
        """Test GenerationResult with files."""
        result = GenerationResult(
            success=True,
            project_path=Path("/test"),
            files_created=[Path("/test/a.py"), Path("/test/b.py")],
        )
        
        assert len(result.files_created) == 2
