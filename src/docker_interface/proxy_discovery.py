"""
Docker Swarm Proxy Service Discovery
=====================================

This module provides automatic discovery and health checking of SSH proxy services
in Docker Swarm environments.

When Next_Prism runs in Swarm mode, it cannot directly execute docker commands on
containers running on other nodes. Instead, it communicates with lightweight SSH
proxy services that run alongside the target containers.

This module:
- Discovers proxy services via Docker API
- Resolves service DNS names to IP addresses
- Tests SSH connectivity and caches successful connections
- Provides fallback logic when proxies are unavailable

Author: Next_Prism Project
License: MIT
"""

import logging
import socket
import time
from dataclasses import dataclass
from typing import Dict, Optional, List

import docker
from docker.errors import DockerException


logger = logging.getLogger(__name__)


@dataclass
class ProxyService:
    """Represents a discovered proxy service."""
    service_name: str
    service_type: str  # "nextcloud" or "photoprism"
    hostname: str
    port: int
    ip_address: Optional[str] = None
    last_check: float = 0
    is_healthy: bool = False
    error_count: int = 0


class ProxyDiscovery:
    """
    Automatic discovery and health checking for Docker Swarm proxy services.
    
    This class maintains a cache of discovered proxy services and periodically
    validates their health status. It provides methods to lookup proxy endpoints
    for Nextcloud and PhotoPrism services.
    
    Example:
        ```python
        discovery = ProxyDiscovery()
        
        # Discover Nextcloud proxy
        proxy = discovery.discover_proxy("nextcloud")
        if proxy:
            print(f"Found proxy at {proxy.hostname}:{proxy.port}")
        
        # Get cached proxy (faster)
        proxy = discovery.get_cached_proxy("nextcloud")
        ```
    """
    
    def __init__(
        self,
        docker_client: Optional[docker.DockerClient] = None,
        cache_ttl: int = 60,
        health_check_timeout: int = 5,
        max_error_count: int = 3
    ):
        """
        Initialize proxy discovery.
        
        Args:
            docker_client: Docker client instance (created if not provided)
            cache_ttl: Cache validity period in seconds
            health_check_timeout: Timeout for health checks
            max_error_count: Remove proxy from cache after this many failures
        """
        self.docker_client = docker_client or docker.from_env()
        self.cache_ttl = cache_ttl
        self.health_check_timeout = health_check_timeout
        self.max_error_count = max_error_count
        
        # Cache: service_type -> ProxyService
        self._cache: Dict[str, ProxyService] = {}
        
        logger.info(
            f"Proxy discovery initialized: cache_ttl={cache_ttl}s, "
            f"health_timeout={health_check_timeout}s"
        )
    
    def discover_proxy(
        self,
        service_type: str,
        force_refresh: bool = False
    ) -> Optional[ProxyService]:
        """
        Discover proxy service for given type.
        
        This method:
        1. Checks cache (unless force_refresh=True)
        2. Queries Docker Swarm for matching services
        3. Resolves DNS name to IP address
        4. Tests SSH connectivity
        5. Caches result
        
        Args:
            service_type: "nextcloud" or "photoprism"
            force_refresh: Bypass cache and discover fresh
            
        Returns:
            ProxyService if found and healthy, None otherwise
        """
        # Check cache first
        if not force_refresh:
            cached = self.get_cached_proxy(service_type)
            if cached:
                return cached
        
        logger.info(f"Discovering {service_type} proxy service...")
        
        try:
            # Query Swarm for proxy services
            services = self.docker_client.services.list(
                filters={"label": f"service={service_type}-proxy"}
            )
            
            if not services:
                logger.warning(f"No {service_type} proxy services found in Swarm")
                return None
            
            if len(services) > 1:
                logger.warning(
                    f"Multiple {service_type} proxy services found, using first"
                )
            
            service = services[0]
            service_name = service.name
            
            # Get service endpoint (typically DNS name in overlay network)
            # Format: <service_name> or <service_name>.<network_name>
            hostname = service_name
            port = 2222  # Standard SSH proxy port
            
            logger.info(
                f"Found {service_type} proxy service: "
                f"{service_name} ({hostname}:{port})"
            )
            
            # Resolve DNS to IP
            ip_address = self._resolve_hostname(hostname)
            
            # Create proxy service object
            proxy = ProxyService(
                service_name=service_name,
                service_type=service_type,
                hostname=hostname,
                port=port,
                ip_address=ip_address,
                last_check=time.time(),
                is_healthy=False,
                error_count=0
            )
            
            # Test connectivity
            if self._check_health(proxy):
                proxy.is_healthy = True
                self._cache[service_type] = proxy
                logger.info(f"Successfully discovered and cached {service_type} proxy")
                return proxy
            else:
                logger.warning(
                    f"Discovered {service_type} proxy but health check failed"
                )
                return None
                
        except DockerException as e:
            logger.error(f"Docker API error during proxy discovery: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during proxy discovery: {e}")
            return None
    
    def get_cached_proxy(self, service_type: str) -> Optional[ProxyService]:
        """
        Get proxy from cache if still valid.
        
        Args:
            service_type: "nextcloud" or "photoprism"
            
        Returns:
            Cached ProxyService if valid, None otherwise
        """
        if service_type not in self._cache:
            return None
        
        proxy = self._cache[service_type]
        age = time.time() - proxy.last_check
        
        # Check cache validity
        if age > self.cache_ttl:
            logger.debug(
                f"Cache expired for {service_type} proxy "
                f"(age: {age:.1f}s, ttl: {self.cache_ttl}s)"
            )
            return None
        
        # Check error count
        if proxy.error_count >= self.max_error_count:
            logger.warning(
                f"Removing {service_type} proxy from cache "
                f"(error count: {proxy.error_count})"
            )
            del self._cache[service_type]
            return None
        
        logger.debug(f"Using cached {service_type} proxy: {proxy.hostname}:{proxy.port}")
        return proxy
    
    def invalidate_cache(self, service_type: Optional[str] = None):
        """
        Invalidate proxy cache.
        
        Args:
            service_type: Specific type to invalidate, or None for all
        """
        if service_type:
            if service_type in self._cache:
                del self._cache[service_type]
                logger.info(f"Invalidated cache for {service_type} proxy")
        else:
            self._cache.clear()
            logger.info("Invalidated all proxy caches")
    
    def mark_proxy_error(self, service_type: str):
        """
        Mark proxy as having encountered an error.
        
        This increments the error counter. If errors exceed max_error_count,
        the proxy will be removed from cache on next access.
        
        Args:
            service_type: "nextcloud" or "photoprism"
        """
        if service_type in self._cache:
            proxy = self._cache[service_type]
            proxy.error_count += 1
            logger.warning(
                f"Marked {service_type} proxy error "
                f"(count: {proxy.error_count}/{self.max_error_count})"
            )
    
    def mark_proxy_success(self, service_type: str):
        """
        Mark proxy as successful (resets error counter).
        
        Args:
            service_type: "nextcloud" or "photoprism"
        """
        if service_type in self._cache:
            proxy = self._cache[service_type]
            proxy.error_count = 0
            proxy.last_check = time.time()
            proxy.is_healthy = True
    
    def get_all_proxies(self) -> List[ProxyService]:
        """
        Get all cached proxy services.
        
        Returns:
            List of cached ProxyService objects
        """
        return list(self._cache.values())
    
    def _resolve_hostname(self, hostname: str) -> Optional[str]:
        """
        Resolve hostname to IP address.
        
        Args:
            hostname: DNS name or IP address
            
        Returns:
            IP address string, or None if resolution failed
        """
        try:
            # Check if already an IP
            socket.inet_aton(hostname)
            return hostname
        except socket.error:
            pass
        
        try:
            logger.debug(f"Resolving hostname: {hostname}")
            ip = socket.gethostbyname(hostname)
            logger.debug(f"Resolved {hostname} -> {ip}")
            return ip
        except socket.gaierror as e:
            logger.warning(f"Failed to resolve hostname {hostname}: {e}")
            return None
    
    def _check_health(self, proxy: ProxyService) -> bool:
        """
        Check if proxy service is reachable.
        
        Performs a basic TCP connection test to the SSH port.
        
        Args:
            proxy: ProxyService to check
            
        Returns:
            True if healthy, False otherwise
        """
        target = proxy.ip_address or proxy.hostname
        
        try:
            logger.debug(
                f"Health checking {proxy.service_type} proxy: {target}:{proxy.port}"
            )
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.health_check_timeout)
            result = sock.connect_ex((target, proxy.port))
            sock.close()
            
            if result == 0:
                logger.debug(f"Health check passed for {proxy.service_type} proxy")
                return True
            else:
                logger.warning(
                    f"Health check failed for {proxy.service_type} proxy: "
                    f"connection refused (code: {result})"
                )
                return False
                
        except socket.timeout:
            logger.warning(
                f"Health check timeout for {proxy.service_type} proxy "
                f"after {self.health_check_timeout}s"
            )
            return False
        except Exception as e:
            logger.error(f"Health check error for {proxy.service_type} proxy: {e}")
            return False
    
    def list_all_proxy_services(self) -> List[Dict[str, str]]:
        """
        List all proxy services in Swarm (cached and uncached).
        
        Returns:
            List of service info dictionaries
        """
        try:
            services = self.docker_client.services.list(
                filters={"label": "service"}
            )
            
            proxy_services = []
            for service in services:
                labels = service.attrs.get("Spec", {}).get("Labels", {})
                if labels.get("service", "").endswith("-proxy"):
                    proxy_services.append({
                        "name": service.name,
                        "type": labels.get("service", "").replace("-proxy", ""),
                        "id": service.id[:12],
                        "replicas": self._get_replica_count(service)
                    })
            
            return proxy_services
            
        except DockerException as e:
            logger.error(f"Failed to list proxy services: {e}")
            return []
    
    def _get_replica_count(self, service) -> str:
        """Get service replica count as string (e.g., "1/1")."""
        try:
            spec = service.attrs.get("Spec", {})
            mode = spec.get("Mode", {})
            
            if "Replicated" in mode:
                desired = mode["Replicated"].get("Replicas", 0)
                tasks = service.tasks(filters={"desired-state": "running"})
                running = len([t for t in tasks if t["Status"]["State"] == "running"])
                return f"{running}/{desired}"
            elif "Global" in mode:
                tasks = service.tasks(filters={"desired-state": "running"})
                running = len([t for t in tasks if t["Status"]["State"] == "running"])
                return f"{running} (global)"
            else:
                return "unknown"
        except Exception:
            return "unknown"
