"""
Sync Engine

Core synchronization logic that coordinates file detection, deduplication,
moving, and triggering of indexing commands.

Author: Next_Prism Project
License: MIT
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from ..utils.logger import get_logger
from ..utils.file_ops import (
    calculate_file_hash,
    safe_move_file,
    archive_file,
    get_file_size_mb
)
from ..config.schema import MonitoredFolder
from ..docker_interface.executor import (
    DockerExecutor,
    NextcloudCommands,
    PhotoPrismCommands,
    CommandResult
)

logger = get_logger(__name__)


class SyncStatus(Enum):
    """Status of a sync operation."""
    PENDING = "pending"
    HASHING = "hashing"
    CHECKING_DUPLICATE = "checking_duplicate"
    MOVING = "moving"
    ARCHIVING = "archiving"
    INDEXING_PHOTOPRISM = "indexing_photoprism"
    SCANNING_NEXTCLOUD = "scanning_nextcloud"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED_DUPLICATE = "skipped_duplicate"


class SyncResult:
    """Result of a file sync operation."""
    
    def __init__(
        self,
        source_path: str,
        status: SyncStatus,
        destination_path: Optional[str] = None,
        error_message: Optional[str] = None,
        file_hash: Optional[str] = None,
        file_size_mb: float = 0.0,
        is_duplicate: bool = False
    ):
        """
        Initialize sync result.
        
        Args:
            source_path: Original file path
            status: Sync status
            destination_path: Destination path (if moved)
            error_message: Error message if failed
            file_hash: File hash
            file_size_mb: File size in MB
            is_duplicate: Whether file was a duplicate
        """
        self.source_path = source_path
        self.status = status
        self.destination_path = destination_path
        self.error_message = error_message
        self.file_hash = file_hash
        self.file_size_mb = file_size_mb
        self.is_duplicate = is_duplicate
        self.timestamp = datetime.now()
    
    def __repr__(self) -> str:
        return f"SyncResult(source={self.source_path}, status={self.status.value})"


class DeduplicationCache:
    """
    Cache for file hashes to speed up duplicate detection.
    
    Maintains an in-memory cache of file hashes in the destination directory.
    """
    
    def __init__(self):
        """Initialize deduplication cache."""
        self.hash_cache: Dict[str, List[str]] = {}  # hash -> [file_paths]
        self._loaded = False
        logger.info("DeduplicationCache initialized")
    
    def load_destination(self, destination_dir: str):
        """
        Load hashes from destination directory.
        
        Args:
            destination_dir: Directory to scan for existing files
        """
        logger.info(f"Loading hashes from destination: {destination_dir}")
        dest_path = Path(destination_dir)
        
        if not dest_path.exists():
            logger.warning(f"Destination directory does not exist: {destination_dir}")
            return
        
        file_count = 0
        
        # Scan all files in destination
        for file_path in dest_path.rglob('*'):
            if not file_path.is_file():
                continue
            
            try:
                file_hash = calculate_file_hash(str(file_path))
                
                if file_hash not in self.hash_cache:
                    self.hash_cache[file_hash] = []
                
                self.hash_cache[file_hash].append(str(file_path))
                file_count += 1
                
                if file_count % 100 == 0:
                    logger.debug(f"Loaded {file_count} file hashes...")
                    
            except Exception as e:
                logger.warning(f"Failed to hash {file_path}: {e}")
        
        self._loaded = True
        logger.info(f"Loaded {file_count} file hashes from destination")
    
    def is_duplicate(self, file_hash: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a file hash already exists.
        
        Args:
            file_hash: Hash to check
            
        Returns:
            Tuple of (is_duplicate, existing_file_path)
        """
        if file_hash in self.hash_cache:
            existing_files = self.hash_cache[file_hash]
            return True, existing_files[0] if existing_files else None
        
        return False, None
    
    def add_file(self, file_path: str, file_hash: str):
        """
        Add a file to the cache.
        
        Args:
            file_path: Path to the file
            file_hash: File hash
        """
        if file_hash not in self.hash_cache:
            self.hash_cache[file_hash] = []
        
        self.hash_cache[file_hash].append(file_path)
    
    def clear(self):
        """Clear the cache."""
        self.hash_cache.clear()
        self._loaded = False


