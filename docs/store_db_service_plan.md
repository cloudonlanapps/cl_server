# DBService Implementation Plan

## Overview
Create a centralized database CRUD service with separate classes per table for better maintainability. DBService acts as a facade providing access to all table-specific services.

**Key Design Goals:**
1. **Minimal but Complete**: Provide all database operations needed by existing services (EntityService, mInsight, etc.)
2. **Multi-process Safe**: Use @with_retry(max_retries=10) for all DB operations
3. **Clean Separation**: DBService handles DB logic only (no file storage, no metadata extraction)
4. **Reusable**: Other services can use DBService for database operations instead of direct ORM queries

**Relationship with EntityService:**
- EntityService will continue to exist for complex business logic (file storage, metadata extraction, hierarchy validation)
- EntityService CAN optionally use DBService for database operations, but this is not required initially
- DBService provides database-only operations that can be used by EntityService, mInsight, or other services

## Architecture

### Service Organization (Class per Table)
```
DBService (facade)
├── entity: EntityDBService
├── entity_version: EntityVersionDBService (read-only)
├── intelligence: ImageIntelligenceDBService
├── job: EntityJobDBService
├── face: FaceDBService
├── known_person: KnownPersonDBService
├── face_match: FaceMatchDBService
└── sync_state: EntitySyncStateDBService
```

### File Structure
```
src/store/common/db_service/
├── __init__.py                    # Exports DBService and all schemas
├── db_service.py                  # DBService facade class
├── schemas.py                     # All Pydantic schemas
├── base.py                        # BaseDBService with common CRUD patterns
├── entity.py                      # EntityDBService + EntityVersionDBService
├── intelligence.py                # ImageIntelligenceDBService + EntityJobDBService
├── face.py                        # FaceDBService + KnownPersonDBService + FaceMatchDBService
└── sync.py                        # EntitySyncStateDBService
```

### Test Structure
```
tests/test_store/test_db_service/
├── __init__.py
├── test_entity.py                 # EntityDBService tests
├── test_entity_version.py         # EntityVersionDBService tests
├── test_intelligence.py           # ImageIntelligence + EntityJob tests
├── test_face.py                   # Face + KnownPerson + FaceMatch tests
└── test_sync.py                   # EntitySyncState tests
```

## Implementation Details

### 1. Pydantic Schemas (schemas.py)

Each table gets schemas for read/write operations:

**EntitySchema** - Matches all Entity model fields
- All fields from Entity model
- `model_config = ConfigDict(from_attributes=True)`

**EntityVersionSchema** - For SQLAlchemy-Continuum version table
- All Entity fields + `transaction_id: int | None`
- Read-only schema (matches EntityVersionData pattern)

**ImageIntelligenceSchema** - Intelligence tracking
- entity_id, md5, image_path, version, status, processing_status
- Job IDs: face_detection_job_id, clip_job_id, dino_job_id, face_embedding_job_ids

**EntityJobSchema** - Job tracking
- id, entity_id, job_id, task_type, status
- created_at, updated_at, completed_at, error_message

**FaceSchema** - Detected faces
- id, entity_id, known_person_id, bbox, confidence, landmarks
- file_path, created_at

**KnownPersonSchema** - Face recognition
- id, name, created_at, updated_at

**FaceMatchSchema** - Face similarity
- id, face_id, matched_face_id, similarity_score, created_at

**EntitySyncStateSchema** - Singleton sync state
- id (always 1), last_version

### 2. Base Service Class (base.py)

Common CRUD patterns with retry logic:

