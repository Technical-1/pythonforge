"""
Tests for pyinit.models
========================

This module contains comprehensive tests for the Pydantic models
used throughout pyinit. Tests cover validation, serialization,
and computed properties.

Test Organization
-----------------
- TestProjectType: Tests for the ProjectType enum
- TestPythonVersion: Tests for PythonVersion enum
- TestLicense: Tests for License enum
- TestToolingConfig: Tests for tooling preferences
- TestFeaturesConfig: Tests for feature flags
- TestAuthorInfo: Tests for author information
- TestProjectConfig: Tests for the main config model
"""

import pytest
from pathlib import Path

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
# ProjectType Tests
# =============================================================================

class TestProjectType:
    """Tests for the ProjectType enumeration."""
    
    def test_all_types_have_values(self) -> None:
        """Verify all project types have string values."""
        for pt in ProjectType:
            assert isinstance(pt.value, str)
            assert len(pt.value) > 0
    
    def test_descriptions_exist(self) -> None:
        """Verify all types have descriptions."""
        for pt in ProjectType:
            assert hasattr(pt, "description")
            assert isinstance(pt.description, str)
            assert len(pt.description) > 0
    
    def test_src_layout_property(self) -> None:
        """Test uses_src_layout property for different types."""
        # Types that should use src layout
        assert ProjectType.LIBRARY.uses_src_layout is True
        assert ProjectType.CLI.uses_src_layout is True
        assert ProjectType.API.uses_src_layout is True
        
        # Types that shouldn't use src layout
        assert ProjectType.APP.uses_src_layout is False
        assert ProjectType.SCRIPT.uses_src_layout is False
    
    def test_type_from_string(self) -> None:
        """Test creating ProjectType from string value."""
        assert ProjectType("library") == ProjectType.LIBRARY
        assert ProjectType("cli") == ProjectType.CLI
        assert ProjectType("api") == ProjectType.API
    
    def test_invalid_type_raises(self) -> None:
        """Test that invalid type strings raise ValueError."""
        with pytest.raises(ValueError):
            ProjectType("invalid")


# =============================================================================
# PythonVersion Tests
# =============================================================================

class TestPythonVersion:
    """Tests for the PythonVersion enumeration."""
    
    def test_requires_python_format(self) -> None:
        """Test that requires_python generates valid PEP 440 specifiers."""
        for pv in PythonVersion:
            spec = pv.requires_python
            assert spec.startswith(">=")
            assert pv.value in spec
    
    def test_version_values(self) -> None:
        """Test that version values are valid Python versions."""
        for pv in PythonVersion:
            parts = pv.value.split(".")
            assert len(parts) == 2
            assert parts[0] == "3"
            assert parts[1].isdigit()


# =============================================================================
# License Tests
# =============================================================================

class TestLicense:
    """Tests for the License enumeration."""
    
    def test_spdx_ids(self) -> None:
        """Test that all licenses have SPDX identifiers."""
        for lic in License:
            assert hasattr(lic, "spdx_id")
            assert isinstance(lic.spdx_id, str)
    
    def test_mit_license(self) -> None:
        """Test MIT license properties."""
        assert License.MIT.value == "MIT"
        assert License.MIT.spdx_id == "MIT"


# =============================================================================
# ToolingConfig Tests
# =============================================================================

class TestToolingConfig:
    """Tests for the ToolingConfig model."""
    
    def test_default_values(self) -> None:
        """Test default tooling configuration."""
        config = ToolingConfig()
        assert config.linter == "ruff"
        assert config.formatter == "ruff"
        assert config.type_checker == "basedpyright"
        assert config.type_checking_mode == TypeCheckingMode.STANDARD
    
    def test_tool_name_normalization(self) -> None:
        """Test that tool names are normalized to lowercase."""
        config = ToolingConfig(linter="RUFF", formatter="Ruff")
        assert config.linter == "ruff"
        assert config.formatter == "ruff"
    
    def test_custom_type_checker(self) -> None:
        """Test setting a custom type checker."""
        config = ToolingConfig(type_checker="mypy")
        assert config.type_checker == "mypy"
    
    def test_strict_mode(self) -> None:
        """Test strict type checking mode."""
        config = ToolingConfig(type_checking_mode=TypeCheckingMode.STRICT)
        assert config.type_checking_mode == TypeCheckingMode.STRICT


