# Implementation Plan: Update CLI Python App for pysdk Changes

## Overview

Update the CLI Python app (`/Users/anandasarangaram/Work/cl_server/apps/cli_python`) to:
1. Align with recent pysdk changes
2. **Make URLs and credentials mandatory (no localhost defaults)**
3. Add new features and commands

**Status**: Most critical changes already compatible ✓. Need to make URLs/credentials mandatory and add new features.

## What Changed in pysdk

### Already Compatible ✓
- CLI already uses `ServerPref` (not old `ServerConfig`)
- CLI already has `asyncio_mode = "strict"` in pytest config
- No direct MQTT parameter usage (uses `mqtt_url` from ServerPref)

### Breaking Changes - MUST FIX
1. **Admin API renamed** (affects CLI):
   - Model: `StoreConfig` → `StorePref`
   - Method: `StoreManager.get_config()` → `StoreManager.get_pref()`
   - Endpoint: `/admin/config` → `/admin/pref`
   - Endpoint: `/admin/config/guest-mode` → `/admin/pref/guest-mode`
   - **Impact**: CLI's `store admin config` command needs update

### New Features to Add
1. **New StoreManager methods**:
   - `delete_face(face_id: int)` - Delete a face
   - `get_audit_report()` - Generate audit report (admin only, uses `/system/audit` endpoint)
   - `clear_orphans()` - Clear orphaned resources (admin only, uses `/system/clear-orphans` endpoint)
   - `get_entity_intelligence(entity_id: int)` - Get intelligence data

2. **New models** in `store_models`:
   - `StorePref` (renamed from `StoreConfig`)
   - `AuditReport`, `CleanupReport`
   - `OrphanedFileInfo`, `OrphanedFaceInfo`, `OrphanedVectorInfo`, `OrphanedMqttInfo`

3. **New model** in `intelligence_models`:
   - `EntityIntelligenceData`

## Implementation Steps

### Step 0: Make URLs Mandatory and Add MQTT URL

**CRITICAL CHANGE**: Remove localhost defaults for URLs and add missing mqtt-url parameter.

**File**: `src/cl_client_cli/main.py` (lines 228-279)

#### Changes Required:

1. **Add `--mqtt-url` option** (currently missing):
```python
@click.option(
    "--mqtt-url",
    envvar="CL_MQTT_URL",
    required=True,
    help="MQTT broker URL (required, e.g., mqtt://mqtt.example.com:1883)",
)
```

2. **Make all URL options required** - Remove localhost defaults and add `required=True`:
```python
@click.option(
    "--auth-url",
    envvar="CL_AUTH_URL",
    required=True,  # NEW - was: default="http://localhost:8000"
    help="Auth service URL (required)",
)
@click.option(
    "--compute-url",
    envvar="CL_COMPUTE_URL",
    required=True,  # NEW - was: default="http://localhost:8002"
    help="Compute service URL (required)",
)
@click.option(
    "--store-url",
    envvar="CL_STORE_URL",
    required=True,  # NEW - was: default="http://localhost:8001"
    help="Store service URL (required)",
)
```

3. **Keep credentials optional** - No changes to username/password (stay Optional):
```python
@click.option(
    "--username",
    envvar="CL_USERNAME",
    help="Username for authentication (optional - uses no-auth mode if not provided)",
)
@click.option(
    "--password",
    envvar="CL_PASSWORD",
    help="Password for authentication (optional - uses no-auth mode if not provided)",
)
```

4. **Keep `--no-auth` flag** - No changes (lines 256-261):
```python
@click.option(
    "--no-auth",
    is_flag=True,
    default=False,
    help="Disable authentication (use no-auth mode)",
)
```

5. **Update `cli()` function signature** (line 270):
```python
def cli(
    ctx: click.Context,
    username: Optional[str],  # Keep Optional
    password: Optional[str],  # Keep Optional
    auth_url: str,  # Now required
    compute_url: str,  # Now required
    store_url: str,  # Now required
    mqtt_url: str,  # NEW parameter (required)
    no_auth: bool,  # Keep this
    output_json: bool,
):
```

6. **Update ServerPref initialization** (line 314):
```python
ctx.obj["server_config"] = ServerPref(
    auth_url=auth_url,
    compute_url=compute_url,
    store_url=store_url,
    mqtt_url=mqtt_url,  # NEW
)
```

