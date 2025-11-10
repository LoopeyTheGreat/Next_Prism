# Next_Prism Testing Plan

## 📅 Tomorrow's Testing Session

Now that all components are built and integrated, here's the comprehensive testing plan.

---

## 🎯 Testing Goals

1. Verify complete sync workflow end-to-end
2. Validate deduplication prevents duplicate imports
3. Test manual triggers from web UI
4. Confirm scheduling system works
5. Check error handling and recovery
6. Monitor performance under load

---

## 🔧 Pre-Test Setup

### 1. Environment Preparation

```bash
# Start Docker containers
cd /path/to/docker-compose
docker-compose up -d nextcloud photoprism

# Verify containers running
docker ps | grep -E "nextcloud|photoprism"

# Check container logs
docker logs nextcloud --tail 50
docker logs photoprism --tail 50
```

### 2. Configuration Check

Review `config/config.yaml`:
```yaml
docker:
  swarm_mode: false  # Set to true if using Swarm
  
nextcloud:
  data_path: "/var/lib/nextcloud/data"  # Verify correct path
  container_name: "nextcloud"  # Match actual container
  
photoprism:
  import_path: "/mnt/photoprism-import"  # Verify correct path
  container_name: "photoprism"  # Match actual container
  
monitoring:
  debounce_seconds: 5  # Start with 5 seconds
  recursive: true
  
sync_engine:
  import_mode: "move"  # Or "copy" for testing
  verify_hashes: true
```

### 3. Test Photos Preparation

Create test photo set:
```bash
# Create test directory
mkdir -p ~/next_prism_test_photos

# Prepare test files
# - 5-10 unique photos (different content)
# - 2-3 duplicate copies (same content, different names)
# - Various formats: JPG, PNG, HEIC, RAW
# - Different sizes: Small (<1MB), Medium (1-5MB), Large (>5MB)
```

### 4. Logging Setup

```bash
# Create logs directory if needed
mkdir -p /mnt/c/Projects/Next_Prism/logs

# Tail logs in separate terminal
tail -f /mnt/c/Projects/Next_Prism/logs/next_prism.log
```

---

## 🧪 Test Cases

### Test 1: Basic Startup
**Objective**: Verify system starts without errors

```bash
cd /mnt/c/Projects/Next_Prism
source venv/bin/activate
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8080
```

**Expected Results**:
- ✅ No import errors
- ✅ "Application startup complete" message
- ✅ Web UI accessible at http://localhost:8080
- ✅ Dashboard loads without errors
- ✅ Status shows "running"

**Validation**:
```bash
# Check web UI
curl http://localhost:8080/health

# Check API status
curl http://localhost:8080/api/status
```

---

### Test 2: Configuration Display
**Objective**: Verify configuration loads and displays correctly

**Steps**:
1. Navigate to http://localhost:8080/config
2. Review displayed configuration
3. Check all sections present

**Expected Results**:
- ✅ Docker settings displayed
- ✅ Nextcloud settings displayed
- ✅ PhotoPrism settings displayed
- ✅ Monitoring settings displayed
- ✅ No errors in browser console

---

### Test 3: File Detection
**Objective**: Verify FileWatcher detects new photos

**Steps**:
1. Identify Nextcloud user data directory (e.g., `/var/lib/nextcloud/data/admin/files`)
2. Copy one test photo to the directory
3. Wait 5+ seconds (debounce period)
4. Check logs for detection event

**Expected Results**:
- ✅ "New photo callback" log entry
- ✅ "Added to queue" log entry
- ✅ Queue size increases (check /api/status)

**Validation**:
```bash
# Check logs
grep "New photo callback" logs/next_prism.log

# Check queue via API
curl http://localhost:8080/api/status | jq '.queue_size'
```

---

### Test 4: Deduplication
**Objective**: Verify duplicate detection works

**Steps**:
1. Add unique photo to Nextcloud folder
2. Wait for processing
3. Add duplicate copy (same content, different name)
4. Check logs for duplicate detection

**Expected Results**:
- ✅ First file processed normally
- ✅ Second file detected as duplicate
- ✅ "Duplicate detected" log entry
- ✅ Second file NOT moved to PhotoPrism

**Validation**:
```bash
# Check deduplication logs
grep "Duplicate detected" logs/next_prism.log

# Check PhotoPrism import directory
ls -la /mnt/photoprism-import/
```

---

### Test 5: File Move Operation
**Objective**: Verify safe file moving

**Steps**:
1. Add unique photo to Nextcloud folder
2. Wait for detection and queueing
3. Monitor processor thread activity
4. Verify file moved to PhotoPrism import

**Expected Results**:
- ✅ File detected and queued
- ✅ Hash calculated before move
- ✅ File moved to import directory
- ✅ Hash verified after move
- ✅ Move logged to history
- ✅ Original file removed from Nextcloud (if import_mode=move)

