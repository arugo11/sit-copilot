#!/usr/bin/env python3
"""Ingest procedure PDF documents into Azure AI Search procedure_index."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchableField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
)

DEFAULT_INDEX_NAME = "procedure_index"
DEFAULT_GLOB = "*.pdf"
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 120
DEFAULT_BATCH_SIZE = 100
DEFAULT_SNIPPET_CHARS = 180
DEFAULT_PHASE1_INPUT_DIR = "scripts/procedure_index_ingest/input"


@dataclass(frozen=True)
class PdfChunk:
    """Single text chunk extracted from a PDF page."""

    source_id: str
    title: str
    section: str
    snippet: str
    content: str
    page: int
    chunk_no: int
    file_name: str
    source_path: str
    lang: str
    updated_at: str

    def to_document(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "section": self.section,
            "snippet": self.snippet,
            "content": self.content,
            "page": self.page,
            "chunk_no": self.chunk_no,
            "file_name": self.file_name,
            "source_path": self.source_path,
            "lang": self.lang,
            "updated_at": self.updated_at,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract text chunks from PDF files and ingest them into Azure AI Search "
            "procedure_index."
        )
    )
    parser.add_argument(
        "--input",
        default="",
        help="PDF file path or directory path containing PDFs.",
    )
    parser.add_argument(
        "--phase1-test",
        action="store_true",
        help=(
            "Use first-stage RAG test dataset under "
            f"{DEFAULT_PHASE1_INPUT_DIR} as input."
        ),
    )
    parser.add_argument(
        "--endpoint",
        default="",
        help="Azure Search endpoint. If omitted, reads AZURE_SEARCH_ENDPOINT.",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="Azure Search API key. If omitted, reads AZURE_SEARCH_API_KEY.",
    )
    parser.add_argument(
        "--index-name",
        default="",
        help=(
            "Target index name. If omitted, reads PROCEDURE_SEARCH_INDEX_NAME "
            f"and falls back to {DEFAULT_INDEX_NAME!r}."
        ),
    )
    parser.add_argument(
        "--glob",
        default=DEFAULT_GLOB,
        help=f"Glob pattern for PDF discovery under directory input (default: {DEFAULT_GLOB}).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Max characters per chunk (default: {DEFAULT_CHUNK_SIZE}).",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP,
        help=f"Overlap characters between chunks (default: {DEFAULT_CHUNK_OVERLAP}).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Upload batch size (default: {DEFAULT_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--lang",
        default="ja",
        help="Language tag stored in index documents (default: ja).",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Optional limit for number of PDF files to process.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and chunk PDFs without indexing documents.",
    )
    parser.add_argument(
        "--skip-index-setup",
        action="store_true",
        help="Skip create_or_update_index call when index is already prepared.",
    )
    return parser.parse_args()


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def iter_pdf_paths(input_path: Path, pattern: str) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() != ".pdf":
            raise ValueError(f"Input file is not PDF: {input_path}")
        return [input_path]

    if input_path.is_dir():
        return sorted(path for path in input_path.rglob(pattern) if path.is_file())

    raise ValueError(f"Input path not found: {input_path}")


def chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    text_len = len(text)
    step = max(1, max_chars - overlap)

    while start < text_len:
        end = min(text_len, start + max_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_len:
            break
        start += step

    return chunks


def build_source_id(pdf_path: Path, page: int, chunk_no: int) -> str:
    # Stable short hash avoids collisions across same filename in different dirs.
    digest = hashlib.sha1(str(pdf_path.resolve()).encode("utf-8")).hexdigest()[:10]
    stem = pdf_path.stem.lower()
    stem = re.sub(r"[^a-z0-9_-]+", "-", stem)
    stem = re.sub(r"-{2,}", "-", stem).strip("-_")
    if not stem:
        stem = "doc"
    return f"{stem}_{digest}_p{page:04d}_c{chunk_no:04d}"


def extract_chunks_from_pdf(
    pdf_path: Path,
    *,
    chunk_size: int,
    chunk_overlap: int,
    lang: str,
) -> list[PdfChunk]:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing dependency: pypdf. Install with `uv add pypdf` and retry."
        ) from exc

    reader = PdfReader(str(pdf_path))
    title = pdf_path.stem
    now = datetime.now(UTC).isoformat()

    chunks: list[PdfChunk] = []
    for page_index, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        normalized_text = normalize_whitespace(raw_text)
        if not normalized_text:
            continue

        page_chunks = chunk_text(
            normalized_text,
            max_chars=chunk_size,
            overlap=chunk_overlap,
        )
        for chunk_no, chunk in enumerate(page_chunks, start=1):
            snippet = chunk[:DEFAULT_SNIPPET_CHARS]
            chunks.append(
                PdfChunk(
                    source_id=build_source_id(pdf_path, page_index, chunk_no),
                    title=title,
                    section=f"page {page_index}",
                    snippet=snippet,
                    content=chunk,
                    page=page_index,
                    chunk_no=chunk_no,
                    file_name=pdf_path.name,
                    source_path=str(pdf_path.resolve()),
                    lang=lang,
                    updated_at=now,
                )
            )

    return chunks


def create_or_update_index(
    *,
    endpoint: str,
    api_key: str,
    index_name: str,
) -> None:
    credential = AzureKeyCredential(api_key)
    client = SearchIndexClient(endpoint=endpoint, credential=credential)

    index = SearchIndex(
        name=index_name,
        fields=[
            SimpleField(
                name="source_id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
            ),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SearchableField(name="section", type=SearchFieldDataType.String),
            SearchableField(name="snippet", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SimpleField(
                name="page",
                type=SearchFieldDataType.Int32,
                filterable=True,
                sortable=True,
            ),
            SimpleField(
                name="chunk_no",
                type=SearchFieldDataType.Int32,
                filterable=True,
                sortable=True,
            ),
            SimpleField(
                name="file_name",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SimpleField(
                name="source_path",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SimpleField(
                name="lang",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SimpleField(
                name="updated_at",
                type=SearchFieldDataType.String,
                filterable=True,
                sortable=True,
            ),
        ],
    )
    client.create_or_update_index(index)


def upload_documents(
    *,
    endpoint: str,
    api_key: str,
    index_name: str,
    documents: list[dict[str, Any]],
    batch_size: int,
) -> tuple[int, int]:
    credential = AzureKeyCredential(api_key)
    search_client = SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=credential,
    )

    success_count = 0
    failure_count = 0
    for start in range(0, len(documents), batch_size):
        batch = documents[start : start + batch_size]
        result = search_client.merge_or_upload_documents(batch)
        for item in result:
            if getattr(item, "succeeded", False):
                success_count += 1
            else:
                failure_count += 1

    return success_count, failure_count


def require_non_empty(value: str, message: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(message)
    return normalized


def main() -> int:
    args = parse_args()

    if args.chunk_size <= 0:
        raise SystemExit("--chunk-size must be > 0")
    if args.chunk_overlap < 0:
        raise SystemExit("--chunk-overlap must be >= 0")
    if args.chunk_overlap >= args.chunk_size:
        raise SystemExit("--chunk-overlap must be less than --chunk-size")
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be > 0")

    endpoint = require_non_empty(
        args.endpoint or os.environ.get("AZURE_SEARCH_ENDPOINT", ""),
        "Missing endpoint. Set --endpoint or AZURE_SEARCH_ENDPOINT.",
    )
    api_key = require_non_empty(
        args.api_key or os.environ.get("AZURE_SEARCH_API_KEY", ""),
        "Missing API key. Set --api-key or AZURE_SEARCH_API_KEY.",
    )
    index_name = (
        args.index_name
        or os.environ.get("PROCEDURE_SEARCH_INDEX_NAME", "")
        or DEFAULT_INDEX_NAME
    )

    input_value = args.input
    if args.phase1_test:
        input_value = DEFAULT_PHASE1_INPUT_DIR
    if not input_value.strip():
        raise SystemExit("Missing input. Set --input or pass --phase1-test.")

    input_path = Path(input_value)
    pdf_paths = iter_pdf_paths(input_path, args.glob)
    if args.max_files > 0:
        pdf_paths = pdf_paths[: args.max_files]

    if not pdf_paths:
        raise SystemExit("No PDF files found.")

    all_chunks: list[PdfChunk] = []
    for pdf_path in pdf_paths:
        chunks = extract_chunks_from_pdf(
            pdf_path,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            lang=args.lang,
        )
        all_chunks.extend(chunks)
        print(f"[parse] {pdf_path} -> {len(chunks)} chunks")

    if not all_chunks:
        raise SystemExit("No text chunks extracted from the input PDFs.")

    documents = [chunk.to_document() for chunk in all_chunks]
    print(
        "[summary] "
        f"files={len(pdf_paths)} chunks={len(documents)} index={index_name} dry_run={args.dry_run}"
    )

    if args.dry_run:
        return 0

    if not args.skip_index_setup:
        create_or_update_index(
            endpoint=endpoint,
            api_key=api_key,
            index_name=index_name,
        )
        print("[index] create_or_update_index completed")

    success_count, failure_count = upload_documents(
        endpoint=endpoint,
        api_key=api_key,
        index_name=index_name,
        documents=documents,
        batch_size=args.batch_size,
    )

    print(f"[upload] success={success_count} failed={failure_count}")
    return 0 if failure_count == 0 else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
