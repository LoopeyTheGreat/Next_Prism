"""
Configuration Schema and Models

Defines Pydantic models for the configuration schema, providing validation,
default values, and type checking for all configuration options.

Author: Next_Prism Project
License: MIT
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator, HttpUrl
from pathlib import Path


class LogLevel(str, Enum):
    """Logging level options."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class NotificationLevel(str, Enum):
    """Notification severity levels."""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


class FolderType(str, Enum):
    """Types of folders that can be monitored."""
    NEXTCLOUD_USERS = "nextcloud_users"
    CUSTOM = "custom"


class NextcloudConfig(BaseModel):
    """Nextcloud-specific configuration."""
    
    data_path: str = Field(
        default="/var/lib/nextcloud/data",
        description="Path to Nextcloud data directory"
    )
    container_name: str = Field(
        default="nextcloud",
        description="Name or ID of Nextcloud Docker container"
    )
    users: Dict[str, List[str]] = Field(
        default={"include": [], "exclude": []},
        description="User inclusion/exclusion lists"
    )
    auto_detect_users: bool = Field(
        default=True,
        description="Automatically detect new Nextcloud users"
    )
    
    @validator("data_path")
    def validate_data_path(cls, v):
        """Ensure data path is absolute."""
        if not Path(v).is_absolute():
            raise ValueError(f"Nextcloud data_path must be absolute: {v}")
        return v


class PhotoPrismConfig(BaseModel):
    """PhotoPrism-specific configuration."""
    
    import_path: str = Field(
        default="/mnt/photoprism-import",
        description="Path to PhotoPrism import directory"
    )
    albums_path: str = Field(
        default="/mnt/photoprism-albums",
        description="Path to PhotoPrism organized albums directory"
    )
    container_name: str = Field(
        default="photoprism",
        description="Name or ID of PhotoPrism Docker container"
    )
    
    @validator("import_path", "albums_path")
    def validate_paths(cls, v):
        """Ensure paths are absolute."""
        if not Path(v).is_absolute():
            raise ValueError(f"PhotoPrism path must be absolute: {v}")
        return v


class MonitoredFolder(BaseModel):
    """Configuration for a monitored folder."""
    
    path: str = Field(
        description="Absolute path to the folder to monitor"
    )
    type: FolderType = Field(
        default=FolderType.CUSTOM,
        description="Type of folder (nextcloud_users or custom)"
    )
    enabled: bool = Field(
        default=True,
        description="Whether monitoring is enabled for this folder"
    )
    schedule: Optional[str] = Field(
        default=None,
        description="Cron expression for custom schedule (None uses default)"
    )
    archive_moved: bool = Field(
        default=True,
        description="Archive moved files instead of deleting them"
    )
    archive_path: Optional[str] = Field(
        default=None,
        description="Custom archive path (if None, uses folder/.archive)"
    )
    extensions: List[str] = Field(
        default=["jpg", "jpeg", "png", "gif", "heic", "heif", "raw", "cr2", "nef", "arw", "dng"],
        description="File extensions to monitor (lowercase, without dots)"
    )
    
    @validator("path")
    def validate_path(cls, v):
        """Ensure path is absolute."""
        if not Path(v).is_absolute():
            raise ValueError(f"Folder path must be absolute: {v}")
        return v
    
    @validator("extensions", pre=True)
    def normalize_extensions(cls, v):
        """Normalize extensions to lowercase without dots."""
        if isinstance(v, list):
            return [ext.lower().lstrip('.') for ext in v]
        return v


class SchedulingConfig(BaseModel):
    """Task scheduling configuration."""
    
    default_schedule: str = Field(
        default="*/15 * * * *",
        description="Default cron expression (every 15 minutes)"
    )
    max_concurrent_tasks: int = Field(
        default=3,
        description="Maximum number of concurrent sync tasks"
    )
    task_timeout: int = Field(
        default=3600,
        description="Task timeout in seconds (1 hour default)"
    )
    retry_attempts: int = Field(
        default=3,
        description="Number of retry attempts for failed tasks"
    )
    retry_delay: int = Field(
        default=300,
        description="Delay between retries in seconds (5 minutes)"
    )


