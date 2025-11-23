# StorySync - Story Content Synchronization Service

A production-grade Python service for synchronizing story content between MongoDB and Elasticsearch with enterprise-level features including structured logging, health monitoring, graceful shutdown, and comprehensive error handling. Designed specifically for story collections with support for deities, themes, tags, and multi-language content.

## 🚀 Features

- **Full & Incremental Sync**: Supports both complete reindexing and delta updates based on `updated_at` timestamps
- **Enterprise Architecture**: Clean Architecture with SOLID principles, dependency injection, and design patterns
- **Robust Error Handling**: Retry logic with exponential backoff, comprehensive error logging
- **Structured Logging**: JSON-formatted logs with rotation, performance metrics, and health monitoring
- **Graceful Shutdown**: Proper signal handling (SIGTERM/SIGINT) for clean service termination
- **Health Monitoring**: Built-in health checks for MongoDB, Elasticsearch, and sync service components
- **Configurable**: Environment-based configuration with validation using Pydantic
- **Testable**: Comprehensive unit tests with mocking and dependency injection
- **Production Ready**: Docker support, performance monitoring, and operational tooling

## 📋 Requirements

- Python 3.8+
- MongoDB 4.4+
- Elasticsearch 8.0+
- Network access to both MongoDB and Elasticsearch clusters

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd storysync
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.template .env
# OR
cp storysync/config/.env.example .env
```

Edit `.env` file with your configuration:

```env
# MongoDB Configuration
MONGO_URI=mongodb://username:password@host:port/?authSource=database
MONGO_DB=your_database_name
MONGO_COLLECTION=stories

# Elasticsearch Configuration
ES_URL=https://your-elasticsearch-url.com/
ES_USER=your_elasticsearch_username
ES_PASS=your_elasticsearch_password
ES_INDEX=stories_index
ES_TIMEOUT=30

# Sync Configuration
SYNC_INTERVAL_MINUTES=10
BATCH_SIZE=1000
MAX_RETRIES=3
RETRY_DELAY=5

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=logs/storysync.log
LOG_ROTATION=1 day
LOG_RETENTION=30 days

# State Management
STATE_FILE=state/last_sync.json
```

## 🚀 Usage

### Running the Service

#### 1. Start Scheduled Sync Service (Default)

```bash
python -m storysync.main
```

This starts the service with periodic synchronization based on the configured interval.

#### 2. Run Immediate Sync

```bash
# Incremental sync
python -m storysync.main --sync-now

# Full sync
python -m storysync.main --full-sync
```

#### 3. Health Check

```bash
python -m storysync.main --health-check
```

#### 4. Show Sync Status

```bash
python -m storysync.main --status
```

### Command Line Options

```bash
python -m storysync.main --help
```

Available options:
- `--sync-now`: Run immediate incremental sync and exit
- `--full-sync`: Run immediate full sync and exit
- `--health-check`: Run health check and exit
- `--status`: Show sync status and exit
- `--config PATH`: Path to configuration file
- `--log-level LEVEL`: Override log level (DEBUG, INFO, WARNING, ERROR)

## 🏗️ Architecture

The service follows Clean Architecture principles with clear separation of concerns:

```
storysync/
├── main.py                 # Entry point and CLI
├── config/                 # Configuration management
│   ├── settings.py         # Pydantic settings with env validation
│   ├── constants.py        # Application constants
│   └── .env.example        # Environment template
├── core/                   # Core business logic
│   ├── mongo_repository.py # MongoDB data access (Repository Pattern)
│   ├── elastic_adapter.py  # Elasticsearch operations (Adapter Pattern)
│   ├── sync_service.py     # Main sync orchestration
│   └── scheduler.py        # Job scheduling and management
├── models/                 # Data models
│   └── story_model.py      # Pydantic models for validation
├── utils/                  # Utilities and helpers
│   ├── logger.py           # Structured logging setup
│   └── helpers.py          # Common utilities and decorators
└── tests/                  # Unit tests
    ├── test_sync_service.py
    └── test_adapters.py
