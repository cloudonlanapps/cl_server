# mInsight Cleanup Refactoring Plan

## Overview
This refactoring separates Store Server query functionality from mInsight compute processing, consolidates models, simplifies service initialization with proper singleton patterns, and improves code organization.

**No backward compatibility needed** - Breaking changes allowed.

---

## Phase 1: Configuration Consolidation

### 1.1 Create BaseConfig in common/config.py
**New File:** `services/store/src/store/common/config.py`

Create base configuration class with shared fields:
- `cl_server_dir`, `media_storage_dir`, `public_key_path`, `auth_disabled`
- `qdrant_url`, `qdrant_collections`, `mqtt_broker`, `mqtt_port`

### 1.2 Update StoreConfig
**File:** `services/store/src/store/store/config.py`

- Extend `BaseConfig`
- Keep only Store-specific: `server_port`
- Remove duplicate fields

### 1.3 Update MInsightConfig
**File:** `services/store/src/store/m_insight/config.py`

- Extend `BaseConfig`
- Add `media_storage_dir` (currently missing)
- Keep ML-specific: `auth_service_url`, `compute_service_url`, credentials, processing settings
- Remove duplicate fields

---

## Phase 2: Database Model Consolidation

### 2.1 Move intelligence models to common/models.py
**File:** `services/store/src/store/common/models.py`

Move from `m_insight/models.py`:
- `EntitySyncState`, `ImageIntelligence`, `Face`, `EntityJob`, `KnownPerson`, `FaceMatch`
- All SQLAlchemy models with `Base`

Keep in `m_insight/models.py`:
- Pydantic models: `EntityVersionData`, `MInsightStartPayload`, etc.

**Import updates needed:**
- `from store.m_insight.models import Face` → `from store.common.models import Face`
- Similar for all moved models

**Files affected:**
- `m_insight/m_insight_processor.py` (formerly worker.py)
- `m_insight/job_callbacks.py`
- `m_insight/retrieval_service.py`
- `m_insight/routes.py`
- `m_insight/job_service.py`
- All test files

### 2.2 Move EntityStorageService to common
**File:** `services/store/src/store/common/entity_storage.py`

Move `EntityStorageService` from `store/entity_storage.py` to `common/entity_storage.py` as it's shared infrastructure.

Update `__init__.py` to export it.

### 2.3 Add path resolution to EntityVersionData
**File:** `services/store/src/store/m_insight/models.py`

```python
def get_file_path(self, storage_service: EntityStorageService) -> Path:
    """Resolve absolute file path using storage service.

    Args:
        storage_service: EntityStorageService instance configured with media_dir

    Returns:
        Absolute Path to the file
    """
    if not self.file_path:
        raise ValueError(f"Entity {self.id} has no file_path")
    return storage_service.get_absolute_path(self.file_path)
```

### 2.4 Add path resolution to Face model
**File:** `services/store/src/store/common/models.py`

```python
def get_file_path(self, storage_service: EntityStorageService, entity: Entity | None = None) -> Path:
    """Resolve absolute file path using storage service.

    Args:
        storage_service: EntityStorageService instance configured with media_dir
        entity: Optional Entity/EntityVersionData for additional context (date field)

    Returns:
        Absolute Path to the face image file
    """
    if not self.file_path:
        raise ValueError(f"Face {self.id} has no file_path")
    return storage_service.get_absolute_path(self.file_path)
```

**Note:** Face paths don't need entity date reconstruction since face files are stored with their own paths. EntityStorageService just resolves relative → absolute.

---

## Phase 3: Vector Store Consolidation

### 3.1 Merge qdrant_image_store.py into vector_stores.py
**File:** `services/store/src/store/m_insight/vector_stores.py`

Changes:
- Rename `QdrantImageStore` → `QdrantVectorStore`
- Move entire class from `qdrant_image_store.py` into `vector_stores.py`
- **Make all vector dimensions configurable** - update singleton functions:
  - `get_clip_store(url, collection_name, vector_size=512)` - configurable (default 512)
  - `get_dino_store(url, collection_name, vector_size=384)` - configurable (default 384)
  - `get_face_store(url, collection_name, vector_size=512)` - configurable (default 512)
