"""
Integration Tests for SSH Proxy Communication
==============================================

These tests validate SSH proxy functionality for Docker Swarm deployments.
Tests can run in two modes:
- Mock mode: Uses mock SSH server for CI/CD pipelines
- Live mode: Connects to actual proxy services for integration testing

Author: Next_Prism Project
License: MIT
"""

import pytest
import socket
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.docker_interface.ssh_proxy import SSHProxyClient, SSHConnection
from src.docker_interface.proxy_discovery import ProxyDiscovery, ProxyService


class TestSSHProxyClient:
    """Test SSH proxy client functionality."""
    
    @pytest.fixture
    def temp_key_file(self, tmp_path):
        """Create temporary ED25519 private key for testing."""
        # Generate test key using ssh-keygen
        key_path = tmp_path / "test_proxy_key"
        import subprocess
        result = subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", str(key_path), "-N", "", "-C", "test"],
            capture_output=True
        )
        if result.returncode == 0:
            return str(key_path)
        else:
            pytest.skip("ssh-keygen not available")
    
    def test_initialization(self, temp_key_file):
        """Test SSH proxy client initialization."""
        client = SSHProxyClient(
            private_key_path=temp_key_file,
            connection_timeout=10,
            max_connections=3
        )
        
        assert client.private_key_path == Path(temp_key_file)
        assert client.connection_timeout == 10
        assert client.max_connections == 3
        assert len(client._pool) == 0
    
    def test_missing_key_file(self):
        """Test handling of missing private key file."""
        with pytest.raises(FileNotFoundError):
            client = SSHProxyClient(private_key_path="/nonexistent/key")
            # Trigger key loading
            client._load_private_key()
    
    @patch('paramiko.SSHClient')
    def test_connection_creation(self, mock_ssh_client, temp_key_file):
        """Test SSH connection creation."""
        # Mock successful connection
        mock_client_instance = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client_instance.get_transport.return_value = mock_transport
        mock_ssh_client.return_value = mock_client_instance
        
        client = SSHProxyClient(
            private_key_path=temp_key_file,
            connection_timeout=5
        )
        
        # Create connection
        conn = client._create_connection("test-proxy", 2222)
        
        assert conn.host == "test-proxy"
        assert conn.port == 2222
        assert conn.in_use is True
        assert conn.error_count == 0
        
        # Verify connection was attempted
        mock_client_instance.connect.assert_called_once()
    
    @patch('paramiko.SSHClient')
    def test_connection_pooling(self, mock_ssh_client, temp_key_file):
        """Test connection pool management."""
        # Mock SSH client
        mock_client_instance = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client_instance.get_transport.return_value = mock_transport
        mock_ssh_client.return_value = mock_client_instance
        
        client = SSHProxyClient(
            private_key_path=temp_key_file,
            max_connections=2
        )
        
        # Get first connection
        conn1 = client._get_connection("test-proxy", 2222)
        assert len(client._pool[("test-proxy", 2222)]) == 1
        
        # Release and get again - should reuse
        client._release_connection(conn1)
        conn2 = client._get_connection("test-proxy", 2222)
        assert conn1 is conn2
        assert len(client._pool[("test-proxy", 2222)]) == 1
    
    @patch('paramiko.SSHClient')
    def test_command_execution(self, mock_ssh_client, temp_key_file):
        """Test command execution through proxy."""
        # Mock successful command execution
        mock_client_instance = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client_instance.get_transport.return_value = mock_transport
        
        # Mock exec_command return
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"Success output"
        mock_stderr.read.return_value = b""
        
        mock_client_instance.exec_command.return_value = (
            mock_stdin, mock_stdout, mock_stderr
        )
        mock_ssh_client.return_value = mock_client_instance
        
        client = SSHProxyClient(private_key_path=temp_key_file)
        
        # Execute command
        success, stdout, stderr = client.execute_command(
            host="test-proxy",
            port=2222,
            command="php occ status"
        )
        
        assert success is True
        assert stdout == "Success output"
        assert stderr == ""
        
        # Verify command was executed
        mock_client_instance.exec_command.assert_called_with(
            "php occ status",
            timeout=300  # Default timeout
        )
    
    @patch('paramiko.SSHClient')
    def test_command_failure(self, mock_ssh_client, temp_key_file):
        """Test handling of failed command execution."""
        # Mock failed command execution
        mock_client_instance = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client_instance.get_transport.return_value = mock_transport
        
        # Mock exec_command return with failure
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b"Command failed"
        
        mock_client_instance.exec_command.return_value = (
            mock_stdin, mock_stdout, mock_stderr
        )
        mock_ssh_client.return_value = mock_client_instance
        
        client = SSHProxyClient(private_key_path=temp_key_file)
        
        # Execute command
        success, stdout, stderr = client.execute_command(
            host="test-proxy",
            port=2222,
            command="php occ invalid:command"
        )
        
        assert success is False
        assert stderr == "Command failed"
    
    def test_connection_cleanup(self, temp_key_file):
        """Test cleanup of idle connections."""
        client = SSHProxyClient(
            private_key_path=temp_key_file,
            connection_idle_timeout=1  # 1 second for testing
        )
        
        # Create mock connection
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = False  # Simulate dead connection
        mock_client.get_transport.return_value = mock_transport
        
        conn = SSHConnection(
            client=mock_client,
            host="test",
            port=2222,
            last_used=time.time() - 10,  # 10 seconds ago
            in_use=False
        )
        
        client._pool[("test", 2222)] = [conn]
        
        # Clean up
        client._cleanup_connections()
        
        # Connection should be removed
        assert ("test", 2222) not in client._pool


