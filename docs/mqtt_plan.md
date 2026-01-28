# MQTT Integration Tests Implementation Plan

## Overview

Implement missing MQTT Wait Tests in `test/integration/compute_workflow_test.dart` by creating a production-ready `MqttService` class that can be used by clients for real-time job monitoring via MQTT broker.

## User Requirements

- **MQTT Broker**: localhost:1883 (Mosquitto, no authentication)
- **Topic**: "inference/events" (single topic, job_id in message payload)
- **Message Format**:
  ```json
  {
    "event_type": "processing",
    "job_id": "job-abc-123",
    "data": {
      "progress": 50.0
    },
    "timestamp": 1702123456789
  }
  ```
  **Note**: No output or error in MQTT messages - only event_type, job_id, progress, timestamp
- **Test Scope**: Run only the MQTT test group, not the full test suite
- **Implementation Scope**: Full production MqttService class (not test-only helpers)
- **Legacy Handling**: Deprecate existing `waitForJobCompletionWithMQTT` method

## Key Design Decisions

### 1. MqttService Architecture (Simplified)

Create a lightweight MQTT service that:
- Manages MQTT broker connection lifecycle
- Subscribes to job update topic
- Parses MQTT messages and converts to **JobStatus** objects (NOT full Job)
- Maintains **JobStatus cache** by jobId
- Provides Stream<JobStatus> for real-time status updates
- Provides `waitForCompletion()` method that returns only jobId when finished
- **Does NOT** fetch or manage full Job objects

### 2. JobStatus Model (NEW)

Create lightweight status model:
```dart
class JobStatus {
  final String jobId;
  final String status;        // 'queued', 'processing', 'completed', 'failed'
  final int progress;         // 0-100
  final int timestamp;        // Unix timestamp from MQTT message
  bool get isFinished => status == 'completed' || status == 'failed';
}
```

**MQTT Message → JobStatus Mapping**:
- `event_type` → `status`
- `job_id` → `jobId`
- `data.progress` → `progress`
- `timestamp` → `timestamp`

**No output or error fields** - clients must call `ComputeService.getJob()` to get full Job with output/error

### 3. Client Workflow

1. Create MqttService and connect
2. Create job via ComputeService
3. Wait for completion: `await mqttService.waitForCompletion(jobId)`
4. Fetch full result: `final job = await computeService.getJob(jobId)`
5. Access output: `job.taskOutput`, error: `job.errorMessage`

## Implementation Steps

### Step 1: Create JobStatus Model

**File**: `lib/src/core/models/compute_models.dart` (MODIFY - add after Job class)

```dart
/// Lightweight job status from MQTT updates
@immutable
class JobStatus {
  const JobStatus({
    required this.jobId,
    required this.status,
    required this.progress,
    required this.timestamp,
  });

  factory JobStatus.fromMqttMessage(Map<String, dynamic> json) {
    return JobStatus(
      jobId: json['job_id'] as String,
      status: json['event_type'] as String,
      progress: (json['data']?['progress'] as num?)?.toInt() ?? 0,
      timestamp: json['timestamp'] as int,
    );
  }

  final String jobId;
  final String status;
  final int progress;
  final int timestamp;

  bool get isFinished => status == 'completed' || status == 'failed';

  JobStatus copyWith({
    String? jobId,
    String? status,
    int? progress,
    int? timestamp,
  }) {
    return JobStatus(
      jobId: jobId ?? this.jobId,
      status: status ?? this.status,
      progress: progress ?? this.progress,
      timestamp: timestamp ?? this.timestamp,
    );
  }
}
```

### Step 2: Create MqttService Class

**File**: `lib/src/services/mqtt_service.dart` (NEW, ~250 lines)

**Core Components**:

```dart
class MqttService {
  // Constructor - NO ComputeService dependency
  MqttService({
    required this.brokerUrl,      // 'localhost'
    required this.brokerPort,     // 1883
    required this.topic,          // 'inference/events'
  });

  // State
  MqttServerClient? _client;
  StreamController<JobStatus>? _statusStreamController;
  Map<String, JobStatus> _statusCache = {};  // Cache JobStatus, not Job
  bool _isConnected = false;

  // Public API
  Future<void> connect();
  Future<void> disconnect();
  Future<String> waitForCompletion({  // Returns jobId, not Job
    required String jobId,
    Duration timeout = const Duration(minutes: 5),
  });
  Stream<JobStatus> get statusStream;
  JobStatus? getStatus(String jobId);  // Query cache

  // Private helpers
  void _handleMessage(List<MqttReceivedMessage<MqttMessage>> messages);
  JobStatus? _parseMessageToStatus(String payload);
}
```

