"""
Web Application Entry Point
============================

FastAPI application for Next_Prism web UI.
Provides REST API for configuration, monitoring, and control.

Author: Next_Prism Project
License: MIT
"""

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import logging

from .routes import api_router, auth_router, set_orchestrator
from .middleware import AuthMiddleware
from ..utils.logger import get_logger
from ..core.orchestrator import Orchestrator
from ..scheduler.task_scheduler import TaskScheduler
from ..config.config_loader import ConfigLoader
from typing import Optional

logger = get_logger(__name__)

# Global orchestrator instance
orchestrator: Optional[Orchestrator] = None
scheduler: Optional[TaskScheduler] = None

# Create FastAPI app
app = FastAPI(
    title="Next_Prism",
    description="Nextcloud to PhotoPrism Sync Orchestrator",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on security settings
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add authentication middleware
app.add_middleware(AuthMiddleware)

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Setup static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(api_router, prefix="/api", tags=["API"])


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve main dashboard page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Serve configuration page."""
    return templates.TemplateResponse("config.html", {"request": request})


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Serve logs viewer page."""
    return templates.TemplateResponse("logs.html", {"request": request})


@app.get("/proxy", response_class=HTMLResponse)
async def proxy_page(request: Request):
    """Serve proxy management page (Swarm mode)."""
    return templates.TemplateResponse("proxy.html", {"request": request})


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    global orchestrator, scheduler
    
    logger.info("Next_Prism web application starting...")
    
    try:
        # Load configuration
        config_loader = ConfigLoader()
        config = config_loader.config
        
        # Initialize orchestrator
        orchestrator = Orchestrator(config)
        orchestrator.initialize()
        
        # Initialize scheduler
        scheduler = TaskScheduler(config)
        
        # Set callback to add files to queue for scanning
        def scan_callback(folder_path: Optional[str] = None):
            """Callback for scheduled scans."""
            if folder_path:
                logger.info(f"Scheduled scan triggered for: {folder_path}")
            else:
                logger.info("Scheduled scan triggered for all folders")
            # Orchestrator's folder_watcher will handle detection
            
        scheduler.set_scan_callback(scan_callback)
        scheduler.start()
        
        # Add default scan job if enabled
        if config.scheduling and config.scheduling.enabled:
            scheduler.add_default_scan_job()
        
        # Make orchestrator available to routes
        set_orchestrator(orchestrator)
        
        # Start orchestrator
        orchestrator.start()
        
        logger.info("Next_Prism initialized successfully")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    global orchestrator, scheduler
    
    logger.info("Next_Prism web application shutting down...")
    
    try:
        # Stop scheduler
        if scheduler:
            scheduler.stop()
        
        # Stop orchestrator
        if orchestrator:
            orchestrator.stop()
        
        logger.info("Shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy", "service": "next_prism"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.web.app:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