**Validation**:
```bash
# Check file exists in PhotoPrism import
ls -la /mnt/photoprism-import/

# Check file removed from Nextcloud (if move mode)
ls -la /var/lib/nextcloud/data/admin/files/

# Check move success in logs
grep "File moved successfully" logs/next_prism.log
```

---

### Test 6: PhotoPrism Import Trigger
**Objective**: Verify PhotoPrism import command executes

**Steps**:
1. Ensure files in PhotoPrism import directory
2. Wait for batch processing
3. Check PhotoPrism container logs

**Expected Results**:
- ✅ "photoprism import" command executed
- ✅ PhotoPrism processes files
- ✅ Photos appear in PhotoPrism UI
- ✅ Import command logged

**Validation**:
```bash
# Check PhotoPrism logs
docker logs photoprism --tail 100 | grep import

# Check PhotoPrism UI
# Open http://localhost:2342 (or your PhotoPrism URL)
# Verify photos imported
```

---

### Test 7: Nextcloud Scanning
**Objective**: Verify Nextcloud file scanning triggers

**Steps**:
1. After files moved, wait for indexing
2. Check Nextcloud logs for scan command

**Expected Results**:
- ✅ "occ files:scan" command executed
- ✅ Nextcloud updates file cache
- ✅ Scan command logged

**Validation**:
```bash
# Check Nextcloud logs
docker logs nextcloud --tail 100 | grep "files:scan"

# Check scan in Next_Prism logs
grep "Triggering Nextcloud scan" logs/next_prism.log
```

---

### Test 8: Manual Sync Trigger
**Objective**: Verify web UI manual trigger works

**Steps**:
1. Add multiple photos to Nextcloud folder
2. Open web UI dashboard
3. Click "Trigger Sync" button
4. Monitor status and logs

**Expected Results**:
- ✅ API request succeeds
- ✅ Queue processes pending files immediately
- ✅ Status updates in UI
- ✅ Manual trigger logged

**Validation**:
```bash
# Trigger via API
curl -X POST http://localhost:8080/api/sync/trigger \
  -H "Content-Type: application/json" \
  -d '{"folder_path": null, "force": false}'

# Check response
# Expected: {"success": true, "message": "Sync triggered successfully", "queue_size": <number>}
```

---

### Test 9: Pause/Resume Functionality
**Objective**: Verify orchestrator can be paused and resumed

**Steps**:
1. Add photos to trigger processing
2. Pause sync via web UI
3. Add more photos (should not be processed)
4. Resume sync
5. Verify delayed photos now process

**Expected Results**:
- ✅ Pause stops processing
- ✅ Queue still accepts new files
- ✅ Resume starts processing again
- ✅ All files eventually processed

**Validation**:
```bash
# Pause
curl -X POST http://localhost:8080/api/sync/pause

# Check status
curl http://localhost:8080/api/status | jq '.status'
# Expected: "stopped"

# Resume
curl -X POST http://localhost:8080/api/sync/resume

# Check status
curl http://localhost:8080/api/status | jq '.status'
# Expected: "running"
```

---

### Test 10: Scheduled Scans
**Objective**: Verify scheduler triggers scans

**Steps**:
1. Update config to short interval (e.g., "*/2 * * * *" for every 2 minutes)
2. Restart application
3. Wait for scheduled trigger
4. Check logs for scheduled scan

**Expected Results**:
- ✅ Scheduler starts with application
- ✅ Jobs added successfully
- ✅ Scheduled scan executes
- ✅ Scan callback invoked

**Validation**:
```bash
# Check scheduler logs
grep "Scheduled scan triggered" logs/next_prism.log

# Check APScheduler activity
grep "apscheduler" logs/next_prism.log
```

---

### Test 11: Error Handling
**Objective**: Verify graceful error handling

**Test Scenarios**:

**11a: PhotoPrism Container Stopped**
```bash
docker stop photoprism
# Add photo, verify error logged, queue retains item
docker start photoprism
# Verify retry succeeds
```

**11b: Insufficient Disk Space**
```bash
# Simulate by setting very high space requirement in config
# Or fill disk if safe to do so
# Verify move fails gracefully
```

**11c: Permission Issues**
```bash
# Make import directory read-only
chmod 555 /mnt/photoprism-import
# Add photo, verify error logged
chmod 755 /mnt/photoprism-import
```

**11d: Invalid Configuration**
```bash
# Set invalid container name
# Restart, verify error logged but application doesn't crash
```

---

### Test 12: Performance Under Load
**Objective**: Test with multiple files

**Steps**:
1. Add 50-100 photos to Nextcloud folder at once
2. Monitor:
   - CPU usage
   - Memory usage
   - Queue processing rate
   - Log volume
3. Verify all files processed correctly

**Expected Results**:
- ✅ All files detected
- ✅ Queue grows then drains
- ✅ No memory leaks
- ✅ Reasonable CPU usage
- ✅ All files eventually processed

