# Implementation Plan: Update apps/cli_python to Current PySDK APIs

## Summary

Comprehensive update of `apps/cli_python` to:
1. Fix API compatibility issues
2. Add missing database features (face recognition, image similarity)
3. Add entity job tracking to monitor embedding generation progress
4. Add integration tests

## Current State Analysis

**Good News**: Basic CLI functionality is compatible with current pysdk APIs due to factory method usage.

**Critical Gaps Identified**:

1. **API Compatibility** (Breaking Change):
   - PySDK renamed `update_read_auth()` → `update_guest_mode()`
   - Affects 3 files, ~15 lines

2. **Missing Features** (High Priority):
   - Face database: similarity search, known persons management
   - Image similarity: CLIP-based image search
   - Job tracking: monitor embedding generation status/progress
   - Admin: worker capabilities, bulk operations

3. **Testing Gap** (Medium Priority):
   - Only unit tests with mocks exist
   - No integration tests against real server
   - PySDK has comprehensive integration test infrastructure we can adapt

**Scope**: Medium-to-large update. Core: API fix + database features + job tracking. Optional: Integration tests.

## Files to Modify/Create

### Phase 1: API Compatibility (3 files)
1. `src/cl_client_cli/main.py` (lines 1004-1030)
2. `tests/conftest.py` (line 127)
3. `tests/test_cli.py` (lines 864-881)

### Phase 2: Database Features (1 file + new tests)
1. `src/cl_client_cli/main.py` - Add new command groups:
   - `store jobs` command (job tracking)
   - `faces` command group (4 commands)
   - `persons` command group (4 commands)
   - `images` command group (2 commands)
2. `tests/test_cli.py` - Add unit tests for new commands
3. `tests/conftest.py` - Add fixtures for new models (FaceResponse, KnownPersonResponse, etc.)

### Phase 3: Integration Tests (new directory)
1. `tests/test_integration/` - New directory
2. `tests/test_integration/conftest.py` - Adapt from PySDK
3. `tests/test_integration/test_compute_integration.py`
4. `tests/test_integration/test_store_integration.py`
5. `tests/test_integration/test_faces_integration.py`
6. `tests/test_integration/test_images_integration.py`
7. `pytest.ini` - Add integration test marker

## Changes Required

### 1. Update Main CLI Command (main.py:1004-1030)

**Change the command decorator and function name:**
```python
# OLD
@store_admin.command("set-read-auth")
def set_read_auth(ctx: click.Context, enabled: bool):

# NEW
@store_admin.command("set-guest-mode")
def set_guest_mode(ctx: click.Context, enabled: bool):
```

**Update docstring and examples:**
```python
# OLD
"""Enable or disable read authentication (admin only).

Examples:
    cl-client store admin set-read-auth true
    cl-client store admin set-read-auth false
"""

# NEW
"""Enable or disable guest mode (admin only).

Guest mode allows unauthenticated access to the store service.

Examples:
    cl-client store admin set-guest-mode true
    cl-client store admin set-guest-mode false
"""
```

**Update the API call:**
```python
# OLD (line 1017)
result = await manager.update_read_auth(enabled=enabled)

# NEW
result = await manager.update_guest_mode(guest_mode=enabled)
```

**Update success message:**
```python
# OLD (line 1023)
console.print(f"[green]✓ Read authentication {'enabled' if enabled else 'disabled'}[/green]")

# NEW
console.print(f"[green]✓ Guest mode {'enabled' if enabled else 'disabled'}[/green]")
```

### 2. Update Test Fixtures (tests/conftest.py:127)

**Update mock method name:**
```python
# OLD
mock_manager.update_read_auth = AsyncMock()

# NEW
mock_manager.update_guest_mode = AsyncMock()
```

### 3. Update Test Cases (tests/test_cli.py:864-881)

**Update test function name:**
```python
# OLD (line 864)
def test_store_admin_set_read_auth(self, mock_store_manager, sample_store_config):
    """Test store admin set-read-auth command."""

# NEW
def test_store_admin_set_guest_mode(self, mock_store_manager, sample_store_config):
    """Test store admin set-guest-mode command."""
```

