# Custom Docker-Based Photo Sync and Indexing Orchestrator

This guide outlines a robust workflow for managing a multi-user Nextcloud deployment with centralized long-term photo storage and tight integration with both Nextcloud Photos/Memories and PhotoPrism. The focus is on moving new user-uploaded photos to a shared main location, triggering re-indexing for both applications, preventing duplicates, and providing web-based scheduling/control. This design works for both Docker Swarm setups and standard single-host Docker.

## Goals

- Automatically move new photos from user-specific Nextcloud directories to a central shared photo archive (bind mount or external storage)
- Trigger Nextcloud `occ files:scan` commands to update database indexes after each move (cover both the main archive and user-specific folders)
- Trigger Nextcloud `occ memories:index` (or equivalent) for the shared photo library to update gallery/AI features
- Minimize duplicates by updating user storage after moves (optional: archive, delete, or mark moved files)
- Provide a simple web GUI for:
    - Scheduling/configuring move intervals (e.g., every X minutes/hours/days)
    - Manual triggering of sync/move
    - Progress and status display
    - Error reporting and logs
- Maintain compatibility for both Docker Swarm and vanilla Docker deployments

## Architectural Overview

- **Dockerized Service** runs as a container, with access to Nextcloud data directories (user uploads and main photo archive) via bind mounts or shared volumes
- **Scheduler Service** periodically executes the move and scan logic, configurable via web GUI
- **RESTful Web GUI** provides simple management interface (can use Flask, FastAPI, or Node/Express for easy setup)
- **File Move Logic**: scans for new images in user upload folders, records/moves to central archive, optional dedupe, logs action/status
- **Nextcloud Indexing Trigger**: runs `docker exec` to trigger `occ files:scan` on directories after moves
- **Memory Index Trigger**: runs `occ memories:index` or similar for AI/thumbnail refresh
- **User Sync Update**: optional post-move action to archive/delete moved originals; prevents duplicate display at user level

## Step-by-Step Plan

### 1. Docker Service Setup
- Create a Docker image with Python (or Node.js) and required dependencies for:
    - File/folder operations
    - CLI execution (for occ commands)
    - Web framework for GUI (Flask, FastAPI, Express, etc.)
    - Scheduler library (Celery, APScheduler, cron, etc.)
- Mount volumes:
    - Nextcloud data root (read/write): e.g., `/var/lib/nextcloud/data`
    - Main photo archive: e.g., `/mnt/photoarchive`
    - Optional: Nextcloud config/occ binary for CLI access
- Expose web UI port (e.g., 8080)

### 2. File Move and Dedupe
- Compare source (user uploads) vs. destination (main archive) files (hash, name, or EXIF)
- Move/copy new photos from each user's folder to centralized photo folder
    - Optionally delete or archive originals after confirming successful move
    - Log each move per user and photo (date, name, any errors)
- Avoid duplicates via filename or hash checking before move

### 3. Trigger Nextcloud Index Refresh
- After move, run:
    ```bash
    docker exec <nextcloud_container> occ files:scan --path="/USERNAME/files/Photos"
    docker exec <nextcloud_container> occ files:scan --path="/centralarchive"
    docker exec <nextcloud_container> occ memories:index
    ```
- Provide REST endpoint for manual triggering/index on-demand
- Periodically verify index/scan status for troubleshooting

### 4. Ensure User-Level Sync
- Optionally, after moving files, clear originals from user folder or move to an 'Archived' subfolder
- Trigger file scan for user folder post-move to update cloud view for the user
- Log actions for troubleshooting and audit

### 5. Web GUI
- Simple interface for:
    - Setting move/index intervals (with cron-like syntax, dropdowns, etc.)
    - Manual "Run Now" buttons and status/progress display (show scanned folders, files moved, last error)
    - View logs and error reports
    - Basic config: mount paths, Nextcloud container name, archive/delete options
- REST API endpoints for controlling all functions for future extension/automation

### 6. Docker Swarm Compatibility
- Use Docker secrets/env variables for paths/credentials
- Use Docker Swarm service labels/affinity to ensure container runs on same node as Nextcloud storage
- Optional: Scale out to handle many users/files; centralize logs/status via Swarm overlay network if needed
- Provide example `docker-compose.yml` and `stack.yml` files for both Docker and Swarm

### 7. Security and Testing
- Ensure credentials for occ commands are handled via secrets/env not plaintext
- Log all actions securely, with sufficient audit data
- Test with dummy photos, simulate large batch/slow external mounts
- Provide restart, error recovery, and self-heal for scheduler tasks

## Example File/Folder Structure
- `/mnt/photoarchive` (main shared photo library, external storage or NAS)
- `/var/lib/nextcloud/data/USER/files/Photos` (auto-upload folders per user)

## Additional Notes
- Manual triggering and status UI make it easy for users/admins to intervene and troubleshoot
- Extendable for future AI/photo workflows, e.g., face recognition, duplicate clustering before move
- Well-suited for 90s sci-fi themed error popups, because why not

---

Feel free to adjust specifics for your target stack, Python vs Node, and your Nextcloud/PhotoPrism environment. VC Copilot/Claude can generate the actual code modules for each part.

additional notes
monitor tbe mointed nextcloud-data folder for new users
allow the user to pick which users to inclufe
maintain a config file thats bind mountrd, which csn be manipylated by the usr manually, or the web ui

)add ntfy notifications gor failures, set via config / webui, user selects nnotification levrls

put everythin in one app tgat handles bith swarm and non swarm usage. 2 Compose files, docjer-compose.yaml and swarm-config.yaml

maintain notes for ypurself or other coding age ts in _AI_Notes. Create user freindly READMR.md

oriject will be made publuc / open source, please provide comprehensive documrntation for forks, both seperate and yhtoughout yhe code as comments

lets use python 3x as our coding language.

build ontop of a debian based image, using a build file to assemmble

security for the docker and webui is very importNt.


files to br moved to the phitiprism 'import' folder, allowing photo prism to organize in its album cilder, nextcloud will  need to access and scan the album folder after photoprism indexing is cimplete

id like the web ui to be password protected if user wants, optional
optional ip/subnet white list / access security
