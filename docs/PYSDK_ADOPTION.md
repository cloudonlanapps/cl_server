# DartSDK Features for Python SDK Adoption

This document describes unique features in the Dart SDK that don't exist in the Python SDK. These features should be considered for future pysdk implementation to improve developer experience and code maintainability.

## Overview

The Dart SDK includes several architectural patterns and high-level modules that are not yet present in the Python SDK:

1. **UserManager Module** - High-level user management API
2. **StoreManager Module** - High-level store entity management API
3. **Command Pattern Architecture** - Clean separation of concerns for complex operations
4. **User Prefixing System** - Automatic prefixing for utility-created users
5. **Result Wrapper Pattern** - Consistent error handling across operations

These features have proven valuable in the Dart SDK and could be adapted to Python to improve the developer experience.

---

## 1. UserManager Module

### Location
- `lib/src/user_manager/user_manager.dart`
- `lib/src/user_manager/commands/` (8 command classes)
- `lib/src/user_manager/models/result_model.dart`
- `lib/src/user_manager/utils/user_prefix_utils.dart`

### Purpose

UserManager provides a high-level, user-friendly API for managing users in the CL Server system. It abstracts away the complexity of direct AuthService calls and provides:

- Automatic user prefixing (see section 4)
- Consistent error handling via Result wrapper
- Command pattern architecture for maintainability
- Both authenticated modes via SessionManager

### API

```dart
// Initialize with authenticated session
final sessionManager = await SessionManager.initialize();
await sessionManager.login('admin', 'password');
final manager = await UserManager.authenticated(
  sessionManager: sessionManager,
  prefix: 't#',  // Optional, default: 't#'
);

// Create user
final result = await manager.createUser(
  username: 'alice',      // Will be stored as 't#alice' internally
  password: 'pass123',
  isAdmin: false,
  permissions: ['read:entities'],
);

if (result.isSuccess) {
  print('Created user: ${result.data}');
} else {
  print('Error: ${result.error}');
}

// List users
final listResult = await manager.listUsers(
  options: UserListOptions(skip: 0, limit: 10),
);

// Get single user
final userResult = await manager.getUser(userId: 123);

// Update user
final updateResult = await manager.updateUser(
  userId: 123,
  password: 'newpass',
  isAdmin: true,
  permissions: ['read:entities', 'write:entities'],
);

// Delete user
final deleteResult = await manager.deleteUser(userId: 123);

// Get user permissions
final permsResult = await manager.getUserPermissions(userId: 123);

// Store config operations
final configResult = await manager.getStoreConfig();
final authResult = await manager.updateReadAuth(enabled: true);
```

### Available Operations

All operations return `UserOperationResult<T>`:

1. **createUser()** - Create new user with automatic prefixing
2. **getUser()** - Retrieve user by ID
3. **listUsers()** - List users with filtering/pagination
4. **updateUser()** - Update user (partial updates allowed)
5. **deleteUser()** - Delete user by ID
6. **getUserPermissions()** - Get permissions for user
7. **getStoreConfig()** - Get store configuration
8. **updateReadAuth()** - Update store read authentication

### Benefits

- **Simpler API**: Developers don't need to know about AuthService internals
- **Automatic Prefixing**: Prevents namespace conflicts (see section 4)
- **Error Handling**: Consistent Result wrapper pattern
- **Type Safety**: Generic `UserOperationResult<T>` provides type safety
- **Testability**: Command pattern makes testing easier

---

## 2. StoreManager Module

### Location
- `lib/src/store_manager/store_manager.dart`
- `lib/src/store_manager/commands/` (6 command classes)
- `lib/src/store_manager/models/result_model.dart`

### Purpose

StoreManager provides a high-level API for managing store entities, similar to UserManager but for the store service. It supports both guest (unauthenticated) and authenticated modes.

### API