**Update StoreConfig in test (line 866-870):**
```python
# The StoreConfig model should remain the same - it still uses read_auth_enabled field
updated_config = StoreConfig(
    read_auth_enabled=False,  # Keep as-is (server model may still use this name)
    updated_at=1704153600000,
    updated_by="admin",
)
```

**Update mock return value (line 871-874):**
```python
# OLD
mock_store_manager.update_read_auth.return_value = StoreOperationResult(
    success="Read authentication configuration updated successfully",
    data=updated_config,
)

# NEW
mock_store_manager.update_guest_mode.return_value = StoreOperationResult(
    success="Guest mode configuration updated successfully",
    data=updated_config,
)
```

**Update CLI invocation (line 877):**
```python
# OLD
result = runner.invoke(cli, ["store", "admin", "set-read-auth", "false"])

# NEW
result = runner.invoke(cli, ["store", "admin", "set-guest-mode", "false"])
```

**Update assertion (line 881):**
```python
# OLD
mock_store_manager.update_read_auth.assert_called_once_with(enabled=False)

# NEW
mock_store_manager.update_guest_mode.assert_called_once_with(guest_mode=False)
```

## Implementation Phases

### Phase 1: API Compatibility Fix (Required)
1. Update `main.py` - Rename command, update API call
2. Update `conftest.py` - Update mock method name
3. Update `test_cli.py` - Update test assertions
4. Run tests to verify changes

### Phase 2: Database Features (High Priority - User Requested)

#### 2A: Job Tracking Commands
Add ability to check if embeddings are generated or still in progress:

**New command group: `store jobs`**
```bash
# Check all jobs for an entity (shows embedding generation status)
cl-client store jobs <entity_id>
```

API: `store_client.get_entity_jobs(entity_id)` → Returns list of jobs with status

**Example output:**
```
Entity Jobs for ID: 123
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Job ID         ┃ Task Type         ┃ Status    ┃ Progress ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│ abc-123        │ face_detection    │ completed │ 100%     │
│ def-456        │ face_embedding    │ completed │ 100%     │
│ ghi-789        │ clip_embedding    │ processing│ 45%      │
└────────────────┴───────────────────┴───────────┴──────────┘
```

#### 2B: Face Database Commands
Add face similarity search and known persons management:

**New command group: `faces`**
```bash
# List faces detected in an entity
cl-client faces list <entity_id>

# Find similar faces (query the face database)
cl-client faces similar <face_id> --limit 10 --threshold 0.7

# Download face embedding
cl-client faces download-embedding <face_id> --output face.npy

# Get face match history
cl-client faces matches <face_id>
```

**New command group: `persons`**
```bash
# List all known persons
cl-client persons list

# Get person details
cl-client persons get <person_id>

# Update person name
cl-client persons update <person_id> --name "John Doe"

# List faces for a person
cl-client persons faces <person_id>
```

APIs used:
- `store_client.get_entity_faces(entity_id)`
- `store_client.find_similar_faces(face_id, limit, threshold)`
- `store_client.download_face_embedding(face_id, dest)`
- `store_client.get_face_matches(face_id)`
- `store_client.get_all_known_persons()`
- `store_client.get_known_person(person_id)`
- `store_client.get_known_person_faces(person_id)`
- `store_client.update_known_person_name(person_id, name)`

#### 2C: Image Similarity Commands
Add CLIP-based image similarity search:

**New command group: `images`**
```bash
# Find similar images (query the CLIP embedding database)
cl-client images similar <entity_id> --limit 10 --threshold 0.85 --details

# Download CLIP embedding
cl-client images download-embedding <entity_id> --output clip.npy
```

APIs used:
- `store_client.find_similar_images(entity_id, limit, score_threshold, include_details)`
- `store_client.download_entity_embedding(entity_id, dest)`

### Phase 3: Integration Tests (Medium Priority)

Add integration tests following PySDK patterns:

