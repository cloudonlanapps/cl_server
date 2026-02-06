# Test Update Guide: Adding --json Flag and SDK Model Validation

This guide shows how to update existing CLI integration tests to use the --json flag and validate output with SDK Pydantic models.

## Overview

All CLI integration tests should:
1. Use `--json` flag in CLI invocations
2. Parse output using `parse_cli_json()` or `parse_cli_json_list()` from conftest.py
3. Validate output against SDK Pydantic models from `cl_client.models`
4. Use type-safe assertions on SDK model fields

## Helper Functions Available

From `conftest.py`:

```python
# For single SDK models
parse_cli_json(result, SDKModel) -> SDKModel

# For lists of SDK models
parse_cli_json_list(result, SDKModel) -> list[SDKModel]

# For success responses (SuccessResponse)
assert_cli_success(result, expected_message="...") -> dict

# For error responses (ErrorResponse)
assert_cli_error(result, error_substring="...") -> dict
```

## Pattern 1: Store Commands Returning SDK Models

### Before (String-based assertions):

```python
def test_store_list(cli_runner, cli_env):
    """Test store list command."""
    result = cli_runner.invoke(
        cli,
        [
            "--username", cli_env["CL_USERNAME"],
            "--password", cli_env["CL_PASSWORD"],
            "--auth-url", cli_env["CL_AUTH_URL"],
            "--store-url", cli_env["CL_STORE_URL"],
            "store", "list",
            "--page", "1",
            "--page-size", "10",
        ],
    )

    assert result.exit_code == 0, f"List failed: {result.output}"
    assert "page" in result.output.lower() or "entities" in result.output.lower()
```

### After (SDK model validation):

```python
from cl_client.models import EntityListResponse

def test_store_list(cli_runner, cli_env):
    """Test store list command with JSON output."""
    result = cli_runner.invoke(
        cli,
        [
            "--username", cli_env["CL_USERNAME"],
            "--password", cli_env["CL_PASSWORD"],
            "--auth-url", cli_env["CL_AUTH_URL"],
            "--store-url", cli_env["CL_STORE_URL"],
            "--json",  # ADD THIS
            "store", "list",
            "--page", "1",
            "--page-size", "10",
        ],
    )

    # Parse and validate with SDK model
    data = parse_cli_json(result, EntityListResponse)

    # Type-safe assertions on SDK model fields
    assert data.pagination.page == 1
    assert data.pagination.page_size == 10
    assert isinstance(data.items, list)
```

## Pattern 2: Store Commands Returning Success

### Before:

```python
def test_store_delete(cli_runner, cli_env, test_helper, test_image):
    """Test store delete command."""
    entity_id = test_helper.create_test_entity(
        label="test_store_delete",
        image_path=test_image,
    )

    result = cli_runner.invoke(
        cli,
        [
            "--username", cli_env["CL_USERNAME"],
            "--password", cli_env["CL_PASSWORD"],
            "--auth-url", cli_env["CL_AUTH_URL"],
            "--store-url", cli_env["CL_STORE_URL"],
            "store", "delete", str(entity_id), "--yes",
        ],
    )

    assert result.exit_code == 0, f"Delete failed: {result.output}"
    assert "deleted" in result.output.lower() or "✓" in result.output
```

### After:

```python
def test_store_delete(cli_runner, cli_env, test_helper, test_image):
    """Test store delete command with JSON output."""
    entity_id = test_helper.create_test_entity(
        label="test_store_delete",
        image_path=test_image,
    )

    result = cli_runner.invoke(
        cli,
        [
            "--username", cli_env["CL_USERNAME"],
            "--password", cli_env["CL_PASSWORD"],
            "--auth-url", cli_env["CL_AUTH_URL"],
            "--store-url", cli_env["CL_STORE_URL"],
            "--json",  # ADD THIS
            "store", "delete", str(entity_id), "--yes",
        ],
    )

    # Validate success response
    assert_cli_success(result, "Deleted entity")
```

## Pattern 3: Database Commands Returning Lists

### Before:

```python
def test_faces_list_command(cli_runner, cli_env, test_helper, test_image):
    """Test faces list command."""
    entity_id = test_helper.create_test_entity(
        label="test_faces_list",
        image_path=test_image,
    )
    face_id = test_helper.wait_for_faces(entity_id)

    result = cli_runner.invoke(
        cli,
        [
            "--username", cli_env["CL_USERNAME"],
            "--password", cli_env["CL_PASSWORD"],
            "--store-url", cli_env["CL_STORE_URL"],
            "faces", "list", str(entity_id),
        ],
    )

    assert result.exit_code == 0
    assert "face" in result.output.lower()
```

### After:

```python
from cl_client.models import Face

def test_faces_list_command(cli_runner, cli_env, test_helper, test_image):
    """Test faces list command with JSON output."""
    entity_id = test_helper.create_test_entity(
        label="test_faces_list",
        image_path=test_image,
    )
    face_id = test_helper.wait_for_faces(entity_id)

    result = cli_runner.invoke(
        cli,
        [
            "--username", cli_env["CL_USERNAME"],
            "--password", cli_env["CL_PASSWORD"],
            "--store-url", cli_env["CL_STORE_URL"],
            "--json",  # ADD THIS
            "faces", "list", str(entity_id),
        ],
    )

    # Parse list of Face models
    faces = parse_cli_json_list(result, Face)

    # Type-safe assertions
    assert len(faces) > 0
    assert faces[0].id == face_id
    assert faces[0].entity_id == entity_id
    assert faces[0].confidence > 0
```

