"""
Document Shredding Service for V3 Project Creation
Extracts metadata and submission requirements from RFP documents using Gemini
"""

import os
import json
import tempfile
from typing import List, Dict, Any, Optional
from datetime import datetime
from google.cloud import storage
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel, Part, SafetySetting


# Initialize GCS client with proper credential handling
def get_gcs_client():
    """Get GCS client with proper credential handling"""
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "fire.json")

    if cred_path.startswith("{"):
        # JSON string from environment - parse and use credentials
        cred_dict = json.loads(cred_path)
        credentials = service_account.Credentials.from_service_account_info(cred_dict)
        client = storage.Client(credentials=credentials, project=os.environ.get("GOOGLE_CLOUD_PROJECT"))
        print("✅ Using environment credentials for GCS bucket access")
    else:
        # Fallback to file path or default credentials
        if os.path.exists(cred_path):
            credentials = service_account.Credentials.from_service_account_file(cred_path)
            client = storage.Client(credentials=credentials)
            print(f"✅ Using credentials from {cred_path}")
        else:
            client = storage.Client()
            print("✅ Using default credentials for GCS bucket access")

    return client


def download_file_from_gcs(gcs_url: str, temp_dir: str) -> tuple[str, str]:
    """
    Download a file from Google Cloud Storage to a temporary directory

    Args:
        gcs_url: GCS URL (gs://bucket/path/to/file)
        temp_dir: Temporary directory to save the file

    Returns:
        Tuple of (local_file_path, filename)
    """
    if not gcs_url.startswith('gs://'):
        raise ValueError(f"Invalid GCS URL: {gcs_url}")

    # Parse GCS URL
    parts = gcs_url.replace('gs://', '').split('/', 1)
    bucket_name = parts[0]
    file_path = parts[1] if len(parts) > 1 else ''

    # Download file using GCS client
    gcs_client = get_gcs_client()
    bucket = gcs_client.bucket(bucket_name)
    blob = bucket.blob(file_path)

    filename = os.path.basename(file_path)
    local_path = os.path.join(temp_dir, filename)

    blob.download_to_filename(local_path)
    print(f"✅ Downloaded {filename} to {local_path}")

    return local_path, filename


