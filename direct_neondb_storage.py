#!/usr/bin/env python3
"""
Direct NeonDB storage - using Docling for parsing, simple chunker for text splitting
Uses AWS Bedrock Cohere embeddings (1024 dimensions)
No LlamaIndex dependencies.
"""
import os
import asyncpg
import asyncio
import uuid
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
import ssl
import urllib3
import certifi

# Import Bedrock Cohere embeddings
try:
    from bedrock_client import cohere_embeddings, BEDROCK_AVAILABLE
except ImportError:
    BEDROCK_AVAILABLE = False
    cohere_embeddings = None
    print("Warning: Bedrock client not available for direct NeonDB storage")

# Import simple text chunker (replacement for LlamaIndex SentenceSplitter)
from text_chunker import chunk_text, SimpleDocument

# SSL Certificate fix
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['CURL_CA_BUNDLE'] = certifi.where()

load_dotenv()


def get_embeddings_from_cohere(texts: List[str]) -> List[List[float]]:
    """Get embeddings for multiple texts using Bedrock Cohere"""
    if not BEDROCK_AVAILABLE or not cohere_embeddings:
        raise RuntimeError("Bedrock Cohere embeddings not available")
    return cohere_embeddings.get_embeddings(texts, input_type="search_document")


class DirectNeonDBStorage:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL not found")

    async def store_embeddings_directly(self, chunks: List[str], file_id: str, org_id: str, user_id: str, filename: str) -> Dict[str, Any]:
        """Store embeddings directly in NeonDB"""
        print(f"Direct storage: {len(chunks)} chunks for file {file_id}")

        # Get embeddings for all chunks using Bedrock Cohere
        print("Getting embeddings from Bedrock Cohere...")
        embeddings = get_embeddings_from_cohere(chunks)
        print(f"Got {len(embeddings)} embeddings")

        # Connect to database
        conn = await asyncpg.connect(self.db_url)

        try:
            stored_count = 0
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                node_id = f"{file_id}_chunk_{i}_{uuid.uuid4().hex[:8]}"

                # Create metadata with additional fields
                metadata = {
                    "org_id": org_id,
                    "user_id": user_id,
                    "filename": filename,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "file_id": file_id
                }

                # Convert embedding list to pgvector format
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'

                # Insert directly into database
                await conn.execute("""
                    INSERT INTO llamaindex_embeddings (
                        node_id, text, embedding, file_id, org_id, chunk_index, metadata, created_at
                    ) VALUES ($1, $2, $3::vector, $4, $5, $6, $7::jsonb, NOW())
                """, node_id, chunk, embedding_str, file_id, org_id, i, json.dumps(metadata))

                stored_count += 1
                if i % 10 == 0:  # Log every 10 chunks
                    print(f"Stored chunk {i+1}/{len(chunks)}")

            print(f"Successfully stored {stored_count} embeddings directly in NeonDB")

            # Verify storage
            count = await conn.fetchval("SELECT COUNT(*) FROM llamaindex_embeddings WHERE file_id = $1", file_id)
            print(f"Verification: {count} records found for file_id {file_id}")

            return {
                "success": True,
                "chunks_stored": stored_count,
                "file_id": file_id,
                "method": "direct_neondb_storage"
            }

        except Exception as e:
            print(f"Direct storage error: {str(e)}")
            raise
        finally:
            await conn.close()


