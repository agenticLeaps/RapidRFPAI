"""
Template Extractor - Extract templates from PDFs with coordinates
Uses PyMuPDF (fitz) for precise location and content extraction
"""

import io
import re
from typing import Dict, Any, List, Optional, Tuple

# PyMuPDF availability
FITZ_AVAILABLE = False
try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    print("PyMuPDF not installed. Template coordinate extraction will be unavailable.")


class TemplateExtractor:
    """Extract templates from PDFs with coordinates and content"""

    # Common form field patterns
    FIELD_PATTERNS = [
        r'_{3,}',                    # Underscores: ___________
        r'\[[\s\.]*\]',              # Brackets: [ ] or [...]
        r'\(\s*\)',                  # Parentheses: ( )
        r'☐|☑|□|▢',                  # Checkboxes
        r'<[^>]+>',                  # Placeholders: <Company Name>
        r'\{[^}]+\}',                # Curly braces: {Enter Value}
    ]

    def __init__(self):
        self.field_pattern = re.compile('|'.join(self.FIELD_PATTERNS))

    def extract_template_from_pdf(
        self,
        pdf_bytes: bytes,
        template_hints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract template region from PDF using AI-provided hints

        Args:
            pdf_bytes: PDF file content
            template_hints: Dict with keys:
                - start_marker: Text marking start of template
                - end_marker: Text marking end of template (optional)
                - template_type: "form", "table", "certificate", etc.
                - source_section: Section reference (e.g., "Appendix B")

        Returns:
            Dict with template_content, template_location, and extracted data
        """
        if not FITZ_AVAILABLE:
            return {
                "success": False,
                "error": "PyMuPDF not available",
                "template_content": None,
                "template_location": None
            }

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            start_marker = template_hints.get("start_marker", "")
            end_marker = template_hints.get("end_marker", "")
            template_type = template_hints.get("template_type", "form")

            # Find template region
            location = self._find_template_region(doc, start_marker, end_marker)

            if not location:
                # Fallback: search by section reference
                section_ref = template_hints.get("source_section", "")
                if section_ref:
                    location = self._find_by_section(doc, section_ref)

            if not location:
                return {
                    "success": False,
                    "error": "Could not locate template in document",
                    "template_content": None,
                    "template_location": None
                }

            # Extract content based on template type
            page = doc[location["page_number"] - 1]
            bbox = fitz.Rect(location["bbox"]) if location.get("bbox") else page.rect

            if template_type == "table":
                content = self._extract_table_content(page, bbox)
            elif template_type in ["form", "certificate"]:
                content = self._extract_form_content(page, bbox)
            else:
                content = self._extract_text_content(page, bbox)

            doc.close()

            return {
                "success": True,
                "template_content": content,
                "template_location": location
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "template_content": None,
                "template_location": None
            }

    def _find_template_region(
        self,
        doc: 'fitz.Document',
        start_marker: str,
        end_marker: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Find template region by start/end markers"""
        if not start_marker:
            return None

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Search for start marker
            start_rects = page.search_for(start_marker)
            if not start_rects:
                continue

            start_rect = start_rects[0]

            # If end marker provided, search for it
            if end_marker:
                end_rects = page.search_for(end_marker)
                if end_rects:
                    end_rect = end_rects[-1]  # Use last occurrence
                    # Create bounding box from start to end
                    bbox = [
                        start_rect.x0,
                        start_rect.y0,
                        max(end_rect.x1, start_rect.x1),
                        end_rect.y1
                    ]
                else:
                    # No end marker found, use rest of page
                    bbox = [
                        start_rect.x0,
                        start_rect.y0,
                        page.rect.width,
                        page.rect.height
                    ]
            else:
                # No end marker, capture from start to end of page
                bbox = [
                    0,  # Full width
                    start_rect.y0,
                    page.rect.width,
                    page.rect.height
                ]

            return {
                "source_file": None,  # Will be set by caller
                "page_number": page_num + 1,
                "bbox": bbox,
                "page_width": page.rect.width,
                "page_height": page.rect.height
            }

        return None

    def _find_by_section(
        self,
        doc: 'fitz.Document',
        section_ref: str
    ) -> Optional[Dict[str, Any]]:
        """Find template region by section reference (e.g., 'Appendix B')"""
        # Common section patterns
        patterns = [
            section_ref,
            section_ref.upper(),
            section_ref.replace("Appendix", "APPENDIX"),
            section_ref.replace("Section", "SECTION"),
        ]

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()

            for pattern in patterns:
                if pattern in text:
                    rects = page.search_for(pattern)
                    if rects:
                        start_rect = rects[0]
                        return {
                            "source_file": None,
                            "page_number": page_num + 1,
                            "bbox": [
                                0,
                                start_rect.y0,
                                page.rect.width,
                                page.rect.height
                            ],
                            "page_width": page.rect.width,
                            "page_height": page.rect.height
                        }

        return None

    def _extract_table_content(
        self,
        page: 'fitz.Page',
        bbox: 'fitz.Rect'
    ) -> Dict[str, Any]:
        """Extract table structure from page region"""
        # Use PyMuPDF's table detection
        tables = page.find_tables(clip=bbox)

        if not tables:
            # Fallback to text extraction
            return self._extract_text_content(page, bbox)

        extracted_tables = []
        for table in tables:
            table_data = table.extract()
            if table_data:
                headers = table_data[0] if table_data else []
                rows = table_data[1:] if len(table_data) > 1 else []

                extracted_tables.append({
                    "headers": headers,
                    "rows": rows,
                    "row_count": len(rows),
                    "col_count": len(headers)
                })

        return {
            "type": "table",
            "tables": extracted_tables,
            "headers": extracted_tables[0]["headers"] if extracted_tables else [],
            "rows": extracted_tables[0]["rows"] if extracted_tables else [],
            "raw_text": page.get_text(clip=bbox)
        }

    def _extract_form_content(
        self,
        page: 'fitz.Page',
        bbox: 'fitz.Rect'
    ) -> Dict[str, Any]:
        """Extract form fields from page region"""
        text = page.get_text(clip=bbox)
        lines = text.split('\n')

        fields = []
        current_label = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line contains form field patterns
            has_field = bool(self.field_pattern.search(line))

            if has_field:
                # Extract label (text before the field pattern)
                label_match = re.split(r'[_\[\(\{<☐☑□▢]', line)
                label = label_match[0].strip().rstrip(':') if label_match else line

                # Determine field type
                field_type = self._classify_field(line)

                fields.append({
                    "name": label or current_label,
                    "type": field_type,
                    "required": self._is_required_field(line),
                    "original_line": line
                })
                current_label = ""
            else:
                # This might be a label for the next field
                if line.endswith(':'):
                    current_label = line.rstrip(':')
                elif not fields:
                    current_label = line

        return {
            "type": "form_fields",
            "fields": fields,
            "field_count": len(fields),
            "raw_text": text
        }

    def _extract_text_content(
        self,
        page: 'fitz.Page',
        bbox: 'fitz.Rect'
    ) -> Dict[str, Any]:
        """Extract plain text content from page region"""
        text = page.get_text(clip=bbox)

        return {
            "type": "text_block",
            "raw_text": text,
            "line_count": len(text.split('\n')),
            "char_count": len(text)
        }

    def _classify_field(self, line: str) -> str:
        """Classify the type of form field"""
        if re.search(r'☐|☑|□|▢', line):
            return "checkbox"
        if re.search(r'_{10,}', line):
            return "long_text"
        if re.search(r'_{3,9}', line):
            return "short_text"
        if re.search(r'date|Date|DATE', line, re.IGNORECASE):
            return "date"
        if re.search(r'signature|Signature|SIGNATURE', line, re.IGNORECASE):
            return "signature"
        if re.search(r'\[[\s\.]*\]|\(\s*\)', line):
            return "text"
        return "text"

    def _is_required_field(self, line: str) -> bool:
        """Determine if a field appears to be required"""
        required_indicators = [
            r'\*',
            r'required',
            r'Required',
            r'REQUIRED',
            r'mandatory',
            r'must',
        ]
        return any(re.search(p, line) for p in required_indicators)

    def extract_full_context(
        self,
        pdf_bytes: bytes,
        section_marker: str,
        max_chars: int = 5000
    ) -> str:
        """
        Extract full context text around a section marker

        Args:
            pdf_bytes: PDF file content
            section_marker: Text to search for
            max_chars: Maximum characters to extract

        Returns:
            Full context text
        """
        if not FITZ_AVAILABLE:
            return ""

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            full_text = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()

                if section_marker in text:
                    # Found the section - extract surrounding context
                    idx = text.find(section_marker)
                    start = max(0, idx - 500)  # 500 chars before
                    end = min(len(text), idx + max_chars - 500)  # Rest after

                    context = text[start:end]
                    full_text.append(context)

                    # Check if we need to continue to next page
                    remaining = max_chars - len(context)
                    if remaining > 0 and page_num + 1 < len(doc):
                        next_page = doc[page_num + 1]
                        next_text = next_page.get_text()[:remaining]
                        full_text.append(next_text)

                    break

            doc.close()
            return '\n'.join(full_text)[:max_chars]

        except Exception as e:
            print(f"Error extracting context: {e}")
            return ""


# Singleton instance
template_extractor = TemplateExtractor()