class SyncEngine:
    """
    Core synchronization engine.
    
    Coordinates the entire sync workflow: detection, deduplication,
    moving, archiving, and triggering indexing commands.
    """
    
    def __init__(
        self,
        docker_executor: DockerExecutor,
        nextcloud_container: str,
        photoprism_container: str,
        photoprism_import_path: str,
        photoprism_albums_path: str
    ):
        """
        Initialize sync engine.
        
        Args:
            docker_executor: Docker command executor
            nextcloud_container: Nextcloud container name
            photoprism_container: PhotoPrism container name
            photoprism_import_path: Path to PhotoPrism import directory
            photoprism_albums_path: Path to PhotoPrism albums directory
        """
        self.docker_executor = docker_executor
        self.nextcloud_commands = NextcloudCommands(docker_executor, nextcloud_container)
        self.photoprism_commands = PhotoPrismCommands(docker_executor, photoprism_container)
        
        self.photoprism_import_path = photoprism_import_path
        self.photoprism_albums_path = photoprism_albums_path
        
        # Initialize deduplication cache
        self.dedupe_cache = DeduplicationCache()
        
        # Stats
        self.stats = {
            "files_processed": 0,
            "files_moved": 0,
            "duplicates_skipped": 0,
            "errors": 0,
            "total_size_mb": 0.0
        }
        
        logger.info("SyncEngine initialized")
    
    def initialize(self):
        """Initialize the sync engine (load dedupe cache, etc.)."""
        logger.info("Initializing sync engine...")
        
        # Load deduplication cache
        self.dedupe_cache.load_destination(self.photoprism_import_path)
        
        # Verify containers are accessible
        if not self.docker_executor.container_exists(self.nextcloud_commands.container_name):
            logger.warning(f"Nextcloud container not found: {self.nextcloud_commands.container_name}")
        
        if not self.docker_executor.container_exists(self.photoprism_commands.container_name):
            logger.warning(f"PhotoPrism container not found: {self.photoprism_commands.container_name}")
        
        logger.info("Sync engine initialized")
    
    def sync_file(
        self,
        file_path: str,
        folder_config: MonitoredFolder,
        skip_dedupe: bool = False
    ) -> SyncResult:
        """
        Sync a single file through the complete workflow.
        
        Args:
            file_path: Path to the file to sync
            folder_config: Configuration for the source folder
            skip_dedupe: Skip deduplication check
            
        Returns:
            SyncResult with operation details
        """
        logger.info(f"Starting sync for file: {file_path}")
        
        # Verify file exists
        if not Path(file_path).exists():
            logger.error(f"File not found: {file_path}")
            return SyncResult(
                source_path=file_path,
                status=SyncStatus.FAILED,
                error_message="File not found"
            )
        
        # Calculate file hash
        try:
            file_hash = calculate_file_hash(file_path)
            file_size = get_file_size_mb(file_path)
            logger.debug(f"File hash: {file_hash}, size: {file_size:.2f}MB")
        except Exception as e:
            logger.error(f"Failed to hash file {file_path}: {e}")
            return SyncResult(
                source_path=file_path,
                status=SyncStatus.FAILED,
                error_message=f"Hashing failed: {e}"
            )
        
        # Check for duplicates
        if not skip_dedupe:
            is_duplicate, existing_path = self.dedupe_cache.is_duplicate(file_hash)
            
            if is_duplicate:
                logger.info(f"Duplicate detected: {file_path} (matches {existing_path})")
                self.stats["duplicates_skipped"] += 1
                
                # Archive or delete the duplicate
                if folder_config.archive_moved:
                    self._archive_source_file(file_path, folder_config)
                else:
                    try:
                        os.remove(file_path)
                        logger.info(f"Deleted duplicate: {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to delete duplicate: {e}")
                
                return SyncResult(
                    source_path=file_path,
                    status=SyncStatus.SKIPPED_DUPLICATE,
                    file_hash=file_hash,
                    file_size_mb=file_size,
                    is_duplicate=True
                )
        
        # Move file to PhotoPrism import
        success, dest_path, error = safe_move_file(
            source=file_path,
            destination_dir=self.photoprism_import_path,
            verify_hash=True,
            collision_strategy="rename"
        )
        
        if not success:
            logger.error(f"Failed to move file: {error}")
            self.stats["errors"] += 1
            return SyncResult(
                source_path=file_path,
                status=SyncStatus.FAILED,
                error_message=error,
                file_hash=file_hash,
                file_size_mb=file_size
            )
        
        logger.info(f"Moved file to: {dest_path}")
        
        # Add to dedupe cache
        self.dedupe_cache.add_file(dest_path, file_hash)
        
        # Archive source if configured (although file was moved, not copied)
        # This would archive from the original user location if we had copied instead
        
        # Update stats
        self.stats["files_processed"] += 1
        self.stats["files_moved"] += 1
        self.stats["total_size_mb"] += file_size
        
        # Trigger PhotoPrism import/index
        # Note: We'll batch these in the orchestrator for efficiency
        
        return SyncResult(
            source_path=file_path,
            status=SyncStatus.COMPLETED,
            destination_path=dest_path,
            file_hash=file_hash,
            file_size_mb=file_size
        )
    
    def _archive_source_file(
        self,
        file_path: str,
        folder_config: MonitoredFolder
    ) -> bool:
        """
        Archive the source file.
        
        Args:
            file_path: File to archive
            folder_config: Folder configuration
            
        Returns:
            True if archived successfully
        """
        # Determine archive path
        if folder_config.archive_path:
            archive_base = folder_config.archive_path
        else:
            # Default: .archive subfolder in the source folder
            archive_base = str(Path(folder_config.path) / ".archive")
        
        success, archive_path, error = archive_file(
            source=file_path,
            archive_base_path=archive_base,
            preserve_structure=True
        )
        
        if success:
            logger.info(f"Archived to: {archive_path}")
            # Delete original after successful archive
            try:
                os.remove(file_path)
                logger.debug(f"Deleted original: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete original after archive: {e}")
            return True
        else:
            logger.error(f"Failed to archive: {error}")
            return False
    
    def trigger_photoprism_index(self) -> CommandResult:
        """
        Trigger PhotoPrism to index imported files.
        
        Returns:
            CommandResult
        """
        logger.info("Triggering PhotoPrism index...")
        result = self.photoprism_commands.import_photos(move=True)
        
        if result.success:
            logger.info("PhotoPrism import completed successfully")
        else:
            logger.error(f"PhotoPrism import failed: {result.error_message}")
        
        return result
    
    def trigger_nextcloud_scan(
        self,
        user: Optional[str] = None,
        path: Optional[str] = None
    ) -> CommandResult:
        """
        Trigger Nextcloud files:scan.
        
        Args:
            user: Specific user to scan
            path: Specific path to scan
            
        Returns:
            CommandResult
        """
        logger.info(f"Triggering Nextcloud scan (user: {user}, path: {path})...")
        result = self.nextcloud_commands.files_scan(user=user, path=path)
        
        if result.success:
            logger.info("Nextcloud scan completed successfully")
        else:
            logger.error(f"Nextcloud scan failed: {result.error_message}")
        
        return result
    
    def trigger_nextcloud_memories_index(
        self,
        user: Optional[str] = None
    ) -> CommandResult:
        """
        Trigger Nextcloud Memories index.
        
        Args:
            user: Specific user to index
            
        Returns:
            CommandResult
        """
        logger.info(f"Triggering Nextcloud Memories index (user: {user})...")
        result = self.nextcloud_commands.memories_index(user=user)
        
        if result.success:
            logger.info("Nextcloud Memories index completed successfully")
        else:
            logger.error(f"Nextcloud Memories index failed: {result.error_message}")
        
        return result
    
    def get_stats(self) -> Dict:
        """Get sync statistics."""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset statistics counters."""
        self.stats = {
            "files_processed": 0,
            "files_moved": 0,
            "duplicates_skipped": 0,
            "errors": 0,
            "total_size_mb": 0.0
        }
        logger.info("Statistics reset")
