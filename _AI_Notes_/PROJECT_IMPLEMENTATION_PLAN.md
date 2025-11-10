# Next_Prism: Phased Implementation Plan

**Project**: Nextcloud-to-PhotoPrism Sync Orchestrator  
**Language**: Python 3.x  
**Base Image**: Debian-based  
**Deployment**: Docker (standalone) & Docker Swarm  
**Date Created**: November 9, 2025

---

## Executive Summary

This is a comprehensive Docker-based orchestration service that automates photo synchronization between Nextcloud user directories and PhotoPrism's import system. The service monitors multiple folders, moves photos to PhotoPrism for organization, triggers appropriate indexing commands, and provides a secure web UI for management and configuration.

**Key Features:**
- Multi-user Nextcloud photo monitoring with selective user inclusion
- Automatic PhotoPrism import triggering with post-import Nextcloud scanning
- Flexible folder monitoring (Nextcloud users + custom folders)
- Per-folder scheduling configuration (default or custom intervals)
- Secure web UI with optional password protection and IP whitelisting
- ntfy.sh integration for failure notifications
- Archive option instead of deletion for moved files
- Docker Swarm proxy services for seamless container command execution
- Comprehensive logging and error recovery

---

## Phase 1: Project Foundation & Core Architecture
**Estimated Duration**: Week 1

### 1.1 Project Structure Setup
- [ ] Initialize Git repository with `.gitignore` (Python, Docker, IDE files)
- [ ] Create directory structure:
  ```
  Next_Prism/
  ├── _AI_Notes/                    # Development notes for AI agents
  │   ├── architecture-notes.md
  │   ├── swarm-proxy-design.md
  │   └── security-considerations.md
  ├── src/                          # Python source code
  │   ├── __init__.py
  │   ├── config/                   # Configuration management
  │   ├── core/                     # Core business logic
  │   ├── monitoring/               # File monitoring services
  │   ├── scheduler/                # Task scheduling
  │   ├── docker_interface/         # Docker exec/command handling
  │   ├── web/                      # Web UI (Flask/FastAPI)
  │   └── utils/                    # Utilities and helpers
  ├── config/                       # User-editable configuration
  │   └── config.yaml               # Main configuration file
  ├── docker/                       # Docker-related files
  │   ├── Dockerfile                # Main application container
  │   ├── proxy-nextcloud.Dockerfile  # Swarm proxy for Nextcloud
  │   └── proxy-photoprism.Dockerfile # Swarm proxy for PhotoPrism
  ├── compose/
  │   ├── docker-compose.yaml       # Standard Docker deployment
  │   ├── swarm-stack.yaml          # Docker Swarm deployment
  │   ├── nextcloud-proxy.yaml      # Nextcloud proxy service
  │   └── photoprism-proxy.yaml     # PhotoPrism proxy service
  ├── tests/                        # Unit and integration tests
  ├── docs/                         # User documentation
  │   ├── README.md
  │   ├── INSTALLATION.md
  │   ├── CONFIGURATION.md
  │   ├── SWARM_SETUP.md
  │   └── CONTRIBUTING.md
  ├── scripts/                      # Setup and utility scripts
  │   ├── generate_keys.sh          # SSH keypair generation
  │   └── first_run_setup.sh        # Initial setup wizard
  ├── requirements.txt              # Python dependencies
  └── README.md                     # Main project README
  ```

### 1.2 Configuration System Design
- [ ] Design YAML configuration schema:
  - Global settings (container names, mount paths, network mode)
  - User selection for Nextcloud (include/exclude lists)
  - Folder monitoring configurations with individual schedules
  - Security settings (passwords, IP whitelist)
  - ntfy.sh notification settings with severity levels
  - Archive vs. delete preferences
  - Docker Swarm mode detection and proxy settings
- [ ] Implement configuration loader with validation
- [ ] Create configuration file watcher for hot-reload
- [ ] Build configuration merger (file + web UI changes)

### 1.3 Base Docker Image
- [ ] Create multi-stage Dockerfile based on `debian:bookworm-slim`
- [ ] Install system dependencies:
  - Python 3.11+
  - OpenSSH client (for Swarm proxy communication)
  - curl/wget for health checks
  - File monitoring tools (inotify-tools)
