"""
SSH Proxy Client for Docker Swarm
==================================

This module provides SSH-based proxy communication for executing Docker commands
across Swarm nodes where direct docker exec is not available.

The SSHProxyClient maintains persistent SSH connections to lightweight proxy containers
that validate and execute whitelisted commands on target containers.

Architecture:
- Connection pooling: Reuse SSH connections across multiple commands
- Automatic reconnection: Detect and recover from connection failures
- Thread-safe: Support concurrent command execution
- Timeout handling: Prevent hung operations

Security:
- Keypair authentication only (ED25519)
- Command validation at proxy level
- No shell access (forced command execution)
- Connection encryption (SSH)

Author: Next_Prism Project
License: MIT
"""

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import paramiko
from paramiko import SSHClient, AutoAddPolicy, RSAKey, Ed25519Key


logger = logging.getLogger(__name__)


@dataclass
class SSHConnection:
    """Represents a pooled SSH connection."""
    client: SSHClient
    host: str
    port: int
    last_used: float
    in_use: bool = False
    error_count: int = 0


class SSHProxyClient:
    """
    SSH client for communicating with Docker Swarm proxy services.
    
    Maintains a pool of persistent SSH connections to proxy containers,
    automatically reconnects on failure, and provides thread-safe command execution.
    
    Example:
        ```python
        proxy = SSHProxyClient(
            private_key_path="/run/secrets/nextcloud_proxy_privkey",
            connection_timeout=10,
            max_connections=5
        )
        
        success, stdout, stderr = proxy.execute_command(
            host="nextcloud-proxy",
            port=2222,
            command="php occ files:scan --all"
        )
        ```
    """
    
    def __init__(
        self,
        private_key_path: str,
        connection_timeout: int = 10,
        command_timeout: int = 300,
        max_connections: int = 5,
        max_retries: int = 3,
        connection_idle_timeout: int = 300
    ):
        """
        Initialize SSH proxy client.
        
        Args:
            private_key_path: Path to ED25519 private key file
            connection_timeout: Timeout for establishing connections (seconds)
            command_timeout: Timeout for command execution (seconds)
            max_connections: Maximum pooled connections per host
            max_retries: Maximum retry attempts for failed operations
            connection_idle_timeout: Close idle connections after this time (seconds)
        """
        self.private_key_path = Path(private_key_path)
        self.connection_timeout = connection_timeout
        self.command_timeout = command_timeout
        self.max_connections = max_connections
        self.max_retries = max_retries
        self.connection_idle_timeout = connection_idle_timeout
        
        # Connection pool: (host, port) -> List[SSHConnection]
        self._pool: Dict[Tuple[str, int], list[SSHConnection]] = {}
        self._pool_lock = threading.Lock()
        
        # Private key (loaded once)
        self._private_key: Optional[Ed25519Key] = None
        self._key_lock = threading.Lock()
        
        logger.info(
            f"SSH proxy client initialized: key={self.private_key_path}, "
            f"timeout={self.connection_timeout}s, max_conn={self.max_connections}"
        )
    
    def _load_private_key(self) -> Ed25519Key:
        """
        Load ED25519 private key from file.
        
        Returns:
            Loaded private key
            
        Raises:
            FileNotFoundError: Key file not found
            paramiko.SSHException: Invalid key format
        """
        with self._key_lock:
            if self._private_key is None:
                if not self.private_key_path.exists():
                    raise FileNotFoundError(
                        f"Private key not found: {self.private_key_path}"
                    )
                
                logger.info(f"Loading private key: {self.private_key_path}")
                self._private_key = Ed25519Key.from_private_key_file(
                    str(self.private_key_path)
                )
                logger.info("Private key loaded successfully")
            
            return self._private_key
    
    def _get_connection(self, host: str, port: int) -> SSHConnection:
        """
        Get or create SSH connection from pool.
        
        Args:
            host: Proxy hostname or IP
            port: SSH port (typically 2222)
            
        Returns:
            Available SSH connection
            
        Raises:
            Exception: Connection failed after retries
        """
        pool_key = (host, port)
        
        with self._pool_lock:
            # Check for existing idle connection
            if pool_key in self._pool:
                for conn in self._pool[pool_key]:
                    if not conn.in_use:
                        # Test if connection is still alive
                        try:
                            transport = conn.client.get_transport()
                            if transport and transport.is_active():
                                conn.in_use = True
                                conn.last_used = time.time()
                                conn.error_count = 0
                                logger.debug(f"Reusing connection to {host}:{port}")
                                return conn
                        except Exception as e:
                            logger.debug(f"Stale connection detected: {e}")
                            # Will be cleaned up and recreated below
            
            # Clean up stale/idle connections
            self._cleanup_connections(pool_key)
            
            # Create new connection if under limit
            if pool_key not in self._pool:
                self._pool[pool_key] = []
            
            if len(self._pool[pool_key]) < self.max_connections:
                try:
                    conn = self._create_connection(host, port)
                    self._pool[pool_key].append(conn)
                    logger.info(
                        f"Created new SSH connection to {host}:{port} "
                        f"(pool size: {len(self._pool[pool_key])})"
                    )
                    return conn
                except Exception as e:
                    logger.error(f"Failed to create connection to {host}:{port}: {e}")
                    raise
            
            # Wait for available connection
            logger.warning(
                f"Connection pool full for {host}:{port}, "
                f"waiting for available connection..."
            )
        
        # Wait outside lock (to allow connections to be released)
        for attempt in range(self.max_retries):
            time.sleep(1)
            with self._pool_lock:
                for conn in self._pool[pool_key]:
                    if not conn.in_use:
                        conn.in_use = True
                        conn.last_used = time.time()
                        return conn
        
        raise Exception(
            f"No available connections to {host}:{port} after "
            f"{self.max_retries} retries"
        )
    
    def _create_connection(self, host: str, port: int) -> SSHConnection:
        """
        Create new SSH connection to proxy.
        
        Args:
            host: Proxy hostname or IP
            port: SSH port
            
        Returns:
            New SSH connection
            
        Raises:
            Exception: Connection failed
        """
        client = SSHClient()
        client.set_missing_host_key_policy(AutoAddPolicy())
        
        pkey = self._load_private_key()
        
        logger.info(f"Connecting to SSH proxy: {host}:{port}")
        client.connect(
            hostname=host,
            port=port,
            username="proxyuser",
            pkey=pkey,
            timeout=self.connection_timeout,
            look_for_keys=False,
            allow_agent=False
        )
        
        return SSHConnection(
            client=client,
            host=host,
            port=port,
            last_used=time.time(),
            in_use=True,
            error_count=0
        )
    
    def _release_connection(self, conn: SSHConnection):
        """Mark connection as available for reuse."""
        with self._pool_lock:
            conn.in_use = False
            conn.last_used = time.time()
    
    def _cleanup_connections(self, pool_key: Optional[Tuple[str, int]] = None):
        """
        Clean up stale or idle connections.
        
        Args:
            pool_key: Specific pool to clean, or None for all pools
        """
        now = time.time()
        keys_to_clean = [pool_key] if pool_key else list(self._pool.keys())
        
        for key in keys_to_clean:
            if key not in self._pool:
                continue
            
            connections = self._pool[key]
            cleaned = []
            
            for conn in connections:
                # Remove if idle too long or transport is dead
                transport = conn.client.get_transport()
                is_stale = (
                    not conn.in_use and 
                    (now - conn.last_used) > self.connection_idle_timeout
                )
                is_dead = not transport or not transport.is_active()
                
                if is_stale or is_dead:
                    try:
                        conn.client.close()
                        logger.debug(
                            f"Closed connection to {conn.host}:{conn.port} "
                            f"(stale={is_stale}, dead={is_dead})"
                        )
                    except Exception as e:
                        logger.debug(f"Error closing connection: {e}")
                else:
                    cleaned.append(conn)
            
            if cleaned:
                self._pool[key] = cleaned
            else:
                del self._pool[key]
    
    def execute_command(
        self,
        host: str,
        port: int,
        command: str,
        timeout: Optional[int] = None
    ) -> Tuple[bool, str, str]:
        """
        Execute command on proxy (which executes on target container).
        
        The command is sent to the SSH proxy, which validates it against
        the whitelist and executes it via docker exec on the target container.
        
        Args:
            host: Proxy hostname or IP
            port: SSH port (typically 2222)
            command: Command to execute (e.g., "php occ files:scan --all")
            timeout: Command timeout in seconds (overrides default)
            
        Returns:
            Tuple of (success, stdout, stderr)
            
        Example:
            ```python
            success, stdout, stderr = client.execute_command(
                host="nextcloud-proxy",
                port=2222,
                command="php occ status"
            )
            if success:
                print(f"Status: {stdout}")
            else:
                print(f"Error: {stderr}")
            ```
        """
        timeout = timeout or self.command_timeout
        conn = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # Get connection from pool
                conn = self._get_connection(host, port)
                
                logger.info(
                    f"Executing command on {host}:{port} (attempt {attempt}): {command}"
                )
                
                # Execute command
                stdin, stdout, stderr = conn.client.exec_command(
                    command,
                    timeout=timeout
                )
                
                # Read output
                exit_code = stdout.channel.recv_exit_status()
                stdout_data = stdout.read().decode('utf-8', errors='replace')
                stderr_data = stderr.read().decode('utf-8', errors='replace')
                
                success = exit_code == 0
                
                if success:
                    logger.info(
                        f"Command succeeded on {host}:{port}: "
                        f"{len(stdout_data)} bytes output"
                    )
                    conn.error_count = 0
                else:
                    logger.warning(
                        f"Command failed on {host}:{port} with exit code {exit_code}: "
                        f"{stderr_data[:200]}"
                    )
                    conn.error_count += 1
                
                return success, stdout_data, stderr_data
                
            except Exception as e:
                logger.error(
                    f"SSH command execution failed on {host}:{port} "
                    f"(attempt {attempt}/{self.max_retries}): {e}"
                )
                
                if conn:
                    conn.error_count += 1
                    # Close connection if too many errors
                    if conn.error_count >= 3:
                        try:
                            conn.client.close()
                            with self._pool_lock:
                                pool_key = (host, port)
                                if pool_key in self._pool:
                                    self._pool[pool_key].remove(conn)
                            logger.info(
                                f"Closed connection to {host}:{port} "
                                f"after {conn.error_count} errors"
                            )
                        except Exception as close_err:
                            logger.debug(f"Error closing connection: {close_err}")
                
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return False, "", str(e)
                    
            finally:
                if conn:
                    self._release_connection(conn)
        
        return False, "", "Maximum retries exceeded"
    
    def close_all(self):
        """Close all pooled connections."""
        with self._pool_lock:
            for pool_key, connections in self._pool.items():
                for conn in connections:
                    try:
                        conn.client.close()
                        logger.debug(f"Closed connection to {conn.host}:{conn.port}")
                    except Exception as e:
                        logger.debug(f"Error closing connection: {e}")
            
            self._pool.clear()
            logger.info("All SSH connections closed")
    
    def get_pool_stats(self) -> Dict[str, int]:
        """
        Get connection pool statistics.
        
        Returns:
            Dictionary with pool statistics
        """
        with self._pool_lock:
            total_connections = sum(len(conns) for conns in self._pool.values())
            active_connections = sum(
                sum(1 for conn in conns if conn.in_use)
                for conns in self._pool.values()
            )
            
            return {
                "total_hosts": len(self._pool),
                "total_connections": total_connections,
                "active_connections": active_connections,
                "idle_connections": total_connections - active_connections
            }