def prepare_gemini_prompt() -> str:
    """
    Prepare the prompt for Gemini document analysis

    Returns:
        Formatted prompt string
    """

    prompt = """You are a specialized RFP Analyst. Your task is to extract structured metadata and submission requirements from the provided RFP documents to initialize a project workspace.

INSTRUCTIONS:
1. **Metadata Extraction**: Carefully identify:
   - Project Name: Look for titles like "Request for Proposal for...", "RFP Title:", "Project:", or document headers
   - Issuer Name: Organization, agency, or company issuing the RFP (look for headers, letterheads, contact information)
   - Due Date: Submission deadline, proposal due date, closing date (convert to ISO 8601 format YYYY-MM-DDTHH:MM:SSZ). Look for phrases like "Due Date:", "Deadline:", "Closing Date:", "Submit by:"

2. **Submission Requirements**: Extract ALL items that proposers must submit. Look for sections like:
   - "Submission Requirements", "Required Documents", "Proposal Components", "Deliverables", "What to Submit"
   - Forms (e.g., "Conflict of Interest Form", "Proposal Cover Sheet", "Budget Template", "Bid Form")
   - Documents (e.g., "Technical Proposal", "Financial Proposal", "Company Profile", "Executive Summary")
   - Certifications (e.g., "Insurance Certificate", "Business License", "Tax Clearance")
   - Attachments (e.g., "Work Samples", "References", "Resumes", "Past Performance")
   - Information to provide (e.g., "Project Timeline", "Pricing Structure", "Methodology")

3. **De-duplication**: If a requirement appears in multiple files/sections, create ONE entry with multiple mentions in the mentions array

4. **Naming**: Use clear, task-friendly names:
   - Good: "Submit Technical Proposal", "Provide Insurance Certificate", "Complete Budget Form"
   - Bad: "Technical Proposal Document Submission Requirements Section 4.1"

5. **Required vs Optional**:
   - Set is_required=true if document explicitly states "required", "mandatory", "must", "shall"
   - Set is_required=false if document states "optional", "if applicable", "may"

6. **Source Location**: Be specific about where you found the requirement:
   - Good: "Section 4.1 - Submission Requirements, Page 12"
   - Bad: "In the document"

7. **Confidence Score**:
   - "high": Clearly stated requirement with explicit details
   - "medium": Implied requirement or unclear details
   - null: If very uncertain

8. **Handle Multiple Documents**: If multiple documents are provided, analyze ALL of them and aggregate findings

EXAMPLE OUTPUT (this is what your response should look like):
{
  "project_metadata": {
    "project_name": "Cloud Infrastructure Services RFP",
    "issuer_name": "Department of Technology",
    "due_date": "2024-03-15T17:00:00Z"
  },
  "submission_requirements": [
    {
      "response_item_name": "Submit Technical Proposal",
      "description": "Detailed technical approach including methodology, timeline, and deliverables. Must not exceed 20 pages and include system architecture diagrams.",
      "is_required": true,
      "mentions": [
        {
          "source_file": "RFP_Main_Document.pdf",
          "source_location": "Section 4.1 - Submission Requirements, Page 12",
          "confidence_score": "high"
        }
      ]
    },
    {
      "response_item_name": "Provide Company Financial Statements",
      "description": "Audited financial statements for the past 3 years demonstrating financial stability and capacity to execute the project",
      "is_required": true,
      "mentions": [
        {
          "source_file": "RFP_Main_Document.pdf",
          "source_location": "Section 4.2 - Qualification Requirements, Page 15",
          "confidence_score": "high"
        },
        {
          "source_file": "Appendix_B.pdf",
          "source_location": "Page 2 - Required Documents Checklist, Item 7",
          "confidence_score": "high"
        }
      ]
    },
    {
      "response_item_name": "Complete Conflict of Interest Form",
      "description": "Mandatory disclosure form regarding potential conflicts of interest. Form template provided in Appendix C.",
      "is_required": true,
      "mentions": [
        {
          "source_file": "RFP_Main_Document.pdf",
          "source_location": "Section 5.3 - Required Forms, Page 22",
          "confidence_score": "high"
        }
      ]
    }
  ]
}

OUTPUT FORMAT: Return ONLY the JSON object. No markdown code blocks, no conversational text, just the raw JSON.

Now analyze the provided document(s) and extract the information according to these instructions."""

    return prompt


def call_gemini_for_shredding(files_data: List[tuple[bytes, str]]) -> Dict[str, Any]:
    """
    Call Gemini to extract metadata and submission requirements using multimodal capabilities

    Args:
        files_data: List of tuples (file_bytes, filename)

    Returns:
        Parsed JSON response from Gemini
    """
    try:
        # Initialize Gemini model
        model = GenerativeModel("gemini-2.0-flash")

        # Prepare parts for multimodal input
        parts = []

        # Add the prompt as the first part
        prompt = prepare_gemini_prompt()
        parts.append(Part.from_text(prompt))

        # Define MIME type mapping
        mime_mapping = {
            "pdf": "application/pdf",
            "txt": "text/plain",
            "csv": "text/csv",
            "json": "application/json",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp"
        }

        # Add each file as a multimodal part
        for file_bytes, filename in files_data:
            file_ext = os.path.splitext(filename)[1].lower().lstrip('.')
            mime_type = mime_mapping.get(file_ext, "application/octet-stream")

            # Add file part
            file_part = Part.from_data(data=file_bytes, mime_type=mime_type)
            parts.append(file_part)

            # Add a text separator with filename
            parts.append(Part.from_text(f"\n\n--- End of document: {filename} ---\n\n"))

            print(f"✅ Added {filename} to multimodal request ({mime_type}, {len(file_bytes)} bytes)")

        # Safety settings to prevent blocking
        safety_settings = [
            SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_NONE"
            ),
            SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_NONE"
            ),
            SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="BLOCK_NONE"
            ),
            SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="BLOCK_NONE"
            ),
        ]

        # Generation config for JSON output
        generation_config = {
            "temperature": 0.2,
            "max_output_tokens": 8192,
            "top_p": 0.8,
        }

        print(f"🤖 Sending request to Gemini for document shredding ({len(files_data)} files)...")

        # Call Gemini with multimodal parts
        response = model.generate_content(
            parts,
            generation_config=generation_config,
            safety_settings=safety_settings,
            stream=False
        )

        print(f"✅ Received response from Gemini")

        # Parse JSON response
        response_text = response.text.strip()
        print(f"📝 Raw response length: {len(response_text)} characters")

        # Clean up response if needed (remove markdown code blocks)
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        # Parse JSON
        result = json.loads(response_text)

        print(f"✅ Successfully parsed JSON response")

        return result

    except Exception as e:
        print(f"❌ Error calling Gemini: {e}")
        import traceback
        traceback.print_exc()
        raise