class TestProxyDiscovery:
    """Test proxy service discovery."""
    
    @pytest.fixture
    def mock_docker_client(self):
        """Create mock Docker client."""
        client = Mock()
        client.services = Mock()
        return client
    
    def test_initialization(self, mock_docker_client):
        """Test proxy discovery initialization."""
        discovery = ProxyDiscovery(
            docker_client=mock_docker_client,
            cache_ttl=60,
            health_check_timeout=5
        )
        
        assert discovery.cache_ttl == 60
        assert discovery.health_check_timeout == 5
        assert len(discovery._cache) == 0
    
    def test_discover_proxy(self, mock_docker_client):
        """Test proxy service discovery."""
        # Mock service discovery
        mock_service = Mock()
        mock_service.name = "nextcloud-proxy"
        mock_docker_client.services.list.return_value = [mock_service]
        
        discovery = ProxyDiscovery(docker_client=mock_docker_client)
        
        # Mock DNS resolution and health check
        with patch.object(discovery, '_resolve_hostname', return_value="10.0.0.1"):
            with patch.object(discovery, '_check_health', return_value=True):
                proxy = discovery.discover_proxy("nextcloud")
        
        assert proxy is not None
        assert proxy.service_name == "nextcloud-proxy"
        assert proxy.service_type == "nextcloud"
        assert proxy.hostname == "nextcloud-proxy"
        assert proxy.port == 2222
        assert proxy.is_healthy is True
        
        # Should be cached
        assert "nextcloud" in discovery._cache
    
    def test_cache_validity(self, mock_docker_client):
        """Test cache TTL and validation."""
        discovery = ProxyDiscovery(
            docker_client=mock_docker_client,
            cache_ttl=2  # 2 seconds for testing
        )
        
        # Create cached proxy
        proxy = ProxyService(
            service_name="test-proxy",
            service_type="nextcloud",
            hostname="test",
            port=2222,
            last_check=time.time(),
            is_healthy=True
        )
        discovery._cache["nextcloud"] = proxy
        
        # Should return cached proxy
        cached = discovery.get_cached_proxy("nextcloud")
        assert cached is not None
        assert cached is proxy
        
        # Wait for cache to expire
        time.sleep(3)
        
        # Should return None (expired)
        cached = discovery.get_cached_proxy("nextcloud")
        assert cached is None
    
    def test_error_counting(self, mock_docker_client):
        """Test proxy error tracking and removal."""
        discovery = ProxyDiscovery(
            docker_client=mock_docker_client,
            max_error_count=3
        )
        
        # Create cached proxy
        proxy = ProxyService(
            service_name="test-proxy",
            service_type="nextcloud",
            hostname="test",
            port=2222,
            last_check=time.time(),
            is_healthy=True
        )
        discovery._cache["nextcloud"] = proxy
        
        # Mark errors
        discovery.mark_proxy_error("nextcloud")
        discovery.mark_proxy_error("nextcloud")
        assert discovery._cache["nextcloud"].error_count == 2
        
        # Should still be cached
        cached = discovery.get_cached_proxy("nextcloud")
        assert cached is not None
        
        # One more error should trigger removal
        discovery.mark_proxy_error("nextcloud")
        cached = discovery.get_cached_proxy("nextcloud")
        assert cached is None
    
    def test_health_check(self, mock_docker_client):
        """Test proxy health checking."""
        discovery = ProxyDiscovery(
            docker_client=mock_docker_client,
            health_check_timeout=2
        )
        
        proxy = ProxyService(
            service_name="test",
            service_type="nextcloud",
            hostname="localhost",
            port=22222,  # Unlikely to be open
            is_healthy=False
        )
        
        # Health check should fail for closed port
        result = discovery._check_health(proxy)
        assert result is False


class TestIntegrationWithExecutor:
    """Integration tests combining executor and proxy components."""
    
    @pytest.fixture
    def mock_components(self, tmp_path):
        """Set up mocked components for integration testing."""
        # Create temp key
        key_path = tmp_path / "test_key"
        import subprocess
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", str(key_path), "-N", ""],
            capture_output=True,
            check=False
        )
        
        return {
            "key_path": str(key_path),
            "docker_client": Mock(),
            "ssh_client": Mock()
        }
    
    @patch('src.docker_interface.executor.SSHProxyClient')
    @patch('src.docker_interface.executor.ProxyDiscovery')
    def test_executor_swarm_mode_initialization(
        self,
        mock_discovery_class,
        mock_ssh_class,
        mock_components
    ):
        """Test executor initialization in Swarm mode."""
        from src.docker_interface.executor import DockerExecutor
        
        # Create executor with Swarm mode
        executor = DockerExecutor(
            swarm_mode=True,
            nextcloud_proxy_key=mock_components["key_path"],
            photoprism_proxy_key=mock_components["key_path"]
        )
        
        # Verify SSH clients were created
        assert mock_ssh_class.call_count >= 1
        assert mock_discovery_class.call_count >= 1


# Manual/Live Testing Notes
# ==========================
# For actual integration testing with running proxy services:
#
# 1. Deploy proxies:
#    $ docker stack deploy -c compose/nextcloud-proxy.yaml test-nc-proxy
#    $ docker stack deploy -c compose/photoprism-proxy.yaml test-pp-proxy
#
# 2. Verify proxies are running:
#    $ docker service ls | grep proxy
#
# 3. Test SSH connectivity:
#    $ ssh -i secrets/ssh-keys/nextcloud_proxy_ed25519 \
#         -p 2222 proxyuser@localhost \
#         "php occ status"
#
# 4. Run live tests:
#    $ pytest tests/test_ssh_proxy.py --live
#
# 5. Check proxy logs:
#    $ docker service logs test-nc-proxy_nextcloud-proxy
