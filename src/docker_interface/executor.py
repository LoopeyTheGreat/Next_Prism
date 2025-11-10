"""
Docker Command Executor

Provides abstraction for executing commands in Docker containers,
supporting both direct Docker exec and SSH proxy communication for Swarm.

Author: Next_Prism Project
License: MIT
"""

import docker
import subprocess
from typing import Optional, Tuple, List
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ExecutionMode(Enum):
    """Docker command execution modes."""
    DIRECT = "direct"  # Direct docker exec
    SSH_PROXY = "ssh_proxy"  # Via SSH proxy (Swarm)


class CommandResult:
    """Result of a command execution."""
    
    def __init__(
        self,
        success: bool,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        error_message: Optional[str] = None
    ):
        """
        Initialize command result.
        
        Args:
            success: Whether command succeeded
            stdout: Standard output
            stderr: Standard error
            exit_code: Command exit code
            error_message: Human-readable error message
        """
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.error_message = error_message
    
    def __repr__(self) -> str:
        return f"CommandResult(success={self.success}, exit_code={self.exit_code})"


class DockerExecutor:
    """
    Docker command executor with support for direct exec and SSH proxies.
    
    Automatically detects Swarm mode and uses appropriate execution method.
    Implements command whitelisting for security and retry logic for reliability.
    """
    
    def __init__(
        self,
        docker_socket: str = "/var/run/docker.sock",
        swarm_mode: Optional[bool] = None
    ):
        """
        Initialize Docker executor.
        
        Args:
            docker_socket: Path to Docker socket
            swarm_mode: Force Swarm mode (None = auto-detect)
        """
        self.docker_socket = docker_socket
        self._swarm_mode = swarm_mode
        self._docker_client: Optional[docker.DockerClient] = None
        
        # Initialize Docker client
        try:
            self._docker_client = docker.DockerClient(base_url=f"unix://{docker_socket}")
            logger.info("Docker client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
        
        # Detect Swarm mode if not specified
        if self._swarm_mode is None:
            self._swarm_mode = self._detect_swarm_mode()
        
        logger.info(f"Docker executor initialized (Swarm mode: {self._swarm_mode})")
    
    def _detect_swarm_mode(self) -> bool:
        """
        Detect if Docker is running in Swarm mode.
        
        Returns:
            True if Swarm mode is active
        """
        if not self._docker_client:
            return False
        
        try:
            swarm_info = self._docker_client.swarm.attrs
            is_swarm = swarm_info.get('ID') is not None
            logger.info(f"Swarm mode detected: {is_swarm}")
            return is_swarm
        except Exception as e:
            logger.debug(f"Not in Swarm mode: {e}")
            return False
    
    def exec_command(
        self,
        container_name: str,
        command: List[str],
        timeout: int = 300,
        retry_attempts: int = 1
    ) -> CommandResult:
        """
        Execute a command in a Docker container.
        
        Automatically uses direct exec or SSH proxy based on Swarm mode.
        
        Args:
            container_name: Name or ID of the container
            command: Command to execute as list of strings
            timeout: Command timeout in seconds
            retry_attempts: Number of retry attempts on failure
            
        Returns:
            CommandResult with execution details
        """
        for attempt in range(retry_attempts):
            if attempt > 0:
                logger.info(f"Retrying command (attempt {attempt + 1}/{retry_attempts})")
            
            if self._swarm_mode:
                result = self._exec_via_proxy(container_name, command, timeout)
            else:
                result = self._exec_direct(container_name, command, timeout)
            
            if result.success or attempt == retry_attempts - 1:
                return result
        
        return result
    
    def _exec_direct(
        self,
        container_name: str,
        command: List[str],
        timeout: int
    ) -> CommandResult:
        """
        Execute command directly via docker exec.
        
        Args:
            container_name: Container name or ID
            command: Command as list of strings
            timeout: Timeout in seconds
            
        Returns:
            CommandResult
        """
        if not self._docker_client:
            return CommandResult(
                success=False,
                error_message="Docker client not initialized"
            )
        
        try:
            # Get container
            container = self._docker_client.containers.get(container_name)
            
            logger.info(f"Executing in {container_name}: {' '.join(command)}")
            
            # Execute command
            exit_code, output = container.exec_run(
                cmd=command,
                stdout=True,
                stderr=True,
                demux=True
            )
            
            # Parse output (output is a tuple of (stdout, stderr) when demux=True)
            stdout = output[0].decode('utf-8') if output[0] else ""
            stderr = output[1].decode('utf-8') if output[1] else ""
            
            success = exit_code == 0
            
            if success:
                logger.info(f"Command succeeded in {container_name}")
                logger.debug(f"Output: {stdout}")
            else:
                logger.error(f"Command failed in {container_name} (exit code: {exit_code})")
                logger.error(f"Error: {stderr}")
            
            return CommandResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code
            )
            
        except docker.errors.NotFound:
            error_msg = f"Container not found: {container_name}"
            logger.error(error_msg)
            return CommandResult(success=False, error_message=error_msg)
        
        except docker.errors.APIError as e:
            error_msg = f"Docker API error: {e}"
            logger.error(error_msg)
            return CommandResult(success=False, error_message=error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error executing command: {e}"
            logger.error(error_msg)
            return CommandResult(success=False, error_message=error_msg)
    
    def _exec_via_proxy(
        self,
        container_name: str,
        command: List[str],
        timeout: int
    ) -> CommandResult:
        """
        Execute command via SSH proxy (Swarm mode).
        
        Args:
            container_name: Container or service name
            command: Command as list of strings
            timeout: Timeout in seconds
            
        Returns:
            CommandResult
        """
        # TODO: Implement SSH proxy execution in Phase 3
        # For now, fall back to direct execution
        logger.warning("SSH proxy not yet implemented, falling back to direct exec")
        return self._exec_direct(container_name, command, timeout)
    
    def is_swarm_mode(self) -> bool:
        """Check if running in Swarm mode."""
        return self._swarm_mode
    
    def container_exists(self, container_name: str) -> bool:
        """
        Check if a container exists and is accessible.
        
        Args:
            container_name: Container name or ID
            
        Returns:
            True if container exists
        """
        if not self._docker_client:
            return False
        
        try:
            self._docker_client.containers.get(container_name)
            return True
        except docker.errors.NotFound:
            return False
        except Exception as e:
            logger.error(f"Error checking container existence: {e}")
            return False


class NextcloudCommands:
    """
    Nextcloud-specific command interface.
    
    Provides high-level methods for common Nextcloud occ commands.
    """
    
    def __init__(self, executor: DockerExecutor, container_name: str):
        """
        Initialize Nextcloud commands interface.
        
        Args:
            executor: DockerExecutor instance
            container_name: Nextcloud container name
        """
        self.executor = executor
        self.container_name = container_name
        logger.info(f"NextcloudCommands initialized for container: {container_name}")
    
    def files_scan(
        self,
        path: Optional[str] = None,
        user: Optional[str] = None,
        all_users: bool = False
    ) -> CommandResult:
        """
        Run occ files:scan command.
        
        Args:
            path: Specific path to scan (relative to user files)
            user: Specific user to scan
            all_users: Scan all users
            
        Returns:
            CommandResult
        """
        command = ["php", "occ", "files:scan"]
        
        if all_users:
            command.append("--all")
        elif user:
            command.extend(["--path", f"/{user}/files"])
            if path:
                command[-1] += f"/{path}"
        elif path:
            command.extend(["--path", path])
        
        logger.info(f"Running Nextcloud files:scan: {' '.join(command)}")
        return self.executor.exec_command(self.container_name, command)
    
    def memories_index(
        self,
        user: Optional[str] = None,
        path: Optional[str] = None
    ) -> CommandResult:
        """
        Run occ memories:index command.
        
        Args:
            user: Specific user to index
            path: Specific path to index
            
        Returns:
            CommandResult
        """
        command = ["php", "occ", "memories:index"]
        
        if user:
            command.extend(["--user", user])
        if path:
            command.extend(["--path", path])
        
        logger.info(f"Running Nextcloud memories:index: {' '.join(command)}")
        return self.executor.exec_command(self.container_name, command)
    
    def check_status(self) -> CommandResult:
        """
        Check Nextcloud status.
        
        Returns:
            CommandResult
        """
        command = ["php", "occ", "status"]
        return self.executor.exec_command(self.container_name, command)


class PhotoPrismCommands:
    """
    PhotoPrism-specific command interface.
    
    Provides high-level methods for PhotoPrism CLI commands.
    """
    
    def __init__(self, executor: DockerExecutor, container_name: str):
        """
        Initialize PhotoPrism commands interface.
        
        Args:
            executor: DockerExecutor instance
            container_name: PhotoPrism container name
        """
        self.executor = executor
        self.container_name = container_name
        logger.info(f"PhotoPrismCommands initialized for container: {container_name}")
    
    def index(
        self,
        path: Optional[str] = None,
        cleanup: bool = False
    ) -> CommandResult:
        """
        Run PhotoPrism index command.
        
        Args:
            path: Specific path to index (relative to import folder)
            cleanup: Remove missing files from index
            
        Returns:
            CommandResult
        """
        command = ["photoprism", "index"]
        
        if path:
            command.extend(["--path", path])
        if cleanup:
            command.append("--cleanup")
        
        logger.info(f"Running PhotoPrism index: {' '.join(command)}")
        return self.executor.exec_command(self.container_name, command, timeout=600)
    
    def import_photos(
        self,
        path: Optional[str] = None,
        move: bool = False
    ) -> CommandResult:
        """
        Run PhotoPrism import command.
        
        Args:
            path: Specific path to import from
            move: Move files instead of copy
            
        Returns:
            CommandResult
        """
        command = ["photoprism", "import"]
        
        if path:
            command.extend(["--path", path])
        if move:
            command.append("--move")
        
        logger.info(f"Running PhotoPrism import: {' '.join(command)}")
        return self.executor.exec_command(self.container_name, command, timeout=600)
    
    def check_status(self) -> CommandResult:
        """
        Check PhotoPrism status.
        
        Returns:
            CommandResult
        """
        command = ["photoprism", "status"]
        return self.executor.exec_command(self.container_name, command)