**Structure:**
```
apps/cli_python/tests/
├── test_cli.py              # Existing unit tests (keep)
├── conftest.py              # Existing fixtures (keep)
├── test_integration/        # NEW
│   ├── conftest.py          # Adapt from PySDK
│   ├── test_compute_integration.py
│   ├── test_store_integration.py
│   ├── test_faces_integration.py
│   └── test_images_integration.py
```

**Reuse PySDK infrastructure:**
- Server configuration fixtures
- Auth configuration with permission checking
- Test media files (TEST_VECTORS_DIR)
- Auth-aware test patterns (should_succeed helper)

**Key tests to add:**
1. CRUD workflow (create → read → update → delete entity)
2. Embedding generation workflow (upload → check jobs → query similar)
3. Face recognition workflow (upload → detect → search similar faces)
4. Image similarity workflow (upload → generate CLIP → search similar)
5. Authentication scenarios (admin, user, no-auth, guest mode)
6. MQTT callback validation (--watch mode)

**Test invocation:**
```bash
# Unit tests (default, fast)
uv run pytest tests/test_cli.py

# Integration tests (requires running server)
# First, start servers in another terminal:
# uv run server-launcher --config configs/dev.json

# Then run integration tests with correct ports from dev.json:
uv run pytest tests/test_integration/ -m integration \
  --auth-url http://localhost:8010 \
  --compute-url http://localhost:8012 \
  --store-url http://localhost:8011 \
  --username admin \
  --password admin123
```

## Verification Plan

### Phase 1: API Compatibility Fix

**1. Unit Tests**
```bash
cd apps/cli_python
uv run pytest tests/test_cli.py -v -k "guest_mode"
```
Expected: Test `test_store_admin_set_guest_mode` passes

**2. Manual Testing**

First, start the servers:
```bash
# In a separate terminal from repo root
uv run server-launcher --config configs/dev.json
```

Then test the commands (using ports from dev.json):
```bash
# Enable guest mode
uv run cl-client \
  --auth-url http://localhost:8010 \
  --compute-url http://localhost:8012 \
  --store-url http://localhost:8011 \
  --username admin --password admin \
  store admin set-guest-mode true

# Disable guest mode
uv run cl-client \
  --auth-url http://localhost:8010 \
  --store-url http://localhost:8011 \
  --username admin --password admin \
  store admin set-guest-mode false
```
Expected: Commands work, output shows "Guest mode enabled/disabled"

### Phase 2: Database Features

**1. Job Tracking Test**

Start servers first:
```bash
uv run server-launcher --config configs/dev.json
```

Then test (using dev.json ports):
```bash
# Upload image
uv run cl-client \
  --auth-url http://localhost:8010 \
  --store-url http://localhost:8011 \
  --username user --password pass \
  store create --label "Test Image" --file test.jpg

# Check jobs (should show face_detection, face_embedding, clip_embedding)
uv run cl-client \
  --auth-url http://localhost:8010 \
  --store-url http://localhost:8011 \
  --username user --password pass \
  store jobs <entity_id>
```
Expected: Table showing all jobs with status (completed, processing, or queued)

**2. Face Database Test**
```bash
# List faces in entity
uv run cl-client --username user --password pass faces list <entity_id>

# Find similar faces
uv run cl-client --username user --password pass faces similar <face_id> --limit 5

# List known persons
uv run cl-client --username user --password pass persons list
```
Expected: Rich tables showing face data, similarity scores, person info

**3. Image Similarity Test**
```bash
# Find similar images
uv run cl-client --username user --password pass images similar <entity_id> --limit 5

# Download embedding
uv run cl-client --username user --password pass images download-embedding <entity_id> --output clip.npy
```
Expected: Table with similar images and scores, NPY file downloaded

### Phase 3: Integration Tests

**1. Run All Integration Tests**
```bash
cd apps/cli_python

# Start servers first (in another terminal from repo root)
# uv run server-launcher --config configs/dev.json

# Then run integration tests with ports from dev.json
uv run pytest tests/test_integration/ -v -m integration \
  --auth-url http://localhost:8010 \
  --compute-url http://localhost:8012 \
  --store-url http://localhost:8011 \
  --username admin \
  --password admin123
```
Expected: All integration tests pass against running server