```python
from cl_ml_tools.utils.profiling import timed
from store.common.database import with_retry

class BaseDBService:
    """Base class with common CRUD operations.

    CRITICAL: Each method manages its own session for multi-process safety.
    Pattern: SessionLocal() → try/commit → finally/close

    All methods decorated with:
    - @timed: Measure execution time (including all retries)
    - @with_retry(max_retries=10): Retry on database locks
    """

    def __init__(self, config: StoreConfig):
        """Initialize service with config only (no session stored)."""
        self.config = config

    # Override in subclasses:
    model_class: type
    schema_class: type

    @timed
    @with_retry(max_retries=10)
    def get(self, id: int) -> Schema | None:
        """Get single record by ID.

        Session: Creates and closes own session.
        """
        from store.common import database

        db = database.SessionLocal()
        try:
            obj = db.query(self.model_class).filter_by(id=id).first()
            return self._to_schema(obj) if obj else None
        finally:
            db.close()

    @timed
    @with_retry(max_retries=10)
    def get_all(self, page: int | None = 1, page_size: int = 20) -> list[Schema] | tuple[list[Schema], int]:
        """Get all records with optional pagination.

        Session: Creates and closes own session.
        """
        from store.common import database

        db = database.SessionLocal()
        try:
            stmt = select(self.model_class)

            if page is None:
                results = db.execute(stmt).scalars().all()
                return [self._to_schema(r) for r in results]
            else:
                total = db.execute(select(func.count()).select_from(self.model_class)).scalar()
                offset = (page - 1) * page_size
                results = db.execute(stmt.offset(offset).limit(page_size)).scalars().all()
                items = [self._to_schema(r) for r in results]
                return (items, total)
        finally:
            db.close()

    @timed
    @with_retry(max_retries=10)
    def create(self, data: Schema, ignore_exception: bool = False) -> Schema | None:
        """Create new record.

        Args:
            data: Schema with data to create
            ignore_exception: If True, return None on errors instead of raising (for callbacks)

        Session: Creates and closes own session.
        """
        from store.common import database

        db = database.SessionLocal()
        try:
            logger.debug(f"Creating {self.model_class.__name__}: {data.model_dump(exclude_unset=True)}")
            obj = self.model_class(**data.model_dump(exclude_unset=True))
            db.add(obj)
            db.commit()
            db.refresh(obj)
            logger.debug(f"Created {self.model_class.__name__} with id={getattr(obj, 'id', 'N/A')}")
            return self._to_schema(obj)
        except Exception as e:
            db.rollback()
            if ignore_exception:
                logger.debug(f"Ignoring exception during create {self.model_class.__name__}: {e}")
                return None
            logger.error(f"Failed to create {self.model_class.__name__}: {e}")
            raise
        finally:
            db.close()

    @timed
    @with_retry(max_retries=10)
    def update(self, id: int, data: Schema, ignore_exception: bool = False) -> Schema | None:
        """Update existing record.

        Args:
            id: Record ID
            data: Schema with updated data
            ignore_exception: If True, return None on errors instead of raising (for callbacks)

        Session: Creates and closes own session.
        """
        from store.common import database

        db = database.SessionLocal()
        try:
            logger.debug(f"Updating {self.model_class.__name__} id={id}: {data.model_dump(exclude_unset=True)}")
            obj = db.query(self.model_class).filter_by(id=id).first()
            if not obj:
                logger.debug(f"{self.model_class.__name__} id={id} not found for update")
                return None

            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(obj, key, value)

            db.commit()
            db.refresh(obj)
            logger.debug(f"Updated {self.model_class.__name__} id={id}")
            return self._to_schema(obj)
        except Exception as e:
            db.rollback()
            if ignore_exception:
                logger.debug(f"Ignoring exception during update {self.model_class.__name__} id={id}: {e}")
                return None
            logger.error(f"Failed to update {self.model_class.__name__} id={id}: {e}")
            raise
        finally:
            db.close()

    @timed
    @with_retry(max_retries=10)
    def delete(self, id: int) -> bool:
        """Delete record and log cascades.

        Session: Creates and closes own session.
        """
        from store.common import database

        db = database.SessionLocal()
        try:
            obj = db.query(self.model_class).filter_by(id=id).first()
            if not obj:
                return False

            self._log_cascade_deletes(obj)
            db.delete(obj)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @timed
    @with_retry(max_retries=10)
    def query(self, **kwargs) -> list[Schema]:
        """Flexible query with operators.

        Session: Creates and closes own session.
        """
        from store.common import database

        db = database.SessionLocal()
        try:
            # ... query implementation
            return [self._to_schema(r) for r in results]
        finally:
            db.close()

    @timed
    @with_retry(max_retries=10)
    def count(self, **kwargs) -> int:
        """Count records matching filters.

        Session: Creates and closes own session.
        """
        from store.common import database

        db = database.SessionLocal()
        try:
            # Build filters (same as query())
            stmt = select(func.count()).select_from(self.model_class).where(*filters)
            return db.execute(stmt).scalar()
        finally:
            db.close()

    def _to_schema(self, orm_obj) -> Schema:
        """Convert ORM to Pydantic."""
        return self.schema_class.model_validate(orm_obj)

    def _log_cascade_deletes(self, orm_obj) -> None:
        """Log what will be cascade deleted (override in subclasses)."""
        pass
```

### 3. Table-Specific Services

#### EntityDBService (entity.py)
- Inherits from BaseDBService
- Override delete() to handle cascade: faces, jobs, intelligence
- Log cascade deletes before deletion

**Additional methods for EntityService compatibility:**
```python
def get_with_intelligence_status(self, id: int) -> tuple[EntitySchema | None, str | None]:
    """Get entity with intelligence status via outer join."""
    result = self.db.query(Entity, ImageIntelligence.status)\
        .outerjoin(ImageIntelligence, Entity.id == ImageIntelligence.entity_id)\
        .filter(Entity.id == id)\
        .first()
    if result:
        entity, status = result
        return (self._to_schema(entity), status)
    return (None, None)

def get_all_with_intelligence_status(
    self,
    page: int | None = 1,
    page_size: int = 20,
    exclude_deleted: bool = False
) -> tuple[list[tuple[EntitySchema, str | None]], int] | list[tuple[EntitySchema, str | None]]:
    """Get all entities with intelligence status via outer join."""
    query = self.db.query(Entity, ImageIntelligence.status)\
        .outerjoin(ImageIntelligence, Entity.id == ImageIntelligence.entity_id)

    if exclude_deleted:
        query = query.filter(Entity.is_deleted == False)

    if page is None:
        results = query.all()
        return [(self._to_schema(e), s) for e, s in results]
    else:
        total = query.count()
        offset = (page - 1) * page_size
        results = query.order_by(Entity.id.asc()).offset(offset).limit(page_size).all()
        items = [(self._to_schema(e), s) for e, s in results]
        return (items, total)

def get_children(self, parent_id: int) -> list[EntitySchema]:
    """Get all child entities of a parent."""
    return self.query(parent_id=parent_id)

def delete_all(self) -> None:
    """Bulk delete all entities and related data (for tests/admin)."""
    # Import necessary models
    from sqlalchemy import text
    from store.common.models import (
        EntityJob, FaceMatch, Face, ImageIntelligence, KnownPerson
    )

    # Delete related data first (order matters for FKs)
    self.db.query(EntityJob).delete()
    self.db.query(FaceMatch).delete()
    self.db.query(Face).delete()
    self.db.query(ImageIntelligence).delete()
    self.db.query(KnownPerson).delete()

    # Clear Continuum version tables
    for table in ["entities_version", "known_persons_version", "transaction_changes", "transaction"]:
        try:
            self.db.execute(text(f"DELETE FROM {table}"))
        except Exception as e:
            logger.warning(f"Failed to clear table {table}: {e}")

    # Delete all entities
    self.db.query(Entity).delete()

    # Reset sqlite sequence
    try:
        self.db.execute(text("DELETE FROM sqlite_sequence"))
    except Exception as e:
        logger.debug(f"sqlite_sequence clear failed: {e}")

    self.db.commit()
```

#### EntityVersionDBService (entity.py)
- Special read-only service
- Uses `version_class(Entity)` from sqlalchemy_continuum
- **CRITICAL:** Query `EntityVersion` table directly (not via Entity.versions relationship)
- **Reason:** Allows retrieving versions even after entity hard-deleted
- Only implements: get(), get_all(), query()
- No create/update/delete methods

