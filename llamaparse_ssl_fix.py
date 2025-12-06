#!/usr/bin/env python3
"""
LlamaParse SSL Fix Module
Provides SSL-friendly LlamaParse initialization
"""

import os
import ssl
import urllib3
import certifi
from typing import Optional

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure asyncio for nested event loops (needed for background threads)
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    print("⚠️ nest_asyncio not installed - some async operations may fail in background threads")

def configure_ssl_environment():
    """Configure environment variables for SSL certificates"""
    cert_path = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = cert_path
    os.environ['SSL_CERT_FILE'] = cert_path
    os.environ['CURL_CA_BUNDLE'] = cert_path
    
def get_llamaparse_parser(api_key: Optional[str] = None, **kwargs):
    """Get LlamaParse parser with SSL fix"""
    try:
        # Configure SSL environment
        configure_ssl_environment()
        
        from llama_parse import LlamaParse
        
        # Default parameters
        default_params = {
            'result_type': 'markdown',
            'verbose': True,
            'language': 'en',
            'ignore_errors': True
        }
        
        # Merge with user parameters
        params = {**default_params, **kwargs}
        
        # Use provided API key or get from environment
        if not api_key:
            api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        
        if not api_key:
            raise ValueError("LLAMA_CLOUD_API_KEY not found in environment")
        
        # Create parser
        parser = LlamaParse(api_key=api_key, **params)
        
        return parser
        
    except ImportError:
        raise ImportError("llama_parse module not available. Install with: pip install llama-parse")
    except Exception as e:
        print(f"⚠️ LlamaParse initialization error: {e}")
        raise

def parse_document_with_ssl_fix(file_path: str, api_key: Optional[str] = None, **kwargs):
    """Parse document with SSL fixes applied"""
    try:
        parser = get_llamaparse_parser(api_key=api_key, **kwargs)
        print(f"📊 Parsing {file_path} with LlamaParse (SSL fix applied)...")

        documents = parser.load_data(file_path)
        print(f"✅ Successfully parsed {len(documents)} document(s)")

        return documents

    except Exception as e:
        print(f"❌ LlamaParse failed: {e}")
        raise

def parse_document_with_metadata(file_path: str, api_key: Optional[str] = None, **kwargs):
    """Parse document with SSL fixes and return both documents and metadata (including page count)"""
    try:
        parser = get_llamaparse_parser(api_key=api_key, **kwargs)
        print(f"📊 Parsing {file_path} with LlamaParse (SSL fix applied)...")

        # Get JSON result which includes job_metadata with accurate page count
        json_result = parser.get_json_result(file_path)

        # Extract page count from job_metadata
        page_count = None
        if json_result and len(json_result) > 0:
            job_metadata = json_result[0].get("job_metadata", {})
            page_count = job_metadata.get("job_pages")
            is_cache_hit = job_metadata.get("job_is_cache_hit", False)

            # Also get page count from pages array as backup
            pages_array = json_result[0].get("pages", [])
            pages_from_array = len(pages_array)

            print(f"📄 Job metadata - job_pages: {page_count}, pages array: {pages_from_array}, cache hit: {is_cache_hit}")

            # Use pages array count if job_pages is 0 or None (can happen with cache hits)
            if (page_count is None or page_count == 0) and pages_from_array > 0:
                page_count = pages_from_array
                print(f"📄 Using pages array count as page_count: {page_count}")

        # Now get documents from the same result using load_data_from_json
        # or convert JSON pages to documents
        from llama_index.core import Document

        documents = []
        if json_result and len(json_result) > 0:
            pages = json_result[0].get("pages", [])
            for i, page in enumerate(pages):
                # Extract text from page (could be 'text' or 'md' field)
                text = page.get("md") or page.get("text", "")
                if text:
                    doc = Document(
                        text=text,
                        metadata={
                            "page_number": page.get("page", i + 1),
                            "source": file_path
                        }
                    )
                    documents.append(doc)

        print(f"✅ Successfully created {len(documents)} document(s) from {page_count or 'unknown'} pages")

        return {
            "documents": documents,
            "page_count": page_count,
            "document_count": len(documents)
        }

    except Exception as e:
        print(f"❌ LlamaParse failed: {e}")
        raise