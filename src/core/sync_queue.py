"""
Sync Queue

Thread-safe queue for pending file sync operations with priority handling.

Author: Next_Prism Project
License: MIT
"""

import queue
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
import json

from ..utils.logger import get_logger

logger = get_logger(__name__)


class Priority(IntEnum):
    """Priority levels for sync operations."""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    MANUAL = 0  # Manual triggers get highest priority


@dataclass(order=True)
class SyncItem:
    """Item in sync queue with priority."""
    priority: int = field(compare=True)
    file_path: Path = field(compare=False)
    source_label: str = field(compare=False)
    timestamp: datetime = field(default_factory=datetime.now, compare=False)
    manual_trigger: bool = field(default=False, compare=False)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'priority': self.priority,
            'file_path': str(self.file_path),
            'source_label': self.source_label,
            'timestamp': self.timestamp.isoformat(),
            'manual_trigger': self.manual_trigger
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SyncItem':
        """Create from dictionary."""
        return cls(
            priority=data['priority'],
            file_path=Path(data['file_path']),
            source_label=data['source_label'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            manual_trigger=data.get('manual_trigger', False)
        )


class SyncQueue:
    """
    Thread-safe priority queue for sync operations.
    
    Features:
    - Priority-based ordering
    - Persistence (can save/load queue state)
    - Queue inspection
    - Statistics tracking
    """
    
    def __init__(self, max_size: int = 10000, persistence_file: Optional[str] = None):
        """
        Initialize sync queue.
        
        Args:
            max_size: Maximum queue size
            persistence_file: Optional file path for queue persistence
        """
        self._queue = queue.PriorityQueue(maxsize=max_size)
        self.max_size = max_size
        self.persistence_file = persistence_file
        
        # Statistics
        self._total_enqueued = 0
        self._total_processed = 0
        
        # Load persisted queue if available
        if persistence_file:
            self._load_from_file()
        
        logger.info(f"SyncQueue initialized (max_size={max_size})")
    
    def enqueue(
        self,
        file_path: Path,
        source_label: str,
        priority: Priority = Priority.NORMAL,
        manual: bool = False
    ) -> bool:
        """
        Add item to queue.
        
        Args:
            file_path: Path to file
            source_label: Source folder label
            priority: Priority level
            manual: Whether this is a manual trigger
        
        Returns:
            True if successfully enqueued
        """
        try:
            if manual:
                priority = Priority.MANUAL
            
            item = SyncItem(
                priority=priority.value,
                file_path=file_path,
                source_label=source_label,
                manual_trigger=manual
            )
            
            self._queue.put_nowait(item)
            self._total_enqueued += 1
            
            logger.info(f"Enqueued: {file_path.name} (priority={priority.name}, queue_size={self.size()})")
            return True
            
        except queue.Full:
            logger.error(f"Queue full, cannot enqueue {file_path.name}")
            return False
        except Exception as e:
            logger.error(f"Error enqueueing {file_path}: {e}")
            return False
    
    def dequeue(self, timeout: Optional[float] = None) -> Optional[SyncItem]:
        """
        Remove and return item from queue.
        
        Args:
            timeout: Optional timeout in seconds (None = blocking)
        
        Returns:
            SyncItem or None if queue is empty/timeout
        """
        try:
            item = self._queue.get(timeout=timeout)
            self._total_processed += 1
            logger.debug(f"Dequeued: {item.file_path.name} (queue_size={self.size()})")
            return item
        except queue.Empty:
            return None
        except Exception as e:
            logger.error(f"Error dequeuing: {e}")
            return None
    
    def size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()
    
    def is_full(self) -> bool:
        """Check if queue is full."""
        return self._queue.full()
    
    def clear(self):
        """Clear all items from queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        logger.info("Queue cleared")
    
    def get_items(self, max_items: int = 100) -> List[dict]:
        """
        Get snapshot of queue items without removing them.
        
        Warning: This creates a temporary copy of the queue.
        
        Args:
            max_items: Maximum number of items to return
        
        Returns:
            List of item dictionaries
        """
        items = []
        temp_items = []
        
        # Temporarily drain queue
        while not self._queue.empty() and len(items) < max_items:
            try:
                item = self._queue.get_nowait()
                items.append(item.to_dict())
                temp_items.append(item)
            except queue.Empty:
                break
        
        # Restore items to queue
        for item in temp_items:
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                logger.error("Queue full during restoration")
                break
        
        return items
    
    def get_statistics(self) -> dict:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            'current_size': self.size(),
            'max_size': self.max_size,
            'total_enqueued': self._total_enqueued,
            'total_processed': self._total_processed,
            'is_full': self.is_full(),
            'is_empty': self.is_empty()
        }
    
    def save_to_file(self):
        """Save queue state to file."""
        if not self.persistence_file:
            return
        
        try:
            items = self.get_items(max_items=self.max_size)
            data = {
                'items': items,
                'statistics': {
                    'total_enqueued': self._total_enqueued,
                    'total_processed': self._total_processed
                }
            }
            
            with open(self.persistence_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved queue state with {len(items)} items")
            
        except Exception as e:
            logger.error(f"Error saving queue to file: {e}")
    
    def _load_from_file(self):
        """Load queue state from file."""
        try:
            import os
            if not os.path.exists(self.persistence_file):
                return
            
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)
            
            # Restore items
            for item_data in data.get('items', []):
                try:
                    item = SyncItem.from_dict(item_data)
                    self._queue.put_nowait(item)
                except Exception as e:
                    logger.warning(f"Could not restore queue item: {e}")
            
            # Restore statistics
            stats = data.get('statistics', {})
            self._total_enqueued = stats.get('total_enqueued', 0)
            self._total_processed = stats.get('total_processed', 0)
            
            logger.info(f"Loaded queue state with {self.size()} items")
            
        except Exception as e:
            logger.warning(f"Could not load queue from file: {e}")
