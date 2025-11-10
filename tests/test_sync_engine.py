"""
Unit Tests for Sync Engine

Tests sync engine functionality including deduplication, file moves,
and indexing triggers.

Author: Next_Prism Project
License: MIT
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from src.core.sync_engine import (
    SyncEngine,
    DeduplicationCache,
    SyncStatus,
    SyncResult
)
from src.config.schema import MonitoredFolder, FolderType


class TestDeduplicationCache:
    """Test suite for deduplication cache."""
    
    def test_cache_initialization(self):
        """Test cache initializes empty."""
        cache = DeduplicationCache()
        
        assert cache.hash_cache == {}
        assert cache._loaded is False
    
    def test_add_and_check_duplicate(self):
        """Test adding files and checking for duplicates."""
        cache = DeduplicationCache()
        
        # Add a file
        cache.add_file("/path/to/file1.jpg", "abc123")
        
        # Check duplicate
        is_dup, existing = cache.is_duplicate("abc123")
        assert is_dup is True
        assert existing == "/path/to/file1.jpg"
        
        # Check non-duplicate
        is_dup, existing = cache.is_duplicate("xyz789")
        assert is_dup is False
        assert existing is None
    
    def test_load_destination(self, tmp_path):
        """Test loading hashes from destination directory."""
        cache = DeduplicationCache()
        
        # Create test files
        dest_dir = tmp_path / "destination"
        dest_dir.mkdir()
        
        (dest_dir / "file1.jpg").write_text("content1")
        (dest_dir / "file2.jpg").write_text("content2")
        
        # Load destination
        cache.load_destination(str(dest_dir))
        
        assert cache._loaded is True
        assert len(cache.hash_cache) == 2


class TestSyncEngine:
    """Test suite for sync engine."""
    
    @pytest.fixture
    def mock_executor(self):
        """Create mock Docker executor."""
        executor = Mock()
        executor.container_exists = Mock(return_value=True)
        return executor
    
    @pytest.fixture
    def sync_engine(self, mock_executor, tmp_path):
        """Create sync engine with mocked components."""
        import_path = tmp_path / "import"
        albums_path = tmp_path / "albums"
        import_path.mkdir()
        albums_path.mkdir()
        
        engine = SyncEngine(
            docker_executor=mock_executor,
            nextcloud_container="nextcloud",
            photoprism_container="photoprism",
            photoprism_import_path=str(import_path),
            photoprism_albums_path=str(albums_path)
        )
        
        return engine
    
    def test_engine_initialization(self, sync_engine):
        """Test sync engine initializes correctly."""
        assert sync_engine.stats["files_processed"] == 0
        assert sync_engine.stats["files_moved"] == 0
        assert sync_engine.stats["duplicates_skipped"] == 0
    
    def test_sync_file_success(self, sync_engine, tmp_path):
        """Test successful file sync."""
        # Create source file
        source = tmp_path / "source.jpg"
        source.write_text("test photo content")
        
        # Create folder config
        folder_config = MonitoredFolder(
            path=str(tmp_path),
            type=FolderType.CUSTOM,
            archive_moved=False
        )
        
        # Sync file
        result = sync_engine.sync_file(
            file_path=str(source),
            folder_config=folder_config,
            skip_dedupe=True
        )
        
        assert result.status == SyncStatus.COMPLETED
        assert result.destination_path is not None
        assert result.file_hash is not None
    
    def test_sync_file_duplicate_detection(self, sync_engine, tmp_path):
        """Test duplicate detection during sync."""
        # Create two identical files
        source1 = tmp_path / "source1.jpg"
        source1.write_text("identical content")
        
        source2 = tmp_path / "source2.jpg"
        source2.write_text("identical content")
        
        folder_config = MonitoredFolder(
            path=str(tmp_path),
            type=FolderType.CUSTOM,
            archive_moved=False
        )
        
        # Sync first file
        result1 = sync_engine.sync_file(
            file_path=str(source1),
            folder_config=folder_config,
            skip_dedupe=False
        )
        
        assert result1.status == SyncStatus.COMPLETED
        
        # Sync second file (should be duplicate)
        result2 = sync_engine.sync_file(
            file_path=str(source2),
            folder_config=folder_config,
            skip_dedupe=False
        )
        
        assert result2.status == SyncStatus.SKIPPED_DUPLICATE
        assert result2.is_duplicate is True
        assert sync_engine.stats["duplicates_skipped"] == 1
    
    def test_sync_nonexistent_file(self, sync_engine, tmp_path):
        """Test syncing non-existent file fails gracefully."""
        folder_config = MonitoredFolder(
            path=str(tmp_path),
            type=FolderType.CUSTOM
        )
        
        result = sync_engine.sync_file(
            file_path="/nonexistent/file.jpg",
            folder_config=folder_config
        )
        
        assert result.status == SyncStatus.FAILED
        assert "not found" in result.error_message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
