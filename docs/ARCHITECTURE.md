# CL Server - System Architecture

This document describes the overall architecture of the CL Server platform, including microservices, SDKs, communication patterns, and integration points.

## Overview

CL Server is a distributed microservices platform for media processing, machine learning inference, and content management. The system consists of three core services (Auth, Store, Compute), client SDKs, and a plugin architecture for extensibility.

**Key Characteristics:**
- **Microservices Architecture**: Independent services with clear boundaries
- **JWT Authentication**: ES256 (ECDSA) token-based authentication
- **MQTT Integration**: Real-time job progress and worker coordination
- **Plugin System**: Extensible compute tasks via cl_ml_tools
- **SQLite + WAL**: Simple, reliable persistence with concurrent access
- **Python 3.12+**: Modern Python with type safety

## System Components

### Core Services

#### 1. Auth Service (Port 8000)
**Purpose:** Authentication and user management

**Responsibilities:**
- JWT token generation and validation (ES256 algorithm)
- User CRUD operations
- Role-based access control (RBAC)
- Permission management
- Public key distribution for token verification

**Technology:**
- FastAPI
- SQLite with WAL mode
- SQLAlchemy with shared Base
- Alembic for migrations
- bcrypt for password hashing
- python-jose for JWT

**Key Endpoints:**
- `POST /auth/token` - Login and token generation
- `POST /auth/token/refresh` - Token refresh
- `GET /auth/public-key` - Public key for other services
- `GET /users/me` - Current user info
- `POST /users/` - Create user (admin only)
- `GET /users/` - List users (admin only)
- `PUT /users/{id}` - Update user (admin only)
- `DELETE /users/{id}` - Delete user (admin only)

**Database:**
- Location: `$CL_SERVER_DIR/user_auth.db`
- Schema: Users table with permissions, admin flag, active status
- Migrations: Alembic

**Authentication Flow:**
1. Client sends credentials to `/auth/token`
2. Auth service validates credentials
3. Returns JWT token with user ID, permissions, admin flag
4. Client includes token in subsequent requests to other services
5. Services validate token using public key from `/auth/public-key`

---

#### 2. Store Service (Port 8001)
**Purpose:** Media entity and job management

**Responsibilities:**
- Media entity CRUD (images, videos)
- File storage and retrieval
- Duplicate detection (MD5-based)
- Metadata extraction
- Job orchestration for compute tasks
- Entity versioning (SQLAlchemy-Continuum)
- mInsight worker coordination via MQTT

**Technology:**
- FastAPI
- SQLite with WAL mode
- SQLAlchemy with SQLAlchemy-Continuum for versioning
- Alembic for migrations
- MQTT for worker coordination
- File storage in `$CL_SERVER_DIR/media` and `$CL_SERVER_DIR/compute`

**Key Endpoints:**
- `GET /entities` - List entities with pagination
- `POST /entities` - Create entity with file upload
- `GET /entities/{id}` - Get entity by ID
- `PUT /entities/{id}` - Update entity
- `PATCH /entities/{id}` - Partial update
- `DELETE /entities/{id}` - Soft delete entity
- `GET /entities/{id}/versions` - Entity version history
- `POST /compute/jobs/{plugin}` - Create compute job (plugin-specific routes)
- `GET /jobs/{id}` - Get job status
- `DELETE /jobs/{id}` - Delete job

**Database:**
- Location: `$CL_SERVER_DIR/store.db`
- Schema: Entities, Jobs, QueueEntries with versioning
- Migrations: Alembic
- Versioning: SQLAlchemy-Continuum tracks entity changes

**Authentication Modes:**
- `--no-auth` CLI flag: No authentication required
- Default mode: Write operations require token, reads are public
- `READ_AUTH_ENABLED=true`: All operations require token

**File Storage:**
- Media files: `$CL_SERVER_DIR/media` (MD5-based deduplication)
- Job files: `$CL_SERVER_DIR/compute` (input/output per job)
- Original filenames preserved with metadata

