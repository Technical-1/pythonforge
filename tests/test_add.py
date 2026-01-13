"""Tests for pyinit add command and add_feature_to_project function."""

from pathlib import Path

import pytest

from pyhatch.generator import (
    FEATURE_TEMPLATES,
    add_feature_to_project,
    load_project_config,
)
from pyhatch.models import ProjectType


class TestLoadProjectConfig:
    """Tests for load_project_config function."""

    def test_load_basic_config(self, tmp_path: Path) -> None:
        """Test loading basic project configuration."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "testproject"
version = "0.1.0"
description = "A test project"
requires-python = ">=3.11"
authors = [
    { name = "Test Author", email = "test@example.com" }
]
""")

        config = load_project_config(tmp_path)

        assert config.name == "testproject"
        assert config.description == "A test project"

    def test_load_cli_project(self, tmp_path: Path) -> None:
        """Test loading CLI project configuration."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "mycli"
version = "0.1.0"

[project.scripts]
mycli = "mycli.cli:main"
""")

        config = load_project_config(tmp_path)

        assert config.name == "mycli"
        assert config.project_type == ProjectType.CLI

    def test_load_with_basedpyright(self, tmp_path: Path) -> None:
        """Test loading config with basedpyright settings."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"

[tool.basedpyright]
typeCheckingMode = "strict"
""")

        config = load_project_config(tmp_path)

        assert config.tooling.type_checking_mode.value == "strict"

    def test_load_detects_existing_features(self, tmp_path: Path) -> None:
        """Test that existing features are detected."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'")

        # Create some feature files
        (tmp_path / ".pre-commit-config.yaml").touch()
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        (tmp_path / ".github" / "workflows" / "ci.yml").touch()

        config = load_project_config(tmp_path)

        assert config.features.pre_commit is True
        assert config.features.github_actions is True
        assert config.features.docker is False

    def test_load_missing_pyproject(self, tmp_path: Path) -> None:
        """Test loading from directory without pyproject.toml."""
        with pytest.raises(FileNotFoundError):
            load_project_config(tmp_path)


class TestFeatureTemplates:
    """Tests for FEATURE_TEMPLATES mapping."""

    def test_all_features_defined(self) -> None:
        """Test that all expected features are defined."""
        expected_features = {
            "github-actions",
            "pre-commit",
            "vscode",
            "docker",
            "docs",
            "devcontainer",
        }
        assert set(FEATURE_TEMPLATES.keys()) == expected_features

    def test_each_feature_has_templates(self) -> None:
        """Test that each feature has at least one template."""
        for feature, templates in FEATURE_TEMPLATES.items():
            assert len(templates) > 0, f"{feature} has no templates"
            for template_name, output_path in templates:
                assert template_name.endswith(".j2"), f"{template_name} should end with .j2"
                assert output_path, f"{feature} has empty output path"


class TestAddFeatureToProject:
    """Tests for add_feature_to_project function."""

    def test_add_github_actions(self, tmp_path: Path) -> None:
        """Test adding GitHub Actions to a project."""
        # Create minimal project
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "testproject"
requires-python = ">=3.11"
""")

        created = add_feature_to_project(tmp_path, "github-actions")

        assert len(created) == 1
        assert (tmp_path / ".github" / "workflows" / "ci.yml").exists()

    def test_add_docker(self, tmp_path: Path) -> None:
        """Test adding Docker configuration."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "testproject"
requires-python = ">=3.12"
""")

        created = add_feature_to_project(tmp_path, "docker")

        assert len(created) == 2
        assert (tmp_path / "Dockerfile").exists()
        assert (tmp_path / "docker-compose.yml").exists()

        # Check Dockerfile content references the project
        dockerfile_content = (tmp_path / "Dockerfile").read_text()
        assert "python" in dockerfile_content.lower()

    def test_add_docs(self, tmp_path: Path) -> None:
        """Test adding documentation configuration."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "testproject"
description = "A test project"
""")

        created = add_feature_to_project(tmp_path, "docs")

        assert len(created) == 2
        assert (tmp_path / "mkdocs.yml").exists()
        assert (tmp_path / "docs" / "index.md").exists()

        # Check mkdocs.yml references the project
        mkdocs_content = (tmp_path / "mkdocs.yml").read_text()
        assert "testproject" in mkdocs_content

    def test_add_pre_commit(self, tmp_path: Path) -> None:
        """Test adding pre-commit configuration."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'")

        created = add_feature_to_project(tmp_path, "pre-commit")

        assert len(created) == 1
        assert (tmp_path / ".pre-commit-config.yaml").exists()

    def test_add_vscode(self, tmp_path: Path) -> None:
        """Test adding VS Code configuration."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'")

        created = add_feature_to_project(tmp_path, "vscode")

        assert len(created) == 2
        assert (tmp_path / ".vscode" / "settings.json").exists()
        assert (tmp_path / ".vscode" / "extensions.json").exists()

    def test_add_devcontainer(self, tmp_path: Path) -> None:
        """Test adding devcontainer configuration."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "testproject"
requires-python = ">=3.12"
""")

        created = add_feature_to_project(tmp_path, "devcontainer")

        assert len(created) == 1
        assert (tmp_path / ".devcontainer" / "devcontainer.json").exists()

    def test_add_unknown_feature(self, tmp_path: Path) -> None:
        """Test adding unknown feature raises error."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'")

        with pytest.raises(ValueError) as exc_info:
            add_feature_to_project(tmp_path, "unknown-feature")

        assert "Unknown feature" in str(exc_info.value)

    def test_add_existing_feature_without_force(self, tmp_path: Path) -> None:
        """Test that adding existing files fails without --force."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'")

        # Create existing file
        (tmp_path / ".pre-commit-config.yaml").write_text("# existing")

        with pytest.raises(FileExistsError):
            add_feature_to_project(tmp_path, "pre-commit", force=False)

    def test_add_existing_feature_with_force(self, tmp_path: Path) -> None:
        """Test that adding existing files works with --force."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'")

        # Create existing file with distinct content
        (tmp_path / ".pre-commit-config.yaml").write_text("# old content")

        created = add_feature_to_project(tmp_path, "pre-commit", force=True)

        assert len(created) == 1
        # Content should be overwritten
        content = (tmp_path / ".pre-commit-config.yaml").read_text()
        assert "# old content" not in content

    def test_add_without_pyproject(self, tmp_path: Path) -> None:
        """Test that adding to project without pyproject.toml fails."""
        with pytest.raises(FileNotFoundError):
            add_feature_to_project(tmp_path, "github-actions")

    def test_templates_render_with_config(self, tmp_path: Path) -> None:
        """Test that templates are rendered with project config."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "my-cool-project"
description = "A very cool project"
requires-python = ">=3.12"
""")

        add_feature_to_project(tmp_path, "docs")

        # Check that config values are in the rendered template
        mkdocs_content = (tmp_path / "mkdocs.yml").read_text()
        assert "my-cool-project" in mkdocs_content
        assert "A very cool project" in mkdocs_content

        index_content = (tmp_path / "docs" / "index.md").read_text()
        assert "my-cool-project" in index_content