- [ ] Install Python dependencies (requirements.txt):
  - FastAPI + Uvicorn (web framework)
  - APScheduler (task scheduling)
  - PyYAML (config parsing)
  - watchdog (file monitoring)
  - docker-py (Docker API interface)
  - paramiko (SSH for Swarm proxies)
  - requests (HTTP/ntfy integration)
  - bcrypt (password hashing)
  - python-multipart (file uploads)
- [ ] Set up proper user/permissions (non-root execution)
- [ ] Configure health check endpoint
- [ ] Optimize image size (multi-stage build, cleanup)

---

## Phase 2: Core Synchronization Engine
**Estimated Duration**: Week 2

### 2.1 File Monitoring System
- [ ] Implement folder watcher using `watchdog` library
- [ ] Detect new users in Nextcloud data directory automatically
- [ ] Monitor configured folders for new photo files (extensions: jpg, jpeg, png, heic, raw, etc.)
- [ ] Queue detected files for processing with metadata (source, timestamp, user)
- [ ] Implement debouncing to avoid duplicate triggers on file writes
- [ ] Handle symlinks and nested directory structures

### 2.2 File Move Logic with Deduplication
- [ ] Implement file hash calculation (SHA256 or MD5)
- [ ] Build duplicate detection system:
  - Check filename in destination
  - Check file hash in destination
  - Optional: EXIF metadata comparison
- [ ] Create safe file move operation:
  - Verify source file exists and is readable
  - Check destination has sufficient space
  - Move to PhotoPrism import folder
  - Verify successful move (hash comparison)
  - Handle collision scenarios (rename with timestamp)
- [ ] Implement archive option:
  - Create archive folder structure in Nextcloud user directory
  - Move originals to archive instead of deletion
  - Preserve directory structure in archive
- [ ] Transaction logging for each file operation
- [ ] Rollback mechanism for failed moves

### 2.3 Docker Command Interface
- [ ] Build Docker exec wrapper for standard Docker mode:
  - Detect Nextcloud container by name/label
  - Detect PhotoPrism container by name/label
  - Execute `occ` commands safely with error handling
  - Execute PhotoPrism CLI commands
- [ ] Implement command queue with retry logic
- [ ] Add timeout handling for long-running commands
- [ ] Parse command output for success/failure detection
- [ ] Log all command executions with timestamps

---

## Phase 3: Docker Swarm Proxy Architecture
**Estimated Duration**: Week 2

### 3.1 Proxy Service Design
- [ ] **Architecture Decision**: Design secure proxy communication method
  - Option A: SSH-based proxy with keypair authentication
  - Option B: REST API proxy with mutual TLS
  - **Recommended**: SSH proxy for simplicity and security
- [ ] Create lightweight proxy containers:
  - Minimal Debian/Alpine base
  - OpenSSH server
  - Docker CLI tools
  - Restricted command execution (whitelist approach)

### 3.2 Nextcloud Proxy Implementation
- [ ] Build Nextcloud proxy Dockerfile
- [ ] Configure SSH server with pubkey authentication only
- [ ] Implement command whitelist (only allow `occ files:scan`, `occ memories:index`)
- [ ] Add command sanitization and validation
- [ ] Create Docker Swarm service definition
- [ ] Implement service discovery (Docker DNS, labels, or overlay network)
- [ ] Add health checks and auto-restart policies

### 3.3 PhotoPrism Proxy Implementation
- [ ] Build PhotoPrism proxy Dockerfile (similar to Nextcloud)
- [ ] Whitelist PhotoPrism CLI commands (`photoprism index`, etc.)
- [ ] Configure SSH access with separate keypair
- [ ] Create Swarm service definition
- [ ] Implement automatic discovery mechanism

### 3.4 Secure Keypair Management
- [ ] Create keypair generation script:
  - Generate ED25519 SSH keypairs
  - Store private keys securely (Docker secrets in Swarm)
  - Distribute public keys to proxy containers
  - Set proper file permissions (600 for private keys)
- [ ] Implement automatic keypair rotation (optional, advanced)
- [ ] Document manual keypair setup for security-conscious users

