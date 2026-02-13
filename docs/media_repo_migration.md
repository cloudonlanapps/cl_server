# Client Migration Map: Media Repo -> Services/Store

This document outlines the API changes required to migrate the `ui_flutter` client from the legacy `media_repo` to the new `services/store`.

## Endpoint Mappings

| Feature | Media Repo Endpoint | Services/Store Endpoint | Notes |
| :--- | :--- | :--- | :--- |
| **List Entities** | `GET /entities` | `GET /entities` | Supports new filters: `md5`, `mime_type`, `type`, `width`, `height`, `file_size_min/max`, `date_from/to`. |
| **Get Entity** | `GET /entities/{id}` | `GET /entities/{id}` | Response structure is largely compatible. |
| **Create Entity** | `POST /entities` | `POST /entities` | Uses `multipart/form-data`. `is_collection` is required. |
| **Update Entity** | `PUT /entities/{id}` | `PUT /entities/{id}` | Full update. Uses `multipart/form-data`. |
| **Patch Entity** | `PATCH /entities/{id}` | `PATCH /entities/{id}` | Partial update. Supports soft-delete (`is_deleted=True`). |
| **Delete Entity** | `DELETE /entities/{id}` | `DELETE /entities/{id}` | **Requires soft-delete first**. Use PATCH `is_deleted=True` before DELETE. |
| **Download Media** | `GET /download/{id}` | `GET /entities/{id}/media` | **New Path**. Returns original file. |
| **Download Preview**| `GET /preview/{id}` | `GET /entities/{id}/preview` | **New Path**. Returns generated preview. |
| **Stream HLS** | `GET /stream/{id}/adaptive.m3u8` | `GET /entities/{id}/stream/adaptive.m3u8` | **New Path**. Helper methods added to SDKs. |

## Data Model Changes

### Entity Fields
Most fields remain the same, but observe the following:
- **`is_deleted`**: Explicitly used for soft deletion.
- **`intelligence_data`**: New field containing AI analysis results (faces, objects).
- **`mime_type`**: Now consistently returned.

## Client-Side Logic Updates

1.  **Deletion Workflow**:
    - **Old**: Single DELETE call might have handled everything.
    - **New**: MUST call `PATCH /entities/{id}` with `is_deleted=True` (Soft Delete) -> visual feedback -> then `DELETE /entities/{id}` (Hard Delete) if user confirms permanent removal. UI should reflect soft-deleted state.

2.  **Streaming**:
    - Update the video player to use the new HLS URL format: `/entities/{id}/stream/adaptive.m3u8`.
    - Ensure authentication tokens are passed if required (cookies or query params).

3.  **Filtering**:
    - Use specific filter parameters (`mime_type='video/mp4'`) instead of generic searches where possible for better performance.

## SDK Updates
Both `pysdk` (Python) and `dartsdk` (Dart) have been updated to support these changes.
- **Python**: `StoreClient.download_media`, `StoreClient.get_stream_url`
- **Dart**: `StoreClient.downloadMedia`, `StoreClient.getStreamUrl`