**MQTT Integration:**
- Configured via `--mqtt-server` and `--mqtt-port` CLI options
- Broadcasts job status updates when MQTT is enabled
- mInsight worker subscribes to job updates

---

#### 3. Compute Service (Port 8002)
**Purpose:** Compute job execution and worker management

**Responsibilities:**
- Job lifecycle management
- Worker capability discovery via MQTT
- Plugin-based task execution
- Job queue management
- Storage management for job files

**Technology:**
- FastAPI
- SQLite with WAL mode (shared with Store via WORKER_DATABASE_URL)
- SQLAlchemy with shared models (Job, QueueEntry from cl_server_shared)
- Alembic for migrations
- MQTT for worker capabilities
- cl_ml_tools plugin system

**Key Endpoints:**
- `GET /jobs/{id}` - Get job status and results
- `DELETE /jobs/{id}` - Delete job and files
- `GET /capabilities` - Get available worker capabilities
- `GET /admin/jobs/storage/size` - Get storage usage
- `DELETE /admin/jobs/cleanup?days=7` - Cleanup old jobs
- Plugin endpoints (dynamically registered): `/compute/jobs/{plugin_name}`

**Database:**
- Location: Shared with Store service (`$CL_SERVER_DIR/store.db`)
- Schema: Jobs, QueueEntries (shared models from cl_server_shared)
- Migrations: `compute-migrate` command

**Worker Architecture:**
- Workers poll job repository for available jobs
- Use `cl_ml_tools.Worker.run_once()` for atomic job claiming
- Execute tasks in-process using registered plugins
- Update job status and progress via repository
- Publish capabilities to MQTT periodically

**Plugin System:**
- Plugins register via `pyproject.toml` entry points
- Entry point group: `cl_ml_tools.tasks`
- `create_master_router()` creates plugin routes
- Worker auto-discovers plugins using `get_task_registry()`

**Built-in Plugins (via cl_ml_tools):**
- clip_embedding - CLIP image embeddings
- dino_embedding - DINO image embeddings
- exif - EXIF metadata extraction
- face_detection - Face detection in images
- face_embedding - Face recognition embeddings
- hash - Perceptual image hashing
- hls_streaming - HLS video streaming
- image_conversion - Image format conversion
- media_thumbnail - Media thumbnail generation

---

### Client SDKs

#### Python SDK (cl-client)
**Purpose:** Python client library for CL Server services

**Features:**
- Async/await support (httpx)
- Real-time MQTT monitoring with callbacks
- HTTP polling fallback
- Type-safe (strict basedpyright)
- Modular authentication (no-auth, JWT)
- All 9 plugin integrations

**Components:**
- `ComputeClient` - Compute service client
- `SessionManager` - High-level auth management with auto token refresh
- `AuthClient` - Auth service client
- `StoreClient` - Store service client
- `MQTTMonitor` - MQTT-based job monitoring
- Plugin clients (e.g., `clip_embedding`, `exif`, etc.)

**Authentication:**
- No-auth mode (default): Direct client usage
- JWT mode: SessionManager handles login, token refresh, logout

**Configuration:**
- `ServerConfig` - Centralized server URLs and MQTT settings
- Environment variables or programmatic config
- Defaults: Auth (8000), Compute (8002), Store (8001), MQTT (localhost:1883)

---

#### CLI Python App (cl-client CLI)
**Purpose:** Command-line interface for CL Server

**Features:**
- All 9 plugin commands
- Real-time progress with `--watch` flag
- Automatic downloads with `--output` flag
- Rich terminal formatting
- Built on cl-client SDK