**Implementation:**
```python
from sqlalchemy.orm import configure_mappers
from sqlalchemy_continuum import version_class

class EntityVersionDBService:
    def __init__(self, config: StoreConfig):
        self.config = config
        # Get the EntityVersion model class
        configure_mappers()
        self.EntityVersion = version_class(Entity)

    @timed
    @with_retry(max_retries=10)
    def get_all_for_entity(self, entity_id: int) -> list[EntityVersionSchema]:
        """Get all versions of a specific entity.

        Works even if entity is deleted from main table.
        """
        db = database.SessionLocal()
        try:
            logger.debug(f"Getting all versions for entity_id={entity_id}")
            stmt = select(self.EntityVersion).where(self.EntityVersion.id == entity_id).order_by(self.EntityVersion.transaction_id)
            versions = db.execute(stmt).scalars().all()
            logger.debug(f"Found {len(versions)} versions for entity_id={entity_id}")
            return [EntityVersionSchema.model_validate(v) for v in versions]
        finally:
            db.close()

    @timed
    @with_retry(max_retries=10)
    def get_by_transaction_id(self, entity_id: int, transaction_id: int) -> EntityVersionSchema | None:
        """Get specific version by entity_id and transaction_id.

        Works even if entity is deleted from main table.
        """
        db = database.SessionLocal()
        try:
            logger.debug(f"Getting version entity_id={entity_id}, transaction_id={transaction_id}")
            stmt = select(self.EntityVersion).where(
                (self.EntityVersion.id == entity_id) & (self.EntityVersion.transaction_id == transaction_id)
            )
            version = db.execute(stmt).scalar_one_or_none()
            result = EntityVersionSchema.model_validate(version) if version else None
            logger.debug(f"Version {'found' if result else 'not found'}")
            return result
        finally:
            db.close()

    @timed
    @with_retry(max_retries=10)
    def get_versions_in_range(
        self,
        start_transaction_id: int,
        end_transaction_id: int | None = None
    ) -> dict[int, EntityVersionSchema]:
        """Get entity changes in transaction ID range, coalesced by entity ID.

        This is the primary method used by mInsight reconciliation.
        Returns latest version for each entity that changed in the range.

        Args:
            start_transaction_id: Start from this transaction (exclusive: transaction_id > start)
            end_transaction_id: End at this transaction (inclusive: transaction_id <= end).
                               If None, returns all versions up to latest.

        Returns:
            Dict mapping entity_id to latest EntityVersionSchema in the range.

        Works even if entities are deleted from main table.
        """
        db = database.SessionLocal()
        try:
            if end_transaction_id is None:
                logger.debug(f"Getting entity deltas from transaction_id > {start_transaction_id} to latest")
                stmt = (
                    select(self.EntityVersion)
                    .where(self.EntityVersion.transaction_id > start_transaction_id)
                    .order_by(self.EntityVersion.transaction_id)
                )
            else:
                logger.debug(f"Getting entity deltas from transaction_id > {start_transaction_id} to <= {end_transaction_id}")
                stmt = (
                    select(self.EntityVersion)
                    .where(
                        (self.EntityVersion.transaction_id > start_transaction_id) &
                        (self.EntityVersion.transaction_id <= end_transaction_id)
                    )
                    .order_by(self.EntityVersion.transaction_id)
                )

            versions = db.execute(stmt).scalars().all()

            # Coalesce by entity_id (keep latest version per entity in range)
            entity_map: dict[int, EntityVersionSchema] = {}
            for version in versions:
                entity_map[version.id] = EntityVersionSchema.model_validate(version)

            logger.debug(f"Found {len(entity_map)} entities with changes in range")
            return entity_map
        finally:
            db.close()

    @timed
    @with_retry(max_retries=10)
    def query(self, **kwargs) -> list[EntityVersionSchema]:
        """Query version table with filters.

        Works even if entities are deleted from main table.
        """
        db = database.SessionLocal()
        try:
            logger.debug(f"Querying EntityVersion with filters: {kwargs}")
            filters = []
            for key, value in kwargs.items():
                if '__' in key:
                    field_name, operator = key.rsplit('__', 1)
                    column = getattr(self.EntityVersion, field_name)
                    if operator == 'gt':
                        filters.append(column > value)
                    elif operator == 'gte':
                        filters.append(column >= value)
                    elif operator == 'lt':
                        filters.append(column < value)
                    elif operator == 'lte':
                        filters.append(column <= value)
                    elif operator == 'ne':
                        filters.append(column != value)
                else:
                    filters.append(getattr(self.EntityVersion, key) == value)

            stmt = select(self.EntityVersion).where(*filters)
            results = db.execute(stmt).scalars().all()
            logger.debug(f"Found {len(results)} EntityVersion records")
            return [EntityVersionSchema.model_validate(r) for r in results]
        finally:
            db.close()
```

#### ImageIntelligenceDBService (intelligence.py)
- Primary key is entity_id (not auto-increment id)
- Override get() to use entity_id

