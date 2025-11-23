#!/usr/bin/env python3
"""
Direct Elasticsearch connection test with detailed error reporting.
"""
import os
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, AuthenticationException, RequestError

def test_elasticsearch_connection():
    """Test Elasticsearch connection with various configurations."""
    
    # Get credentials from environment variables
    url = os.environ.get('ES_URL', 'https://your-elasticsearch-url.com/')
    username = os.environ.get('ES_USER', 'elastic')
    password = os.environ.get('ES_PASS')
    
    print("=== Elasticsearch Connection Test ===")
    print(f"URL: {url}")
    print(f"Username: {username}")
    print(f"Password: {password[:5]}***{password[-3:]}")
    print("-" * 40)
    
    # Test 1: Basic connection with SSL verification disabled
    print("\n[TEST 1] Basic connection (SSL verification disabled)")
    try:
        client = Elasticsearch(
            hosts=[url],
            basic_auth=(username, password),
            verify_certs=False,
            ssl_show_warn=False,
            ssl_assert_hostname=False,
            ssl_assert_fingerprint=None,
            request_timeout=10
        )
        
        # Test ping
        if client.ping():
            print("[SUCCESS] Ping successful!")
            
            # Get cluster info
            info = client.info()
            print(f"[SUCCESS] Cluster: {info.get('cluster_name', 'Unknown')}")
            print(f"[SUCCESS] Version: {info.get('version', {}).get('number', 'Unknown')}")
            
            # Test index operations
            index_name = "stories_index"
            try:
                # Check if index exists
                exists = client.indices.exists(index=index_name)
                print(f"[SUCCESS] Index '{index_name}' exists: {exists}")
                
                if not exists:
                    print(f"[INFO] Creating index '{index_name}'...")
                    client.indices.create(index=index_name, ignore=400)
                    print(f"[SUCCESS] Index '{index_name}' created successfully!")
                
                # Get index stats
                stats = client.indices.stats(index=index_name)
                doc_count = stats['indices'][index_name]['total']['docs']['count']
                print(f"[SUCCESS] Documents in index: {doc_count}")
                
                print("\n[SUCCESS] Elasticsearch connection is working perfectly!")
                return True
                
            except Exception as e:
                print(f"[WARNING] Index operations failed: {str(e)}")
                return False
                
        else:
            print("[FAILED] Ping failed")
            return False
            
    except AuthenticationException as e:
        print(f"[FAILED] Authentication failed: {str(e)}")
        print("   Check username and password")
        return False
        
    except ConnectionError as e:
        print(f"[FAILED] Connection failed: {str(e)}")
        print("   Possible causes:")
        print("   - Network connectivity issues")
        print("   - Elasticsearch service is down")
        print("   - Firewall blocking the connection")
        print("   - Incorrect URL")
        return False
        
    except RequestError as e:
        print(f"[FAILED] Request error: {str(e)}")
        return False
        
    except Exception as e:
        print(f"[FAILED] Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_elasticsearch_connection()
    if success:
        print("\n[READY] Ready to run the sync service!")
        print("   Run: python -m storysync.main --sync-now")
    else:
        print("\n[INFO] Please check Elasticsearch configuration and try again.")