**Commands:**
- `cl-client clip-embedding embed` - CLIP embeddings
- `cl-client dino-embedding embed` - DINO embeddings
- `cl-client exif extract` - EXIF extraction
- `cl-client face-detection detect` - Face detection
- `cl-client face-embedding embed` - Face embeddings
- `cl-client hash compute` - Perceptual hashing
- `cl-client hls-streaming generate-manifest` - HLS manifest
- `cl-client image-conversion convert` - Image conversion
- `cl-client media-thumbnail generate` - Thumbnail generation
- `cl-client download` - Download job files

---

### Shared Infrastructure

#### cl_server_shared
**Purpose:** Shared code and models across services

**Contents:**
- SQLAlchemy Base class (declarative base)
- Shared models: Job, QueueEntry
- Common configuration (Config class)
- Shared utilities

**Usage:**
- All services import from `cl_server_shared.models`
- Ensures consistent database schema
- Single source of truth for shared entities

---

#### cl_ml_tools
**Purpose:** Machine learning plugin system

**Features:**
- Plugin registration via entry points
- Task registry and discovery
- Worker execution engine
- MQTT broadcaster for capabilities
- Job claiming and execution

**Plugin Structure:**
- Each plugin implements task interface
- Pydantic models for parameters
- Input/output file handling
- Progress reporting

---

## Communication Patterns

### Service-to-Service Communication

#### Auth → Other Services
**Flow:** Public key distribution
1. Other services fetch public key from Auth service on startup
2. Auth service exposes `GET /auth/public-key` endpoint
3. Services cache public key for token validation
4. Tokens are stateless - no session storage required

**Endpoints Used:**
- Auth: `GET /auth/public-key` (public, no auth)

---

#### Store → Compute
**Flow:** Job creation and tracking
1. Store service creates job record in shared database
2. Store service adds entry to job queue
3. Compute workers poll job queue
4. Workers claim and execute jobs
5. Workers update job status in shared database
6. Store service monitors job status via database

**Integration:**
- Shared database: `$CL_SERVER_DIR/store.db`
- Shared models: Job, QueueEntry from cl_server_shared
- No direct HTTP calls between services
- Database acts as message queue

---

#### MQTT-Based Communication
**Flow:** Real-time updates and worker coordination

**Participants:**
- Store service (publisher when MQTT enabled)
- Compute workers (publishers for capabilities)
- Clients (subscribers for job updates)
- mInsight worker (subscriber for job updates)

**Topics:**
- Job updates: `job/status/{job_id}`
- Worker capabilities: `worker/capabilities/{worker_id}`

**Message Flow:**
1. Worker publishes capabilities on startup and periodically
2. Compute service subscribes to capability topics
3. Store service publishes job status updates (when MQTT enabled)
4. Clients subscribe to job updates for real-time progress

---

### Client-to-Service Communication

#### Authentication Flow
1. Client sends credentials to Auth service
2. Receives JWT token
3. Includes token in Authorization header for subsequent requests
4. Token validated by services using public key from Auth

#### Job Submission Flow (via Python SDK)
**Polling Mode:**
1. Client calls `client.clip_embedding.embed_image(image, wait=True)`
2. SDK submits job to Compute service
3. SDK polls job status via HTTP until completion
4. Returns completed job with results

**Watch Mode (MQTT):**
1. Client calls `client.clip_embedding.embed_image(image, on_complete=callback)`
2. SDK submits job to Compute service
3. SDK subscribes to MQTT topic for job updates
4. Receives real-time progress updates
5. Calls callback when job completes

---

## Data Flow

### Media Upload and Processing

```
1. Client uploads image
   ↓
2. Store service creates entity
   ↓
3. Store service saves file to $CL_SERVER_DIR/media
   ↓
4. Store service checks for duplicates (MD5)
   ↓
5. Store service extracts metadata
   ↓
6. Store service returns entity ID
   ↓
7. Client requests compute job (e.g., CLIP embedding)
   ↓
8. Store service creates job in database
   ↓
9. Store service adds to job queue
   ↓
10. Compute worker claims job
   ↓
11. Compute worker executes plugin
   ↓
12. Compute worker saves result to $CL_SERVER_DIR/compute
   ↓
13. Compute worker updates job status
   ↓
14. Client polls or receives MQTT notification
   ↓
15. Client downloads result file
```

