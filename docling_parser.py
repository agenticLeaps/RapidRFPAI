"""
Docling parsing client - replacement for LlamaParse.
Communicates with parsing.rapidrfp.ai for document parsing.
Native handling for CSV/XLSX spreadsheets.
"""

import os
import httpx
import tempfile
import subprocess
import pandas as pd
from typing import Dict, Any, List
from text_chunker import SimpleDocument as Document

DOCLING_URL = os.getenv("DOCLING_SERVICE_URL", "https://parsing.rapidrfp.ai")

# Strict format allowlist
ALLOWED_FORMATS = {'.pdf', '.docx', '.doc', '.pptx', '.ppt', '.txt', '.xlsx', '.xls', '.csv'}
PDF_CONVERTIBLE = {'.docx', '.doc', '.pptx', '.ppt'}
SPREADSHEET_FORMATS = {'.xlsx', '.xls', '.csv'}
DIRECT_PARSE_FORMATS = {'.pdf', '.txt'}


class UnsupportedFormatError(Exception):
    """Raised when file format is not in allowlist."""
    pass


def validate_format(file_path: str) -> str:
    """Validate file format is in allowlist. Returns extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ALLOWED_FORMATS:
        raise UnsupportedFormatError(
            f"Unsupported format: {ext}. Allowed: PDF, DOCX, PPTX, TXT, XLSX, CSV"
        )
    return ext


def convert_to_pdf(file_path: str) -> str:
    """Convert DOCX/PPTX to PDF using LibreOffice."""
    output_dir = tempfile.mkdtemp()
    cmd = [
        'soffice', '--headless', '--convert-to', 'pdf',
        '--outdir', output_dir, file_path
    ]
    subprocess.run(cmd, check=True, timeout=120)
    pdf_name = os.path.splitext(os.path.basename(file_path))[0] + '.pdf'
    return os.path.join(output_dir, pdf_name)


def parse_spreadsheet(file_path: str) -> Dict[str, Any]:
    """Parse CSV/XLSX with native sheet extraction."""
    ext = os.path.splitext(file_path)[1].lower()
    filename = os.path.basename(file_path)
    documents = []

    if ext == '.csv':
        df = pd.read_csv(file_path)
        text = f"# Sheet: {filename}\n\n"
        text += df.to_markdown(index=False)
        documents.append(Document(
            text=text,
            metadata={"filename": filename, "sheet_name": "Sheet1", "source": file_path}
        ))
        page_count = 1

    else:  # xlsx/xls
        xlsx = pd.ExcelFile(file_path)
        sheet_names = xlsx.sheet_names
        for sheet_name in sheet_names:
            df = pd.read_excel(xlsx, sheet_name=sheet_name)
            text = f"# Sheet: {sheet_name}\n\n"
            text += df.to_markdown(index=False)
            documents.append(Document(
                text=text,
                metadata={"filename": filename, "sheet_name": sheet_name, "source": file_path}
            ))
        page_count = len(sheet_names)

    return {
        "documents": documents,
        "page_count": page_count,
        "document_count": len(documents)
    }


def parse_text_file(file_path: str) -> Dict[str, Any]:
    """Parse plain text files."""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    filename = os.path.basename(file_path)
    documents = [Document(
        text=content,
        metadata={"filename": filename, "source": file_path}
    )]

    return {
        "documents": documents,
        "page_count": 1,
        "document_count": 1
    }


def parse_with_docling(pdf_path: str, original_filename: str) -> Dict[str, Any]:
    """Send PDF to Docling service for parsing."""
    with open(pdf_path, 'rb') as f:
        files = {"files": (os.path.basename(pdf_path), f, "application/pdf")}
        data = {"to_formats": ["json", "md"]}

        response = httpx.post(
            f"{DOCLING_URL}/v1/convert/file",
            files=files,
            data=data,
            timeout=None  # No timeout - processing can take long for large documents
        )
        response.raise_for_status()

    result = response.json()
    doc_data = result.get("document", {})
    json_content = doc_data.get("json_content", {})
    md_content = doc_data.get("md_content", "")

    # Extract page count from pages dict
    pages = json_content.get("pages", {})
    page_count = len(pages) if pages else 1

    # Create document with markdown content
    documents = []
    if md_content:
        documents.append(Document(
            text=md_content,
            metadata={
                "filename": original_filename,
                "page_count": page_count,
                "source": pdf_path
            }
        ))

    return {
        "documents": documents,
        "page_count": page_count,
        "document_count": len(documents)
    }


def parse_document_with_docling(file_path: str, api_key: str = None) -> Dict[str, Any]:
    """
    Parse document using Docling service.
    Returns same structure as LlamaParse for compatibility.

    Supported formats: PDF, DOCX, PPTX, TXT, XLSX, CSV
    Raises UnsupportedFormatError for other formats.

    Args:
        file_path: Path to the document file
        api_key: Unused, kept for compatibility with LlamaParse signature

    Returns:
        Dict with keys: documents, page_count, document_count
    """
    # Validate format
    ext = validate_format(file_path)
    filename = os.path.basename(file_path)
    temp_pdf = None

    try:
        # Route based on format
        if ext in SPREADSHEET_FORMATS:
            # Native spreadsheet handling - no Docling
            print(f"📊 Parsing {filename} as spreadsheet (native)...")
            return parse_spreadsheet(file_path)

        elif ext == '.txt':
            # Direct text file reading
            print(f"📄 Parsing {filename} as text file...")
            return parse_text_file(file_path)

        elif ext in PDF_CONVERTIBLE:
            # Convert to PDF first
            print(f"🔄 Converting {filename} to PDF via LibreOffice...")
            temp_pdf = convert_to_pdf(file_path)
            print(f"📊 Parsing converted PDF with Docling...")
            result = parse_with_docling(temp_pdf, filename)

        else:  # .pdf
            print(f"📊 Parsing {filename} with Docling...")
            result = parse_with_docling(file_path, filename)

        return result

    finally:
        # Cleanup temp PDF
        if temp_pdf and os.path.exists(temp_pdf):
            os.remove(temp_pdf)
            temp_dir = os.path.dirname(temp_pdf)
            if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)