- Add vector_size to QdrantCollectionsConfig if needed

**Delete:** `services/store/src/store/m_insight/qdrant_image_store.py`

**Import updates:**
- `from .qdrant_image_store import QdrantImageStore` → `from .vector_stores import QdrantVectorStore`

**Files affected:**
- `m_insight/job_callbacks.py`
- `m_insight/retrieval_service.py`
- `m_insight/processing_service.py`
- Test files

---

## Phase 4: Rename worker.py to m_insight_processor.py

### 4.1 Rename file and class
**Current:** `services/store/src/store/m_insight/worker.py`
**New:** `services/store/src/store/m_insight/m_insight_processor.py`

Changes:
- Rename file: `worker.py` → `m_insight_processor.py`
- Rename class: `mInsight` → `MInsightProcessor`
- Update docstrings

**Import updates:**
- `from .m_insight.worker import mInsight` → `from .m_insight.m_insight_processor import MInsightProcessor`

**Files affected:**
- `m_insight_worker.py` (main entry point)
- `tests/test_m_insight_worker.py`
- `tests/test_m_insight_mqtt.py`

**Delete:** `services/store/src/store/m_insight/worker.py`

---

## Phase 5: JobSubmissionService Refactoring

### 5.1 Update ImageIntelligence model with job tracking
**File:** `services/store/src/store/common/models.py`

Add job ID fields to ImageIntelligence table:
```python
class ImageIntelligence(Base):
    # ... existing fields ...

    # Job tracking fields
    face_detection_job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    clip_job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    dino_job_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # Overall processing status
    processing_status: Mapped[str] = mapped_column(String, default="pending")  # pending, processing, completed, failed
```

**Note:** This requires an Alembic migration to add these columns.

### 5.2 Create JobSubmissionStatus Pydantic model
**File:** `services/store/src/store/m_insight/models.py`

```python
class JobSubmissionStatus(BaseModel):
    """Status of job submissions for an entity (return value)."""
    face_detection_job_id: str | None = None
    clip_job_id: str | None = None
    dino_job_id: str | None = None
```

This is the return value from `trigger_async_jobs()` that gets stored in ImageIntelligence.

### 5.4 Update JobSubmissionService methods
**File:** `services/store/src/store/m_insight/job_service.py`

Update method signatures to accept `EntityVersionData` and use `EntityStorageService`:
- `submit_face_detection(entity: EntityVersionData, on_complete_callback)` - resolve path using storage service
- `submit_clip_embedding(entity: EntityVersionData, on_complete_callback)` - resolve path using storage service
- `submit_dino_embedding(entity: EntityVersionData, on_complete_callback)` - resolve path using storage service
- `submit_face_embedding(face: Face, entity: EntityVersionData, on_complete_callback)` - pass both Face and EntityVersionData

Update constructor:
```python
def __init__(self, compute_client: ComputeClient, storage_service: EntityStorageService):
    self.compute_client = compute_client
    self.storage_service = storage_service
```

Use path resolution:
```python
# For entity files
file_path = entity.get_file_path(self.storage_service)

# For face files
face_path = face.get_file_path(self.storage_service, entity)
```

---

## Phase 6: IntelligenceProcessingService Singleton

### 6.1 Convert to proper singleton pattern
**File:** `services/store/src/store/m_insight/processing_service.py`

**Major changes:**
- Remove `_ensure_singletons()` complexity
- Create all services in factory method (since SessionManager.login() is async):