### 3.5 Proxy Communication Layer
- [ ] Build SSH client wrapper in Python (using Paramiko)
- [ ] Implement proxy auto-discovery:
  - Check for proxy services via Docker API
  - Fall back to direct exec if proxies not available
- [ ] Create unified command interface (abstracts standard vs. Swarm)
- [ ] Add connection pooling and retry logic
- [ ] Implement command response parsing

---

## Phase 4: Scheduling & Task Management
**Estimated Duration**: Week 1

### 4.1 Scheduler Implementation
- [ ] Integrate APScheduler with FastAPI
- [ ] Support multiple schedule types per folder:
  - Interval-based (every X minutes/hours)
  - Cron expression support
  - Manual trigger only
  - Default schedule inheritance
- [ ] Implement schedule persistence (survive restarts)
- [ ] Create task queue with priority handling
- [ ] Add concurrent task limits (prevent resource exhaustion)
- [ ] Implement graceful shutdown (complete running tasks)

### 4.2 Task Execution Pipeline
- [ ] Define task workflow:
  1. Scan folder for new files
  2. Process files (dedupe, move)
  3. Execute PhotoPrism import/index
  4. Wait for PhotoPrism completion
  5. Execute Nextcloud scan on album folder
  6. Execute Nextcloud scan on user folder (if archived)
  7. Trigger Memories index
  8. Log results and cleanup
- [ ] Implement task state tracking (pending, running, completed, failed)
- [ ] Add task history and statistics
- [ ] Create task cancellation mechanism

### 4.3 Error Handling & Recovery
- [ ] Implement retry logic with exponential backoff
- [ ] Define recoverable vs. non-recoverable errors
- [ ] Create dead letter queue for permanently failed tasks
- [ ] Add manual retry option via web UI
- [ ] Implement circuit breaker pattern for failing services

---

## Phase 5: Web UI Development
**Estimated Duration**: Week 2-3

### 5.1 Backend API (FastAPI)
- [ ] Set up FastAPI application structure
- [ ] Implement authentication system:
  - Optional password protection (bcrypt hashing)
  - Session management (JWT tokens)
  - Optional IP/subnet whitelist middleware
- [ ] Create REST API endpoints:
  - **Config Management**: GET/POST `/api/config`
  - **Users**: GET `/api/users` (detected Nextcloud users)
  - **Folders**: GET/POST/DELETE `/api/folders`
  - **Schedules**: GET/POST/PUT `/api/schedules/{folder_id}`
  - **Tasks**: GET `/api/tasks`, POST `/api/tasks/trigger`
  - **Logs**: GET `/api/logs` (paginated, filterable)
  - **Status**: GET `/api/status` (health, statistics)
  - **Notifications**: POST `/api/notifications/test`
- [ ] Implement request validation with Pydantic models
- [ ] Add CORS configuration for frontend
- [ ] Create OpenAPI documentation (auto-generated by FastAPI)

### 5.2 Frontend UI (HTML/CSS/JS)
- [ ] Choose frontend approach:
  - Option A: Server-side templates (Jinja2)
  - Option B: Modern SPA (Vue.js/React - keep it simple)
  - **Recommended**: Vue.js for reactivity without complexity
- [ ] Design responsive UI layout:
  - **Dashboard**: Overview, statistics, recent activity
  - **Folders**: List monitored folders with status indicators
  - **Configuration**: Edit settings, user selection, scheduling
  - **Logs**: Filterable log viewer with search
  - **Manual Trigger**: Big button to run sync now
  - **Notifications**: Configure ntfy.sh integration
  - **Security**: Set password, manage IP whitelist
- [ ] Implement real-time updates:
  - WebSocket connection for live status
  - Progress bars for running tasks
  - Toast notifications for events
- [ ] Add 90s sci-fi themed error popups (as requested! 🚀)
- [ ] Ensure accessibility (ARIA labels, keyboard navigation)

### 5.3 Security Implementation
- [ ] Password protection:
  - Login page with bcrypt verification
  - Secure session management
  - Password change functionality
  - Rate limiting on login attempts
- [ ] IP whitelist:
  - CIDR notation support
  - Middleware to check incoming requests
  - Configurable via web UI or config file
- [ ] HTTPS support:
  - Document reverse proxy setup (Traefik, Nginx)
  - Provide example configurations
  - Self-signed certificate generation script
