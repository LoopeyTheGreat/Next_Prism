"""
File Watcher

Monitors Nextcloud user directories and custom folders for new photo files.
Uses watchdog library to detect filesystem events and queue files for processing.

Author: Next_Prism Project
License: MIT
"""

import os
import time
from pathlib import Path
from typing import Set, Callable, Optional, Dict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
from threading import Lock
import logging

from ..utils.logger import get_logger
from ..config.schema import Config

logger = get_logger(__name__)


class PhotoFileHandler(FileSystemEventHandler):
    """
    Handler for filesystem events that filters for photo files.
    
    Implements debouncing to avoid duplicate triggers during file writes.
    """
    
    # Photo file extensions to monitor (case-insensitive)
    PHOTO_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
        '.heic', '.heif', '.webp',
        '.raw', '.cr2', '.nef', '.arw', '.dng', '.orf', '.rw2',
        '.raf', '.sr2', '.pef', '.crw'
    }
    
    def __init__(self, callback: Callable[[Path, str], None], debounce_seconds: float = 5.0):
        """
        Initialize photo file handler.
        
        Args:
            callback: Function to call when a new photo is detected (path, source_folder)
            debounce_seconds: Time to wait for file stability before processing
        """
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        
        # Track files being written (debouncing)
        self._pending_files: Dict[str, float] = {}
        self._lock = Lock()
    
    def _is_photo_file(self, path: str) -> bool:
        """Check if file is a photo based on extension."""
        return Path(path).suffix.lower() in self.PHOTO_EXTENSIONS
    
    def _is_hidden_or_temp(self, path: str) -> bool:
        """Check if file is hidden or temporary."""
        filename = os.path.basename(path)
        return (
            filename.startswith('.') or
            filename.startswith('~') or
            filename.endswith('.tmp') or
            filename.endswith('.part') or
            '/.~' in path
        )
    
    def on_created(self, event: FileCreatedEvent):
        """Handle file creation events."""
        if event.is_directory:
            return
        
        if not self._is_photo_file(event.src_path):
            return
        
        if self._is_hidden_or_temp(event.src_path):
            return
        
        logger.debug(f"Photo file created: {event.src_path}")
        self._add_pending_file(event.src_path)
    
    def on_modified(self, event: FileModifiedEvent):
        """Handle file modification events (file write completion)."""
        if event.is_directory:
            return
        
        if not self._is_photo_file(event.src_path):
            return
        
        if self._is_hidden_or_temp(event.src_path):
            return
        
        logger.debug(f"Photo file modified: {event.src_path}")
        self._add_pending_file(event.src_path)
    
    def _add_pending_file(self, path: str):
        """Add file to pending queue with timestamp."""
        with self._lock:
            self._pending_files[path] = time.time()
    
    def process_pending_files(self):
        """
        Process pending files that have been stable (not modified) for debounce period.
        
        This should be called periodically (e.g., every second) to check for stable files.
        """
        current_time = time.time()
        files_to_process = []
        
        with self._lock:
            for path, timestamp in list(self._pending_files.items()):
                # Check if file has been stable for debounce period
                if current_time - timestamp >= self.debounce_seconds:
                    # Check if file still exists (might have been moved/deleted)
                    if os.path.exists(path) and os.path.isfile(path):
                        files_to_process.append(path)
                    del self._pending_files[path]
        
        # Process stable files
        for path in files_to_process:
            try:
                logger.info(f"Processing stable file: {path}")
                self.callback(Path(path), str(Path(path).parent))
            except Exception as e:
                logger.error(f"Error processing file {path}: {e}")


