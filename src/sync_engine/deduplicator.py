"""
Deduplicator

Detects duplicate files using hash-based comparison before moving to PhotoPrism.
Maintains hash cache for performance.

Author: Next_Prism Project
License: MIT
"""

import hashlib
import os
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
import json
import time

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DuplicateCheckResult:
    """Result of duplicate check operation."""
    is_duplicate: bool
    existing_file: Optional[Path] = None
    hash_value: Optional[str] = None
    match_type: Optional[str] = None  # 'filename', 'hash', or None


class Deduplicator:
    """
    File deduplication system using hash comparison.
    
    Features:
    - SHA256 hash calculation for accuracy
    - Filename matching for quick checks
    - Hash cache for performance
    - EXIF metadata comparison (optional, future enhancement)
    """
    
    HASH_ALGORITHM = 'sha256'
    CHUNK_SIZE = 65536  # 64KB chunks for hashing
    
    def __init__(self, cache_file: Optional[str] = None):
        """
        Initialize deduplicator.
        
        Args:
            cache_file: Path to hash cache file (JSON)
        """
        self.cache_file = cache_file
        self._hash_cache: Dict[str, Tuple[str, float]] = {}  # path -> (hash, mtime)
        
        if cache_file and os.path.exists(cache_file):
            self._load_cache()
        
        logger.info("Deduplicator initialized")
    
    def calculate_hash(self, file_path: Path, use_cache: bool = True) -> str:
        """
        Calculate SHA256 hash of file.
        
        Args:
            file_path: Path to file
            use_cache: Whether to use cached hash if available
        
        Returns:
            Hex string of file hash
        """
        file_str = str(file_path)
        
        # Check cache if enabled
        if use_cache and file_str in self._hash_cache:
            cached_hash, cached_mtime = self._hash_cache[file_str]
            current_mtime = os.path.getmtime(file_str)
            
            # Use cached hash if file hasn't been modified
            if abs(current_mtime - cached_mtime) < 1.0:  # 1 second tolerance
                logger.debug(f"Using cached hash for {file_path.name}")
                return cached_hash
        
        # Calculate hash
        logger.debug(f"Calculating {self.HASH_ALGORITHM} hash for {file_path.name}")
        hasher = hashlib.new(self.HASH_ALGORITHM)
        
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(self.CHUNK_SIZE):
                    hasher.update(chunk)
            
            hash_value = hasher.hexdigest()
            
            # Update cache
            self._hash_cache[file_str] = (hash_value, os.path.getmtime(file_str))
            
            return hash_value
            
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            raise
    
    def check_duplicate(
        self,
        file_path: Path,
        search_directories: list[Path],
        check_filename: bool = True,
        check_hash: bool = True
    ) -> DuplicateCheckResult:
        """
        Check if file is a duplicate of any file in search directories.
        
        Args:
            file_path: Path to file to check
            search_directories: List of directories to search for duplicates
            check_filename: Whether to check for filename matches
            check_hash: Whether to check for hash matches
        
        Returns:
            DuplicateCheckResult with duplicate status
        """
        filename = file_path.name
        
        # Quick check: filename match
        if check_filename:
            for search_dir in search_directories:
                potential_duplicate = search_dir / filename
                if potential_duplicate.exists() and potential_duplicate != file_path:
                    logger.info(f"Duplicate detected (filename): {filename} exists in {search_dir}")
                    return DuplicateCheckResult(
                        is_duplicate=True,
                        existing_file=potential_duplicate,
                        match_type='filename'
                    )
        
        # Thorough check: hash comparison
        if check_hash:
            try:
                file_hash = self.calculate_hash(file_path)
                
                # Search for matching hash in all directories
                for search_dir in search_directories:
                    if not search_dir.exists():
                        continue
                    
                    for existing_file in search_dir.rglob('*'):
                        if not existing_file.is_file():
                            continue
                        
                        if existing_file == file_path:
                            continue
                        
                        # Calculate hash of potential duplicate
                        try:
                            existing_hash = self.calculate_hash(existing_file)
                            
                            if existing_hash == file_hash:
                                logger.info(f"Duplicate detected (hash): {filename} matches {existing_file}")
                                return DuplicateCheckResult(
                                    is_duplicate=True,
                                    existing_file=existing_file,
                                    hash_value=file_hash,
                                    match_type='hash'
                                )
                        except Exception as e:
                            logger.warning(f"Error hashing {existing_file}: {e}")
                            continue
                
                # No duplicate found
                return DuplicateCheckResult(
                    is_duplicate=False,
                    hash_value=file_hash
                )
                
            except Exception as e:
                logger.error(f"Error during duplicate check for {file_path}: {e}")
                # Return non-duplicate on error (fail open)
                return DuplicateCheckResult(is_duplicate=False)
        
        # No checks performed or no duplicates found
        return DuplicateCheckResult(is_duplicate=False)
    
    def build_directory_hash_index(self, directory: Path) -> Dict[str, Path]:
        """
        Build hash index of all files in directory for faster duplicate checking.
        
        Args:
            directory: Directory to index
        
        Returns:
            Dictionary mapping hash -> file path
        """
        logger.info(f"Building hash index for {directory}")
        hash_index = {}
        
        if not directory.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return hash_index
        
        file_count = 0
        for file_path in directory.rglob('*'):
            if not file_path.is_file():
                continue
            
            try:
                file_hash = self.calculate_hash(file_path)
                hash_index[file_hash] = file_path
                file_count += 1
                
                if file_count % 100 == 0:
                    logger.debug(f"Indexed {file_count} files...")
                    
            except Exception as e:
                logger.warning(f"Error indexing {file_path}: {e}")
                continue
        
        logger.info(f"Indexed {file_count} files in {directory}")
        return hash_index
    
    def check_duplicate_fast(
        self,
        file_path: Path,
        hash_index: Dict[str, Path]
    ) -> DuplicateCheckResult:
        """
        Fast duplicate check using pre-built hash index.
        
        Args:
            file_path: File to check
            hash_index: Pre-built hash index from build_directory_hash_index()
        
        Returns:
            DuplicateCheckResult
        """
        try:
            file_hash = self.calculate_hash(file_path)
            
            if file_hash in hash_index:
                existing_file = hash_index[file_hash]
                if existing_file != file_path:
                    logger.info(f"Duplicate detected: {file_path.name} matches {existing_file}")
                    return DuplicateCheckResult(
                        is_duplicate=True,
                        existing_file=existing_file,
                        hash_value=file_hash,
                        match_type='hash'
                    )
            
            return DuplicateCheckResult(
                is_duplicate=False,
                hash_value=file_hash
            )
            
        except Exception as e:
            logger.error(f"Error during fast duplicate check: {e}")
            return DuplicateCheckResult(is_duplicate=False)
    
    def _load_cache(self):
        """Load hash cache from file."""
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                self._hash_cache = {
                    path: (hash_val, mtime)
                    for path, (hash_val, mtime) in data.items()
                }
            logger.info(f"Loaded hash cache with {len(self._hash_cache)} entries")
        except Exception as e:
            logger.warning(f"Could not load hash cache: {e}")
            self._hash_cache = {}
    
    def save_cache(self):
        """Save hash cache to file."""
        if not self.cache_file:
            return
        
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self._hash_cache, f)
            logger.info(f"Saved hash cache with {len(self._hash_cache)} entries")
        except Exception as e:
            logger.error(f"Error saving hash cache: {e}")
    
    def clear_cache(self):
        """Clear hash cache."""
        self._hash_cache.clear()
        logger.info("Hash cache cleared")
    
    def prune_cache(self, max_age_days: int = 30):
        """
        Remove old entries from cache for files that no longer exist.
        
        Args:
            max_age_days: Remove entries older than this many days
        """
        current_time = time.time()
        max_age_seconds = max_age_days * 86400
        
        paths_to_remove = []
        for path, (_, mtime) in self._hash_cache.items():
            # Remove if file doesn't exist or is too old
            if not os.path.exists(path) or (current_time - mtime) > max_age_seconds:
                paths_to_remove.append(path)
        
        for path in paths_to_remove:
            del self._hash_cache[path]
        
        logger.info(f"Pruned {len(paths_to_remove)} entries from hash cache")
