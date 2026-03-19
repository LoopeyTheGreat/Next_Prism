




# Nextcloud SMB/CIFS Integration Docker Container - AI Coding Assistant Instructions

This Docker container is designed to integrate Nextcloud with SMB/CIFS file sharing capabilities using smbclient support. The project includes custom configurations for SMB external storage, PHP extensions, and optimized performance settings for Nextcloud instances in containerized environments.

Project Goals:

    Provide Nextcloud instance with built-in SMB/CIFS support
    Enable seamless integration with Windows file shares and NAS devices
    Optimize container performance for photo storage and file management (PhotoPrism integration compatible)
    Maintain security best practices for containerized deployments

Target Audience:

    Self-hosted users deploying Nextcloud in Docker/Kubernetes environments
    Users requiring SMB/CIFS external storage support
    Home lab and small business deployments with network file shares

Development Context
Repository Structure
Code

photoprism-nextcloud-sync-guide.md  # Workflow documentation for photo management
apps/                               # Example Nextcloud application configurations
docker-compose files/               # Reference deployment configurations
terraform/                          # Infrastructure as code examples (if present)
_AI_Notes/                         # Internal development notes for AI agents
README.md                          # User-facing documentation

Key Technologies

    Container Base: Alpine Linux / Debian-based Nextcloud images
    Core Technologies: PHP 8.x+, Nextcloud latest stable, libsmbclient
    Dependencies:
        PHP modules: smbclient, imagick, opcache, APCu
        System packages: samba-client, cifs-utils
        Database support: PostgreSQL, MariaDB, SQLite
    Orchestration: Docker Compose, Docker Swarm (dual configuration)
    Integration Tools: Nextcloud occ commands, cron jobs, memory indexing

Current Features

    SMB/CIFS external storage support via PHP smbclient extension
    Optimized PHP configuration for file uploads and memory handling
    Integration with PhotoPrism for photo management workflows
    Configurable user selection and folder monitoring
    Ntfy notification support for workflow events
    Web UI for configuration management (planned feature)

Code Generation Guidelines
General Principles

    Security First: Never expose credentials in plaintext, use Docker secrets or bind-mounted config files
    Documentation Quality: Provide inline comments explaining WHY code exists, not just what it does
    User Experience: Design for non-technical users deploying via CasaOS or Portainer
    Compatibility: Support both Docker Swarm and standard Docker Compose deployments

Docker Best Practices
Dockerfile