```python
@classmethod
async def create(cls, db: Session, config: MInsightConfig) -> 'IntelligenceProcessingService':
    """Factory method for async initialization."""
    instance = cls.__new__(cls)
    await instance._initialize(db, config)
    return instance

async def _initialize(self, db: Session, config: MInsightConfig):
    self.db = db
    self.config = config

    # Initialize Storage Service
    self.storage_service = EntityStorageService(str(config.media_storage_dir))

    # Initialize Compute Client & Session
    server_config = ServerConfig(...)
    self.compute_session = SessionManager(server_config=server_config)
    await self.compute_session.login(...)
    self.compute_client = self.compute_session.create_compute_client()

    # Initialize Vector Stores (all three in init)
    self.clip_store = get_clip_store(
        config.qdrant_url,
        config.qdrant_collections.clip,
        vector_size=512  # configurable
    )
    self.dino_store = get_dino_store(
        config.qdrant_url,
        config.qdrant_collections.dino,
        vector_size=384  # configurable
    )
    self.face_store = get_face_store(
        config.qdrant_url,
        config.qdrant_collections.face,
        vector_size=config.face_vector_size  # from config
    )

    # Initialize Services
    self.job_service = JobSubmissionService(self.compute_client, self.storage_service)
    self.callback_handler = JobCallbackHandler(
        self.compute_client,
        self.clip_store,
        self.dino_store,
        self.face_store,
        config=config,
        job_submission_service=self.job_service,
    )
```

### 6.2 Update trigger_async_jobs to store job IDs in DB
**File:** `services/store/src/store/m_insight/processing_service.py`

```python
async def trigger_async_jobs(self, entity: EntityVersionData) -> JobSubmissionStatus | None:
    """Submit jobs and update ImageIntelligence with job IDs.

    Returns:
        JobSubmissionStatus with 3 job IDs, or None if submission failed
    """
    # Submit jobs
    face_job_id = await self.job_service.submit_face_detection(entity, ...)
    clip_job_id = await self.job_service.submit_clip_embedding(entity, ...)
    dino_job_id = await self.job_service.submit_dino_embedding(entity, ...)

    # Update ImageIntelligence with job IDs and status
    with get_db_session() as session:
        intelligence = session.query(ImageIntelligence).filter_by(entity_id=entity.id).first()
        if intelligence:
            intelligence.face_detection_job_id = face_job_id
            intelligence.clip_job_id = clip_job_id
            intelligence.dino_job_id = dino_job_id
            intelligence.processing_status = "processing"
            session.commit()

    return JobSubmissionStatus(
        face_detection_job_id=face_job_id,
        clip_job_id=clip_job_id,
        dino_job_id=dino_job_id,
    )
```

**Note:** JobCallbackHandler should also update `processing_status` to "completed" or "failed" when all jobs finish.

### 6.3 Simplify shutdown method
**File:** `services/store/src/store/m_insight/processing_service.py`

Convert from class method to instance method:
```python
async def shutdown(self) -> None:
    """Shutdown this instance's resources."""
    if self.compute_client:
        await self.compute_client.close()
    if self.compute_session:
        await self.compute_session.close()
```

### 6.4 Update JobCallbackHandler
**File:** `services/store/src/store/m_insight/job_callbacks.py`

Update constructor:
- Add `face_store: QdrantVectorStore` parameter
- Change `config: StoreConfig` → `config: MInsightConfig`
- Use `entity.get_file_path()` and `face.get_file_path()` for path resolution

---

## Phase 7: Remove StoreConfig from Processing Service

### 7.1 Update processing_service.py
**File:** `services/store/src/store/m_insight/processing_service.py`

- Remove `StoreConfig` import and parameter
- Remove `EntityStorageService` (path resolution now in models)
- Constructor uses only `MInsightConfig`

### 7.2 Update m_insight_processor.py
**File:** `services/store/src/store/m_insight/m_insight_processor.py`

- Remove mock `StoreConfig` creation
- Pass only `MInsightConfig`:
  ```python
  intelligence_service = await IntelligenceProcessingService.create(session, self.config)
  await intelligence_service.trigger_async_jobs(entity_version)
  ```

---

## Phase 8: Update All Imports

Systematically update imports across codebase:

**Priority order:**
1. Core model imports (Phase 2)
2. Config imports (Phase 1)
3. Vector store imports (Phase 3)
4. Processor imports (Phase 4)
5. Service imports (Phases 5-7)

**Files to update:**
- All files in `m_insight/` directory
- `m_insight_worker.py`
- All test files
- Any integration tests

---

## Phase 9: Test Updates

### 9.1 Update test imports
Update all test files with new imports:
- `tests/test_m_insight_worker.py`
- `tests/test_m_insight_mqtt.py`
- `tests/test_store/test_integration/test_processing_service.py`
- `tests/test_store/test_integration/test_intelligence_routes.py`
- `tests/test_store/test_integration/test_retrieve_service.py`
- `tests/conftest.py`

