"""
File Operation Utilities

Provides safe file operations including hashing, moving, copying,
and archive management.

Author: Next_Prism Project
License: MIT
"""

import os
import shutil
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from .logger import get_logger

logger = get_logger(__name__)


def calculate_file_hash(file_path: str, algorithm: str = "sha256", chunk_size: int = 8192) -> str:
    """
    Calculate hash of a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (md5, sha1, sha256, etc.)
        chunk_size: Size of chunks to read (bytes)
        
    Returns:
        Hexadecimal hash string
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If algorithm is unsupported
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    try:
        hash_func = hashlib.new(algorithm)
    except ValueError:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()


def safe_move_file(
    source: str,
    destination_dir: str,
    verify_hash: bool = True,
    collision_strategy: str = "rename"
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Safely move a file to a destination directory with verification.
    
    Args:
        source: Source file path
        destination_dir: Destination directory path
        verify_hash: Verify file integrity after move
        collision_strategy: How to handle filename collisions
            - "rename": Append timestamp to filename
            - "skip": Skip if file exists
            - "overwrite": Overwrite existing file
            
    Returns:
        Tuple of (success: bool, destination_path: str, error_message: str)
    """
    try:
        source_path = Path(source)
        dest_dir = Path(destination_dir)
        
        if not source_path.exists():
            return False, None, f"Source file not found: {source}"
        
        if not source_path.is_file():
            return False, None, f"Source is not a file: {source}"
        
        # Create destination directory
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine destination path
        dest_path = dest_dir / source_path.name
        
        # Handle collisions
        if dest_path.exists():
            if collision_strategy == "skip":
                logger.info(f"Skipping existing file: {dest_path}")
                return False, None, "File already exists (skipped)"
            elif collision_strategy == "rename":
                # Append timestamp to filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                stem = dest_path.stem
                suffix = dest_path.suffix
                dest_path = dest_dir / f"{stem}_{timestamp}{suffix}"
                logger.info(f"Renaming to avoid collision: {dest_path.name}")
            # For "overwrite", just proceed
        
        # Calculate source hash if verification enabled
        source_hash = None
        if verify_hash:
            source_hash = calculate_file_hash(str(source_path))
        
        # Move the file
        shutil.move(str(source_path), str(dest_path))
        logger.debug(f"Moved: {source} -> {dest_path}")
        
        # Verify hash after move
        if verify_hash and source_hash:
            dest_hash = calculate_file_hash(str(dest_path))
            if source_hash != dest_hash:
                logger.error(f"Hash mismatch after move: {dest_path}")
                # Attempt to restore (if possible)
                return False, None, "File integrity check failed after move"
        
        return True, str(dest_path), None
        
    except PermissionError as e:
        logger.error(f"Permission error moving file: {e}")
        return False, None, f"Permission denied: {e}"
    except OSError as e:
        logger.error(f"OS error moving file: {e}")
        return False, None, f"OS error: {e}"
    except Exception as e:
        logger.error(f"Unexpected error moving file: {e}")
        return False, None, f"Unexpected error: {e}"


def archive_file(
    source: str,
    archive_base_path: str,
    preserve_structure: bool = True
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Archive a file by copying to archive location.
    
    Args:
        source: Source file path
        archive_base_path: Base path for archive directory
        preserve_structure: Preserve directory structure in archive
        
    Returns:
        Tuple of (success: bool, archive_path: str, error_message: str)
    """
    try:
        source_path = Path(source)
        archive_base = Path(archive_base_path)
        
        if not source_path.exists():
            return False, None, f"Source file not found: {source}"
        
        # Determine archive location
        if preserve_structure and source_path.parent != Path("."):
            # Preserve relative directory structure
            archive_path = archive_base / source_path.parent.name / source_path.name
        else:
            archive_path = archive_base / source_path.name
        
        # Create archive directory
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Handle collisions with timestamp
        if archive_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = archive_path.stem
            suffix = archive_path.suffix
            archive_path = archive_path.parent / f"{stem}_{timestamp}{suffix}"
        
        # Copy file to archive
        shutil.copy2(str(source_path), str(archive_path))
        logger.info(f"Archived: {source} -> {archive_path}")
        
        return True, str(archive_path), None
        
    except Exception as e:
        logger.error(f"Error archiving file: {e}")
        return False, None, f"Archive error: {e}"


def is_image_file(file_path: str, extensions: Optional[list] = None) -> bool:
    """
    Check if a file is an image based on extension.
    
    Args:
        file_path: Path to the file
        extensions: List of valid extensions (without dots)
        
    Returns:
        True if file is an image
    """
    if extensions is None:
        extensions = [
            "jpg", "jpeg", "png", "gif", "bmp", "tiff", "tif",
            "heic", "heif", "webp", "raw", "cr2", "nef", "arw",
            "dng", "orf", "rw2", "pef", "srw"
        ]
    
    path = Path(file_path)
    ext = path.suffix.lower().lstrip('.')
    return ext in extensions


def get_file_size_mb(file_path: str) -> float:
    """
    Get file size in megabytes.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File size in MB
    """
    return os.path.getsize(file_path) / (1024 * 1024)


def ensure_directory(directory: str) -> bool:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory: Directory path
        
    Returns:
        True if directory exists or was created
    """
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {directory}: {e}")
        return False
