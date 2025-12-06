# NodeRAG API Token Usage Requirements

## Summary of Changes Made to v3/chat

✅ **COMPLETED - Backend Changes:**
- Modified `v3/chat` endpoint to extract and return `token_usage` in response
- For `ragversion=v1`: Extracts tokens from local `llm_integration.py`
- For `ragversion=v2`: Extracts tokens from NodeRAG API response

---

## For ragversion=v1 (Local RAG)

**Location:** `app.py:11161-11167`

The backend now extracts token usage from the local LLM integration:

```python
# Extract token usage from LLM result (v1 mode)
usage = llm_result.get("usage", {})
input_tokens = usage.get("prompt_tokens", 0)
output_tokens = usage.get("completion_tokens", 0)
total_tokens = usage.get("total_tokens", 0)
```

**Response format for v1:**
```json
{
  "query": "What is your return policy?",
  "orgId": "org_123",
  "answer": "Our return policy allows...",
  "sources": [...],
  "token_usage": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "total_tokens": 1801
  },
  "llm_metadata": {...},
  "pipeline": "complete_rag"
}
```

---

## For ragversion=v2 (NodeRAG)

**Location:** `app.py:11003-11021`

The backend expects token usage from the NodeRAG API response.

### What NodeRAG API Must Return

The NodeRAG service endpoint `/api/v1/generate-response` **MUST** include a `usage` object in its JSON response with the following structure:

```json
{
  "response": "Generated answer text here...",
  "sources": ["file_id_1", "file_id_2"],
  "algorithm_used": "NodeRAG Advanced Search",
  "confidence": 0.85,
  "usage": {
    "prompt_tokens": 1234,
    "output_tokens": 567,
    "total_tokens": 1801
  },
  "metadata": {...}
}
```

### CURL Example: What to Expect from NodeRAG

**Request to NodeRAG:**
```bash
curl -X POST http://localhost:5001/api/v1/generate-response \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": "org_123",
    "query": "What is your return policy?",
    "conversation_history": "",
    "max_tokens": 2048,
    "temperature": 0.7
  }'
```

**Expected Response from NodeRAG (must include `usage`):**
```json
{
  "response": "Based on our company policies, our return policy states that customers can return items within 30 days of purchase...",
  "sources": [
    "file_abc123",
    "file_def456"
  ],
  "algorithm_used": "NodeRAG Advanced Search",
  "confidence": 0.92,
  "node_types": {
    "document": 3,
    "chunk": 5
  },
  "context_used": 1500,
  "search_results": 5,
  "usage": {
    "prompt_tokens": 1234,
    "completion_tokens": 567,
    "total_tokens": 1801
  },
  "search_components": {
    "semantic_search": true,
    "keyword_search": true,
    "reranking": true
  },
  "retrieval_metadata": {
    "chunks_retrieved": 5,
    "avg_similarity": 0.87
  }
}
```

### Critical Field Required

```json
"usage": {
  "prompt_tokens": <integer>,      // REQUIRED: Input tokens sent to LLM
  "completion_tokens": <integer>,  // REQUIRED: Output tokens from LLM
  "total_tokens": <integer>        // REQUIRED: Sum of input + output
}
```

---

## Response Format from v3/chat (ragversion=v2)

After the backend receives the NodeRAG response, it formats it like this:

```json
{
  "response": "Based on our company policies...",
  "query": "What is your return policy?",
  "orgId": "org_123",
  "source": "noderag_v2",
  "token_usage": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "total_tokens": 1801
  },
  "metadata": {
    "rag_version": "v2",
    "processing_type": "noderag",
    "algorithm_used": "NodeRAG Advanced Search",
    "confidence": 0.92,
    "sources": ["file_abc123", "file_def456"],
    "node_types": {...},
    "context_used": 1500,
    "search_results": 5,
    "search_components": {...},
    "retrieval_metadata": {...}
  }
}
```

---

## How NodeRAG Should Capture Token Usage

In your NodeRAG service code, when you call the LLM (e.g., OpenAI), the API response includes token usage:

### Example: OpenAI API Response
```python
import openai

response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[...],
    max_tokens=2048
)

# Extract usage from OpenAI response
usage = {
    "prompt_tokens": response.usage.prompt_tokens,
    "completion_tokens": response.usage.completion_tokens,
    "total_tokens": response.usage.total_tokens
}

# Include in your NodeRAG API response
return {
    "response": response.choices[0].message.content,
    "sources": [...],
    "usage": usage,  # <-- INCLUDE THIS
    ...
}
```

---

## Testing the Integration

### Test v1 (Local RAG):
```bash
curl -X POST http://localhost:8002/api/v3/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is your return policy?",
    "orgId": "org_123",
    "ragversion": "v1"
  }'
```

**Expected response includes:**
```json
{
  "answer": "...",
  "token_usage": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "total_tokens": 1801
  }
}
```

### Test v2 (NodeRAG):
```bash
curl -X POST http://localhost:8002/api/v3/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is your return policy?",
    "orgId": "org_123",
    "ragversion": "v2"
  }'
```

**Expected response includes:**
```json
{
  "response": "...",
  "token_usage": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "total_tokens": 1801
  }
}
```

---

## Action Items for NodeRAG Service

1. ✅ Modify `/api/v1/generate-response` endpoint to capture token usage from LLM calls
2. ✅ Include `usage` object in the JSON response with `prompt_tokens`, `completion_tokens`, and `total_tokens`
3. ✅ Test the endpoint to ensure token counts are accurate
4. ✅ Deploy the updated NodeRAG service

---

## Summary

- **v3/chat with ragversion=v1**: ✅ Already working - tokens come from `llm_integration.py`
- **v3/chat with ragversion=v2**: ⚠️ Requires NodeRAG API to return `usage` object
- **Response format**: Both versions now include `token_usage` in the response

The backend changes are **COMPLETE**. You now need to update the **NodeRAG service** to include the `usage` object in its API responses.
