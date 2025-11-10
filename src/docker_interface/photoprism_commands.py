"""
PhotoPrism Commands

Wrapper for PhotoPrism CLI commands via Docker.

Author: Next_Prism Project
License: MIT
"""

from typing import Optional

from ..utils.logger import get_logger
from .docker_executor import DockerExecutor, CommandResult

logger = get_logger(__name__)


class PhotoPrismCommands:
    """
    PhotoPrism command wrapper using CLI.
    
    Common commands:
    - import: Import photos from import directory
    - index: Index photos in originals directory
    - start: Start PhotoPrism server
    """
    
    def __init__(self, executor: DockerExecutor):
        """
        Initialize PhotoPrism commands.
        
        Args:
            executor: DockerExecutor instance
        """
        self.executor = executor
        logger.info("PhotoPrismCommands initialized")
    
    def import_photos(self, move: bool = True) -> CommandResult:
        """
        Import photos from import directory.
        
        Args:
            move: True to move files, False to copy
        
        Returns:
            CommandResult
        """
        cmd = ["photoprism", "import"]
        
        if move:
            # Move files instead of copying
            cmd.append("--move")
        
        logger.info(f"Importing photos ({'move' if move else 'copy'} mode)")
        return self.executor.execute_command("photoprism", cmd, timeout=600)
    
    def index_photos(self, path: Optional[str] = None) -> CommandResult:
        """
        Index photos in originals directory.
        
        Args:
            path: Optional specific path to index
        
        Returns:
            CommandResult
        """
        cmd = ["photoprism", "index"]
        
        if path:
            cmd.append(path)
            logger.info(f"Indexing photos at path: {path}")
        else:
            logger.info("Indexing all photos")
        
        return self.executor.execute_command("photoprism", cmd, timeout=600)
    
    def get_version(self) -> CommandResult:
        """
        Get PhotoPrism version.
        
        Returns:
            CommandResult with version information
        """
        cmd = ["photoprism", "version"]
        return self.executor.execute_command("photoprism", cmd, timeout=30)
    
    def get_status(self) -> CommandResult:
        """
        Get PhotoPrism status.
        
        Returns:
            CommandResult with status information
        """
        cmd = ["photoprism", "status"]
        return self.executor.execute_command("photoprism", cmd, timeout=30)
    
    def optimize_thumbnails(self) -> CommandResult:
        """
        Optimize thumbnails.
        
        Returns:
            CommandResult
        """
        cmd = ["photoprism", "thumbnails", "--force"]
        logger.info("Optimizing thumbnails")
        return self.executor.execute_command("photoprism", cmd, timeout=1800)
    
    def backup_database(self, output_path: str) -> CommandResult:
        """
        Backup database.
        
        Args:
            output_path: Path for backup file
        
        Returns:
            CommandResult
        """
        cmd = ["photoprism", "backup", "--force", "--output", output_path]
        logger.info(f"Backing up database to {output_path}")
        return self.executor.execute_command("photoprism", cmd, timeout=300)
    
    def restore_database(self, backup_path: str) -> CommandResult:
        """
        Restore database from backup.
        
        Args:
            backup_path: Path to backup file
        
        Returns:
            CommandResult
        """
        cmd = ["photoprism", "restore", "--force", backup_path]
        logger.info(f"Restoring database from {backup_path}")
        return self.executor.execute_command("photoprism", cmd, timeout=300)