**Actual mInsight Usage:**
```python
@timed
@with_retry(max_retries=10)
def get_by_entity_id(self, entity_id: int) -> ImageIntelligenceSchema | None:
    """Get by entity_id (primary key)."""
    db = database.SessionLocal()
    try:
        logger.debug(f"Getting ImageIntelligence for entity_id={entity_id}")
        obj = db.query(ImageIntelligence).filter(ImageIntelligence.entity_id == entity_id).first()
        result = self._to_schema(obj) if obj else None
        logger.debug(f"ImageIntelligence entity_id={entity_id}: {'found' if result else 'not found'}")
        return result
    finally:
        db.close()

@timed
@with_retry(max_retries=10)
def create_or_update(self, data: ImageIntelligenceSchema, ignore_exception: bool = False) -> ImageIntelligenceSchema | None:
    """Upsert intelligence record.

    Args:
        data: Intelligence data
        ignore_exception: If True, return None on errors (e.g., entity deleted during callback)
    """
    db = database.SessionLocal()
    try:
        # Check if entity exists before writing
        entity_exists = db.query(Entity.id).filter(Entity.id == data.entity_id).scalar() is not None
        if not entity_exists:
            logger.debug(f"Entity {data.entity_id} not found, skipping ImageIntelligence create/update")
            if ignore_exception:
                return None
            raise ValueError(f"Entity {data.entity_id} does not exist")

        logger.debug(f"Creating/updating ImageIntelligence for entity_id={data.entity_id}")
        obj = db.query(ImageIntelligence).filter(ImageIntelligence.entity_id == data.entity_id).first()
        if obj:
            # Update existing
            logger.debug(f"Updating existing ImageIntelligence for entity_id={data.entity_id}")
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(obj, key, value)
        else:
            # Create new
            logger.debug(f"Creating new ImageIntelligence for entity_id={data.entity_id}")
            obj = ImageIntelligence(**data.model_dump(exclude_unset=True))
            db.add(obj)

        db.commit()
        db.refresh(obj)
        logger.debug(f"ImageIntelligence for entity_id={data.entity_id} saved")
        return self._to_schema(obj)
    except Exception as e:
        db.rollback()
        if ignore_exception:
            logger.debug(f"Ignoring exception for ImageIntelligence entity_id={data.entity_id}: {e}")
            return None
        logger.error(f"Failed to create/update ImageIntelligence entity_id={data.entity_id}: {e}")
        raise
    finally:
        db.close()

@timed
@with_retry(max_retries=10)
def update_job_ids(self, entity_id: int, ignore_exception: bool = False, **job_ids) -> ImageIntelligenceSchema | None:
    """Update specific job ID fields (face_detection_job_id, clip_job_id, etc.).

    Args:
        entity_id: Entity ID
        ignore_exception: If True, return None on errors
        **job_ids: Field names and values to update
    """
    db = database.SessionLocal()
    try:
        # Check if entity exists
        entity_exists = db.query(Entity.id).filter(Entity.id == entity_id).scalar() is not None
        if not entity_exists:
            logger.debug(f"Entity {entity_id} not found, skipping job ID update")
            if ignore_exception:
                return None
            raise ValueError(f"Entity {entity_id} does not exist")

        logger.debug(f"Updating ImageIntelligence job IDs for entity_id={entity_id}: {job_ids}")
        obj = db.query(ImageIntelligence).filter(ImageIntelligence.entity_id == entity_id).first()
        if not obj:
            logger.debug(f"ImageIntelligence not found for entity_id={entity_id}")
            return None

        for key, value in job_ids.items():
            setattr(obj, key, value)

        db.commit()
        db.refresh(obj)
        logger.debug(f"Updated ImageIntelligence job IDs for entity_id={entity_id}")
        return self._to_schema(obj)
    except Exception as e:
        db.rollback()
        if ignore_exception:
            logger.debug(f"Ignoring exception for ImageIntelligence update entity_id={entity_id}: {e}")
            return None
        logger.error(f"Failed to update ImageIntelligence job IDs entity_id={entity_id}: {e}")
        raise
    finally:
        db.close()
```

#### EntityJobDBService (intelligence.py)
- Standard CRUD operations
- Cascaded when Entity deleted

**Actual mInsight Usage:**
```python
@timed
@with_retry(max_retries=10)
def get_by_job_id(self, job_id: str) -> EntityJobSchema | None:
    """Get job by job_id (unique field)."""
    db = database.SessionLocal()
    try:
        logger.debug(f"Getting EntityJob by job_id={job_id}")
        obj = db.query(EntityJob).filter(EntityJob.job_id == job_id).first()
        result = self._to_schema(obj) if obj else None
        logger.debug(f"EntityJob job_id={job_id}: {'found' if result else 'not found'}")
        return result
    finally:
        db.close()

@timed
@with_retry(max_retries=10)
def get_by_entity_id(self, entity_id: int) -> list[EntityJobSchema]:
    """Get all jobs for an entity."""
    db = database.SessionLocal()
    try:
        logger.debug(f"Getting EntityJobs for entity_id={entity_id}")
        objs = db.query(EntityJob).filter(EntityJob.entity_id == entity_id).all()
        logger.debug(f"Found {len(objs)} EntityJobs for entity_id={entity_id}")
        return [self._to_schema(obj) for obj in objs]
    finally:
        db.close()

@timed
@with_retry(max_retries=10)
def create(self, data: EntityJobSchema, ignore_exception: bool = False) -> EntityJobSchema | None:
    """Create job record.

    Args:
        data: Job data
        ignore_exception: If True, return None on errors (e.g., entity deleted)
    """
    db = database.SessionLocal()
    try:
        # Check if entity exists before creating job
        entity_exists = db.query(Entity.id).filter(Entity.id == data.entity_id).scalar() is not None
        if not entity_exists:
            logger.debug(f"Entity {data.entity_id} not found, skipping EntityJob create")
            if ignore_exception:
                return None
            raise ValueError(f"Entity {data.entity_id} does not exist")

        logger.debug(f"Creating EntityJob for entity_id={data.entity_id}, job_id={data.job_id}")
        obj = EntityJob(**data.model_dump(exclude_unset=True))
        db.add(obj)
        db.commit()
        db.refresh(obj)
        logger.debug(f"Created EntityJob id={obj.id}")
        return self._to_schema(obj)
    except Exception as e:
        db.rollback()
        if ignore_exception:
            logger.debug(f"Ignoring exception for EntityJob create: {e}")
            return None
        logger.error(f"Failed to create EntityJob: {e}")
        raise
    finally:
        db.close()

@timed
@with_retry(max_retries=10)
def update_status(
    self,
    job_id: str,
    status: str,
    error_message: str | None = None,
    completed_at: int | None = None,
    ignore_exception: bool = False
) -> tuple[EntityJobSchema | None, int | None]:
    """Update job status, returns (job, entity_id) for broadcasting.

    Args:
        job_id: Job ID
        status: New status
        error_message: Optional error message
        completed_at: Optional completion timestamp
        ignore_exception: If True, return (None, None) on errors
    """
    db = database.SessionLocal()
    try:
        logger.debug(f"Updating EntityJob status job_id={job_id} to {status}")
        obj = db.query(EntityJob).filter(EntityJob.job_id == job_id).first()
        if not obj:
            logger.debug(f"EntityJob job_id={job_id} not found")
            return (None, None)

        obj.status = status
        obj.updated_at = _now_timestamp()
        if error_message:
            obj.error_message = error_message
        if completed_at:
            obj.completed_at = completed_at

        db.commit()
        db.refresh(obj)
        logger.debug(f"Updated EntityJob job_id={job_id} status to {status}")
        return (self._to_schema(obj), obj.entity_id)
    except Exception as e:
        db.rollback()
        if ignore_exception:
            logger.debug(f"Ignoring exception for EntityJob status update job_id={job_id}: {e}")
            return (None, None)
        logger.error(f"Failed to update EntityJob status job_id={job_id}: {e}")
        raise
    finally:
        db.close()

@timed
@with_retry(max_retries=10)
def delete_by_job_id(self, job_id: str, ignore_exception: bool = False) -> bool:
    """Delete job by job_id.

    Args:
        job_id: Job ID
        ignore_exception: If True, return False on errors
    """
    db = database.SessionLocal()
    try:
        logger.debug(f"Deleting EntityJob job_id={job_id}")
        obj = db.query(EntityJob).filter(EntityJob.job_id == job_id).first()
        if not obj:
            logger.debug(f"EntityJob job_id={job_id} not found for deletion")
            return False

        db.delete(obj)
        db.commit()
        logger.debug(f"Deleted EntityJob job_id={job_id}")
        return True
    except Exception as e:
        db.rollback()
        if ignore_exception:
            logger.debug(f"Ignoring exception for EntityJob delete job_id={job_id}: {e}")
            return False
        logger.error(f"Failed to delete EntityJob job_id={job_id}: {e}")
        raise
    finally:
        db.close()
```