# =============================================================================
# FeaturesConfig Tests
# =============================================================================

class TestFeaturesConfig:
    """Tests for the FeaturesConfig model."""
    
    def test_default_features(self) -> None:
        """Test default feature configuration."""
        config = FeaturesConfig()
        assert config.github_actions is True
        assert config.pre_commit is True
        assert config.vscode is True
        assert config.docker is False
        assert config.docs is False
        assert config.devcontainer is False
    
    def test_enabled_features_property(self) -> None:
        """Test enabled_features returns correct list."""
        config = FeaturesConfig(
            github_actions=True,
            pre_commit=False,
            vscode=True,
            docker=True,
        )
        enabled = config.enabled_features
        assert "github_actions" in enabled
        assert "vscode" in enabled
        assert "docker" in enabled
        assert "pre_commit" not in enabled
    
    def test_all_features_disabled(self) -> None:
        """Test when all features are disabled."""
        config = FeaturesConfig(
            github_actions=False,
            pre_commit=False,
            vscode=False,
            docker=False,
            docs=False,
            devcontainer=False,
        )
        assert config.enabled_features == []


# =============================================================================
# AuthorInfo Tests
# =============================================================================

class TestAuthorInfo:
    """Tests for the AuthorInfo model."""
    
    def test_name_only(self) -> None:
        """Test author with name only."""
        author = AuthorInfo(name="John Doe")
        assert author.name == "John Doe"
        assert author.email is None
    
    def test_name_and_email(self) -> None:
        """Test author with name and email."""
        author = AuthorInfo(name="Jane Doe", email="jane@example.com")
        assert author.name == "Jane Doe"
        assert author.email == "jane@example.com"
    
    def test_invalid_email_rejected(self) -> None:
        """Test that invalid email format is rejected."""
        with pytest.raises(ValueError, match="Invalid email"):
            AuthorInfo(name="Test", email="not-an-email")
    
    def test_empty_name_rejected(self) -> None:
        """Test that empty name is rejected."""
        with pytest.raises(ValueError):
            AuthorInfo(name="")
    
    def test_valid_email_formats(self) -> None:
        """Test various valid email formats."""
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.com",
            "user@subdomain.example.com",
        ]
        for email in valid_emails:
            author = AuthorInfo(name="Test", email=email)
            assert author.email == email


# =============================================================================
# ProjectConfig Tests
# =============================================================================