7. **Keep no-auth logic unchanged** in helper functions:
   - `get_client()` (line 321-349): Keep existing no-auth conditional
   - `get_store_manager()` (line 376-401): Keep existing guest mode logic
   - Keep all references to `no_auth` flag

8. **Update docstring examples** (lines 280-298) to show required URLs:
```python
"""CL Client CLI - Command-line interface for compute, store, and auth operations.

Examples:
  # No-auth mode (credentials not required)
  cl-client --auth-url http://auth.example.com:8000 \
    --compute-url http://compute.example.com:8002 \
    --store-url http://store.example.com:8001 \
    --mqtt-url mqtt://mqtt.example.com:1883 \
    --no-auth \
    clip-embedding embed image.jpg --watch

  # With authentication
  cl-client --username user --password pass \
    --auth-url http://auth.example.com:8000 \
    --compute-url http://compute.example.com:8002 \
    --store-url http://store.example.com:8001 \
    --mqtt-url mqtt://mqtt.example.com:1883 \
    clip-embedding embed image.jpg

  # Using environment variables (recommended)
  export CL_AUTH_URL=http://auth.example.com:8000
  export CL_COMPUTE_URL=http://compute.example.com:8002
  export CL_STORE_URL=http://store.example.com:8001
  export CL_MQTT_URL=mqtt://mqtt.example.com:1883
  export CL_USERNAME=user
  export CL_PASSWORD=pass
  cl-client clip-embedding embed image.jpg
"""
```

#### Impact Analysis:

**Breaking Changes**:
- Users must now provide all URLs (no localhost defaults)
- Cannot use CLI without specifying URLs
- Must add `--mqtt-url` parameter

**No Breaking Changes**:
- Credentials remain optional (no-auth mode still works)
- `--no-auth` flag remains available
- Existing auth logic unchanged

**Migration Path**:
- Users should set environment variables for convenience (especially for URLs)
- Update all documentation and examples to show required URLs
- Update integration tests to provide all required URL parameters

### Step 1: Update Model Imports and Fix Admin Method Calls

**CRITICAL**: pysdk renamed `StoreConfig` → `StorePref` and `get_config()` → `get_pref()`

#### File: `src/cl_client_cli/main.py`

**1.1 Update imports** (line 21-22):

```python
from cl_client.store_models import (
    AuditReport,           # NEW - for audit reports
    CleanupReport,         # NEW - for cleanup reports
    StorePref,             # RENAMED from StoreConfig
    # Keep existing: Entity, EntityListResponse, EntityVersion, etc.
)
from cl_client.intelligence_models import EntityIntelligenceData  # NEW
```

**1.2 Fix admin method call** (line 1117):

Change from:
```python
result = await manager.get_config()
```

To:
```python
result = await manager.get_pref()
```

**Note**: Command name can stay as `store admin config` for backward compatibility, but internally calls `get_pref()`.

#### File: `tests/conftest.py`

**Update fixture** (around line 219-226):

```python
@pytest.fixture
def sample_store_pref() -> StorePref:  # Renamed from sample_store_config
    """Create a sample store preference."""
    return StorePref(  # Renamed from StoreConfig
        guest_mode=False,
        updated_at=1704067200000,
        updated_by="admin",
    )
```

**Update mock** (line 141):

```python
mock_manager.get_pref = AsyncMock()  # Renamed from get_config
```

#### Files: Test imports to update

**`tests/test_cli.py`** (line 9):
```python
from cl_client.store_models import Entity, EntityListResponse, StorePref, StoreOperationResult
# Changed: StoreConfig → StorePref
```

**`tests/test_integration/test_auth_errors_cli.py`** (line 19):
```python
from cl_client.store_models import StorePref
# Changed: StoreConfig → StorePref
```

**`tests/test_integration/test_store_cli.py`** (line 19):
```python
from cl_client.store_models import Entity, EntityListResponse, EntityVersion, StorePref
# Changed: StoreConfig → StorePref
```

### Step 2: Add Face Delete Command

**File**: `src/cl_client_cli/main.py` (after store commands, ~line 1090)

Create new command group and delete command:

```python
@store.group("face")
def face():
    """Manage faces in the store."""
    pass

@face.command("delete")
@click.argument("face_id", type=int)
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def delete_face(ctx: click.Context, face_id: int, yes: bool):
    """Delete a face from the database."""
    # Implementation pattern: follow store delete command (lines 991-1039)
    # - Require confirmation unless --yes
    # - Use get_store_manager()
    # - Call manager.delete_face(face_id)
    # - Output success/error via output_sdk_result()
```