class FileWatcher:
    """
    Main file watcher service.
    
    Monitors multiple folders and dispatches detected photos to callback.
    """
    
    def __init__(self, config: Config, callback: Callable[[Path, str], None]):
        """
        Initialize file watcher.
        
        Args:
            config: Configuration object with monitoring settings
            callback: Function to call when new photo detected (path, source_folder)
        """
        self.config = config
        self.callback = callback
        self.observer = Observer()
        self._watched_paths: Set[str] = set()
        self._handlers: Dict[str, PhotoFileHandler] = {}
        self._is_running = False
        
        logger.info("FileWatcher initialized")
    
    def start(self):
        """Start watching configured folders."""
        if self._is_running:
            logger.warning("FileWatcher already running")
            return
        
        # Add Nextcloud user folders
        self._add_nextcloud_folders()
        
        # Add custom folders
        self._add_custom_folders()
        
        # Start observer
        self.observer.start()
        self._is_running = True
        
        logger.info(f"FileWatcher started, monitoring {len(self._watched_paths)} folders")
    
    def stop(self):
        """Stop watching folders."""
        if not self._is_running:
            return
        
        self.observer.stop()
        self.observer.join(timeout=5.0)
        self._is_running = False
        
        logger.info("FileWatcher stopped")
    
    def _add_nextcloud_folders(self):
        """Discover and add Nextcloud user photo folders."""
        nc_config = self.config.nextcloud
        data_path = Path(nc_config.data_path)
        
        if not data_path.exists():
            logger.warning(f"Nextcloud data path does not exist: {data_path}")
            return
        
        # Get list of users to monitor
        users_to_monitor = self._get_users_to_monitor(data_path)
        
        for username in users_to_monitor:
            photos_path = data_path / username / "files" / nc_config.photos_folder
            
            if photos_path.exists() and photos_path.is_dir():
                self._add_watch_path(str(photos_path), f"nextcloud:{username}")
                logger.info(f"Monitoring Nextcloud user: {username} at {photos_path}")
            else:
                logger.warning(f"Photos folder not found for user {username}: {photos_path}")
    
    def _get_users_to_monitor(self, data_path: Path) -> Set[str]:
        """
        Determine which Nextcloud users to monitor based on configuration.
        
        Returns:
            Set of usernames to monitor
        """
        nc_config = self.config.nextcloud
        
        # Get all users from data directory
        all_users = set()
        try:
            for item in data_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    # Check if it has a files directory (valid user)
                    if (item / "files").exists():
                        all_users.add(item.name)
        except Exception as e:
            logger.error(f"Error reading Nextcloud data directory: {e}")
            return set()
        
        # Apply user selection mode
        if nc_config.user_selection == "all":
            return all_users
        
        elif nc_config.user_selection == "include":
            # Only include specified users
            included = set(nc_config.users) & all_users
            logger.info(f"Including users: {included}")
            return included
        
        elif nc_config.user_selection == "exclude":
            # Exclude specified users
            excluded = set(nc_config.users)
            result = all_users - excluded
            logger.info(f"Excluding users: {excluded}, monitoring: {result}")
            return result
        
        else:
            logger.warning(f"Unknown user_selection mode: {nc_config.user_selection}, defaulting to 'all'")
            return all_users
    
    def _add_custom_folders(self):
        """Add custom monitored folders from configuration."""
        for folder in self.config.monitoring.custom_folders:
            folder_path = folder.path
            
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                self._add_watch_path(folder_path, f"custom:{folder_path}")
                logger.info(f"Monitoring custom folder: {folder_path}")
            else:
                logger.warning(f"Custom folder does not exist: {folder_path}")
    
    def _add_watch_path(self, path: str, source_label: str):
        """
        Add a path to be watched.
        
        Args:
            path: Directory path to monitor
            source_label: Human-readable label for logging
        """
        if path in self._watched_paths:
            logger.debug(f"Path already being watched: {path}")
            return
        
        # Create handler for this path
        handler = PhotoFileHandler(
            callback=lambda p, s: self.callback(p, source_label),
            debounce_seconds=self.config.monitoring.debounce_seconds
        )
        
        # Schedule watch
        self.observer.schedule(handler, path, recursive=True)
        
        self._watched_paths.add(path)
        self._handlers[path] = handler
        
        logger.debug(f"Added watch path: {path} (label: {source_label})")
    
    def process_pending_files(self):
        """Process pending files in all handlers (call periodically)."""
        for handler in self._handlers.values():
            handler.process_pending_files()
    
    def get_watched_folders(self) -> list:
        """
        Get list of currently watched folders.
        
        Returns:
            List of folder paths
        """
        return list(self._watched_paths)
    
    def reload_folders(self):
        """Reload folder configuration (e.g., after config change)."""
        logger.info("Reloading watched folders")
        
        # Stop current observer
        was_running = self._is_running
        if was_running:
            self.stop()
        
        # Clear current watches
        self._watched_paths.clear()
        self._handlers.clear()
        self.observer = Observer()
        
        # Restart with new configuration
        if was_running:
            self.start()
