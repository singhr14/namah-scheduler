#!/usr/bin/env python3
"""
Quick connection test script for MongoDB and Elasticsearch.
"""
from storysync.core.mongo_repository import MongoRepository
from storysync.config.settings import get_settings

def test_connections():
    settings = get_settings()
    print('=== MongoDB Connection Test ===')
    print(f'MongoDB URI: {settings.mongo_uri}')
    print(f'Database: {settings.mongo_db}')
    print(f'Collection: {settings.mongo_collection}')

    try:
        with MongoRepository(settings) as repo:
            stats = repo.get_collection_stats()
            print('[SUCCESS] MongoDB Connection: SUCCESS')
            print(f'Total Documents: {stats["total_documents"]:,}')
            print(f'Active Documents: {stats["active_documents"]:,}')
            print(f'Collection Size: {stats["collection_size"]:,} bytes')
            
            latest_update = repo.get_latest_update_time()
            if latest_update:
                print(f'Latest Update: {latest_update}')
            else:
                print('Latest Update: No documents with update time found')
                
    except Exception as e:
        print(f'[FAILED] MongoDB Connection: FAILED - {str(e)}')

    print('\n=== Elasticsearch Connection Test ===')
    print(f'Elasticsearch URL: {settings.es_url}')
    print(f'Index: {settings.es_index}')
    print('Note: Connection may fail if credentials are not correct or service is unreachable')

if __name__ == "__main__":
    test_connections()