---

### Job Lifecycle

```
1. PENDING - Job created, waiting in queue
   ↓
2. CLAIMED - Worker claimed job
   ↓
3. PROCESSING - Worker executing task
   ↓
4a. COMPLETED - Task succeeded
   OR
4b. FAILED - Task failed
```

**State Transitions:**
- PENDING → CLAIMED (worker claims job)
- CLAIMED → PROCESSING (worker starts execution)
- PROCESSING → COMPLETED (success)
- PROCESSING → FAILED (error)

---

## Database Architecture

### Auth Service Database
**File:** `$CL_SERVER_DIR/user_auth.db`

**Tables:**
- `users` - User records with credentials, permissions, admin flag
- `alembic_version` - Migration tracking

**Indexes:**
- Unique index on username

---

### Store Service Database
**File:** `$CL_SERVER_DIR/store.db`

**Tables:**
- `entities` - Media entities with metadata
- `entity_version` - Entity version history (SQLAlchemy-Continuum)
- `transaction` - Version transaction tracking (SQLAlchemy-Continuum)
- `jobs` - Compute jobs (shared with Compute)
- `queue_entries` - Job queue (shared with Compute)
- `alembic_version` - Migration tracking

**Indexes:**
- MD5 hash for duplicate detection
- Entity IDs for fast lookups

**Versioning:**
- SQLAlchemy-Continuum tracks all entity changes
- Each update creates new version record
- Full audit trail available

---

### Compute Service Database
**File:** Same as Store (`$CL_SERVER_DIR/store.db`)

**Shared Tables:**
- `jobs` - Job records
- `queue_entries` - Job queue
- `alembic_version` - Migration tracking

**Why Shared?**
- Store and Compute need coordinated access to job data
- Eliminates need for service-to-service HTTP calls
- Database acts as message queue
- SQLite WAL mode allows concurrent access

---

## File Storage

### Directory Structure
```
$CL_SERVER_DIR/
├── media/                    # Media entity files
│   └── {md5}/               # MD5-based organization
│       └── {filename}       # Original filename preserved
├── compute/                 # Job files
│   └── {job_id}/           # Per-job directory
│       ├── input/          # Input files
│       └── output/         # Output files
├── user_auth.db            # Auth database
├── store.db                # Store/Compute shared database
├── private_key.pem         # Auth service private key
├── public_key.pem          # Auth service public key
└── run_logs/               # Service logs
```

---

## Security

### Authentication
- **Algorithm:** ES256 (ECDSA with SHA-256)
- **Key Management:** Auto-generated on first startup, stored in `$CL_SERVER_DIR`
- **Token Lifetime:** Configurable (default: 30 minutes)
- **Token Refresh:** Supported via `/auth/token/refresh`

### Authorization
**Permission Model:**
- Permissions stored as comma-separated strings
- Admin flag for privileged operations
- Per-service permission checks

**Common Permissions:**
- `media_store_read` - Read entities
- `media_store_write` - Modify entities
- `ai_inference_support` - Create compute jobs
- `admin` - Admin operations

### Password Security
- bcrypt hashing with salt
- Passwords never stored in plaintext
- No password recovery (admin must reset)

---

## Scalability Considerations

### Current Architecture
- Single-server deployment
- SQLite for simplicity
- Suitable for small to medium workloads

### Scaling Paths

**Horizontal Scaling (Workers):**
- ✅ Workers can be scaled independently
- ✅ Multiple workers can run concurrently
- ✅ MQTT coordinates worker capabilities
- ✅ Job queue prevents duplicate work

