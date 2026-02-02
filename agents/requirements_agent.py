"""
Requirements Agent - Pass 4 (Background)
Extracts submission requirements - what to submit, volume structure, page limits, attachments.
"""

from typing import Dict, Any
from .base_agent import BaseExtractionAgent


class RequirementsAgent(BaseExtractionAgent):
    """
    Submission Requirements extraction agent.
    Extracts volume structure, page limits, required attachments, format requirements.
    """

    AGENT_TYPE = "REQUIREMENTS"
    MAX_ITEMS = 50

    def get_prompt(self) -> str:
        return f"""You are a Proposal Submission Specialist analyzing RFP documents.
Extract detailed submission requirements that define WHAT to submit and HOW.

INSTRUCTIONS:
1. Read Section L (Instructions), Section M (Evaluation), and any submission guidance
2. Identify the complete volume/document structure required
3. Extract ALL page limits, format requirements, and mandatory attachments
4. Note any unique submission requirements

EXTRACT:

1. **volume_structure** - The proposal organization
   For each volume/section:
   - volume_number: Volume identifier (e.g., "Volume I", "1", "Technical")
   - volume_name: Name of the volume
   - description: What should be included
   - page_limit: Maximum pages allowed (null if not specified)
   - format_requirements: Specific format for this volume
   - subsections: Array of required subsections with names and page limits
   - is_separately_bound: Whether this volume must be separate

2. **required_attachments** - Mandatory documents/forms
   For each attachment:
   - name: Name of the required document
   - description: What it is
   - file_extension: Required file format extension (e.g., ".pdf", ".xlsx", ".docx", ".doc", ".xls", ".zip", ".txt", null if not specified)
     IMPORTANT: Extract the exact file extension if the RFP specifies a format (e.g., "Submit in PDF format" -> ".pdf", "Excel spreadsheet" -> ".xlsx")
   - template_provided: true/false - is a template/form provided
   - source_section: Where this requirement is stated
   - is_mandatory: true/false
   - submission_method: How to submit (with proposal, separate, portal, etc.)

3. **format_requirements** - Overall format specifications
   - font_type: Required font (e.g., "Times New Roman", "Arial")
   - font_size: Minimum font size
   - margins: Margin requirements
   - line_spacing: Single, double, 1.5, etc.
   - paper_size: Letter, A4, etc.
   - header_footer_requirements: What must appear in headers/footers
   - numbering_requirements: Page/section numbering rules
   - file_format: PDF, Word, etc.
   - file_naming_convention: How to name files
   - max_file_size: Maximum file size if specified
   - electronic_submission: Portal URL, email, or other electronic method
   - physical_copies: Number of hard copies required

4. **evaluation_factors** - How proposal will be scored
   For each factor:
   - factor_name: Name of evaluation factor
   - weight: Percentage or points if specified
   - description: What is being evaluated
   - subfactors: Array of subfactors with names and weights
   - source_section: Where defined

5. **key_dates** - Important deadlines
   - questions_due: Deadline for questions
   - answers_published: When answers will be posted
   - proposal_due: Final submission deadline
   - oral_presentations: If applicable, when
   - award_date: Expected award date
   - performance_start: Contract start date

6. **special_instructions** - Any unique requirements
   - Array of special submission instructions not covered above

OUTPUT FORMAT:
{{
  "volume_structure": [...],
  "required_attachments": [...],
  "format_requirements": {{...}},
  "evaluation_factors": [...],
  "key_dates": {{...}},
  "special_instructions": [...]
}}

Return ONLY valid JSON, no markdown."""

    def validate_result(self, result: Dict) -> Dict:
        """Validate and ensure required fields exist"""
        validated = {
            "volume_structure": [],
            "required_attachments": [],
            "format_requirements": {},
            "evaluation_factors": [],
            "key_dates": {},
            "special_instructions": []
        }

        # Volume structure
        if "volume_structure" in result:
            for vol in result["volume_structure"]:
                validated["volume_structure"].append({
                    "volume_number": vol.get("volume_number"),
                    "volume_name": vol.get("volume_name", ""),
                    "description": vol.get("description", ""),
                    "page_limit": vol.get("page_limit"),
                    "format_requirements": vol.get("format_requirements"),
                    "subsections": vol.get("subsections", []),
                    "is_separately_bound": bool(vol.get("is_separately_bound", False)),
                })

        # Required attachments
        if "required_attachments" in result:
            for att in result["required_attachments"]:
                # Normalize file extension - ensure it starts with a dot
                file_ext = att.get("file_extension")
                if file_ext and not file_ext.startswith('.'):
                    file_ext = f".{file_ext}"

                validated["required_attachments"].append({
                    "name": att.get("name", ""),
                    "description": att.get("description", ""),
                    "file_extension": file_ext.lower() if file_ext else None,
                    "template_provided": bool(att.get("template_provided", False)),
                    "source_section": att.get("source_section"),
                    "is_mandatory": bool(att.get("is_mandatory", True)),
                    "submission_method": att.get("submission_method"),
                })

        # Format requirements
        if "format_requirements" in result:
            fr = result["format_requirements"]
            validated["format_requirements"] = {
                "font_type": fr.get("font_type"),
                "font_size": fr.get("font_size"),
                "margins": fr.get("margins"),
                "line_spacing": fr.get("line_spacing"),
                "paper_size": fr.get("paper_size"),
                "header_footer_requirements": fr.get("header_footer_requirements"),
                "numbering_requirements": fr.get("numbering_requirements"),
                "file_format": fr.get("file_format"),
                "file_naming_convention": fr.get("file_naming_convention"),
                "max_file_size": fr.get("max_file_size"),
                "electronic_submission": fr.get("electronic_submission"),
                "physical_copies": fr.get("physical_copies"),
            }

        # Evaluation factors
        if "evaluation_factors" in result:
            for factor in result["evaluation_factors"]:
                validated["evaluation_factors"].append({
                    "factor_name": factor.get("factor_name", ""),
                    "weight": factor.get("weight"),
                    "description": factor.get("description", ""),
                    "subfactors": factor.get("subfactors", []),
                    "source_section": factor.get("source_section"),
                })

        # Key dates
        if "key_dates" in result:
            kd = result["key_dates"]
            validated["key_dates"] = {
                "questions_due": kd.get("questions_due"),
                "answers_published": kd.get("answers_published"),
                "proposal_due": kd.get("proposal_due"),
                "oral_presentations": kd.get("oral_presentations"),
                "award_date": kd.get("award_date"),
                "performance_start": kd.get("performance_start"),
            }

        # Special instructions
        if "special_instructions" in result:
            validated["special_instructions"] = result["special_instructions"]

        # Add counts for tracking
        validated["count"] = len(validated["volume_structure"])
        validated["attachment_count"] = len(validated["required_attachments"])
        validated["factor_count"] = len(validated["evaluation_factors"])

        return validated


# Endpoint handler for Flask
def extract_requirements_handler(request_data: Dict) -> Dict[str, Any]:
    """
    Handle requirements extraction request

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

    agent = RequirementsAgent()
    return agent.extract(files, org_id)