```dart
// Guest mode (no authentication)
final manager = StoreManager.guest('http://localhost:8001');

// Or authenticated mode
final sessionManager = await SessionManager.initialize();
await sessionManager.login('user', 'password');
final manager = await StoreManager.authenticated(
  sessionManager: sessionManager,
);

// List entities
final result = await manager.listEntities(
  page: 1,
  pageSize: 20,
  searchQuery: 'photos',
);

// Create entity
final createResult = await manager.createEntity(
  label: 'My Photos',
  description: 'Personal photo collection',
  isCollection: true,
);

// Read entity
final readResult = await manager.readEntity(entityId: 123);

// Update entity (full update)
final updateResult = await manager.updateEntity(
  entityId: 123,
  label: 'Updated Label',
  isCollection: false,
);

// Patch entity (partial update)
final patchResult = await manager.patchEntity(
  entityId: 123,
  description: 'New description',
);

// Delete entity
final deleteResult = await manager.deleteEntity(entityId: 123);
```

### Available Operations

All operations return `StoreOperationResult<T>`:

1. **listEntities()** - List entities with pagination/search
2. **createEntity()** - Create new entity
3. **readEntity()** - Read single entity by ID
4. **updateEntity()** - Full update (requires label + isCollection)
5. **patchEntity()** - Partial update (any field)
6. **deleteEntity()** - Delete entity by ID

### Benefits

- **Dual Mode**: Guest and authenticated modes for different use cases
- **Clean API**: Abstracts StoreService complexity
- **Consistent Errors**: Result wrapper pattern
- **Parent Resolution**: Can resolve parent collections by label or ID

---

## 3. Command Pattern Architecture

### Used In
- UserManager (8 command classes)
- StoreManager (6 command classes)

### Pattern Structure

Each operation is implemented as a separate command class:

```dart
// Example: CreateUserCommand
class CreateUserCommand {
  CreateUserCommand(this._authService, this._prefix);

  final AuthService _authService;
  final String _prefix;

  Future<UserOperationResult<dynamic>> execute({
    required String username,
    required String password,
    bool isAdmin = false,
    List<String>? permissions,
  }) async {
    try {
      // Add prefix to username
      final prefixedUsername = UserPrefixUtils.addPrefix(username, _prefix);

      final user = await _authService.createUser(
        username: prefixedUsername,
        password: password,
        isAdmin: isAdmin,
        permissions: permissions ?? [],
      );

      return UserOperationResult(
        success: 'User created successfully',
        data: user,
      );
    } on PermissionException catch (e) {
      return UserOperationResult(
        error: 'Permission denied: ${e.message}',
      );
    } on ValidationException catch (e) {
      return UserOperationResult(
        error: 'Validation failed: ${e.message}',
      );
    } on CLServerException catch (e) {
      return UserOperationResult(
        error: 'Server error: ${e.message}',
      );
    } on Exception catch (e) {
      return UserOperationResult(
        error: 'Failed to create user: $e',
      );
    }
  }
}
```

### Manager Delegates to Commands

```dart
class UserManager {
  Future<UserOperationResult<dynamic>> createUser({
    required String username,
    required String password,
    bool isAdmin = false,
    List<String>? permissions,
  }) => CreateUserCommand(_authService, _prefix).execute(
        username: username,
        password: password,
        isAdmin: isAdmin,
        permissions: permissions,
      );
}
```

### Benefits

1. **Separation of Concerns**: Each operation is isolated
2. **Testability**: Easy to test individual commands in isolation
3. **Maintainability**: Changes to one operation don't affect others
4. **Consistent Error Handling**: All exceptions caught and wrapped
5. **Single Responsibility**: Each command class has one job
6. **Easy to Extend**: New operations = new command class

### Why This Matters for pysdk

The pysdk currently has monolithic service classes. The command pattern would:
- Make code more modular and maintainable
- Improve testability (mock individual commands)
- Provide consistent error handling across all operations
- Make it easier to add new operations without bloating service classes

---

## 4. User Prefixing System

### Location
`lib/src/user_manager/utils/user_prefix_utils.dart`

### Purpose

Automatically prefix usernames created by utilities to distinguish them from:
- System users (admin, service accounts)
- Manually created users
- Users from different utilities/tools

### How It Works

```dart
// When creating a user via UserManager
final manager = await UserManager.authenticated(
  sessionManager: sessionManager,
  prefix: 't#',  // Prefix for this utility
);

// User provides unprefixed name
await manager.createUser(
  username: 'alice',  // Developer writes 'alice'
  password: 'pass123',
);

// Internally stored as 't#alice' in the system
// When listing users, the prefix is handled transparently
```

