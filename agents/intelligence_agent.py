"""
Intelligence Agent - Pass 2 (Background)
Runs the Intelligence Layer for Go/No-Go assessment, risk identification,
and competitive positioning analysis.

This agent:
1. Extracts eligibility requirements and compares against company profile (via RAG)
2. Identifies contract risks with plain-language explanations
3. Generates competitive positioning insights
4. Extracts volume/pricing intelligence

RAG Integration:
After extracting eligibility items from the RFP, this agent queries the
NodeRAG system directly to auto-verify each requirement against the company's
knowledge base (SDVOSB status, NAICS codes, certifications, past performance, etc.)
"""

import os
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base_agent import BaseExtractionAgent


class RAGVerificationClient:
    """
    Client for querying the NodeRAG system to verify eligibility requirements
    against company profile/knowledge base.

    Uses NodeRAGClient directly for efficient in-process queries.
    """

    def __init__(self, service_url: str = None, org_id: str = None):
        """
        Initialize RAG client.

        Args:
            service_url: Deprecated - no longer used (direct function calls)
            org_id: Organization ID for the company's knowledge base
        """
        self.org_id = org_id
        self.noderag_client = None

        # Initialize NodeRAG client
        try:
            from noderag_client import NodeRAGClient
            self.noderag_client = NodeRAGClient()
            print(f"✅ [RAG] NodeRAGClient initialized for direct queries")
        except ImportError as e:
            print(f"⚠️ [RAG] NodeRAGClient not available: {e}")
        except Exception as e:
            print(f"⚠️ [RAG] Error initializing NodeRAGClient: {e}")

    def verify_requirement(self, requirement_text: str) -> Dict[str, Any]:
        """
        Query RAG to verify if company meets a specific requirement.

        Args:
            requirement_text: The eligibility requirement to verify

        Returns:
            Dict with verification result: status, confidence, source, explanation
        """
        if not self.org_id:
            print("⚠️ [RAG] No org_id provided, skipping verification")
            return {
                "verified": False,
                "status": "PENDING",
                "confidence": 0,
                "explanation": "No organization ID available for RAG lookup",
                "sources": []
            }

        if not self.noderag_client:
            print("⚠️ [RAG] NodeRAG client not available, skipping verification")
            return {
                "verified": False,
                "status": "PENDING",
                "confidence": 0,
                "explanation": "RAG service not available",
                "sources": []
            }

        try:
            # Formulate the verification query
            query = f"""Based on our company profile and capabilities, do we meet this RFP requirement?

Requirement: {requirement_text}

Answer with ONE of these at the START of your response:
- YES - if we clearly meet this requirement (provide evidence)
- NO - if we clearly do NOT meet this requirement (explain why)
- PARTIAL - if we partially meet it or need clarification
- UNKNOWN - if there's not enough information in our company profile

Then explain your answer with specific evidence from our company profile."""

            # Call NodeRAG directly instead of HTTP request
            result = self.noderag_client.generate_response(
                query=query,
                org_id=self.org_id,
                top_k=5
            )

            # Handle error responses
            if not result or result.get("error"):
                print(f"⚠️ [RAG] NodeRAG error: {result.get('error', 'Unknown error')}")
                return {
                    "verified": False,
                    "status": "PENDING",
                    "confidence": 0,
                    "explanation": result.get("error", "RAG query failed"),
                    "sources": []
                }

            # Extract answer from NodeRAG response
            # NodeRAG returns: {"response": "...", "sources": [...], "metadata": {...}}
            answer = result.get("response", "") or ""
            answer_upper = answer.upper()

            # Get metadata from response
            metadata = result.get("metadata", {})

            # Get sources - check multiple locations
            # v2: metadata.sources or top-level sources
            # v1: search_results or sources
            retrieved_nodes = (
                metadata.get("sources", []) or
                result.get("sources", []) or
                result.get("search_results", []) or
                result.get("retrieved_nodes", [])
            )

            # Get RAG confidence from metadata if available
            rag_confidence = metadata.get("confidence", 0)

            # Check if RAG has no relevant data
            no_data_indicators = [
                "NO RELEVANT INFORMATION",
                "NOT FOUND",
                "DON'T HAVE ENOUGH INFORMATION",
                "I DON'T HAVE",
                "CANNOT FIND",
                "NO INFORMATION AVAILABLE"
            ]
            if any(indicator in answer_upper for indicator in no_data_indicators):
                print(f"⚠️ [RAG] No relevant company data found for this requirement")
                return {
                    "verified": False,
                    "status": "PENDING",
                    "confidence": 0,
                    "explanation": "No relevant company profile data found for this requirement.",
                    "sources": []
                }

            # Determine status from answer (check first 100 chars for the verdict)
            status = "PENDING"
            confidence = rag_confidence if rag_confidence > 0 else 0  # Start with RAG confidence if available
            answer_start = answer_upper[:100]

            if answer_start.startswith("YES") or "YES -" in answer_start or "YES:" in answer_start:
                status = "PASS"
                if confidence == 0:
                    confidence = 0.85
            elif answer_start.startswith("NO") or "NO -" in answer_start or "NO:" in answer_start:
                status = "FAIL"
                if confidence == 0:
                    confidence = 0.85
            elif "PARTIAL" in answer_start:
                status = "PARTIAL"
                if confidence == 0:
                    confidence = 0.6
            elif "UNKNOWN" in answer_start:
                status = "PENDING"
                if confidence == 0:
                    confidence = 0.3
            else:
                # Try to infer from content
                if "WE MEET" in answer_upper or "WE HAVE" in answer_upper or "WE ARE" in answer_upper:
                    status = "PASS"
                    if confidence == 0:
                        confidence = 0.7
                elif "WE DO NOT" in answer_upper or "WE DON'T" in answer_upper or "NOT MEET" in answer_upper:
                    status = "FAIL"
                    if confidence == 0:
                        confidence = 0.7
                else:
                    status = "PENDING"
                    if confidence == 0:
                        confidence = 0.4

            # Adjust confidence based on source count
            if len(retrieved_nodes) > 3:
                confidence = min(confidence + 0.1, 1.0)
            elif len(retrieved_nodes) < 1:
                confidence = max(confidence - 0.2, 0.1)

            # Extract source references with full text for display
            sources = []
            source_text_parts = []
            for node in retrieved_nodes[:3]:  # Top 3 sources
                if isinstance(node, dict):
                    content = node.get("content", node.get("text", node.get("chunk_text", "")))
                    if content:
                        sources.append({
                            "content": content[:500],  # More content for display
                            "type": node.get("type", node.get("source_type", "document")),
                            "file_name": node.get("file_name", node.get("filename", "")),
                            "similarity": node.get("similarity_score", node.get("score", 0))
                        })
                        source_text_parts.append(content[:300])
                elif isinstance(node, str):
                    sources.append({
                        "content": node[:500],
                        "type": "document"
                    })
                    source_text_parts.append(node[:300])

            # Combine source texts for ragSourceText field
            combined_source_text = "\n---\n".join(source_text_parts) if source_text_parts else None

            print(f"✅ [RAG] Verification result: {status} (confidence: {confidence:.2f}, sources: {len(sources)})")

            return {
                "verified": True,
                "status": status,
                "confidence": confidence,
                "explanation": answer[:500],  # Limit explanation length
                "sources": sources,
                "source_text": combined_source_text,  # Combined source text for ragSourceText
                "rag_confidence": confidence,  # Explicit field for confidence
            }

        except TimeoutError:
            print(f"⚠️ [RAG] Request timeout for requirement: {requirement_text[:50]}...")
            return {
                "verified": False,
                "status": "PENDING",
                "confidence": 0,
                "explanation": "RAG verification timed out",
                "sources": []
            }
        except Exception as e:
            print(f"⚠️ [RAG] Error verifying requirement: {e}")
            return {
                "verified": False,
                "status": "PENDING",
                "confidence": 0,
                "explanation": f"RAG error: {str(e)}",
                "sources": []
            }

    def verify_requirements_batch(self, requirements: List[Dict], batch_size: int = 5) -> List[Dict]:
        """
        Verify multiple eligibility requirements in batches.

        Args:
            requirements: List of requirement dicts with 'requirement_text' field
            batch_size: Number of concurrent verifications

        Returns:
            List of requirements with updated verification results
        """
        if not self.org_id:
            print("⚠️ [RAG] No org_id provided, skipping batch verification")
            return requirements

        print(f"🔍 [RAG] Verifying {len(requirements)} requirements against company profile...")

        verified_requirements = []
        total = len(requirements)

        for i, req in enumerate(requirements):
            requirement_text = req.get("requirement_text", "")

            if not requirement_text:
                verified_requirements.append(req)
                continue

            print(f"  [{i+1}/{total}] Verifying: {requirement_text[:60]}...")

            # Query RAG for this requirement
            verification = self.verify_requirement(requirement_text)

            # Update requirement with verification results
            updated_req = req.copy()

            if verification["verified"]:
                # If RAG verification succeeded with good confidence, mark as AUTO_VERIFIED
                if verification["confidence"] >= 0.6 and verification["status"] in ["PASS", "FAIL"]:
                    updated_req["category"] = "AUTO_VERIFIED"
                    updated_req["status"] = verification["status"]
                    updated_req["verification_source"] = "RAG Company Profile"
                    updated_req["rag_confidence"] = verification["confidence"]
                    updated_req["rag_explanation"] = verification["explanation"][:500]
                    updated_req["rag_sources"] = verification.get("sources", [])  # Include sources for display
                    print(f"    ✅ AUTO_VERIFIED: {verification['status']} (confidence: {verification['confidence']:.2f})")
                else:
                    # Keep as USER_INPUT but add RAG context
                    updated_req["category"] = "USER_INPUT"
                    updated_req["status"] = verification["status"]
                    updated_req["rag_hint"] = verification["explanation"][:300]
                    updated_req["rag_confidence"] = verification["confidence"]
                    updated_req["rag_sources"] = verification.get("sources", [])  # Include sources even for user input
                    print(f"    📝 USER_INPUT needed: {verification['status']} (confidence: {verification['confidence']:.2f})")
            else:
                # RAG verification failed, needs user input
                updated_req["category"] = "USER_INPUT"
                updated_req["status"] = "PENDING"
                print(f"    ⏸️ PENDING: RAG verification unavailable")

            verified_requirements.append(updated_req)

            # Small delay between requests to avoid overwhelming the RAG service
            if i < total - 1:
                time.sleep(0.5)

        # Summary
        auto_verified = sum(1 for r in verified_requirements if r.get("category") == "AUTO_VERIFIED")
        print(f"📊 [RAG] Verification complete: {auto_verified}/{total} auto-verified")

        return verified_requirements


