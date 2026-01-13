"""
pytest configuration and shared fixtures for pyinit tests.

This module provides fixtures and configuration used across all test modules.
Fixtures defined here are automatically available to all tests.

Fixtures
--------
temp_project_dir : Path
    A temporary directory that is cleaned up after each test.

sample_pyproject : str
    A sample pyproject.toml content for testing.
"""

import pytest
from pathlib import Path


@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Path:
    """
    Create a temporary directory for project creation tests.
    
    This fixture provides a clean temporary directory for each test.
    The directory is automatically cleaned up after the test completes.
    
    Yields
    ------
    Path
        Path to the temporary directory.
    """
    project_dir = tmp_path / "test_projects"
    project_dir.mkdir()
    return project_dir


@pytest.fixture
def sample_pyproject() -> str:
    """
    Provide sample pyproject.toml content for testing.
    
    Returns
    -------
    str
        A minimal but valid pyproject.toml content.
    """
    return '''
[project]
name = "sample-project"
version = "0.1.0"
description = "A sample project for testing"
requires-python = ">=3.11"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
'''


@pytest.fixture
def sample_python_file() -> str:
    """
    Provide sample Python file content for testing.
    
    Returns
    -------
    str
        Valid Python code for testing.
    """
    return '''
"""A sample module."""

def hello(name: str = "World") -> str:
    """Return a greeting."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(hello())
'''


# =============================================================================
# pytest Configuration
# =============================================================================

def pytest_configure(config: pytest.Config) -> None:
    """
    Configure pytest with custom markers.
    
    This function is called by pytest during startup to register
    custom markers used in our test suite.
    """
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests requiring external resources"
    )