class TestProjectConfig:
    """Tests for the main ProjectConfig model."""
    
    def test_minimal_config(self) -> None:
        """Test creating config with just a name."""
        config = ProjectConfig(name="myproject")
        assert config.name == "myproject"
        assert config.project_type == ProjectType.LIBRARY
        assert config.python_version == PythonVersion.PY312
    
    def test_name_validation_lowercase(self) -> None:
        """Test that names are converted to lowercase."""
        config = ProjectConfig(name="MyProject")
        assert config.name == "myproject"
    
    def test_name_validation_strips_whitespace(self) -> None:
        """Test that whitespace is stripped from names."""
        config = ProjectConfig(name="  myproject  ")
        assert config.name == "myproject"
    
    def test_invalid_name_rejected(self) -> None:
        """Test that invalid names are rejected."""
        invalid_names = [
            "123project",      # Starts with number
            "my project",      # Contains space
            "my.project",      # Contains dot
            "@myproject",      # Starts with special char
        ]
        for name in invalid_names:
            with pytest.raises(ValueError):
                ProjectConfig(name=name)
    
    def test_reserved_word_rejected(self) -> None:
        """Test that Python reserved words are rejected."""
        reserved_words = ["import", "class", "def", "return", "if"]
        for word in reserved_words:
            with pytest.raises(ValueError, match="reserved word"):
                ProjectConfig(name=word)
    
    def test_package_name_conversion(self) -> None:
        """Test package_name converts hyphens to underscores."""
        config = ProjectConfig(name="my-cool-project")
        assert config.package_name == "my_cool_project"
    
    def test_project_dir_path(self) -> None:
        """Test project_dir is output_dir / name."""
        config = ProjectConfig(
            name="myproject",
            output_dir=Path("/home/user"),
        )
        assert config.project_dir == Path("/home/user/myproject")
    
    def test_src_path_for_library(self) -> None:
        """Test get_src_path for library projects."""
        config = ProjectConfig(
            name="mylib",
            project_type=ProjectType.LIBRARY,
        )
        assert config.get_src_path() == Path("src/mylib")
    
    def test_src_path_for_app(self) -> None:
        """Test get_src_path for app projects."""
        config = ProjectConfig(
            name="myapp",
            project_type=ProjectType.APP,
        )
        assert config.get_src_path() == Path("myapp")
    
    def test_test_path(self) -> None:
        """Test get_test_path returns tests directory."""
        config = ProjectConfig(name="myproject")
        assert config.get_test_path() == Path("tests")
    
    def test_script_with_docker_rejected(self) -> None:
        """Test that script projects can't have Docker."""
        with pytest.raises(ValueError, match="Docker is not applicable"):
            ProjectConfig(
                name="myscript",
                project_type=ProjectType.SCRIPT,
                features=FeaturesConfig(docker=True),
            )
    
    def test_script_with_docs_rejected(self) -> None:
        """Test that script projects can't have docs."""
        with pytest.raises(ValueError, match="Documentation setup is not applicable"):
            ProjectConfig(
                name="myscript",
                project_type=ProjectType.SCRIPT,
                features=FeaturesConfig(docs=True),
            )
    
    def test_full_config(self) -> None:
        """Test creating a fully specified config."""
        config = ProjectConfig(
            name="full-project",
            description="A fully configured project",
            project_type=ProjectType.CLI,
            python_version=PythonVersion.PY313,
            license=License.APACHE2,
            author=AuthorInfo(name="Dev", email="dev@example.com"),
            tooling=ToolingConfig(
                type_checker="pyright",
                type_checking_mode=TypeCheckingMode.STRICT,
            ),
            features=FeaturesConfig(
                github_actions=True,
                docker=True,
            ),
        )
        
        assert config.name == "full-project"
        assert config.package_name == "full_project"
        assert config.project_type == ProjectType.CLI
        assert config.python_version == PythonVersion.PY313
        assert config.license == License.APACHE2
        assert config.author.name == "Dev"
        assert config.tooling.type_checker == "pyright"
        assert config.features.docker is True
    
    def test_to_toml_dict(self) -> None:
        """Test serialization to TOML-compatible dict."""
        config = ProjectConfig(name="myproject")
        data = config.to_toml_dict()
        
        assert isinstance(data, dict)
        assert data["name"] == "myproject"
        assert isinstance(data["output_dir"], str)


# =============================================================================
# Integration Tests
# =============================================================================

class TestConfigIntegration:
    """Integration tests for configuration models."""
    
    def test_config_with_hyphenated_name(self) -> None:
        """Test full workflow with hyphenated project name."""
        config = ProjectConfig(
            name="my-awesome-project",
            project_type=ProjectType.CLI,
        )
        
        # Name should be preserved with hyphens
        assert config.name == "my-awesome-project"
        
        # Package name should convert to underscores
        assert config.package_name == "my_awesome_project"
        
        # Src path should use package name
        assert config.get_src_path() == Path("src/my_awesome_project")
    
    def test_api_project_defaults(self) -> None:
        """Test API project has correct defaults."""
        config = ProjectConfig(
            name="myapi",
            project_type=ProjectType.API,
        )
        
        assert config.project_type.uses_src_layout is True
        assert config.get_src_path() == Path("src/myapi")
