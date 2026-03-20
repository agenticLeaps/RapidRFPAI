"""
NodeRAG Client - HTTP client for Rapidrfpv2 RAG service.
Provides a clean interface for RapidRFPAI to query the NodeRAG knowledge base.
"""
import os
import requests
from typing import Dict, Any, Optional, List


class NodeRAGClient:
    """
    HTTP client for Rapidrfpv2 NodeRAG service.
    Replaces direct module import with HTTP API calls.
    """

    def __init__(self, base_url: str = None, timeout: int = 30):
        """
        Initialize the NodeRAG client.

        Args:
            base_url: Base URL of the Rapidrfpv2 service.
                      Defaults to NODERAG_SERVICE_URL env var or http://localhost:5001
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv("NODERAG_SERVICE_URL", "http://localhost:5001")
        self.timeout = timeout
        self._verify_connection()

    def _verify_connection(self):
        """Verify connection to Rapidrfpv2 service."""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=5
            )
            if response.status_code == 200:
                print(f"[NodeRAGClient] Connected to Rapidrfpv2 at {self.base_url}")
            else:
                print(f"[NodeRAGClient] Warning: Rapidrfpv2 health check returned {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"[NodeRAGClient] Warning: Could not connect to Rapidrfpv2: {e}")

    def generate_response(
        self,
        query: str,
        session_id: str = None,
        org_id: str = None,
        top_k: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a response using RAG from the NodeRAG knowledge base.

        Args:
            query: The question/query to search for
            session_id: Session/org ID for the knowledge base (alias: org_id)
            org_id: Organization ID (alias for session_id)
            top_k: Number of top results to retrieve
            **kwargs: Additional parameters

        Returns:
            Dict with response, sources, and confidence
        """
        # Support both session_id and org_id
        effective_session_id = session_id or org_id or "default"

        try:
            payload = {
                "query": query,
                "session_id": effective_session_id,
                "top_k": top_k,
                **kwargs
            }

            response = requests.post(
                f"{self.base_url}/api/v1/generate-response",
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "response": data.get("response", ""),
                    "sources": data.get("sources", []),
                    "confidence": data.get("confidence", 0.0),
                    "context_used": data.get("context_used", False)
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "response": "",
                    "sources": [],
                    "confidence": 0.0
                }

        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timed out",
                "response": "",
                "sources": [],
                "confidence": 0.0
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "response": "",
                "sources": [],
                "confidence": 0.0
            }

    def search(
        self,
        query: str,
        session_id: str = "default",
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Search the knowledge base without generating a response.

        Args:
            query: The search query
            session_id: Session/org ID
            top_k: Number of results

        Returns:
            Dict with search results
        """
        try:
            payload = {
                "query": query,
                "session_id": session_id,
                "top_k": top_k
            }

            response = requests.post(
                f"{self.base_url}/api/v1/search",
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "results": response.json().get("results", [])
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned status {response.status_code}",
                    "results": []
                }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "results": []
            }

    def verify_eligibility(
        self,
        requirement_text: str,
        session_id: str,
        confidence_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Verify an eligibility requirement against the knowledge base.

        Args:
            requirement_text: The requirement to verify
            session_id: Organization/session ID
            confidence_threshold: Minimum confidence for auto-verification

        Returns:
            Dict with verification result
        """
        # Use generate_response with a verification-focused query
        query = f"Does the company meet this requirement: {requirement_text}"

        result = self.generate_response(
            query=query,
            session_id=session_id,
            top_k=5
        )

        if not result.get("success"):
            return {
                "verified": False,
                "confidence": 0.0,
                "sources": [],
                "explanation": result.get("error", "Verification failed")
            }

        confidence = result.get("confidence", 0.0)
        sources = result.get("sources", [])

        return {
            "verified": confidence >= confidence_threshold,
            "confidence": confidence,
            "sources": sources,
            "explanation": result.get("response", ""),
            "rag_hint": sources[0].get("text", "") if sources else None
        }


# Convenience function for quick verification
def verify_requirement(requirement: str, org_id: str) -> Dict[str, Any]:
    """
    Quick helper to verify a requirement.

    Args:
        requirement: The requirement text
        org_id: Organization ID

    Returns:
        Verification result
    """
    client = NodeRAGClient()
    return client.verify_eligibility(requirement, org_id)
