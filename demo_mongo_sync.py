#!/usr/bin/env python3
"""
Demo script showing MongoDB sync functionality without Elasticsearch.
This demonstrates that the core sync logic works perfectly.
"""
from storysync.core.mongo_repository import MongoRepository
from storysync.config.settings import get_settings
from storysync.models.story_model import StoryDocument
import time

def demo_mongodb_sync():
    """Demonstrate MongoDB data fetching and processing."""
    settings = get_settings()
    
    print("=== StorySync Demo - Story Content Synchronization ===")
    print(f"MongoDB: {settings.mongo_db}.{settings.mongo_collection}")
    print(f"Target Index: {settings.es_index}")
    print("-" * 50)
    
    try:
        with MongoRepository(settings) as repo:
            # Get collection statistics
            stats = repo.get_collection_stats()
            print(f"📊 Collection Stats:")
            print(f"   Total Documents: {stats['total_documents']:,}")
            print(f"   Active Documents: {stats['active_documents']:,}")
            print(f"   Collection Size: {stats['collection_size']:,} bytes")
            
            # Get latest update time
            latest_update = repo.get_latest_update_time()
            if latest_update:
                print(f"   Latest Update: {latest_update}")
            
            print("\n🔄 Fetching documents for sync...")
            
            # Simulate full sync
            total_docs = 0
            processed_docs = []
            
            for batch_num, batch in enumerate(repo.fetch_all_documents(batch_size=5), 1):
                print(f"\n📦 Batch {batch_num}: {len(batch)} documents")
                
                for doc in batch:
                    total_docs += 1
                    processed_docs.append(doc)
                    
                    # Show document details
                    print(f"   {total_docs}. {doc.title or 'Untitled'}")
                    print(f"      ID: {doc.mongo_id}")
                    print(f"      Status: {doc.status or 'N/A'}")
                    print(f"      Updated: {doc.updated_at or 'N/A'}")
                    
                    # Convert to Elasticsearch format
                    es_doc = doc.to_elasticsearch_doc()
                    print(f"      ES Fields: {len(es_doc)} fields ready for indexing")
                
                # Simulate processing time
                time.sleep(0.5)
            
            print(f"\n✅ Sync Simulation Complete!")
            print(f"   Documents Processed: {total_docs}")
            print(f"   Ready for Elasticsearch: {len(processed_docs)}")
            
            # Show what would be indexed
            if processed_docs:
                sample_doc = processed_docs[0].to_elasticsearch_doc()
                print(f"\n📄 Sample Elasticsearch Document:")
                for key, value in list(sample_doc.items())[:8]:  # Show first 8 fields
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:47] + "..."
                    print(f"   {key}: {value}")
                if len(sample_doc) > 8:
                    print(f"   ... and {len(sample_doc) - 8} more fields")
            
            print(f"\n🎯 Next Steps:")
            print(f"   1. Fix Elasticsearch connectivity")
            print(f"   2. Run: python -m storysync.main --sync-now")
            print(f"   3. Start scheduled service: python -m storysync.main")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    demo_mongodb_sync()
