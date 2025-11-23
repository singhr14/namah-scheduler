"""
Scheduler implementation for periodic sync jobs using the schedule library.
Handles job execution, error handling, and graceful shutdown.
"""
import time
import threading
from typing import Optional, Callable, Any
from datetime import datetime
import schedule

from ..config.settings import Settings
from ..core.sync_service import MongoToElasticSyncService
from ..utils.logger import get_logger, log_sync_metrics
from ..utils.helpers import GracefulShutdownHandler, format_duration, get_utc_now

logger = get_logger(__name__)


class SyncScheduler:
    """
    Scheduler for periodic synchronization jobs.
    Manages job execution with error handling and graceful shutdown.
    """
    
    def __init__(self, settings: Settings, sync_service: MongoToElasticSyncService):
        """
        Initialize scheduler with settings and sync service.
        
        Args:
            settings: Application settings
            sync_service: Sync service instance
        """
        self.settings = settings
        self.sync_service = sync_service
        self.shutdown_handler = GracefulShutdownHandler()
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        
        # Job execution tracking
        self.last_job_start: Optional[datetime] = None
        self.last_job_end: Optional[datetime] = None
        self.job_count = 0
        self.successful_jobs = 0
        self.failed_jobs = 0
        
        logger.info(f"SyncScheduler initialized with interval: {settings.sync_interval_minutes} minutes")
    
    def setup_jobs(self) -> None:
        """Setup scheduled jobs."""
        try:
            # Clear any existing jobs
            schedule.clear()
            
            # Schedule incremental sync job
            schedule.every(self.settings.sync_interval_minutes).minutes.do(
                self._run_sync_job,
                job_type="incremental"
            )
            
            # Schedule daily full sync at 2 AM (if not already done in last 24 hours)
            schedule.every().day.at("02:00").do(
                self._run_sync_job,
                job_type="full"
            )
            
            # Schedule health check every hour
            schedule.every().hour.do(self._run_health_check)
            
            logger.info("Scheduled jobs configured:")
            logger.info(f"  - Incremental sync: every {self.settings.sync_interval_minutes} minutes")
            logger.info("  - Full sync: daily at 02:00")
            logger.info("  - Health check: every hour")
            
        except Exception as e:
            logger.error(f"Error setting up scheduled jobs: {str(e)}")
            raise
    
    def start(self) -> None:
        """Start the scheduler in a separate thread."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        try:
            self.setup_jobs()
            self.is_running = True
            
            # Start scheduler in a separate thread
            self.scheduler_thread = threading.Thread(
                target=self._run_scheduler,
                name="SyncScheduler",
                daemon=True
            )
            self.scheduler_thread.start()
            
            logger.info("Scheduler started successfully")
            
        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}")
            self.is_running = False
            raise
    
    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self.is_running:
            logger.info("Scheduler is not running")
            return
        
        logger.info("Stopping scheduler...")
        self.is_running = False
        
        # Signal shutdown
        self.shutdown_handler.shutdown_requested = True
        self.shutdown_handler.shutdown_event.set()
        
        # Wait for scheduler thread to finish
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=30)  # Wait up to 30 seconds
            
            if self.scheduler_thread.is_alive():
                logger.warning("Scheduler thread did not stop gracefully")
            else:
                logger.info("Scheduler stopped successfully")
        
        # Clear scheduled jobs
        schedule.clear()
    
    def _run_scheduler(self) -> None:
        """Main scheduler loop running in separate thread."""
        logger.info("Scheduler loop started")
        
        try:
            while self.is_running and not self.shutdown_handler.is_shutdown_requested():
                try:
                    # Run pending jobs
                    schedule.run_pending()
                    
                    # Sleep for 1 second before checking again
                    if not self.shutdown_handler.wait_for_shutdown(timeout=1.0):
                        continue
                    else:
                        # Shutdown requested
                        break
                        
                except Exception as e:
                    logger.error(f"Error in scheduler loop: {str(e)}")
                    time.sleep(5)  # Wait before retrying
                    
        except Exception as e:
            logger.error(f"Critical error in scheduler loop: {str(e)}")
        finally:
            logger.info("Scheduler loop ended")
    
    def _run_sync_job(self, job_type: str = "incremental") -> None:
        """
        Execute a sync job with error handling.
        
        Args:
            job_type: Type of sync job ("incremental" or "full")
        """
        job_start_time = get_utc_now()
        self.last_job_start = job_start_time
        self.job_count += 1
        
        logger.info(f"Starting scheduled {job_type} sync job #{self.job_count}")
        
        try:
            # Check if shutdown was requested
            if self.shutdown_handler.is_shutdown_requested():
                logger.info("Shutdown requested, skipping sync job")
                return
            
            # Run sync based on type
            if job_type == "full":
                sync_result = self.sync_service.run_full_sync()
            else:
                sync_result = self.sync_service.run_incremental_sync()
            
            # Update job tracking
            self.last_job_end = get_utc_now()
            job_duration = (self.last_job_end - job_start_time).total_seconds()
            
            if sync_result.success:
                self.successful_jobs += 1
                logger.info(f"Scheduled {job_type} sync job completed successfully in {format_duration(job_duration)}")
                logger.info(f"  - Documents processed: {sync_result.documents_processed}")
                logger.info(f"  - Documents indexed: {sync_result.documents_indexed}")
                logger.info(f"  - Documents failed: {sync_result.documents_failed}")
            else:
                self.failed_jobs += 1
                logger.error(f"Scheduled {job_type} sync job failed after {format_duration(job_duration)}")
                logger.error(f"  - Documents processed: {sync_result.documents_processed}")
                logger.error(f"  - Documents indexed: {sync_result.documents_indexed}")
                logger.error(f"  - Documents failed: {sync_result.documents_failed}")
                
                # Log first few errors
                for error in sync_result.errors[:5]:
                    logger.error(f"  - Error: {error}")
            
        except Exception as e:
            self.failed_jobs += 1
            self.last_job_end = get_utc_now()
            job_duration = (self.last_job_end - job_start_time).total_seconds()
            
            logger.error(f"Critical error in scheduled {job_type} sync job after {format_duration(job_duration)}: {str(e)}")
    
    def _run_health_check(self) -> None:
        """Run health check and log results."""
        try:
            logger.debug("Running scheduled health check")
            
            health_status = self.sync_service.health_check()
            
            if health_status.get("status") == "healthy":
                logger.info("Health check passed - all components healthy")
            else:
                logger.warning(f"Health check failed: {health_status}")
                
                # Log component-specific issues
                for component in ["mongodb", "elasticsearch", "sync_service"]:
                    component_status = health_status.get(component, {})
                    if component_status.get("status") != "healthy":
                        logger.warning(f"  - {component}: {component_status.get('status', 'unknown')} - {component_status.get('error', 'no details')}")
            
        except Exception as e:
            logger.error(f"Error during health check: {str(e)}")
    
    def run_immediate_sync(self, sync_type: str = "incremental") -> None:
        """
        Run an immediate sync job (outside of schedule).
        
        Args:
            sync_type: Type of sync ("incremental" or "full")
        """
        logger.info(f"Running immediate {sync_type} sync")
        self._run_sync_job(sync_type)
    
    def get_scheduler_status(self) -> dict:
        """
        Get current scheduler status and statistics.
        
        Returns:
            dict: Scheduler status information
        """
        next_jobs = []
        for job in schedule.jobs:
            next_jobs.append({
                "job": str(job.job_func),
                "next_run": job.next_run.isoformat() if job.next_run else None,
                "interval": str(job.interval),
                "unit": job.unit
            })
        
        return {
            "is_running": self.is_running,
            "total_jobs_executed": self.job_count,
            "successful_jobs": self.successful_jobs,
            "failed_jobs": self.failed_jobs,
            "success_rate": (self.successful_jobs / self.job_count * 100) if self.job_count > 0 else 0,
            "last_job_start": self.last_job_start.isoformat() if self.last_job_start else None,
            "last_job_end": self.last_job_end.isoformat() if self.last_job_end else None,
            "next_scheduled_jobs": next_jobs,
            "shutdown_requested": self.shutdown_handler.is_shutdown_requested()
        }
    
    def wait_for_shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for shutdown signal.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            bool: True if shutdown was requested, False if timeout
        """
        return self.shutdown_handler.wait_for_shutdown(timeout)


class SingletonScheduler:
    """Singleton wrapper for SyncScheduler to ensure only one instance."""
    
    _instance: Optional[SyncScheduler] = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls, settings: Settings, sync_service: MongoToElasticSyncService) -> SyncScheduler:
        """
        Get singleton scheduler instance.
        
        Args:
            settings: Application settings
            sync_service: Sync service instance
            
        Returns:
            SyncScheduler: Singleton scheduler instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = SyncScheduler(settings, sync_service)
        
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (mainly for testing)."""
        with cls._lock:
            if cls._instance:
                cls._instance.stop()
            cls._instance = None
