"""
Compliance Agent - Pass 3 (Background)
Extracts compliance matrix items - discrete requirements the contractor must meet.
Focuses on "shall", "must", "required" statements from PWS, QASP, and performance sections.
"""

from typing import Dict, Any
from .base_agent import BaseExtractionAgent


class ComplianceAgent(BaseExtractionAgent):
    """
    Compliance Matrix extraction agent.
    Extracts 20-40 discrete requirements with categorization and severity.
    """

    AGENT_TYPE = "COMPLIANCE"
    MAX_ITEMS = 40

    def get_prompt(self) -> str:
        return f"""You are a Compliance Matrix Specialist analyzing RFP documents.
Extract discrete compliance requirements that a contractor must meet.

INSTRUCTIONS:
1. Read through PWS (Performance Work Statement), QASP, SOW, and all technical/performance sections
2. Identify EVERY statement with "shall", "must", "will", "required to", "contractor will/shall"
3. Each requirement should be a SINGLE, DISCRETE, VERIFIABLE obligation
4. Extract between 20 and {self.MAX_ITEMS} of the most critical requirements

For each requirement, extract:

- id: Sequential ID format "CM-001", "CM-002", etc.
- requirement_text: The EXACT requirement text, condensed to one clear sentence
- source_section: Section reference (e.g., "L.4.2.1", "PWS 3.2", "Section C.5")
- source_page: Page number where found
- category: One of:
  - "ADMINISTRATIVE" - Administrative/procedural requirements
  - "TECHNICAL" - Technical specifications and capabilities
  - "PERSONNEL" - Staffing, qualifications, certifications
  - "CERTIFICATION" - Required certifications, licenses, registrations
  - "EXPERIENCE" - Past performance, experience requirements
  - "FINANCIAL" - Financial requirements, bonding, insurance
  - "LEGAL" - Legal/regulatory compliance
  - "SECURITY" - Security clearances, IT security
  - "FORMAT" - Document format, submission format
  - "SUBMISSION" - What to submit, how to submit
  - "PERFORMANCE" - Performance standards, SLAs, metrics
  - "OTHER" - Doesn't fit other categories

- severity:
  - "BLOCKING" - Failure to comply = automatic disqualification
  - "CRITICAL" - Must be addressed, significant evaluation impact
  - "IMPORTANT" - Should be addressed, some evaluation impact
  - "INFORMATIONAL" - Good to address, minimal impact

- response_section: Suggested proposal section to address this (e.g., "Technical Approach", "Management Plan", "Past Performance")

GUIDELINES:
- Focus on ACTIONABLE requirements, not general statements
- Combine related sub-requirements if they're clearly part of one obligation
- Prioritize requirements that have evaluation weight or are explicitly labeled "mandatory"
- For personnel requirements, include specific numbers, qualifications, and certifications
- Include delivery/timeline requirements

OUTPUT FORMAT:
{{
  "compliance_matrix": [
    {{
      "id": "CM-001",
      "requirement_text": "...",
      "source_section": "...",
      "source_page": 15,
      "category": "TECHNICAL",
      "severity": "CRITICAL",
      "response_section": "Technical Approach"
    }}
  ],
  "summary": {{
    "total_count": 30,
    "blocking_count": 5,
    "critical_count": 12,
    "by_category": {{
      "TECHNICAL": 10,
      "PERSONNEL": 5,
      ...
    }}
  }}
}}

Return ONLY valid JSON, no markdown."""

    def validate_result(self, result: Dict) -> Dict:
        """Validate and ensure required fields exist"""
        validated = {
            "compliance_matrix": [],
            "summary": {
                "total_count": 0,
                "blocking_count": 0,
                "critical_count": 0,
                "by_category": {}
            }
        }

        valid_categories = {
            "ADMINISTRATIVE", "TECHNICAL", "PERSONNEL", "CERTIFICATION",
            "EXPERIENCE", "FINANCIAL", "LEGAL", "SECURITY", "FORMAT",
            "SUBMISSION", "PERFORMANCE", "OTHER"
        }

        valid_severities = {"BLOCKING", "CRITICAL", "IMPORTANT", "INFORMATIONAL"}

        category_counts = {}
        blocking_count = 0
        critical_count = 0

        if "compliance_matrix" in result:
            for idx, item in enumerate(result["compliance_matrix"]):
                # Generate ID if not present
                item_id = item.get("id", f"CM-{str(idx + 1).zfill(3)}")

                # Validate category
                category = item.get("category", "OTHER")
                if category not in valid_categories:
                    category = "OTHER"

                # Validate severity
                severity = item.get("severity", "IMPORTANT")
                if severity not in valid_severities:
                    severity = "IMPORTANT"

                if severity == "BLOCKING":
                    blocking_count += 1
                elif severity == "CRITICAL":
                    critical_count += 1

                # Track category counts
                category_counts[category] = category_counts.get(category, 0) + 1

                validated["compliance_matrix"].append({
                    "id": item_id,
                    "requirement_text": item.get("requirement_text", ""),
                    "source_section": item.get("source_section"),
                    "source_page": item.get("source_page"),
                    "category": category,
                    "severity": severity,
                    "response_section": item.get("response_section"),
                })

        # Build summary
        validated["summary"] = {
            "total_count": len(validated["compliance_matrix"]),
            "blocking_count": blocking_count,
            "critical_count": critical_count,
            "by_category": category_counts
        }

        # Add count for status tracking
        validated["count"] = len(validated["compliance_matrix"])

        return validated


# Endpoint handler for Flask
def extract_compliance_handler(request_data: Dict) -> Dict[str, Any]:
    """
    Handle compliance extraction request

    Args:
        request_data: Dict with 'files' list and 'org_id'

    Returns:
        Extraction result
    """
    files = request_data.get("files", [])
    org_id = request_data.get("org_id", "")

    if not files:
        return {
            "success": False,
            "error": "No files provided"
        }

    agent = ComplianceAgent()
    return agent.extract(files, org_id)
