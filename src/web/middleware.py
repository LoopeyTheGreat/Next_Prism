"""
Authentication Middleware
=========================

JWT-based authentication for web UI access.
Supports optional password protection and IP whitelisting.

Author: Next_Prism Project
License: MIT
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, List
import jwt
import logging
from datetime import datetime, timedelta

from ..config.config_loader import ConfigLoader
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Initialize config loader
_config_loader = ConfigLoader()

def load() -> dict:
    """Load configuration as dictionary."""
    config = _config_loader.load()
    return config.dict() if hasattr(config, 'dict') else config.__dict__


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for web UI.
    
    Features:
    - Optional password protection (disabled if no password set)
    - IP whitelisting
    - JWT token validation
    - Public endpoints (login, health, static)
    """
    
    # Public endpoints that don't require authentication
    PUBLIC_PATHS = [
        "/auth/login",
        "/auth/logout",
        "/health",
        "/static",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json"
    ]
    
    async def dispatch(self, request: Request, call_next):
        """Process request through authentication checks."""
        
        # Load config
        try:
            config = load()
            security = config.get('security', {})
        except Exception as e:
            logger.error(f"Failed to load config in auth middleware: {e}")
            # Allow access if config fails (fail open for now)
            return await call_next(request)
        
        # Check if path is public
        if any(request.url.path.startswith(path) for path in self.PUBLIC_PATHS):
            return await call_next(request)
        
        # Check IP whitelist if configured
        ip_whitelist = security.get('ip_whitelist')
        if ip_whitelist:
            client_ip = self._get_client_ip(request)
            if client_ip not in ip_whitelist:
                logger.warning(f"Access denied for IP: {client_ip}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access forbidden from your IP address"
                )
        
        # Check if password protection is enabled
        if not security.get('web_password'):
            # No password required, allow access
            return await call_next(request)
        
        # Verify JWT token
        token = self._get_token(request)
        if not token:
            # No token, redirect to login
            if request.url.path.startswith("/api/"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            return RedirectResponse(url="/auth/login", status_code=302)
        
        # Validate token
        try:
            jwt_secret = security.get('jwt_secret', 'default-secret-key')
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"]
            )
            
            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.utcnow().timestamp() > exp:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired"
                )
            
            # Store user info in request state
            request.state.user = payload.get("sub", "admin")
            
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            if request.url.path.startswith("/api/"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            return RedirectResponse(url="/auth/login", status_code=302)
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Get client IP address from request.
        
        Checks X-Forwarded-For header first (for proxies),
        falls back to direct client IP.
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _get_token(self, request: Request) -> Optional[str]:
        """
        Extract JWT token from request.
        
        Checks:
        1. Authorization header (Bearer token)
        2. Cookie (auth_token)
        """
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]
        
        # Check cookie
        return request.cookies.get("auth_token")


def create_token(username: str, jwt_secret: str, expires_hours: int = 24) -> str:
    """
    Create JWT token for authenticated user.
    
    Args:
        username: Username for token
        jwt_secret: Secret key for signing
        expires_hours: Token expiration in hours
        
    Returns:
        JWT token string
    """
    payload = {
        "sub": username,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=expires_hours)
    }
    
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


def verify_token(token: str, jwt_secret: str) -> Optional[str]:
    """
    Verify JWT token and return username.
    
    Args:
        token: JWT token to verify
        jwt_secret: Secret key for verification
        
    Returns:
        Username if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None
