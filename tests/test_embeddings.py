from __future__ import annotations

from types import SimpleNamespace

from findmyfiles.embeddings import _extract_embeddings


def test_extract_embeddings_supports_embeddings_alias_field() -> None:
    response = SimpleNamespace(
        embeddings_=[
            SimpleNamespace(values=[0.1, 0.2]),
            SimpleNamespace(values=[0.3, 0.4]),
        ]
    )

    vectors = _extract_embeddings(response)

    assert vectors == [(0.1, 0.2), (0.3, 0.4)]


def test_extract_embeddings_supports_single_embedding_field() -> None:
    response = SimpleNamespace(embedding=SimpleNamespace(values=[0.5, 0.6]))

    vectors = _extract_embeddings(response)

    assert vectors == [(0.5, 0.6)]
