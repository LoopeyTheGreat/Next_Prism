"""
Web UI Module
=============

FastAPI-based web interface for Next_Prism configuration and monitoring.

Author: Next_Prism Project
License: MIT
"""

from .app import app
from .routes import api_router, auth_router
from .middleware import AuthMiddleware

__all__ = ["app", "api_router", "auth_router", "AuthMiddleware"]