### Utility Functions

```dart
class UserPrefixUtils {
  // Common prefixes used by different tools
  static const List<String> commonPrefixes = ['t#', 'test_', 'cli_', 'util_'];

  // Add prefix to username
  static String addPrefix(String username, String prefix);
  // Example: addPrefix('alice', 't#') → 't#alice'

  // Remove any common prefix from username
  static String removePrefix(String username);
  // Example: removePrefix('t#alice') → 'alice'
  // Example: removePrefix('alice') → 'alice' (unchanged)

  // Check if user was created by a utility
  static bool isUtilityCreatedUser(String username, String prefix);
  // Returns true if username has current or any common prefix

  // Check if username has any known prefix
  static bool hasAnyPrefix(String username);

  // Extract the prefix from a username
  static String extractPrefix(String username);
  // Example: extractPrefix('t#alice') → 't#'
  // Example: extractPrefix('alice') → ''
}
```

### Use Cases

1. **Testing Tools**: Prefix test users with `test_` to easily identify and clean up
2. **CLI Tools**: Prefix with `cli_` to distinguish from web UI users
3. **Automation**: Prefix with `util_` or custom prefix per utility
4. **Multi-tenancy**: Different tools can have different prefixes

### Benefits

- **Namespace Management**: Prevents name collisions between tools
- **Easy Cleanup**: Identify and delete all users from a specific tool
- **Audit Trail**: Know which tool created which users
- **Transparent**: Hidden from end-user API (they just use 'alice')

### Example: Cleanup

```dart
// List all users created by this utility
final result = await manager.listUsers();
final users = result.data['users'];

for (final user in users) {
  if (UserPrefixUtils.isUtilityCreatedUser(user['username'], 't#')) {
    await manager.deleteUser(userId: user['id']);
  }
}
```

---

## 5. Result Wrapper Pattern

### Location
- `lib/src/user_manager/models/result_model.dart` (UserOperationResult)
- `lib/src/store_manager/models/result_model.dart` (StoreOperationResult)

### Purpose

Provide consistent, type-safe error handling across all manager operations without throwing exceptions.

### Implementation

```dart
class UserOperationResult<T> {
  UserOperationResult({
    this.success,
    this.error,
    this.data,
  });

  final String? success;  // Success message
  final String? error;    // Error message
  final T? data;          // Result data (generic type)

  bool get isSuccess => success != null && error == null;
  bool get isError => error != null;

  // Get value or throw exception
  T get valueOrThrow {
    if (isError) {
      throw UserOperationException(error ?? 'Unknown error');
    }
    return data as T;
  }
}
```

### Usage Patterns

**Pattern 1: Check and handle**
```dart
final result = await manager.createUser(
  username: 'alice',
  password: 'pass123',
);

if (result.isSuccess) {
  print('Created: ${result.data}');
} else {
  print('Error: ${result.error}');
}
```

**Pattern 2: Use valueOrThrow**
```dart
try {
  final user = await manager.createUser(
    username: 'alice',
    password: 'pass123',
  ).then((r) => r.valueOrThrow);

  print('Created: $user');
} on UserOperationException catch (e) {
  print('Error: $e');
}
```

**Pattern 3: Functional chaining**
```dart
final result = await manager.getUser(userId: 123);
final userName = result.isSuccess
  ? result.data['username']
  : 'unknown';
```

### Benefits

1. **No Silent Failures**: Operations never fail silently
2. **Explicit Error Handling**: Forces developers to handle errors
3. **Type Safety**: Generic `Result<T>` provides compile-time safety
4. **Flexible**: Choose between check-then-use or throw patterns
5. **Consistent**: All manager operations use same error pattern
6. **Informative**: Success/error messages explain what happened

### Why This Matters for pysdk

The pysdk currently raises exceptions directly, which can lead to:
- Uncaught exceptions crashing programs
- Inconsistent error handling across operations
- Less explicit error flows in code

The Result pattern provides:
- More Pythonic approach (similar to `Optional[T]` or `Union[Success, Error]`)
- Better composability (can chain operations with error checks)
- Explicit success/failure states