async def store_project_support_embeddings(chunks: List[str], file_id: str, org_id: str, user_id: str, project_id: str, filename: str) -> Dict[str, Any]:
    """Store embeddings in project_support_embeddings table with project_id"""
    print(f"Storing project support embeddings: {len(chunks)} chunks for project {project_id}")

    # Get embeddings for all chunks using Bedrock Cohere
    print("Getting embeddings from Bedrock Cohere...")
    embeddings = get_embeddings_from_cohere(chunks)
    print(f"Got {len(embeddings)} embeddings")

    # Connect to database
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not found")

    conn = await asyncpg.connect(db_url)

    try:
        # Create table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS project_support_embeddings (
                id SERIAL PRIMARY KEY,
                node_id TEXT UNIQUE NOT NULL,
                text TEXT NOT NULL,
                embedding vector(1024),
                file_id TEXT NOT NULL,
                org_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                user_id TEXT,
                chunk_index INTEGER,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Create indexes for better query performance
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_support_org_id ON project_support_embeddings(org_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_support_project_id ON project_support_embeddings(project_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_support_file_id ON project_support_embeddings(file_id)
        """)

        stored_count = 0
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            node_id = f"project_{project_id}_file_{file_id}_chunk_{i}_{uuid.uuid4().hex[:8]}"

            # Create metadata with project info
            metadata = {
                "org_id": org_id,
                "user_id": user_id,
                "project_id": project_id,
                "filename": filename,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "file_id": file_id,
                "document_type": "project_support"
            }

            # Convert embedding list to pgvector format
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'

            # Insert into project support table
            await conn.execute("""
                INSERT INTO project_support_embeddings (
                    node_id, text, embedding, file_id, org_id, project_id, user_id, chunk_index, metadata, created_at
                ) VALUES ($1, $2, $3::vector, $4, $5, $6, $7, $8, $9::jsonb, NOW())
            """, node_id, chunk, embedding_str, file_id, org_id, project_id, user_id, i, json.dumps(metadata))

            stored_count += 1
            if i % 10 == 0:
                print(f"Stored project chunk {i+1}/{len(chunks)}")

        print(f"Successfully stored {stored_count} project support embeddings in NeonDB")

        # Verify storage
        count = await conn.fetchval("SELECT COUNT(*) FROM project_support_embeddings WHERE file_id = $1 AND project_id = $2", file_id, project_id)
        print(f"Verification: {count} records found for file_id {file_id} in project {project_id}")

        return {
            "success": True,
            "chunks_stored": stored_count,
            "file_id": file_id,
            "project_id": project_id,
            "method": "direct_project_support_storage"
        }

    except Exception as e:
        print(f"Project support storage error: {str(e)}")
        raise
    finally:
        await conn.close()


def process_file_direct_storage_project_support(file_path: str, file_id: str, org_id: str, user_id: str, project_id: str, filename: str) -> Dict[str, Any]:
    """Process file for project support using Docling + direct storage approach"""
    print(f"Project Support Processing: {filename}")
    print(f"Project: {project_id}, Org: {org_id}, File: {file_id}")

    try:
        # Use Docling parser for document parsing
        from docling_parser import parse_document_with_docling, UnsupportedFormatError

        try:
            print(f"Parsing {filename} with Docling...")
            parse_result = parse_document_with_docling(file_path=file_path)

            documents = parse_result.get("documents", [])
            page_count = parse_result.get("page_count")

            print(f"Docling loaded {len(documents)} document(s)")
            if page_count:
                print(f"Total pages parsed: {page_count}")

        except UnsupportedFormatError as e:
            print(f"Unsupported format: {str(e)}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            print(f"Docling parsing failed: {str(e)}")
            # Fallback to simple text reading
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                except:
                    return {"success": False, "error": f"Cannot read file: {filename}"}

            documents = [SimpleDocument(text=content, metadata={"filename": filename})]
            print(f"Created document from simple text reading")

        if not documents:
            return {"success": False, "error": "No content extracted from document"}

        # Extract text from documents and chunk
        all_text = " ".join([doc.text for doc in documents])
        print(f"Chunking text ({len(all_text)} chars)...")

        chunks = chunk_text(all_text)
        print(f"Created {len(chunks)} chunks")

        if not chunks:
            return {"success": False, "error": "No chunks created from document"}

        # Store in project support table
        result = asyncio.run(store_project_support_embeddings(
            chunks=chunks,
            file_id=file_id,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            filename=filename
        ))

        return result

    except Exception as e:
        print(f"Project Support processing error: {str(e)}")
        return {"success": False, "error": str(e)}


def process_file_direct_storage(file_path: str, file_id: str, org_id: str, user_id: str, filename: str) -> Dict[str, Any]:
    """Process file using Docling + direct storage method"""
    print(f"Direct processing with Docling: {filename}")

    # Get file extension to determine processing method
    file_ext = filename.split('.')[-1].lower()
    page_count = None

    # Use Docling parser for all supported formats
    from docling_parser import parse_document_with_docling, UnsupportedFormatError

    try:
        print(f"Parsing {filename} with Docling...")
        parse_result = parse_document_with_docling(file_path=file_path)

        documents = parse_result.get("documents", [])
        page_count = parse_result.get("page_count")

        print(f"Docling completed successfully")
        print(f"Docling loaded {len(documents)} document(s)")
        if page_count:
            print(f"Total pages parsed: {page_count}")

        if documents:
            print(f"First document preview: {documents[0].text[:200]}...")

    except UnsupportedFormatError as e:
        print(f"Unsupported format: {str(e)}")
        return None
    except Exception as e:
        print(f"Docling parsing failed: {str(e)}")
        return None

    if not documents:
        print(f"No documents extracted from {filename}")
        return None

    # Add metadata to documents
    for doc in documents:
        doc.metadata.update({
            "file_id": file_id,
            "org_id": org_id,
            "user_id": user_id,
            "filename": filename,
            "file_extension": file_ext
        })

    # Chunk text using simple chunker (replacement for LlamaIndex SentenceSplitter)
    print(f"Parsing documents into chunks...")
    all_text = " ".join([doc.text for doc in documents])
    chunks = chunk_text(all_text)
    print(f"Created {len(chunks)} chunks")

    if chunks:
        print(f"First chunk preview: {chunks[0][:200]}...")

    # Store directly
    storage = DirectNeonDBStorage()
    result = asyncio.run(storage.store_embeddings_directly(chunks, file_id, org_id, user_id, filename))

    # Add page count to result
    if page_count is not None:
        result["page_count"] = page_count
        print(f"Adding page count to result: {page_count} pages")

    return result
