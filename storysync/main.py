"""
Main entry point for StorySync - the story content synchronization service.
Handles service initialization, startup, and graceful shutdown.
"""
import sys
import os
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from storysync.config.settings import get_settings
from storysync.core.sync_service import MongoToElasticSyncService
from storysync.core.scheduler import SingletonScheduler
from storysync.utils.logger import setup_logger, get_logger
from storysync.utils.helpers import GracefulShutdownHandler

# Initialize logger early
settings = get_settings()
setup_logger(settings)
logger = get_logger(__name__)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="StorySync - Story Content Synchronization Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Start scheduled sync service
  python main.py --sync-now         # Run immediate sync and exit
  python main.py --full-sync        # Run full sync and exit
  python main.py --health-check     # Run health check and exit
  python main.py --status           # Show sync status and exit
        """
    )
    
    parser.add_argument(
        "--sync-now",
        action="store_true",
        help="Run immediate incremental sync and exit"
    )
    
    parser.add_argument(
        "--full-sync",
        action="store_true",
        help="Run immediate full sync and exit"
    )
    
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Run health check and exit"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show sync status and exit"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file (default: .env)"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override log level"
    )
    
    return parser.parse_args()


def run_immediate_sync(sync_type: str = "incremental") -> int:
    """
    Run immediate sync and exit.
    
    Args:
        sync_type: Type of sync to run ("incremental" or "full")
        
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    logger.info(f"Running immediate {sync_type} sync")
    
    try:
        with MongoToElasticSyncService(settings) as sync_service:
            if sync_type == "full":
                result = sync_service.run_full_sync()
            else:
                result = sync_service.run_incremental_sync()
            
            if result.success:
                logger.info(f"Immediate {sync_type} sync completed successfully")
                logger.info(f"  - Documents processed: {result.documents_processed}")
                logger.info(f"  - Documents indexed: {result.documents_indexed}")
                logger.info(f"  - Documents failed: {result.documents_failed}")
                logger.info(f"  - Duration: {result.duration:.2f} seconds")
                return 0
            else:
                logger.error(f"Immediate {sync_type} sync failed")
                for error in result.errors[:5]:  # Show first 5 errors
                    logger.error(f"  - {error}")
                return 1
                
    except Exception as e:
        logger.error(f"Critical error during immediate {sync_type} sync: {str(e)}")
        return 1


def run_health_check() -> int:
    """
    Run health check and exit.
    
    Returns:
        int: Exit code (0 for healthy, 1 for unhealthy)
    """
    logger.info("Running health check")
    
    try:
        with MongoToElasticSyncService(settings) as sync_service:
            health_status = sync_service.health_check()
            
            print("\n=== Health Check Results ===")
            print(f"Overall Status: {health_status.get('status', 'unknown').upper()}")
            
            # MongoDB status
            mongo_status = health_status.get('mongodb', {})
            print(f"\nMongoDB: {mongo_status.get('status', 'unknown').upper()}")
            if mongo_status.get('connected'):
                stats = mongo_status.get('stats', {})
                print(f"  - Database: {mongo_status.get('database', 'unknown')}")
                print(f"  - Collection: {mongo_status.get('collection', 'unknown')}")
                print(f"  - Total Documents: {stats.get('total_documents', 0):,}")
                print(f"  - Active Documents: {stats.get('active_documents', 0):,}")
            else:
                print(f"  - Error: {mongo_status.get('error', 'Connection failed')}")
            
            # Elasticsearch status
            es_status = health_status.get('elasticsearch', {})
            print(f"\nElasticsearch: {es_status.get('status', 'unknown').upper()}")
            if es_status.get('connected'):
                print(f"  - Cluster: {es_status.get('cluster_name', 'unknown')}")
                print(f"  - Cluster Status: {es_status.get('cluster_status', 'unknown')}")
                print(f"  - Index: {es_status.get('index', 'unknown')}")
                stats = es_status.get('stats', {})
                print(f"  - Documents: {stats.get('document_count', 0):,}")
            else:
                print(f"  - Error: {es_status.get('error', 'Connection failed')}")
            
            # Sync service status
            sync_status = health_status.get('sync_service', {})
            print(f"\nSync Service: {sync_status.get('status', 'unknown').upper()}")
            if sync_status.get('last_sync'):
                print(f"  - Last Sync: {sync_status.get('last_sync')}")
                print(f"  - Total Synced: {sync_status.get('total_synced', 0):,}")
            
            print("\n" + "="*30)
            
            if health_status.get('status') == 'healthy':
                logger.info("Health check passed")
                return 0
            else:
                logger.warning("Health check failed")
                return 1
                
    except Exception as e:
        logger.error(f"Critical error during health check: {str(e)}")
        print(f"\nHealth check failed with error: {str(e)}")
        return 1


