"""
Docker Executor

Executes commands in Docker containers via docker exec or SSH proxies.
Automatically detects Docker vs. Swarm mode and uses appropriate method.

Author: Next_Prism Project
License: MIT
"""

import subprocess
import time
from typing import Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import get_logger
from ..config.schema import Config

logger = get_logger(__name__)


class ExecutionMode(Enum):
    """Execution mode for Docker commands."""
    DOCKER_EXEC = "docker_exec"
    SSH_PROXY = "ssh_proxy"


@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float


class DockerExecutor:
    """
    Execute commands in Docker containers.
    
    Supports both standard Docker (docker exec) and Swarm mode (SSH proxies).
    Automatically detects available method and falls back gracefully.
    """
    
    def __init__(self, config: Config):
        """
        Initialize Docker executor.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.mode = self._detect_execution_mode()
        
        logger.info(f"DockerExecutor initialized in {self.mode.value} mode")
    
    def _detect_execution_mode(self) -> ExecutionMode:
        """
        Detect whether to use docker exec or SSH proxies.
        
        Returns:
            ExecutionMode enum value
        """
        if self.config.docker.swarm_mode:
            # Check if SSH proxies are available
            if self._check_ssh_proxy_available():
                logger.info("SSH proxies detected, using SSH proxy mode")
                return ExecutionMode.SSH_PROXY
            else:
                logger.warning("Swarm mode enabled but SSH proxies not available, falling back to docker exec")
                return ExecutionMode.DOCKER_EXEC
        else:
            return ExecutionMode.DOCKER_EXEC
    
    def _check_ssh_proxy_available(self) -> bool:
        """
        Check if SSH proxy services are accessible.
        
        Returns:
            True if proxies are available
        """
        # TODO: Implement actual SSH connectivity check
        # For now, assume available if keys exist
        import os
        nextcloud_key = self.config.docker.proxy.nextcloud_key_path
        photoprism_key = self.config.docker.proxy.photoprism_key_path
        
        return os.path.exists(nextcloud_key) and os.path.exists(photoprism_key)
    
    def execute_command(
        self,
        container_name: str,
        command: List[str],
        timeout: int = 300,
        retry_count: int = 3
    ) -> CommandResult:
        """
        Execute command in Docker container.
        
        Args:
            container_name: Name of container (nextcloud or photoprism)
            command: Command to execute as list of arguments
            timeout: Command timeout in seconds
            retry_count: Number of retries on failure
        
        Returns:
            CommandResult with execution details
        """
        for attempt in range(retry_count):
            try:
                if self.mode == ExecutionMode.DOCKER_EXEC:
                    result = self._execute_docker_exec(container_name, command, timeout)
                else:
                    result = self._execute_via_ssh_proxy(container_name, command, timeout)
                
                if result.success or attempt == retry_count - 1:
                    return result
                
                # Retry with exponential backoff
                wait_time = 2 ** attempt
                logger.warning(f"Command failed, retrying in {wait_time}s (attempt {attempt + 1}/{retry_count})")
                time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Error executing command (attempt {attempt + 1}/{retry_count}): {e}")
                if attempt == retry_count - 1:
                    return CommandResult(
                        success=False,
                        stdout="",
                        stderr=str(e),
                        exit_code=-1,
                        execution_time=0.0
                    )
                time.sleep(2 ** attempt)
        
        return CommandResult(
            success=False,
            stdout="",
            stderr="Max retries exceeded",
            exit_code=-1,
            execution_time=0.0
        )
    
    def _execute_docker_exec(
        self,
        container_name: str,
        command: List[str],
        timeout: int
    ) -> CommandResult:
        """
        Execute command via docker exec.
        
        Args:
            container_name: Container name
            command: Command arguments
            timeout: Timeout in seconds
        
        Returns:
            CommandResult
        """
        # Get actual container name from config
        if container_name == "nextcloud":
            actual_container = self.config.docker.nextcloud_container
        elif container_name == "photoprism":
            actual_container = self.config.docker.photoprism_container
        else:
            raise ValueError(f"Unknown container: {container_name}")
        
        # Build docker exec command
        docker_cmd = ["docker", "exec", actual_container] + command
        
        logger.info(f"Executing: {' '.join(docker_cmd)}")
        start_time = time.time()
        
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            
            execution_time = time.time() - start_time
            
            success = result.returncode == 0
            if success:
                logger.info(f"Command completed successfully in {execution_time:.2f}s")
            else:
                logger.error(f"Command failed with exit code {result.returncode}")
            
            return CommandResult(
                success=success,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                execution_time=execution_time
            )
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            logger.error(f"Command timed out after {timeout}s")
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                exit_code=-1,
                execution_time=execution_time
            )
    
    def _execute_via_ssh_proxy(
        self,
        container_name: str,
        command: List[str],
        timeout: int
    ) -> CommandResult:
        """
        Execute command via SSH proxy service.
        
        Args:
            container_name: Container name (determines which proxy)
            command: Command arguments
            timeout: Timeout in seconds
        
        Returns:
            CommandResult
        """
        # Determine SSH key and proxy hostname
        if container_name == "nextcloud":
            key_path = self.config.docker.proxy.nextcloud_key_path
            proxy_host = "nextcloud-proxy"  # Service name in Swarm
        elif container_name == "photoprism":
            key_path = self.config.docker.proxy.photoprism_key_path
            proxy_host = "photoprism-proxy"
        else:
            raise ValueError(f"Unknown container: {container_name}")
        
        # Build SSH command
        ssh_cmd = [
            "ssh",
            "-i", key_path,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", f"ConnectTimeout={min(timeout, 30)}",
            f"root@{proxy_host}"
        ] + command
        
        logger.info(f"Executing via SSH proxy: {' '.join(command)}")
        start_time = time.time()
        
        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            
            execution_time = time.time() - start_time
            
            success = result.returncode == 0
            if success:
                logger.info(f"Command completed successfully in {execution_time:.2f}s")
            else:
                logger.error(f"Command failed with exit code {result.returncode}")
            
            return CommandResult(
                success=success,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                execution_time=execution_time
            )
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            logger.error(f"SSH command timed out after {timeout}s")
            return CommandResult(
                success=False,
                stdout="",
                stderr=f"SSH command timed out after {timeout}s",
                exit_code=-1,
                execution_time=execution_time
            )
    
    def test_connection(self, container_name: str) -> Tuple[bool, str]:
        """
        Test connection to container.
        
        Args:
            container_name: Container to test (nextcloud or photoprism)
        
        Returns:
            Tuple of (success, message)
        """
        try:
            if container_name == "nextcloud":
                # Test Nextcloud with occ status
                result = self.execute_command("nextcloud", ["php", "occ", "status"], timeout=30, retry_count=1)
            elif container_name == "photoprism":
                # Test PhotoPrism with version command
                result = self.execute_command("photoprism", ["photoprism", "version"], timeout=30, retry_count=1)
            else:
                return False, f"Unknown container: {container_name}"
            
            if result.success:
                return True, f"Successfully connected to {container_name}"
            else:
                return False, f"Connection failed: {result.stderr}"
                
        except Exception as e:
            logger.error(f"Error testing connection to {container_name}: {e}")
            return False, str(e)
