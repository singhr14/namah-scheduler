"""
MongoDB repository implementation following the Repository Pattern.
Handles all MongoDB operations with connection management and error handling.
"""
from typing import List, Optional, Dict, Any, Iterator
from datetime import datetime
import pymongo
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError, ConnectionFailure, ServerSelectionTimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..config.settings import Settings
from ..config.constants import MONGO_ACTIVE_FILTER, RETRY_STOP_AFTER_ATTEMPT, RETRY_WAIT_EXPONENTIAL_MULTIPLIER, RETRY_WAIT_EXPONENTIAL_MAX
from ..models.story_model import StoryDocument
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MongoRepository:
    """Repository class for MongoDB operations following Repository Pattern."""
    
    def __init__(self, settings: Settings):
        """Initialize MongoDB repository with settings."""
        self.settings = settings
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None
        self._collection: Optional[Collection] = None
        
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
        retry=retry_if_exception_type((ConnectionFailure, ServerSelectionTimeoutError))
    )
    def connect(self) -> None:
        """Establish connection to MongoDB with retry logic."""
        try:
            logger.info(f"Connecting to MongoDB: {self.settings.mongo_uri}")
            
            self._client = MongoClient(
                self.settings.mongo_uri,
                serverSelectionTimeoutMS=30000,  # 30 seconds
                connectTimeoutMS=20000,  # 20 seconds
                socketTimeoutMS=20000,  # 20 seconds
                maxPoolSize=10,
                retryWrites=True
            )
            
            # Test connection
            self._client.admin.command('ping')
            
            self._db = self._client[self.settings.mongo_db]
            self._collection = self._db[self.settings.mongo_collection]
            
            logger.info(f"Successfully connected to MongoDB database: {self.settings.mongo_db}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise
    
    def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self._client:
            try:
                self._client.close()
                logger.info("MongoDB connection closed")
            except Exception as e:
                logger.warning(f"Error closing MongoDB connection: {str(e)}")
            finally:
                self._client = None
                self._db = None
                self._collection = None
    
    def is_connected(self) -> bool:
        """Check if MongoDB connection is active."""
        if not self._client:
            return False
        
        try:
            self._client.admin.command('ping')
            return True
        except Exception:
            return False
    
    def ensure_connection(self) -> None:
        """Ensure MongoDB connection is active, reconnect if necessary."""
        if not self.is_connected():
            logger.warning("MongoDB connection lost, attempting to reconnect...")
            self.disconnect()
            self.connect()
    
    @retry(
        stop=stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
        wait=wait_exponential(multiplier=RETRY_WAIT_EXPONENTIAL_MULTIPLIER, max=RETRY_WAIT_EXPONENTIAL_MAX),
        retry=retry_if_exception_type(PyMongoError)
    )
    def fetch_all_documents(self, batch_size: int = 1000) -> Iterator[List[StoryDocument]]:
        """
        Fetch all documents from MongoDB collection in batches.
        
        Args:
            batch_size: Number of documents to fetch per batch
            
        Yields:
            List[StoryDocument]: Batches of story documents
        """
        self.ensure_connection()
        
        try:
            logger.info(f"Starting full fetch of all documents with batch size: {batch_size}")
            
            total_count = self._collection.count_documents(MONGO_ACTIVE_FILTER)
            logger.info(f"Total documents to fetch: {total_count}")
            
            processed = 0
            cursor = self._collection.find(MONGO_ACTIVE_FILTER).batch_size(batch_size)
            
            batch = []
            for doc in cursor:
                try:
                    story_doc = StoryDocument.from_mongo_doc(doc)
                    batch.append(story_doc)
                    
                    if len(batch) >= batch_size:
                        processed += len(batch)
                        logger.debug(f"Yielding batch of {len(batch)} documents (processed: {processed}/{total_count})")
                        yield batch
                        batch = []
                        
                except Exception as e:
                    logger.error(f"Error processing document {doc.get('_id', 'unknown')}: {str(e)}")
                    continue
            
            # Yield remaining documents
            if batch:
                processed += len(batch)
                logger.debug(f"Yielding final batch of {len(batch)} documents (processed: {processed}/{total_count})")
                yield batch
            
            logger.info(f"Completed full fetch: {processed} documents processed")
            
        except Exception as e:
            logger.error(f"Error fetching all documents: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
        wait=wait_exponential(multiplier=RETRY_WAIT_EXPONENTIAL_MULTIPLIER, max=RETRY_WAIT_EXPONENTIAL_MAX),
        retry=retry_if_exception_type(PyMongoError)
    )
    def fetch_updated_documents(self, since_time: datetime, batch_size: int = 1000) -> Iterator[List[StoryDocument]]:
        """
        Fetch documents updated since a specific time.
        
        Args:
            since_time: Fetch documents updated after this time
            batch_size: Number of documents to fetch per batch
            
        Yields:
            List[StoryDocument]: Batches of updated story documents
        """
        self.ensure_connection()
        
        try:
            logger.info(f"Fetching documents updated since: {since_time.isoformat()}")
            
            # Query for documents updated since the given time
            query = {
                **MONGO_ACTIVE_FILTER,
                "updated_at": {"$gt": since_time}
            }
            
            total_count = self._collection.count_documents(query)
            logger.info(f"Found {total_count} updated documents")
            
            if total_count == 0:
                return
            
            processed = 0
            cursor = self._collection.find(query).sort("updated_at", 1).batch_size(batch_size)
            
            batch = []
            for doc in cursor:
                try:
                    story_doc = StoryDocument.from_mongo_doc(doc)
                    batch.append(story_doc)
                    
                    if len(batch) >= batch_size:
                        processed += len(batch)
                        logger.debug(f"Yielding batch of {len(batch)} updated documents (processed: {processed}/{total_count})")
                        yield batch
                        batch = []
                        
                except Exception as e:
                    logger.error(f"Error processing updated document {doc.get('_id', 'unknown')}: {str(e)}")
                    continue
            
            # Yield remaining documents
            if batch:
                processed += len(batch)
                logger.debug(f"Yielding final batch of {len(batch)} updated documents (processed: {processed}/{total_count})")
                yield batch
            
            logger.info(f"Completed incremental fetch: {processed} updated documents processed")
            
        except Exception as e:
            logger.error(f"Error fetching updated documents: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
        wait=wait_exponential(multiplier=RETRY_WAIT_EXPONENTIAL_MULTIPLIER, max=RETRY_WAIT_EXPONENTIAL_MAX),
        retry=retry_if_exception_type(PyMongoError)
    )
    def get_latest_update_time(self) -> Optional[datetime]:
        """
        Get the latest update time from the collection.
        
        Returns:
            Optional[datetime]: Latest update time or None if no documents exist
        """
        self.ensure_connection()
        
        try:
            latest_doc = self._collection.find_one(
                MONGO_ACTIVE_FILTER,
                sort=[("updated_at", pymongo.DESCENDING)],
                projection={"updated_at": 1}
            )
            
            if latest_doc and "updated_at" in latest_doc:
                latest_time = latest_doc["updated_at"]
                logger.debug(f"Latest update time in collection: {latest_time}")
                return latest_time
            
            logger.debug("No documents with update time found")
            return None
            
        except Exception as e:
            logger.error(f"Error getting latest update time: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(RETRY_STOP_AFTER_ATTEMPT),
        wait=wait_exponential(multiplier=RETRY_WAIT_EXPONENTIAL_MULTIPLIER, max=RETRY_WAIT_EXPONENTIAL_MAX),
        retry=retry_if_exception_type(PyMongoError)
    )
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics.
        
        Returns:
            Dict[str, Any]: Collection statistics
        """
        self.ensure_connection()
        
        try:
            stats = self._db.command("collStats", self.settings.mongo_collection)
            
            # Add custom counts
            total_count = self._collection.count_documents({})
            active_count = self._collection.count_documents(MONGO_ACTIVE_FILTER)
            
            return {
                "total_documents": total_count,
                "active_documents": active_count,
                "collection_size": stats.get("size", 0),
                "storage_size": stats.get("storageSize", 0),
                "index_count": stats.get("nindexes", 0),
                "avg_obj_size": stats.get("avgObjSize", 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            raise
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on MongoDB connection.
        
        Returns:
            Dict[str, Any]: Health check results
        """
        try:
            self.ensure_connection()
            
            # Test basic operations
            ping_result = self._client.admin.command('ping')
            stats = self.get_collection_stats()
            
            return {
                "status": "healthy",
                "connected": True,
                "ping_ok": ping_result.get("ok") == 1,
                "database": self.settings.mongo_db,
                "collection": self.settings.mongo_collection,
                "stats": stats
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "database": self.settings.mongo_db,
                "collection": self.settings.mongo_collection
            }
