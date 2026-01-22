# CL Server

A distributed microservices platform for media processing, machine learning inference, and content management.

**Architecture:** Microservices (Auth, Store, Compute)
**Package Manager:** uv
**Python Version:** 3.12+
**Database:** SQLite with WAL mode
**Authentication:** JWT ES256 (ECDSA)

> **Architecture:** See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for comprehensive system architecture, service communication patterns, and integration points.

## Overview

This repository acts as a **workspace / umbrella project** that aggregates multiple independent services, SDKs, and applications using **Git submodules**.

**Core Services:**
- **Auth Service (Port 8000)** - JWT authentication and user management
- **Store Service (Port 8001)** - Media entity management, job orchestration, versioning
- **Compute Service (Port 8002)** - Job execution, worker management, plugin system

**SDKs:**
- **Python SDK (cl-client)** - Async client library with MQTT support
- **Dart SDK** - Flutter/Dart client library

**Applications:**
- **CLI Python App** - Command-line interface for all services
- **CLI Dart App** - Dart-based command-line interface
- **Flutter App** - Mobile and desktop application

**Infrastructure:**
- **cl_server_shared** - Shared models and utilities
- **cl_ml_tools** - Machine learning plugin system

## Features

- 🔐 **JWT Authentication** - Secure ES256 token-based authentication
- 📦 **Media Management** - Entity CRUD with versioning and duplicate detection
- 🤖 **ML Inference** - 9 built-in plugins (CLIP, DINO, face detection, etc.)
- 📡 **Real-time Updates** - MQTT-based job progress monitoring
- 🔌 **Plugin System** - Extensible compute tasks via entry points
- 📊 **Job Orchestration** - Queue-based job management with worker coordination
- 🗄️ **Versioning** - Full audit trail with SQLAlchemy-Continuum
- 🧪 **High Test Coverage** - 90%+ coverage across services

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Git (for submodules)
- MQTT broker (optional, for real-time features)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Set required environment variable
export CL_SERVER_DIR=~/.data/cl_server_data
mkdir -p $CL_SERVER_DIR
```

### Workspace Installation

**Option 1: Clone with Submodules**

```bash
# Clone repository with all submodules
git clone --recurse-submodules git@github.com:cloudonlanapps/cl_server.git
cd cl_server

# Install all packages in workspace
./install.sh
```

**Option 2: Clone then Initialize Submodules**

```bash
# Clone repository
git clone git@github.com:cloudonlanapps/cl_server.git
cd cl_server

# Initialize and update submodules
git submodule update --init --recursive

# Install all packages in workspace
./install.sh
```

**What install.sh Does:**
- Installs all services (auth, store, compute)
- Installs Python SDK (pysdk)
- Installs CLI Python app
- Installs cl_ml_tools plugin system
- Installs all in editable mode with development dependencies

### Individual Package Installation

You can also install packages individually. See each package's README for details:

- **[Auth Service](services/auth/README.md)** - `cd services/auth && uv sync`
- **[Store Service](services/store/README.md)** - `cd services/store && uv sync`
- **[Compute Service](services/compute/README.md)** - `cd services/compute && uv sync`
- **[Python SDK](sdks/pysdk/README.md)** - `cd sdks/pysdk && uv sync`
- **[CLI Python App](apps/cli_python/README.md)** - `cd apps/cli_python && uv sync`

### Running Services

**1. Start Auth Service**

```bash
cd services/auth
uv run alembic upgrade head  # Run migrations
uv run auth-server --reload   # Start with auto-reload
```

Service available at: http://localhost:8000

**2. Start Store Service**

```bash
cd services/store
uv run alembic upgrade head  # Run migrations
uv run store --reload        # Start with auto-reload
```

Service available at: http://localhost:8001

**3. Start Compute Service**

```bash
cd services/compute
uv run compute-migrate       # Run migrations
uv run compute-server --reload  # Start with auto-reload
```

Service available at: http://localhost:8002

**4. Start Compute Worker**

```bash
cd services/compute
uv run compute-worker --worker-id worker-1
```

### Using the CLI

```bash
cd apps/cli_python