### Step 3: Add Entity Intelligence Command

**File**: `src/cl_client_cli/main.py` (after store get, ~line 870)

```python
@store.command("intelligence")
@click.argument("entity_id", type=int)
@click.option("--output", type=click.Path(), help="Save output to file")
@click.pass_context
def get_intelligence(ctx: click.Context, entity_id: int, output: str | None):
    """Get intelligence data for an entity."""
    # Implementation pattern: follow store get command (lines 821-869)
    # - Use get_store_manager()
    # - Call manager.get_entity_intelligence(entity_id)
    # - Handle None response (no intelligence data)
    # - Output via output_sdk_result()
    # - Optional file save with --output
```

### Step 4: Add Admin Audit Report Command

**File**: `src/cl_client_cli/main.py` (in store_admin group, after line 1168)

```python
@store_admin.command("audit-report")
@click.option("--output", type=click.Path(), help="Save report to file")
@click.pass_context
def audit_report(ctx: click.Context, output: str | None):
    """Generate audit report of orphaned resources (admin only)."""
    # Implementation pattern: follow store admin config (lines 1104-1132)
    # - Require authentication (admin)
    # - Use get_store_manager()
    # - Call manager.get_audit_report()
    # - Output AuditReport model
    # - Optional file save with --output
    # - Display summary in human mode
```

### Step 5: Add Admin Clear Orphans Command

**File**: `src/cl_client_cli/main.py` (in store_admin group, after audit-report)

```python
@store_admin.command("clear-orphans")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def clear_orphans(ctx: click.Context, yes: bool):
    """Remove all orphaned resources (admin only)."""
    # Implementation pattern: similar to delete commands with confirmation
    # - Require authentication (admin)
    # - Require confirmation unless --yes
    # - Use get_store_manager()
    # - Call manager.clear_orphans()
    # - Output CleanupReport with deletion counts
```

### Step 6: Add Test Fixtures

**File**: `tests/conftest.py` (after existing fixtures, ~line 226)

Add fixtures for new models:

```python
@pytest.fixture
def sample_audit_report() -> AuditReport:
    """Create sample audit report."""
    # Return AuditReport with sample orphaned resources

@pytest.fixture
def sample_cleanup_report() -> CleanupReport:
    """Create sample cleanup report."""
    # Return CleanupReport with deletion counts

@pytest.fixture
def sample_entity_intelligence() -> EntityIntelligenceData:
    """Create sample intelligence data."""
    # Return EntityIntelligenceData with sample data
```

Update mock_store_manager fixture to include new methods:
```python
mock_manager.delete_face = AsyncMock()
mock_manager.get_audit_report = AsyncMock()
mock_manager.clear_orphans = AsyncMock()
mock_manager.get_entity_intelligence = AsyncMock()
```

### Step 7: Add Unit Tests

**File**: Create `tests/test_new_commands.py` or extend `tests/test_cli.py`

Add unit tests for:
- `test_face_delete_command` - Test face deletion with/without --yes
- `test_entity_intelligence_command` - Test intelligence retrieval
- `test_audit_report_command` - Test audit report generation
- `test_clear_orphans_command` - Test orphan cleanup with/without --yes

Pattern: Follow existing CLI test patterns using mocked managers and fixtures.

### Step 8: Add Integration Tests

**File**: `tests/test_integration/test_store_cli.py` or new file

Add integration tests for new commands (require live services):
- `test_face_delete_integration` - Actually delete a face
- `test_entity_intelligence_integration` - Get real intelligence data
- `test_audit_report_integration` (admin_only marker)
- `test_clear_orphans_integration` (admin_only marker)

Pattern: Use `cli_runner.invoke()` and `parse_cli_json()` helpers.

### Step 9: Update Documentation

**File**: `README.md`

Add documentation for new commands in the "Available Commands" section:

1. **Face Management** section:
   - `cl-client store face delete <face_id>` command
   - Example usage with --yes flag

2. **Store Admin Commands** section:
   - `cl-client store admin audit-report` command
   - `cl-client store admin clear-orphans` command
   - Example usage and output format