### 9.2 Update test logic
- Tests creating `IntelligenceProcessingService` must use factory pattern: `await IntelligenceProcessingService.create(...)`
- Tests checking `trigger_async_jobs` must expect `JobSubmissionStatus | None`
- Tests mocking `EntityVersionData` must provide `get_file_path()` method
- Tests mocking `Face` must provide `get_file_path()` method

---

## Phase 10: Database Migration

### 10.1 Create Alembic migration for ImageIntelligence job tracking

**Command:**
```bash
cd services/store
alembic revision --autogenerate -m "add_job_tracking_to_image_intelligence"
```

**Review the generated migration** to ensure it adds:
- `face_detection_job_id` (String, nullable)
- `clip_job_id` (String, nullable)
- `dino_job_id` (String, nullable)
- `processing_status` (String, default="pending")

**Apply migration:**
```bash
alembic upgrade head
```

**Note:** This must be done after Phase 5.1 (updating ImageIntelligence model) but before testing.

---

## Phase 11: Validation and Cleanup

### 11.1 Run full test suite
```bash
pytest tests/
```

### 11.2 Delete obsolete files
- `services/store/src/store/m_insight/qdrant_image_store.py` (merged)
- `services/store/src/store/m_insight/worker.py` (renamed)

Verify no references remain: `grep -r "qdrant_image_store" services/store/`

### 11.3 Update __init__.py files for cleaner imports

**File:** `services/store/src/store/common/__init__.py`
```python
"""Common shared infrastructure for Store service."""

# Database
from .database import SessionLocal, engine, get_db, init_db, close_db
from .models import (
    Base,
    Entity,
    Face,
    EntityJob,
    ImageIntelligence,
    KnownPerson,
    FaceMatch,
    EntitySyncState,
    ServiceConfig,
)

# Configuration
from .config import BaseConfig, QdrantCollectionsConfig

# Storage
from .entity_storage import EntityStorageService

# Auth
from .auth import UserPayload, get_current_user, Permission

# Schemas
from .schemas import EntityResponse, EntityCreate, EntityUpdate

__all__ = [
    # Database
    "SessionLocal",
    "engine",
    "get_db",
    "init_db",
    "close_db",
    # Models
    "Base",
    "Entity",
    "Face",
    "EntityJob",
    "ImageIntelligence",
    "KnownPerson",
    "FaceMatch",
    "EntitySyncState",
    "ServiceConfig",
    # Config
    "BaseConfig",
    "QdrantCollectionsConfig",
    # Storage
    "EntityStorageService",
    # Auth
    "UserPayload",
    "get_current_user",
    "Permission",
    # Schemas
    "EntityResponse",
    "EntityCreate",
    "EntityUpdate",
]
```

**File:** `services/store/src/store/store/__init__.py`
```python
"""Store server API."""

from .config import StoreConfig
from .store import app, create_app

__all__ = ["app", "create_app", "StoreConfig"]
```

**File:** `services/store/src/store/m_insight/__init__.py`
```python
"""mInsight compute processing service."""

from .config import MInsightConfig
from .m_insight_processor import MInsightProcessor
from .processing_service import IntelligenceProcessingService
from .retrieval_service import IntelligenceRetrieveService
from .vector_stores import QdrantVectorStore, get_clip_store, get_dino_store, get_face_store

__all__ = [
    "MInsightConfig",
    "MInsightProcessor",
    "IntelligenceProcessingService",
    "IntelligenceRetrieveService",
    "QdrantVectorStore",
    "get_clip_store",
    "get_dino_store",
    "get_face_store",
]
```

### 11.4 Update main entry points to use clean imports

**File:** `services/store/src/store/main.py`
```python
# Instead of: from .store.config import StoreConfig
# Use: from .store import StoreConfig

# Instead of: from .common import database
# Use: from .common import init_db
```

**File:** `services/store/src/store/m_insight_worker.py`
```python
# Instead of: from .m_insight.worker import mInsight
# Use: from .m_insight import MInsightProcessor

# Instead of: from .common.models import Entity
# Use: from .common import Entity
```