**Critical Implementation Details**:

1. **Connection Setup**:
   - Use `MqttServerClient` from mqtt_client package
   - Auto-generate client ID: `'dart_mqtt_${timestamp}'`
   - Subscribe to topic with QoS 1 (at least once)
   - Setup message handler on `client.updates` stream

2. **Message Parsing**:
   ```dart
   JobStatus? _parseMessageToStatus(String payload) {
     try {
       final json = jsonDecode(payload);
       final status = JobStatus.fromMqttMessage(json);

       // Update cache
       _statusCache[status.jobId] = status;

       return status;
     } catch (e) {
       // Log error, return null
       return null;
     }
   }
   ```

3. **Wait for Completion**:
   ```dart
   Future<String> waitForCompletion({
     required String jobId,
     Duration timeout = const Duration(minutes: 5),
   }) async {
     final completer = Completer<String>();
     late StreamSubscription<JobStatus> subscription;

     subscription = statusStream.listen(
       (status) {
         if (status.jobId == jobId && status.isFinished) {
           completer.complete(jobId);  // Just return jobId
           subscription.cancel();
         }
       },
       onError: completer.completeError,
     );

     return completer.future.timeout(
       timeout,
       onTimeout: () {
         subscription.cancel();
         throw TimeoutException('Timeout waiting for job: $jobId', timeout);
       },
     );
   }
   ```

4. **Query Cache**:
   ```dart
   JobStatus? getStatus(String jobId) => _statusCache[jobId];
   ```

**Exception Classes** (add to `lib/src/core/exceptions.dart`):
```dart
class MqttConnectionException implements Exception {
  MqttConnectionException(this.message);
  final String message;
  @override
  String toString() => 'MqttConnectionException: $message';
}
```

### Step 3: Update Library Exports

**File**: `lib/cl_server_dart_client.dart` (MODIFY)

Update line 44 to export JobStatus:
```dart
export 'src/core/models/compute_models.dart';  // Now includes JobStatus
```

Add export on line 50:
```dart
export 'src/services/mqtt_service.dart';
```

### Step 4: Deprecate Old Method

**File**: `lib/src/services/compute_service.dart` (MODIFY, line 141)

Add deprecation:
```dart
@Deprecated('Use MqttService directly. It provides JobStatus stream, not Job stream.')
Future<Job> waitForJobCompletionWithMQTT({
  required String jobId,
  required Stream<Job> jobUpdateStream,
  Duration timeout = const Duration(minutes: 5),
}) async {
  // Keep implementation for backward compatibility
  ...
}
```

### Step 5: Add MQTT Broker Health Check

**File**: `test/integration/health_check_test.dart` (MODIFY)

Add helper function:
```dart
Future<bool> checkMqttBrokerHealth() async {
  try {
    final client = MqttServerClient(
      'localhost',
      'health_check_${DateTime.now().millisecondsSinceEpoch}',
    );
    client.port = 1883;
    client.logging(on: false);

    await client.connect();

    if (client.connectionStatus?.state == MqttConnectionState.connected) {
      client.disconnect();
      return true;
    }
    return false;
  } catch (e) {
    return false;
  }
}
```

### Step 6: Implement Integration Tests

**File**: `test/integration/compute_workflow_test.dart` (MODIFY, lines 820-834)

Replace placeholder with comprehensive test group:

**Test Structure**:
```dart
group('MQTT Integration Tests', () {
  late MqttService mqttService;

  setUp(() async {
    if (!await checkMqttBrokerHealth()) {
      markTestSkipped('MQTT broker not available at localhost:1883');
      return;
    }

    mqttService = MqttService(
      brokerUrl: 'localhost',
      brokerPort: 1883,
      topic: 'inference/events',
    );

    await mqttService.connect();
  });

  tearDown() async {
    if (mqttService.isConnected) {
      await mqttService.disconnect();
    }
  });

  // Tests listed below
});
```

**Test Cases** (7 tests):

1. **✅ Complete job workflow with MQTT updates**
   - Create image_resize job
   - Wait for completion: `await mqttService.waitForCompletion(jobId)`
   - Fetch full job: `final job = await computeService.getJob(jobId)`
   - Verify job.status, job.taskOutput