#### FaceDBService (face.py)
- Override delete() to log FaceMatch cascades
- Cascaded when Entity deleted
- known_person_id can be NULL

**Actual mInsight Usage:**
```python
def get_by_entity_id(self, entity_id: int) -> list[FaceSchema]:
    """Get all faces for an entity."""
    db = database.SessionLocal()
    try:
        objs = db.query(Face).filter(Face.entity_id == entity_id).all()
        return [self._to_schema(obj) for obj in objs]
    finally:
        db.close()

def get_by_known_person_id(self, known_person_id: int) -> list[FaceSchema]:
    """Get all faces for a known person."""
    db = database.SessionLocal()
    try:
        objs = db.query(Face).filter(Face.known_person_id == known_person_id).all()
        return [self._to_schema(obj) for obj in objs]
    finally:
        db.close()

def count_by_entity_id(self, entity_id: int) -> int:
    """Count faces for an entity."""
    db = database.SessionLocal()
    try:
        return db.query(Face).filter(Face.entity_id == entity_id).count()
    finally:
        db.close()

def count_by_known_person_id(self, known_person_id: int) -> int:
    """Count faces for a known person."""
    db = database.SessionLocal()
    try:
        return db.query(Face).filter(Face.known_person_id == known_person_id).count()
    finally:
        db.close()

@timed
@with_retry(max_retries=10)
def create_or_update(self, data: FaceSchema, ignore_exception: bool = False) -> FaceSchema | None:
    """Upsert face (deterministic ID: entity_id * 10000 + index).

    Args:
        data: Face data
        ignore_exception: If True, return None on errors (e.g., entity deleted during callback)
    """
    db = database.SessionLocal()
    try:
        # Check if entity exists before writing face
        entity_exists = db.query(Entity.id).filter(Entity.id == data.entity_id).scalar() is not None
        if not entity_exists:
            logger.debug(f"Entity {data.entity_id} not found, skipping Face create/update")
            if ignore_exception:
                return None
            raise ValueError(f"Entity {data.entity_id} does not exist")

        logger.debug(f"Creating/updating Face id={data.id} for entity_id={data.entity_id}")
        obj = db.query(Face).filter(Face.id == data.id).first()
        if obj:
            # Update existing
            logger.debug(f"Updating existing Face id={data.id}")
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(obj, key, value)
        else:
            # Create new
            logger.debug(f"Creating new Face id={data.id}")
            obj = Face(**data.model_dump(exclude_unset=True))
            db.add(obj)

        db.commit()
        db.refresh(obj)
        logger.debug(f"Face id={data.id} saved")
        return self._to_schema(obj)
    except Exception as e:
        db.rollback()
        if ignore_exception:
            logger.debug(f"Ignoring exception for Face id={data.id}: {e}")
            return None
        logger.error(f"Failed to create/update Face id={data.id}: {e}")
        raise
    finally:
        db.close()

def update_known_person_id(self, face_id: int, known_person_id: int | None) -> FaceSchema | None:
    """Link/unlink face to known person."""
    db = database.SessionLocal()
    try:
        obj = db.query(Face).filter(Face.id == face_id).first()
        if not obj:
            return None

        obj.known_person_id = known_person_id
        db.commit()
        db.refresh(obj)
        return self._to_schema(obj)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

#### KnownPersonDBService (face.py)
- Override delete() to prevent deletion if faces are linked
- Log affected faces on delete

**Actual mInsight Usage:**
```python
def create_with_flush(self) -> KnownPersonSchema:
    """Create new person and flush to get ID (for immediate linking)."""
    db = database.SessionLocal()
    try:
        now = _now_timestamp()
        obj = KnownPerson(created_at=now, updated_at=now)
        db.add(obj)
        db.flush()  # Get ID without committing
        db.commit()
        db.refresh(obj)
        return self._to_schema(obj)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def update_name(self, person_id: int, name: str) -> KnownPersonSchema | None:
    """Update person name."""
    db = database.SessionLocal()
    try:
        obj = db.query(KnownPerson).filter(KnownPerson.id == person_id).first()
        if not obj:
            return None

        obj.name = name
        obj.updated_at = _now_timestamp()
        db.commit()
        db.refresh(obj)
        return self._to_schema(obj)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def exists(self, person_id: int) -> bool:
    """Check if person exists."""
    db = database.SessionLocal()
    try:
        return db.query(KnownPerson.id).filter(KnownPerson.id == person_id).scalar() is not None
    finally:
        db.close()