```

### Design Patterns Used

- **Repository Pattern**: `MongoRepository` abstracts MongoDB operations
- **Adapter Pattern**: `ElasticsearchAdapter` handles ES-specific operations
- **Dependency Injection**: Services accept dependencies for testability
- **Singleton Pattern**: Shared logger and scheduler instances
- **Strategy Pattern**: Different sync strategies (full vs incremental)

## 📊 Data Flow

1. **MongoDB Source**: Reads documents from `stories` collection
2. **Transformation**: Converts MongoDB documents to Elasticsearch format
3. **Elasticsearch Target**: Bulk indexes documents to `stories_index`
4. **State Tracking**: Maintains sync state in JSON file for incremental updates

### Document Schema Mapping

| MongoDB Field | Elasticsearch Field | Type | Description |
|---------------|-------------------|------|-------------|
| `_id` | `mongo_id` | keyword | MongoDB ObjectId as string |
| `slug` | `slug` | keyword | Story URL slug |
| `status` | `status` | keyword | Publication status |
| `title` | `title` | text | Story title (analyzed + keyword) |
| `summary` | `summary` | text | Story summary (analyzed) |
| `created_at` | `created_at` | date | Creation timestamp |
| `updated_at` | `updated_at` | date | Last update timestamp |
| ... | ... | ... | Additional fields as per schema |

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URI` | Required | MongoDB connection string |
| `MONGO_DB` | `namahStories` | Database name |
| `MONGO_COLLECTION` | `stories` | Collection name |
| `ES_URL` | Required | Elasticsearch URL |
| `ES_USER` | `elastic` | Elasticsearch username |
| `ES_PASS` | Required | Elasticsearch password |
| `ES_INDEX` | `stories_index` | Target index name |
| `SYNC_INTERVAL_MINUTES` | `10` | Sync frequency |
| `BATCH_SIZE` | `1000` | Documents per batch |
| `LOG_LEVEL` | `INFO` | Logging level |

### Sync Behavior

- **Full Sync**: Reindexes all active documents (status != "deleted")
- **Incremental Sync**: Only processes documents updated since last sync
- **Automatic Full Sync**: Runs daily at 2 AM or after 5+ consecutive errors
- **Error Handling**: Retries with exponential backoff, continues on partial failures

## 📈 Monitoring and Logging

### Log Files

- **Console**: Colored, human-readable format
- **File**: `logs/storysync.log` with rotation
- **Structured**: `logs/storysync_structured.json` for log aggregation

### Log Levels

- **DEBUG**: Detailed execution flow
- **INFO**: Normal operations, sync results
- **WARNING**: Recoverable issues
- **ERROR**: Failed operations, exceptions

### Metrics

The service logs structured metrics including:
- Documents processed/indexed/failed
- Sync duration and throughput
- Error rates and types
- Component health status

### Health Monitoring

Health checks verify:
- MongoDB connectivity and collection access
- Elasticsearch cluster status and index health
- Sync service state and recent errors

## 🧪 Testing

### Run Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=storysync --cov-report=html

# Run specific test file
pytest tests/test_sync_service.py -v
```

### Test Coverage

The test suite covers:
- Core sync logic and error scenarios
- MongoDB repository operations
- Elasticsearch adapter functionality
- Configuration validation
- Error handling and retries

## 🐳 Docker Deployment

### Build Docker Image

```bash
docker build -t storysync .
```

### Run Container

```bash
docker run -d \
  --name storysync \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/state:/app/state \
  storysync
```

### Docker Compose

```yaml
version: '3.8'
services:
  storysync:
    build: .
    env_file: .env
    volumes:
      - ./logs:/app/logs
      - ./state:/app/state
    restart: unless-stopped
```

## 🔍 Troubleshooting

### Common Issues

1. **Connection Failures**
   ```bash
   python -m storysync.main --health-check
   ```

2. **Permission Issues**
   - Ensure MongoDB user has read access to collection
   - Verify Elasticsearch user can create/write to index

3. **Memory Issues**
   - Reduce `BATCH_SIZE` for large documents
   - Monitor memory usage during full sync

4. **Performance Issues**
   - Check network latency between services
   - Monitor Elasticsearch cluster health
   - Review batch size and sync frequency

### Debug Mode

```bash
python -m storysync.main --log-level DEBUG --sync-now
```

### Log Analysis

```bash
# View recent logs
tail -f logs/storysync.log

# Search for errors
grep "ERROR" logs/storysync.log

# Analyze structured logs
jq '.sync_metrics' logs/storysync_structured.json
```

## 📚 API Reference

### Sync Service Methods

- `run_full_sync()`: Complete reindexing
- `run_incremental_sync()`: Delta updates only
- `run_sync_cycle()`: Automatic sync type selection
- `get_sync_status()`: Current sync state
- `health_check()`: Component health verification

### Repository Methods

- `fetch_all_documents()`: Retrieve all active documents
- `fetch_updated_documents()`: Get documents updated since timestamp
- `get_latest_update_time()`: Find most recent update
- `get_collection_stats()`: Collection metrics

### Adapter Methods

- `bulk_index_documents()`: Bulk Elasticsearch indexing
- `index_single_document()`: Single document indexing
- `get_index_stats()`: Index statistics
- `refresh_index()`: Force index refresh

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt

# Run code formatting
black storysync/

# Run linting
flake8 storysync/

# Run type checking
mypy storysync/
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review logs for detailed error information

## 📝 Changelog

### v1.0.0
- Initial release with full and incremental sync
- Enterprise architecture with clean separation
- Comprehensive error handling and logging
- Health monitoring and graceful shutdown
- Docker support and production deployment