### 11.5 Update alembic/env.py for new model locations

**File:** `services/store/alembic/env.py`

```python
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from sqlalchemy.orm import configure_mappers
from sqlalchemy_continuum import make_versioned

from alembic import context

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Initialize versioning before importing models
make_versioned(user_cls=None)

# Import ALL models from common (unified location)
from store.common.models import (
    Base,
    Entity,
    Face,
    EntityJob,
    ImageIntelligence,
    KnownPerson,
    FaceMatch,
    EntitySyncState,
    ServiceConfig,
)

# Configure mappers after models are imported
configure_mappers()

from store.common.utils import get_db_url

# ... rest of the file unchanged ...
```

**Changes:**
- Remove imports from `store.m_insight.models` (ImageIntelligence moved)
- Remove imports from `store.m_insight.intelligence.models` (all moved to common)
- Import all models from `store.common.models`

---

## Critical Files

**Create:**
- `services/store/src/store/common/config.py`

**Major Refactor:**
- `services/store/src/store/common/models.py` - Add all intelligence models
- `services/store/src/store/m_insight/processing_service.py` - Singleton pattern
- `services/store/src/store/m_insight/job_service.py` - EntityVersionData params
- `services/store/src/store/m_insight/vector_stores.py` - Merge QdrantImageStore

**Rename:**
- `services/store/src/store/m_insight/worker.py` → `m_insight_processor.py`

**Delete:**
- `services/store/src/store/m_insight/qdrant_image_store.py`
- `services/store/src/store/m_insight/worker.py`

**Update:**
- `services/store/src/store/store/config.py` - Extend BaseConfig
- `services/store/src/store/m_insight/config.py` - Extend BaseConfig
- `services/store/src/store/m_insight/models.py` - Add path resolution, JobSubmissionStatus
- `services/store/src/store/m_insight/job_callbacks.py` - Use MInsightConfig, face_store
- `services/store/src/store/m_insight/m_insight_processor.py` - Use new service pattern
- `services/store/src/store/m_insight_worker.py` - Import MInsightProcessor
- All test files

---

## Risk Assessment

### High Risk
- **Async initialization**: SessionManager.login() is async → Use factory pattern
- **Import cycles**: Moving models to common/ → Use TYPE_CHECKING guards

### Medium Risk
- **Path resolution**: New methods on models → Test with various formats
- **Singleton patterns**: Tests might rely on state → Clear between tests

### Low Risk
- **Renaming**: Comprehensive grep ensures no missed references
- **Vector store merge**: Keep same interfaces

---

## Verification Steps

After each phase:
1. Run imports: `python -c "from store.m_insight.processing_service import IntelligenceProcessingService"`
2. Run tests: `pytest tests/test_m_insight_worker.py -v`
3. Check for circular imports

Final verification:
1. All tests pass: `pytest tests/`
2. Store server starts: `python -m store.main`
3. mInsight worker starts: `m-insight-process`
4. No grep results for old names: `grep -r "QdrantImageStore" services/store/`

---

## Success Criteria

✅ All tests pass
✅ No import errors in store server
✅ No import errors in mInsight worker
✅ IntelligenceProcessingService initialization is straightforward
✅ All models in `common/models.py`
✅ No StoreConfig dependency in processing service
✅ Vector stores merged into single file
✅ Clear separation: Query service vs Compute service
✅ EntityStorageService used for path resolution
✅ Vector store dimensions configurable
✅ Job IDs stored in ImageIntelligence table
✅ Clean __init__.py exports
✅ Alembic env.py updated

---

## Final Folder Structure