```

#### FaceMatchDBService (face.py)
- Cascaded when either Face is deleted
- Requires face_id and matched_face_id

**Actual mInsight Usage:**
```python
def get_by_face_id(self, face_id: int) -> list[FaceMatchSchema]:
    """Get all matches for a face."""
    db = database.SessionLocal()
    try:
        objs = db.query(FaceMatch).filter(FaceMatch.face_id == face_id).all()
        return [self._to_schema(obj) for obj in objs]
    finally:
        db.close()

def count_by_face_id(self, face_id: int) -> int:
    """Count matches for a face (for delete logging)."""
    db = database.SessionLocal()
    try:
        return db.query(FaceMatch).filter(
            (FaceMatch.face_id == face_id) | (FaceMatch.matched_face_id == face_id)
        ).count()
    finally:
        db.close()

@timed
@with_retry(max_retries=10)
def create_batch(self, matches: list[FaceMatchSchema], ignore_exception: bool = False) -> list[FaceMatchSchema]:
    """Create multiple match records in single transaction.

    Args:
        matches: List of face match data
        ignore_exception: If True, return empty list on errors
    """
    db = database.SessionLocal()
    try:
        logger.debug(f"Creating batch of {len(matches)} FaceMatch records")
        objs = [FaceMatch(**m.model_dump(exclude_unset=True)) for m in matches]
        db.add_all(objs)
        db.commit()
        for obj in objs:
            db.refresh(obj)
        logger.debug(f"Created {len(objs)} FaceMatch records")
        return [self._to_schema(obj) for obj in objs]
    except Exception as e:
        db.rollback()
        if ignore_exception:
            logger.debug(f"Ignoring exception for FaceMatch batch create: {e}")
            return []
        logger.error(f"Failed to create FaceMatch batch: {e}")
        raise
    finally:
        db.close()
```

#### EntitySyncStateDBService (sync.py)
- Singleton table (id=1)
- Override get() to always use id=1
- Override create() to prevent multiple rows
- No delete()

**Actual mInsight Usage:**
```python
def get_or_create(self) -> EntitySyncStateSchema:
    """Get singleton sync state, create if doesn't exist."""
    db = database.SessionLocal()
    try:
        obj = db.query(EntitySyncState).filter(EntitySyncState.id == 1).first()
        if not obj:
            obj = EntitySyncState(id=1, last_version=0)
            db.add(obj)
            db.commit()
            db.refresh(obj)
        return self._to_schema(obj)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def get_last_version(self) -> int:
    """Get last processed version (shorthand)."""
    state = self.get_or_create()
    return state.last_version

def update_last_version(self, version: int) -> EntitySyncStateSchema:
    """Update last processed version."""
    db = database.SessionLocal()
    try:
        obj = db.query(EntitySyncState).filter(EntitySyncState.id == 1).first()
        if not obj:
            # Create if doesn't exist
            obj = EntitySyncState(id=1, last_version=version)
            db.add(obj)
        else:
            obj.last_version = version

        db.commit()
        db.refresh(obj)
        return self._to_schema(obj)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# Override base methods to prevent misuse
def create(self, data):
    raise NotImplementedError("Use get_or_create() for singleton EntitySyncState")

def delete(self, id):
    raise NotImplementedError("Cannot delete singleton EntitySyncState")
```

### 4. Query Implementation

Support flexible filtering with operators and ordering:

```python
# Usage examples:
face_service.query(entity_id=5)  # Exact match
face_service.query(confidence__gte=0.9)  # Greater than or equal
face_service.query(entity_id=5, confidence__gte=0.9)  # Multiple filters
face_service.query(is_deleted=False, order_by='id', ascending=True)  # With ordering
```

**Supported operators:**
- No suffix: exact match (=)
- `__gt`: greater than (>)
- `__gte`: greater than or equal (>=)
- `__lt`: less than (<)
- `__lte`: less than or equal (<=)
- `__ne`: not equal (!=)

**Additional parameters:**
- `order_by`: Field name to order by (optional)
- `ascending`: Sort direction (default: True)
- `limit`: Max records to return (optional)
- `offset`: Skip N records (optional)

**Implementation:**
```python
def query(
    self,
    order_by: str | None = None,
    ascending: bool = True,
    limit: int | None = None,
    offset: int | None = None,
    **kwargs
) -> list[Schema]:
    filters = []
    for key, value in kwargs.items():
        if '__' in key:
            field_name, operator = key.rsplit('__', 1)
            column = getattr(self.model_class, field_name)
            if operator == 'gt':
                filters.append(column > value)
            elif operator == 'gte':
                filters.append(column >= value)
            elif operator == 'lt':
                filters.append(column < value)
            elif operator == 'lte':
                filters.append(column <= value)
            elif operator == 'ne':
                filters.append(column != value)
        else:
            filters.append(getattr(self.model_class, key) == value)

    stmt = select(self.model_class).where(*filters)

    # Apply ordering
    if order_by:
        order_column = getattr(self.model_class, order_by)
        stmt = stmt.order_by(order_column.asc() if ascending else order_column.desc())

    # Apply limit/offset
    if offset:
        stmt = stmt.offset(offset)
    if limit:
        stmt = stmt.limit(limit)

    results = self.db.execute(stmt).scalars().all()
    return [self._to_schema(r) for r in results]