**Database Scaling:**
- Current: SQLite with WAL mode
- Future: Migrate to PostgreSQL for multi-server deployments
- Migration path: Update database URL, run Alembic migrations

**Service Scaling:**
- Current: Single instance per service
- Future: Load balancer + multiple instances (requires PostgreSQL)

---

## Deployment

### Development Setup
1. Set `CL_SERVER_DIR` environment variable
2. Run `./install.sh` to install all packages
3. Start services in order:
   - Auth service: `cd services/auth && uv run auth-server --reload`
   - Store service: `cd services/store && uv run store --reload`
   - Compute service: `cd services/compute && uv run compute-server --reload`
   - Compute worker: `cd services/compute && uv run compute-worker`

### Production Deployment
- Use systemd service files
- Configure MQTT broker (Mosquitto recommended)
- Set up reverse proxy (nginx)
- Configure TLS/SSL certificates
- Use environment-specific configuration

---

## Extension Points

### Adding New Compute Plugins
1. Create plugin class implementing task interface
2. Register in `pyproject.toml` under `[project.entry-points."cl_ml_tools.tasks"]`
3. Implement Pydantic model for parameters
4. Handle input/output files
5. Workers auto-discover plugin via entry points
6. Compute service auto-generates API route

### Adding New Services
1. Follow microservices pattern
2. Use shared models from cl_server_shared
3. Implement JWT authentication
4. Register routes in FastAPI app
5. Add Alembic migrations
6. Document in this architecture guide

---

## Monitoring and Observability

### Logs
- Service logs in `$CL_SERVER_DIR/run_logs`
- Structured logging (JSON recommended for production)
- Log levels configurable via CLI

### Metrics
- Job completion rates
- Worker utilization
- API endpoint latency
- Storage usage (available via admin endpoints)

### Health Checks
- Auth: `GET /` - Returns service status
- Store: `GET /` - Returns service status
- Compute: `GET /capabilities` - Returns worker capabilities

---

## Technology Stack Summary

| Component | Technologies |
|-----------|-------------|
| **Services** | FastAPI, uvicorn, Python 3.12+ |
| **Database** | SQLite with WAL mode, SQLAlchemy, Alembic |
| **Authentication** | JWT (ES256), bcrypt, python-jose |
| **Messaging** | MQTT (paho-mqtt) |
| **Storage** | File system (local storage) |
| **ML/Compute** | cl_ml_tools plugin system |
| **Testing** | pytest, pytest-cov, pytest-asyncio |
| **Type Checking** | basedpyright |
| **Linting** | ruff |
| **Package Manager** | uv |
| **Versioning** | SQLAlchemy-Continuum (Store service) |

---

## Future Enhancements

### Planned Features
- PostgreSQL support for multi-instance deployments
- Redis caching layer
- WebSocket support for real-time updates
- S3-compatible object storage
- Kubernetes deployment manifests
- Prometheus metrics export
- Distributed tracing (OpenTelemetry)
- Multi-tenant support

---

## References

### Service Documentation
- **[Auth Service](../services/auth/README.md)** - Authentication and user management
- **[Store Service](../services/store/README.md)** - Media entity and job management
- **[Compute Service](../services/compute/README.md)** - Job execution and worker management

### SDK Documentation
- **[Python SDK](../sdks/pysdk/README.md)** - Python client library
- **[CLI Python App](../apps/cli_python/README.md)** - Command-line interface

### Developer Guides
- **[Auth Service Internals](../services/auth/INTERNALS.md)**
- **[Store Service Internals](../services/store/INTERNALS.md)**
- **[Compute Service Internals](../services/compute/INTERNALS.md)**
- **[Python SDK Internals](../sdks/pysdk/INTERNALS.md)**

---

## Version History

- **v0.1.0** - Initial architecture document
- Platform consists of 3 microservices, Python SDK, and CLI app
- SQLite-based deployment for simplicity
- MQTT for real-time coordination
- Plugin-based compute system