- [ ] Security headers:
  - Content Security Policy (CSP)
  - X-Frame-Options, X-Content-Type-Options
  - HSTS (when using HTTPS)

---

## Phase 6: Notification System
**Estimated Duration**: Week 1

### 6.1 ntfy.sh Integration
- [ ] Implement ntfy client wrapper
- [ ] Support notification levels:
  - **Critical**: Service crashes, data loss risks
  - **Error**: Task failures, command execution failures
  - **Warning**: Partial failures, high retry counts
  - **Info**: Successful completions (optional)
  - **Debug**: Detailed operation logs (optional)
- [ ] Allow user-configurable severity threshold
- [ ] Add notification rate limiting (avoid spam)
- [ ] Implement notification formatting:
  - Clear subject lines
  - Actionable messages
  - Include relevant context (folder, user, error details)
- [ ] Add "Test Notification" button in web UI
- [ ] Support multiple ntfy topics (different priorities)

### 6.2 Logging System
- [ ] Implement structured logging (JSON format)
- [ ] Configure log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- [ ] Set up log rotation (max size, max files)
- [ ] Create separate log files:
  - Application log (general operations)
  - Task log (sync operations)
  - Error log (failures only)
  - Audit log (config changes, manual triggers)
- [ ] Add log persistence via Docker volume
- [ ] Implement log viewer in web UI with filtering:
  - By severity level
  - By date range
  - By folder/user
  - Full-text search
- [ ] Export logs functionality (download as JSON/CSV)

---

## Phase 7: Docker Deployment Configurations
**Estimated Duration**: Week 1

### 7.1 Standard Docker Compose
- [ ] Create `docker-compose.yaml`:
  - Main application service with proper volumes:
    - Nextcloud data (read-write)
    - PhotoPrism import (read-write)
    - PhotoPrism albums (read-only, for scanning)
    - Config file (bind mount)
    - Additional monitored folders (configurable)
  - Network configuration (same network as Nextcloud/PhotoPrism)
  - Environment variables with defaults
  - Restart policy
  - Resource limits (CPU, memory)
  - Health check configuration
- [ ] Document volume mount requirements
- [ ] Provide example `.env` file
- [ ] Add comments explaining each section

### 7.2 Docker Swarm Stack
- [ ] Create `swarm-stack.yaml`:
  - Main application service
  - Placement constraints (if needed)
  - Replicas (typically 1 for file operations)
  - Docker secrets for sensitive data
  - Overlay network configuration
  - Rolling update strategy
- [ ] Create `nextcloud-proxy.yaml`:
  - Proxy service definition
  - SSH server configuration
  - Volume mounts for Docker socket access
  - Security constraints
  - Health checks
- [ ] Create `photoprism-proxy.yaml`:
  - Similar to Nextcloud proxy
  - PhotoPrism-specific command whitelist
- [ ] Document Swarm deployment process:
  - Secret creation commands
  - Stack deployment order
  - Service discovery verification

### 7.3 Environment Detection
- [ ] Implement auto-detection of Docker vs. Swarm:
  - Check for Swarm mode via Docker API
  - Detect available proxy services
  - Fall back to direct exec if proxies unavailable
- [ ] Create startup validation:
  - Verify required containers are accessible
  - Test mount points are writable
  - Validate config file syntax
  - Check Docker socket access
- [ ] Provide clear error messages for misconfiguration

---

## Phase 8: Testing & Quality Assurance
**Estimated Duration**: Week 1-2

### 8.1 Unit Testing
- [ ] Set up pytest framework
- [ ] Write tests for:
  - Configuration loading and validation
  - File deduplication logic
  - Hash calculation accuracy
  - Schedule parsing and execution
  - Command sanitization
  - Authentication/authorization
  - Notification formatting
- [ ] Aim for >80% code coverage
- [ ] Mock external dependencies (Docker, file system)

### 8.2 Integration Testing
- [ ] Set up test environment:
  - Mock Nextcloud data structure
  - Mock PhotoPrism import folder
  - Test containers for Nextcloud/PhotoPrism
