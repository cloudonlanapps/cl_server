# CL Server Package Structure Template

This document defines the standard structure for CL Server packages. Use this as a reference when creating new services or libraries.

## Directory Layout

```
package-name/
├── src/package_name/      # Main source code
│   ├── __init__.py        # Public API exports
│   ├── main.py            # CLI entry point (optional)
│   ├── models.py          # Database models (if applicable)
│   └── ...
├── tests/                 # Test suite
│   ├── conftest.py        # Pytest fixtures
│   ├── test_*.py          # Test files
│   └── README.md          # Test documentation
├── alembic/               # Database migrations (if applicable)
│   ├── versions/
│   └── env.py
├── pyproject.toml         # Package configuration
├── README.md              # User documentation
├── INTERNALS.md           # Developer documentation
└── CLAUDE.md              # AI assistant instructions (optional)
```

## Mandatory Files

### 1. `README.md` (User-facing)
**Purpose:** End-user documentation for installing and using the package.

**Must contain:**
- Quick start (installation, basic usage)
- Environment variables
- API/CLI reference
- Troubleshooting
- Examples

**Must NOT contain:**
- Development workflows
- Package internals
- Contribution guidelines

### 2. `INTERNALS.md` (Developer-facing)
**Purpose:** Developer documentation for contributors.

**Must contain:**
- Package structure explanation
- Development setup
- Testing instructions (link to tests/README.md)
- Code quality tools (linting, formatting)
- Development workflow
- Architecture notes
- Future enhancements/roadmap
- Contributing guidelines

### 3. `tests/README.md` (Testing-specific)
**Purpose:** Detailed testing documentation.

**Must contain:**
- Prerequisites (Python version, uv)
- How to run tests (`uv run pytest`)
- Coverage requirements
- Test file organization
- Example commands (all tests, specific files, individual tests)

### 4. `pyproject.toml`
**Must configure:**
- Package metadata (name, version, description)
- Dependencies
- Build system (hatchling/setuptools)
- Entry points for CLI scripts
- Tool configurations (pytest, ruff, coverage)

### 5. `src/package_name/__init__.py`
**Purpose:** Define public API.

**Pattern:**
```python
from .module import PublicClass, public_function

__all__ = ["PublicClass", "public_function"]
```

## Test Organization

### File Naming
- `conftest.py` - Shared fixtures
- `test_<feature>.py` - Feature-specific tests
- Prefix all test functions with `test_`

### Structure Pattern
```
tests/
├── conftest.py              # Fixtures (DB sessions, clients, mock data)
├── test_core.py             # Core functionality
├── test_api.py              # API endpoints (if applicable)
├── test_integration.py      # Integration tests
└── README.md                # How to run tests
```

### Test Requirements
- Use pytest as test runner
- Set minimum coverage threshold (e.g., 90%)
- Use in-memory databases for DB tests
- Isolate tests (no shared state)
- Mock external dependencies

## Development Commands Standard

All packages should support these commands:

```bash
# Installation
uv sync                              # Install dependencies

# Testing
uv run pytest                        # Run all tests
uv run pytest tests/test_file.py -v # Run specific test
uv run pytest --no-cov               # Quick test without coverage

# Code Quality
uv run ruff check src/               # Lint
uv run ruff format src/              # Format

# Dependencies
uv add package-name                  # Add dependency
uv add --dev package-name            # Add dev dependency
```

## Environment Variables Pattern

- `CL_SERVER_DIR` - Required base directory for all services
- `<SERVICE>_DATABASE_URL` - Database connection (if applicable)
- `LOG_LEVEL` - Logging level (default: INFO)
- Service-specific variables should be prefixed

## Documentation Cross-References

### In README.md
```markdown
> **For Developers:** See [INTERNALS.md](INTERNALS.md) for development setup.
```

### In INTERNALS.md
```markdown
### Running Tests
See [tests/README.md](tests/README.md) for detailed testing information.
```

## Optional Files

- `CLAUDE.md` - Instructions for Claude Code assistant
- `alembic/` - Only if package uses database migrations
- `.env.example` - Example environment variables
- `Dockerfile` - For containerized services

## Package Manager

**Standard:** uv (required)
- No manual venv creation
- All commands via `uv run`
- Dependencies managed in `pyproject.toml`

## Key Principles

1. **Separation of Concerns:** User docs (README.md) ≠ Developer docs (INTERNALS.md)
2. **Single Source of Truth:** Don't duplicate information between files
3. **uv-First:** All commands use `uv run`, no manual environment activation
4. **Test Coverage:** Maintain high coverage (≥90% recommended)
5. **Consistent Structure:** Follow this template for all packages
