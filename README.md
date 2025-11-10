# Next_Prism

**Nextcloud-to-PhotoPrism Sync Orchestrator**

A robust, secure Docker-based service that automatically synchronizes photos from Nextcloud user directories to PhotoPrism's import system, with intelligent deduplication, flexible scheduling, and comprehensive monitoring.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)

---

## 🚀 Features

- **Automatic Photo Synchronization**: Monitor multiple Nextcloud user directories and custom folders
- **Intelligent Deduplication**: Hash-based duplicate detection prevents redundant imports
- **PhotoPrism Integration**: Seamlessly move photos to PhotoPrism import folder with automatic indexing
- **Flexible Scheduling**: Per-folder custom schedules or use default intervals
- **User Selection**: Choose which Nextcloud users to monitor
- **Archive Option**: Optionally archive moved files instead of deletion
- **Secure Web UI**: Password-protected dashboard with IP whitelisting
- **Notifications**: ntfy.sh integration with configurable severity levels
- **Docker & Swarm Support**: Single application works in both standard Docker and Docker Swarm environments
- **Comprehensive Logging**: Detailed logs with web-based viewer and filtering

---

## 📋 Prerequisites

- Docker 20.10+ or Docker Swarm
- Nextcloud instance (running in Docker)
- PhotoPrism instance (running in Docker)
- Python 3.11+ (for local development only)

---

## 🏃 Quick Start

### Standard Docker

```bash
# Clone the repository
git clone git@github.com:LoopeyTheGreat/Next_Prism.git
cd Next_Prism

# Copy and configure environment file
cp .env.example .env
nano .env

# Start the service
docker-compose up -d

# Access the web UI
open http://localhost:8080
```

### Docker Swarm

```bash
# Generate SSH keypairs for proxy services
./scripts/generate_keys.sh

# Deploy proxy services (if using Swarm)
docker stack deploy -c compose/nextcloud-proxy.yaml nextcloud-proxy
docker stack deploy -c compose/photoprism-proxy.yaml photoprism-proxy

# Deploy main application
docker stack deploy -c compose/swarm-stack.yaml next-prism
```

📖 **Full installation guide**: [INSTALLATION.md](docs/INSTALLATION.md)

---

## 🔧 Configuration

Configuration is managed via `config/config.yaml` (auto-generated on first run) or through the web UI.

Example configuration:

```yaml
nextcloud:
  data_path: /var/lib/nextcloud/data
  container_name: nextcloud
  users:
    include: ["user1", "user2"]
    exclude: []

photoprism:
  import_path: /mnt/photoprism-import
  albums_path: /mnt/photoprism-albums
  container_name: photoprism

folders:
  - path: /mnt/nextcloud-data
    type: nextcloud_users
    schedule: "*/15 * * * *"  # Every 15 minutes
  - path: /mnt/other-photos
    type: custom
    schedule: "0 2 * * *"  # Daily at 2 AM

notifications:
  ntfy:
    enabled: true
    server: https://ntfy.sh
    topic: next-prism-alerts
    level: error  # critical, error, warning, info

security:
  password_enabled: true
  ip_whitelist: ["192.168.1.0/24"]
```

📖 **Full configuration guide**: [CONFIGURATION.md](docs/CONFIGURATION.md)

---

## 🏗️ Architecture

```
┌─────────────────┐       ┌──────────────────┐       ┌─────────────────┐
│   Nextcloud     │       │   Next_Prism     │       │   PhotoPrism    │
│   (Users)       │──────▶│   Orchestrator   │──────▶│   (Import)      │
└─────────────────┘       └──────────────────┘       └─────────────────┘
                                   │
                                   ├─▶ Web UI (Port 8080)
                                   ├─▶ ntfy Notifications
                                   └─▶ Logs & Monitoring
```

**Key Components:**
- **File Monitoring Service**: Watches for new photos
- **Sync Engine**: Deduplicates and moves files
- **Scheduler**: Manages per-folder sync intervals
- **Docker Interface**: Executes indexing commands
- **Web UI**: Configuration and monitoring dashboard
- **Swarm Proxies**: Secure command execution in Swarm mode

---

## 📸 Screenshots

*(Coming soon - web UI screenshots)*

---

## 🐳 Docker Swarm Proxy Architecture

For Docker Swarm deployments, Next_Prism uses lightweight proxy containers to securely execute commands on Nextcloud and PhotoPrism services:

- **SSH-based authentication** with ED25519 keypairs
- **Command whitelisting** for security
- **Automatic service discovery** via Docker DNS
- **Fallback to direct exec** when proxies unavailable

📖 **Swarm setup guide**: [SWARM_SETUP.md](docs/SWARM_SETUP.md)

---

## 🔒 Security

- **Non-root container execution**
- **Optional password protection** (bcrypt hashing)
- **IP/subnet whitelisting**
- **SSH keypair authentication** for Swarm proxies
- **Command sanitization** and whitelisting
- **Secure secret management** via Docker secrets
- **HTTPS support** via reverse proxy

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built for the Nextcloud and PhotoPrism communities
- Inspired by the need for seamless photo management workflows
- Thanks to all contributors and testers

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/LoopeyTheGreat/Next_Prism/issues)
- **Discussions**: [GitHub Discussions](https://github.com/LoopeyTheGreat/Next_Prism/discussions)
- **Documentation**: [docs/](docs/)

---

## 🗺️ Roadmap

- [x] Core sync engine
- [x] Web UI with scheduling
- [x] Docker Swarm support
- [ ] v1.0.0 Release (Q1 2026)
- [ ] Face recognition integration
- [ ] Multi-PhotoPrism support
- [ ] S3/object storage support
- [ ] Mobile monitoring app

---

**Status**: 🚧 In Active Development

*This project is currently in the initial development phase. Follow the repository for updates!*
