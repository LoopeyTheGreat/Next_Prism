"""
Sync Engine Module

Core synchronization logic including deduplication and file moving.

Author: Next_Prism Project
License: MIT
"""

from .deduplicator import Deduplicator, DuplicateCheckResult
from .file_mover import FileMover, MoveResult

__all__ = ['Deduplicator', 'DuplicateCheckResult', 'FileMover', 'MoveResult']
