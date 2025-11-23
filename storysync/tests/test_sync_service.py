"""
Unit tests for the sync service module.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from typing import List

from ..core.sync_service import MongoToElasticSyncService
from ..models.story_model import StoryDocument, SyncState, SyncResult
from ..config.settings import Settings


class TestMongoToElasticSyncService:
    """Test cases for MongoToElasticSyncService."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = Mock(spec=Settings)
        settings.batch_size = 100
        settings.state_file = "test_state.json"
        return settings
    
    @pytest.fixture
    def mock_mongo_repo(self):
        """Create mock MongoDB repository."""
        repo = Mock()
        repo.__enter__ = Mock(return_value=repo)
        repo.__exit__ = Mock(return_value=None)
        return repo
    
    @pytest.fixture
    def mock_elastic_adapter(self):
        """Create mock Elasticsearch adapter."""
        adapter = Mock()
        adapter.__enter__ = Mock(return_value=adapter)
        adapter.__exit__ = Mock(return_value=None)
        return adapter
    
    @pytest.fixture
    def sample_documents(self):
        """Create sample story documents for testing."""
        return [
            StoryDocument(
                mongo_id="507f1f77bcf86cd799439011",
                title="Test Story 1",
                slug="test-story-1",
                status="published",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            ),
            StoryDocument(
                mongo_id="507f1f77bcf86cd799439012",
                title="Test Story 2",
                slug="test-story-2",
                status="published",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
        ]
    
    @pytest.fixture
    def sync_service(self, mock_settings, mock_mongo_repo, mock_elastic_adapter):
        """Create sync service with mocked dependencies."""
        with patch('mongo_es_sync.utils.helpers.load_sync_state') as mock_load_state:
            mock_load_state.return_value = SyncState()
            service = MongoToElasticSyncService(
                mock_settings,
                mock_mongo_repo,
                mock_elastic_adapter
            )
            return service
    
    def test_init(self, mock_settings, mock_mongo_repo, mock_elastic_adapter):
        """Test service initialization."""
        with patch('mongo_es_sync.utils.helpers.load_sync_state') as mock_load_state:
            mock_load_state.return_value = SyncState()
            
            service = MongoToElasticSyncService(
                mock_settings,
                mock_mongo_repo,
                mock_elastic_adapter
            )
            
            assert service.settings == mock_settings
            assert service.mongo_repo == mock_mongo_repo
            assert service.elastic_adapter == mock_elastic_adapter
            assert isinstance(service.sync_state, SyncState)
    
    def test_context_manager(self, sync_service, mock_mongo_repo, mock_elastic_adapter):
        """Test context manager functionality."""
        with sync_service as service:
            assert service == sync_service
        
        mock_mongo_repo.__enter__.assert_called_once()
        mock_mongo_repo.__exit__.assert_called_once()
        mock_elastic_adapter.__enter__.assert_called_once()
        mock_elastic_adapter.__exit__.assert_called_once()
    
    def test_run_full_sync_success(self, sync_service, mock_mongo_repo, mock_elastic_adapter, sample_documents):
        """Test successful full sync operation."""
        # Setup mocks
        mock_mongo_repo.fetch_all_documents.return_value = [sample_documents]
        mock_elastic_adapter.bulk_index_documents.return_value = (2, 0, [])
        
        with patch('mongo_es_sync.utils.helpers.save_sync_state') as mock_save_state:
            mock_save_state.return_value = True
            
            # Run full sync
            result = sync_service.run_full_sync()
            
            # Assertions
            assert isinstance(result, SyncResult)
            assert result.success is True
            assert result.documents_processed == 2
            assert result.documents_indexed == 2
            assert result.documents_failed == 0
            assert len(result.errors) == 0
            
            # Verify method calls
            mock_mongo_repo.fetch_all_documents.assert_called_once()
            mock_elastic_adapter.bulk_index_documents.assert_called_once_with(sample_documents)
            mock_save_state.assert_called_once()
    
    def test_run_full_sync_with_failures(self, sync_service, mock_mongo_repo, mock_elastic_adapter, sample_documents):
        """Test full sync with some failures."""
        # Setup mocks
        mock_mongo_repo.fetch_all_documents.return_value = [sample_documents]
        mock_elastic_adapter.bulk_index_documents.return_value = (1, 1, ["Error indexing document"])
        
        with patch('mongo_es_sync.utils.helpers.save_sync_state') as mock_save_state:
            mock_save_state.return_value = True
            
            # Run full sync
            result = sync_service.run_full_sync()
            
            # Assertions
            assert isinstance(result, SyncResult)
            assert result.success is True  # Should still be successful if some docs indexed
            assert result.documents_processed == 2
            assert result.documents_indexed == 1
            assert result.documents_failed == 1
            assert len(result.errors) == 1
    
    def test_run_incremental_sync_success(self, sync_service, mock_mongo_repo, mock_elastic_adapter, sample_documents):
        """Test successful incremental sync operation."""
        # Setup sync state with last sync time
        sync_service.sync_state.last_sync_time = datetime.now(timezone.utc)
        
        # Setup mocks
        mock_mongo_repo.fetch_updated_documents.return_value = [sample_documents]
        mock_elastic_adapter.bulk_index_documents.return_value = (2, 0, [])
        
        with patch('mongo_es_sync.utils.helpers.save_sync_state') as mock_save_state:
            mock_save_state.return_value = True
            
            # Run incremental sync
            result = sync_service.run_incremental_sync()
            
            # Assertions
            assert isinstance(result, SyncResult)
            assert result.success is True
            assert result.documents_processed == 2
            assert result.documents_indexed == 2
            assert result.documents_failed == 0
            
            # Verify method calls
            mock_mongo_repo.fetch_updated_documents.assert_called_once()
            mock_elastic_adapter.bulk_index_documents.assert_called_once_with(sample_documents)
    
    def test_run_incremental_sync_no_last_sync_time(self, sync_service):
        """Test incremental sync when no last sync time exists."""
        # Ensure no last sync time
        sync_service.sync_state.last_sync_time = None
        
        with patch.object(sync_service, 'run_full_sync') as mock_full_sync:
            mock_full_sync.return_value = SyncResult(success=True)
            
            # Run incremental sync
            result = sync_service.run_incremental_sync()
            
            # Should fall back to full sync
            mock_full_sync.assert_called_once()
    
    def test_run_incremental_sync_no_updates(self, sync_service, mock_mongo_repo, mock_elastic_adapter):
        """Test incremental sync when no documents need updating."""
        # Setup sync state with last sync time
        sync_service.sync_state.last_sync_time = datetime.now(timezone.utc)
        
        # Setup mocks - no documents returned
        mock_mongo_repo.fetch_updated_documents.return_value = []
        
        with patch('mongo_es_sync.utils.helpers.save_sync_state') as mock_save_state:
            mock_save_state.return_value = True
            
            # Run incremental sync
            result = sync_service.run_incremental_sync()
            
            # Assertions
            assert isinstance(result, SyncResult)
            assert result.success is True
            assert result.documents_processed == 0
            assert result.documents_indexed == 0
            assert result.documents_failed == 0
    
    def test_process_document_batch_success(self, sync_service, mock_elastic_adapter, sample_documents):
        """Test successful document batch processing."""
        mock_elastic_adapter.bulk_index_documents.return_value = (2, 0, [])
        
        processed, indexed, failed, errors = sync_service._process_document_batch(sample_documents, "test")
        
        assert processed == 2
        assert indexed == 2
        assert failed == 0
        assert len(errors) == 0
    
    def test_process_document_batch_with_failures(self, sync_service, mock_elastic_adapter, sample_documents):
        """Test document batch processing with failures."""
        mock_elastic_adapter.bulk_index_documents.return_value = (1, 1, ["Index error"])
        
        processed, indexed, failed, errors = sync_service._process_document_batch(sample_documents, "test")
        
        assert processed == 2
        assert indexed == 1
        assert failed == 1
        assert len(errors) == 1
    
    def test_process_document_batch_empty(self, sync_service):
        """Test processing empty document batch."""
        processed, indexed, failed, errors = sync_service._process_document_batch([], "test")
        
        assert processed == 0
        assert indexed == 0
        assert failed == 0
        assert len(errors) == 0
    
    def test_run_sync_cycle_incremental(self, sync_service):
        """Test sync cycle runs incremental sync by default."""
        with patch.object(sync_service, 'run_incremental_sync') as mock_incremental:
            mock_incremental.return_value = SyncResult(success=True)
            
            result = sync_service.run_sync_cycle()
            
            mock_incremental.assert_called_once()
            assert result.success is True
    
    def test_run_sync_cycle_force_full(self, sync_service):
        """Test sync cycle with forced full sync."""
        with patch.object(sync_service, 'run_full_sync') as mock_full:
            mock_full.return_value = SyncResult(success=True)
            
            result = sync_service.run_sync_cycle(force_full_sync=True)
            
            mock_full.assert_called_once()
            assert result.success is True
    
    def test_should_run_full_sync_no_previous_full_sync(self, sync_service):
        """Test should run full sync when no previous full sync exists."""
        sync_service.sync_state.last_full_sync = None
        
        # Should return False because _should_run_full_sync only checks time-based conditions
        # The None check is handled in run_sync_cycle
        assert sync_service._should_run_full_sync() is False
    
    def test_should_run_full_sync_old_full_sync(self, sync_service):
        """Test should run full sync when last full sync is old."""
        from datetime import timedelta
        
        # Set last full sync to 25 hours ago
        sync_service.sync_state.last_full_sync = datetime.now(timezone.utc) - timedelta(hours=25)
        
        assert sync_service._should_run_full_sync() is True
    
    def test_should_run_full_sync_many_errors(self, sync_service):
        """Test should run full sync when there are many recent errors."""
        sync_service.sync_state.sync_errors = ["error"] * 5
        
        assert sync_service._should_run_full_sync() is True
    
    def test_get_sync_status(self, sync_service):
        """Test getting sync status."""
        # Setup sync state
        now = datetime.now(timezone.utc)
        sync_service.sync_state.last_sync_time = now
        sync_service.sync_state.total_documents_synced = 100
        sync_service.sync_state.last_sync_duration = 30.5
        
        status = sync_service.get_sync_status()
        
        assert isinstance(status, dict)
        assert status['last_sync_time'] == now.isoformat()
        assert status['total_documents_synced'] == 100
        assert status['last_sync_duration'] == 30.5
        assert 'performance_metrics' in status
    
    def test_health_check_healthy(self, sync_service, mock_mongo_repo, mock_elastic_adapter):
        """Test health check when all components are healthy."""
        mock_mongo_repo.health_check.return_value = {"status": "healthy"}
        mock_elastic_adapter.health_check.return_value = {"status": "healthy"}
        
        health_status = sync_service.health_check()
        
        assert health_status['status'] == 'healthy'
        assert health_status['mongodb']['status'] == 'healthy'
        assert health_status['elasticsearch']['status'] == 'healthy'
        assert health_status['sync_service']['status'] == 'healthy'
    
    def test_health_check_unhealthy(self, sync_service, mock_mongo_repo, mock_elastic_adapter):
        """Test health check when components are unhealthy."""
        mock_mongo_repo.health_check.return_value = {"status": "unhealthy"}
        mock_elastic_adapter.health_check.return_value = {"status": "healthy"}
        
        health_status = sync_service.health_check()
        
        assert health_status['status'] == 'unhealthy'
        assert health_status['mongodb']['status'] == 'unhealthy'
        assert health_status['elasticsearch']['status'] == 'healthy'
    
    def test_health_check_exception(self, sync_service, mock_mongo_repo):
        """Test health check when exception occurs."""
        mock_mongo_repo.health_check.side_effect = Exception("Connection failed")
        
        health_status = sync_service.health_check()
        
        assert health_status['status'] == 'unhealthy'
        assert 'error' in health_status
        assert 'Connection failed' in health_status['error']
