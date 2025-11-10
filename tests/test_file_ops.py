"""
Unit Tests for File Operations

Tests file hashing, moving, archiving, and utility functions.

Author: Next_Prism Project
License: MIT
"""

import os
import tempfile
import pytest
from pathlib import Path

from src.utils.file_ops import (
    calculate_file_hash,
    safe_move_file,
    archive_file,
    is_image_file,
    get_file_size_mb,
    ensure_directory
)


class TestFileHashing:
    """Test suite for file hashing functions."""
    
    def test_calculate_hash_sha256(self, tmp_path):
        """Test SHA256 hash calculation."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")
        
        hash_value = calculate_file_hash(str(test_file), algorithm="sha256")
        
        # SHA256 of "Hello, World!"
        expected = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"
        assert hash_value == expected
    
    def test_calculate_hash_md5(self, tmp_path):
        """Test MD5 hash calculation."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        hash_value = calculate_file_hash(str(test_file), algorithm="md5")
        
        assert len(hash_value) == 32  # MD5 is 32 hex chars
    
    def test_hash_nonexistent_file_raises_error(self):
        """Test that hashing non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            calculate_file_hash("/nonexistent/file.txt")
    
    def test_hash_large_file(self, tmp_path):
        """Test hashing larger files with chunks."""
        test_file = tmp_path / "large.txt"
        
        # Create a 1MB file
        with open(test_file, 'wb') as f:
            f.write(b'A' * (1024 * 1024))
        
        hash_value = calculate_file_hash(str(test_file))
        assert len(hash_value) == 64  # SHA256 is 64 hex chars


class TestSafeMoveFile:
    """Test suite for safe file moving."""
    
    def test_successful_move(self, tmp_path):
        """Test successful file move."""
        source = tmp_path / "source.txt"
        source.write_text("test content")
        
        dest_dir = tmp_path / "destination"
        
        success, dest_path, error = safe_move_file(
            str(source), str(dest_dir), verify_hash=False
        )
        
        assert success is True
        assert dest_path is not None
        assert error is None
        assert Path(dest_path).exists()
        assert not source.exists()
    
    def test_move_with_hash_verification(self, tmp_path):
        """Test file move with hash verification."""
        source = tmp_path / "source.txt"
        source.write_text("test content")
        
        dest_dir = tmp_path / "destination"
        
        success, dest_path, error = safe_move_file(
            str(source), str(dest_dir), verify_hash=True
        )
        
        assert success is True
        assert Path(dest_path).read_text() == "test content"
    
    def test_collision_rename_strategy(self, tmp_path):
        """Test rename strategy for filename collisions."""
        source1 = tmp_path / "source.txt"
        source1.write_text("content 1")
        
        source2 = tmp_path / "source2" / "source.txt"
        source2.parent.mkdir()
        source2.write_text("content 2")
        
        dest_dir = tmp_path / "destination"
        
        # Move first file
        safe_move_file(str(source1), str(dest_dir), verify_hash=False)
        
        # Move second file with same name
        success, dest_path, error = safe_move_file(
            str(source2), str(dest_dir), 
            verify_hash=False, collision_strategy="rename"
        )
        
        assert success is True
        # Should have renamed with timestamp
        assert "source_" in str(dest_path)
    
    def test_collision_skip_strategy(self, tmp_path):
        """Test skip strategy for filename collisions."""
        source1 = tmp_path / "source.txt"
        source1.write_text("content 1")
        
        source2 = tmp_path / "source2" / "source.txt"
        source2.parent.mkdir()
        source2.write_text("content 2")
        
        dest_dir = tmp_path / "destination"
        
        # Move first file
        safe_move_file(str(source1), str(dest_dir))
        
        # Try to move second file with skip strategy
        success, dest_path, error = safe_move_file(
            str(source2), str(dest_dir), collision_strategy="skip"
        )
        
        assert success is False
        assert "already exists" in error


class TestArchiveFile:
    """Test suite for file archiving."""
    
    def test_archive_file_basic(self, tmp_path):
        """Test basic file archiving."""
        source = tmp_path / "source.txt"
        source.write_text("test content")
        
        archive_dir = tmp_path / "archive"
        
        success, archive_path, error = archive_file(
            str(source), str(archive_dir), preserve_structure=False
        )
        
        assert success is True
        assert archive_path is not None
        assert Path(archive_path).exists()
        assert source.exists()  # Original should still exist
    
    def test_archive_preserves_structure(self, tmp_path):
        """Test archiving with directory structure preservation."""
        subdir = tmp_path / "photos" / "2024"
        subdir.mkdir(parents=True)
        
        source = subdir / "photo.jpg"
        source.write_text("fake image")
        
        archive_dir = tmp_path / "archive"
        
        success, archive_path, error = archive_file(
            str(source), str(archive_dir), preserve_structure=True
        )
        
        assert success is True
        # Should preserve parent directory name
        assert "2024" in archive_path


class TestImageFileDetection:
    """Test suite for image file detection."""
    
    def test_common_image_extensions(self):
        """Test detection of common image extensions."""
        assert is_image_file("photo.jpg") is True
        assert is_image_file("photo.JPG") is True
        assert is_image_file("photo.jpeg") is True
        assert is_image_file("photo.png") is True
        assert is_image_file("photo.HEIC") is True
        assert is_image_file("photo.raw") is True
    
    def test_non_image_files(self):
        """Test rejection of non-image files."""
        assert is_image_file("document.txt") is False
        assert is_image_file("video.mp4") is False
        assert is_image_file("archive.zip") is False
    
    def test_custom_extensions(self):
        """Test custom extension list."""
        assert is_image_file("photo.jpg", extensions=["jpg", "png"]) is True
        assert is_image_file("photo.gif", extensions=["jpg", "png"]) is False


class TestUtilityFunctions:
    """Test suite for utility functions."""
    
    def test_get_file_size_mb(self, tmp_path):
        """Test file size calculation in MB."""
        test_file = tmp_path / "test.txt"
        # Create 1MB file
        test_file.write_bytes(b'A' * (1024 * 1024))
        
        size_mb = get_file_size_mb(str(test_file))
        assert 0.99 < size_mb < 1.01  # Account for rounding
    
    def test_ensure_directory(self, tmp_path):
        """Test directory creation."""
        new_dir = tmp_path / "new" / "nested" / "directory"
        
        result = ensure_directory(str(new_dir))
        
        assert result is True
        assert new_dir.exists()
        assert new_dir.is_dir()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
