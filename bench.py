from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Callable

from src.chunking import RecursiveChunker, SentenceChunker
from src.embeddings import GeminiEmbedder, LocalEmbedder, OpenAIEmbedder, _mock_embed
from src.models import Document
from src.store import EmbeddingStore


BENCHMARK_QUERIES = [
    {
        "id": 1,
        "query": "Người mua có thể gửi yêu cầu trả hàng hoặc hoàn tiền trong bao nhiêu ngày kể từ khi giao hàng thành công?",
        "filter": {"audience": "buyer"},
        "gold_answer": "Theo chính sách Shopee, người mua có thể gửi yêu cầu trả hàng/hoàn tiền trong vòng 15 ngày kể từ khi đơn hàng được cập nhật giao hàng thành công.",
        "target_keywords": ["15 ngày", "trả hàng", "hoàn tiền"],
        "expected_docs": ["shopee-return-regulation"],
    },
    {
        "id": 2,
        "query": "Người bán Shopee phải phản hồi quyết định trả hàng hoặc hoàn tiền trong bao lâu?",
        "filter": {"audience": "both"},
        "gold_answer": "Người bán phải gửi phản hồi trong vòng 02 ngày lịch kể từ khi nhận được thông báo của Shopee.",
        "target_keywords": ["02 ngày", "phản hồi", "Người Bán"],
        "expected_docs": ["shopee-return-refund-policy"],
    },
    {
        "id": 3,
        "query": "Người bán TikTok có thể gửi khiếu nại trong bao nhiêu ngày đối với yêu cầu trả hàng?",
        "filter": {"audience": "seller"},
        "gold_answer": "Đối với trả hàng gửi tại bưu cục hoặc lấy hàng, người bán có thể gửi khiếu nại trong vòng 7 ngày kể từ khi nhận hàng trả về; với trả hàng tự sắp xếp là 15 ngày.",
        "target_keywords": ["15 ngày", "khiếu nại", "người bán"],
        "expected_docs": ["tiktok-return-refund"],
    },
    {
        "id": 4,
        "query": "Người bán TikTok cần quay video mở kiện hàng và thể hiện những gì khi khiếu nại hàng trả về?",
        "filter": {"audience": "seller"},
        "gold_answer": "Cần cung cấp video mở kiện hàng liên tục, hiển thị thông tin đơn trả hàng, hình ảnh tất cả 6 mặt của kiện hàng và quá trình mở hàng.",
        "target_keywords": ["video mở kiện hàng", "6 mặt", "kiện hàng"],
        "expected_docs": ["tiktok-return-refund"],
    },
    {
        "id": 5,
        "query": "Sau khi yêu cầu trả hàng hoàn tiền được chấp nhận, mã giảm giá Shopee được hoàn lại trong bao lâu?",
        "filter": {"audience": "buyer"},
        "gold_answer": "Mã giảm giá được hoàn lại trong vòng 48 giờ, không kể thứ 7, chủ nhật và ngày lễ, kể từ khi yêu cầu được chấp nhận hoàn tiền.",
        "target_keywords": ["48 giờ", "hoàn tiền", "Mã giảm giá"],
        "expected_docs": ["shopee-return-regulation"],
    },
]


class HeadingChunker:
    """Split Markdown sections and retain each heading in all child chunks."""

    HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)

    def __init__(self, max_chars: int = 1200) -> None:
        self.max_chars = max(1, max_chars)
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
        for sentence_chunk in self.sentence_chunker.chunk(body):
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
        for index, chunk in enumerate(chunker.chunk(content)):
            documents.append(Document(f"{path.stem}#{index}", chunk, metadata.copy()))
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
        except Exception as error:
            print(f"WARNING: real local embedder unavailable ({error}).")
            return _mock_embed, "mock embeddings fallback", True
    raise ValueError(f"Unsupported embedding backend: {backend}")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in value if not unicodedata.combining(char))


def keyword_hits(content: str, keywords: list[str]) -> list[str]:
    normalized = normalize(content)
    return [keyword for keyword in keywords if normalize(keyword) in normalized]


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
    return store.search_with_filter(
        benchmark["query"], top_k=3, metadata_filter=metadata_filter
    )


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


def run_benchmark(
    data_dir: Path, backend: str, chunk_size: int, output_path: Path
) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    embedder, backend_name, is_mock = select_embedder(backend)
    strategies = {
        "heading": HeadingChunker(max_chars=chunk_size),
        "sentence": SentenceChunker(max_sentences_per_chunk=4),
        "recursive": RecursiveChunker(chunk_size=chunk_size),
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
            lines.append(
                f"  WITH_FILTER {benchmark['filter']}: total_points={filtered_points}"
            )
            lines.extend(filtered_lines)
            strategy_total += filtered_points
            evaluations = [
                evaluate_result(result, benchmark, rank)
                for rank, result in enumerate(filtered, 1)
            ]
            if not any(evaluation["answer_chunk"] for evaluation in evaluations):
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
