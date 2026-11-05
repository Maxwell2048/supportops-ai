"""Bounded local-only embeddings. Input text and provider responses never enter errors/logs."""
from dataclasses import asdict, dataclass
import math
from uuid import NAMESPACE_URL, uuid5

import httpx

from supportops.errors import ApiError
from supportops.idempotency import canonical_hash


@dataclass(frozen=True)
class EmbeddingSpec:
    provider: str
    model: str
    model_digest: str
    dimensions: int
    license_note: str
    normalization: str = "l2-v1"

    @property
    def id(self):
        return uuid5(NAMESPACE_URL, "supportops.embedding/" + canonical_hash(asdict(self)))


MINILM = EmbeddingSpec("ollama", "all-minilm:22m", "1b226e2802dbb772b5fc32a58f103ca1804ef7501331012de126ab22f67475ef", 384,
    "Apache-2.0; https://ollama.com/library/all-minilm; https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2")


def normalize_vectors(value, count, dimensions):
    if not isinstance(value, list) or len(value) != count:
        raise ApiError(503, "invalid_embedding", "The embedding provider returned an invalid response")
    result = []
    for row in value:
        if not isinstance(row, list) or len(row) != dimensions or any(type(number) not in {int, float} or not math.isfinite(number) for number in row):
            raise ApiError(503, "invalid_embedding", "The embedding provider returned an invalid response")
        norm = math.sqrt(math.fsum(number * number for number in row))
        if not math.isfinite(norm) or norm <= 0:
            raise ApiError(503, "invalid_embedding", "The embedding provider returned an invalid response")
        result.append([number / norm for number in row])
    return result


class OllamaEmbedding:
    spec = MINILM

    def __init__(self, url="http://127.0.0.1:11434", *, transport=None):
        # Settings also validate this boundary; validate direct CLI/test construction too.
        from supportops.config import Settings
        Settings(embedding_url=url)
        self.url, self.transport = url.rstrip("/"), transport

    def embed(self, texts):
        if not texts or len(texts) > 140 or any(not isinstance(item, str) or not item or len(item) > 500 for item in texts):
            raise ApiError(422, "embedding_input", "Embedding input is outside the bounded retrieval contract")
        try:
            with httpx.Client(base_url=self.url, timeout=15, trust_env=False, follow_redirects=False, transport=self.transport) as client:
                def verify():
                    response = client.get("/api/tags")
                    response.raise_for_status()
                    if not any(row.get("name") == self.spec.model and row.get("digest") == self.spec.model_digest for row in response.json()["models"]):
                        raise ApiError(503, "embedding_model_changed", "The configured local embedding model is missing or has changed")
                verify()
                response = client.post("/api/embed", json={"model": self.spec.model, "input": texts, "truncate": False})
                response.raise_for_status()
                vectors = normalize_vectors(response.json()["embeddings"], len(texts), self.spec.dimensions)
                verify()
                return vectors
        except ApiError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            raise ApiError(503, "embedding_unavailable", "Local embeddings are unavailable; check the pinned model and retry") from None
