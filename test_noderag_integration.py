#!/usr/bin/env python3
"""
Test script for NodeRAG integration
Tests the complete flow from document upload to search
"""

import requests
import time
import json
import os

# Configuration
MAIN_SERVER_URL = "http://localhost:5000"
NODERAG_SERVICE_URL = "http://localhost:5001"

def test_health_checks():
    """Test health endpoints"""
    print("🩺 Testing health checks...")
    
    # Test NodeRAG service health
    try:
        response = requests.get(f"{NODERAG_SERVICE_URL}/api/v1/health", timeout=5)
        if response.status_code == 200:
            print("✅ NodeRAG service is healthy")
        else:
            print(f"❌ NodeRAG service unhealthy: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ NodeRAG service unreachable: {e}")
        return False
    
    print("✅ All health checks passed")
    return True

def test_document_upload_v1():
    """Test v1 (naive RAG) document upload"""
    print("📄 Testing v1 document upload...")
    
    # Create a test text file
    test_content = """
    This is a test document for the RapidRFP AI system.
    It contains information about artificial intelligence and machine learning.
    The document discusses various aspects of natural language processing.
    NodeRAG is an advanced graph-based retrieval augmented generation system.
    """
    
    test_file_path = "/tmp/test_document_v1.txt"
    with open(test_file_path, "w") as f:
        f.write(test_content)
    
    try:
        with open(test_file_path, "rb") as f:
            files = {"file": f}
            data = {
                "orgId": "test_org_123",
                "fileId": "test_file_v1_456", 
                "userId": "test_user_789",
                "ragversion": "v1"
            }
            
            response = requests.post(
                f"{MAIN_SERVER_URL}/api/v3/upload",
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 202:
                result = response.json()
                print(f"✅ V1 upload successful: {result['message']}")
                print(f"   Processing method: {result['processing_method']}")
                return True
            else:
                print(f"❌ V1 upload failed: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ V1 upload error: {e}")
        return False
    finally:
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

def test_document_upload_v2():
    """Test v2 (NodeRAG) document upload"""
    print("📄 Testing v2 document upload...")
    
    # Create a test text file
    test_content = """
    NodeRAG Advanced Graph Processing System
    
    NodeRAG is a sophisticated retrieval augmented generation system that uses graph-based 
    knowledge representation. The system processes documents through multiple phases:
    
    Phase 1: Graph Decomposition
    - Extract text nodes (T) from document chunks
    - Identify semantic units (S) within the text
    - Extract named entities (N) with deduplication
    - Discover relationships (R) between entities
    
    Phase 2: Graph Augmentation  
    - Generate attribute nodes (A) for important entities
    - Create high-level summary nodes (H) for communities
    - Produce overview nodes (O) with descriptive titles
    
    Phase 3: Embedding Generation
    - Generate embeddings for all node types
    - Store embeddings in vector database
    - Enable similarity-based retrieval
    
    Key Benefits:
    - Enhanced semantic understanding
    - Improved relationship discovery
    - Better context preservation
    - Multi-modal knowledge representation
    """
    
    test_file_path = "/tmp/test_document_v2.txt"
    with open(test_file_path, "w") as f:
        f.write(test_content)
    
    try:
        with open(test_file_path, "rb") as f:
            files = {"file": f}
            data = {
                "orgId": "test_org_123",
                "fileId": "test_file_v2_456",
                "userId": "test_user_789", 
                "ragversion": "v2"
            }
            
            response = requests.post(
                f"{MAIN_SERVER_URL}/api/v3/upload",
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 202:
                result = response.json()
                print(f"✅ V2 upload successful: {result['message']}")
                print(f"   Processing method: {result['processing_method']}")
                return True
            else:
                print(f"❌ V2 upload failed: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ V2 upload error: {e}")
        return False
    finally:
        if os.path.exists(test_file_path):
            os.unlink(test_file_path)

def wait_for_processing():
    """Wait for processing to complete"""
    print("⏳ Waiting for processing to complete...")
    time.sleep(30)  # Give time for processing
    print("✅ Processing wait complete")

def test_unified_search():
    """Test unified search across v1 and v2 data"""
    print("🔍 Testing unified search...")
    
    search_queries = [
        "artificial intelligence",
        "NodeRAG system", 
        "graph processing",
        "embedding generation"
    ]
    
    for query in search_queries:
        print(f"\n🔍 Testing query: '{query}'")
        
        # Test search with both versions
        search_data = {
            "query": query,
            "orgId": "test_org_123",
            "top_k": 5,
            "ragversion": "both"
        }
        
        try:
            response = requests.post(
                f"{MAIN_SERVER_URL}/api/v3/search",
                json=search_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Search successful:")
                print(f"   Total results: {result['total_results']}")
                print(f"   V1 results: {result['sources'].get('v1', {}).get('count', 0)}")
                print(f"   V2 results: {result['sources'].get('v2', {}).get('count', 0)}")
                
                # Show top results
                for i, res in enumerate(result['combined_results'][:2]):
                    source = res.get('source_type', 'unknown')
                    score = res.get('score', res.get('similarity_score', 'N/A'))
                    content = res.get('content', res.get('text', ''))[:100]
                    print(f"   Result {i+1} ({source}): {content}... (score: {score})")
                    
            else:
                print(f"❌ Search failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Search error: {e}")

def test_noderag_direct_search():
    """Test direct NodeRAG service search"""
    print("🔍 Testing direct NodeRAG search...")
    
    search_data = {
        "org_id": "test_org_123",
        "query": "graph processing phases",
        "top_k": 3
    }
    
    try:
        response = requests.post(
            f"{NODERAG_SERVICE_URL}/api/v1/search",
            json=search_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Direct NodeRAG search successful:")
            print(f"   Results found: {result['count']}")
            
            for i, res in enumerate(result['results'][:2]):
                node_type = res.get('node_type', 'unknown')
                score = res.get('similarity_score', 'N/A')
                content = res.get('content', '')[:80]
                print(f"   Result {i+1} ({node_type}): {content}... (score: {score})")
                
        else:
            print(f"❌ Direct search failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Direct search error: {e}")

def main():
    """Run all tests"""
    print("🚀 Starting NodeRAG Integration Tests")
    print("=" * 50)
    
    # Test 1: Health checks
    if not test_health_checks():
        print("❌ Health checks failed. Ensure both services are running.")
        return
    
    # Test 2: Document uploads
    print("\n" + "=" * 50)
    v1_success = test_document_upload_v1()
    
    print("\n" + "=" * 50) 
    v2_success = test_document_upload_v2()
    
    if not (v1_success or v2_success):
        print("❌ Both upload tests failed")
        return
    
    # Test 3: Wait for processing
    print("\n" + "=" * 50)
    wait_for_processing()
    
    # Test 4: Search tests
    print("\n" + "=" * 50)
    test_unified_search()
    
    print("\n" + "=" * 50)
    test_noderag_direct_search()
    
    print("\n" + "=" * 50)
    print("🎉 NodeRAG Integration Tests Complete!")
    print("Check the logs for detailed processing information.")

if __name__ == "__main__":
    main()