class IntelligenceAgent(BaseExtractionAgent):
    """
    Intelligence Layer agent for Go/No-Go analysis.
    Extracts: eligibility_items, risks, competitive_insights, pricing_intelligence

    After extraction, uses RAG to auto-verify eligibility items against
    the company's knowledge base.
    """

    AGENT_TYPE = "INTELLIGENCE"

    def __init__(self, company_profile: Optional[Dict] = None, org_id: str = None):
        super().__init__()
        self.company_profile = company_profile or {}
        self.org_id = org_id
        self.rag_client = None

        # Initialize RAG client if org_id provided
        if org_id:
            self.rag_client = RAGVerificationClient(org_id=org_id)
            print(f"🔗 [INTELLIGENCE] RAG verification enabled (org: {org_id[:8]}...)")

    def get_prompt(self) -> str:
        # Build company profile context if available
        company_context = ""
        if self.company_profile:
            company_context = f"""
COMPANY PROFILE (use to auto-verify eligibility):
- Business Type: {self.company_profile.get('business_type', 'Unknown')}
- SDVOSB Status: {self.company_profile.get('sdvosb_status', 'Unknown')}
- NAICS Codes: {self.company_profile.get('naics_codes', [])}
- Size Standard: {self.company_profile.get('size_standard', 'Unknown')}
- SAM Registration: {self.company_profile.get('sam_registered', 'Unknown')}
- Past Contract Types: {self.company_profile.get('past_contract_types', [])}

For each eligibility requirement, check if our company profile matches.
"""

        return f"""You are an expert Government Contracts Analyst performing a Go/No-Go assessment.
Analyze the RFP documents and extract intelligence for bid decision-making.

{company_context}

EXTRACT THE FOLLOWING:

1. **eligibility_items** - Requirements that determine if bidder can compete
   For each item:
   - requirement_text: The specific eligibility requirement
   - category: "AUTO_VERIFIED" (if we can confirm from profile) or "USER_INPUT" (needs human answer)
   - status: "PASS", "FAIL", "PARTIAL", or "PENDING"
   - is_disqualifying: true if failure means cannot bid
   - verification_source: What document/section verifies this
   - specific_question: If USER_INPUT, the PRECISE question to ask (not generic)
     Example: "Do you have at least 12 U.S.-licensed pharmacists who can pass a National Criminal History Check and are available to begin Oracle Health training within 30 days of award?"
   - source_section: Section reference
   - source_page: Page number

2. **risks** - Unusual or high-risk contract features
   For each risk:
   - risk_type: "contract_structure", "financial", "operational", "compliance", "performance"
   - title: Short descriptive title
   - description: What the risk is
   - severity: "high", "medium", "low"
   - impact: Plain-language explanation of what this means for the bidder
   - source_section: Where found
   - source_page: Page number

   Common risks to look for:
   - Zero or low guaranteed minimum
   - Required investment before revenue (training, credentials, etc.)
   - Limitations on Subcontracting percentages
   - Government's right to increase scope
   - Unusual payment terms
   - Heavy liquidated damages
   - Stringent SLAs/KPIs

3. **competitive_insights** - What will differentiate winning bids
   For each insight:
   - insight_type: "differentiator", "pricing_strategy", "evaluation_focus", "past_performance"
   - title: Short title
   - description: The insight
   - actionable: Specific action the bidder should take
   - source_section: Where derived from

   Based on evaluation criteria, identify:
   - If NPV is used, note that lower future-year pricing has outsized impact
   - If past performance is weighted heavily, note specific PSC/NAICS codes needed
   - Key discriminators that will separate winners from losers

4. **pricing_intelligence** - Volume and pricing data
   - estimated_value: Estimated total contract value (if stated or calculable)
   - contract_type: "FFP", "T&M", "CPFF", "IDIQ", etc.
   - pricing_notes: Key pricing considerations
   - volume_data: Estimated quantities by facility/location/CLIN if available

5. **go_no_go_recommendation** - Overall assessment
   - recommendation: "PURSUE", "PURSUE_WITH_RISK", "DO_NOT_PURSUE", "INCOMPLETE"
   - rationale: Brief explanation
   - key_concerns: List of top 3 concerns
   - key_strengths: List of top 3 potential strengths

OUTPUT FORMAT:
{{
  "eligibility_items": [...],
  "risks": [...],
  "competitive_insights": [...],
  "pricing_intelligence": {{...}},
  "go_no_go_recommendation": {{...}}
}}

Return ONLY valid JSON, no markdown."""

    def extract(self, files: List[Dict[str, str]], org_id: str, skip_rag_verification: bool = False) -> Dict[str, Any]:
        """
        Run extraction and optionally verify eligibility items via RAG.

        Args:
            files: List of file dictionaries with 'file_id', 'filename', 'gcs_url'
            org_id: Organization ID
            skip_rag_verification: If True, skip RAG verification (for two-phase approach)

        Returns:
            Dictionary with extraction results including RAG-verified eligibility items
        """
        # First, run the base extraction
        result = super().extract(files, org_id)

        if not result.get("success"):
            return result

        # If skip_rag_verification is True, return items without verification
        # Backend will handle verification separately for per-item loading
        if skip_rag_verification:
            print("ℹ️ [INTELLIGENCE] RAG verification skipped (two-phase mode)")
            result["rag_verification_enabled"] = False
            result["rag_verification_pending"] = True
            return result

        # If RAG client is available, verify eligibility items
        if self.rag_client and result.get("eligibility_items"):
            print(f"🔍 [INTELLIGENCE] Starting RAG verification of {len(result['eligibility_items'])} eligibility items...")

            try:
                verified_items = self.rag_client.verify_requirements_batch(
                    result["eligibility_items"],
                    batch_size=5
                )
                result["eligibility_items"] = verified_items

                # Update counts
                auto_verified_count = sum(1 for item in verified_items if item.get("category") == "AUTO_VERIFIED")
                result["auto_verified_count"] = auto_verified_count
                result["user_input_count"] = len(verified_items) - auto_verified_count
                result["rag_verification_enabled"] = True

                print(f"✅ [INTELLIGENCE] RAG verification complete: {auto_verified_count} auto-verified, {result['user_input_count']} need user input")

            except Exception as e:
                print(f"⚠️ [INTELLIGENCE] RAG verification failed: {e}")
                result["rag_verification_error"] = str(e)
                result["rag_verification_enabled"] = False
        else:
            result["rag_verification_enabled"] = False
            if not self.rag_client:
                print("ℹ️ [INTELLIGENCE] RAG verification skipped (no session ID provided)")

        return result

    def verify_single_item(self, requirement_text: str) -> Dict[str, Any]:
        """
        Verify a single eligibility item against RAG.

        Args:
            requirement_text: The requirement text to verify

        Returns:
            Verification result with status, category, confidence, sources, etc.
        """
        if not self.rag_client:
            return {
                "success": False,
                "error": "No RAG client configured",
                "status": "PENDING",
                "category": "USER_INPUT"
            }

        try:
            result = self.rag_client.verify_requirement(requirement_text)

            # Extract values from RAG result
            confidence = result.get("confidence", 0)
            status = result.get("status", "PENDING")
            explanation = result.get("explanation", "")
            sources = result.get("sources", [])

            # Determine category based on verification result
            category = "USER_INPUT"
            if result.get("verified") and confidence >= 0.6 and status in ["PASS", "FAIL"]:
                category = "AUTO_VERIFIED"

            return {
                "success": result.get("verified", False),
                "status": status,
                "category": category,
                "confidence": confidence,
                "rag_confidence": confidence,  # Alias for backwards compatibility
                "explanation": explanation,
                "rag_explanation": explanation,  # Alias for backwards compatibility
                "sources": sources,
                "verification_source": "RAG Company Profile" if result.get("verified") else None,
                "nodes_retrieved": result.get("nodes_retrieved", 0),
            }
        except Exception as e:
            print(f"⚠️ [INTELLIGENCE] Single item RAG verification failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "status": "PENDING",
                "category": "USER_INPUT"
            }

    def validate_result(self, result: Dict) -> Dict:
        """Validate and ensure required fields exist"""
        validated = {
            "eligibility_items": [],
            "risks": [],
            "competitive_insights": [],
            "pricing_intelligence": {},
            "go_no_go_recommendation": {
                "recommendation": "INCOMPLETE",
                "rationale": "Assessment incomplete",
                "key_concerns": [],
                "key_strengths": []
            }
        }

        # Eligibility items
        if "eligibility_items" in result:
            valid_categories = {"AUTO_VERIFIED", "USER_INPUT"}
            valid_statuses = {"PASS", "FAIL", "PARTIAL", "PENDING"}

            for item in result["eligibility_items"]:
                category = item.get("category", "USER_INPUT")
                if category not in valid_categories:
                    category = "USER_INPUT"

                status = item.get("status", "PENDING")
                if status not in valid_statuses:
                    status = "PENDING"

                validated["eligibility_items"].append({
                    "requirement_text": item.get("requirement_text", ""),
                    "category": category,
                    "status": status,
                    "is_disqualifying": bool(item.get("is_disqualifying", False)),
                    "verification_source": item.get("verification_source"),
                    "specific_question": item.get("specific_question"),
                    "source_section": item.get("source_section"),
                    "source_page": item.get("source_page"),
                })

        # Risks
        if "risks" in result:
            valid_types = {"contract_structure", "financial", "operational", "compliance", "performance"}
            valid_severity = {"high", "medium", "low"}

            for risk in result["risks"]:
                risk_type = risk.get("risk_type", "operational")
                if risk_type not in valid_types:
                    risk_type = "operational"

                severity = risk.get("severity", "medium")
                if severity not in valid_severity:
                    severity = "medium"

                validated["risks"].append({
                    "risk_type": risk_type,
                    "title": risk.get("title", ""),
                    "description": risk.get("description", ""),
                    "severity": severity,
                    "impact": risk.get("impact"),
                    "source_section": risk.get("source_section"),
                    "source_page": risk.get("source_page"),
                })

        # Competitive insights
        if "competitive_insights" in result:
            valid_insight_types = {"differentiator", "pricing_strategy", "evaluation_focus", "past_performance"}

            for insight in result["competitive_insights"]:
                insight_type = insight.get("insight_type", "differentiator")
                if insight_type not in valid_insight_types:
                    insight_type = "differentiator"

                validated["competitive_insights"].append({
                    "insight_type": insight_type,
                    "title": insight.get("title", ""),
                    "description": insight.get("description", ""),
                    "actionable": insight.get("actionable"),
                    "source_section": insight.get("source_section"),
                })

        # Pricing intelligence
        if "pricing_intelligence" in result:
            pi = result["pricing_intelligence"]
            validated["pricing_intelligence"] = {
                "estimated_value": pi.get("estimated_value"),
                "contract_type": pi.get("contract_type"),
                "pricing_notes": pi.get("pricing_notes"),
                "volume_data": pi.get("volume_data"),
            }

        # Go/No-Go recommendation
        if "go_no_go_recommendation" in result:
            rec = result["go_no_go_recommendation"]
            valid_recommendations = {"PURSUE", "PURSUE_WITH_RISK", "DO_NOT_PURSUE", "INCOMPLETE"}

            recommendation = rec.get("recommendation", "INCOMPLETE")
            if recommendation not in valid_recommendations:
                recommendation = "INCOMPLETE"

            validated["go_no_go_recommendation"] = {
                "recommendation": recommendation,
                "rationale": rec.get("rationale", ""),
                "key_concerns": rec.get("key_concerns", [])[:5],  # Max 5
                "key_strengths": rec.get("key_strengths", [])[:5],  # Max 5
            }

        # Add counts
        validated["count"] = len(validated["eligibility_items"])
        validated["risk_count"] = len(validated["risks"])
        validated["insight_count"] = len(validated["competitive_insights"])

        return validated


