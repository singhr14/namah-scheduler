"""
Unit tests for MongoDB repository and Elasticsearch adapter.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from bson import ObjectId

from ..core.mongo_repository import MongoRepository
from ..core.elastic_adapter import ElasticsearchAdapter
from ..models.story_model import StoryDocument
from ..config.settings import Settings


class TestMongoRepository:
    """Test cases for MongoRepository."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = Mock(spec=Settings)
        settings.mongo_uri = "mongodb://test:test@localhost:27017/test"
        settings.mongo_db = "test_db"
        settings.mongo_collection = "test_collection"
        return settings
    
    @pytest.fixture
    def mock_client(self):
        """Create mock MongoDB client."""
        client = Mock()
        db = Mock()
        collection = Mock()
        
        client.__getitem__.return_value = db
        db.__getitem__.return_value = collection
        client.admin.command.return_value = {"ok": 1}
        
        return client, db, collection
    
    @pytest.fixture
    def mongo_repo(self, mock_settings):
        """Create MongoDB repository with mocked client."""
        return MongoRepository(mock_settings)
    
    def test_init(self, mock_settings):
        """Test repository initialization."""
        repo = MongoRepository(mock_settings)
        
        assert repo.settings == mock_settings
        assert repo._client is None
        assert repo._db is None
        assert repo._collection is None
    
    @patch('mongo_es_sync.core.mongo_repository.MongoClient')
    def test_connect_success(self, mock_mongo_client, mongo_repo, mock_settings):
        """Test successful MongoDB connection."""
        client, db, collection = Mock(), Mock(), Mock()
        mock_mongo_client.return_value = client
        client.__getitem__.return_value = db
        db.__getitem__.return_value = collection
        client.admin.command.return_value = {"ok": 1}
        
        mongo_repo.connect()
        
        assert mongo_repo._client == client
        assert mongo_repo._db == db
        assert mongo_repo._collection == collection
        mock_mongo_client.assert_called_once()
        client.admin.command.assert_called_once_with('ping')
    
    @patch('mongo_es_sync.core.mongo_repository.MongoClient')
    def test_connect_failure(self, mock_mongo_client, mongo_repo):
        """Test MongoDB connection failure."""
        mock_mongo_client.side_effect = Exception("Connection failed")
        
        with pytest.raises(Exception, match="Connection failed"):
            mongo_repo.connect()
    
    def test_disconnect(self, mongo_repo):
        """Test MongoDB disconnection."""
        mock_client = Mock()
        mongo_repo._client = mock_client
        
        mongo_repo.disconnect()
        
        mock_client.close.assert_called_once()
        assert mongo_repo._client is None
        assert mongo_repo._db is None
        assert mongo_repo._collection is None
    
    def test_is_connected_true(self, mongo_repo):
        """Test is_connected when connected."""
        mock_client = Mock()
        mock_client.admin.command.return_value = {"ok": 1}
        mongo_repo._client = mock_client
        
        assert mongo_repo.is_connected() is True
        mock_client.admin.command.assert_called_once_with('ping')
    
    def test_is_connected_false_no_client(self, mongo_repo):
        """Test is_connected when no client."""
        assert mongo_repo.is_connected() is False
    
    def test_is_connected_false_ping_fails(self, mongo_repo):
        """Test is_connected when ping fails."""
        mock_client = Mock()
        mock_client.admin.command.side_effect = Exception("Ping failed")
        mongo_repo._client = mock_client
        
        assert mongo_repo.is_connected() is False
    
    def test_fetch_all_documents(self, mongo_repo):
        """Test fetching all documents."""
        # Setup mocks
        mock_collection = Mock()
        mongo_repo._collection = mock_collection
        mongo_repo.ensure_connection = Mock()
        
        # Mock documents
        mock_docs = [
            {"_id": ObjectId(), "title": "Test 1", "status": "published"},
            {"_id": ObjectId(), "title": "Test 2", "status": "published"}
        ]
        
        mock_collection.count_documents.return_value = 2
        mock_collection.find.return_value.batch_size.return_value = iter(mock_docs)
        
        # Test
        batches = list(mongo_repo.fetch_all_documents(batch_size=10))
        
        assert len(batches) == 1
        assert len(batches[0]) == 2
        assert all(isinstance(doc, StoryDocument) for doc in batches[0])
        
        mongo_repo.ensure_connection.assert_called_once()
        mock_collection.count_documents.assert_called_once()
        mock_collection.find.assert_called_once()
    
    def test_fetch_updated_documents(self, mongo_repo):
        """Test fetching updated documents."""
        # Setup mocks
        mock_collection = Mock()
        mongo_repo._collection = mock_collection
        mongo_repo.ensure_connection = Mock()
        
        since_time = datetime.now(timezone.utc)
        mock_docs = [
            {"_id": ObjectId(), "title": "Updated 1", "updated_at": since_time}
        ]
        
        mock_collection.count_documents.return_value = 1
        mock_collection.find.return_value.sort.return_value.batch_size.return_value = iter(mock_docs)
        
        # Test
        batches = list(mongo_repo.fetch_updated_documents(since_time, batch_size=10))
        
        assert len(batches) == 1
        assert len(batches[0]) == 1
        assert isinstance(batches[0][0], StoryDocument)
        
        mongo_repo.ensure_connection.assert_called_once()
        mock_collection.count_documents.assert_called_once()
        mock_collection.find.assert_called_once()
    
    def test_get_latest_update_time(self, mongo_repo):
        """Test getting latest update time."""
        mock_collection = Mock()
        mongo_repo._collection = mock_collection
        mongo_repo.ensure_connection = Mock()
        
        latest_time = datetime.now(timezone.utc)
        mock_collection.find_one.return_value = {"updated_at": latest_time}
        
        result = mongo_repo.get_latest_update_time()
        
        assert result == latest_time
        mongo_repo.ensure_connection.assert_called_once()
        mock_collection.find_one.assert_called_once()
    
    def test_get_latest_update_time_no_docs(self, mongo_repo):
        """Test getting latest update time when no documents exist."""
        mock_collection = Mock()
        mongo_repo._collection = mock_collection
        mongo_repo.ensure_connection = Mock()
        
        mock_collection.find_one.return_value = None
        
        result = mongo_repo.get_latest_update_time()
        
        assert result is None
    
    def test_get_collection_stats(self, mongo_repo):
        """Test getting collection statistics."""
        mock_db = Mock()
        mock_collection = Mock()
        mongo_repo._db = mock_db
        mongo_repo._collection = mock_collection
        mongo_repo.ensure_connection = Mock()
        
        mock_db.command.return_value = {
            "size": 1000,
            "storageSize": 2000,
            "nindexes": 3,
            "avgObjSize": 100
        }
        mock_collection.count_documents.side_effect = [500, 450]  # total, active
        
        stats = mongo_repo.get_collection_stats()
        
        assert stats["total_documents"] == 500
        assert stats["active_documents"] == 450
        assert stats["collection_size"] == 1000
        assert stats["storage_size"] == 2000
        assert stats["index_count"] == 3
        assert stats["avg_obj_size"] == 100
    
    def test_health_check_healthy(self, mongo_repo):
        """Test health check when healthy."""
        mongo_repo.ensure_connection = Mock()
        mongo_repo._client = Mock()
        mongo_repo._client.admin.command.return_value = {"ok": 1}
        
        with patch.object(mongo_repo, 'get_collection_stats') as mock_stats:
            mock_stats.return_value = {"total_documents": 100}
            
            health = mongo_repo.health_check()
            
            assert health["status"] == "healthy"
            assert health["connected"] is True
            assert health["ping_ok"] is True
    
    def test_health_check_unhealthy(self, mongo_repo):
        """Test health check when unhealthy."""
        mongo_repo.ensure_connection = Mock(side_effect=Exception("Connection failed"))
        
        health = mongo_repo.health_check()
        
        assert health["status"] == "unhealthy"
        assert health["connected"] is False
        assert "Connection failed" in health["error"]