```
services/store/
├── alembic/
│   ├── env.py                              # ✏️ UPDATED - Import models from common
│   └── versions/
│       └── [new]_add_job_tracking.py      # ➕ NEW MIGRATION - Job ID fields
│
├── src/store/
│   ├── __init__.py
│   │
│   ├── common/                            # 🎯 SHARED INFRASTRUCTURE
│   │   ├── __init__.py                    # ✏️ UPDATED - Export all common modules
│   │   ├── auth.py                        # ✅ (existing)
│   │   ├── config.py                      # ➕ NEW - BaseConfig, QdrantCollectionsConfig
│   │   ├── database.py                    # ✏️ UPDATED - Add close_db() function
│   │   ├── entity_storage.py              # ↔️ MOVED from store/entity_storage.py
│   │   ├── models.py                      # ✏️ MAJOR UPDATE - Add all intelligence models
│   │   │   # - Base (existing)
│   │   │   # - Entity (existing)
│   │   │   # - ServiceConfig (existing)
│   │   │   # + EntitySyncState (moved from m_insight)
│   │   │   # + ImageIntelligence (moved, add job_id fields)
│   │   │   # + Face (moved, add get_file_path method)
│   │   │   # + EntityJob (moved from m_insight)
│   │   │   # + KnownPerson (moved from m_insight)
│   │   │   # + FaceMatch (moved from m_insight)
│   │   ├── schemas.py                     # ✅ (existing)
│   │   ├── utils.py                       # ✅ (existing)
│   │   └── versioning.py                  # ✅ (existing)
│   │
│   ├── store/                             # 🌐 STORE SERVER (Query Service)
│   │   ├── __init__.py                    # ✏️ UPDATED - Export app, create_app, StoreConfig
│   │   ├── config.py                      # ✏️ UPDATED - StoreConfig extends BaseConfig
│   │   ├── entity_storage.py              # ❌ DELETED - Moved to common/
│   │   ├── monitor.py                     # ✅ (existing - MQTT listener)
│   │   ├── routes.py                      # ✅ (existing - Entity CRUD)
│   │   └── store.py                       # ✏️ UPDATED - Use clean imports
│   │
│   ├── m_insight/                         # 🤖 mINSIGHT COMPUTE SERVICE
│   │   ├── __init__.py                    # ✏️ UPDATED - Export MInsightProcessor, services
│   │   │
│   │   ├── config.py                      # ✏️ UPDATED - MInsightConfig extends BaseConfig
│   │   │
│   │   ├── models.py                      # ✏️ UPDATED - Keep only Pydantic models
│   │   │   # - EntityVersionData (add get_file_path method)
│   │   │   # - JobSubmissionStatus (Pydantic)
│   │   │   # - MInsightStartPayload
│   │   │   # - MInsightStopPayload
│   │   │   # - MInsightStatusPayload
│   │   │
│   │   ├── m_insight_processor.py         # ↔️ RENAMED from worker.py
│   │   │   # - Class: MInsightProcessor (renamed from mInsight)
│   │   │   # ✏️ UPDATED - Use new imports, IntelligenceProcessingService.create()
│   │   │
│   │   ├── processing_service.py          # ✏️ MAJOR REFACTOR
│   │   │   # - IntelligenceProcessingService
│   │   │   # - Remove _ensure_singletons()
│   │   │   # - Factory pattern: async create()
│   │   │   # - Initialize all services in _initialize()
│   │   │   # - trigger_async_jobs() updates ImageIntelligence
│   │   │   # - shutdown() is instance method
│   │   │
│   │   ├── job_service.py                 # ✏️ UPDATED
│   │   │   # - JobSubmissionService
│   │   │   # - Accept EntityVersionData + EntityStorageService
│   │   │   # - submit_* methods use entity/face path resolution
│   │   │
│   │   ├── job_callbacks.py               # ✏️ UPDATED
│   │   │   # - JobCallbackHandler
│   │   │   # - Accept face_store in constructor
│   │   │   # - Use MInsightConfig (not StoreConfig)
│   │   │   # - Update ImageIntelligence.processing_status
│   │   │   # - Use path resolution methods
│   │   │
│   │   ├── vector_stores.py               # ✏️ MAJOR UPDATE - Merged file
│   │   │   # - QdrantVectorStore (renamed from QdrantImageStore)
│   │   │   # - get_clip_store(url, collection, vector_size=512)
│   │   │   # - get_dino_store(url, collection, vector_size=384)
│   │   │   # - get_face_store(url, collection, vector_size=512)
│   │   │   # - All dimensions configurable
│   │   │
│   │   ├── qdrant_image_store.py          # ❌ DELETED - Merged into vector_stores.py
│   │   ├── worker.py                      # ❌ DELETED - Renamed to m_insight_processor.py
│   │   │
│   │   ├── retrieval_service.py           # ✏️ UPDATED - Use QdrantVectorStore
│   │   ├── routes.py                      # ✏️ UPDATED - Use clean imports
│   │   ├── schemas.py                     # ✅ (existing)
│   │   └── broadcaster.py                 # ✅ (existing)
│   │
│   ├── main.py                            # ✏️ UPDATED - Use clean imports from .store
│   └── m_insight_worker.py                # ✏️ UPDATED - Import MInsightProcessor from .m_insight
│
└── tests/
    ├── conftest.py                        # ✏️ UPDATED - Update imports
    ├── test_m_insight_worker.py           # ✏️ UPDATED - MInsightProcessor, new patterns
    ├── test_m_insight_mqtt.py             # ✏️ UPDATED - MInsightProcessor
    └── test_store/
        └── test_integration/
            ├── test_processing_service.py # ✏️ UPDATED - Factory pattern, job IDs
            ├── test_intelligence_routes.py# ✏️ UPDATED - Updated imports
            └── test_retrieve_service.py   # ✏️ UPDATED - QdrantVectorStore

Legend:
  ✅ No changes needed (existing file remains as-is)
  ✏️ Updated (existing file modified)
  ➕ New (file created)
  ↔️ Renamed/Moved (file renamed or moved to new location)
  ❌ Deleted (file removed, merged elsewhere)
```