# Submit a CLIP embedding job
uv run cl-client clip-embedding embed photo.jpg --watch --output embedding.npy
```

## Repository Structure

### Services

| Directory | Description | Port | Documentation |
|-----------|-------------|------|---------------|
| `services/auth` | Authentication service | 8000 | [README](services/auth/README.md) |
| `services/store` | Media entity management | 8001 | [README](services/store/README.md) |
| `services/compute` | Job execution service | 8002 | [README](services/compute/README.md) |
| `services/shared` | Shared models and utilities | N/A | Imported by services |

### SDKs

| Directory | Description | Documentation |
|-----------|-------------|---------------|
| `sdks/pysdk` | Python client library | [README](sdks/pysdk/README.md) |
| `sdks/dartsdk` | Dart/Flutter client library | [README](sdks/dartsdk/README.md) |

### Applications

| Directory | Description | Documentation |
|-----------|-------------|---------------|
| `apps/cli_python` | Python CLI tool | [README](apps/cli_python/README.md) |
| `apps/cli_dart` | Dart CLI tool | TBD |
| `apps/flutter_app` | Flutter mobile/desktop app | TBD |

### Infrastructure

| Directory | Description |
|-----------|-------------|
| `services/packages/cl_ml_tools` | ML plugin system |
| `dockers` | Docker configurations |
| `docs` | System-wide documentation |

## Git Submodules

### Submodule Mapping

| Repository | Local Path |
|-----------|-----------|
| `git@github.com:cloudonlanapps/cl_server_dockers.git` | `dockers` |
| `git@github.com:cloudonlanapps/cl_server_auth_service.git` | `services/auth` |
| `git@github.com:cloudonlanapps/cl_server_compute_service.git` | `services/compute` |
| `git@github.com:cloudonlanapps/cl_server_store_service.git` | `services/store` |
| `git@github.com:cloudonlanapps/cl_server_shared.git` | `services/shared` |
| `git@github.com:cloudonlanapps/cl_server_sdk_python.git` | `clients/python` |
| `git@github.com:cloudonlanapps/cl_server_sdk_dart.git` | `clients/dart` |

Command

```bash
git submodule add -b main git@github.com:cloudonlanapps/cl_server_dockers.git dockers
git submodule add -b main git@github.com:cloudonlanapps/cl_server_auth_service.git services/auth
git submodule add -b main git@github.com:cloudonlanapps/cl_server_compute_service.git services/compute
git submodule add -b main git@github.com:cloudonlanapps/cl_server_store_service.git services/store
git submodule add -b main git@github.com:cloudonlanapps/cl_server_shared.git services/shared
git submodule add -b main git@github.com:cloudonlanapps/cl_server_sdk_python.git clients/python
git submodule add -b main git@github.com:cloudonlanapps/cl_server_sdk_dart.git clients/dart
```


### Cloning the Workspace

To clone this repository **with all submodules**:

```bash
git clone --recurse-submodules git@github.com:cloudonlanapps/cl_server.git
```

If already cloned:

```bash
git submodule update --init --recursive
```

Update a single submodule:

```bash
git submodule update --remote services/auth
```


### Keeping Submodules in Sync

All submodules are configured to track the `main` branch.

To update **all submodules** to the latest `main`:

```bash
git submodule update --remote --merge
git commit -am "Update submodules to latest main"
```

### Update a Single Submodule

```bash
# Update specific submodule to latest
git submodule update --remote services/auth

# Or update and merge
cd services/auth
git pull origin main
cd ../..
git add services/auth
git commit -m "Update auth service submodule"
```

## Documentation

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System-wide architecture, service communication, data flow
- **[ISSUES.md](docs/ISSUES.md)** - Documentation issues and standardization tracking

### Service Documentation
- **[Auth Service](services/auth/README.md)** - Authentication API and user management
- **[Store Service](services/store/README.md)** - Media entity management API
- **[Compute Service](services/compute/README.md)** - Job execution and worker management

### SDK Documentation
- **[Python SDK](sdks/pysdk/README.md)** - Python client library
- **[CLI Python App](apps/cli_python/README.md)** - Command-line interface

## Development

### Running Tests

**All Services:**
```bash
# Run tests for each service
cd services/auth && uv run pytest
cd services/store && uv run pytest
cd services/compute && uv run pytest
```

**SDKs:**
```bash
# Python SDK tests
cd sdks/pysdk && uv run pytest

# CLI Python app tests
cd apps/cli_python && uv run pytest tests/test_cli.py
```

### Code Quality

Each package includes code quality tools:

```bash
# Format code
uv run ruff format src/

# Lint code
uv run ruff check src/

# Type checking
uv run basedpyright
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and code quality checks
5. Submit a pull request

**Standards:**
- Maintain 90%+ test coverage
- Use ruff for formatting and linting
- Use basedpyright for type checking
- Follow existing code patterns
- Update documentation for user-facing changes

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: See individual package READMEs and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Issues**: Report at project issue tracker
- **Architecture Questions**: See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Version

- **Platform Version**: 0.1.0
- **Python**: 3.12+
- **Package Manager**: uv


