#!/usr/bin/env python3
"""
Script to check Elasticsearch index details and search documents.
"""
import os
from elasticsearch import Elasticsearch

def check_elasticsearch_details():
    """Check Elasticsearch index details and documents."""
    
    # Set credentials
    url = os.environ.get('ES_URL', 'https://your-elasticsearch-url.com/')
    username = os.environ.get('ES_USER', 'elastic')
    password = os.environ.get('ES_PASS')
    index_name = "stories_index"
    
    print("=== Elasticsearch Index Details ===")
    print(f"URL: {url}")
    print(f"Index: {index_name}")
    print("-" * 50)
    
    try:
        # Connect to Elasticsearch
        client = Elasticsearch(
            hosts=[url],
            basic_auth=(username, password),
            verify_certs=False,
            ssl_show_warn=False,
            ssl_assert_hostname=False,
            ssl_assert_fingerprint=None,
            request_timeout=10
        )
        
        # 1. Check cluster health
        print("\n1. CLUSTER HEALTH:")
        health = client.cluster.health()
        print(f"   Status: {health['status']}")
        print(f"   Cluster Name: {health['cluster_name']}")
        print(f"   Number of Nodes: {health['number_of_nodes']}")
        
        # 2. Check if index exists
        print(f"\n2. INDEX STATUS:")
        exists = client.indices.exists(index=index_name)
        print(f"   Index '{index_name}' exists: {exists}")
        
        if not exists:
            print("   [INFO] Index doesn't exist. Run sync first!")
            return
        
        # 3. Get index stats
        print(f"\n3. INDEX STATISTICS:")
        stats = client.indices.stats(index=index_name)
        index_stats = stats['indices'][index_name]['total']
        
        doc_count = index_stats['docs']['count']
        deleted_count = index_stats['docs']['deleted']
        store_size = index_stats['store']['size_in_bytes']
        
        print(f"   Total Documents: {doc_count:,}")
        print(f"   Deleted Documents: {deleted_count:,}")
        print(f"   Store Size: {store_size:,} bytes ({store_size/1024:.2f} KB)")
        
        # 4. Get index mapping
        print(f"\n4. INDEX MAPPING:")
        mapping = client.indices.get_mapping(index=index_name)
        properties = mapping[index_name]['mappings']['properties']
        print(f"   Fields in index: {len(properties)}")
        for field_name, field_config in list(properties.items())[:10]:  # Show first 10 fields
            field_type = field_config.get('type', 'unknown')
            print(f"   - {field_name}: {field_type}")
        if len(properties) > 10:
            print(f"   ... and {len(properties) - 10} more fields")
        
        # 5. Search for documents
        print(f"\n5. SAMPLE DOCUMENTS:")
        if doc_count > 0:
            # Get all documents
            search_result = client.search(
                index=index_name,
                body={
                    "query": {"match_all": {}},
                    "size": 5,  # Get first 5 documents
                    "sort": [{"updated_at": {"order": "desc"}}]
                }
            )
            
            hits = search_result['hits']['hits']
            print(f"   Showing {len(hits)} of {doc_count} documents:")
            
            for i, hit in enumerate(hits, 1):
                source = hit['_source']
                print(f"\n   Document {i}:")
                print(f"     ID: {hit['_id']}")
                print(f"     Title: {source.get('title', 'N/A')}")
                print(f"     Status: {source.get('status', 'N/A')}")
                print(f"     Updated: {source.get('updated_at', 'N/A')}")
                print(f"     Fields: {len(source)} total fields")
        else:
            print("   No documents found in index")
        
        # 6. Search by specific criteria
        print(f"\n6. SEARCH EXAMPLES:")
        
        # Search for published stories
        published_search = client.search(
            index=index_name,
            body={
                "query": {"term": {"status": "published"}},
                "size": 0  # Just get count
            }
        )
        published_count = published_search['hits']['total']['value']
        print(f"   Published stories: {published_count}")
        
        # Search by title (if any documents exist)
        if doc_count > 0:
            title_search = client.search(
                index=index_name,
                body={
                    "query": {"exists": {"field": "title"}},
                    "size": 0
                }
            )
            title_count = title_search['hits']['total']['value']
            print(f"   Stories with titles: {title_count}")
        
        print(f"\n[SUCCESS] Elasticsearch check completed!")
        print(f"Summary: {doc_count} documents in '{index_name}' index")
        
    except Exception as e:
        print(f"[ERROR] Failed to check Elasticsearch: {str(e)}")

if __name__ == "__main__":
    check_elasticsearch_details()
