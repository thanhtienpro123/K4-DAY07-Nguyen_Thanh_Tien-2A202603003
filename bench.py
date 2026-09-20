from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.chunking import RecursiveChunker, SentenceChunker
from src.embeddings import GeminiEmbedder, LocalEmbedder, OpenAIEmbedder, _mock_embed
from src.models import Document
from src.store import EmbeddingStore


BENCHMARK_QUERIES = [
    {
        "id": 1,
        "query": "Thời hạn yêu cầu đổi trả hoặc hoàn tiền dành cho người mua là bao nhiêu ngày?",
        "filter": {"audience": "buyer"},
        "gold_answer": "Theo chính sách đổi trả trong corpus, người mua được đổi mới hoặc yêu cầu hỗ trợ trong thời hạn được quy định, thường 30 ngày đầu nếu lỗi do nhà sản xuất.",
        "target_keywords": ["30 ngày", "đổi", "hoàn tiền"],
        "expected_docs": [
            "doi-tra-bao-hanh-cellphones-buyer",
            "doi-tra-bao-hanh-tgdd-buyer",
            "doi-tra-bao-hanh-lazada-buyer",
        ],
    },
    {
        "id": 2,
        "query": "Thời hạn Người bán phải phản hồi và gửi khiếu nại Trả hàng/Hoàn tiền là bao lâu?",
        "filter": {"audience": "seller"},
        "gold_answer": "Người bán có thời hạn 2 ngày hoặc 48 giờ tùy nền tảng để xử lý và gửi khiếu nại.",
        "target_keywords": ["2 ngày", "48 giờ", "khiếu nại"],
        "expected_docs": [
            "doi-tra-bao-hanh-shopee-seller",
            "doi-tra-bao-hanh-lazada-seller",
            "doi-tra-bao-hanh-tiki-seller",
        ],
    },
    {
        "id": 3,
        "query": "Thời hạn bảo hành xe máy điện và Pin LFP VinFast là bao nhiêu năm?",
        "filter": None,
        "gold_answer": "Xe máy điện được bảo hành 6 năm không giới hạn km; pin LFP được bảo hành lên tới 8 năm.",
        "target_keywords": ["6 năm", "8 năm", "Pin LFP"],
        "expected_docs": ["doi-tra-bao-hanh-vinfast-buyer"],
    },
    {
        "id": 4,
        "query": "Các trường hợp nào thiết bị di động bị từ chối bảo hành hoặc bị trừ phí khi đổi trả?",
        "filter": None,
        "gold_answer": "Có thể bị từ chối khi tự tháo mở sửa chữa, rơi vỡ hoặc ngập nước; có thể bị trừ phí nếu sản phẩm không lỗi hoặc thiếu hộp và phụ kiện.",
        "target_keywords": ["rơi vỡ", "tháo", "trừ phí"],
        "expected_docs": [
            "doi-tra-bao-hanh-tgdd-buyer",
            "doi-tra-bao-hanh-cellphones-buyer",
        ],
    },
    {
        "id": 5,
        "query": "Người bán cần chuẩn bị những bằng chứng gì khi khiếu nại đơn hàng bị trả về không nguyên vẹn?",
        "filter": {"audience": "seller"},
        "gold_answer": "Người bán cần video mở kiện hàng, thể hiện 6 mặt kiện hàng và tình trạng sản phẩm bên trong, tốt nhất có bằng chứng giao nhận.",
        "target_keywords": ["video", "6 mặt", "shipper"],
        "expected_docs": [
            "doi-tra-bao-hanh-shopee-seller",
            "doi-tra-bao-hanh-lazada-seller",
            "doi-tra-bao-hanh-tiki-seller",
        ],
    },
]


class HeadingChunker:
    """Split Markdown sections and retain each heading in all child chunks."""

    HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)

    def __init__(self, max_chars: int = 1200, overlap_sentences: int = 1) -> None:
        self.max_chars = max(1, max_chars)
        self.overlap_sentences = max(0, overlap_sentences)
        self.sentence_chunker = SentenceChunker(max_sentences_per_chunk=4)
        self.recursive_chunker = RecursiveChunker(chunk_size=self.max_chars)

    def chunk(self, content: str) -> list[str]:
        text = content.strip()
        if not text:
            return []
        matches = list(self.HEADING_RE.finditer(text))
        if not matches:
            return self._split_section("", text)

        chunks: list[str] = []
        if matches[0].start() > 0:
            chunks.extend(self._split_section("", text[: matches[0].start()].strip()))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            chunks.extend(
                self._split_section(
                    match.group(0).strip(), text[match.end() : end].strip()
                )
            )
        return chunks

    def _split_section(self, heading: str, body: str) -> list[str]:
        prefix = f"{heading}\n\n" if heading else ""
        section = f"{prefix}{body}".strip()
        if not section:
            return []
        if len(section) <= self.max_chars:
            return [section]

        chunks: list[str] = []
        sentence_chunks = self.sentence_chunker.chunk(body)
        for index, sentence_chunk in enumerate(sentence_chunks):
            if self.overlap_sentences and index:
                previous = sentence_chunks[index - 1].split()
                prefix_overlap = " ".join(previous[-self.overlap_sentences * 20 :])
                sentence_chunk = f"{prefix_overlap} {sentence_chunk}"
            candidate = f"{prefix}{sentence_chunk}".strip()
            if len(candidate) <= self.max_chars:
                chunks.append(candidate)
            else:
                chunks.extend(
                    f"{prefix}{piece}".strip()
                    for piece in self.recursive_chunker.chunk(sentence_chunk)
                )
        return chunks


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", text, re.DOTALL)
    if not match:
        return {}, text.strip()
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata, match.group(2).strip()