**2. Verify Coverage**
```bash
# Unit tests coverage (should remain ~80%)
uv run pytest tests/test_cli.py --cov=cl_client_cli --cov-report=term

# Integration tests (separate coverage)
uv run pytest tests/test_integration/ -m integration --cov=cl_client_cli
```

### Complete Workflow Test

**End-to-end face recognition workflow:**

Start servers:
```bash
uv run server-launcher --config configs/dev.json
```

Then run the workflow (using dev.json ports):
```bash
# Set up URL flags for convenience
AUTH_URL="http://localhost:8010"
STORE_URL="http://localhost:8011"
COMPUTE_URL="http://localhost:8012"

# 1. Upload image with faces
uv run cl-client --auth-url $AUTH_URL --store-url $STORE_URL \
  --username admin --password admin \
  store create --label "Family Photo" --file family.jpg
# Output: Created entity 123

# 2. Monitor embedding generation
uv run cl-client --auth-url $AUTH_URL --store-url $STORE_URL \
  --username admin --password admin \
  store jobs 123
# Wait until all jobs show "completed"

# 3. List detected faces
uv run cl-client --auth-url $AUTH_URL --store-url $STORE_URL \
  --username admin --password admin \
  faces list 123
# Output: Table with face IDs, bounding boxes, confidence

# 4. Find similar faces
uv run cl-client --auth-url $AUTH_URL --store-url $STORE_URL \
  --username admin --password admin \
  faces similar <face_id> --limit 5
# Output: Table with similar faces and scores

# 5. Check known persons
uv run cl-client --auth-url $AUTH_URL --store-url $STORE_URL \
  --username admin --password admin \
  persons list
# Output: List of automatically identified persons

# 6. Find similar images
uv run cl-client --auth-url $AUTH_URL --store-url $STORE_URL \
  --username admin --password admin \
  images similar 123 --limit 5
# Output: Similar images based on CLIP embeddings
```

## Notes

- **No other pysdk API changes required**: The CLI already uses factory methods (`SessionManager.create_compute_client()`, `SessionManager.create_store_manager()`) which insulate it from internal pysdk changes
- **Backwards compatibility**: The command name change (`set-read-auth` → `set-guest-mode`) is a breaking change for any scripts using this command, but this is acceptable since we're updating to match the new pysdk terminology
- **Test coverage**: Current coverage is 80.48%, should remain at similar level after changes
- **Documentation**: The README.md and CLI_TEST_RESULTS.md may need updates if they reference the old command name (check and update if needed)

## Edge Cases and Considerations

### Phase 1
1. **Server compatibility**: Ensure the server's store service has been updated to support the `guest_mode` parameter
2. **Error messages**: Verify error messages from the server make sense with the new terminology
3. **Help text**: The `--help` output will automatically update due to the docstring changes

### Phase 2
1. **Empty results**: Handle cases where entities have no faces detected
2. **No embeddings**: Handle entities where embedding jobs haven't completed yet
3. **Similarity thresholds**: Provide good default thresholds (0.7 for faces, 0.85 for images)
4. **Large result sets**: Use pagination or limit results to prevent overwhelming output
5. **Download paths**: Validate output paths for embedding downloads
6. **Missing store_client methods**: Need to access `_store_client` from `StoreManager` since database methods are in `StoreClient`, not `StoreManager`

### Phase 3
1. **Server startup time**: Integration tests need to wait for server readiness
2. **Test isolation**: Clean up entities/jobs after each test
3. **Async workers**: Wait for worker availability before running tests
4. **Media files**: Ensure TEST_VECTORS_DIR is set correctly
5. **Output parsing**: CLI output uses Rich tables - need regex to extract IDs

## Server Configuration

**Starting the servers for testing:**
```bash
# From repository root
uv run server-launcher --config configs/dev.json
```