---

## Recommendations for pysdk

Based on the success of these patterns in dartsdk, we recommend implementing them in pysdk:

### Priority 1: UserManager Module

**Why**: High developer value, relatively simple to implement

**What to include**:
- `UserManager` class with authenticated mode
- All 8 user operations (create, get, list, update, delete, permissions, store config)
- Result wrapper pattern for consistent errors
- Command pattern for maintainability

**Suggested Python structure**:
```python
# cl_client/user_manager/user_manager.py
class UserManager:
    @classmethod
    async def authenticated(cls, session_manager, prefix='t#'):
        # Create from authenticated session
        pass

    async def create_user(self, username: str, password: str,
                         is_admin: bool = False,
                         permissions: Optional[List[str]] = None) -> UserOperationResult:
        return await CreateUserCommand(self._auth_service, self._prefix).execute(
            username=username,
            password=password,
            is_admin=is_admin,
            permissions=permissions,
        )
```

### Priority 2: User Prefixing System

**Why**: Prevents namespace conflicts, useful for testing tools

**What to include**:
- `user_prefix_utils.py` module
- Common prefixes list
- Add/remove/check prefix functions
- Integrate with UserManager

**Suggested Python structure**:
```python
# cl_client/user_manager/utils/user_prefix_utils.py
class UserPrefixUtils:
    COMMON_PREFIXES = ['t#', 'test_', 'cli_', 'util_']

    @staticmethod
    def add_prefix(username: str, prefix: str) -> str:
        return f"{prefix}{username}"

    @staticmethod
    def remove_prefix(username: str) -> str:
        for prefix in UserPrefixUtils.COMMON_PREFIXES:
            if username.startswith(prefix):
                return username[len(prefix):]
        return username
```

### Priority 3: Result Wrapper Pattern

**Why**: Improves error handling consistency

**What to include**:
- `UserOperationResult` class (or generic `Result[T]`)
- `is_success`, `is_error` properties
- `value_or_raise` method (Python equivalent of `valueOrThrow`)

**Suggested Python structure**:
```python
# cl_client/user_manager/models/result_model.py
from typing import Generic, TypeVar, Optional

T = TypeVar('T')

class UserOperationResult(Generic[T]):
    def __init__(self, success: Optional[str] = None,
                 error: Optional[str] = None,
                 data: Optional[T] = None):
        self.success = success
        self.error = error
        self.data = data

    @property
    def is_success(self) -> bool:
        return self.success is not None and self.error is None

    @property
    def is_error(self) -> bool:
        return self.error is not None

    def value_or_raise(self) -> T:
        if self.is_error:
            raise UserOperationException(self.error or 'Unknown error')
        return self.data
```

### Priority 4: Command Pattern Architecture

**Why**: Improves maintainability and testability

**What to include**:
- Command base class
- Individual command classes for each operation
- Manager delegates to commands

**Suggested Python structure**:
```python
# cl_client/user_manager/commands/create_user.py
class CreateUserCommand:
    def __init__(self, auth_service, prefix):
        self._auth_service = auth_service
        self._prefix = prefix

    async def execute(self, username: str, password: str,
                     is_admin: bool = False,
                     permissions: Optional[List[str]] = None) -> UserOperationResult:
        try:
            prefixed_username = UserPrefixUtils.add_prefix(username, self._prefix)
            user = await self._auth_service.create_user(
                username=prefixed_username,
                password=password,
                is_admin=is_admin,
                permissions=permissions or [],
            )
            return UserOperationResult(
                success='User created successfully',
                data=user,
            )
        except PermissionException as e:
            return UserOperationResult(error=f'Permission denied: {e}')
        except ValidationException as e:
            return UserOperationResult(error=f'Validation failed: {e}')
        except Exception as e:
            return UserOperationResult(error=f'Failed to create user: {e}')
```

### Priority 5: StoreManager Module

**Why**: Completes the high-level API suite

**What to include**:
- Same patterns as UserManager but for store operations
- Guest and authenticated modes
- Result wrapper pattern
- Command pattern

---

## Implementation Timeline Suggestion

Based on dartsdk's implementation experience:

