"""
Regression tests for the investigation-driven bug fixes.
=======================================================

Each test in this module corresponds to a specific issue found during the
repository investigation. They are grouped by the area of the fix.
"""

import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from quickforge.auditor import detect_ci
from quickforge.generator import (
    create_jinja_env,
    init_git_repository,
    load_project_config,
    render_all_templates,
    render_template,
)
from quickforge.models import (
    AuthorInfo,
    License,
    ProjectConfig,
    ProjectType,
)
from quickforge.upgrader import _migrate_poetry_to_uv, _migrate_requirements_to_uv


# =============================================================================
# Fix 1: All offered licenses must produce a LICENSE file
# =============================================================================


class TestLicenseFilesGenerated:
    """Every License the CLI offers must render an actual LICENSE file."""

    @pytest.mark.parametrize("license_", list(License))
    def test_license_file_is_rendered(self, tmp_path: Path, license_: License) -> None:
        config = ProjectConfig(
            name="lictest",
            license=license_,
            author=AuthorInfo(name="Jane Doe"),
            output_dir=tmp_path,
        )
        rendered = render_all_templates(config)

        assert Path("LICENSE") in rendered, f"No LICENSE rendered for {license_.value}"
        assert rendered[Path("LICENSE")].strip(), "LICENSE file is empty"

    def test_apache_license_content(self, tmp_path: Path) -> None:
        config = ProjectConfig(
            name="lictest",
            license=License.APACHE2,
            output_dir=tmp_path,
        )
        rendered = render_all_templates(config)
        assert "Apache License" in rendered[Path("LICENSE")]

    def test_gpl_license_content(self, tmp_path: Path) -> None:
        config = ProjectConfig(
            name="lictest",
            license=License.GPL3,
            output_dir=tmp_path,
        )
        rendered = render_all_templates(config)
        assert "GNU GENERAL PUBLIC LICENSE" in rendered[Path("LICENSE")]


# =============================================================================
# Fix 2: Free-text fields must not break generated TOML / Python files
# =============================================================================

NASTY = 'Has "quotes", {braces}, a \\ backslash and """ triple-quotes'


class TestTemplateInjection:
    """Special characters in description/author must not break output."""

    def _config(self, tmp_path: Path, project_type: ProjectType) -> ProjectConfig:
        return ProjectConfig(
            name="injtest",
            description=NASTY,
            project_type=project_type,
            author=AuthorInfo(name='Evil "Name" {x}'),
            output_dir=tmp_path,
        )

    @pytest.mark.parametrize(
        "project_type",
        [ProjectType.LIBRARY, ProjectType.CLI, ProjectType.API],
    )
    def test_generated_project_validates(
        self, tmp_path: Path, project_type: ProjectType
    ) -> None:
        config = self._config(tmp_path, project_type)

        # Write the rendered project to disk the way create_project does.
        config.project_dir.mkdir(parents=True)
        rendered = render_all_templates(config)
        for rel, content in rendered.items():
            full = config.project_dir / rel
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")

        # Every generated Python file must compile.
        for py_file in config.project_dir.rglob("*.py"):
            compile(py_file.read_text(encoding="utf-8"), str(py_file), "exec")

        # pyproject.toml must be valid TOML and round-trip the description.
        with (config.project_dir / "pyproject.toml").open("rb") as f:
            data = tomllib.load(f)
        assert data["project"]["description"] == NASTY

    def test_pyproject_author_name_round_trips(self, tmp_path: Path) -> None:
        config = self._config(tmp_path, ProjectType.LIBRARY)
        content = render_template(create_jinja_env(), "pyproject.toml.j2", config)
        data = tomllib.loads(content)
        assert data["project"]["authors"][0]["name"] == 'Evil "Name" {x}'


# =============================================================================
# Fix 3: Valid PyPI trove classifier + SPDX id for every license
# =============================================================================


class TestLicenseMetadata:
    """License enum must expose correct trove classifiers and SPDX ids."""

    def test_every_license_has_a_classifier(self) -> None:
        for lic in License:
            assert lic.classifier.startswith("License :: ")

    def test_apache_classifier(self) -> None:
        assert License.APACHE2.classifier == (
            "License :: OSI Approved :: Apache Software License"
        )

    def test_bsd_classifier(self) -> None:
        assert License.BSD3.classifier == "License :: OSI Approved :: BSD License"

    def test_proprietary_is_not_marked_osi_approved(self) -> None:
        assert "OSI Approved" not in License.PROPRIETARY.classifier

    def test_proprietary_spdx_is_valid_reference(self) -> None:
        # "Proprietary" is not a valid SPDX expression; use a LicenseRef.
        assert License.PROPRIETARY.spdx_id == "LicenseRef-Proprietary"

    def test_generated_classifier_in_pyproject(self, tmp_path: Path) -> None:
        config = ProjectConfig(
            name="clstest",
            license=License.APACHE2,
            output_dir=tmp_path,
        )
        content = render_template(create_jinja_env(), "pyproject.toml.j2", config)
        data = tomllib.loads(content)
        assert (
            "License :: OSI Approved :: Apache Software License"
            in data["project"]["classifiers"]
        )


