"""
Configuration Loader

Handles loading, parsing, and merging configuration from YAML files,
environment variables, and provides hot-reloading capabilities.

Author: Next_Prism Project
License: MIT
"""

import os
import yaml
import secrets
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from .schema import Config, MonitoredFolder, FolderType


class ConfigLoader:
    """
    Configuration loader and manager.
    
    Loads configuration from YAML file, merges with environment variables,
    validates the structure, and provides hot-reload capabilities.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration loader.
        
        Args:
            config_path: Path to the configuration file. If None, uses default location.
        """
        self.config_path = config_path or os.getenv(
            "CONFIG_PATH", 
            "/app/config/config.yaml"
        )
        self._config: Optional[Config] = None
        
        # Load environment variables from .env if present
        load_dotenv()
    
    def load(self) -> Config:
        """
        Load and validate configuration.
        
        Returns:
            Validated Config object
            
        Raises:
            FileNotFoundError: If config file doesn't exist and can't be created
            yaml.YAMLError: If YAML parsing fails
            ValueError: If configuration validation fails
        """
        config_data = self._load_yaml()
        config_data = self._merge_env_vars(config_data)
        config_data = self._apply_defaults(config_data)
        
        # Validate and create Config object
        self._config = Config(**config_data)
        
        # Generate JWT secret if not set
        if self._config.security.jwt_secret is None:
            self._config.security.jwt_secret = secrets.token_urlsafe(32)
        
        return self._config
    
    def _load_yaml(self) -> Dict[str, Any]:
        """
        Load YAML configuration file.
        
        Returns:
            Dictionary with configuration data
        """
        config_file = Path(self.config_path)
        
        # If config doesn't exist, create default
        if not config_file.exists():
            return self._create_default_config()
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            return data
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML config: {e}")
    
    def _create_default_config(self) -> Dict[str, Any]:
        """
        Create default configuration structure.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "app": {
                "host": "0.0.0.0",
                "port": 8080,
                "log_level": "INFO"
            },
            "nextcloud": {
                "data_path": "/var/lib/nextcloud/data",
                "container_name": "nextcloud",
                "users": {
                    "include": [],
                    "exclude": []
                },
                "auto_detect_users": True
            },
            "photoprism": {
                "import_path": "/mnt/photoprism-import",
                "albums_path": "/mnt/photoprism-albums",
                "container_name": "photoprism"
            },
            "folders": [],
            "scheduling": {
                "default_schedule": "*/15 * * * *",
                "max_concurrent_tasks": 3,
                "task_timeout": 3600,
                "retry_attempts": 3,
                "retry_delay": 300
            },
            "notifications": {
                "enabled": False,
                "server": "https://ntfy.sh",
                "topic": "next-prism-alerts",
                "level": "error"
            },
            "security": {
                "password_enabled": False,
                "ip_whitelist_enabled": False,
                "ip_whitelist": [],
                "session_timeout": 3600
            },
            "docker": {
                "swarm_mode": None,
                "nextcloud_proxy_service": "nextcloud-proxy",
                "photoprism_proxy_service": "photoprism-proxy",
                "proxy_ssh_port": 2222,
                "docker_socket": "/var/run/docker.sock"
            }
        }
    
    def _merge_env_vars(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge environment variables into configuration.
        
        Environment variables override config file values.
        Naming convention: SECTION_KEY (e.g., APP_PORT, NEXTCLOUD_CONTAINER_NAME)
        
        Args:
            config_data: Configuration dictionary from file
            
        Returns:
            Merged configuration dictionary
        """
        # App settings
        if os.getenv("APP_HOST"):
            config_data.setdefault("app", {})["host"] = os.getenv("APP_HOST")
        if os.getenv("APP_PORT"):
            config_data.setdefault("app", {})["port"] = int(os.getenv("APP_PORT"))
        if os.getenv("APP_LOG_LEVEL"):
            config_data.setdefault("app", {})["log_level"] = os.getenv("APP_LOG_LEVEL")
        
        # Nextcloud settings
        if os.getenv("NEXTCLOUD_DATA_PATH"):
            config_data.setdefault("nextcloud", {})["data_path"] = os.getenv("NEXTCLOUD_DATA_PATH")
        if os.getenv("NEXTCLOUD_CONTAINER_NAME"):
            config_data.setdefault("nextcloud", {})["container_name"] = os.getenv("NEXTCLOUD_CONTAINER_NAME")
        
        # PhotoPrism settings
        if os.getenv("PHOTOPRISM_IMPORT_PATH"):
            config_data.setdefault("photoprism", {})["import_path"] = os.getenv("PHOTOPRISM_IMPORT_PATH")
        if os.getenv("PHOTOPRISM_ALBUMS_PATH"):
            config_data.setdefault("photoprism", {})["albums_path"] = os.getenv("PHOTOPRISM_ALBUMS_PATH")
        if os.getenv("PHOTOPRISM_CONTAINER_NAME"):
            config_data.setdefault("photoprism", {})["container_name"] = os.getenv("PHOTOPRISM_CONTAINER_NAME")
        
        # Additional folders from env (comma-separated)
        if os.getenv("ADDITIONAL_FOLDERS"):
            folders = config_data.setdefault("folders", [])
            for folder_path in os.getenv("ADDITIONAL_FOLDERS").split(","):
                folder_path = folder_path.strip()
                if folder_path and not any(f.get("path") == folder_path for f in folders):
                    folders.append({
                        "path": folder_path,
                        "type": "custom",
                        "enabled": True
                    })
        
        # Notifications
        if os.getenv("NTFY_ENABLED"):
            config_data.setdefault("notifications", {})["enabled"] = os.getenv("NTFY_ENABLED").lower() == "true"
        if os.getenv("NTFY_SERVER"):
            config_data.setdefault("notifications", {})["server"] = os.getenv("NTFY_SERVER")
        if os.getenv("NTFY_TOPIC"):
            config_data.setdefault("notifications", {})["topic"] = os.getenv("NTFY_TOPIC")
        if os.getenv("NTFY_LEVEL"):
            config_data.setdefault("notifications", {})["level"] = os.getenv("NTFY_LEVEL")
        
        # Security
        if os.getenv("WEB_PASSWORD"):
            import bcrypt
            config_data.setdefault("security", {})["password_enabled"] = True
            config_data["security"]["password_hash"] = bcrypt.hashpw(
                os.getenv("WEB_PASSWORD").encode('utf-8'),
                bcrypt.gensalt()
            ).decode('utf-8')
        if os.getenv("IP_WHITELIST"):
            config_data.setdefault("security", {})["ip_whitelist_enabled"] = True
            config_data["security"]["ip_whitelist"] = [
                ip.strip() for ip in os.getenv("IP_WHITELIST").split(",")
            ]
        
        # Docker/Swarm
        if os.getenv("SWARM_MODE"):
            config_data.setdefault("docker", {})["swarm_mode"] = os.getenv("SWARM_MODE").lower() == "true"
        
        return config_data
    
    def _apply_defaults(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply intelligent defaults based on configuration.
        
        Args:
            config_data: Configuration dictionary
            
        Returns:
            Configuration with defaults applied
        """
        # Auto-add Nextcloud users folder if enabled
        if config_data.get("nextcloud", {}).get("auto_detect_users", True):
            nextcloud_data = config_data.get("nextcloud", {}).get("data_path")
            if nextcloud_data:
                folders = config_data.setdefault("folders", [])
                # Check if nextcloud_users folder already exists
                if not any(f.get("type") == "nextcloud_users" for f in folders):
                    folders.insert(0, {
                        "path": nextcloud_data,
                        "type": "nextcloud_users",
                        "enabled": True
                    })
        
        return config_data
    
    def save(self, config: Config, path: Optional[str] = None) -> None:
        """
        Save configuration to YAML file.
        
        Args:
            config: Config object to save
            path: Path to save to (uses default if None)
        """
        save_path = Path(path or self.config_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert Config to dict
        config_dict = config.dict()
        
        # Remove runtime-generated values
        if config_dict.get("security", {}).get("jwt_secret"):
            config_dict["security"]["jwt_secret"] = None
        
        with open(save_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(config_dict, f, default_flow_style=False, sort_keys=False)
    
    def reload(self) -> Config:
        """
        Reload configuration from file.
        
        Returns:
            Reloaded Config object
        """
        return self.load()
    
    @property
    def config(self) -> Optional[Config]:
        """Get the current configuration object."""
        return self._config


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Convenience function to load configuration.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        Loaded and validated Config object
    """
    loader = ConfigLoader(config_path)
    return loader.load()
