from __future__ import annotations

from typing import Any, Callable

from .chunking import _dot
from .embeddings import _mock_embed
from .models import Document


from typing import Any, Callable


class EmbeddingStore:
    """
    A vector store for text chunks.

    Tries to use ChromaDB if available; falls back to an in-memory store.
    The embedding_fn parameter allows injection of mock embeddings for tests.
    """

    def __init__(
        self,
        collection_name: str = "documents",
        embedding_fn: Callable[[str], list[float]] | None = None,
    ) -> None:
        self._embedding_fn = embedding_fn or _mock_embed
        self._collection_name = collection_name
        self._use_chroma = False
        self._store: list[dict[str, Any]] = []
        self._collection = None
        self._next_index = 0

        try:
            import chromadb

            # Initialize ChromaDB client and collection
            client = chromadb.Client()

            self._collection = client.get_or_create_collection(name=collection_name)

            self._use_chroma = True

        except Exception:
            self._use_chroma = False
            self._collection = None

    def _make_record(self, doc: Document) -> dict[str, Any]:
        """Build a normalized stored record for one document."""

        embedding = self._embedding_fn(doc.content)

        # Use document ID if available.
        # Otherwise generate an internal ID.
        doc_id = getattr(doc, "id", None)

        if not doc_id:
            doc_id = f"doc_{self._next_index}"

        metadata = dict(getattr(doc, "metadata", {}) or {})

        # Preserve a source-document ID when storing chunks.
        metadata.setdefault("doc_id", str(doc_id))

        record = {
            "id": str(doc_id),
            "content": doc.content,
            "embedding": embedding,
            "metadata": metadata,
        }

        self._next_index += 1

        return record

    def _search_records(
        self,
        query: str,
        records: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Run in-memory similarity search over provided records."""

        if not records or top_k <= 0:
            return []

        query_embedding = self._embedding_fn(query)

        results = []

        for record in records:
            embedding = record["embedding"]

            # Dot product as specified by the class docstring
            similarity = sum(a * b for a, b in zip(query_embedding, embedding))

            result = dict(record)
            result["similarity"] = similarity
            result["score"] = similarity

            results.append(result)

        # Highest similarity first
        results.sort(
            key=lambda record: record["similarity"],
            reverse=True,
        )

        return results[:top_k]

    def add_documents(self, docs: list[Document]) -> None:
        """
        Embed each document's content and store it.

        For ChromaDB: use collection.add(ids=[...], documents=[...], embeddings=[...])
        For in-memory: append dicts to self._store
        """

        if not docs:
            return

        records = [self._make_record(doc) for doc in docs]

        if self._use_chroma:
            self._collection.add(
                ids=[record["id"] for record in records],
                documents=[record["content"] for record in records],
                embeddings=[record["embedding"] for record in records],
                metadatas=[record["metadata"] for record in records],
            )
        else:
            self._store.extend(records)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Find the top_k most similar documents to query.

        For in-memory: compute dot product of query embedding vs all stored embeddings.
        """

        if top_k <= 0:
            return []

        if self._use_chroma:
            query_embedding = self._embedding_fn(query)

            result = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
            )

            results = []

            ids = result.get("ids", [[]])[0]
            documents = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]

            for i, doc_id in enumerate(ids):
                record = {
                    "id": doc_id,
                    "content": documents[i],
                    "metadata": metadatas[i],
                }

                # Chroma returns distance rather than similarity.
                if distances:
                    record["distance"] = distances[i]
                    record["score"] = -distances[i]
                else:
                    record["score"] = 0.0

                results.append(record)

            return results

        return self._search_records(
            query,
            self._store,
            top_k,
        )

    def get_collection_size(self) -> int:
        """Return the total number of stored chunks."""

        if self._use_chroma:
            return self._collection.count()

        return len(self._store)

    def search_with_filter(
        self, query: str, top_k: int = 3, metadata_filter: dict = None
    ) -> list[dict]:
        """
        Search with optional metadata pre-filtering.

        First filter stored chunks by metadata_filter,
        then run similarity search.
        """

        if top_k <= 0:
            return []

        # No filter -> normal search
        if not metadata_filter:
            return self.search(query, top_k)

        if self._use_chroma:
            query_embedding = self._embedding_fn(query)

            result = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=metadata_filter,
            )

            results = []

            ids = result.get("ids", [[]])[0]
            documents = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]

            for i, doc_id in enumerate(ids):
                record = {
                    "id": doc_id,
                    "content": documents[i],
                    "metadata": metadatas[i],
                }

                if distances:
                    record["distance"] = distances[i]
                    record["score"] = -distances[i]
                else:
                    record["score"] = 0.0

                results.append(record)

            return results

        # In-memory metadata filtering
        def matches_filter(record: dict[str, Any]) -> bool:
            metadata = record.get("metadata", {})

            return all(
                metadata.get(key) == value for key, value in metadata_filter.items()
            )

        filtered_records = [record for record in self._store if matches_filter(record)]

        return self._search_records(
            query,
            filtered_records,
            top_k,
        )

    def delete_document(self, doc_id: str) -> bool:
        """
        Remove all chunks belonging to a document.

        Returns True if any chunks were removed, False otherwise.
        """

        doc_id = str(doc_id)

        if self._use_chroma:
            # Find all chunks belonging to this document
            result = self._collection.get(where={"doc_id": doc_id})

            ids = result.get("ids", [])

            if not ids:
                return False

            self._collection.delete(ids=ids)

            return True

        original_size = len(self._store)

        self._store = [
            record
            for record in self._store
            if str(record.get("metadata", {}).get("doc_id")) != doc_id
        ]

        return len(self._store) < original_size
