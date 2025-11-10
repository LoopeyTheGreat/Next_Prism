# Phase 2 Development: Core Sync Engine

**Status**: In Progress  
**Started**: November 9, 2025

## Overview
Building the core synchronization engine that monitors Nextcloud folders for new photos, deduplicates, moves to PhotoPrism, and triggers appropriate scanning commands.

## Components to Build

### 1. File Monitoring System (`src/monitoring/`)
**File**: `file_watcher.py`
- Use watchdog library for filesystem events
- Monitor Nextcloud user photo directories
- Support custom folder monitoring
- Detect new files with photo extensions (jpg, jpeg, png, heic, raw, etc.)
- Implement debouncing to avoid duplicate triggers
- Queue detected files with metadata (source, timestamp, user)

**File**: `folder_manager.py`
- Discover Nextcloud users automatically
- Apply user inclusion/exclusion filters
- Manage list of monitored folders
- Handle folder additions/removals dynamically

### 2. Deduplication System (`src/sync_engine/`)
**File**: `deduplicator.py`
- Calculate file hashes (SHA256 for balance of speed/accuracy)
- Check for existing files in PhotoPrism import directory by:
  - Filename comparison
  - Hash comparison
  - Optional: EXIF metadata comparison
- Maintain hash cache for performance
- Return duplicate status with existing file path

### 3. File Move Logic (`src/sync_engine/`)
**File**: `file_mover.py`
- Verify source file exists and is readable
- Check destination has sufficient disk space
- Safe file move operation with verification
- Handle filename collisions (append timestamp)
- Support archive mode (move to archive folder instead of delete)
- Preserve directory structure in archive
- Transaction logging for each operation
- Rollback capability for failed moves

### 4. Docker Command Interface (`src/docker_interface/`)
**File**: `docker_executor.py`
- Abstract interface for Docker commands
- Auto-detect standard Docker vs. Swarm mode
- Execute commands via docker exec or SSH proxy
- Command implementations:
  - `occ files:scan --path=/user/files/Photos`
  - `occ memories:index`
  - `photoprism index`
  - `photoprism import`
- Parse command output for success/failure
- Implement retry logic with exponential backoff
- Command timeout handling
- Queue commands for sequential execution

**File**: `nextcloud_commands.py`
- Wrapper for Nextcloud occ commands
- User folder scanning
- Album folder scanning
- Memories indexing

**File**: `photoprism_commands.py`
- Wrapper for PhotoPrism CLI
- Import trigger with options (move/copy)
- Index trigger
- Status checking

### 5. Main Orchestrator (`src/core/`)
**File**: `orchestrator.py`
- Main service coordinator class
- Initialize all subsystems (monitoring, sync, Docker interface)
- Manage sync queue with priority
- Coordinate workflow:
  1. Receive file from monitor
  2. Check for duplicates
  3. Move file to PhotoPrism import
  4. Trigger PhotoPrism import/index
  5. Wait for completion
  6. Trigger Nextcloud scans
  7. Trigger Memories index
  8. Log results
- Track statistics (files synced, duplicates, errors)
- Provide status interface for web UI
- Graceful shutdown handling

**File**: `sync_queue.py`
- Thread-safe queue for pending files
- Priority handling (manual triggers > scheduled)
- Queue persistence (survive restarts)
- Queue inspection methods
- Clear queue functionality

### 6. Web UI Integration
**Update**: `src/web/routes.py`
- Import orchestrator instance
- Replace TODO stubs with real orchestrator method calls:
  - `/api/status` → orchestrator.get_status()
  - `/api/sync/trigger` → orchestrator.trigger_manual_sync()
  - `/api/sync/pause` → orchestrator.pause()
  - `/api/sync/resume` → orchestrator.resume()
  - `/api/queue` → orchestrator.get_queue()
  - `/api/logs` → read from log files
  - `/api/test/nextcloud` → docker_executor.test_nextcloud()
  - `/api/test/photoprism` → docker_executor.test_photoprism()

**Update**: `src/web/app.py`
- Create orchestrator singleton on startup
- Pass orchestrator to routes
- Start orchestrator background thread
- Stop orchestrator on shutdown

### 7. Scheduling System
**File**: `src/scheduler/task_scheduler.py`
- Integrate APScheduler with FastAPI
- Add periodic jobs for folder scanning
- Support cron expressions from config
- Per-folder schedule overrides
- Job persistence across restarts
- Start/stop/pause scheduling

## Development Order

1. ✅ **Phase 4 Complete**: Web UI with placeholder APIs
2. **Start here**: File monitoring system (basic watchdog implementation)
3. Build deduplication logic (hash calculation, comparison)
4. Implement file mover with archive support
5. Create Docker command interface (exec wrapper)
6. Build main orchestrator to coordinate everything
7. Connect orchestrator to web UI APIs
8. Add scheduling with APScheduler
9. Test end-to-end workflow
10. Add error handling and recovery

## Testing Strategy

### Unit Tests
- Test file hash calculation accuracy
- Test duplicate detection logic
- Test filename collision handling
- Test archive folder structure
- Test Docker command parsing

### Integration Tests
- Test complete sync workflow with mock containers
- Test error scenarios (disk full, permission denied)
- Test large file handling
- Test concurrent operations
- Test graceful shutdown

### Manual Testing
- Monitor real Nextcloud folder
- Upload test photos
- Verify deduplication works
- Check PhotoPrism import
- Verify Nextcloud scanning updates
- Test web UI controls

## Next Immediate Steps

1. Create `src/monitoring/file_watcher.py` with watchdog integration
2. Create `src/sync_engine/deduplicator.py` for hash-based deduplication
3. Create `src/sync_engine/file_mover.py` for safe file operations
4. Create `src/docker_interface/docker_executor.py` for command execution
5. Create `src/core/orchestrator.py` to tie everything together
6. Update `src/web/routes.py` to use orchestrator methods
7. Test with real Nextcloud/PhotoPrism containers

---

**Goal**: By end of this phase, have a fully functional sync engine that can be controlled via the web UI, with automatic monitoring and manual trigger capabilities.
