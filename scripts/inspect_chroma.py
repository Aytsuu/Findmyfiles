from __future__ import annotations

import argparse
from pathlib import Path

import chromadb


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect the local Findmyfiles ChromaDB collection.")
    parser.add_argument(
        "--root",
        default=str(Path.home() / ".findmyfiles" / "chroma"),
        help="Path to the Chroma persistence directory.",
    )
    parser.add_argument(
        "--collection",
        default="findmyfiles",
        help="Collection name to inspect.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of rows to print.",
    )
    parser.add_argument(
        "--include-embeddings",
        action="store_true",
        help="Print the full embedding vectors instead of just their dimensionality.",
    )
    parser.add_argument(
        "--path-contains",
        help="Only print rows whose path contains this substring (case-insensitive).",
    )
    parser.add_argument(
        "--mime",
        help="Only print rows matching this MIME type exactly.",
    )
    parser.add_argument(
        "--chunk",
        type=int,
        help="Only print rows for a specific chunk index.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    client = chromadb.PersistentClient(path=str(root))
    collection = client.get_collection(args.collection)

    print(f"root: {root}")
    print(f"collection: {args.collection}")
    print(f"count: {collection.count()}")

    include = ["documents", "metadatas", "embeddings"]
    rows = collection.get(include=include)

    documents = rows.get("documents")
    metadatas = rows.get("metadatas")
    embeddings = rows.get("embeddings")

    if documents is None:
        documents = []
    if metadatas is None:
        metadatas = []
    if embeddings is None:
        embeddings = []

    filtered_rows: list[tuple[str, dict[str, object], object]] = []
    for document, metadata, embedding in zip(documents, metadatas, embeddings, strict=True):
        if metadata is None:
            continue
        if not _matches_filters(
            metadata=metadata,
            path_contains=args.path_contains,
            mime=args.mime,
            chunk=args.chunk,
        ):
            continue
        filtered_rows.append((str(document), metadata, embedding))
        if len(filtered_rows) >= args.limit:
            break

    print(f"shown: {len(filtered_rows)}")

    for index, (document, metadata, embedding) in enumerate(filtered_rows, start=1):
        print(f"\nrow {index}")
        print(f"path: {metadata['path']}")
        print(f"chunk: {metadata['chunk']}")
        print(f"mime: {metadata['mime']}")
        print(f"size: {metadata['size']}")
        print(f"mtime: {metadata['mtime']}")
        print(f"embedding_dims: {len(embedding)}")
        print(f"snippet: {_safe_console_text(str(document)[:120])}")
        if args.include_embeddings:
            print(f"embedding: {embedding}")


def _safe_console_text(value: str) -> str:
    return value.encode("cp1252", errors="replace").decode("cp1252")


def _matches_filters(
    *,
    metadata: dict[str, object],
    path_contains: str | None,
    mime: str | None,
    chunk: int | None,
) -> bool:
    path = str(metadata.get("path", ""))
    if path_contains and path_contains.lower() not in path.lower():
        return False
    if mime and str(metadata.get("mime")) != mime:
        return False
    if chunk is not None and int(metadata.get("chunk", -1)) != chunk:
        return False
    return True


if __name__ == "__main__":
    main()
