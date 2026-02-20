"""
Requirements Agent - Pass 4 (Background)
Extracts submission requirements - what to submit, volume structure, page limits, attachments.
Enhanced with template extraction and coordinate tracking.
"""

from typing import Dict, Any, List, Tuple
from .base_agent import BaseExtractionAgent


class RequirementsAgent(BaseExtractionAgent):
    """
    Submission Requirements extraction agent.
    Extracts volume structure, page limits, required attachments, format requirements.
    Now also extracts template content and location markers for coordinate extraction.
    """

    AGENT_TYPE = "REQUIREMENTS"
    MAX_ITEMS = 50

    def get_prompt(self) -> str:
        return f"""You are a Proposal Submission Specialist analyzing RFP documents.
Extract detailed submission requirements that define WHAT to submit and HOW.
IMPORTANT: For each requirement with a template/form, extract the FULL template content and location markers.

INSTRUCTIONS:
1. Read Section L (Instructions), Section M (Evaluation), and any submission guidance
2. Identify the complete volume/document structure required
3. Extract ALL page limits, format requirements, and mandatory attachments
4. For attachments with templates: Extract the COMPLETE template text including all fields, tables, and instructions
5. Note any unique submission requirements

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
   - source_section: Where this requirement is stated (e.g., "Section L.3")
   - source_text: The EXACT quoted text from the document where this is defined (verbatim quote, max 500 chars)

2. **required_attachments** - Mandatory documents/forms (ENHANCED)
   For each attachment:
   - name: Name of the required document
   - description: What it is
   - file_extension: Required file format extension (e.g., ".pdf", ".xlsx", ".docx", ".doc", ".xls", ".zip", ".txt", null if not specified)
     IMPORTANT: Extract the exact file extension if the RFP specifies a format (e.g., "Submit in PDF format" -> ".pdf", "Excel spreadsheet" -> ".xlsx")
   - template_provided: true/false - is a template/form provided in the RFP
   - source_section: Where this requirement is stated (e.g., "Section L.5.2", "Appendix B")
   - source_text: The EXACT quoted text from the document where this requirement is stated (verbatim quote, max 500 chars)
   - is_mandatory: true/false
   - submission_method: How to submit (with proposal, separate, portal, etc.)

   NEW FIELDS for template extraction:
   - full_context: The COMPLETE text explaining this requirement including all instructions, guidance, and the template itself (up to 5000 chars). Include 2-3 paragraphs before and after the template.
   - template_type: One of: "form", "table", "certificate", "checklist", "narrative", "spreadsheet", "acknowledgment"
   - template_content: Object containing the extracted template structure:
     - type: "table" | "form_fields" | "text_block"
     - headers: Array of column headers (for tables)
     - rows: Array of row data (for tables, each row is array of cell values)
     - fields: Array of form fields, each with: {{name, type, required, description}}
       - type can be: "text", "signature", "date", "checkbox", "long_text", "number"
     - raw_text: The complete raw text of the template exactly as it appears
   - template_markers: Object to help locate the template in the original document:
     - start_text: The EXACT text that marks the beginning of the template (first 100 chars)
     - end_text: The EXACT text that marks the end of the template (last 100 chars)
     - page_hint: Approximate page number if mentioned (e.g., "Appendix B" or page number)

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
   - source_section: Where defined (e.g., "Section M.2")
   - source_text: The EXACT quoted text from the document defining this factor (verbatim quote, max 500 chars)

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
                    "source_section": vol.get("source_section"),
                    "source_text": vol.get("source_text"),
                })

        # Required attachments (Enhanced with template extraction)
        if "required_attachments" in result:
            for att in result["required_attachments"]:
                # Normalize file extension - ensure it starts with a dot
                file_ext = att.get("file_extension")
                if file_ext and not file_ext.startswith('.'):
                    file_ext = f".{file_ext}"

                # Process template_content if present
                template_content = att.get("template_content")
                if template_content:
                    template_content = {
                        "type": template_content.get("type", "text_block"),
                        "headers": template_content.get("headers", []),
                        "rows": template_content.get("rows", []),
                        "fields": template_content.get("fields", []),
                        "raw_text": template_content.get("raw_text", "")
                    }

                # Process template_markers if present
                template_markers = att.get("template_markers")
                if template_markers:
                    template_markers = {
                        "start_text": template_markers.get("start_text", ""),
                        "end_text": template_markers.get("end_text", ""),
                        "page_hint": template_markers.get("page_hint")
                    }

                validated["required_attachments"].append({
                    # Original fields
                    "name": att.get("name", ""),
                    "description": att.get("description", ""),
                    "file_extension": file_ext.lower() if file_ext else None,
                    "template_provided": bool(att.get("template_provided", False)),
                    "source_section": att.get("source_section"),
                    "source_text": att.get("source_text"),
                    "is_mandatory": bool(att.get("is_mandatory", True)),
                    "submission_method": att.get("submission_method"),
                    # NEW: Enhanced template fields
                    "full_context": att.get("full_context", ""),
                    "template_type": att.get("template_type"),
                    "template_content": template_content,
                    "template_markers": template_markers,
                    "template_location": None,  # Will be populated by coordinate extraction
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
                    "source_text": factor.get("source_text"),
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


    def extract_template_coordinates(
        self,
        attachments: List[Dict],
        files_data: List[Tuple[bytes, str]]
    ) -> List[Dict]:
        """
        Post-process attachments to add template coordinates using PyMuPDF

        Args:
            attachments: List of validated attachment dicts
            files_data: List of (file_bytes, filename) tuples

        Returns:
            Attachments with template_location populated
        """
        try:
            from .template_extractor import template_extractor
        except ImportError:
            print("Template extractor not available")
            return attachments

        # Build filename to bytes mapping
        file_map = {filename: data for data, filename in files_data}

        for att in attachments:
            if not att.get("template_provided") or not att.get("template_markers"):
                continue

            markers = att["template_markers"]
            source_section = att.get("source_section", "")

            # Try to find the template in each PDF file
            for filename, file_bytes in file_map.items():
                if not filename.lower().endswith('.pdf'):
                    continue

                result = template_extractor.extract_template_from_pdf(
                    pdf_bytes=file_bytes,
                    template_hints={
                        "start_marker": markers.get("start_text", ""),
                        "end_marker": markers.get("end_text", ""),
                        "template_type": att.get("template_type", "form"),
                        "source_section": source_section
                    }
                )

                if result.get("success"):
                    location = result["template_location"]
                    if location:
                        location["source_file"] = filename
                        att["template_location"] = location

                    # Optionally enhance template_content with extracted data
                    if result.get("template_content") and not att.get("template_content", {}).get("raw_text"):
                        att["template_content"] = result["template_content"]

                    break  # Found in this file, no need to check others

        return attachments

    def extract(self, files: List[Dict[str, str]], org_id: str) -> Dict[str, Any]:
        """
        Override base extract to add template coordinate extraction

        Args:
            files: List of file dictionaries with 'file_id', 'filename', 'gcs_url'
            org_id: Organization ID

        Returns:
            Dictionary with extraction results including template coordinates
        """
        # Call parent extract method
        result = super().extract(files, org_id)

        if not result.get("success"):
            return result

        # Post-process to add template coordinates
        if result.get("required_attachments"):
            # We need file bytes for coordinate extraction
            # Re-download files for this (or cache from parent call)
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix="rfp_template_")

            try:
                files_data = self._download_files(files, temp_dir)
                result["required_attachments"] = self.extract_template_coordinates(
                    result["required_attachments"],
                    files_data
                )
            except Exception as e:
                print(f"Template coordinate extraction failed: {e}")
            finally:
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass

        return result


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
