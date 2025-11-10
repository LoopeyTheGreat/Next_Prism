"""
Docker Interface Module

Docker command execution interface for Nextcloud and PhotoPrism.

Author: Next_Prism Project
License: MIT
"""

from .docker_executor import DockerExecutor, CommandResult, ExecutionMode
from .nextcloud_commands import NextcloudCommands
from .photoprism_commands import PhotoPrismCommands

__all__ = [
    'DockerExecutor',
    'CommandResult',
    'ExecutionMode',
    'NextcloudCommands',
    'PhotoPrismCommands'
]

__version__ = "0.1.0"