3. **Entity Intelligence** section:
   - `cl-client store intelligence <entity_id>` command
   - Example usage with --output flag

Update command count in introduction if mentioned.

## Critical Files

### To Modify:
- `src/cl_client_cli/main.py` - **PRIMARY FILE**
  - Add `--mqtt-url` parameter
  - Make all URLs required (remove defaults)
  - Fix imports: `StoreConfig` → `StorePref`, add new models
  - Fix method call: `get_config()` → `get_pref()` (line 1117)
  - Add 4 new commands (~200 lines)

- `tests/conftest.py` - Update fixtures
  - Rename `StoreConfig` → `StorePref`
  - Add fixtures for new models (~50 lines)

- `tests/test_cli.py` - Update imports
  - Change `StoreConfig` → `StorePref`

- `tests/test_integration/test_store_cli.py` - Update imports and add tests
  - Change `StoreConfig` → `StorePref`
  - Add integration tests for new commands (~150 lines)

- `tests/test_integration/test_auth_errors_cli.py` - Update imports
  - Change `StoreConfig` → `StorePref`

- `README.md` - Update documentation
  - Show required URL parameters in examples
  - Add documentation for new commands (~100 lines)

### No Changes Needed:
- `pyproject.toml` - Already compatible
- `tests/test_integration/conftest.py` - No async fixture changes needed

## Verification Steps

### Manual Testing

**Note**: All commands now require URLs to be specified (no localhost defaults).

Test each new command:

```bash
# Set up environment variables (recommended)
export CL_AUTH_URL=http://auth.example.com:8000
export CL_COMPUTE_URL=http://compute.example.com:8002
export CL_STORE_URL=http://store.example.com:8001
export CL_MQTT_URL=mqtt://mqtt.example.com:1883
export CL_USERNAME=admin
export CL_PASSWORD=admin

# 1. Face deletion
cl-client store face delete 123

# 2. Entity intelligence
cl-client store intelligence 456

# 3. Audit report (admin)
cl-client store admin audit-report

# 4. Clear orphans (admin)
cl-client store admin clear-orphans --yes

# Or specify all parameters directly
cl-client --auth-url http://auth.example.com:8000 \
  --compute-url http://compute.example.com:8002 \
  --store-url http://store.example.com:8001 \
  --mqtt-url mqtt://mqtt.example.com:1883 \
  --username admin --password admin \
  store face delete 123
```

### Automated Testing

```bash
# Unit tests
pytest tests/test_cli.py -v

# Integration tests (requires running services)
# Note: These also need to be updated to provide all required URLs
pytest tests/test_integration/ \
  --auth-url=http://auth.example.com:8000 \
  --compute-url=http://compute.example.com:8002 \
  --store-url=http://store.example.com:8001 \
  --username=admin \
  --password=admin

# Coverage check (maintain 70%+)
pytest --cov=cl_client_cli --cov-report=html

# Type checking
basedpyright src/cl_client_cli/
```

### JSON Output Mode

Verify all commands work with `--json` flag (URLs still required):

```bash
# With environment variables set
cl-client --json store face delete 123 --yes
cl-client --json store intelligence 456
cl-client --json store admin audit-report
cl-client --json store admin clear-orphans --yes

# Test no-auth mode with new URL requirements
cl-client --auth-url http://auth.example.com:8000 \
  --compute-url http://compute.example.com:8002 \
  --store-url http://store.example.com:8001 \
  --mqtt-url mqtt://mqtt.example.com:1883 \
  --no-auth --json \
  clip-embedding embed image.jpg
```

## Success Criteria

- ✓ Admin API breaking changes fixed (`StoreConfig` → `StorePref`, `get_config()` → `get_pref()`)
- ✓ All URL parameters are mandatory (no localhost defaults)
- ✓ MQTT URL parameter added
- ✓ All 4 new commands implemented and working
- ✓ Commands follow existing CLI patterns (confirmation, JSON output, error handling)
- ✓ Unit tests pass
- ✓ Integration tests pass with live services
- ✓ Documentation is complete and accurate
- ✓ Code coverage remains ≥70%
- ✓ Type checking passes
- ✓ Both `--json` and human-readable output modes work

## Notes

- All changes are additive - no breaking changes to existing CLI
- Commands follow established patterns from existing store commands
- Admin commands require authentication and have appropriate safeguards
- Face delete and clear-orphans include confirmation prompts for safety