---

## Module Organization

### services/store/src/store/common/ - Shared Infrastructure
**Purpose:** Infrastructure shared between Store server and mInsight process

**Exports:**
- Database: SessionLocal, get_db, init_db, close_db
- Models: ALL SQLAlchemy models (Base, Entity, Face, ImageIntelligence, etc.)
- Config: BaseConfig, QdrantCollectionsConfig
- Storage: EntityStorageService
- Auth: UserPayload, get_current_user, Permission
- Schemas: EntityResponse, EntityCreate, EntityUpdate

**Used by:** Both Store server and mInsight worker

---

### services/store/src/store/store/ - Store Server (Query Service)
**Purpose:** REST API for querying entities and intelligence data

**Exports:**
- app: FastAPI application
- create_app: Application factory
- StoreConfig: Store server configuration

**Endpoints:**
- Entity CRUD operations
- Collections management
- Soft delete/restore

**Dependencies:**
- common/ - Database, models, auth
- Does NOT depend on mInsight compute services

---

### services/store/src/store/m_insight/ - mInsight Compute Service
**Purpose:** Background processing for ML jobs and intelligence extraction

**Exports:**
- MInsightProcessor: Main reconciliation loop
- IntelligenceProcessingService: Job submission coordinator
- IntelligenceRetrieveService: Query service for intelligence data
- QdrantVectorStore: Vector store interface
- Vector store factories: get_clip_store, get_dino_store, get_face_store

**Components:**
1. **MInsightProcessor** (m_insight_processor.py): Version reconciliation, triggers processing
2. **IntelligenceProcessingService** (processing_service.py): Submits ML jobs to compute service
3. **JobSubmissionService** (job_service.py): Wraps compute client job submission
4. **JobCallbackHandler** (job_callbacks.py): Processes job completion, stores results
5. **IntelligenceRetrieveService** (retrieval_service.py): Queries DB and vector stores
6. **QdrantVectorStore** (vector_stores.py): Qdrant operations with configurable dimensions

**Routes (routes.py):**
- Intelligence query endpoints (faces, embeddings, similarity search)
- Known persons management
- Uses IntelligenceRetrieveService (not direct vector store access)

**Dependencies:**
- common/ - Database, models, storage
- Compute service (via cl_client SDK)
- Qdrant vector database

---

## Import Patterns

### Clean imports using __init__.py exports:

```python
# ✅ Good - Use module exports
from store.common import Entity, Face, ImageIntelligence, init_db, EntityStorageService
from store.store import create_app, StoreConfig
from store.m_insight import MInsightProcessor, IntelligenceProcessingService

# ❌ Bad - Direct imports from internal modules
from store.common.models import Entity
from store.store.config import StoreConfig
from store.m_insight.m_insight_processor import MInsightProcessor
```
