"""
Unit Tests for Configuration Module

Tests configuration loading, validation, environment variable merging,
and error handling.

Author: Next_Prism Project
License: MIT
"""

import os
import tempfile
import pytest
from pathlib import Path

from src.config.config_loader import ConfigLoader, load_config
from src.config.schema import Config, NextcloudConfig, PhotoPrismConfig


class TestConfigLoader:
    """Test suite for ConfigLoader class."""
    
    def test_create_default_config(self):
        """Test default configuration creation."""
        loader = ConfigLoader()
        default_config = loader._create_default_config()
        
        assert "app" in default_config
        assert "nextcloud" in default_config
        assert "photoprism" in default_config
        assert default_config["app"]["port"] == 8080
        assert default_config["app"]["log_level"] == "INFO"
    
    def test_load_nonexistent_config_creates_default(self, tmp_path):
        """Test that loading non-existent config creates defaults."""
        config_path = tmp_path / "config.yaml"
        loader = ConfigLoader(str(config_path))
        
        config = loader.load()
        
        assert isinstance(config, Config)
        assert config.app.port == 8080
        assert config.nextcloud.container_name == "nextcloud"
    
    def test_config_validation(self):
        """Test that Config validates required fields."""
        # Valid config
        config_data = {
            "nextcloud": {
                "data_path": "/var/lib/nextcloud/data",
                "container_name": "nextcloud"
            },
            "photoprism": {
                "import_path": "/mnt/import",
                "albums_path": "/mnt/albums"
            }
        }
        
        config = Config(**config_data)
        assert config.nextcloud.data_path == "/var/lib/nextcloud/data"
    
    def test_invalid_path_raises_error(self):
        """Test that relative paths are rejected."""
        with pytest.raises(ValueError):
            NextcloudConfig(data_path="relative/path")
    
    def test_env_var_override(self, tmp_path, monkeypatch):
        """Test environment variable overrides."""
        # Set environment variables
        monkeypatch.setenv("APP_PORT", "9090")
        monkeypatch.setenv("APP_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("NEXTCLOUD_CONTAINER_NAME", "my-nextcloud")
        
        config_path = tmp_path / "config.yaml"
        loader = ConfigLoader(str(config_path))
        config = loader.load()
        
        assert config.app.port == 9090
        assert config.app.log_level == "DEBUG"
        assert config.nextcloud.container_name == "my-nextcloud"
    
    def test_additional_folders_from_env(self, tmp_path, monkeypatch):
        """Test adding folders via environment variable."""
        monkeypatch.setenv("ADDITIONAL_FOLDERS", "/mnt/folder1,/mnt/folder2")
        
        config_path = tmp_path / "config.yaml"
        loader = ConfigLoader(str(config_path))
        config = loader.load()
        
        # Should have at least the custom folders
        custom_folders = [f for f in config.folders if f.type == "custom"]
        assert len(custom_folders) >= 2
        folder_paths = [f.path for f in custom_folders]
        assert "/mnt/folder1" in folder_paths
        assert "/mnt/folder2" in folder_paths
    
    def test_jwt_secret_generation(self, tmp_path):
        """Test that JWT secret is auto-generated."""
        config_path = tmp_path / "config.yaml"
        loader = ConfigLoader(str(config_path))
        config = loader.load()
        
        assert config.security.jwt_secret is not None
        assert len(config.security.jwt_secret) > 20
    
    def test_unique_folder_paths_validation(self):
        """Test that duplicate folder paths are rejected."""
        config_data = {
            "folders": [
                {"path": "/mnt/photos", "type": "custom"},
                {"path": "/mnt/photos", "type": "custom"}
            ]
        }
        
        with pytest.raises(ValueError, match="Duplicate folder paths"):
            Config(**config_data)


class TestConfigSchema:
    """Test suite for configuration schema models."""
    
    def test_nextcloud_config_defaults(self):
        """Test NextcloudConfig default values."""
        config = NextcloudConfig()
        
        assert config.data_path == "/var/lib/nextcloud/data"
        assert config.container_name == "nextcloud"
        assert config.auto_detect_users is True
        assert config.users == {"include": [], "exclude": []}
    
    def test_photoprism_config_defaults(self):
        """Test PhotoPrismConfig default values."""
        config = PhotoPrismConfig()
        
        assert config.import_path == "/mnt/photoprism-import"
        assert config.albums_path == "/mnt/photoprism-albums"
        assert config.container_name == "photoprism"
    
    def test_extension_normalization(self):
        """Test that file extensions are normalized."""
        from src.config.schema import MonitoredFolder
        
        folder = MonitoredFolder(
            path="/mnt/photos",
            extensions=[".JPG", "PNG", ".HEIC"]
        )
        
        assert folder.extensions == ["jpg", "png", "heic"]
    
    def test_notification_level_enum(self):
        """Test NotificationLevel enum values."""
        from src.config.schema import NotificationLevel
        
        assert NotificationLevel.CRITICAL == "critical"
        assert NotificationLevel.ERROR == "error"
        assert NotificationLevel.INFO == "info"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
