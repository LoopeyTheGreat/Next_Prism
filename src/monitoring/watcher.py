"""
File System Watcher

Monitors configured folders for new photo files using the watchdog library.
Implements debouncing to avoid duplicate triggers and queues files for processing.

Author: Next_Prism Project
License: MIT
"""

import time
from pathlib import Path
from typing import Dict, Set, Callable, Optional
from threading import Lock
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from ..utils.logger import get_logger
from ..utils.file_ops import is_image_file
from ..config.schema import MonitoredFolder

logger = get_logger(__name__)


class PhotoFileHandler(FileSystemEventHandler):
    """
    File system event handler for photo files.
    
    Monitors for new photo files, implements debouncing to avoid duplicate
    events, and calls a callback when a new photo is confirmed.
    """
    
    def __init__(
        self,
        folder_config: MonitoredFolder,
        on_new_photo: Callable[[str, MonitoredFolder], None],
        debounce_seconds: int = 2
    ):
        """
        Initialize the photo file handler.
        
        Args:
            folder_config: Configuration for the monitored folder
            on_new_photo: Callback function(file_path, folder_config) when new photo detected
            debounce_seconds: Seconds to wait before confirming a file is stable
        """
        super().__init__()
        self.folder_config = folder_config
        self.on_new_photo = on_new_photo
        self.debounce_seconds = debounce_seconds
        
        # Track pending files with their last modification time
        self._pending_files: Dict[str, float] = {}
        self._lock = Lock()
        
        logger.info(f"Initialized handler for {folder_config.path}")
    
    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return
        
        self._handle_file_event(event.src_path)
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        # Update modification time for pending files
        with self._lock:
            if event.src_path in self._pending_files:
                self._pending_files[event.src_path] = time.time()
    
    def _handle_file_event(self, file_path: str):
        """
        Handle a file event by checking if it's an image and adding to pending.
        
        Args:
            file_path: Path to the file
        """
        # Check if it's an image file based on extension
        if not is_image_file(file_path, extensions=self.folder_config.extensions):
            logger.debug(f"Skipping non-image file: {file_path}")
            return
        
        # Add to pending files
        with self._lock:
            self._pending_files[file_path] = time.time()
            logger.debug(f"Added to pending: {file_path}")
    
    def process_pending(self):
        """
        Process pending files that have stabilized (no changes for debounce period).
        
        Should be called periodically by the watcher.
        """
        current_time = time.time()
        stable_files = []
        
        with self._lock:
            # Find files that haven't been modified recently
            for file_path, last_modified in list(self._pending_files.items()):
                if current_time - last_modified >= self.debounce_seconds:
                    stable_files.append(file_path)
                    del self._pending_files[file_path]
        
        # Process stable files (outside the lock)
        for file_path in stable_files:
            # Verify file still exists and is accessible
            if not Path(file_path).exists():
                logger.warning(f"File disappeared before processing: {file_path}")
                continue
            
            try:
                # Call the callback
                logger.info(f"New photo detected: {file_path}")
                self.on_new_photo(file_path, self.folder_config)
            except Exception as e:
                logger.error(f"Error processing new photo {file_path}: {e}")


class FolderWatcher:
    """
    Manages file system monitoring for multiple folders.
    
    Creates observers for each configured folder and coordinates
    event processing across all monitored locations.
    """
    
    def __init__(self, on_new_photo: Callable[[str, MonitoredFolder], None]):
        """
        Initialize the folder watcher.
        
        Args:
            on_new_photo: Callback function when new photo is detected
        """
        self.on_new_photo = on_new_photo
        self.observers: Dict[str, Observer] = {}
        self.handlers: Dict[str, PhotoFileHandler] = {}
        self._running = False
        
        logger.info("FolderWatcher initialized")
    
    def add_folder(self, folder_config: MonitoredFolder):
        """
        Add a folder to monitor.
        
        Args:
            folder_config: Configuration for the folder to monitor
        """
        if not folder_config.enabled:
            logger.info(f"Skipping disabled folder: {folder_config.path}")
            return
        
        folder_path = Path(folder_config.path)
        
        if not folder_path.exists():
            logger.warning(f"Folder does not exist: {folder_config.path}")
            return
        
        if not folder_path.is_dir():
            logger.error(f"Path is not a directory: {folder_config.path}")
            return
        
        # Create handler and observer
        handler = PhotoFileHandler(
            folder_config=folder_config,
            on_new_photo=self.on_new_photo,
            debounce_seconds=2
        )
        
        observer = Observer()
        observer.schedule(handler, str(folder_path), recursive=True)
        
        # Store references
        self.observers[folder_config.path] = observer
        self.handlers[folder_config.path] = handler
        
        # Start observer if watcher is running
        if self._running:
            observer.start()
            logger.info(f"Started monitoring: {folder_config.path}")
        else:
            logger.info(f"Prepared monitoring for: {folder_config.path}")
    
    def remove_folder(self, folder_path: str):
        """
        Remove a folder from monitoring.
        
        Args:
            folder_path: Path to the folder to stop monitoring
        """
        if folder_path in self.observers:
            observer = self.observers[folder_path]
            observer.stop()
            observer.join(timeout=5)
            
            del self.observers[folder_path]
            del self.handlers[folder_path]
            
            logger.info(f"Stopped monitoring: {folder_path}")
    
    def start(self):
        """Start monitoring all configured folders."""
        if self._running:
            logger.warning("FolderWatcher already running")
            return
        
        # Start all observers
        for folder_path, observer in self.observers.items():
            observer.start()
            logger.info(f"Started monitoring: {folder_path}")
        
        self._running = True
        logger.info("FolderWatcher started")
    
    def stop(self):
        """Stop monitoring all folders."""
        if not self._running:
            return
        
        # Stop all observers
        for folder_path, observer in self.observers.items():
            observer.stop()
            logger.info(f"Stopping monitoring: {folder_path}")
        
        # Wait for observers to finish
        for observer in self.observers.values():
            observer.join(timeout=5)
        
        self._running = False
        logger.info("FolderWatcher stopped")
    
    def process_pending_files(self):
        """
        Process pending files across all handlers.
        
        Should be called periodically (e.g., every second) to check for
        stabilized files that are ready for processing.
        """
        for handler in self.handlers.values():
            handler.process_pending()
    
    def is_running(self) -> bool:
        """Check if the watcher is currently running."""
        return self._running
    
    def get_monitored_folders(self) -> Set[str]:
        """Get set of currently monitored folder paths."""
        return set(self.observers.keys())


