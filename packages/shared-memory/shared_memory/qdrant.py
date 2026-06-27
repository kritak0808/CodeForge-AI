import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

logger = logging.getLogger("shared-memory.qdrant")

class QdrantManager:
    def __init__(self, url: Optional[str] = None, host: Optional[str] = None, port: Optional[int] = None, api_key: Optional[str] = None):
        """
        Initializes the Qdrant client. If no url/host is provided, falls back to in-memory mode
        which is ideal for unit tests and local sandboxes.
        """
        if not url and not host:
            logger.info("Initializing in-memory Qdrant client for local testing.")
            self.client = QdrantClient(":memory:")
        else:
            logger.info(f"Initializing Qdrant client with host={host or url}")
            self.client = QdrantClient(
                url=url,
                host=host,
                port=port,
                api_key=api_key
            )

    async def create_collection_if_not_exists(self, collection_name: str, vector_size: int = 1536) -> bool:
        """
        Creates a Qdrant collection configured with Cosine similarity and HNSW index if it does not already exist.
        """
        try:
            # Check if exists
            collections = self.client.get_collections()
            exist = any(c.name == collection_name for c in collections.collections)
            if exist:
                logger.debug(f"Collection '{collection_name}' already exists.")
                return False

            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100
                )
            )
            logger.info(f"Created Qdrant collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            raise

    def upsert_vectors(self, collection_name: str, points: List[Dict[str, Any]]) -> None:
        """
        Upserts a batch of points (vectors and payloads) into Qdrant.
        Each point dict should contain:
          - "id": UUID or string or int identifier
          - "vector": List[float] embedding values
          - "payload": Dict[str, Any] metadata fields
        """
        qdrant_points = []
        for p in points:
            pt_id = p["id"]
            if isinstance(pt_id, UUID):
                pt_id = str(pt_id)
            
            qdrant_points.append(
                models.PointStruct(
                    id=pt_id,
                    vector=p["vector"],
                    payload=p.get("payload", {})
                )
            )

        try:
            self.client.upsert(
                collection_name=collection_name,
                points=qdrant_points
            )
            logger.debug(f"Upserted {len(points)} points into '{collection_name}'.")
        except Exception as e:
            logger.error(f"Failed to upsert points into '{collection_name}': {e}")
            raise

    def search_similarity(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Queries Qdrant for similar vectors.
        """
        qdrant_filter = None
        if filters:
            must_clauses = []
            for key, val in filters.items():
                must_clauses.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=val)
                    )
                )
            qdrant_filter = models.Filter(must=must_clauses)

        try:
            response = self.client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=limit
            )
            
            output = []
            for r in response.points:
                output.append({
                    "id": r.id,
                    "score": r.score,
                    "payload": r.payload
                })
            return output
        except Exception as e:
            logger.error(f"Failed similarity search in '{collection_name}': {e}")
            raise

