"""
Nextcloud Commands

Wrapper for Nextcloud occ commands via Docker.

Author: Next_Prism Project
License: MIT
"""

from pathlib import Path
from typing import Optional, List

from ..utils.logger import get_logger
from .docker_executor import DockerExecutor, CommandResult

logger = get_logger(__name__)


class NextcloudCommands:
    """
    Nextcloud command wrapper using occ CLI.
    
    Common commands:
    - files:scan: Scan files for a user or path
    - memories:index: Trigger Memories app indexing
    """
    
    def __init__(self, executor: DockerExecutor):
        """
        Initialize Nextcloud commands.
        
        Args:
            executor: DockerExecutor instance
        """
        self.executor = executor
        logger.info("NextcloudCommands initialized")
    
    def scan_user_files(self, username: str, path: Optional[str] = None) -> CommandResult:
        """
        Scan files for a specific user.
        
        Args:
            username: Nextcloud username
            path: Optional specific path to scan (relative to user files)
        
        Returns:
            CommandResult
        """
        cmd = ["php", "occ", "files:scan"]
        
        if path:
            cmd.extend(["--path", f"/{username}/files/{path}"])
        else:
            cmd.append(username)
        
        logger.info(f"Scanning files for user {username}" + (f" path {path}" if path else ""))
        return self.executor.execute_command("nextcloud", cmd, timeout=300)
    
    def scan_all_users(self) -> CommandResult:
        """
        Scan files for all users.
        
        Returns:
            CommandResult
        """
        cmd = ["php", "occ", "files:scan", "--all"]
        logger.info("Scanning files for all users")
        return self.executor.execute_command("nextcloud", cmd, timeout=600)
    
    def trigger_memories_index(self, username: Optional[str] = None) -> CommandResult:
        """
        Trigger Memories app indexing.
        
        Args:
            username: Optional specific user to index
        
        Returns:
            CommandResult
        """
        cmd = ["php", "occ", "memories:index"]
        
        if username:
            cmd.append(username)
            logger.info(f"Triggering Memories index for user {username}")
        else:
            logger.info("Triggering Memories index for all users")
        
        return self.executor.execute_command("nextcloud", cmd, timeout=600)
    
    def get_status(self) -> CommandResult:
        """
        Get Nextcloud status.
        
        Returns:
            CommandResult with status information
        """
        cmd = ["php", "occ", "status"]
        return self.executor.execute_command("nextcloud", cmd, timeout=30)
    
    def maintenance_mode(self, enable: bool) -> CommandResult:
        """
        Enable or disable maintenance mode.
        
        Args:
            enable: True to enable, False to disable
        
        Returns:
            CommandResult
        """
        mode = "on" if enable else "off"
        cmd = ["php", "occ", "maintenance:mode", f"--{mode}"]
        logger.info(f"Setting maintenance mode: {mode}")
        return self.executor.execute_command("nextcloud", cmd, timeout=30)
    
    def list_users(self) -> List[str]:
        """
        Get list of Nextcloud users.
        
        Returns:
            List of usernames
        """
        cmd = ["php", "occ", "user:list", "--output=json"]
        result = self.executor.execute_command("nextcloud", cmd, timeout=30)
        
        if result.success:
            try:
                import json
                users_data = json.loads(result.stdout)
                return list(users_data.keys())
            except Exception as e:
                logger.error(f"Error parsing user list: {e}")
                return []
        else:
            logger.error("Failed to retrieve user list")
            return []
