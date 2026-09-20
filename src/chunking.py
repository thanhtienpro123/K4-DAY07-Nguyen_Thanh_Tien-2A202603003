from __future__ import annotations

import math
import re


class FixedSizeChunker:
    """
    Split text into fixed-size chunks with optional overlap.

    Rules:
        - Each chunk is at most chunk_size characters long.
        - Consecutive chunks share overlap characters.
        - The last chunk contains whatever remains.
        - If text is shorter than chunk_size, return [text].
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        step = self.chunk_size - self.overlap
        chunks: list[str] = []
        for start in range(0, len(text), step):
            chunk = text[start : start + self.chunk_size]
            chunks.append(chunk)
            if start + self.chunk_size >= len(text):
                break
        return chunks


import re


class SentenceChunker:
    """
    Split text into chunks of at most max_sentences_per_chunk sentences.

    Sentence detection: split on ". ", "! ", "? " or ".\n".
    Strip extra whitespace from each chunk.
    """

    def __init__(self, max_sentences_per_chunk: int = 3) -> None:
        self.max_sentences_per_chunk = max(1, max_sentences_per_chunk)

    def chunk(self, text: str) -> list[str]:
        # Split after sentence-ending punctuation followed by
        # whitespace or a newline.
        sentences = re.split(r"(?<=[.!?])(?: +|\n+)", text.strip())

        # Remove empty sentences
        sentences = [sentence.strip() for sentence in sentences if sentence.strip()]

        # Group sentences into chunks
        chunks = []
        for i in range(0, len(sentences), self.max_sentences_per_chunk):
            chunk = " ".join(sentences[i : i + self.max_sentences_per_chunk])
            chunks.append(chunk.strip())

        return chunks


class RecursiveChunker:
    """
    Recursively split text using separators in priority order.

    Default separator priority:
        ["\n\n", "\n", ". ", " ", ""]
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    def __init__(
        self, separators: list[str] | None = None, chunk_size: int = 500
    ) -> None:
        self.separators = (
            self.DEFAULT_SEPARATORS if separators is None else list(separators)
        )
        self.chunk_size = max(1, chunk_size)

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        chunks = self._split(text.strip(), self.separators)

        # Clean up whitespace and remove empty chunks
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    def _split(self, current_text: str, remaining_separators: list[str]) -> list[str]:

        current_text = current_text.strip()

        if not current_text:
            return []

        # Already small enough
        if len(current_text) <= self.chunk_size:
            return [current_text]

        # No separators left -> hard split by character
        if not remaining_separators:
            return [
                current_text[i : i + self.chunk_size]
                for i in range(0, len(current_text), self.chunk_size)
            ]

        separator = remaining_separators[0]
        next_separators = remaining_separators[1:]

        # Special case: empty separator means character-level splitting
        if separator == "":
            return [
                current_text[i : i + self.chunk_size]
                for i in range(0, len(current_text), self.chunk_size)
            ]

        # Separator doesn't exist in the text.
        # Try the next separator.
        if separator not in current_text:
            return self._split(current_text, next_separators)

        # Split using the current separator
        pieces = current_text.split(separator)

        chunks = []
        current_chunk = ""

        for piece in pieces:
            piece = piece.strip()

            if not piece:
                continue

            # Keep the separator when joining pieces back together.
            candidate = (
                piece if not current_chunk else current_chunk + separator + piece
            )

            if len(candidate) <= self.chunk_size:
                current_chunk = candidate
            else:
                # Save the current chunk first
                if current_chunk:
                    chunks.append(current_chunk)

                # If this individual piece is still too large,
                # recursively split it using lower-priority separators.
                if len(piece) > self.chunk_size:
                    sub_chunks = self._split(piece, next_separators)
                    chunks.extend(sub_chunks)
                    current_chunk = ""
                else:
                    current_chunk = piece

        # Add remaining text
        if current_chunk:
            chunks.append(current_chunk)

        return chunks


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


import math


def compute_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    cosine_similarity = dot(a, b) / (||a|| * ||b||)

    Returns 0.0 if either vector has zero magnitude.
    """
    if len(vec_a) != len(vec_b):
        raise ValueError("Vectors must have the same dimension.")

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))

    magnitude_a = math.sqrt(sum(a * a for a in vec_a))
    magnitude_b = math.sqrt(sum(b * b for b in vec_b))

    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


class ChunkingStrategyComparator:
    """Run all built-in chunking strategies and compare their results."""

    def compare(self, text: str, chunk_size: int = 200) -> dict:
        chunkers = {
            "fixed_size": FixedSizeChunker(
                chunk_size=chunk_size,
                overlap=0,
            ),
            "by_sentences": SentenceChunker(max_sentences_per_chunk=3),
            "recursive": RecursiveChunker(chunk_size=chunk_size),
        }

        comparison = {}

        for name, chunker in chunkers.items():
            chunks = chunker.chunk(text)

            lengths = [len(chunk) for chunk in chunks]

            comparison[name] = {
                "chunks": chunks,
                "count": len(chunks),
                "avg_length": (sum(lengths) / len(lengths) if lengths else 0.0),
                "num_chunks": len(chunks),
                "avg_chunk_length": (sum(lengths) / len(lengths) if lengths else 0.0),
                "min_chunk_length": min(lengths) if lengths else 0,
                "max_chunk_length": max(lengths) if lengths else 0,
                "total_characters": sum(lengths),
                "chunks_over_size": (sum(length > chunk_size for length in lengths)),
            }

        return comparison