## Pattern 4: Plugin Commands Returning JobResponse

### Before:

```python
def test_clip_embed_http_polling(cli_runner, cli_env, test_image):
    """Test clip-embedding embed with HTTP polling."""
    result = cli_runner.invoke(
        cli,
        [
            "--username", cli_env["CL_USERNAME"],
            "--password", cli_env["CL_PASSWORD"],
            "--compute-url", cli_env["CL_COMPUTE_URL"],
            "clip-embedding", "embed", str(test_image),
        ],
    )

    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert "completed" in result.output.lower() or "✓" in result.output
```

### After:

```python
from cl_client.models import JobResponse

def test_clip_embed_http_polling(cli_runner, cli_env, test_image):
    """Test clip-embedding embed with HTTP polling and JSON output."""
    result = cli_runner.invoke(
        cli,
        [
            "--username", cli_env["CL_USERNAME"],
            "--password", cli_env["CL_PASSWORD"],
            "--compute-url", cli_env["CL_COMPUTE_URL"],
            "--json",  # ADD THIS
            "clip-embedding", "embed", str(test_image),
        ],
    )

    # Parse and validate JobResponse
    job = parse_cli_json(result, JobResponse)

    # Type-safe assertions
    assert job.status == "completed"
    assert job.task_type == "clip_embedding"
    assert job.job_id is not None
```

## Pattern 5: Error Handling Tests

### Before:

```python
def test_clip_embed_invalid_file(cli_runner, cli_env):
    """Test clip-embedding embed with missing file."""
    result = cli_runner.invoke(
        cli,
        [
            "--username", cli_env["CL_USERNAME"],
            "--password", cli_env["CL_PASSWORD"],
            "--compute-url", cli_env["CL_COMPUTE_URL"],
            "clip-embedding", "embed", "/nonexistent/file.jpg",
        ],
    )

    assert result.exit_code != 0
    assert "error" in result.output.lower() or "not found" in result.output.lower()
```

### After:

```python
def test_clip_embed_invalid_file(cli_runner, cli_env):
    """Test clip-embedding embed with missing file and JSON error."""
    result = cli_runner.invoke(
        cli,
        [
            "--username", cli_env["CL_USERNAME"],
            "--password", cli_env["CL_PASSWORD"],
            "--compute-url", cli_env["CL_COMPUTE_URL"],
            "--json",  # ADD THIS
            "clip-embedding", "embed", "/nonexistent/file.jpg",
        ],
    )

    # Validate error response
    assert_cli_error(result, "not found")
```

## SDK Models Reference

### Common SDK Models to Import

```python
from cl_client.models import (
    # Job models
    JobResponse,

    # Entity models
    Entity,
    EntityListResponse,

    # Face models
    Face,

    # Person models
    KnownPerson,

    # Similarity models
    SimilaritySearchResponse,

    # User models
    User,

    # Config models
    StoreConfig,
)
```

### Model Field Examples

**JobResponse:**
- `job_id: str`
- `status: str` ("completed", "failed", "queued", "in_progress")
- `task_type: str` ("clip_embedding", "face_detection", etc.)
- `entity_id: int | None`
- `progress: int`
- `error_message: str | None`

**EntityListResponse:**
- `items: list[Entity]`
- `pagination: PaginationInfo`
  - `page: int`
  - `page_size: int`
  - `total_items: int`
  - `total_pages: int`

**Entity:**
- `id: int`
- `label: str | None`
- `is_collection: bool`
- `parent_id: int | None`
- `file_size: int | None`
- `width: int | None`
- `height: int | None`

**Face:**
- `id: int`
- `entity_id: int`
- `confidence: float`
- `bbox: BoundingBox`
- `known_person_id: int | None`

## Checklist for Updating Each Test

- [ ] Add `--json` flag to CLI invocation
- [ ] Import appropriate SDK model from `cl_client.models`
- [ ] Replace string-based assertions with `parse_cli_json()` or `parse_cli_json_list()`
- [ ] Use type-safe assertions on SDK model fields
- [ ] For success responses, use `assert_cli_success()`
- [ ] For error responses, use `assert_cli_error()`
- [ ] Verify test still passes with `pytest test_file.py -v`

## Files to Update (66 tests across 13 files)

1. `test_clip_embedding_cli.py` - 5 tests
2. `test_dino_embedding_cli.py` - 4 tests
3. `test_exif_cli.py` - 4 tests
4. `test_face_detection_cli.py` - 4 tests
5. `test_face_embedding_cli.py` - 4 tests
6. `test_hash_cli.py` - 4 tests
7. `test_hls_streaming_cli.py` - 4 tests
8. `test_image_conversion_cli.py` - 5 tests
9. `test_media_thumbnail_cli.py` - 5 tests
10. `test_store_cli.py` - 8 tests
11. `test_user_management_cli.py` - 8 tests
12. `test_auth_errors_cli.py` - 6 tests
13. `test_database_features.py` - 11 tests

## Benefits of This Approach

1. **Type Safety:** SDK models provide compile-time type checking with basedpyright
2. **Validation:** Pydantic automatically validates all fields match expected types
3. **Maintainability:** If SDK models change, tests break at parse time, not assertion time
4. **Clarity:** Clear what data structure is expected from each command
5. **Script-Friendly:** CLI output is now machine-readable JSON
6. **Single Source of Truth:** SDK models are the canonical schema