1. **Week 1-2**: Result wrapper pattern + User prefixing utils
   - Small, foundational pieces
   - No dependencies on other features
   - Can be tested independently

2. **Week 3-4**: Command pattern infrastructure + First 2-3 UserManager commands
   - Create command base class
   - Implement CreateUserCommand, GetUserCommand, ListUsersCommand
   - Establish patterns for others to follow

3. **Week 5**: Complete UserManager (remaining 5 commands)
   - Update, Delete, Permissions, Store config operations
   - Full test coverage

4. **Week 6**: StoreManager (if desired)
   - Apply same patterns to store operations
   - Reuse Result wrapper and command pattern

5. **Week 7**: Documentation and examples
   - Update pysdk README
   - Add examples to docs
   - Migration guide for existing code

**Total estimate**: 5-7 weeks for full UserManager + StoreManager

---

## Testing Strategy

The command pattern makes testing much easier:

```python
# Test individual command in isolation
async def test_create_user_command():
    mock_auth_service = MagicMock()
    mock_auth_service.create_user.return_value = {'id': 1, 'username': 't#alice'}

    command = CreateUserCommand(mock_auth_service, prefix='t#')
    result = await command.execute(
        username='alice',
        password='pass123',
        is_admin=False,
    )

    assert result.is_success
    assert result.data['username'] == 't#alice'
    mock_auth_service.create_user.assert_called_once_with(
        username='t#alice',
        password='pass123',
        is_admin=False,
        permissions=[],
    )
```

---

## Backward Compatibility

These new features should NOT break existing pysdk code:

- UserManager is a **new module** (no existing code to break)
- Existing `AuthService` and `StoreService` remain unchanged
- UserManager wraps existing services, doesn't replace them
- Developers can choose to adopt UserManager or continue using services directly

**Migration path**:
```python
# Old way (still works)
auth_service = AuthService(base_url)
user = await auth_service.create_user(
    username='alice',
    password='pass123',
)

# New way (recommended)
manager = await UserManager.authenticated(session_manager=session)
result = await manager.create_user(
    username='alice',  # Auto-prefixed
    password='pass123',
)
if result.is_success:
    user = result.data
```

---

## Summary

The Dart SDK has successfully implemented several high-level features that improve developer experience:

1. **UserManager**: High-level user management API with automatic prefixing
2. **StoreManager**: High-level store entity management API
3. **Command Pattern**: Clean, maintainable, testable architecture
4. **User Prefixing**: Namespace management for utilities
5. **Result Wrapper**: Consistent, type-safe error handling

These patterns have proven valuable in dartsdk and should be considered for pysdk adoption to:
- Improve developer experience
- Increase code maintainability
- Provide consistent error handling
- Support testing and automation tools

The implementation is straightforward, backward compatible, and provides immediate value to developers building on the CL Server platform.

---

## 6. Test Infrastructure Parity

### Overview

As of this update, the Dart SDK test infrastructure has been fully aligned with the Python SDK's pytest-based testing system, with some architectural differences due to language-specific patterns.

### Test Infrastructure Comparison

| Feature | Python SDK | Dart SDK | Status |
|---------|-----------|----------|--------|
| Auth mode parametrization | `pytest --auth-mode=admin` | `TEST_AUTH_MODE=admin dart test` | ✅ Equivalent |
| Server config matrix testing | Shell script (4 configs) | Shell script (4 configs) | ✅ Aligned |
| Test user management | Automatic setup | Automatic setup | ✅ Aligned |
| Decision functions | `should_succeed()` | `shouldSucceed()` | ✅ Aligned |
| Individual plugin tests | 9 separate files | 9 separate files | ✅ Aligned |
| Store integration tests | 12 tests | 8 tests | ⚠️ Partial (see Gaps) |
| User management tests | 7 tests | 8 tests | ✅ Aligned |
| Auth error tests | 5 tests | Not implemented | ❌ Gap |

### Test Files Structure

**Python SDK:**
```
tests/test_integration/
  ├── test_store_integration.py
  ├── test_user_management_integration.py
  ├── test_auth_errors_integration.py
  ├── test_clip_embedding_integration.py
  ├── test_dino_embedding_integration.py
  ├── test_exif_integration.py
  ├── test_face_detection_integration.py
  ├── test_face_embedding_integration.py
  ├── test_hash_integration.py
  ├── test_hls_streaming_integration.py
  ├── test_image_conversion_integration.py
  └── test_media_thumbnail_integration.py
```

