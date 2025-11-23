"""
Configuration management using Pydantic for environment variable loading and validation.
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # MongoDB Configuration
    mongo_uri: str = Field(
        default="mongodb://storyUser:Open%241234@13.127.252.2:27017/?authSource=namahStories",
        description="MongoDB connection URI"
    )
    mongo_db: str = Field(default="namahStories", description="MongoDB database name")
    mongo_collection: str = Field(default="stories", description="MongoDB collection name")
    
    # Elasticsearch Configuration
    es_url: str = Field(
        default="https://search-dev.aumnamah.com/",
        description="Elasticsearch URL"
    )
    es_user: str = Field(default="elastic", description="Elasticsearch username")
    es_pass: str = Field(default="XDdKobotxL6cm_bBTtAA", description="Elasticsearch password")
    es_index: str = Field(default="stories_index", description="Elasticsearch index name")
    es_timeout: int = Field(default=30, description="Elasticsearch timeout in seconds")
    
    # Sync Configuration
    sync_interval_minutes: int = Field(
        default=10, 
        description="Sync interval in minutes"
    )
    batch_size: int = Field(
        default=1000, 
        description="Batch size for bulk operations"
    )
    max_retries: int = Field(default=3, description="Maximum number of retries")
    retry_delay: int = Field(default=5, description="Retry delay in seconds")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: str = Field(
        default="logs/storysync.log", 
        description="Log file path"
    )
    log_rotation: str = Field(
        default="1 day", 
        description="Log rotation interval"
    )
    log_retention: str = Field(
        default="30 days", 
        description="Log retention period"
    )
    
    # State Management
    state_file: str = Field(
        default="state/last_sync.json", 
        description="State file for tracking last sync time"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance."""
    return settings
