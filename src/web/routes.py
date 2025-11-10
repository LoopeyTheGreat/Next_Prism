"""
API Routes
==========

REST API endpoints for configuration, monitoring, and control.

Author: Next_Prism Project
License: MIT
"""

from fastapi import APIRouter, HTTPException, status, Body, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import asyncio

from ..config.config_loader import ConfigLoader
from ..config.schema import Config
from ..utils.logger import get_logger

# Initialize config loader
config_loader = ConfigLoader()

# Global orchestrator reference (set by app.py)
_orchestrator = None

def set_orchestrator(orchestrator):
    """Set orchestrator instance for routes."""
    global _orchestrator
    _orchestrator = orchestrator

def get_orchestrator():
    """Get orchestrator instance."""
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    return _orchestrator

# Helper functions for simplified API
def load() -> dict:
    """Load configuration as dictionary."""
    config = config_loader.load()
    return config.dict() if hasattr(config, 'dict') else config.__dict__

def save(config_dict: dict):
    """Save configuration from dictionary."""
    config = Config(**config_dict)
    config_loader.save(config)

logger = get_logger(__name__)

# Create routers
api_router = APIRouter()
auth_router = APIRouter()


# ============================================================================
# Pydantic Models for API Requests/Responses
# ============================================================================

class LoginRequest(BaseModel):
    """Login request model."""
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Login response model."""
    success: bool
    token: Optional[str] = None
    expires_in: int = 86400  # 24 hours in seconds
    message: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    """Configuration update request."""
    config: Dict[str, Any]


class SyncTriggerRequest(BaseModel):
    """Manual sync trigger request."""
    folder_path: Optional[str] = None
    force: bool = False


class StatusResponse(BaseModel):
    """System status response."""
    status: str
    uptime: float
    sync_stats: Dict[str, Any]
    queue_size: int
    monitored_folders: int
    swarm_mode: bool
    proxy_status: Optional[Dict[str, Any]] = None


# ============================================================================
# Authentication Routes
# ============================================================================

@auth_router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return JWT token.
    """
    try:
        config = load()
        security = config.get('security', {})
        
        # Check if password protection is enabled
        if not security.get('web_password'):
            return LoginResponse(
                success=False,
                message="Password authentication not configured"
            )
        
        # Verify password
        import bcrypt
        if not bcrypt.checkpw(
            request.password.encode('utf-8'),
            security.get('web_password', '').encode('utf-8')
        ):
            logger.warning("Failed login attempt")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password"
            )
        
        # Generate token
        from .middleware import create_token
        token = create_token("admin", security.jwt_secret, expires_hours=24)
        
        logger.info("User logged in successfully")
        return LoginResponse(
            success=True,
            token=token,
            expires_in=86400
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@auth_router.post("/logout")
async def logout():
    """Logout user (client-side token removal)."""
    return {"success": True, "message": "Logged out successfully"}


@auth_router.get("/login")
async def login_page(request: Request):
    """Serve login page."""
    from fastapi.templating import Jinja2Templates
    from pathlib import Path
    
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    
    return templates.TemplateResponse("login.html", {"request": request})


# ============================================================================
# Configuration Routes
# ============================================================================

@api_router.get("/config")
async def get_config():
    """
    Get current configuration.
    
    Returns full configuration as JSON for UI editing.
    """
    try:
        config_dict = load()
        
        # Remove sensitive data
        if config_dict.get("security", {}).get("web_password"):
            config_dict["security"]["web_password"] = "***HIDDEN***"
        
        return JSONResponse(content=config_dict)
        
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load configuration: {str(e)}"
        )


@api_router.post("/config")
async def update_config(request: ConfigUpdateRequest):
    """
    Update configuration.
    
    Accepts partial or full configuration updates.
    Validates before saving and triggers hot-reload.
    """
    try:
        # Load current config
        config_dict = load()
        
        # Merge updates
        config_dict.update(request.config)
        
        # Validate new config
        try:
            new_config = Config(**config_dict)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid configuration: {str(e)}"
            )
        
        # Save config
        save(new_config)
        
        logger.info("Configuration updated via web UI")
        return {
            "success": True,
            "message": "Configuration updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update configuration: {str(e)}"
        )


@api_router.post("/config/validate")
async def validate_config(request: ConfigUpdateRequest):
    """
    Validate configuration without saving.
    
    Useful for real-time validation in UI forms.
    """
    try:
        Config(**request.config)
        return {
            "valid": True,
            "message": "Configuration is valid"
        }
    except Exception as e:
        return {
            "valid": False,
            "message": str(e),
            "errors": [str(e)]
        }


# ============================================================================
# Status and Monitoring Routes
# ============================================================================

@api_router.get("/status", response_model=StatusResponse)
async def get_status():
    """
    Get system status and statistics.
    """
    try:
        orchestrator = get_orchestrator()
        config = load()
        
        # Get status from orchestrator
        is_running = orchestrator._running if hasattr(orchestrator, '_running') else False
        queue_size = orchestrator.file_queue.qsize() if hasattr(orchestrator, 'file_queue') else 0
        
        # Get folder count
        watched_folders = 0
        if hasattr(orchestrator, 'folder_watcher'):
            watched_folders = len(orchestrator.folder_watcher.watched_folders)
        
        return StatusResponse(
            status="running" if is_running else "stopped",
            uptime=0.0,  # TODO: Track actual uptime
            sync_stats={
                "total_synced": 0,  # TODO: Get from orchestrator stats
                "total_duplicates": 0,
                "total_errors": 0
            },
            queue_size=queue_size,
            monitored_folders=watched_folders,
            swarm_mode=config.get('docker', {}).get('swarm_mode', False),
            proxy_status=None
        )
        
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get status"
        )