**Dart SDK:**
```
test/integration/
  ├── store_integration_test.dart
  ├── user_management_integration_test.dart
  ├── clip_embedding_integration_test.dart
  ├── dino_embedding_integration_test.dart
  ├── exif_integration_test.dart
  ├── face_detection_integration_test.dart
  ├── face_embedding_integration_test.dart
  ├── hash_integration_test.dart
  ├── hls_streaming_integration_test.dart
  ├── image_conversion_integration_test.dart
  └── media_thumbnail_integration_test.dart
```

### Critical API Differences

#### Compute Plugin Submission

**Python SDK: Generic submission**
```python
# Python uses generic submit_job with task_input dict
job = await client.submit_job(
    task_type='clip_embedding',
    task_input={'image_path': '../pysdk/tests/media/images/test.jpg'},
    wait=True
)
```

**Dart SDK: Typed plugin clients**
```dart
// Dart uses typed plugin clients with specific methods
final job = await client.clipEmbedding.embedImage(
  image: File('../pysdk/tests/media/images/test.jpg'),
  wait: true,
);
```

This is an **intentional architectural difference**:
- **Python**: Favors flexibility with generic `task_input` dicts
- **Dart**: Favors type safety with specific plugin methods

Each approach has benefits:
- Python: Easier to add new plugins without SDK changes
- Dart: Compile-time type safety, better IDE support, clearer API

#### Plugin-Specific APIs

| Plugin | Python API | Dart API |
|--------|-----------|----------|
| CLIP | `submit_job('clip_embedding', {'image_path': path})` | `clipEmbedding.embedImage(image: File(path))` |
| DINO | `submit_job('dino_embedding', {'image_path': path})` | `dinoEmbedding.embedImage(image: File(path))` |
| EXIF | `submit_job('exif', {'image_path': path})` | `exif.extract(image: File(path))` |
| Face Detection | `submit_job('face_detection', {'image_path': path})` | `faceDetection.detect(image: File(path))` |
| Face Embedding | `submit_job('face_embedding', {'image_path': path})` | `faceEmbedding.embedFaces(image: File(path))` |
| Hash | `submit_job('hash', {'image_path': path})` | `hash.compute(image: File(path))` |
| HLS | `submit_job('hls_streaming', {'video_path': path})` | `hlsStreaming.generateManifest(video: File(path))` |
| Image Conversion | `submit_job('image_conversion', {'image_path': path, 'target_format': 'webp', 'quality': 85})` | `imageConversion.convert(image: File(path), outputFormat: 'webp', quality: 85)` |
| Thumbnail | `submit_job('media_thumbnail', {'image_path': path, 'width': 300, 'height': 200})` | `mediaThumbnail.generate(media: File(path), width: 300, height: 200)` |

### Dart SDK Test Infrastructure Features

**Configuration System:**
- `test/config/test_config.json` - Centralized test configuration
- `test/test_config_loader.dart` - Config loader with environment overrides
- `test/server_capabilities.dart` - Auto-detects server auth/guest mode
- `test/auth_test_context.dart` - Auth mode enumeration and context
- `test/decision_functions.dart` - Operation authorization logic
- `test/test_user_setup.dart` - Automatic test user creation/validation
- `test/test_helpers.dart` - Auth-aware client factories
- `run_all_tests.sh` - Shell script orchestrating 16-scenario matrix (4 server configs × 4 auth modes)

**Test Pattern:**
```dart
testWithAuthMode('Test description matching Python',
    (AuthTestContext context) async {
  final client = await createTestComputeClient(context);

  if (shouldSucceed(context, OperationType.plugin)) {
    // Operation should succeed
    final job = await client.pluginName.method(...);
    expect(job.status, equals('completed'));
    await client.deleteJob(job.jobId);
  } else {
    // Operation should fail with auth error
    try {
      await client.pluginName.method(...);
      fail('Expected error but operation succeeded');
    } catch (e) {
      expect(e, isNotNull);
    }
  }
});
```