# Endpoint handler for Flask
def extract_intelligence_handler(request_data: Dict) -> Dict[str, Any]:
    """
    Handle intelligence extraction request

    Args:
        request_data: Dict with:
            - 'files': List of file dicts with gcs_url, filename, file_id
            - 'org_id': Organization ID (also used for RAG knowledge base lookup)
            - 'company_profile': Optional static company profile dict
            - 'rag_session_id': Deprecated - use org_id instead
            - 'skip_rag_verification': If True, skip RAG verification (for two-phase approach)

    Returns:
        Extraction result with RAG-verified eligibility items
    """
    files = request_data.get("files", [])
    org_id = request_data.get("org_id", "")
    company_profile = request_data.get("company_profile")
    # Support both org_id and rag_session_id (rag_session_id is deprecated, use org_id)
    rag_org_id = request_data.get("rag_session_id") or org_id
    skip_rag_verification = request_data.get("skip_rag_verification", False)

    if not files:
        return {
            "success": False,
            "error": "No files provided"
        }

    # Log RAG configuration
    if skip_rag_verification:
        print("ℹ️ [INTELLIGENCE] Two-phase mode - RAG verification will be done per-item")
    elif rag_org_id:
        print(f"🔗 RAG verification enabled with org: {rag_org_id[:8]}...")
    else:
        print("ℹ️ [INTELLIGENCE] No org_id provided - eligibility items will need manual verification")

    agent = IntelligenceAgent(
        company_profile=company_profile,
        org_id=rag_org_id
    )
    return agent.extract(files, org_id, skip_rag_verification=skip_rag_verification)


def verify_item_handler(request_data: Dict) -> Dict[str, Any]:
    """
    Handle single eligibility item RAG verification request

    Args:
        request_data: Dict with:
            - 'requirement_text': The requirement text to verify
            - 'org_id': Organization ID for RAG knowledge base lookup
            - 'rag_session_id': Deprecated - use org_id instead

    Returns:
        Verification result with status, category, confidence
    """
    requirement_text = request_data.get("requirement_text", "")
    # Support both org_id and rag_session_id
    org_id = request_data.get("org_id") or request_data.get("rag_session_id")

    if not requirement_text:
        return {
            "success": False,
            "error": "No requirement_text provided"
        }

    if not org_id:
        return {
            "success": False,
            "error": "No org_id provided",
            "status": "PENDING",
            "category": "USER_INPUT"
        }

    agent = IntelligenceAgent(org_id=org_id)
    return agent.verify_single_item(requirement_text)