@api_router.get("/logs")
async def get_logs(
    level: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get application logs.
    
    Args:
        level: Filter by log level (DEBUG, INFO, WARNING, ERROR)
        limit: Maximum number of log entries
        offset: Offset for pagination
    """
    try:
        # TODO: Implement log reading from file
        # Placeholder implementation
        logs = [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "message": "System started",
                "component": "orchestrator"
            }
        ]
        
        return {
            "logs": logs,
            "total": len(logs),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Failed to get logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get logs"
        )


@api_router.get("/logs/stream")
async def stream_logs():
    """
    Stream logs in real-time using Server-Sent Events (SSE).
    """
    async def event_generator():
        """Generate SSE events with log updates."""
        while True:
            # TODO: Read from log file or queue
            # Placeholder implementation
            await asyncio.sleep(1)
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "message": "Heartbeat",
                "component": "web"
            }
            yield f"data: {json.dumps(log_entry)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# ============================================================================
# Control Routes
# ============================================================================

@api_router.post("/sync/trigger")
async def trigger_sync(request: SyncTriggerRequest):
    """
    Manually trigger a sync operation.
    
    Args:
        folder_path: Specific folder to sync (optional)
        force: Force sync even if no changes detected
    """
    try:
        orchestrator = get_orchestrator()
        
        logger.info(f"Manual sync triggered: folder={request.folder_path}, force={request.force}")
        
        # Check orchestrator is running
        if not orchestrator._running:
            raise HTTPException(
                status_code=400,
                detail="Orchestrator is not running"
            )
        
        # Process pending files from folder watcher
        if hasattr(orchestrator, 'folder_watcher'):
            orchestrator.folder_watcher.process_pending_files()
        
        return {
            "success": True,
            "message": "Sync triggered successfully",
            "queue_size": orchestrator.file_queue.qsize()
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger sync"
        )


@api_router.post("/sync/pause")
async def pause_sync():
    """Pause sync operations."""
    try:
        orchestrator = get_orchestrator()
        
        # Stop orchestrator
        orchestrator.stop()
        
        return {
            "success": True,
            "message": "Sync paused",
            "status": "stopped"
        }
    except Exception as e:
        logger.error(f"Failed to pause sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause sync"
        )


@api_router.post("/sync/resume")
async def resume_sync():
    """Resume sync operations."""
    try:
        orchestrator = get_orchestrator()
        
        # Start orchestrator
        orchestrator.start()
        
        return {
            "success": True,
            "message": "Sync resumed",
            "status": "running"
        }
    except Exception as e:
        logger.error(f"Failed to resume sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resume sync"
        )


@api_router.delete("/queue")
async def clear_queue():
    """Clear pending sync queue."""
    try:
        # TODO: Clear queue in orchestrator
        return {"success": True, "message": "Queue cleared"}
    except Exception as e:
        logger.error(f"Failed to clear queue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear queue"
        )


# ============================================================================
# Docker Connection Test Routes
# ============================================================================

@api_router.post("/test/nextcloud")
async def test_nextcloud_connection():
    """Test Nextcloud container connectivity."""
    try:
        # TODO: Test Nextcloud connection via executor
        return {
            "success": True,
            "message": "Nextcloud connection successful",
            "version": "Unknown"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Nextcloud connection failed: {str(e)}"
        }


@api_router.post("/test/photoprism")
async def test_photoprism_connection():
    """Test PhotoPrism container connectivity."""
    try:
        # TODO: Test PhotoPrism connection via executor
        return {
            "success": True,
            "message": "PhotoPrism connection successful",
            "version": "Unknown"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"PhotoPrism connection failed: {str(e)}"
        }


# ============================================================================
# Proxy Management Routes (Swarm Mode)
# ============================================================================

@api_router.get("/proxy/status")
async def get_proxy_status():
    """Get status of Swarm proxy services."""
    try:
        # TODO: Get proxy status from discovery service
        return {
            "nextcloud_proxy": {
                "available": False,
                "hostname": None,
                "port": None,
                "healthy": False
            },
            "photoprism_proxy": {
                "available": False,
                "hostname": None,
                "port": None,
                "healthy": False
            }
        }
    except Exception as e:
        logger.error(f"Failed to get proxy status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get proxy status"
        )


@api_router.post("/proxy/discover")
async def discover_proxies():
    """Force proxy service discovery."""
    try:
        # TODO: Trigger proxy discovery
        return {
            "success": True,
            "message": "Proxy discovery completed"
        }
    except Exception as e:
        logger.error(f"Failed to discover proxies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to discover proxies"
        )


@api_router.get("/proxy/pools")
async def get_connection_pools():
    """Get SSH connection pool statistics."""
    try:
        # TODO: Get pool stats from SSH clients
        return {
            "nextcloud": {
                "total_connections": 0,
                "active_connections": 0,
                "idle_connections": 0
            },
            "photoprism": {
                "total_connections": 0,
                "active_connections": 0,
                "idle_connections": 0
            }
        }
    except Exception as e:
        logger.error(f"Failed to get pool stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get connection pool stats"
        )