class TestElasticsearchAdapter:
    """Test cases for ElasticsearchAdapter."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = Mock(spec=Settings)
        settings.es_url = "https://localhost:9200"
        settings.es_user = "elastic"
        settings.es_pass = "password"
        settings.es_index = "test_index"
        settings.es_timeout = 30
        settings.batch_size = 100
        return settings
    
    @pytest.fixture
    def elastic_adapter(self, mock_settings):
        """Create Elasticsearch adapter."""
        return ElasticsearchAdapter(mock_settings)
    
    @pytest.fixture
    def sample_documents(self):
        """Create sample documents for testing."""
        return [
            StoryDocument(
                mongo_id="507f1f77bcf86cd799439011",
                title="Test Story 1",
                slug="test-story-1",
                status="published"
            ),
            StoryDocument(
                mongo_id="507f1f77bcf86cd799439012",
                title="Test Story 2",
                slug="test-story-2",
                status="published"
            )
        ]
    
    def test_init(self, mock_settings):
        """Test adapter initialization."""
        adapter = ElasticsearchAdapter(mock_settings)
        
        assert adapter.settings == mock_settings
        assert adapter._client is None
    
    @patch('mongo_es_sync.core.elastic_adapter.Elasticsearch')
    def test_connect_success(self, mock_es_class, elastic_adapter):
        """Test successful Elasticsearch connection."""
        mock_client = Mock()
        mock_es_class.return_value = mock_client
        mock_client.ping.return_value = True
        mock_client.info.return_value = {
            "cluster_name": "test-cluster",
            "version": {"number": "8.0.0"}
        }
        
        with patch.object(elastic_adapter, '_ensure_index_exists'):
            elastic_adapter.connect()
        
        assert elastic_adapter._client == mock_client
        mock_client.ping.assert_called_once()
        mock_client.info.assert_called_once()
    
    @patch('mongo_es_sync.core.elastic_adapter.Elasticsearch')
    def test_connect_failure(self, mock_es_class, elastic_adapter):
        """Test Elasticsearch connection failure."""
        mock_client = Mock()
        mock_es_class.return_value = mock_client
        mock_client.ping.return_value = False
        
        with pytest.raises(Exception):
            elastic_adapter.connect()
    
    def test_disconnect(self, elastic_adapter):
        """Test Elasticsearch disconnection."""
        mock_client = Mock()
        elastic_adapter._client = mock_client
        
        elastic_adapter.disconnect()
        
        mock_client.close.assert_called_once()
        assert elastic_adapter._client is None
    
    def test_is_connected_true(self, elastic_adapter):
        """Test is_connected when connected."""
        mock_client = Mock()
        mock_client.ping.return_value = True
        elastic_adapter._client = mock_client
        
        assert elastic_adapter.is_connected() is True
    
    def test_is_connected_false_no_client(self, elastic_adapter):
        """Test is_connected when no client."""
        assert elastic_adapter.is_connected() is False
    
    def test_is_connected_false_ping_fails(self, elastic_adapter):
        """Test is_connected when ping fails."""
        mock_client = Mock()
        mock_client.ping.side_effect = Exception("Ping failed")
        elastic_adapter._client = mock_client
        
        assert elastic_adapter.is_connected() is False
    
    def test_ensure_index_exists_create_new(self, elastic_adapter):
        """Test ensuring index exists when it doesn't."""
        mock_client = Mock()
        elastic_adapter._client = mock_client
        elastic_adapter.ensure_connection = Mock()
        
        mock_client.indices.exists.return_value = False
        
        elastic_adapter._ensure_index_exists()
        
        mock_client.indices.exists.assert_called_once()
        mock_client.indices.create.assert_called_once()
    
    def test_ensure_index_exists_already_exists(self, elastic_adapter):
        """Test ensuring index exists when it already does."""
        mock_client = Mock()
        elastic_adapter._client = mock_client
        elastic_adapter.ensure_connection = Mock()
        
        mock_client.indices.exists.return_value = True
        
        elastic_adapter._ensure_index_exists()
        
        mock_client.indices.exists.assert_called_once()
        mock_client.indices.create.assert_not_called()
        mock_client.indices.put_mapping.assert_called_once()
    
    @patch('mongo_es_sync.core.elastic_adapter.bulk')
    def test_bulk_index_documents_success(self, mock_bulk, elastic_adapter, sample_documents):
        """Test successful bulk indexing."""
        elastic_adapter.ensure_connection = Mock()
        mock_bulk.return_value = (2, [])  # 2 successful, 0 failed
        
        success_count, failed_count, errors = elastic_adapter.bulk_index_documents(sample_documents)
        
        assert success_count == 2
        assert failed_count == 0
        assert len(errors) == 0
        mock_bulk.assert_called_once()
    
    @patch('mongo_es_sync.core.elastic_adapter.bulk')
    def test_bulk_index_documents_with_failures(self, mock_bulk, elastic_adapter, sample_documents):
        """Test bulk indexing with failures."""
        elastic_adapter.ensure_connection = Mock()
        failed_docs = [
            {"index": {"_id": "test", "error": {"type": "error", "reason": "test error"}}}
        ]
        mock_bulk.return_value = (1, failed_docs)  # 1 successful, 1 failed
        
        success_count, failed_count, errors = elastic_adapter.bulk_index_documents(sample_documents)
        
        assert success_count == 1
        assert failed_count == 1
        assert len(errors) == 1
        assert "test error" in errors[0]
    
    def test_bulk_index_documents_empty(self, elastic_adapter):
        """Test bulk indexing with empty document list."""
        elastic_adapter.ensure_connection = Mock()
        
        success_count, failed_count, errors = elastic_adapter.bulk_index_documents([])
        
        assert success_count == 0
        assert failed_count == 0
        assert len(errors) == 0
    
    def test_index_single_document_success(self, elastic_adapter, sample_documents):
        """Test successful single document indexing."""
        mock_client = Mock()
        elastic_adapter._client = mock_client
        elastic_adapter.ensure_connection = Mock()
        
        mock_client.index.return_value = {"result": "created"}
        
        result = elastic_adapter.index_single_document(sample_documents[0])
        
        assert result is True
        mock_client.index.assert_called_once()
    
    def test_index_single_document_failure(self, elastic_adapter, sample_documents):
        """Test failed single document indexing."""
        mock_client = Mock()
        elastic_adapter._client = mock_client
        elastic_adapter.ensure_connection = Mock()
        
        mock_client.index.side_effect = Exception("Index failed")
        
        result = elastic_adapter.index_single_document(sample_documents[0])
        
        assert result is False
    
    def test_delete_document_success(self, elastic_adapter):
        """Test successful document deletion."""
        mock_client = Mock()
        elastic_adapter._client = mock_client
        elastic_adapter.ensure_connection = Mock()
        
        mock_client.delete.return_value = {"result": "deleted"}
        
        result = elastic_adapter.delete_document("test_id")
        
        assert result is True
        mock_client.delete.assert_called_once()
    
    def test_delete_document_not_found(self, elastic_adapter):
        """Test document deletion when document not found."""
        from elasticsearch.exceptions import NotFoundError
        
        mock_client = Mock()
        elastic_adapter._client = mock_client
        elastic_adapter.ensure_connection = Mock()
        
        mock_client.delete.side_effect = NotFoundError("Not found")
        
        result = elastic_adapter.delete_document("test_id")
        
        assert result is True  # Should return True for not found
    
    def test_get_index_stats(self, elastic_adapter):
        """Test getting index statistics."""
        mock_client = Mock()
        elastic_adapter._client = mock_client
        elastic_adapter.ensure_connection = Mock()
        
        mock_client.indices.stats.return_value = {
            "indices": {
                "test_index": {
                    "total": {
                        "docs": {"count": 100, "deleted": 5},
                        "store": {"size_in_bytes": 1000},
                        "indexing": {"index_total": 150},
                        "search": {"query_total": 50}
                    }
                }
            }
        }
        
        stats = elastic_adapter.get_index_stats()
        
        assert stats["document_count"] == 100
        assert stats["deleted_count"] == 5
        assert stats["store_size"] == 1000
        assert stats["indexing_total"] == 150
        assert stats["search_total"] == 50
    
    def test_refresh_index_success(self, elastic_adapter):
        """Test successful index refresh."""
        mock_client = Mock()
        elastic_adapter._client = mock_client
        elastic_adapter.ensure_connection = Mock()
        
        mock_client.indices.refresh.return_value = {"_shards": {"failed": 0}}
        
        result = elastic_adapter.refresh_index()
        
        assert result is True
        mock_client.indices.refresh.assert_called_once()
    
    def test_refresh_index_failure(self, elastic_adapter):
        """Test failed index refresh."""
        mock_client = Mock()
        elastic_adapter._client = mock_client
        elastic_adapter.ensure_connection = Mock()
        
        mock_client.indices.refresh.side_effect = Exception("Refresh failed")
        
        result = elastic_adapter.refresh_index()
        
        assert result is False
    
    def test_health_check_healthy(self, elastic_adapter):
        """Test health check when healthy."""
        elastic_adapter.ensure_connection = Mock()
        mock_client = Mock()
        elastic_adapter._client = mock_client
        
        mock_client.cluster.health.return_value = {
            "status": "green",
            "cluster_name": "test-cluster"
        }
        
        with patch.object(elastic_adapter, 'get_index_stats') as mock_stats:
            mock_stats.return_value = {"document_count": 100}
            
            health = elastic_adapter.health_check()
            
            assert health["status"] == "healthy"
            assert health["connected"] is True
            assert health["cluster_status"] == "green"
    
    def test_health_check_unhealthy(self, elastic_adapter):
        """Test health check when unhealthy."""
        elastic_adapter.ensure_connection = Mock(side_effect=Exception("Connection failed"))
        
        health = elastic_adapter.health_check()
        
        assert health["status"] == "unhealthy"
        assert health["connected"] is False
        assert "Connection failed" in health["error"]