# Use multi-stage builds when appropriate
# Pin versions for reproducibility
# Example:
FROM nextcloud:29.0-apache as base
RUN apt-get update && apt-get install -y \
    libsmbclient-dev \
    smbclient \
 && docker-php-ext-install smbclient \
 && rm -rf /var/lib/apt/lists/*

Configuration Management

    Store all configuration in /config bind mount
    Use environment variables for dynamic configuration
    Provide sensible defaults with override capability
    Example env vars: NEXTCLOUD_TRUSTED_DOMAINS, SMB_HOST, SMB_SHARE

Python Code Style (for orchestration scripts)
Python

import os
from pathlib import Path

def scan_nextcloud_users(data_path: Path) -> list[str]:
    """
    Scan Nextcloud data directory for user folders.
    
    Args:
        data_path: Path to Nextcloud data directory
        
    Returns:
        List of discovered username strings
        
    Raises:
        PermissionError: If data directory is not accessible
    """
    # Implementation with error handling

Bash Scripting Standards (for entrypoint/init scripts)
bash

#!/usr/bin/env bash
set -euo pipefail

# Always include error handling
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Use functions for complex logic
configure_smb_client() {
    local config_file="/etc/samba/smb.conf"
    
    # Check prerequisites
    if [[ ! -f "$config_file" ]]; then
        echo "ERROR: SMB config not found" >&2
        return 1
    fi
    
    # Implementation
}

Documentation Requirements
Code Comments

    Function/Class Headers: Purpose, parameters, return values, potential exceptions
    Complex Logic: Explain the business logic, not obvious syntax
    Security Considerations: Flag any security-critical sections

README Sections Required

    Features: Clear bullet list of capabilities
    Prerequisites: System requirements, dependencies
    Quick Start: Copy-paste example with minimal configuration
    Configuration Reference: All environment variables and bind mounts
    Troubleshooting: Common issues and solutions
    Integration Examples: PhotoPrism sync workflow, calendar sync, etc.

_AI_NOTES Format

Keep internal development notes in _AI_Notes/ directory:
Code

_AI_NOTES/
+-- architecture-decisions.md    # Why we chose specific approaches
+-- known-issues.md              # Current limitations and workarounds
+-- testing-protocols.md         # How to validate changes
+-- roadmap.md                   # Planned features and improvements

Integration Context
PhotoPrism Workflow

From photoprism-nextcloud-sync-guide.md, the system should support:

    Monitoring Nextcloud user upload folders
    Moving new photos to PhotoPrism import directory
    Triggering occ files:scan after file operations
    Running occ memories:index for gallery updates
    Sending notifications via ntfy for workflow events

Web UI Requirements

When implementing the planned web UI:

    Framework: Lightweight options (Flask, FastAPI, Express.js)
    Authentication: Optional password protection + IP whitelist
    Features:
        User selection checkboxes
        Schedule configuration (cron-style)
        Manual trigger buttons
        Live log streaming
        Configuration file editor (with validation)

Testing Expectations
Unit Tests

    Test file operations with mock filesystem
    Validate configuration parsing and defaults
    Test error handling for common failure modes

Integration Tests
Python

def test_nextcloud_occ_scan():
    """Verify occ files:scan triggers correctly after file move."""
    # Setup test environment
    # Execute file move
    # Assert occ command was called with correct parameters
    # Verify Nextcloud database updated

Container Tests

    Build succeeds with both Docker and Docker Swarm configs
    Container starts without errors
    Health check endpoint responds
    SMB mount works with test credentials

Security Considerations
Credential Handling
YAML

# docker-compose.yml - GOOD
services:
  nextcloud:
    secrets:
      - smb_password
      - nextcloud_admin_password
    environment:
      SMB_USER: ${SMB_USER}  # Reference external env file

secrets:
  smb_password:
    file: ./secrets/smb_pass.txt

Network Isolation

    Use Docker networks to isolate services
    Only expose necessary ports
    Document firewall requirements

File Permissions

    Run container as non-root user when possible
    Set appropriate umask for created files
    Document required host directory permissions

Performance Optimization
PHP Configuration Targets
INI

; /usr/local/etc/php/conf.d/nextcloud.ini
upload_max_filesize = 10G
post_max_size = 10G
memory_limit = 512M
max_execution_time = 3600

; OPcache settings
opcache.enable = 1
opcache.interned_strings_buffer = 32
opcache.max_accelerated_files = 10000
opcache.memory_consumption = 256

Database Tuning

    Recommend PostgreSQL over SQLite for production
    Document optimal connection pool settings
    Suggest database maintenance cron jobs

Common Pitfalls to Avoid

    Do not hardcode file paths - use environment variables
    Do not assume directory structure - validate paths exist
    Do not skip error handling for network operations (SMB can be flaky)
    Do not forget to clean up temporary files in long-running containers
    Do not expose Docker socket without strict security controls

Useful Resources

    Nextcloud External Storage Configuration
    PhotoPrism Import Folder Documentation
    Docker Security Best Practices
    Samba/CIFS Mount Options

Example Code Generation Prompt

When generating code, prefer this style:

Prompt: "Create a Python script to monitor Nextcloud user folders for new photos and copy them to PhotoPrism import directory."

Good Output:
Python

#!/usr/bin/env python3
"""
Nextcloud to PhotoPrism Photo Sync Service

Monitors specified Nextcloud user directories for new photo uploads,
copies them to PhotoPrism import folder, and triggers Nextcloud reindexing.

Environment Variables:
    NEXTCLOUD_DATA_DIR: Path to Nextcloud data directory
    PHOTOPRISM_IMPORT_DIR: Path to PhotoPrism import directory
    WATCHED_USERS: Comma-separated list of Nextcloud usernames to monitor
    NTFY_TOPIC: Optional ntfy.sh topic for notifications
"""

import os
import shutil
import logging
from pathlib import Path
from typing import List
import subprocess

# Configure logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PhotoSyncService:
    """Handles syncing photos from Nextcloud to PhotoPrism."""
    
    PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.heic', '.raw'}
    
    def __init__(self):
        self.nextcloud_data = Path(os.getenv('NEXTCLOUD_DATA_DIR', '/var/www/html/data'))
        self.photoprism_import = Path(os.getenv('PHOTOPRISM_IMPORT_DIR', '/photoprism/import'))
        self.watched_users = os.getenv('WATCHED_USERS', '').split(',')
        self.ntfy_topic = os.getenv('NTFY_TOPIC')
        
        # Validate paths exist
        if not self.nextcloud_data.exists():
            raise ValueError(f"Nextcloud data directory not found: {self.nextcloud_data}")
        if not self.photoprism_import.exists():
            raise ValueError(f"PhotoPrism import directory not found: {self.photoprism_import}")
    
    def trigger_nextcloud_scan(self, user: str) -> None:
        """
        Trigger Nextcloud files:scan for specific user.
        
        Args:
            user: Nextcloud username to scan
            
        Raises:
            subprocess.CalledProcessError: If occ command fails
        """
        try:
            subprocess.run(
                ['docker', 'exec', 'nextcloud', 'occ', 'files:scan', '--path', f'/{user}/files'],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Successfully scanned Nextcloud files for user: {user}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to scan Nextcloud files: {e.stderr}")
            raise
    
    # ... rest of implementation with similar documentation quality

Questions to Ask Before Coding

When given a task, consider asking:

    Deployment Context: "Will this run in Docker Swarm or standard Docker Compose?"
    User Interaction: "Should this be configured via environment variables, config file, or web UI?"
    Error Handling: "What should happen if SMB mount fails? Retry logic needed?"
    Logging: "Should this log to stdout/stderr, syslog, or file?"
    Permissions: "What user should this process run as? Root necessary?"

Related Documentation Links

    Main project README: README.md
    Photo sync workflow: photoprism-nextcloud-sync-guide.md
    Docker Compose example: docker-compose.yaml
    Docker Swarm config: swarm-config.yaml
    Development notes: _AI_Notes/

Last Updated: Based on photoprism-nextcloud-sync-guide.md content Maintained By: Project contributors and AI coding assistants
Code


This instruction file provides comprehensive guidance for GitHub Copilot and other AI coding assistants working on the Nextcloud/SMB/PhotoPrism integration project. Key features:

1. **Context-Rich**: Explains project goals, architecture, and integration workflows
2. **Code Quality Standards**: Examples of proper documentation, error handling, and security practices
3. **Technology Specific**: Covers Docker, Python, Bash, PHP, and infrastructure patterns
4. **Security Focused**: Emphasizes secrets management and container security
5. **User-Centric**: Reminds AI to design for non-technical self-hosters
6. **Comprehensive Documentation**: Requires both user-facing docs and internal AI notes

The file references real components from the provided guide while adding professional software development standards appropriate for an open-source, security-conscious containerized application.