# =============================================================================
# Fix 4: CI detection must recognise .yaml workflow files
# =============================================================================


class TestDetectCiYaml:
    def test_detects_github_actions_with_yaml_extension(self, tmp_path: Path) -> None:
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yaml").write_text("name: CI")

        ci, _info = detect_ci(tmp_path)
        assert ci == "github-actions"


# =============================================================================
# Fix 5: load_project_config must detect API and app project types
# =============================================================================


class TestLoadProjectConfigType:
    def test_detects_api_from_dependencies(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\n"
            'name = "svc"\n'
            'version = "0.1.0"\n'
            'dependencies = ["fastapi>=0.115", "uvicorn>=0.32"]\n'
        )
        config = load_project_config(tmp_path)
        assert config.project_type == ProjectType.API

    def test_detects_cli_from_scripts(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\n"
            'name = "tool"\n'
            'version = "0.1.0"\n'
            "[project.scripts]\n"
            'tool = "tool.cli:app"\n'
        )
        config = load_project_config(tmp_path)
        assert config.project_type == ProjectType.CLI


# =============================================================================
# Fix 7: requirements.txt migration must warn about skipped -r/-e lines
# =============================================================================


class TestRequirementsMigrationWarnings:
    def test_warns_on_skipped_include_lines(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("requests>=2.0\n-r base.txt\n-e .\n")
        changes = _migrate_requirements_to_uv(tmp_path, dry_run=True)
        joined = " ".join(changes).lower()
        assert "skip" in joined
        assert "-r base.txt" in joined or "-e ." in joined


# =============================================================================
# Fix 8: Poetry migration must handle a table-form python requirement
# =============================================================================


class TestPoetryPythonDictSpec:
    def test_table_form_python_requirement(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.poetry]\n"
            'name = "demo"\n'
            'version = "0.1.0"\n'
            "[tool.poetry.dependencies]\n"
            'python = { version = "^3.11" }\n'
        )
        # Must not raise AttributeError on the dict-form spec.
        changes = _migrate_poetry_to_uv(tmp_path, dry_run=True)
        assert any(">=3.11" in c for c in changes)


# =============================================================================
# Fix 9: git init must respect a configured user identity
# =============================================================================


class TestGitAuthorIdentity:
    def _make_run(self, *, has_identity: bool):
        """Build a fake subprocess.run that records the commit invocation."""
        calls: list[dict] = []

        class _Result:
            returncode = 0

            def __init__(self, stdout: str = "") -> None:
                self.stdout = stdout

        def fake_run(cmd, *args, **kwargs):
            calls.append({"cmd": cmd, "kwargs": kwargs})
            if cmd[:2] == ["git", "config"]:
                return _Result("Real User" if has_identity else "")
            return _Result("")

        return fake_run, calls

    def test_does_not_override_configured_identity(self, tmp_path: Path) -> None:
        fake_run, calls = self._make_run(has_identity=True)
        with patch("quickforge.generator.subprocess.run", side_effect=fake_run):
            init_git_repository(tmp_path)

        commit_calls = [c for c in calls if c["cmd"][:2] == ["git", "commit"]]
        assert commit_calls, "git commit was never invoked"
        env = commit_calls[0]["kwargs"].get("env")
        if env is not None:
            assert env.get("GIT_AUTHOR_EMAIL") != "quickforge@example.com"

    def test_falls_back_when_no_identity(self, tmp_path: Path) -> None:
        fake_run, calls = self._make_run(has_identity=False)
        with patch("quickforge.generator.subprocess.run", side_effect=fake_run):
            init_git_repository(tmp_path)

        commit_calls = [c for c in calls if c["cmd"][:2] == ["git", "commit"]]
        assert commit_calls, "git commit was never invoked"
        env = commit_calls[0]["kwargs"].get("env")
        assert env is not None
        assert env.get("GIT_AUTHOR_EMAIL") == "quickforge@example.com"