**Validation**:
```bash
# Monitor system resources
top -p $(pgrep -f "uvicorn")

# Watch queue size
watch -n 1 'curl -s http://localhost:8080/api/status | jq ".queue_size"'

# Count processed files
grep "File moved successfully" logs/next_prism.log | wc -l
```

---

## 📊 Test Results Template

### Test Execution Log

| Test # | Test Name | Status | Duration | Notes |
|--------|-----------|--------|----------|-------|
| 1 | Basic Startup | ⏳ Pending | - | - |
| 2 | Configuration Display | ⏳ Pending | - | - |
| 3 | File Detection | ⏳ Pending | - | - |
| 4 | Deduplication | ⏳ Pending | - | - |
| 5 | File Move Operation | ⏳ Pending | - | - |
| 6 | PhotoPrism Import Trigger | ⏳ Pending | - | - |
| 7 | Nextcloud Scanning | ⏳ Pending | - | - |
| 8 | Manual Sync Trigger | ⏳ Pending | - | - |
| 9 | Pause/Resume | ⏳ Pending | - | - |
| 10 | Scheduled Scans | ⏳ Pending | - | - |
| 11 | Error Handling | ⏳ Pending | - | - |
| 12 | Performance Under Load | ⏳ Pending | - | - |

**Legend**: ✅ Pass | ❌ Fail | ⚠️ Partial | ⏳ Pending

---

## 🐛 Known Issues to Watch For

Based on the architecture, keep an eye on:

1. **Thread Synchronization**
   - Watcher thread and processor thread coordination
   - Queue operations under high load

2. **File System Events**
   - Watchdog may generate multiple events for single file
   - Debouncing must prevent duplicate processing

3. **Docker Command Timeouts**
   - Large imports may take >5 minutes
   - Ensure timeout values appropriate

4. **Hash Cache Performance**
   - With many files, cache size could grow large
   - Monitor memory usage

5. **Scheduler Precision**
   - APScheduler accuracy with short intervals
   - Ensure jobs don't overlap

---

## 🔍 Debugging Tips

### Check Orchestrator State
```python
# In Python shell or debug session
from src.core.orchestrator import Orchestrator
# Check orchestrator attributes
orchestrator._running
orchestrator.file_queue.qsize()
orchestrator.folder_watcher.watched_folders
```

### Inspect Queue Contents
```python
from src.core.sync_queue import SyncQueue
queue = SyncQueue()
queue.load_from_file('queue_persistence.json')
items = queue.get_items()
for item in items:
    print(f"{item.priority}: {item.file_path}")
```

### Monitor File Watcher
```bash
# Check what folders being watched
grep "Watching folder" logs/next_prism.log

# Check file events
grep "File event" logs/next_prism.log
```

### Check Docker Commands
```bash
# List recent Docker commands
grep "Executing Docker command" logs/next_prism.log

# Check command results
grep "Command result" logs/next_prism.log
```

---

## ✅ Success Criteria

Testing is considered successful when:

1. ✅ All 12 test cases pass
2. ✅ No critical errors in logs
3. ✅ All photos processed correctly
4. ✅ Deduplication prevents duplicates
5. ✅ Web UI responsive and functional
6. ✅ Manual triggers work reliably
7. ✅ Scheduled scans execute
8. ✅ Error recovery works
9. ✅ Performance acceptable under load
10. ✅ System runs stable for >1 hour

---

## 📝 Post-Testing Actions

1. **Document Issues**
   - Create GitHub issues for bugs found
   - Priority: Critical, High, Medium, Low

2. **Update Configuration**
   - Adjust debounce timing based on results
   - Tune batch sizes
   - Optimize scan schedules

3. **Performance Tuning**
   - Adjust thread pool sizes if needed
   - Optimize hash cache settings
   - Tune Docker command timeouts

4. **Write User Documentation**
   - Setup guide
   - Configuration reference
   - Troubleshooting guide
   - FAQ

5. **Plan Phase 3 Features**
   - Advanced deduplication (perceptual hashing)
   - Web UI enhancements
   - Notification system
   - Statistics dashboard
   - Backup/restore functionality

---

## 🎓 Testing Best Practices

1. **Isolate Test Environment**
   - Use separate test Nextcloud/PhotoPrism instances
   - Don't test with production data initially

2. **Start Simple**
   - Test with single file first
   - Gradually increase complexity
   - Validate each component independently

3. **Log Everything**
   - Set log level to DEBUG initially
   - Monitor logs continuously
   - Save logs for analysis

4. **Take Backups**
   - Backup configuration before testing
   - Backup test data
   - Document baseline state

5. **Test in Order**
   - Follow test case sequence
   - Don't skip tests
   - Fix issues before proceeding

---

## 🚀 Ready to Test!

Everything is in place. Tomorrow's testing session will validate the complete system and prepare for production deployment.

**Good luck! 🍀**