class NtfyConfig(BaseModel):
    """ntfy.sh notification configuration."""
    
    enabled: bool = Field(
        default=False,
        description="Enable ntfy notifications"
    )
    server: str = Field(
        default="https://ntfy.sh",
        description="ntfy server URL"
    )
    topic: str = Field(
        default="next-prism-alerts",
        description="ntfy topic name"
    )
    level: NotificationLevel = Field(
        default=NotificationLevel.ERROR,
        description="Minimum notification level to send"
    )
    username: Optional[str] = Field(
        default=None,
        description="ntfy authentication username (optional)"
    )
    password: Optional[str] = Field(
        default=None,
        description="ntfy authentication password (optional)"
    )
    rate_limit: int = Field(
        default=10,
        description="Maximum notifications per hour"
    )


class SecurityConfig(BaseModel):
    """Web UI security configuration."""
    
    password_enabled: bool = Field(
        default=False,
        description="Enable password protection for web UI"
    )
    password_hash: Optional[str] = Field(
        default=None,
        description="Bcrypt password hash (set via web UI or generate manually)"
    )
    ip_whitelist_enabled: bool = Field(
        default=False,
        description="Enable IP/subnet whitelist"
    )
    ip_whitelist: List[str] = Field(
        default=[],
        description="List of allowed IP addresses or CIDR subnets"
    )
    session_timeout: int = Field(
        default=3600,
        description="Session timeout in seconds (1 hour)"
    )
    jwt_secret: Optional[str] = Field(
        default=None,
        description="JWT secret for session tokens (auto-generated if not set)"
    )


class DockerConfig(BaseModel):
    """Docker and Swarm configuration."""
    
    swarm_mode: Optional[bool] = Field(
        default=None,
        description="Force Swarm mode on/off (None = auto-detect)"
    )
    nextcloud_proxy_service: str = Field(
        default="nextcloud-proxy",
        description="Nextcloud proxy service name (Swarm only)"
    )
    photoprism_proxy_service: str = Field(
        default="photoprism-proxy",
        description="PhotoPrism proxy service name (Swarm only)"
    )
    proxy_ssh_port: int = Field(
        default=2222,
        description="SSH port for proxy services"
    )
    docker_socket: str = Field(
        default="/var/run/docker.sock",
        description="Path to Docker socket"
    )


class AppConfig(BaseModel):
    """Main application configuration."""
    
    host: str = Field(
        default="0.0.0.0",
        description="Web UI host address"
    )
    port: int = Field(
        default=8080,
        description="Web UI port"
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Application logging level"
    )
    log_to_file: bool = Field(
        default=True,
        description="Enable logging to file"
    )
    log_rotation_size: int = Field(
        default=10485760,  # 10MB
        description="Log file size before rotation (bytes)"
    )
    log_retention_count: int = Field(
        default=5,
        description="Number of rotated log files to keep"
    )
    config_watch: bool = Field(
        default=True,
        description="Watch config file for changes and hot-reload"
    )


class Config(BaseModel):
    """
    Root configuration model for Next_Prism.
    
    This is the main configuration object that contains all settings for the
    application. It's loaded from config.yaml and can be overridden by
    environment variables.
    """
    
    app: AppConfig = Field(default_factory=AppConfig)
    nextcloud: NextcloudConfig = Field(default_factory=NextcloudConfig)
    photoprism: PhotoPrismConfig = Field(default_factory=PhotoPrismConfig)
    folders: List[MonitoredFolder] = Field(
        default=[],
        description="List of folders to monitor"
    )
    scheduling: SchedulingConfig = Field(default_factory=SchedulingConfig)
    notifications: NtfyConfig = Field(default_factory=NtfyConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    docker: DockerConfig = Field(default_factory=DockerConfig)
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True
        
    @validator("folders")
    def validate_unique_paths(cls, v):
        """Ensure no duplicate folder paths."""
        paths = [f.path for f in v]
        if len(paths) != len(set(paths)):
            raise ValueError("Duplicate folder paths detected in configuration")
        return v