```

### 5. Pagination Implementation

```python
def get_all(self, page: int | None = 1, page_size: int = 20):
    stmt = select(self.model_class)

    if page is None:
        # Return all records
        results = self.db.execute(stmt).scalars().all()
        return [self._to_schema(r) for r in results]
    else:
        # Paginated
        total = self.db.execute(select(func.count()).select_from(self.model_class)).scalar()
        offset = (page - 1) * page_size
        results = self.db.execute(stmt.offset(offset).limit(page_size)).scalars().all()
        items = [self._to_schema(r) for r in results]
        return (items, total)
```

### 6. DBService Facade (db_service.py)

```python
class DBService:
    """Facade providing access to all table services.

    Each service manages its own sessions internally for multi-process safety.
    """

    def __init__(self, config: StoreConfig):
        """Initialize all table services.

        Args:
            config: Store configuration (no session stored)
        """
        self.entity = EntityDBService(config)
        self.entity_version = EntityVersionDBService(config)
        self.intelligence = ImageIntelligenceDBService(config)
        self.job = EntityJobDBService(config)
        self.face = FaceDBService(config)
        self.known_person = KnownPersonDBService(config)
        self.face_match = FaceMatchDBService(config)
        self.sync_state = EntitySyncStateDBService(config)
```

Usage:
```python
# Initialize once (no session passed)
db_service = DBService(config)

# Each call creates/closes its own session
entity = db_service.entity.get(5)
faces = db_service.face.get_by_entity_id(5)
sync_state = db_service.sync_state.get_or_create()
```

### 7. Cascade Delete Handling

**Policy 1: Entity deletion - ALLOW WITH LOGGING**
Cascades to:
- ImageIntelligence (1 record)
- Face (multiple records)
- EntityJob (multiple records)

Implementation:
```python
def delete(self, id: int) -> bool:
    entity = self.db.query(Entity).filter_by(id=id).first()
    if not entity:
        return False

    # Log what will be cascade deleted
    logger.info(f"Deleting Entity {entity.id} will cascade delete:")
    logger.info(f"  - ImageIntelligence: {1 if entity.intelligence else 0}")
    logger.info(f"  - Faces: {len(entity.faces)}")
    logger.info(f"  - EntityJobs: {len(entity.jobs)}")

    self.db.delete(entity)
    self.db.commit()
    return True
```

**Policy 2: Face deletion - ALLOW WITH LOGGING**
Cascades to:
- FaceMatch (all matches where face_id or matched_face_id matches)

Implementation:
```python
def delete(self, id: int) -> bool:
    face = self.db.query(Face).filter_by(id=id).first()
    if not face:
        return False

    # Count FaceMatch records that will be deleted
    match_count = self.db.query(FaceMatch).filter(
        (FaceMatch.face_id == id) | (FaceMatch.matched_face_id == id)
    ).count()

    logger.info(f"Deleting Face {id} (entity_id={face.entity_id}) will cascade delete:")
    logger.info(f"  - FaceMatch records: {match_count}")

    self.db.delete(face)
    self.db.commit()
    return True
```

**Policy 3: KnownPerson deletion - PREVENT IF RELATIONS EXIST**
Does NOT cascade (Face.known_person_id set to NULL by DB, but we prevent deletion):

Implementation:
```python
def delete(self, id: int) -> bool:
    person = self.db.query(KnownPerson).filter_by(id=id).first()
    if not person:
        return False

    # Check for linked faces
    face_count = self.db.query(Face).filter_by(known_person_id=id).count()
    if face_count > 0:
        raise ValueError(
            f"Cannot delete KnownPerson {id}: {face_count} Face(s) are linked. "
            f"Unlink faces first by setting their known_person_id to NULL."
        )

    self.db.delete(person)
    self.db.commit()
    return True
```

**No cascade concerns:**
- EntitySyncState - Singleton, no relationships
- ImageIntelligence - Only incoming cascade from Entity
- EntityJob - Only incoming cascade from Entity
- FaceMatch - Only incoming cascade from Face
- EntityVersion - Read-only, managed by SQLAlchemy-Continuum

## Testing Strategy

### Test Coverage Areas

1. **Basic CRUD** (all services):
   - Create record
   - Get by ID
   - Get all (paginated and non-paginated)
   - Update record
   - Delete record

2. **Query operations** (all services):
   - Exact match
   - Greater than / less than
   - Multiple filters
   - No results

3. **Retry logic**:
   - Simulate database locks
   - Verify exponential backoff
   - Confirm max retries

4. **Cascade deletes**:
   - Entity → Intelligence, Faces, Jobs
   - Face → FaceMatch
   - KnownPerson → Face.known_person_id set to NULL

5. **Edge cases**:
   - EntityVersion read-only (no create/update/delete)
   - EntitySyncState singleton (prevent multiple rows)
   - ImageIntelligence primary key is entity_id
   - Pagination edge cases (page 0, huge page_size)

6. **Integration**:
   - Multi-service operations
   - Foreign key constraints
   - Transaction rollback on errors

### Test Fixtures

```python
@pytest.fixture
def db_service(db_session, store_config):
    return DBService(db_session, store_config)

@pytest.fixture
def sample_entity(db_service):
    data = EntitySchema(
        is_collection=False,
        label="Test Image",
        md5="abc123",
        # ... other fields
    )
    return db_service.entity.create(data)