- [ ] Test scenarios:
  - End-to-end photo sync workflow
  - New user detection and inclusion
  - Duplicate file handling
  - Archive folder creation
  - Failed move recovery
  - Proxy communication (Swarm mode)
  - Web UI authentication
  - Notification delivery
- [ ] Create automated test suite

### 8.3 Load Testing
- [ ] Test with large numbers of files (1000+ photos)
- [ ] Test with many users (10+ simultaneous)
- [ ] Verify resource usage (CPU, memory, disk I/O)
- [ ] Test slow network conditions (simulate NAS mounts)
- [ ] Validate concurrent task handling

### 8.4 Security Testing
- [ ] Test authentication bypass attempts
- [ ] Validate IP whitelist enforcement
- [ ] Test command injection vectors
- [ ] Verify file path traversal prevention
- [ ] Check for exposed secrets in logs
- [ ] Test SSH keypair security (Swarm proxies)

---

## Phase 9: Documentation
**Estimated Duration**: Week 1

### 9.1 User Documentation
- [ ] **README.md** (main project page):
  - Project overview and features
  - Quick start guide
  - Screenshots of web UI
  - Link to detailed documentation
  - License information (choose: MIT, Apache 2.0, GPL-3.0)
  - Contributing guidelines
- [ ] **INSTALLATION.md**:
  - Prerequisites (Docker version, system requirements)
  - Standard Docker installation steps
  - Docker Swarm installation steps
  - First-run setup wizard usage
  - Troubleshooting common issues
- [ ] **CONFIGURATION.md**:
  - Complete config.yaml reference
  - All available options explained
  - Example configurations for common scenarios
  - Schedule syntax guide (cron expressions)
  - ntfy.sh setup instructions
- [ ] **SWARM_SETUP.md**:
  - Detailed Swarm deployment guide
  - Proxy service configuration
  - SSH keypair setup
  - Security best practices
  - Multi-node considerations
- [ ] **CONTRIBUTING.md**:
  - Code style guidelines (PEP 8)
  - How to submit issues
  - Pull request process
  - Development environment setup
  - Testing requirements

### 9.2 Developer Documentation
- [ ] Create architecture diagrams:
  - System overview (component relationships)
  - Data flow diagrams (photo sync pipeline)
  - Swarm proxy communication architecture
  - Scheduling workflow
- [ ] Document all modules with docstrings:
  - Function/class purpose
  - Parameters and return types
  - Usage examples
  - Exceptions raised
- [ ] Create API documentation (auto-generated from FastAPI)
- [ ] Add inline code comments for complex logic

### 9.3 AI Agent Notes
- [ ] Maintain `_AI_Notes/` for future AI development:
  - `architecture-notes.md`: High-level design decisions
  - `swarm-proxy-design.md`: Proxy implementation details
  - `security-considerations.md`: Security design and threats
  - `testing-strategy.md`: Test coverage and scenarios
  - `future-enhancements.md`: Roadmap and ideas
- [ ] Document design decisions and trade-offs
- [ ] Provide context for future modifications

---

## Phase 10: Final Polish & Release
**Estimated Duration**: Week 1

### 10.1 Code Quality
- [ ] Run linters (pylint, flake8, black)
- [ ] Fix all warnings and errors
- [ ] Optimize performance bottlenecks
- [ ] Refactor duplicated code
- [ ] Review all TODO/FIXME comments
- [ ] Ensure consistent naming conventions

### 10.2 User Experience
- [ ] Create setup wizard script:
  - Interactive prompts for configuration
  - Automatic detection of Nextcloud/PhotoPrism containers
  - Generate initial config.yaml
  - Set up SSH keypairs for Swarm
  - Test connectivity
- [ ] Add helpful error messages with actionable solutions
- [ ] Create example Docker Compose files for common setups
- [ ] Add version information and update checker

### 10.3 Release Preparation
- [ ] Choose semantic versioning (v1.0.0)
- [ ] Create CHANGELOG.md
- [ ] Tag release in Git
- [ ] Create GitHub releases with:
  - Release notes
  - Installation instructions
  - Known issues
  - Upgrade guide (for future versions)
- [ ] Set up GitHub repository:
  - Add relevant topics/tags
  - Create issue templates
  - Set up GitHub Actions (CI/CD):
    - Automated testing
    - Docker image builds
    - Security scanning
