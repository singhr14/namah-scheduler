"""
Elasticsearch adapter implementation following the Adapter Pattern.
Handles all Elasticsearch operations with connection management and bulk operations.
"""
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import (
    ConnectionError, 
    RequestError, 
    NotFoundError, 
    ConflictError,
    TransportError
)
from elasticsearch.helpers import bulk, BulkIndexError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..config.settings import Settings
from ..config.constants import (
    ES_INDEX_MAPPING, 
    RETRY_STOP_AFTER_ATTEMPT, 
    RETRY_WAIT_EXPONENTIAL_MULTIPLIER, 
    RETRY_WAIT_EXPONENTIAL_MAX
)
from ..models.story_model import StoryDocument
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ElasticsearchAdapter:
    """Adapter class for Elasticsearch operations following Adapter Pattern."""
    
    def __init__(self, settings: Settings):
        """Initialize Elasticsearch adapter with settings."""
        self.settings = settings
        self._client: Optional[Elasticsearch] = None
        
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    @retry(
        stop=stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
        wait=wait_exponential(multiplier=RETRY_WAIT_EXPONENTIAL_MULTIPLIER, max=RETRY_WAIT_EXPONENTIAL_MAX),
        retry=retry_if_exception_type((ConnectionError, TransportError))
    )
    def connect(self) -> None:
        """Establish connection to Elasticsearch with retry logic."""
        try:
            logger.info(f"Connecting to Elasticsearch: {self.settings.es_url}")
            
            self._client = Elasticsearch(
                hosts=[self.settings.es_url],
                basic_auth=(self.settings.es_user, self.settings.es_pass),
                request_timeout=self.settings.es_timeout,
                verify_certs=False,
                ssl_show_warn=False,
                ssl_assert_hostname=False,
                ssl_assert_fingerprint=None
            )
            
            # Test connection by getting cluster info directly (more reliable than ping)
            try:
                info = self._client.info()
                logger.info(f"Connected to Elasticsearch cluster: {info['cluster_name']} (version: {info['version']['number']})")
            except Exception as e:
                raise ConnectionError(f"Failed to get cluster info: {str(e)}")
            
            # Ensure index exists with proper mapping
            self._ensure_index_exists()
            
        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {str(e)}")
            raise
    
    def disconnect(self) -> None:
        """Close Elasticsearch connection."""
        if self._client:
            try:
                self._client.close()
                logger.info("Elasticsearch connection closed")
            except Exception as e:
                logger.warning(f"Error closing Elasticsearch connection: {str(e)}")
            finally:
                self._client = None
    
    def is_connected(self) -> bool:
        """Check if Elasticsearch connection is active."""
        if not self._client:
            return False
        
        try:
            return self._client.ping()
        except Exception:
            return False
    
    def ensure_connection(self) -> None:
        """Ensure Elasticsearch connection is active, reconnect if necessary."""
        if not self.is_connected():
            logger.warning("Elasticsearch connection lost, attempting to reconnect...")
            self.disconnect()
            self.connect()
    
    @retry(
        stop=stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
        wait=wait_exponential(multiplier=RETRY_WAIT_EXPONENTIAL_MULTIPLIER, max=RETRY_WAIT_EXPONENTIAL_MAX),
        retry=retry_if_exception_type((ConnectionError, TransportError))
    )
    def _ensure_index_exists(self) -> None:
        """Ensure the target index exists with proper mapping."""
        try:
            index_name = self.settings.es_index
            
            if not self._client.indices.exists(index=index_name):
                logger.info(f"Creating Elasticsearch index: {index_name}")
                
                self._client.indices.create(
                    index=index_name,
                    body=ES_INDEX_MAPPING
                )
                
                logger.info(f"Successfully created index: {index_name}")
            else:
                logger.debug(f"Index already exists: {index_name}")
                
                # Optionally update mapping for existing index
                try:
                    self._client.indices.put_mapping(
                        index=index_name,
                        body=ES_INDEX_MAPPING["mappings"]
                    )
                    logger.debug(f"Updated mapping for index: {index_name}")
                except Exception as e:
                    logger.warning(f"Could not update mapping for existing index: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error ensuring index exists: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
        wait=wait_exponential(multiplier=RETRY_WAIT_EXPONENTIAL_MULTIPLIER, max=RETRY_WAIT_EXPONENTIAL_MAX),
        retry=retry_if_exception_type((ConnectionError, TransportError))
    )
    def bulk_index_documents(self, documents: List[StoryDocument]) -> Tuple[int, int, List[str]]:
        """
        Bulk index documents to Elasticsearch.
        
        Args:
            documents: List of StoryDocument objects to index
            
        Returns:
            Tuple[int, int, List[str]]: (successful_count, failed_count, error_messages)
        """
        self.ensure_connection()
        
        if not documents:
            logger.warning("No documents provided for bulk indexing")
            return 0, 0, []
        
        try:
            logger.info(f"Starting bulk index of {len(documents)} documents")
            
            # Prepare bulk actions
            actions = []
            for doc in documents:
                try:
                    es_doc = doc.to_elasticsearch_doc()
                    
                    action = {
                        "_index": self.settings.es_index,
                        "_id": doc.mongo_id,  # Use MongoDB ID as Elasticsearch document ID
                        "_source": es_doc
                    }
                    actions.append(action)
                    
                except Exception as e:
                    logger.error(f"Error preparing document {doc.mongo_id} for indexing: {str(e)}")
                    continue
            
            if not actions:
                logger.warning("No valid actions prepared for bulk indexing")
                return 0, len(documents), ["No valid documents to index"]
            
            # Execute bulk operation
            success_count = 0
            failed_count = 0
            error_messages = []
            
            try:
                success, failed = bulk(
                    self._client,
                    actions,
                    index=self.settings.es_index,
                    chunk_size=self.settings.batch_size,
                    request_timeout=self.settings.es_timeout,
                    max_retries=3,
                    initial_backoff=2,
                    max_backoff=600
                )
                
                success_count = success
                failed_count = len(failed)
                
                # Process failed documents
                for failed_doc in failed:
                    error_info = failed_doc.get('index', {})
                    error_msg = error_info.get('error', {})
                    doc_id = error_info.get('_id', 'unknown')
                    
                    if isinstance(error_msg, dict):
                        error_text = f"Document {doc_id}: {error_msg.get('type', 'unknown')} - {error_msg.get('reason', 'no reason')}"
                    else:
                        error_text = f"Document {doc_id}: {str(error_msg)}"
                    
                    error_messages.append(error_text)
                    logger.error(error_text)
                
                logger.info(f"Bulk indexing completed: {success_count} successful, {failed_count} failed")
                
            except BulkIndexError as e:
                logger.error(f"Bulk index error: {str(e)}")
                
                # Process errors from BulkIndexError
                for error in e.errors:
                    error_info = error.get('index', {})
                    error_msg = error_info.get('error', {})
                    doc_id = error_info.get('_id', 'unknown')
                    
                    if isinstance(error_msg, dict):
                        error_text = f"Document {doc_id}: {error_msg.get('type', 'unknown')} - {error_msg.get('reason', 'no reason')}"
                    else:
                        error_text = f"Document {doc_id}: {str(error_msg)}"
                    
                    error_messages.append(error_text)
                    failed_count += 1
                
                success_count = len(documents) - failed_count
            
            return success_count, failed_count, error_messages
            
        except Exception as e:
            error_msg = f"Critical error during bulk indexing: {str(e)}"
            logger.error(error_msg)
            return 0, len(documents), [error_msg]
    
    @retry(
        stop=stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
        wait=wait_exponential(multiplier=RETRY_WAIT_EXPONENTIAL_MULTIPLIER, max=RETRY_WAIT_EXPONENTIAL_MAX),
        retry=retry_if_exception_type((ConnectionError, TransportError))
    )
    def index_single_document(self, document: StoryDocument) -> bool:
        """
        Index a single document to Elasticsearch.
        
        Args:
            document: StoryDocument to index
            
        Returns:
            bool: True if successful, False otherwise
        """
        self.ensure_connection()
        
        try:
            es_doc = document.to_elasticsearch_doc()
            
            response = self._client.index(
                index=self.settings.es_index,
                id=document.mongo_id,
                body=es_doc,
                timeout=f"{self.settings.es_timeout}s"
            )
            
            success = response.get('result') in ['created', 'updated']
            if success:
                logger.debug(f"Successfully indexed document: {document.mongo_id}")
            else:
                logger.warning(f"Unexpected result for document {document.mongo_id}: {response.get('result')}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error indexing single document {document.mongo_id}: {str(e)}")
            return False
    
    @retry(
        stop=stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
        wait=wait_exponential(multiplier=RETRY_WAIT_EXPONENTIAL_MULTIPLIER, max=RETRY_WAIT_EXPONENTIAL_MAX),
        retry=retry_if_exception_type((ConnectionError, TransportError))
    )
    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from Elasticsearch.
        
        Args:
            document_id: ID of document to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        self.ensure_connection()
        
        try:
            response = self._client.delete(
                index=self.settings.es_index,
                id=document_id,
                timeout=f"{self.settings.es_timeout}s"
            )
            
            success = response.get('result') == 'deleted'
            if success:
                logger.debug(f"Successfully deleted document: {document_id}")
            else:
                logger.warning(f"Document not found for deletion: {document_id}")
            
            return success
            
        except NotFoundError:
            logger.warning(f"Document not found for deletion: {document_id}")
            return True  # Consider it successful if already not there
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {str(e)}")
            return False
    
    @retry(
        stop=stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
        wait=wait_exponential(multiplier=RETRY_WAIT_EXPONENTIAL_MULTIPLIER, max=RETRY_WAIT_EXPONENTIAL_MAX),
        retry=retry_if_exception_type((ConnectionError, TransportError))
    )
    def get_index_stats(self) -> Dict[str, Any]:
        """
        Get index statistics.
        
        Returns:
            Dict[str, Any]: Index statistics
        """
        self.ensure_connection()
        
        try:
            stats = self._client.indices.stats(index=self.settings.es_index)
            index_stats = stats['indices'][self.settings.es_index]
            
            return {
                "document_count": index_stats['total']['docs']['count'],
                "deleted_count": index_stats['total']['docs']['deleted'],
                "store_size": index_stats['total']['store']['size_in_bytes'],
                "indexing_total": index_stats['total']['indexing']['index_total'],
                "search_total": index_stats['total']['search']['query_total']
            }
            
        except Exception as e:
            logger.error(f"Error getting index stats: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
        wait=wait_exponential(multiplier=RETRY_WAIT_EXPONENTIAL_MULTIPLIER, max=RETRY_WAIT_EXPONENTIAL_MAX),
        retry=retry_if_exception_type((ConnectionError, TransportError))
    )
    def refresh_index(self) -> bool:
        """
        Refresh the index to make recent changes searchable.
        
        Returns:
            bool: True if successful, False otherwise
        """
        self.ensure_connection()
        
        try:
            response = self._client.indices.refresh(index=self.settings.es_index)
            success = response.get('_shards', {}).get('failed', 0) == 0
            
            if success:
                logger.debug(f"Successfully refreshed index: {self.settings.es_index}")
            else:
                logger.warning(f"Index refresh had failures: {response}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error refreshing index: {str(e)}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on Elasticsearch connection.
        
        Returns:
            Dict[str, Any]: Health check results
        """
        try:
            self.ensure_connection()
            
            # Test basic operations
            cluster_health = self._client.cluster.health()
            index_stats = self.get_index_stats()
            
            return {
                "status": "healthy",
                "connected": True,
                "cluster_status": cluster_health.get("status"),
                "cluster_name": cluster_health.get("cluster_name"),
                "index": self.settings.es_index,
                "stats": index_stats
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "index": self.settings.es_index
            }