def load_documents(data_dir: Path, chunker: Any) -> list[Document]:
    documents: list[Document] = []
    for path in sorted(data_dir.glob("*.md")):
        metadata, content = parse_frontmatter(path.read_text(encoding="utf-8-sig"))
        metadata["doc_id"] = path.stem
        chunks = chunker.chunk(content)
        for index, chunk in enumerate(chunks):
            context_parts = chunks[max(0, index - 1) : index + 2]
            contextual_chunk = "\n\n".join(context_parts)
            documents.append(
                Document(f"{path.stem}#{index}", contextual_chunk, metadata.copy())
            )
    return documents


def select_embedder(backend: str) -> tuple[Callable[[str], list[float]], str, bool]:
    if backend == "mock":
        return _mock_embed, "mock embeddings", True
    if backend == "local":
        embedder = LocalEmbedder()
        return embedder, "local sentence-transformers", False
    if backend == "openai":
        embedder = OpenAIEmbedder()
        return embedder, "openai", False
    if backend == "gemini":
        embedder = GeminiEmbedder()
        return embedder, "gemini", False
    if backend == "auto":
        try:
            embedder = LocalEmbedder()
            return embedder, "local sentence-transformers", False
        except (ImportError, OSError, RuntimeError) as error:
            print(f"WARNING: real local embedder unavailable ({error}).")
            return _mock_embed, "mock embeddings fallback", True
    raise ValueError(f"Unsupported embedding backend: {backend}")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in value if not unicodedata.combining(char))


def keyword_hits(content: str, keywords: list[str]) -> list[str]:
    normalized = normalize(content)
    return [keyword for keyword in keywords if normalize(keyword) in normalized]


def lexical_overlap(query: str, content: str) -> float:
    query_terms = {
        term for term in re.findall(r"\w+", normalize(query)) if len(term) > 2
    }
    content_terms = set(re.findall(r"\w+", normalize(content)))
    if not query_terms:
        return 0.0
    return len(query_terms & content_terms) / len(query_terms)


def evaluate_result(
    result: dict[str, Any], benchmark: dict[str, Any], rank: int
) -> dict[str, Any]:
    metadata = result.get("metadata", {})
    doc_id = metadata.get("doc_id", "")
    hits = keyword_hits(result.get("content", ""), benchmark["target_keywords"])
    is_gold = doc_id in benchmark["expected_docs"]
    contains_answer = len(hits) == len(benchmark["target_keywords"])
    answer_chunk = is_gold and contains_answer
    points = 2 if answer_chunk and rank == 1 else 1 if answer_chunk and rank <= 3 else 0
    return {
        "doc_id": doc_id,
        "hits": hits,
        "gold_doc": is_gold,
        "answer_chunk": answer_chunk,
        "points": points,
    }


def retrieve(
    store: EmbeddingStore, benchmark: dict[str, Any], use_filter: bool
) -> list[dict[str, Any]]:
    metadata_filter = benchmark["filter"] if use_filter else None
    results = store.search_with_filter(
        benchmark["query"], top_k=3, metadata_filter=metadata_filter
    )
    # Keep semantic retrieval as the primary method, then use lexical evidence
    # to break ties between chunks with the same broad policy topic.
    candidates = store.search_with_filter(
        benchmark["query"], top_k=12, metadata_filter=metadata_filter
    )
    candidates.sort(
        key=lambda result: (
            lexical_overlap(benchmark["query"], result.get("content", "")),
            result.get("score", 0.0),
        ),
        reverse=True,
    )
    return candidates[:3] if candidates else results


def format_results(
    results: list[dict[str, Any]], benchmark: dict[str, Any]
) -> tuple[list[str], int]:
    lines: list[str] = []
    points = 0
    for rank, result in enumerate(results, 1):
        evaluation = evaluate_result(result, benchmark, rank)
        points += evaluation["points"]
        lines.append(
            f"  {rank}. score={result.get('score', 0.0):.6f} "
            f"doc_id={evaluation['doc_id']} chunk_id={result.get('id', '<missing>')} "
            f"keywords={evaluation['hits']} gold_doc={evaluation['gold_doc']} "
            f"answer_chunk={evaluation['answer_chunk']} points={evaluation['points']}"
        )
    return lines, points