```

## Critical Files to Modify/Create

**New files:**
1. `src/store/common/db_service/__init__.py`
2. `src/store/common/db_service/db_service.py`
3. `src/store/common/db_service/schemas.py`
4. `src/store/common/db_service/base.py`
5. `src/store/common/db_service/entity.py`
6. `src/store/common/db_service/intelligence.py`
7. `src/store/common/db_service/face.py`
8. `src/store/common/db_service/sync.py`
9. `tests/test_store/test_db_service/__init__.py`
10. `tests/test_store/test_db_service/test_entity.py`
11. `tests/test_store/test_db_service/test_entity_version.py`
12. `tests/test_store/test_db_service/test_intelligence.py`
13. `tests/test_store/test_db_service/test_face.py`
14. `tests/test_store/test_db_service/test_sync.py`

**Reference files:**
- `src/store/common/models.py` - Model definitions
- `src/store/common/database.py` - @with_retry decorator
- `src/store/store/service.py` - EntityService pattern
- `src/store/m_insight/media_insight.py` - EntityVersion usage
- `src/store/m_insight/schemas.py` - EntityVersionData schema

## Verification Plan

1. **Run unit tests:**
   ```bash
   uv run pytest tests/test_store/test_db_service/ -v
   ```

2. **Test individual services:**
   ```bash
   uv run pytest tests/test_store/test_db_service/test_entity.py::test_create_entity -v
   ```

3. **Coverage check:**
   ```bash
   uv run pytest tests/test_store/test_db_service/ --cov=src/store/common/db_service
   ```

4. **Integration test:**
   - Create Entity with DBService
   - Create Face linked to Entity
   - Delete Entity
   - Verify Face was cascade deleted

5. **Multi-process safety:**
   - Run concurrent operations from multiple processes
   - Verify retry logic handles database locks
   - No data corruption or deadlocks

## Implementation Order

1. **Phase 1: Foundation**
   - Create schemas.py with all Pydantic schemas
   - Create base.py with BaseDBService
   - Set up package structure

2. **Phase 2: Core Services**
   - EntityDBService (most complex)
   - EntityVersionDBService (read-only)
   - Basic tests for these two

3. **Phase 3: Related Services**
   - ImageIntelligenceDBService
   - EntityJobDBService
   - FaceDBService
   - Tests

4. **Phase 4: Remaining Services**
   - KnownPersonDBService
   - FaceMatchDBService
   - EntitySyncStateDBService
   - Tests

5. **Phase 5: Facade & Integration**
   - DBService facade class
   - Integration tests
   - Coverage verification

6. **Phase 6: Documentation**
   - Docstrings for all methods
   - Usage examples in __init__.py
   - Update CLAUDE.md if needed

## Utilities

### Timestamp Helper
All services need current timestamp in milliseconds:

```python
# In base.py or utils.py
from datetime import UTC, datetime

def _now_timestamp() -> int:
    """Return current UTC timestamp in milliseconds."""
    return int(datetime.now(UTC).timestamp() * 1000)
```

Used by: EntityJob, Face, KnownPerson, FaceMatch for `created_at`, `updated_at` fields.

## Summary: Minimal Required Functionality

### Core Operations (All Services)
✅ **Must have:**
- create(data: Schema) → Schema
- get(id: int) → Schema | None
- get_all(page, page_size) → list[Schema] or tuple[list, count]
- update(id: int, data: Schema) → Schema | None
- delete(id: int) → bool
- query(**kwargs) → list[Schema]

### EntityDBService Specific
✅ **Must have:**
- get_with_intelligence_status() - For EntityService compatibility
- get_all_with_intelligence_status() - For EntityService compatibility
- get_children() - For parent-child queries
- delete_all() - For tests/admin cleanup

### EntityVersionDBService Specific
✅ **Must have (read-only):**
- get_entity_versions(entity_id) - Get all versions of an entity
- get_entity_version_by_index(entity_id, version) - Get specific version
- query() - Query version table directly (for mInsight reconciliation)

### Query Features
✅ **Must have:**
- Operators: `=`, `__ne`, `__gt`, `__gte`, `__lt`, `__lte`
- Multiple filters combined with AND
- order_by, ascending parameters
- limit, offset parameters (for manual pagination)

### Special Handling
✅ **Must have:**
- **Decorators on ALL DB methods:**
  - `@timed` - Measures total execution time (including all retries)
  - `@with_retry(max_retries=10)` - Retries on database locks with exponential backoff
  - Order: `@timed` first (outer), then `@with_retry` (inner)

- **Session management:**
  - Each method creates own session: `db = database.SessionLocal()`
  - Always closes in finally block: `finally: db.close()`
  - Pattern: create → try/commit → except/rollback → finally/close

- **Entity validation before writes (CRITICAL for race condition safety):**
  - **Tables with entity_id FK:** ImageIntelligence, EntityJob, Face
  - **Before create/update:** Check `db.query(Entity.id).filter(Entity.id == entity_id).scalar() is not None`
  - **If entity deleted:** Return None if `ignore_exception=True`, otherwise raise ValueError
  - **Reason:** Callbacks may attempt writes after entity cascade deleted

- **ignore_exception parameter:**
  - All `create()` and `update()` methods accept `ignore_exception: bool = False`
  - When `True`: Log error and return None instead of raising
  - When `False`: Raise exception normally
  - **Use case:** Job callbacks where entity may be deleted mid-processing

- **Debug logging (enabled only in DEBUG mode):**
  - Log entry/exit of every DB method with parameters
  - Log entity validation checks
  - Log create vs. update decisions
  - Log exception handling (both raised and ignored)
  - Format: `logger.debug(f"Operation {details}")`

- **Cascade delete logging:**
  - Entity deletion → log Intelligence, Faces, Jobs to be deleted
  - Face deletion → log FaceMatch count
  - KnownPerson deletion → prevent if faces linked

- **Singleton validation:**
  - EntitySyncState always uses id=1
  - Prevent multiple rows

- **Special primary keys:**
  - ImageIntelligence: entity_id (not auto-increment id)
  - Face: deterministic ID (entity_id * 10000 + index)

### Testing
✅ **Must have:**
- Basic CRUD tests for all services
- Query operator tests
- Pagination tests
- Cascade delete tests
- Retry logic simulation test

❌ **Not required initially:**
- Complex join queries (beyond Entity+ImageIntelligence)
- Full-text search
- OR conditions in queries
- Batch operations (bulk insert/update)
- Transaction context managers
- Soft delete helpers
