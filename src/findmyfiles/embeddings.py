from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image


class Embedder(Protocol):
    def embed_documents(self, chunks: list[str]) -> list[tuple[float, ...]]:
        ...

    def embed_images(self, images: list[Image.Image]) -> list[tuple[float, ...]]:
        ...

    def embed_query(self, query: str) -> tuple[float, ...]:
        ...


@dataclass(frozen=True)
class GeminiEmbeddingConfig:
    api_key: str
    model: str


class GeminiEmbedder:
    def __init__(self, config: GeminiEmbeddingConfig) -> None:
        if not config.api_key:
            raise ValueError("GEMINI_API_KEY is required to generate embeddings.")

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - exercised in runtime only
            msg = "google-genai is required at runtime. Install dependencies with `python -m pip install -e .`."
            raise RuntimeError(msg) from exc

        self._client = genai.Client(api_key=config.api_key)
        self._types = types
        self._model = config.model

    def embed_documents(self, chunks: list[str]) -> list[tuple[float, ...]]:
        if not chunks:
            return []
        embeddings = self._embed_contents(chunks, task_type="RETRIEVAL_DOCUMENT")
        if len(embeddings) == len(chunks):
            return embeddings

        # Gemini batch responses can occasionally collapse to a single vector.
        # Fall back to one request per chunk so indexing remains correct.
        fallback_embeddings = [
            self._embed_contents([chunk], task_type="RETRIEVAL_DOCUMENT")[0]
            for chunk in chunks
        ]
        if len(fallback_embeddings) != len(chunks):
            msg = (
                "Gemini embedding response count did not match the indexed chunks. "
                f"expected={len(chunks)} actual={len(fallback_embeddings)}"
            )
            raise RuntimeError(msg)
        return fallback_embeddings

    def embed_images(self, images: list[Image.Image]) -> list[tuple[float, ...]]:
        if not images:
            return []
        embeddings = self._embed_contents(images, task_type="RETRIEVAL_DOCUMENT")
        if len(embeddings) == len(images):
            return embeddings

        fallback_embeddings = [
            self._embed_contents([image], task_type="RETRIEVAL_DOCUMENT")[0]
            for image in images
        ]
        if len(fallback_embeddings) != len(images):
            msg = (
                "Gemini image embedding response count did not match the indexed images. "
                f"expected={len(images)} actual={len(fallback_embeddings)}"
            )
            raise RuntimeError(msg)
        return fallback_embeddings

    def embed_query(self, query: str) -> tuple[float, ...]:
        embeddings = self._embed_contents([query], task_type="RETRIEVAL_QUERY")
        if not embeddings:
            raise RuntimeError("Gemini embedding response did not include any vectors.")
        return embeddings[0]

    def _embed_contents(self, contents: list[object], *, task_type: str) -> list[tuple[float, ...]]:
        response = self._client.models.embed_content(
            model=self._model,
            contents=contents,
            config=self._types.EmbedContentConfig(task_type=task_type),
        )
        return _extract_embeddings(response)


def _extract_embeddings(response: object) -> list[tuple[float, ...]]:
    raw_embeddings = getattr(response, "embeddings", None)
    if raw_embeddings is None:
        raw_embeddings = getattr(response, "embeddings_", None)
    if raw_embeddings is None:
        raw_embedding = getattr(response, "embedding", None)
        raw_embeddings = [] if raw_embedding is None else [raw_embedding]

    vectors: list[tuple[float, ...]] = []
    for embedding in raw_embeddings:
        values = getattr(embedding, "values", None)
        if values is None and isinstance(embedding, dict):
            values = embedding.get("values")
        if values is None:
            raise RuntimeError("Gemini embedding response had an unexpected shape.")
        vectors.append(tuple(float(value) for value in values))
    return vectors
