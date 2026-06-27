import os
import argparse
import hashlib
import uuid
import logging
from typing import List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import KnowledgeSource, Document, Embedding
from shared_memory.qdrant import QdrantManager
from shared_memory.rag import ParentChildChunker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shared-memory.ingest")

def generate_mock_embedding(text: str, size: int = 1536) -> List[float]:
    """
    Generates a deterministic float vector based on the text hash.
    Used for offline testing and local sandboxes.
    """
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vector = []
    for i in range(size):
        byte_val = h[i % len(h)]
        vector.append(float(byte_val) / 255.0 - 0.5)
    return vector

def ingest_markdown_files(
    docs_dir: str,
    db_url: str,
    qdrant_url: Optional[str] = None,
    tech_tag: str = "general"
):
    # 1. Initialize DB Session
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 2. Initialize Qdrant Client
    qdrant_mgr = QdrantManager(url=qdrant_url)
    collection_name = "tech_documentation"
    
    # Run async collection creation blocking
    import asyncio
    asyncio.run(qdrant_mgr.create_collection_if_not_exists(collection_name))

    # 3. Create or fetch Knowledge Source
    source_name = f"{tech_tag}-documentation"
    source = session.query(KnowledgeSource).filter_by(tech_tag=tech_tag).first()
    if not source:
        source = KnowledgeSource(
            name=source_name,
            url=docs_dir,
            tech_tag=tech_tag
        )
        session.add(source)
        session.commit()
        session.refresh(source)

    logger.info(f"Ingesting docs from {docs_dir} into Knowledge Source {source.source_id}")

    # 4. Search and read markdown files
    for root, _, files in os.walk(docs_dir):
        for file in files:
            if not file.endswith(".md"):
                continue
                
            file_path = os.path.join(root, file)
            logger.info(f"Processing: {file}")
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            file_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            
            # Check if document already exists matching tag/hash
            existing_doc = session.query(Document).filter_by(hash=file_hash, source_id=source.source_id).first()
            if existing_doc:
                logger.info(f"Document {file} already ingested (matching hash). Skipping.")
                continue

            # Create Document row
            doc = Document(
                source_id=source.source_id,
                title=file,
                content_path=file_path,
                hash=file_hash
            )
            session.add(doc)
            session.commit()
            session.refresh(doc)

            # 5. Chunk the text
            chunks = ParentChildChunker.chunk_document(content)
            logger.info(f"Generated {len(chunks)} child chunks for doc: {file}")

            # 6. Embed and upsert to Qdrant & DB
            points = []
            for chunk in chunks:
                vector_id = uuid.uuid4()
                # Generate mock embedding for offline sandbox capability
                embedding_vector = generate_mock_embedding(chunk["child_text"])
                
                # Save Embedding reference in database
                emb = Embedding(
                    document_id=doc.document_id,
                    vector_id=vector_id,
                    chunk_index=chunk["chunk_index"],
                    metadata_json={
                        "child_text": chunk["child_text"],
                        "parent_text": chunk["parent_text"],
                        "parent_id": str(chunk["parent_id"]),
                        "tech_tag": tech_tag
                    }
                )
                session.add(emb)
                
                # Prepare Qdrant upsert
                points.append({
                    "id": vector_id,
                    "vector": embedding_vector,
                    "payload": {
                        "document_id": str(doc.document_id),
                        "title": doc.title,
                        "tech_tag": tech_tag,
                        "child_text": chunk["child_text"],
                        "parent_text": chunk["parent_text"],
                        "parent_id": str(chunk["parent_id"])
                    }
                })

            session.commit()
            
            # Perform batch upsert to Qdrant index
            qdrant_mgr.upsert_vectors(collection_name, points)
            logger.info(f"Successfully indexed document {file}")

    session.close()
    logger.info("Ingestion finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest markdown documentation into Qdrant & SQL DB.")
    parser.add_argument("--dir", required=True, help="Directory containing markdown files")
    parser.add_argument("--db-url", required=True, help="SQL Database connection URL")
    parser.add_argument("--qdrant-url", help="Qdrant API URL")
    parser.add_argument("--tag", default="general", help="Tech stack identifier tag (e.g. fastapi)")
    
    args = parser.parse_args()
    ingest_markdown_files(
        docs_dir=args.dir,
        db_url=args.db_url,
        qdrant_url=args.qdrant_url,
        tech_tag=args.tag
    )