def show_sync_status() -> int:
    """
    Show sync status and exit.
    
    Returns:
        int: Exit code (always 0)
    """
    logger.info("Showing sync status")
    
    try:
        with MongoToElasticSyncService(settings) as sync_service:
            status = sync_service.get_sync_status()
            
            print("\n=== Sync Status ===")
            print(f"Last Sync: {status.get('last_sync_time', 'Never')}")
            print(f"Last Full Sync: {status.get('last_full_sync', 'Never')}")
            print(f"Total Documents Synced: {status.get('total_documents_synced', 0):,}")
            
            if status.get('last_sync_duration'):
                print(f"Last Sync Duration: {status.get('last_sync_duration'):.2f} seconds")
            
            recent_errors = status.get('recent_errors', [])
            if recent_errors:
                print(f"\nRecent Errors ({len(recent_errors)}):")
                for i, error in enumerate(recent_errors[-5:], 1):  # Show last 5
                    print(f"  {i}. {error}")
            else:
                print("\nNo recent errors")
            
            # Performance metrics
            metrics = status.get('performance_metrics', {})
            if metrics:
                print("\nPerformance Metrics:")
                for operation, stats in metrics.items():
                    print(f"  {operation}:")
                    print(f"    - Count: {stats.get('count', 0)}")
                    print(f"    - Average: {stats.get('average', 0):.3f}s")
                    print(f"    - Min: {stats.get('min', 0):.3f}s")
                    print(f"    - Max: {stats.get('max', 0):.3f}s")
            
            print("\n" + "="*20)
            return 0
            
    except Exception as e:
        logger.error(f"Error showing sync status: {str(e)}")
        print(f"\nError retrieving sync status: {str(e)}")
        return 1


def run_scheduled_service() -> int:
    """
    Run the scheduled sync service.
    
    Returns:
        int: Exit code
    """
    logger.info("Starting StorySync - Story Content Synchronization Service")
    logger.info(f"Configuration:")
    logger.info(f"  - MongoDB: {settings.mongo_uri}")
    logger.info(f"  - Database: {settings.mongo_db}")
    logger.info(f"  - Collection: {settings.mongo_collection}")
    logger.info(f"  - Elasticsearch: {settings.es_url}")
    logger.info(f"  - Index: {settings.es_index}")
    logger.info(f"  - Sync Interval: {settings.sync_interval_minutes} minutes")
    logger.info(f"  - Batch Size: {settings.batch_size}")
    
    shutdown_handler = GracefulShutdownHandler()
    
    try:
        # Initialize sync service
        with MongoToElasticSyncService(settings) as sync_service:
            # Run initial health check
            logger.info("Performing initial health check...")
            health_status = sync_service.health_check()
            
            if health_status.get('status') != 'healthy':
                logger.error("Initial health check failed!")
                logger.error(f"MongoDB: {health_status.get('mongodb', {}).get('status', 'unknown')}")
                logger.error(f"Elasticsearch: {health_status.get('elasticsearch', {}).get('status', 'unknown')}")
                
                # Try to continue anyway, but warn user
                logger.warning("Continuing despite health check failure - service may not work properly")
            else:
                logger.info("Initial health check passed - all components healthy")
            
            # Initialize and start scheduler
            scheduler = SingletonScheduler.get_instance(settings, sync_service)
            scheduler.start()
            
            logger.info("Sync service started successfully")
            logger.info("Press Ctrl+C to stop the service gracefully")
            
            # Run an immediate sync to verify everything works
            logger.info("Running initial sync to verify setup...")
            try:
                initial_result = sync_service.run_incremental_sync()
                if initial_result.success:
                    logger.info(f"Initial sync completed: {initial_result.documents_processed} documents processed")
                else:
                    logger.warning("Initial sync had issues, but continuing with scheduled service")
            except Exception as e:
                logger.warning(f"Initial sync failed: {str(e)}, but continuing with scheduled service")
            
            # Main service loop - wait for shutdown signal
            try:
                while not shutdown_handler.is_shutdown_requested():
                    if shutdown_handler.wait_for_shutdown(timeout=10.0):
                        break
                    
                    # Optionally log periodic status
                    # This runs every 10 seconds, but we only log status occasionally
                    
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
            
            # Graceful shutdown
            logger.info("Shutting down sync service...")
            scheduler.stop()
            
            # Show final statistics
            scheduler_status = scheduler.get_scheduler_status()
            logger.info("Final Statistics:")
            logger.info(f"  - Total jobs executed: {scheduler_status.get('total_jobs_executed', 0)}")
            logger.info(f"  - Successful jobs: {scheduler_status.get('successful_jobs', 0)}")
            logger.info(f"  - Failed jobs: {scheduler_status.get('failed_jobs', 0)}")
            logger.info(f"  - Success rate: {scheduler_status.get('success_rate', 0):.1f}%")
            
            logger.info("Sync service stopped successfully")
            return 0
            
    except Exception as e:
        logger.error(f"Critical error in sync service: {str(e)}")
        return 1


def main() -> int:
    """
    Main function - entry point of the application.
    
    Returns:
        int: Exit code
    """
    try:
        args = parse_arguments()
        
        # Override log level if specified
        if args.log_level:
            import logging
            logging.getLogger().setLevel(getattr(logging, args.log_level))
        
        # Handle different run modes
        if args.health_check:
            return run_health_check()
        elif args.status:
            return show_sync_status()
        elif args.sync_now:
            return run_immediate_sync("incremental")
        elif args.full_sync:
            return run_immediate_sync("full")
        else:
            # Default: run scheduled service
            return run_scheduled_service()
            
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Unhandled error in main: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
