"""
Core synchronization service that orchestrates data sync between MongoDB and Elasticsearch.
Implements the main business logic following Clean Architecture principles.
"""
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
import time

from ..config.settings import Settings
from ..models.story_model import StoryDocument, SyncState, SyncResult
from ..core.mongo_repository import MongoRepository
from ..core.elastic_adapter import ElasticsearchAdapter
from ..utils.logger import get_logger, log_sync_metrics, LoggerContextManager
from ..utils.helpers import (
    get_utc_now, 
    load_sync_state, 
    save_sync_state, 
    format_duration,
    timing_decorator,
    PerformanceMonitor
)

logger = get_logger(__name__)


class MongoToElasticSyncService:
    """
    Core synchronization service that handles data sync between MongoDB and Elasticsearch.
    Follows Clean Architecture principles with dependency injection.
    """
    
    def __init__(
        self, 
        settings: Settings,
        mongo_repo: Optional[MongoRepository] = None,
        elastic_adapter: Optional[ElasticsearchAdapter] = None
    ):
        """
        Initialize sync service with dependencies.
        
        Args:
            settings: Application settings
            mongo_repo: MongoDB repository (injected for testing)
            elastic_adapter: Elasticsearch adapter (injected for testing)
        """
        self.settings = settings
        self.mongo_repo = mongo_repo or MongoRepository(settings)
        self.elastic_adapter = elastic_adapter or ElasticsearchAdapter(settings)
        self.performance_monitor = PerformanceMonitor()
        
        # Load sync state
        self.sync_state = load_sync_state(settings.state_file)
        
        logger.info("MongoToElasticSyncService initialized")
    
    def __enter__(self):
        """Context manager entry."""
        self.mongo_repo.__enter__()
        self.elastic_adapter.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.mongo_repo.__exit__(exc_type, exc_val, exc_tb)
        self.elastic_adapter.__exit__(exc_type, exc_val, exc_tb)
    
    @timing_decorator
    def run_full_sync(self) -> SyncResult:
        """
        Perform full synchronization of all documents.
        
        Returns:
            SyncResult: Results of the sync operation
        """
        with LoggerContextManager("full_sync"):
            logger.info("Starting full synchronization")
            
            sync_result = SyncResult(
                success=False,
                start_time=get_utc_now()
            )
            
            try:
                self.performance_monitor.start_timer("full_sync")
                
                total_processed = 0
                total_indexed = 0
                total_failed = 0
                all_errors = []
                
                # Fetch and process documents in batches
                for batch in self.mongo_repo.fetch_all_documents(self.settings.batch_size):
                    if not batch:
                        continue
                    
                    batch_result = self._process_document_batch(batch, "full_sync")
                    
                    total_processed += batch_result[0]
                    total_indexed += batch_result[1]
                    total_failed += batch_result[2]
                    all_errors.extend(batch_result[3])
                    
                    logger.debug(f"Processed batch: {len(batch)} documents")
                
                # Update sync result
                sync_result.documents_processed = total_processed
                sync_result.documents_indexed = total_indexed
                sync_result.documents_failed = total_failed
                sync_result.errors = all_errors
                sync_result.success = total_failed == 0 or (total_indexed > 0 and total_failed < total_processed)
                sync_result.end_time = get_utc_now()
                sync_result.duration = self.performance_monitor.end_timer("full_sync")
                
                # Update sync state
                self.sync_state.last_full_sync = sync_result.end_time
                self.sync_state.last_sync_time = sync_result.end_time
                self.sync_state.total_documents_synced += total_indexed
                self.sync_state.last_sync_duration = sync_result.duration
                
                if all_errors:
                    self.sync_state.sync_errors = all_errors[-10:]  # Keep last 10 errors
                
                # Save state
                save_sync_state(self.settings.state_file, self.sync_state)
                
                # Log metrics
                log_sync_metrics(
                    "full",
                    total_processed,
                    total_indexed,
                    total_failed,
                    sync_result.duration,
                    all_errors
                )
                
                logger.info(f"Full sync completed: {total_indexed}/{total_processed} documents indexed in {format_duration(sync_result.duration)}")
                
                return sync_result
                
            except Exception as e:
                error_msg = f"Full sync failed: {str(e)}"
                logger.error(error_msg)
                
                sync_result.success = False
                sync_result.errors = [error_msg]
                sync_result.end_time = get_utc_now()
                sync_result.duration = self.performance_monitor.end_timer("full_sync")
                
                return sync_result
    
    @timing_decorator
    def run_incremental_sync(self, since_time: Optional[datetime] = None) -> SyncResult:
        """
        Perform incremental synchronization of updated documents.
        
        Args:
            since_time: Sync documents updated since this time (defaults to last sync time)
            
        Returns:
            SyncResult: Results of the sync operation
        """
        with LoggerContextManager("incremental_sync"):
            # Determine since time
            if since_time is None:
                since_time = self.sync_state.last_sync_time
            
            if since_time is None:
                logger.warning("No previous sync time found, performing full sync instead")
                return self.run_full_sync()
            
            logger.info(f"Starting incremental synchronization since: {since_time.isoformat()}")
            
            sync_result = SyncResult(
                success=False,
                start_time=get_utc_now()
            )
            
            try:
                self.performance_monitor.start_timer("incremental_sync")
                
                total_processed = 0
                total_indexed = 0
                total_failed = 0
                all_errors = []
                
                # Fetch and process updated documents in batches
                for batch in self.mongo_repo.fetch_updated_documents(since_time, self.settings.batch_size):
                    if not batch:
                        continue
                    
                    batch_result = self._process_document_batch(batch, "incremental_sync")
                    
                    total_processed += batch_result[0]
                    total_indexed += batch_result[1]
                    total_failed += batch_result[2]
                    all_errors.extend(batch_result[3])
                    
                    logger.debug(f"Processed incremental batch: {len(batch)} documents")
                
                # Update sync result
                sync_result.documents_processed = total_processed
                sync_result.documents_indexed = total_indexed
                sync_result.documents_failed = total_failed
                sync_result.errors = all_errors
                sync_result.success = total_failed == 0 or (total_processed == 0) or (total_indexed > 0 and total_failed < total_processed)
                sync_result.end_time = get_utc_now()
                sync_result.duration = self.performance_monitor.end_timer("incremental_sync")
                
                # Update sync state only if we processed some documents or had no updates
                if total_processed > 0 or total_processed == 0:
                    self.sync_state.last_sync_time = sync_result.end_time
                    self.sync_state.total_documents_synced += total_indexed
                    self.sync_state.last_sync_duration = sync_result.duration
                    
                    if all_errors:
                        self.sync_state.sync_errors = all_errors[-10:]  # Keep last 10 errors
                    
                    # Save state
                    save_sync_state(self.settings.state_file, self.sync_state)
                
                # Log metrics
                log_sync_metrics(
                    "incremental",
                    total_processed,
                    total_indexed,
                    total_failed,
                    sync_result.duration,
                    all_errors
                )
                
                if total_processed == 0:
                    logger.info("Incremental sync completed: No new documents to sync")
                else:
                    logger.info(f"Incremental sync completed: {total_indexed}/{total_processed} documents indexed in {format_duration(sync_result.duration)}")
                
                return sync_result
                
            except Exception as e:
                error_msg = f"Incremental sync failed: {str(e)}"
                logger.error(error_msg)
                
                sync_result.success = False
                sync_result.errors = [error_msg]
                sync_result.end_time = get_utc_now()
                sync_result.duration = self.performance_monitor.end_timer("incremental_sync")
                
                return sync_result
    
    def _process_document_batch(self, documents: List[StoryDocument], operation: str) -> Tuple[int, int, int, List[str]]:
        """
        Process a batch of documents for indexing.
        
        Args:
            documents: List of documents to process
            operation: Operation type for logging
            
        Returns:
            Tuple[int, int, int, List[str]]: (processed, indexed, failed, errors)
        """
        if not documents:
            return 0, 0, 0, []
        
        try:
            # Transform documents if needed (already handled in StoryDocument.to_elasticsearch_doc)
            transformed_docs = []
            transform_errors = []
            
            for doc in documents:
                try:
                    # Additional transformation logic can be added here
                    transformed_docs.append(doc)
                except Exception as e:
                    error_msg = f"Error transforming document {doc.mongo_id}: {str(e)}"
                    transform_errors.append(error_msg)
                    logger.error(error_msg)
            
            if not transformed_docs:
                return len(documents), 0, len(documents), transform_errors
            
            # Bulk index to Elasticsearch
            indexed_count, failed_count, index_errors = self.elastic_adapter.bulk_index_documents(transformed_docs)
            
            total_errors = transform_errors + index_errors
            
            return len(documents), indexed_count, failed_count + len(transform_errors), total_errors
            
        except Exception as e:
            error_msg = f"Critical error processing batch: {str(e)}"
            logger.error(error_msg)
            return len(documents), 0, len(documents), [error_msg]
    
    @timing_decorator
    def run_sync_cycle(self, force_full_sync: bool = False) -> SyncResult:
        """
        Run a complete sync cycle (incremental or full based on conditions).
        
        Args:
            force_full_sync: Force a full sync regardless of conditions
            
        Returns:
            SyncResult: Results of the sync operation
        """
        with LoggerContextManager("sync_cycle"):
            logger.info("Starting sync cycle")
            
            try:
                # Determine sync type
                should_run_full_sync = (
                    force_full_sync or
                    self.sync_state.last_full_sync is None or
                    self._should_run_full_sync()
                )
                
                if should_run_full_sync:
                    logger.info("Running full synchronization")
                    return self.run_full_sync()
                else:
                    logger.info("Running incremental synchronization")
                    return self.run_incremental_sync()
                    
            except Exception as e:
                error_msg = f"Sync cycle failed: {str(e)}"
                logger.error(error_msg)
                
                return SyncResult(
                    success=False,
                    errors=[error_msg],
                    start_time=get_utc_now(),
                    end_time=get_utc_now()
                )
    
    def _should_run_full_sync(self) -> bool:
        """
        Determine if a full sync should be run based on conditions.
        
        Returns:
            bool: True if full sync should be run
        """
        # Run full sync if last full sync was more than 24 hours ago
        if self.sync_state.last_full_sync:
            time_since_full_sync = get_utc_now() - self.sync_state.last_full_sync
            if time_since_full_sync > timedelta(hours=24):
                logger.info("Last full sync was more than 24 hours ago, running full sync")
                return True
        
        # Run full sync if there have been too many recent errors
        if len(self.sync_state.sync_errors) >= 5:
            logger.info("Too many recent sync errors, running full sync")
            return True
        
        return False
    
    def get_sync_status(self) -> dict:
        """
        Get current sync status and statistics.
        
        Returns:
            dict: Sync status information
        """
        return {
            "last_sync_time": self.sync_state.last_sync_time.isoformat() if self.sync_state.last_sync_time else None,
            "last_full_sync": self.sync_state.last_full_sync.isoformat() if self.sync_state.last_full_sync else None,
            "total_documents_synced": self.sync_state.total_documents_synced,
            "last_sync_duration": self.sync_state.last_sync_duration,
            "recent_errors": self.sync_state.sync_errors,
            "performance_metrics": self.performance_monitor.get_metrics_summary()
        }
    
    def health_check(self) -> dict:
        """
        Perform health check on all components.
        
        Returns:
            dict: Health check results
        """
        try:
            mongo_health = self.mongo_repo.health_check()
            es_health = self.elastic_adapter.health_check()
            
            overall_healthy = (
                mongo_health.get("status") == "healthy" and 
                es_health.get("status") == "healthy"
            )
            
            return {
                "status": "healthy" if overall_healthy else "unhealthy",
                "mongodb": mongo_health,
                "elasticsearch": es_health,
                "sync_service": {
                    "status": "healthy",
                    "last_sync": self.sync_state.last_sync_time.isoformat() if self.sync_state.last_sync_time else None,
                    "total_synced": self.sync_state.total_documents_synced
                }
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "mongodb": {"status": "unknown"},
                "elasticsearch": {"status": "unknown"},
                "sync_service": {"status": "error", "error": str(e)}
            }
