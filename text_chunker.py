#!/usr/bin/env python3
"""
Simple text chunker - replacement for LlamaIndex SentenceSplitter
Uses sentence boundaries for natural text splitting
"""
import re
import os
from typing import List, Dict, Any


def chunk_text(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
    separator: str = " "
) -> List[str]:
    """
    Split text into chunks with overlap.

    Args:
        text: Input text to chunk
        chunk_size: Maximum characters per chunk (default from env or 1024)
        chunk_overlap: Overlap between chunks (default from env or 20)
        separator: Word separator

    Returns:
        List of text chunks
    """
    if not text or not text.strip():
        return []

    chunk_size = chunk_size or int(os.getenv("LLAMAINDEX_CHUNK_SIZE", "1024"))
    chunk_overlap = chunk_overlap or int(os.getenv("LLAMAINDEX_CHUNK_OVERLAP", "20"))

    # Split into sentences for more natural boundaries
    sentences = split_into_sentences(text)

    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        sentence_length = len(sentence)

        # If single sentence is too long, split it further
        if sentence_length > chunk_size:
            # Save current chunk if not empty
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                # Keep overlap
                overlap_text = " ".join(current_chunk)
                if len(overlap_text) > chunk_overlap:
                    overlap_words = overlap_text.split()[-chunk_overlap//5:]  # Approximate overlap
                    current_chunk = overlap_words
                    current_length = sum(len(w) + 1 for w in overlap_words)
                else:
                    current_chunk = []
                    current_length = 0

            # Split long sentence into smaller parts
            words = sentence.split()
            for word in words:
                word_length = len(word) + 1  # +1 for space

                if current_length + word_length > chunk_size and current_chunk:
                    chunks.append(" ".join(current_chunk))
                    # Keep overlap
                    overlap_words = current_chunk[-chunk_overlap//5:] if len(current_chunk) > chunk_overlap//5 else []
                    current_chunk = overlap_words + [word]
                    current_length = sum(len(w) + 1 for w in current_chunk)
                else:
                    current_chunk.append(word)
                    current_length += word_length
        else:
            # Check if adding sentence would exceed chunk size
            if current_length + sentence_length > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                # Keep overlap by retaining last few words
                overlap_text = " ".join(current_chunk)
                if len(overlap_text) > chunk_overlap:
                    overlap_words = overlap_text.split()[-chunk_overlap//5:]
                    current_chunk = overlap_words
                    current_length = sum(len(w) + 1 for w in overlap_words)
                else:
                    current_chunk = []
                    current_length = 0

            current_chunk.extend(sentence.split())
            current_length += sentence_length

    # Add remaining chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences using regex patterns.

    Args:
        text: Input text

    Returns:
        List of sentences
    """
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text.strip())

    # Split on sentence boundaries (. ! ? followed by space and capital letter)
    # Also handles common abbreviations
    sentence_endings = r'(?<=[.!?])\s+(?=[A-Z])'
    sentences = re.split(sentence_endings, text)

    # Filter empty sentences
    return [s.strip() for s in sentences if s.strip()]


def chunk_documents(
    documents: List[Dict[str, Any]],
    chunk_size: int = None,
    chunk_overlap: int = None
) -> List[Dict[str, Any]]:
    """
    Chunk multiple documents and preserve metadata.

    Args:
        documents: List of document dicts with 'text' and optional 'metadata' keys
        chunk_size: Maximum characters per chunk
        chunk_overlap: Overlap between chunks

    Returns:
        List of chunk dicts with text, metadata, and chunk_index
    """
    all_chunks = []

    for doc in documents:
        text = doc.get("text", "")
        metadata = doc.get("metadata", {})

        chunks = chunk_text(text, chunk_size, chunk_overlap)

        for i, chunk_text_content in enumerate(chunks):
            chunk_dict = {
                "text": chunk_text_content,
                "metadata": {
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
            }
            all_chunks.append(chunk_dict)

    return all_chunks


# Simple Document class replacement
class SimpleDocument:
    """Simple document class to replace LlamaIndex Document"""

    def __init__(self, text: str = "", metadata: Dict[str, Any] = None):
        self.text = text
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimpleDocument":
        return cls(
            text=data.get("text", ""),
            metadata=data.get("metadata", {})
        )


# Test function
if __name__ == "__main__":
    test_text = """
    This is a test document for the text chunker. It contains multiple sentences.
    The chunker should split this text into smaller pieces while maintaining sentence boundaries.
    Each chunk should have some overlap with the previous chunk for context continuity.
    This helps with retrieval and ensures no information is lost at chunk boundaries.
    """

    chunks = chunk_text(test_text, chunk_size=200, chunk_overlap=20)
    print(f"Created {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1} ({len(chunk)} chars):")
        print(chunk[:100] + "..." if len(chunk) > 100 else chunk)