- [ ] Publish Docker images to Docker Hub/GHCR
- [ ] Announce on relevant communities (Reddit, forums)

---

## Additional Enhancements (Future Phases)

### Phase 11: Advanced Features (Optional)
- [ ] Face recognition integration before move
- [ ] Duplicate clustering with ML
- [ ] Photo metadata preservation and enhancement
- [ ] Multi-PhotoPrism instance support
- [ ] S3/object storage support
- [ ] Webhook support for external integrations
- [ ] Grafana/Prometheus metrics export
- [ ] Mobile app for monitoring
- [ ] Plugin system for extensibility

---

## Technical Specifications Summary

### Core Technologies
- **Language**: Python 3.11+
- **Web Framework**: FastAPI + Uvicorn
- **Scheduler**: APScheduler
- **File Monitoring**: Watchdog
- **Docker Interface**: docker-py, Paramiko (SSH)
- **Frontend**: Vue.js 3 (or vanilla JS for simplicity)
- **Database**: SQLite (for task history, optional)
- **Notifications**: ntfy.sh via HTTP

### Security Features
- SSH keypair authentication for Swarm proxies
- Optional password protection (bcrypt)
- IP/subnet whitelist
- Command sanitization and whitelisting
- Non-root container execution
- Secure secret management (Docker secrets)
- HTTPS support via reverse proxy

### Deployment
- Single unified application
- Automatic Docker vs. Swarm detection
- Separate proxy containers for Swarm
- Volume mounts for data access
- Configuration via YAML file
- Environment variable overrides

---

## Success Criteria

### Functional Requirements
✅ Automatically detects new Nextcloud users  
✅ Monitors user-uploaded photos and custom folders  
✅ Moves photos to PhotoPrism import without duplicates  
✅ Triggers PhotoPrism indexing  
✅ Scans Nextcloud album and user folders post-import  
✅ Supports flexible per-folder scheduling  
✅ Provides web UI for configuration and monitoring  
✅ Sends ntfy notifications on failures  
✅ Works in both Docker and Docker Swarm environments  

### Non-Functional Requirements
✅ Secure by default (authentication, whitelisting, SSH keys)  
✅ Well-documented for users and contributors  
✅ Comprehensive inline code comments  
✅ Easy to deploy with provided Compose files  
✅ Efficient resource usage  
✅ Resilient to failures with automatic recovery  
✅ Extensible for future enhancements  

---

## Timeline Summary

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| 1. Foundation | 1 week | Project structure, config system, base Docker image |
| 2. Core Sync | 2 weeks | File monitoring, move logic, Docker interface |
| 3. Swarm Proxies | 2 weeks | SSH proxies, keypair management, auto-discovery |
| 4. Scheduling | 1 week | APScheduler integration, task pipeline, error handling |
| 5. Web UI | 2-3 weeks | FastAPI backend, Vue.js frontend, security |
| 6. Notifications | 1 week | ntfy integration, logging system |
| 7. Deployment | 1 week | Compose files, Swarm configs, env detection |
| 8. Testing | 1-2 weeks | Unit tests, integration tests, security tests |
| 9. Documentation | 1 week | User docs, developer docs, AI notes |
| 10. Release | 1 week | Code quality, UX polish, GitHub setup |
| **Total** | **12-14 weeks** | **Fully functional v1.0.0 release** |

---

## Next Steps

1. **Review this plan** - Provide feedback on priorities, scope, or technical choices
2. **Phase 1 kickoff** - Begin with project structure and configuration system
3. **Iterative development** - Build, test, and refine each phase
4. **Regular checkpoints** - Review progress and adjust plan as needed
5. **Community feedback** - Engage early adopters for testing and suggestions

---

**Notes for AI Coding Agents**: This project requires careful attention to security, especially around Docker command execution and SSH key management. All file operations should be atomic and logged. The Swarm proxy architecture is the most complex component—take time to design it properly before implementation. Prioritize user experience and clear documentation throughout.

**Project Vision**: Create a robust, secure, and user-friendly solution that the open-source community can adopt, extend, and improve. Make it accessible to non-technical users while providing power features for advanced deployments.

---

*Generated by GitHub Copilot based on project requirements and best practices for Docker-based orchestration services.*
