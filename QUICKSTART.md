# Next_Prism Quick Start Guide

## 🚀 Get Up and Running in 5 Minutes

---

## Installation

```bash
cd /mnt/c/Projects/Next_Prism

# Install dependencies (if not already done)
pip install -r requirements.txt
```

---

## Configuration

Edit `config/config.yaml`:

```yaml
docker:
  swarm_mode: false  # or true if using Docker Swarm
  
nextcloud:
  container_name: "nextcloud"  # Your Nextcloud container name
  data_path: "/var/lib/nextcloud/data"  # Path to Nextcloud data
  
photoprism:
  container_name: "photoprism"  # Your PhotoPrism container name
  import_path: "/mnt/photoprism-import"  # Import directory
```

---

## Start the System

```bash
# Method 1: Direct Python
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8080

# Method 2: Development mode (auto-reload)
python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8080 --reload
```

---

## Access Web UI

Open browser: **http://localhost:8080**

Default login:
- Password: Set in config `security.web_password` (default: empty)

---

## Common Tasks

### Manual Sync Trigger
```bash
curl -X POST http://localhost:8080/api/sync/trigger \
  -H "Content-Type: application/json" \
  -d '{"folder_path": null, "force": false}'
```

### Check Status
```bash
curl http://localhost:8080/api/status
```

### Pause Sync
```bash
curl -X POST http://localhost:8080/api/sync/pause
```

### Resume Sync
```bash
curl -X POST http://localhost:8080/api/sync/resume
```

---

## Troubleshooting

### Web UI won't start
```bash
# Check if port 8080 in use
fuser -k 8080/tcp

# Check logs
tail -f logs/next_prism.log
```

### Files not detected
```bash
# Verify FileWatcher running
grep "FileWatcher" logs/next_prism.log

# Check monitored folders
curl http://localhost:8080/api/status | jq '.monitored_folders'
```

### Docker commands failing
```bash
# Test Docker connection
docker ps

# Check container names match config
docker ps --format "{{.Names}}"

# Verify paths exist
docker exec nextcloud ls /var/lib/nextcloud/data
docker exec photoprism ls /mnt/photoprism-import
```

---

## File Locations

- **Config**: `config/config.yaml`
- **Logs**: `logs/next_prism.log`
- **Queue**: `queue_persistence.json` (auto-created)
- **Hash Cache**: `hash_cache.json` (auto-created)
- **Templates**: `src/web/templates/`
- **Static**: `src/web/static/`

---

## Key Features

✅ **Auto-detection**: Monitors Nextcloud folders in real-time  
✅ **Deduplication**: Prevents duplicate imports with SHA256  
✅ **Safe operations**: Verifies hashes and disk space  
✅ **Priority queue**: Manual triggers processed first  
✅ **Scheduling**: Cron-based periodic scans  
✅ **Web UI**: Full dashboard and control  
✅ **Swarm support**: Works with Docker and Swarm  

---

## Need Help?

- Check `_AI_Notes_/integration-complete.md` for architecture
- See `_AI_Notes_/tomorrow-testing-plan.md` for testing guide
- Review logs at `logs/next_prism.log`

---

**Next_Prism v0.1.0** - Happy syncing! 📸✨
