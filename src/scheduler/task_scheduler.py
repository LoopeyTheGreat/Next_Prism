"""
Task Scheduler

APScheduler integration for periodic folder scanning and sync operations.

Author: Next_Prism Project
License: MIT
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from typing import Optional, Callable
from datetime import datetime

from ..utils.logger import get_logger
from ..config.schema import Config

logger = get_logger(__name__)


class TaskScheduler:
    """
    Manages scheduled tasks for folder scanning and sync operations.
    
    Features:
    - Cron-based scheduling
    - Interval-based scheduling
    - Per-folder schedule configuration
    - Persistence across restarts
    """
    
    def __init__(self, config: Config):
        """
        Initialize task scheduler.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.scheduler = BackgroundScheduler(
            timezone='UTC',
            job_defaults={
                'coalesce': True,  # Combine missed executions
                'max_instances': 1  # Only one instance per job
            }
        )
        
        self._scan_callback: Optional[Callable] = None
        
        logger.info("TaskScheduler initialized")
    
    def start(self):
        """Start the scheduler."""
        if self.scheduler.running:
            logger.warning("Scheduler already running")
            return
        
        self.scheduler.start()
        logger.info("Scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        if not self.scheduler.running:
            return
        
        self.scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")
    
    def set_scan_callback(self, callback: Callable[[Optional[str]], None]):
        """
        Set callback function for scheduled scans.
        
        Args:
            callback: Function that takes optional folder_path parameter
        """
        self._scan_callback = callback
        logger.info("Scan callback registered")
    
    def add_default_scan_job(self):
        """Add default scan job based on configuration."""
        cron_expr = self.config.scheduling.default_interval
        
        if not cron_expr:
            logger.warning("No default scan interval configured")
            return
        
        try:
            # Parse cron expression
            # Format: "minute hour day month day_of_week"
            parts = cron_expr.split()
            
            if len(parts) == 5:
                trigger = CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                    timezone='UTC'
                )
            else:
                logger.error(f"Invalid cron expression: {cron_expr}")
                return
            
            self.scheduler.add_job(
                func=self._execute_default_scan,
                trigger=trigger,
                id='default_scan',
                name='Default Folder Scan',
                replace_existing=True
            )
            
            logger.info(f"Added default scan job with schedule: {cron_expr}")
            
        except Exception as e:
            logger.error(f"Error adding default scan job: {e}")
    
    def add_folder_scan_job(self, folder_path: str, schedule: str):
        """
        Add scheduled scan job for specific folder.
        
        Args:
            folder_path: Folder to scan
            schedule: Cron expression
        """
        try:
            parts = schedule.split()
            
            if len(parts) == 5:
                trigger = CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                    timezone='UTC'
                )
            else:
                logger.error(f"Invalid cron expression: {schedule}")
                return
            
            job_id = f"scan_{hash(folder_path)}"
            
            self.scheduler.add_job(
                func=lambda: self._execute_folder_scan(folder_path),
                trigger=trigger,
                id=job_id,
                name=f"Scan: {folder_path}",
                replace_existing=True
            )
            
            logger.info(f"Added scan job for {folder_path} with schedule: {schedule}")
            
        except Exception as e:
            logger.error(f"Error adding folder scan job: {e}")
    
    def remove_folder_scan_job(self, folder_path: str):
        """
        Remove scheduled scan job for folder.
        
        Args:
            folder_path: Folder path
        """
        job_id = f"scan_{hash(folder_path)}"
        
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed scan job for {folder_path}")
        except Exception as e:
            logger.warning(f"Could not remove job {job_id}: {e}")
    
    def add_periodic_cleanup_job(self, interval_hours: int = 24):
        """
        Add periodic cleanup job for cache and old logs.
        
        Args:
            interval_hours: Interval in hours
        """
        trigger = IntervalTrigger(hours=interval_hours)
        
        self.scheduler.add_job(
            func=self._execute_cleanup,
            trigger=trigger,
            id='periodic_cleanup',
            name='Periodic Cleanup',
            replace_existing=True
        )
        
        logger.info(f"Added periodic cleanup job (every {interval_hours} hours)")
    
    def _execute_default_scan(self):
        """Execute default scan job."""
        logger.info("Executing scheduled default scan")
        
        if self._scan_callback:
            try:
                self._scan_callback(None)  # None = scan all folders
            except Exception as e:
                logger.error(f"Error in default scan callback: {e}")
        else:
            logger.warning("No scan callback registered")
    
    def _execute_folder_scan(self, folder_path: str):
        """Execute folder-specific scan job."""
        logger.info(f"Executing scheduled scan for {folder_path}")
        
        if self._scan_callback:
            try:
                self._scan_callback(folder_path)
            except Exception as e:
                logger.error(f"Error in folder scan callback: {e}")
        else:
            logger.warning("No scan callback registered")
    
    def _execute_cleanup(self):
        """Execute cleanup tasks."""
        logger.info("Executing periodic cleanup")
        
        # TODO: Implement cleanup logic
        # - Prune old log files
        # - Clear expired hash cache entries
        # - Remove old queue persistence files
        pass
    
    def get_jobs(self) -> list:
        """
        Get list of scheduled jobs.
        
        Returns:
            List of job information dictionaries
        """
        jobs = []
        
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time
            
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': next_run.isoformat() if next_run else None,
                'trigger': str(job.trigger)
            })
        
        return jobs
    
    def pause_all_jobs(self):
        """Pause all scheduled jobs."""
        self.scheduler.pause()
        logger.info("All jobs paused")
    
    def resume_all_jobs(self):
        """Resume all scheduled jobs."""
        self.scheduler.resume()
        logger.info("All jobs resumed")
