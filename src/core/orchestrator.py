"""
Orchestrator

Main orchestration logic that coordinates file monitoring, sync engine,
and scheduled tasks.

Author: Next_Prism Project
License: MIT
"""

import time
from typing import List, Optional
from threading import Thread, Event
from queue import Queue, Empty

from ..utils.logger import get_logger
from ..config.schema import Config, MonitoredFolder
from ..monitoring.watcher import FolderWatcher, NextcloudUserDetector
from ..docker_interface.executor import DockerExecutor
from ..core.sync_engine import SyncEngine, SyncResult

logger = get_logger(__name__)


class FileQueueItem:
    """Item in the file processing queue."""
    
    def __init__(self, file_path: str, folder_config: MonitoredFolder):
        """
        Initialize queue item.
        
        Args:
            file_path: Path to the file
            folder_config: Configuration for the source folder
        """
        self.file_path = file_path
        self.folder_config = folder_config
        self.retry_count = 0
        self.max_retries = 3


class Orchestrator:
    """
    Main orchestrator for Next_Prism.
    
    Coordinates file monitoring, queueing, processing, and indexing.
    Manages the complete workflow from file detection to final indexing.
    """
    
    def __init__(self, config: Config):
        """
        Initialize orchestrator.
        
        Args:
            config: Application configuration
        """
        self.config = config
        
        # Initialize Docker executor
        self.docker_executor = DockerExecutor(
            docker_socket=config.docker.docker_socket,
            swarm_mode=config.docker.swarm_mode
        )
        
        # Initialize sync engine
        self.sync_engine = SyncEngine(
            docker_executor=self.docker_executor,
            nextcloud_container=config.nextcloud.container_name,
            photoprism_container=config.photoprism.container_name,
            photoprism_import_path=config.photoprism.import_path,
            photoprism_albums_path=config.photoprism.albums_path
        )
        
        # Initialize file watcher
        self.folder_watcher = FolderWatcher(on_new_photo=self._on_new_photo)
        
        # File processing queue
        self.file_queue: Queue[FileQueueItem] = Queue()
        
        # Control flags
        self._running = False
        self._stop_event = Event()
        
        # Worker threads
        self._watcher_thread: Optional[Thread] = None
        self._processor_thread: Optional[Thread] = None
        
        # Batch processing
        self._batch_size = 10  # Process files in batches
        self._batch_timeout = 30  # Seconds to wait before processing incomplete batch
        
        logger.info("Orchestrator initialized")
    
    def initialize(self):
        """Initialize the orchestrator (setup folders, detect users, etc.)."""
        logger.info("Initializing orchestrator...")
        
        # Initialize sync engine
        self.sync_engine.initialize()
        
        # Detect Nextcloud users if configured
        if self.config.nextcloud.auto_detect_users:
            self._detect_and_add_nextcloud_users()
        
        # Add configured folders to watcher
        for folder_config in self.config.folders:
            if folder_config.enabled:
                self.folder_watcher.add_folder(folder_config)
        
        logger.info("Orchestrator initialized")
    
    def _detect_and_add_nextcloud_users(self):
        """Detect Nextcloud users and add their photo folders to monitoring."""
        logger.info("Detecting Nextcloud users...")
        
        detector = NextcloudUserDetector(self.config.nextcloud.data_path)
        
        user_photos = detector.get_all_user_photos_paths(
            include_list=self.config.nextcloud.users.get("include", []) or None,
            exclude_list=self.config.nextcloud.users.get("exclude", [])
        )
        
        for username, photos_path in user_photos.items():
            logger.info(f"Adding monitoring for user: {username} ({photos_path})")
            
            # Create folder config for this user
            from ..config.schema import MonitoredFolder, FolderType
            
            folder_config = MonitoredFolder(
                path=str(photos_path),
                type=FolderType.NEXTCLOUD_USERS,
                enabled=True,
                schedule=None,  # Uses default schedule
                archive_moved=True,
                archive_path=None  # Default archive location
            )
            
            self.folder_watcher.add_folder(folder_config)
    
    def _on_new_photo(self, file_path: str, folder_config: MonitoredFolder):
        """
        Callback when a new photo is detected.
        
        Args:
            file_path: Path to the new photo
            folder_config: Configuration for the source folder
        """
        logger.info(f"New photo callback: {file_path}")
        
        # Add to processing queue
        queue_item = FileQueueItem(file_path, folder_config)
        self.file_queue.put(queue_item)
        
        logger.debug(f"Added to queue (size: {self.file_queue.qsize()})")
    
    def start(self):
        """Start the orchestrator."""
        if self._running:
            logger.warning("Orchestrator already running")
            return
        
        logger.info("Starting orchestrator...")
        
        self._running = True
        self._stop_event.clear()
        
        # Start folder watcher
        self.folder_watcher.start()
        
        # Start watcher thread (processes pending files)
        self._watcher_thread = Thread(target=self._watcher_loop, daemon=True)
        self._watcher_thread.start()
        
        # Start processor thread (processes queued files)
        self._processor_thread = Thread(target=self._processor_loop, daemon=True)
        self._processor_thread.start()
        
        logger.info("Orchestrator started")
    
    def stop(self):
        """Stop the orchestrator."""
        if not self._running:
            return
        
        logger.info("Stopping orchestrator...")
        
        self._running = False
        self._stop_event.set()
        
        # Stop folder watcher
        self.folder_watcher.stop()
        
        # Wait for threads to finish
        if self._watcher_thread:
            self._watcher_thread.join(timeout=10)
        
        if self._processor_thread:
            self._processor_thread.join(timeout=10)
        
        logger.info("Orchestrator stopped")
    
    def _watcher_loop(self):
        """Thread loop for processing pending files in the watcher."""
        logger.info("Watcher loop started")
        
        while self._running:
            try:
                # Process pending files every second
                self.folder_watcher.process_pending_files()
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in watcher loop: {e}")
                time.sleep(5)
        
        logger.info("Watcher loop stopped")
    
    def _processor_loop(self):
        """Thread loop for processing queued files."""
        logger.info("Processor loop started")
        
        batch: List[FileQueueItem] = []
        last_batch_time = time.time()
        
        while self._running:
            try:
                # Try to get item from queue
                try:
                    item = self.file_queue.get(timeout=1)
                    batch.append(item)
                except Empty:
                    pass
                
                # Process batch if full or timeout reached
                current_time = time.time()
                batch_ready = (
                    len(batch) >= self._batch_size or
                    (batch and current_time - last_batch_time >= self._batch_timeout)
                )
                
                if batch_ready and batch:
                    self._process_batch(batch)
                    batch.clear()
                    last_batch_time = time.time()
                
            except Exception as e:
                logger.error(f"Error in processor loop: {e}")
                time.sleep(5)
        
        # Process remaining batch on shutdown
        if batch:
            logger.info("Processing remaining batch on shutdown...")
            self._process_batch(batch)
        
        logger.info("Processor loop stopped")
    
    def _process_batch(self, batch: List[FileQueueItem]):
        """
        Process a batch of files.
        
        Args:
            batch: List of FileQueueItems to process
        """
        logger.info(f"Processing batch of {len(batch)} files...")
        
        results: List[SyncResult] = []
        
        # Process each file
        for item in batch:
            try:
                result = self.sync_engine.sync_file(
                    file_path=item.file_path,
                    folder_config=item.folder_config,
                    skip_dedupe=False
                )
                
                results.append(result)
                
                # Handle failures with retry
                if not result.status.value in ["completed", "skipped_duplicate"]:
                    if item.retry_count < item.max_retries:
                        item.retry_count += 1
                        logger.warning(f"Retrying failed file (attempt {item.retry_count})")
                        self.file_queue.put(item)
                
            except Exception as e:
                logger.error(f"Error processing file {item.file_path}: {e}")
        
        # Trigger indexing after batch
        if results:
            self._trigger_indexing(results)
        
        logger.info(f"Batch processed: {len(results)} files")
    
    def _trigger_indexing(self, results: List[SyncResult]):
        """
        Trigger indexing commands after processing files.
        
        Args:
            results: List of sync results
        """
        # Count successful moves
        moved_count = sum(1 for r in results if r.status.value == "completed")
        
        if moved_count == 0:
            logger.debug("No files moved, skipping indexing")
            return
        
        logger.info(f"Triggering indexing for {moved_count} moved files...")
        
        # Trigger PhotoPrism import
        try:
            photoprism_result = self.sync_engine.trigger_photoprism_index()
            
            if photoprism_result.success:
                logger.info("PhotoPrism import successful")
                
                # Trigger Nextcloud scan of albums directory
                self.sync_engine.trigger_nextcloud_scan(
                    path=self.config.photoprism.albums_path
                )
                
                # Trigger Memories index
                self.sync_engine.trigger_nextcloud_memories_index()
            else:
                logger.error("PhotoPrism import failed")
                
        except Exception as e:
            logger.error(f"Error triggering indexing: {e}")
    
    def manual_sync(self):
        """Manually trigger a sync of all monitored folders."""
        logger.info("Manual sync triggered")
        
        # TODO: Implement manual folder scan
        # This would scan all monitored folders and queue any new files
        
        logger.info("Manual sync completed")
    
    def get_status(self) -> dict:
        """
        Get current orchestrator status.
        
        Returns:
            Dictionary with status information
        """
        return {
            "running": self._running,
            "queue_size": self.file_queue.qsize(),
            "monitored_folders": list(self.folder_watcher.get_monitored_folders()),
            "sync_stats": self.sync_engine.get_stats(),
            "swarm_mode": self.docker_executor.is_swarm_mode()
        }
