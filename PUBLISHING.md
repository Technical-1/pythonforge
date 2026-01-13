# Publishing pyhatch to PyPI

This guide covers how to publish pyhatch to PyPI so it can be installed with `pip install pyhatch`.

## Prerequisites

1. **PyPI Account**: Create accounts on:
   - [PyPI](https://pypi.org/account/register/) (production)
   - [TestPyPI](https://test.pypi.org/account/register/) (testing)

2. **API Tokens**: Generate API tokens for authentication:
   - PyPI: https://pypi.org/manage/account/token/
   - TestPyPI: https://test.pypi.org/manage/account/token/

## One-Time Setup

### 1. Install Build Tools

```bash
cd /Volumes/NO\ NAME/01_ACTIVE/Pypi/pyhatch

# Using uv (if available)
uv pip install build twine

# Or using pip
pip install build twine
```

### 2. Configure PyPI Credentials

Create or edit `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR_PYPI_API_TOKEN_HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR_TESTPYPI_API_TOKEN_HERE
```

**Security Note**: Set proper permissions: `chmod 600 ~/.pypirc`

## Building the Package

### 1. Clean Previous Builds

```bash
rm -rf dist/ build/ *.egg-info src/*.egg-info
```

### 2. Build Source Distribution and Wheel

```bash
python -m build
```

This creates:
- `dist/pyhatch-0.1.0.tar.gz` (source distribution)
- `dist/pyhatch-0.1.0-py3-none-any.whl` (wheel)

### 3. Verify the Build

```bash
# Check the contents
tar -tzf dist/pyhatch-0.1.0.tar.gz | head -20
unzip -l dist/pyhatch-0.1.0-py3-none-any.whl | head -20

# Validate with twine
twine check dist/*
```

## Publishing

### Option A: Test First (Recommended)

1. **Upload to TestPyPI**:
   ```bash
   twine upload --repository testpypi dist/*
   ```

2. **Test Installation**:
   ```bash
   # Create a fresh virtual environment
   python -m venv test_env
   source test_env/bin/activate  # or test_env\Scripts\activate on Windows

   # Install from TestPyPI
   pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ pyhatch

   # Test it works
   pyhatch --version
   pyhatch --help
   ```

3. **Upload to Production PyPI**:
   ```bash
   twine upload dist/*
   ```

### Option B: Direct to PyPI

```bash
twine upload dist/*
```

## Verifying the Release

After publishing:

```bash
# Install from PyPI
pip install pyhatch

# Verify installation
pyhatch --version
pyhatch new test-project --type library --yes
```

## Version Bumping

Before each release, update the version in:
1. `pyproject.toml`: `version = "X.Y.Z"`
2. `src/pyhatch/__init__.py`: `__version__ = "X.Y.Z"`

Follow [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

## GitHub Release (Optional)

After publishing to PyPI, create a GitHub release:

1. Tag the release:
   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0"
   git push origin v0.1.0
   ```

2. Create release on GitHub with release notes

## Automated Publishing with GitHub Actions

Add this workflow to `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write  # Required for trusted publishing

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install build tools
        run: pip install build

      - name: Build package
        run: python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        # Uses trusted publishing - no token needed!
```

To enable trusted publishing:
1. Go to PyPI → Your Projects → pyhatch → Settings → Publishing
2. Add GitHub as a trusted publisher:
   - Owner: `Technical-1`
   - Repository: `pyhatch`
   - Workflow: `publish.yml`

## Troubleshooting

### "Package already exists"
The version already exists on PyPI. Bump the version number.

### "Invalid API token"
Regenerate your API token and update `~/.pypirc`.

### "File too large"
Check that `.gitignore` excludes test files, `.venv`, etc.

### Package name taken
If `pyhatch` is already taken on PyPI, you'll need to choose a different name like `py-init` or `pyhatch-cli`.

## Quick Commands Reference

```bash
# Full release workflow
cd /Volumes/NO\ NAME/01_ACTIVE/Pypi/pyhatch
rm -rf dist/ build/
python -m build
twine check dist/*
twine upload --repository testpypi dist/*  # Test first
twine upload dist/*  # Production
```