def shred_documents(files: List[Dict[str, str]], org_id: str) -> Dict[str, Any]:
    """
    Main function to shred RFP documents and extract metadata

    Args:
        files: List of file dictionaries with 'file_id', 'filename', 'gcs_url'
        org_id: Organization ID

    Returns:
        Dictionary with project_metadata and submission_requirements
    """

    print(f"📄 Starting document shredding for {len(files)} files...")

    # Create temporary directory for downloads
    temp_dir = tempfile.mkdtemp(prefix="rfp_shredding_")

    try:
        # Step 1: Download all files from GCS and read as bytes
        files_data = []

        for file_info in files:
            filename = file_info['filename']
            gcs_url = file_info['gcs_url']

            print(f"📥 Downloading {filename} from GCS...")

            try:
                local_path, _ = download_file_from_gcs(gcs_url, temp_dir)

                # Read file as bytes
                with open(local_path, 'rb') as f:
                    file_bytes = f.read()

                files_data.append((file_bytes, filename))
                print(f"✅ Prepared {filename} for multimodal upload ({len(file_bytes)} bytes)")

            except Exception as e:
                print(f"❌ Error processing {filename}: {e}")
                # Continue with other files
                continue

        if not files_data:
            raise Exception("No files could be processed")

        # Step 2: Call Gemini with all files using multimodal input
        result = call_gemini_for_shredding(files_data)

        # Step 3: Validate and return result
        if not result.get('project_metadata'):
            result['project_metadata'] = {
                'project_name': None,
                'issuer_name': None,
                'due_date': None
            }

        if not result.get('submission_requirements'):
            result['submission_requirements'] = []

        print(f"✅ Document shredding complete!")
        print(f"   - Project Name: {result['project_metadata'].get('project_name')}")
        print(f"   - Issuer: {result['project_metadata'].get('issuer_name')}")
        print(f"   - Due Date: {result['project_metadata'].get('due_date')}")
        print(f"   - Requirements Found: {len(result['submission_requirements'])}")

        return result

    finally:
        # Clean up temporary directory
        import shutil
        try:
            shutil.rmtree(temp_dir)
            print(f"🧹 Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            print(f"⚠️ Could not clean up temp directory: {e}")


def shred_documents_endpoint_handler(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flask endpoint handler for document shredding

    Args:
        request_data: Request JSON data with 'files' and 'org_id'

    Returns:
        Response dictionary
    """
    try:
        # Validate request
        files = request_data.get('files', [])
        org_id = request_data.get('org_id')

        if not files:
            return {
                'success': False,
                'error': 'No files provided'
            }, 400

        if not org_id:
            return {
                'success': False,
                'error': 'Organization ID is required'
            }, 400

        # Validate each file has required fields
        for file_info in files:
            if not all(key in file_info for key in ['file_id', 'filename', 'gcs_url']):
                return {
                    'success': False,
                    'error': 'Each file must have file_id, filename, and gcs_url'
                }, 400

        # Perform document shredding
        result = shred_documents(files, org_id)

        return {
            'success': True,
            'project_metadata': result['project_metadata'],
            'submission_requirements': result['submission_requirements']
        }, 200

    except Exception as e:
        print(f"❌ Error in document shredding endpoint: {e}")
        import traceback
        traceback.print_exc()

        return {
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }, 500