**Port configuration (from configs/dev.json):**
- Auth service: `http://localhost:8010`
- Store service: `http://localhost:8011`
- Compute service: `http://localhost:8012`
- Workers: 2 workers with all 9 task types enabled

**CLI Configuration:**
The CLI is already configurable via flags or environment variables:

```bash
# Via flags
uv run cl-client \
  --auth-url http://localhost:8010 \
  --compute-url http://localhost:8012 \
  --store-url http://localhost:8011 \
  --username admin --password admin \
  <command>

# Via environment variables
export CL_AUTH_URL=http://localhost:8010
export CL_COMPUTE_URL=http://localhost:8012
export CL_STORE_URL=http://localhost:8011
export CL_USERNAME=admin
export CL_PASSWORD=admin
uv run cl-client <command>
```

## Implementation Notes

### Accessing StoreClient from CLI

The database methods (`get_entity_faces`, `find_similar_faces`, etc.) are in `StoreClient`, not `StoreManager`. The CLI currently uses `StoreManager` which wraps `StoreClient`.

**Two approaches:**

1. **Direct access** (simpler): Use `manager._store_client.method()` directly
2. **Add to StoreManager** (cleaner): Add wrapper methods to `StoreManager` that delegate to `_store_client`

**Recommendation**: Use direct access for Phase 2 (faster implementation), optionally refactor to add wrappers to StoreManager in Phase 3.

### Command Organization

New CLI structure after Phase 2:
```
cl-client
├── clip-embedding        # Existing
├── dino-embedding        # Existing
├── face-detection        # Existing
├── face-embedding        # Existing
├── hash                  # Existing
├── exif                  # Existing
├── media-thumbnail       # Existing
├── image-conversion      # Existing
├── hls-streaming         # Existing
├── download              # Existing
├── store                 # Existing + enhanced
│   ├── list              # Existing
│   ├── create            # Existing
│   ├── get               # Existing
│   ├── update            # Existing
│   ├── patch             # Existing
│   ├── delete            # Existing
│   ├── versions          # Existing
│   ├── jobs              # NEW - job tracking
│   └── admin             # Existing + updated
│       ├── config        # Existing
│       └── set-guest-mode # Updated (was set-read-auth)
├── faces                 # NEW group
│   ├── list              # NEW
│   ├── similar           # NEW
│   ├── download-embedding # NEW
│   └── matches           # NEW
├── persons               # NEW group
│   ├── list              # NEW
│   ├── get               # NEW
│   ├── update            # NEW
│   └── faces             # NEW
├── images                # NEW group
│   ├── similar           # NEW
│   └── download-embedding # NEW
└── user                  # Existing
    ├── create            # Existing
    ├── list              # Existing
    ├── get               # Existing
    ├── update            # Existing
    └── delete            # Existing
```

Total new commands: 11 (1 job tracking + 4 faces + 4 persons + 2 images)

## Success Criteria

### Phase 1 (Required)
- ✅ Unit tests pass
- ✅ `set-guest-mode` command works with real server
- ✅ No regressions in existing commands

### Phase 2 (High Priority)
- ✅ All 11 new commands implemented
- ✅ Job tracking shows embedding generation progress
- ✅ Face similarity search returns results
- ✅ Image similarity search returns results
- ✅ Known persons management works
- ✅ Embedding downloads succeed
- ✅ Unit tests for new commands pass (with mocks)
- ✅ Manual testing against real server succeeds

### Phase 3 (Medium Priority)
- ✅ Integration test infrastructure set up
- ✅ At least 20 integration tests passing
- ✅ Tests cover all auth scenarios (admin, user, guest, no-auth)
- ✅ Tests cover complete workflows (upload → process → query)
- ✅ CI can run integration tests with docker-compose

## Estimated Effort

- **Phase 1**: 1-2 hours (simple API rename)
- **Phase 2**: 6-8 hours (11 new commands + tests + models)
- **Phase 3**: 4-6 hours (integration test infrastructure + 20+ tests)

**Total**: 11-16 hours for complete implementation