2. **✅ Track status transitions via MQTT**
   - Create job
   - Listen to statusStream and collect all status updates
   - Verify transitions: queued → processing → completed/failed
   - Print transition sequence

3. **✅ Handle multiple concurrent jobs**
   - Create 3 jobs simultaneously
   - Use Future.wait() to wait for all: `Future.wait([job1, job2, job3].map((id) => mqttService.waitForCompletion(jobId: id)))`
   - Verify each returns correct jobId

4. **❌ Timeout when job never completes**
   - Create job
   - Delete job immediately (so MQTT never sends completion)
   - Expect TimeoutException after 3 seconds

5. **✅ MQTT faster than polling**
   - Create two identical jobs
   - Measure MQTT completion time
   - Measure polling completion time (2s interval)
   - Print comparison and speedup factor
   - Assert MQTT is faster or within tolerance

6. **✅ Query status cache**
   - Create job and wait for some updates
   - Query cache: `final status = mqttService.getStatus(jobId)`
   - Verify status is not null and has correct jobId

7. **✅ Handle MQTT connection loss gracefully**
   - Disconnect and reconnect
   - Verify isConnected flag updates correctly

**Test Helpers**:
- Reuse existing: `generateTestImage()`, `createTestJob()`, `hasTaskType()`
- Add cleanup for created jobs and files in tearDownAll

**Key Pattern in Tests**:
```dart
// Create job
final response = await createTestJob(...);

// Wait for MQTT completion (returns jobId only)
final completedJobId = await mqttService.waitForCompletion(
  jobId: response.jobId,
  timeout: Duration(minutes: 2),
);

// Fetch full Job from API
final job = await computeService.getJob(completedJobId);

// Now access output/error
expect(job.taskOutput, isNotNull);
expect(job.errorMessage, isNull);
```

## Running the Tests

Execute only MQTT test group:
```bash
dart test test/integration/compute_workflow_test.dart --name "MQTT Integration Tests"
```

With verbose output:
```bash
dart test test/integration/compute_workflow_test.dart --name "MQTT Integration Tests" --reporter=expanded
```

**Prerequisites**:
1. MQTT broker (Mosquitto) running at localhost:1883
2. Auth service at http://localhost:8000
3. Store/Compute service at http://localhost:8001
4. At least one compute worker with image_resize capability
5. Admin credentials: username='admin', password='admin'

## Files to Create/Modify

### New Files
1. `lib/src/services/mqtt_service.dart` (~250 lines)

### Modified Files
1. `lib/src/core/models/compute_models.dart` (add JobStatus class after Job class)
2. `lib/cl_server_dart_client.dart` (line 50: add mqtt_service export)
3. `lib/src/services/compute_service.dart` (line 141: add @Deprecated)
4. `lib/src/core/exceptions.dart` (add MqttConnectionException)
5. `test/integration/health_check_test.dart` (add checkMqttBrokerHealth)
6. `test/integration/compute_workflow_test.dart` (lines 820-834: replace with ~200 lines of tests)

## Critical Dependencies

**Existing** (already in pubspec.yaml):
- `mqtt_client: ^10.0.0` - MQTT protocol implementation

**New Model**:
- `JobStatus` - Lightweight status tracking (jobId, status, progress, timestamp only)

## Success Criteria

1. All 7 MQTT integration tests pass
2. MqttService provides lightweight JobStatus (NOT full Job objects)
3. Tests run in isolation (only MQTT group)
4. Proper cleanup (no hanging connections)
5. Tests handle missing MQTT broker gracefully (skip, not fail)
6. Performance test shows MQTT is faster than polling
7. Concurrent jobs properly filtered by jobId
8. Old waitForJobCompletionWithMQTT marked deprecated
9. MqttService has NO dependency on ComputeService
10. Clients call computeService.getJob() to fetch full Job after MQTT completion

## Implementation Notes

- **MqttService is dumb**: Only tracks status, never fetches Job objects
- Use broadcast stream for statusStream (multiple listeners)
- Handle malformed JSON gracefully (log, don't crash)
- Cache all JobStatus updates (unlimited cache for session)
- Clean up StreamController and subscriptions properly
- All tests use existing test helpers for consistency
- Track created jobs and files for tearDownAll cleanup
- Tests demonstrate pattern: MQTT completion → API fetch → verify output
