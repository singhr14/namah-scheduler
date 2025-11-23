"""
Pydantic models for story documents and data validation.
"""
from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field, validator
from bson import ObjectId


class StoryDocument(BaseModel):
    """Pydantic model representing a story document from MongoDB."""
    
    mongo_id: str = Field(..., description="MongoDB ObjectId as string")
    slug: Optional[str] = Field(None, description="Story slug")
    status: Optional[str] = Field(None, description="Story status")
    audiences: Optional[List[str]] = Field(default_factory=list, description="Target audiences")
    tags: Optional[List[str]] = Field(default_factory=list, description="Story tags")
    themes: Optional[List[str]] = Field(default_factory=list, description="Story themes")
    deities: Optional[List[str]] = Field(default_factory=list, description="Associated deities")
    badges: Optional[List[str]] = Field(default_factory=list, description="Story badges")
    title: Optional[str] = Field(None, description="Story title")
    summary: Optional[str] = Field(None, description="Story summary")
    estimated_readtime_seconds: Optional[int] = Field(None, description="Estimated read time in seconds")
    cover_image_key: Optional[str] = Field(None, description="Cover image key")
    authors: Optional[List[str]] = Field(default_factory=list, description="Story authors")
    sources: Optional[List[str]] = Field(default_factory=list, description="Story sources")
    language: Optional[str] = Field(None, description="Primary language")
    available_languages: Optional[List[str]] = Field(default_factory=list, description="Available languages")
    story_type: Optional[str] = Field(None, description="Type of story")
    chapter_ids: Optional[List[str]] = Field(default_factory=list, description="Associated chapter IDs")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            ObjectId: str
        }
        populate_by_name = True
        arbitrary_types_allowed = True
    
    @validator('mongo_id', pre=True)
    def validate_mongo_id(cls, v):
        """Convert ObjectId to string if necessary."""
        if isinstance(v, ObjectId):
            return str(v)
        return v
    
    @validator('created_at', 'updated_at', pre=True)
    def validate_datetime(cls, v):
        """Validate and convert datetime fields."""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                return None
        return v
    
    def to_elasticsearch_doc(self) -> Dict[str, Any]:
        """Convert to Elasticsearch document format."""
        doc = self.dict(exclude_none=True)
        
        # Convert datetime objects to ISO format strings
        for field in ['created_at', 'updated_at']:
            if field in doc and doc[field]:
                if isinstance(doc[field], datetime):
                    doc[field] = doc[field].isoformat()
        
        return doc
    
    @classmethod
    def from_mongo_doc(cls, mongo_doc: Dict[str, Any]) -> 'StoryDocument':
        """Create StoryDocument from MongoDB document."""
        # Convert MongoDB _id to mongo_id
        if '_id' in mongo_doc:
            mongo_doc['mongo_id'] = str(mongo_doc['_id'])
            del mongo_doc['_id']
        
        # Handle missing fields with defaults
        for field in ['audiences', 'tags', 'themes', 'deities', 'badges', 'authors', 'sources', 'available_languages', 'chapter_ids']:
            if field not in mongo_doc or mongo_doc[field] is None:
                mongo_doc[field] = []
        
        return cls(**mongo_doc)


class SyncState(BaseModel):
    """Model for tracking sync state."""
    
    last_sync_time: Optional[datetime] = Field(None, description="Last successful sync timestamp")
    last_full_sync: Optional[datetime] = Field(None, description="Last full sync timestamp")
    total_documents_synced: int = Field(default=0, description="Total documents synced")
    last_sync_duration: Optional[float] = Field(None, description="Last sync duration in seconds")
    sync_errors: List[str] = Field(default_factory=list, description="Recent sync errors")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.dict()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SyncState':
        """Create SyncState from dictionary."""
        # Convert ISO strings back to datetime objects
        for field in ['last_sync_time', 'last_full_sync']:
            if field in data and data[field]:
                if isinstance(data[field], str):
                    try:
                        data[field] = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
                    except ValueError:
                        data[field] = None
        
        return cls(**data)


class SyncResult(BaseModel):
    """Model for sync operation results."""
    
    success: bool = Field(..., description="Whether sync was successful")
    documents_processed: int = Field(default=0, description="Number of documents processed")
    documents_indexed: int = Field(default=0, description="Number of documents indexed")
    documents_failed: int = Field(default=0, description="Number of documents that failed")
    duration: float = Field(default=0.0, description="Sync duration in seconds")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered")
    start_time: datetime = Field(default_factory=datetime.utcnow, description="Sync start time")
    end_time: Optional[datetime] = Field(None, description="Sync end time")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
