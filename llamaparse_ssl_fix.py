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