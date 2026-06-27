import re
import uuid
import logging
from typing import List, Dict, Any, Optional
from shared_memory.qdrant import QdrantManager

logger = logging.getLogger("shared-memory.rag")

class ParentChildChunker:
    @staticmethod
    def chunk_document(
        text: str,
        parent_max_chars: int = 8000,  # ~2000 words
        child_chunk_size: int = 1500,  # ~350 tokens
        child_overlap: int = 250       # ~60 tokens
    ) -> List[Dict[str, Any]]:
        """
        Splits a text document into parent chunks and child chunks with overlap.
        Returns a list of dicts describing the child chunks with links to parent chunks.
        Each child has:
          - "child_id": UUID
          - "parent_id": UUID
          - "parent_text": str (full context)
          - "child_text": str (specific passage)
        """
        # 1. Create parent chunks
        parent_chunks = []
        # Split by double newline or custom header to keep markdown structure
        paragraphs = text.split("\n\n")
        current_parent = []
        current_len = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if current_len + len(para) > parent_max_chars and current_parent:
                parent_chunks.append("\n\n".join(current_parent))
                current_parent = [para]
                current_len = len(para)
            else:
                current_parent.append(para)
                current_len += len(para) + 2
                
        if current_parent:
            parent_chunks.append("\n\n".join(current_parent))

        # 2. For each parent chunk, generate overlapping child chunks
        all_children = []
        for p_idx, p_text in enumerate(parent_chunks):
            parent_id = uuid.uuid4()
            
            # Simple character-level sliding window for children
            words = p_text.split()
            # Approx char conversions: child_chunk_size chars is roughly 250-300 words
            # Let's chunk by words instead of raw chars for better readability of child texts
            words_per_child = 300
            overlap_words = 50
            
            w_idx = 0
            while w_idx < len(words):
                child_words = words[w_idx : w_idx + words_per_child]
                child_text = " ".join(child_words)
                
                all_children.append({
                    "child_id": uuid.uuid4(),
                    "parent_id": parent_id,
                    "parent_text": p_text,
                    "child_text": child_text,
                    "chunk_index": len(all_children)
                })
                
                w_idx += (words_per_child - overlap_words)
                if w_idx >= len(words) or len(child_words) < words_per_child:
                    break

        return all_children

class HybridRetriever:
    def __init__(self, qdrant_mgr: QdrantManager, collection_name: str = "tech_documentation"):
        self.qdrant_mgr = qdrant_mgr
        self.collection_name = collection_name

    async def retrieve(
        self,
        query: str,
        query_vector: List[float],
        db_session: Any,  # SQLAlchemy AsyncSession
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Performs hybrid dense (Qdrant) and lexical (Postgres/SQLite) search,
        combines them using Reciprocal Rank Fusion (RRF), and returns top matches.
        """
        # 1. Dense Vector Lookup
        dense_results = self.qdrant_mgr.search_similarity(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=limit * 2
        )

        # 2. Lexical Lookup (Postgres/SQLite fallback)
        lexical_results = []
        try:
            # We search the database using standard SQL LIKE filter on Document title/content
            # Querying the `documents` table or `embeddings` metadata
            from sqlalchemy import select, or_
            from app.models import Document
            
            # Simple keyword extraction
            keywords = [w.lower() for w in re.findall(r'\w+', query) if len(w) > 3]
            if keywords:
                filters = []
                for kw in keywords:
                    filters.append(Document.title.ilike(f"%{kw}%"))
                
                sql_query = select(Document).filter(or_(*filters)).limit(limit * 2)
                res = await db_session.execute(sql_query)
                docs = res.scalars().all()
                for doc in docs:
                    lexical_results.append({
                        "id": str(doc.document_id),
                        "title": doc.title,
                        "content_path": doc.content_path
                    })
        except Exception as e:
            logger.warning(f"Lexical DB search skipped or failed: {e}")

        # 3. Combine results using Reciprocal Rank Fusion (RRF)
        # Score = Sum (1 / (constant + rank))
        rrf_scores = {}
        constant = 60
        
        # Rank dense
        for rank, item in enumerate(dense_results):
            doc_id = item["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (constant + rank + 1))
            
        # Rank lexical
        for rank, item in enumerate(lexical_results):
            doc_id = item["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (constant + rank + 1))

        # Sort by RRF score desc
        sorted_ids = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)[:limit]
        
        # Fetch the payloads/details for the top IDs
        final_results = []
        for doc_id in sorted_ids:
            # Match item in dense or lexical results
            matched = None
            for item in dense_results:
                if item["id"] == doc_id:
                    matched = item
                    break
            
            if matched:
                final_results.append({
                    "id": doc_id,
                    "score": rrf_scores[doc_id],
                    "payload": matched["payload"]
                })
            else:
                # Lexical only match
                for item in lexical_results:
                    if item["id"] == doc_id:
                        final_results.append({
                            "id": doc_id,
                            "score": rrf_scores[doc_id],
                            "payload": {
                                "title": item["title"],
                                "content_path": item["content_path"],
                                "child_text": "Content matched by keyword search."
                            }
                        })
                        break

        return final_results
