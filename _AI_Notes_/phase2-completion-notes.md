# Phase 2 Development Notes

## Completed: November 9, 2025

### File Monitoring System
- ✅ Created PhotoFileHandler with debouncing (2 second delay to ensure file stability)
- ✅ Implemented FolderWatcher to manage multiple monitored folders
- ✅ Recursive monitoring with watchdog library
- ✅ Event handling for file creation and modification
- ✅ Pending file queue with timestamp tracking

### Nextcloud User Detection
- ✅ NextcloudUserDetector scans data directory for users
- ✅ Include/exclude list filtering (whitelist/blacklist)
- ✅ Automatic detection of Photos directories
- ✅ Fallback for lowercase 'photos' folders
- ✅ Returns mapping of username to photos path

### Docker Command Interface
- ✅ DockerExecutor with direct exec support
- ✅ Automatic Swarm mode detection via Docker API
- ✅ CommandResult wrapper for execution details
- ✅ NextcloudCommands: files:scan, memories:index, status
- ✅ PhotoPrismCommands: index, import, status
- ✅ Retry logic and timeout handling
- ✅ Container existence checking

### Sync Engine
- ✅ Complete sync workflow coordination
- ✅ DeduplicationCache with SHA256 hash tracking
- ✅ In-memory cache of destination files for fast duplicate detection
- ✅ Safe file moving with hash verification
- ✅ Archive support for moved files
- ✅ Statistics tracking (files processed, moved, duplicates, errors, total size)
- ✅ Batch processing triggers for indexing
- ✅ Integration with Docker commands for Nextcloud and PhotoPrism

### Orchestrator
- ✅ Main coordination layer tying all components together
- ✅ File queue with FileQueueItem wrapper
- ✅ Multi-threaded architecture (watcher thread + processor thread)
- ✅ Batch processing (10 files or 30 second timeout)
- ✅ Automatic Nextcloud user detection and folder addition
- ✅ Retry logic for failed files (max 3 attempts)
- ✅ Graceful start/stop with thread management
- ✅ Status reporting endpoint

### Testing
- ✅ Unit tests for deduplication cache
- ✅ Unit tests for sync engine
- ✅ Tests for duplicate detection workflow
- ✅ Tests for error handling

## Architecture Highlights

### Threading Model
```
Main Thread
├── Watcher Thread (processes pending files every 1s)
└── Processor Thread (processes queue in batches)
```

### Workflow
```
1. File detected → PhotoFileHandler
2. Debounce (2s) → Stable file confirmed
3. Add to Queue → FileQueueItem
4. Batch Processing → SyncEngine.sync_file()
5. Dedupe Check → DeduplicationCache
6. Move File → PhotoPrism import folder
7. Batch Complete → Trigger indexing
8. PhotoPrism Import → Organize to albums
9. Nextcloud Scan → Update file index
10. Memories Index → Update gallery
```

### Key Design Decisions

**Deduplication Strategy:**
- In-memory hash cache for speed
- Cache loaded on startup by scanning destination
- SHA256 hashing (good balance of speed/security)
- Duplicate handling: skip and optionally archive

**Batch Processing:**
- Groups files to reduce indexing overhead
- Triggers indexing once per batch instead of per file
- Configurable batch size and timeout
- Efficient for high-volume uploads

**Error Handling:**
- Retry logic with max 3 attempts
- Failed files re-queued automatically
- Comprehensive logging at each step
- CommandResult wrapper for Docker exec status

**Thread Safety:**
- Queue for inter-thread communication
- Lock protection for pending file dict
- Event-based shutdown signaling
- Clean thread joins with timeouts

## Next Steps (Phase 3)

- [ ] SSH proxy implementation for Swarm mode
- [ ] Proxy Dockerfiles (Nextcloud + PhotoPrism)
- [ ] Swarm service discovery
- [ ] Secure SSH communication layer
- [ ] Proxy command whitelisting
- [ ] Docker Swarm stack files
- [ ] Keypair management integration

## Known Limitations / TODOs

- [ ] SSH proxy currently falls back to direct exec
- [ ] Manual sync not fully implemented (TODO in orchestrator)
- [ ] No persistent task history yet (in-memory only)
- [ ] Need to handle PhotoPrism import timing (wait for completion)
- [ ] Some type hints need Optional[] refinement
- [ ] Integration tests needed for full workflow

## Technical Debt

- Consider adding SQLite for persistent sync history
- May need rate limiting for very high volume scenarios
- Could optimize cache loading with incremental updates
- Batch size/timeout should be configurable per folder

## Performance Considerations

- Cache loading time depends on destination size
- Hash calculation is CPU-bound (but fast with SHA256)
- Thread pool for parallel file hashing could help
- Monitor memory usage with large caches

## Security Notes

- Docker socket access required (read-only would be better)
- Command execution needs validation/sanitization
- SSH keys for Swarm must be secured properly
- File paths need sanitization to prevent traversal
