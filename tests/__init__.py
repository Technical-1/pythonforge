"""
pyinit test suite
=================

This package contains comprehensive tests for pyinit.

Test Modules
------------
- test_models.py: Tests for Pydantic configuration models
- test_generator.py: Tests for project generation logic
- test_cli.py: Tests for command-line interface

Running Tests
-------------
    # Run all tests
    pytest

    # Run with coverage
    pytest --cov=src/pyinit

    # Run specific module
    pytest tests/test_models.py

    # Run specific test class
    pytest tests/test_models.py::TestProjectConfig

    # Run specific test
    pytest tests/test_models.py::TestProjectConfig::test_minimal_config
"""