### Dart-Specific Superior Tests

The following tests exist in Dart SDK but not in Python SDK and should be considered for adoption:

#### 1. Comprehensive MQTT Integration Tests
**Location:** `test/integration/compute_workflow_test.dart`

**Tests:**
- MQTT status stream subscriptions
- Concurrent job monitoring via MQTT
- Timeout handling with MQTT
- Performance comparison: HTTP polling vs MQTT

**Why valuable:**
- Validates MQTT as the primary workflow
- Tests real-time job status updates
- Ensures concurrent job monitoring works correctly

**Recommendation:** Port to Python SDK

#### 2. Session State Management Tests
**Location:** `test/unit/session/` (7 test files)

**Tests:**
- Token storage and persistence
- JWT parsing and validation
- Session lifecycle (login, logout, refresh)
- Token expiration handling
- Concurrent session management

**Why valuable:**
- Validates session state machine
- Ensures secure token handling
- Tests edge cases in authentication flow

**Recommendation:** Consider for Python SDK if session architecture is added

#### 3. Health Check Utilities
**Location:** `test/integration/health_check_test.dart`

**Functions:**
- Service availability checking (auth, compute, store, MQTT)
- Pre-test validation
- Skip tests if services unavailable

**Why valuable:**
- Prevents cryptic test failures when services are down
- Clear error messages for developers
- Faster test suite execution (fail fast)

**Recommendation:** Port to Python SDK

#### 4. Storage Management Tests
**Location:** Part of `test/integration/compute_workflow_test.dart`

**Tests:**
- `getStorageSize()` - Check job storage usage
- `cleanupOldJobs()` - Admin cleanup functionality
- Storage quotas and limits

**Why valuable:**
- Tests admin-only storage management features
- Validates cleanup workflows
- Ensures storage APIs work correctly

**Recommendation:** Consider for Python SDK

### Feature Gaps (Dart Missing from Python)

Based on comparison with Python SDK tests, Dart SDK is missing:

#### 1. Auth Errors Integration Tests
**Python file:** `test_auth_errors_integration.py`

**Missing tests:**
- Unauthenticated request rejection (401)
- Invalid token rejection (401)
- Malformed token rejection (401)
- Non-admin user forbidden from admin endpoint (403)
- Valid auth operations succeed

**Recommendation:** Create `test/integration/auth_errors_integration_test.dart`

#### 2. Store Integration Test Gaps
**Missing from Dart:**
- File upload with entity creation
- Entity version history retrieval
- Admin get/set read auth config

**Reason:** These features may not be fully implemented in StoreManager yet

**Recommendation:** Add to Dart SDK once StoreManager supports these features

### Test Parity Status Summary

✅ **Fully Aligned:**
- Plugin integration tests (9 files)
- User management integration tests
- Auth mode parametrization
- Server configuration matrix testing
- Decision function logic

⚠️ **Partially Aligned:**
- Store integration tests (missing file upload, version history, admin config)

❌ **Dart SDK Gaps:**
- Auth errors integration tests

✅ **Dart SDK Superior:**
- MQTT integration tests
- Session management tests
- Health check utilities
- Storage management tests

### Recommendations for Python SDK

1. **Add MQTT Integration Tests** - Dart's comprehensive MQTT tests should be ported
2. **Add Health Check Utilities** - Improve developer experience with better error messages
3. **Consider Session Tests** - If Python SDK adds session management, adopt Dart's test patterns
4. **Add Storage Management Tests** - Test admin storage cleanup features

### Recommendations for Dart SDK

1. **Add Auth Errors Tests** - Create `auth_errors_integration_test.dart` matching Python
2. **Complete Store Integration Tests** - Add file upload, version history, admin config tests once StoreManager supports them

---

## Questions or Feedback

For questions about these features or implementation details, refer to:
- Dart implementation: `sdks/dartsdk/lib/src/user_manager/`
- Example usage: `sdks/dartsdk/example/bin/user_manager.dart`
- Tests: `sdks/dartsdk/test/unit/user_manager/`
- Test infrastructure: `sdks/dartsdk/test/` (integration tests)

Or contact the dartsdk maintainers for guidance on adapting these patterns to Python.
