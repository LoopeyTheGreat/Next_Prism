"""
File Mover

Safely moves photo files from Nextcloud to PhotoPrism import directory.
Handles verification, collision resolution, and archiving.

Author: Next_Prism Project
License: MIT
"""

import os
import shutil
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import time

from ..utils.logger import get_logger
from ..config.schema import Config
from .deduplicator import Deduplicator

logger = get_logger(__name__)


@dataclass
class MoveResult:
    """Result of file move operation."""
    success: bool
    source_path: Path
    destination_path: Optional[Path] = None
    archive_path: Optional[Path] = None
    error_message: Optional[str] = None
    was_archived: bool = False
    was_renamed: bool = False


class FileMover:
    """
    Safe file move operations with verification and archiving.
    
    Features:
    - Disk space verification
    - Hash verification after move
    - Collision handling (rename with timestamp)
    - Archive mode (move to archive instead of delete)
    - Transaction logging
    - Rollback capability
    """
    
    def __init__(self, config: Config, deduplicator: Optional[Deduplicator] = None):
        """
        Initialize file mover.
        
        Args:
            config: Configuration object
            deduplicator: Deduplicator instance for hash verification
        """
        self.config = config
        self.deduplicator = deduplicator or Deduplicator()
        self._move_log = []
        
        logger.info("FileMover initialized")
    
    def move_to_photoprism(
        self,
        source_file: Path,
        verify_hash: bool = True
    ) -> MoveResult:
        """
        Move file from Nextcloud to PhotoPrism import directory.
        
        Args:
            source_file: Source file path
            verify_hash: Whether to verify hash after move
        
        Returns:
            MoveResult with operation details
        """
        if not source_file.exists():
            logger.error(f"Source file does not exist: {source_file}")
            return MoveResult(
                success=False,
                source_path=source_file,
                error_message="Source file does not exist"
            )
        
        # Determine destination
        import_path = Path(self.config.photoprism.import_path)
        destination_file = import_path / source_file.name
        
        # Handle filename collision
        if destination_file.exists():
            logger.warning(f"Destination file exists: {destination_file}")
            destination_file = self._generate_unique_filename(destination_file)
            was_renamed = True
        else:
            was_renamed = False
        
        # Check disk space
        if not self._check_disk_space(source_file, import_path):
            return MoveResult(
                success=False,
                source_path=source_file,
                error_message="Insufficient disk space at destination"
            )
        
        # Calculate source hash before move
        source_hash = None
        if verify_hash:
            try:
                source_hash = self.deduplicator.calculate_hash(source_file)
                logger.debug(f"Source hash: {source_hash}")
            except Exception as e:
                logger.warning(f"Could not calculate source hash: {e}")
        
        # Perform move
        try:
            logger.info(f"Moving {source_file.name} to {destination_file}")
            
            # Ensure destination directory exists
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Move file
            if self.config.photoprism.import_mode == "copy":
                shutil.copy2(source_file, destination_file)
                logger.debug(f"Copied file to {destination_file}")
            else:
                shutil.move(str(source_file), str(destination_file))
                logger.debug(f"Moved file to {destination_file}")
            
            # Verify hash after move
            if verify_hash and source_hash:
                dest_hash = self.deduplicator.calculate_hash(destination_file)
                if dest_hash != source_hash:
                    logger.error(f"Hash mismatch after move! Source: {source_hash}, Dest: {dest_hash}")
                    # Attempt rollback
                    self._rollback_move(source_file, destination_file, copy_mode=(self.config.photoprism.import_mode == "copy"))
                    return MoveResult(
                        success=False,
                        source_path=source_file,
                        error_message="Hash verification failed after move"
                    )
                logger.debug("Hash verification passed")
            
            # Archive original if in copy mode and archive enabled
            archive_path = None
            was_archived = False
            if self.config.photoprism.import_mode == "copy" and self.config.monitoring.archive_mode:
                archive_result = self._archive_original(source_file)
                if archive_result:
                    archive_path = archive_result
                    was_archived = True
            
            # Log successful move
            self._log_move(source_file, destination_file, archive_path)
            
            return MoveResult(
                success=True,
                source_path=source_file,
                destination_path=destination_file,
                archive_path=archive_path,
                was_archived=was_archived,
                was_renamed=was_renamed
            )
            
        except Exception as e:
            logger.error(f"Error moving file {source_file}: {e}")
            return MoveResult(
                success=False,
                source_path=source_file,
                error_message=str(e)
            )
    
    def _check_disk_space(self, source_file: Path, destination_dir: Path) -> bool:
        """
        Check if destination has sufficient disk space.
        
        Args:
            source_file: Source file
            destination_dir: Destination directory
        
        Returns:
            True if sufficient space available
        """
        try:
            source_size = source_file.stat().st_size
            dest_stat = os.statvfs(destination_dir)
            available_space = dest_stat.f_bavail * dest_stat.f_frsize
            
            # Require 10% buffer
            required_space = source_size * 1.1
            
            if available_space < required_space:
                logger.error(
                    f"Insufficient disk space. Required: {required_space / 1024 / 1024:.2f} MB, "
                    f"Available: {available_space / 1024 / 1024:.2f} MB"
                )
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Could not check disk space: {e}")
            # Assume space is available if check fails
            return True
    
    def _generate_unique_filename(self, file_path: Path) -> Path:
        """
        Generate unique filename by appending timestamp.
        
        Args:
            file_path: Original file path
        
        Returns:
            New unique file path
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = file_path.stem
        suffix = file_path.suffix
        new_name = f"{stem}_{timestamp}{suffix}"
        new_path = file_path.parent / new_name
        
        # If still exists (unlikely), add counter
        counter = 1
        while new_path.exists():
            new_name = f"{stem}_{timestamp}_{counter}{suffix}"
            new_path = file_path.parent / new_name
            counter += 1
        
        logger.info(f"Generated unique filename: {new_name}")
        return new_path
    
    def _archive_original(self, source_file: Path) -> Optional[Path]:
        """
        Move original file to archive directory.
        
        Args:
            source_file: Source file to archive
        
        Returns:
            Archive path if successful, None otherwise
        """
        try:
            # Determine archive path
            # Try to find the user's root directory
            parts = source_file.parts
            nc_data_path = Path(self.config.nextcloud.data_path)
            
            # Find user directory
            user_dir = None
            for i, part in enumerate(parts):
                if i > 0 and Path(*parts[:i]) == nc_data_path:
                    user_dir = Path(*parts[:i+1])
                    break
            
            if not user_dir:
                logger.warning(f"Could not determine user directory for {source_file}")
                return None
            
            # Build archive path maintaining structure
            relative_path = source_file.relative_to(user_dir / "files")
            archive_base = user_dir / "files" / self.config.monitoring.archive_path
            archive_file = archive_base / relative_path
            
            # Ensure archive directory exists
            archive_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Move to archive
            logger.info(f"Archiving {source_file.name} to {archive_file}")
            shutil.move(str(source_file), str(archive_file))
            
            return archive_file
            
        except Exception as e:
            logger.error(f"Error archiving file {source_file}: {e}")
            return None
    
    def _rollback_move(self, source_path: Path, dest_path: Path, copy_mode: bool):
        """
        Rollback a failed move operation.
        
        Args:
            source_path: Original source path
            dest_path: Destination path
            copy_mode: Whether operation was in copy mode
        """
        try:
            if dest_path.exists():
                logger.info(f"Rolling back: removing {dest_path}")
                dest_path.unlink()
            
            # If in move mode and source doesn't exist, can't fully rollback
            if not copy_mode and not source_path.exists():
                logger.error("Cannot fully rollback move - source file already moved")
                
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
    
    def _log_move(self, source: Path, destination: Path, archive: Optional[Path]):
        """Log successful move operation."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'source': str(source),
            'destination': str(destination),
            'archive': str(archive) if archive else None,
            'mode': self.config.photoprism.import_mode
        }
        self._move_log.append(log_entry)
        
        # Keep last 1000 entries
        if len(self._move_log) > 1000:
            self._move_log = self._move_log[-1000:]
    
    def get_move_history(self, limit: int = 100) -> list:
        """
        Get recent move history.
        
        Args:
            limit: Maximum number of entries to return
        
        Returns:
            List of move log entries
        """
        return self._move_log[-limit:]
    
    def clear_move_history(self):
        """Clear move history log."""
        self._move_log.clear()
        logger.info("Move history cleared")
