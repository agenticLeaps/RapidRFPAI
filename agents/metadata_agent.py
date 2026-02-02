"""
Metadata Agent - Pass 1 (Blocking)
Extracts project metadata needed for project creation
This is the ONLY blocking extraction - must complete before project is created
"""

from typing import Dict, Any
from .base_agent import BaseExtractionAgent


class MetadataAgent(BaseExtractionAgent):
    """
    Metadata extraction agent for project creation.
    Extracts: project_metadata, pursuit_details, production_details, file_classifications
    """

    AGENT_TYPE = "METADATA"

    def get_prompt(self) -> str:
        return """You are a specialized RFP Analyst. Extract ONLY the following critical metadata needed to initialize a project workspace.

IMPORTANT: This is the FIRST extraction pass. Extract ONLY what's specified below - do NOT extract compliance requirements or submission items.

EXTRACT:

1. **project_metadata** (REQUIRED):
   - project_name: Title of the RFP/solicitation (from subject line, cover page, or header)
   - issuer_name: Organization/agency issuing the RFP
   - due_date: Submission deadline in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
   - solicitation_number: Official solicitation/RFP number if provided
   - naics_code: NAICS code if specified
   - set_aside_type: Set-aside type if specified (e.g., "SDVOSB", "8(a)", "HUBZone", "Small Business", "None")
   - contract_type: Contract type if specified (e.g., "FFP", "T&M", "CPFF", "IDIQ")

2. **pursuit_details** (if found):
   - customer_address: Full address object with street, city, state, zip, country
   - contact_info: Primary contact with name, email, phone, title
   - final_approver: Person with final approval authority (name, title)
   - signer: Authorized contract signer (name, title)
   - contracting_office: Name of contracting office

3. **production_details** (if found):
   - submission_format: "Digital", "Physical", "Both"
   - file_requirements: Object with allowed formats, max_file_size, naming_convention
   - print_requirements: Object with copies, binding, paper_size
   - delivery_method: Object with electronic (method, destination, portal_url) and physical (address)
   - special_instructions: Any special formatting or delivery instructions
   - questions_deadline: Deadline for submitting questions (ISO 8601)
   - period_of_performance: Contract duration if specified

4. **file_classifications** (REQUIRED - for each input document):
   For each document you analyze, provide:
   - filename: Original filename
   - role: One of: "PRIMARY_SOLICITATION", "AMENDMENT", "PRICING_TEMPLATE", "QUESTIONNAIRE_TEMPLATE", "REFERENCE_DOCUMENT", "UNKNOWN"
   - confidence: "high", "medium", or "low"
   - description: Brief description of what the document contains

OUTPUT FORMAT:
{
  "project_metadata": {...},
  "pursuit_details": {...},
  "production_details": {...},
  "file_classifications": [
    {"filename": "...", "role": "...", "confidence": "...", "description": "..."}
  ]
}

DO NOT extract compliance matrix or submission requirements - those will be processed by separate agents.
Return ONLY valid JSON, no markdown."""

    def validate_result(self, result: Dict) -> Dict:
        """Validate and ensure required fields exist"""
        validated = {
            "project_metadata": {},
            "pursuit_details": {},
            "production_details": {},
            "file_classifications": []
        }

        # Project metadata
        if "project_metadata" in result:
            pm = result["project_metadata"]
            validated["project_metadata"] = {
                "project_name": pm.get("project_name", "Untitled RFP"),
                "issuer_name": pm.get("issuer_name"),
                "due_date": pm.get("due_date"),
                "solicitation_number": pm.get("solicitation_number"),
                "naics_code": pm.get("naics_code"),
                "set_aside_type": pm.get("set_aside_type"),
                "contract_type": pm.get("contract_type"),
            }

        # Pursuit details
        if "pursuit_details" in result:
            pd = result["pursuit_details"]
            validated["pursuit_details"] = {
                "customer_address": pd.get("customer_address", {}),
                "contact_info": pd.get("contact_info", {}),
                "final_approver": pd.get("final_approver", {}),
                "signer": pd.get("signer", {}),
                "contracting_office": pd.get("contracting_office"),
            }

        # Production details
        if "production_details" in result:
            prod = result["production_details"]
            validated["production_details"] = {
                "submission_format": prod.get("submission_format"),
                "file_requirements": prod.get("file_requirements", {}),
                "print_requirements": prod.get("print_requirements", {}),
                "delivery_method": prod.get("delivery_method", {}),
                "special_instructions": prod.get("special_instructions"),
                "questions_deadline": prod.get("questions_deadline"),
                "period_of_performance": prod.get("period_of_performance"),
            }

        # File classifications
        if "file_classifications" in result:
            valid_roles = {
                "PRIMARY_SOLICITATION", "AMENDMENT", "PRICING_TEMPLATE",
                "QUESTIONNAIRE_TEMPLATE", "REFERENCE_DOCUMENT", "UNKNOWN"
            }
            for fc in result["file_classifications"]:
                role = fc.get("role", "UNKNOWN")
                if role not in valid_roles:
                    role = "UNKNOWN"
                validated["file_classifications"].append({
                    "filename": fc.get("filename", ""),
                    "role": role,
                    "confidence": fc.get("confidence", "low"),
                    "description": fc.get("description", ""),
                })

        return validated


# Endpoint handler for Flask
def extract_metadata_handler(request_data: Dict) -> Dict[str, Any]:
    """
    Handle metadata extraction request

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

    agent = MetadataAgent()
    return agent.extract(files, org_id)
