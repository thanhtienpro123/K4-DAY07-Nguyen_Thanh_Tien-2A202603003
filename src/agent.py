from typing import Callable

from .store import EmbeddingStore


class KnowledgeBaseAgent:
    """
    An agent that answers questions using a vector knowledge base.

    Retrieval-augmented generation (RAG) pattern:
        1. Retrieve top-k relevant chunks from the store.
        2. Build a prompt with the chunks as context.
        3. Call the LLM to generate an answer.
    """

    def __init__(self, store: EmbeddingStore, llm_fn: Callable[[str], str]) -> None:
        self.store = store
        self.llm_fn = llm_fn

    def answer(self, question: str, top_k: int = 3) -> str:
        # 1. Retrieve relevant chunks
        chunks = self.store.search(question, top_k=top_k)

        # 2. Build context from retrieved chunks
        context = "\n\n".join(chunk["content"] for chunk in chunks)

        # 3. Build prompt
        prompt = f"""
Answer the question using only the information provided in the context below.

Context:
{context}

Question:
{question}

Answer:
""".strip()

        # 4. Call LLM
        return self.llm_fn(prompt)
