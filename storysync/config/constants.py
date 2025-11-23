"""
Application constants and fixed values.
"""
from typing import Dict, Any

# Field mappings for MongoDB to Elasticsearch transformation
FIELD_MAPPINGS = {
    "_id": "mongo_id",
    "slug": "slug",
    "status": "status",
    "audiences": "audiences",
    "tags": "tags",
    "themes": "themes",
    "deities": "deities",
    "badges": "badges",
    "title": "title",
    "summary": "summary",
    "estimated_readtime_seconds": "estimated_readtime_seconds",
    "cover_image_key": "cover_image_key",
    "authors": "authors",
    "sources": "sources",
    "language": "language",
    "available_languages": "available_languages",
    "story_type": "story_type",
    "chapter_ids": "chapter_ids",
    "created_at": "created_at",
    "updated_at": "updated_at"
}

# Elasticsearch index mapping
ES_INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
        "refresh_interval": "1s",
        "analysis": {
            "analyzer": {
                "autocomplete_analyzer": {
                    "tokenizer": "autocomplete_tokenizer",
                    "filter": ["lowercase"]
                },
                "autocomplete_search_analyzer": {
                    "tokenizer": "lowercase"
                }
            },
            "tokenizer": {
                "autocomplete_tokenizer": {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 20,
                    "token_chars": ["letter", "digit"]
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "mongo_id": {"type": "keyword"},
            "slug": {"type": "keyword"},
            "status": {"type": "keyword"},
            "audiences": {"type": "keyword"},
            "tags": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "as_you_type": {"type": "search_as_you_type"}
                }
            },
            "themes": {"type": "keyword"},
            "deities": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "as_you_type": {"type": "search_as_you_type"}
                }
            },
            "badges": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "as_you_type": {"type": "search_as_you_type"}
                }
            },
            "summary": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "as_you_type": {"type": "search_as_you_type"}
                }
            },
            "estimated_readtime_seconds": {"type": "integer"},
            "cover_image_key": {"type": "keyword"},
            "authors": {"type": "keyword"},
            "sources": {"type": "keyword"},
            "language": {"type": "keyword"},
            "available_languages": {"type": "keyword"},
            "story_type": {"type": "keyword"},
            "chapter_ids": {"type": "keyword"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"}
        }
    }
}

# MongoDB query filters
MONGO_ACTIVE_FILTER = {"status": {"$ne": "deleted"}}

# Date format for ISO timestamps
ISO_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

# Retry configuration
RETRY_STOP_AFTER_ATTEMPT = 3
RETRY_WAIT_EXPONENTIAL_MULTIPLIER = 1
RETRY_WAIT_EXPONENTIAL_MAX = 10

# Logging format
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"

# Signal handling
SHUTDOWN_SIGNALS = ["SIGTERM", "SIGINT"]