def context_evaluation(
    results: list[dict[str, Any]], benchmark: dict[str, Any]
) -> dict[str, Any]:
    context = "\n".join(result.get("content", "") for result in results)
    hits = keyword_hits(context, benchmark["target_keywords"])
    gold_docs = {result.get("metadata", {}).get("doc_id", "") for result in results}
    return {
        "hits": hits,
        "all_keywords": len(hits) == len(benchmark["target_keywords"]),
        "gold_doc": bool(gold_docs & set(benchmark["expected_docs"])),
    }


def run_benchmark(
    data_dir: Path, backend: str, chunk_size: int, output_path: Path
) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    embedder, backend_name, is_mock = select_embedder(backend)
    strategies = {
        "heading": HeadingChunker(max_chars=chunk_size, overlap_sentences=1),
        "sentence": SentenceChunker(max_sentences_per_chunk=4),
    }
    lines = [
        "CHECKPOINT 6 - CHUNKING RETRIEVAL BENCHMARK",
        f"data_dir: {data_dir}",
        f"embedding_backend: {backend_name}",
        "embedding_warning: mock scores are not semantically reliable; analyze chunk count, average length, and coherence."
        if is_mock
        else "embedding_warning: real embedding backend selected.",
        "",
    ]

    failure_cases: list[str] = []
    for strategy_name, chunker in strategies.items():
        documents = load_documents(data_dir, chunker)
        store = EmbeddingStore(
            f"bench_{strategy_name}_{backend_name[:8]}", embedding_fn=embedder
        )
        store.add_documents(documents)
        lengths = [len(document.content) for document in documents]
        lines.extend(
            [
                f"## Strategy: {strategy_name}",
                f"chunks_loaded: {len(documents)}",
                f"average_chunk_length: {sum(lengths) / len(lengths) if lengths else 0:.2f}",
            ]
        )
        strategy_total = 0

        for benchmark in BENCHMARK_QUERIES:
            lines.append(f"Q{benchmark['id']}: {benchmark['query']}")
            filtered = retrieve(store, benchmark, use_filter=True)
            filtered_lines, filtered_points = format_results(filtered, benchmark)
            context_result = context_evaluation(filtered, benchmark)
            lines.append(
                f"  WITH_FILTER {benchmark['filter']}: total_points={filtered_points}"
            )
            lines.extend(filtered_lines)
            strategy_total += filtered_points
            evaluations = [
                evaluate_result(result, benchmark, rank)
                for rank, result in enumerate(filtered, 1)
            ]
            if not context_result["gold_doc"] or not context_result["all_keywords"]:
                available = ", ".join(
                    result.get("metadata", {}).get("doc_id", "<missing>")
                    for result in filtered
                )
                missing = ", ".join(benchmark["expected_docs"])
                has_gold_doc = any(evaluation["gold_doc"] for evaluation in evaluations)
                if has_gold_doc:
                    cause = "gold document is in Top-3 but the retrieved section lacks the answer keywords"
                    fix = "add overlap or adjust chunk boundaries so the numeric/detail evidence stays with its topic"
                else:
                    cause = "no expected source document is in Top-3"
                    fix = "review metadata filter or use a multilingual embedding model and inspect query wording"
                failure_cases.append(
                    f"{strategy_name} Q{benchmark['id']}: Top-3=[{available}], expected source(s)=[{missing}]. "
                    f"Cause: {cause}. Fix: {fix}."
                )

            if benchmark["filter"]:
                unfiltered = retrieve(store, benchmark, use_filter=False)
                unfiltered_lines, unfiltered_points = format_results(
                    unfiltered, benchmark
                )
                filtered_ids = [
                    item.get("metadata", {}).get("doc_id") for item in filtered
                ]
                unfiltered_ids = [
                    item.get("metadata", {}).get("doc_id") for item in unfiltered
                ]
                changed = filtered_ids != unfiltered_ids
                lines.append(
                    f"  WITHOUT_FILTER: total_points={unfiltered_points} changed_top3={changed}"
                )
                lines.extend(unfiltered_lines)
                lines.append(
                    f"  A_B_CONCLUSION: {'filter changes Top-3' if changed else 'filter does not change Top-3'}"
                )
            lines.append(f"  gold_answer: {benchmark['gold_answer']}")
            lines.append("")

        lines.append(f"strategy_total_points: {strategy_total}/10")
        lines.append("")

    lines.append("## Failure cases")
    lines.extend(f"- {failure}" for failure in failure_cases[:10])
    lines.append("")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved: {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Checkpoint 6 chunking and retrieval benchmark."
    )
    parser.add_argument(
        "--data-dir", type=Path, default=Path("data/ecommerce-return-policy")
    )
    parser.add_argument(
        "--embedding-backend",
        choices=("auto", "local", "openai", "gemini", "mock"),
        default="auto",
    )
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument(
        "--member",
        default="default",
        help="Member name for the individual result file.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    output = Path(
        "ket_qua_benchmark.txt"
        if args.member == "default"
        else f"ket_qua_benchmark_{args.member}.txt"
    )
    run_benchmark(args.data_dir, args.embedding_backend, args.chunk_size, output)