class NextcloudUserDetector:
    """
    Detects Nextcloud users by scanning the data directory.
    
    Identifies user directories and can filter based on include/exclude lists.
    """
    
    def __init__(self, nextcloud_data_path: str):
        """
        Initialize the user detector.
        
        Args:
            nextcloud_data_path: Path to Nextcloud data directory
        """
        self.nextcloud_data_path = Path(nextcloud_data_path)
        logger.info(f"NextcloudUserDetector initialized for: {nextcloud_data_path}")
    
    def detect_users(
        self,
        include_list: Optional[list] = None,
        exclude_list: Optional[list] = None
    ) -> Set[str]:
        """
        Detect Nextcloud users in the data directory.
        
        Args:
            include_list: If provided, only include these users (whitelist)
            exclude_list: List of users to exclude (blacklist)
            
        Returns:
            Set of detected usernames
        """
        if not self.nextcloud_data_path.exists():
            logger.error(f"Nextcloud data path does not exist: {self.nextcloud_data_path}")
            return set()
        
        detected_users = set()
        
        # Scan for user directories
        for item in self.nextcloud_data_path.iterdir():
            if not item.is_dir():
                continue
            
            # Skip system directories
            if item.name in ['__groupfolders', 'appdata_', 'files_external', '.ocdata']:
                continue
            
            # Check if it looks like a user directory (has 'files' subdirectory)
            files_dir = item / 'files'
            if files_dir.exists() and files_dir.is_dir():
                username = item.name
                
                # Apply include list filter (whitelist)
                if include_list and username not in include_list:
                    logger.debug(f"Skipping user (not in include list): {username}")
                    continue
                
                # Apply exclude list filter (blacklist)
                if exclude_list and username in exclude_list:
                    logger.debug(f"Skipping user (in exclude list): {username}")
                    continue
                
                detected_users.add(username)
                logger.info(f"Detected Nextcloud user: {username}")
        
        logger.info(f"Detected {len(detected_users)} Nextcloud users")
        return detected_users
    
    def get_user_photos_path(self, username: str) -> Optional[Path]:
        """
        Get the path to a user's Photos directory.
        
        Args:
            username: Username to get photos path for
            
        Returns:
            Path to user's Photos directory, or None if it doesn't exist
        """
        photos_path = self.nextcloud_data_path / username / 'files' / 'Photos'
        
        if photos_path.exists() and photos_path.is_dir():
            return photos_path
        
        # Try 'photos' (lowercase) as fallback
        photos_path = self.nextcloud_data_path / username / 'files' / 'photos'
        if photos_path.exists() and photos_path.is_dir():
            return photos_path
        
        logger.debug(f"No Photos directory found for user: {username}")
        return None
    
    def get_all_user_photos_paths(
        self,
        include_list: Optional[list] = None,
        exclude_list: Optional[list] = None
    ) -> Dict[str, Path]:
        """
        Get photos paths for all detected users.
        
        Args:
            include_list: If provided, only include these users
            exclude_list: List of users to exclude
            
        Returns:
            Dictionary mapping username to photos path
        """
        users = self.detect_users(include_list, exclude_list)
        user_paths = {}
        
        for username in users:
            photos_path = self.get_user_photos_path(username)
            if photos_path:
                user_paths[username] = photos_path
        
        return user_paths
