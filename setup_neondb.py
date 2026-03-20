#!/usr/bin/env python3
"""
Setup AWS RDS PostgreSQL with pgvector for embeddings
Uses Bedrock Cohere embeddings (1024 dimensions)
"""
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

load_dotenv()

def setup_rds_database():
    """Initialize AWS RDS PostgreSQL with pgvector extension and tables"""

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not found in environment")

    print("Setting up AWS RDS PostgreSQL with pgvector...")

    try:
        # Connect to database
        conn = psycopg2.connect(db_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Enable pgvector extension
        print("Enabling pgvector extension...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # Drop existing table if it exists (to handle dimension changes)
        print("Dropping existing llamaindex_embeddings table if it exists...")
        cursor.execute("DROP TABLE IF EXISTS llamaindex_embeddings CASCADE;")

        # Create embeddings table with 1024 dimensions (Cohere)
        print("Creating llamaindex_embeddings table (1024 dimensions)...")
        cursor.execute("""
            CREATE TABLE llamaindex_embeddings (
                id SERIAL PRIMARY KEY,
                node_id VARCHAR(255) UNIQUE NOT NULL,
                text TEXT NOT NULL,
                metadata JSONB,
                embedding vector(1024),
                org_id VARCHAR(255),
                file_id VARCHAR(255),
                chunk_index INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create indexes for better performance
        print("Creating indexes...")

        # Vector similarity index (1024 dimensions works with ivfflat)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_embeddings_vector
            ON llamaindex_embeddings USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_org_file
            ON llamaindex_embeddings (org_id, file_id);
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metadata
            ON llamaindex_embeddings USING gin (metadata);
        """)

        # Create project_support_embeddings table
        print("Creating project_support_embeddings table (1024 dimensions)...")
        cursor.execute("DROP TABLE IF EXISTS project_support_embeddings CASCADE;")
        cursor.execute("""
            CREATE TABLE project_support_embeddings (
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
            );
        """)

        # Create indexes for project_support table
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_support_vector
            ON project_support_embeddings USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_support_org_id ON project_support_embeddings(org_id);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_support_project_id ON project_support_embeddings(project_id);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_support_file_id ON project_support_embeddings(file_id);
        """)

        # Create noderag_embeddings table for NodeRAG pipeline embeddings
        print("Creating noderag_embeddings table (1024 dimensions)...")
        cursor.execute("DROP TABLE IF EXISTS noderag_embeddings CASCADE;")
        cursor.execute("""
            CREATE TABLE noderag_embeddings (
                id SERIAL PRIMARY KEY,
                node_id TEXT UNIQUE NOT NULL,
                node_type TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding vector(1024),
                file_id TEXT NOT NULL,
                org_id TEXT NOT NULL,
                user_id TEXT,
                chunk_index INTEGER,
                graph_metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # Create indexes for noderag_embeddings table
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_noderag_vector
            ON noderag_embeddings USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_noderag_org_id ON noderag_embeddings(org_id);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_noderag_file_id ON noderag_embeddings(file_id);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_noderag_node_type ON noderag_embeddings(node_type);
        """)

        print("AWS RDS setup complete!")
        print("Vector dimension: 1024 (Bedrock Cohere)")
        print("Tables: llamaindex_embeddings, project_support_embeddings, noderag_embeddings")
        print("Indexes: vector similarity (ivfflat), org/file, metadata")

        # Test the setup
        cursor.execute("SELECT COUNT(*) FROM llamaindex_embeddings;")
        count = cursor.fetchone()[0]
        print(f"llamaindex_embeddings count: {count}")

        cursor.execute("SELECT COUNT(*) FROM project_support_embeddings;")
        count = cursor.fetchone()[0]
        print(f"project_support_embeddings count: {count}")

        cursor.execute("SELECT COUNT(*) FROM noderag_embeddings;")
        count = cursor.fetchone()[0]
        print(f"noderag_embeddings count: {count}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Setup failed: {e}")
        raise

if __name__ == "__main__":
    setup_rds_database()