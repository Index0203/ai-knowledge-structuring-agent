"""Key-free embedding used so the pipeline stays runnable in local development."""

import hashlib
import math
import re

LATIN_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
CJK_SEGMENT_PATTERN = re.compile(r"[\u4e00-\u9fff]+")


class DeterministicEmbeddingProvider:
    """Hashing bag-of-words embedding with L2 normalisation.

    The vectors are lexical rather than semantic: identical wording scores high,
    paraphrases do not. Results are deterministic, so tests and demos never need
    a provider key. Configure EMBEDDING_PROVIDER=openai for semantic retrieval.
    """

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive.")
        self.dimensions = dimensions
        self.name = f"deterministic-hashing-{dimensions}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token, weight in self._token_weights(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def _token_weights(text: str) -> list[tuple[str, float]]:
        counts: dict[str, int] = {}
        lowered = text.lower()
        for token in LATIN_TOKEN_PATTERN.findall(lowered):
            counts[token] = counts.get(token, 0) + 1
        for segment in CJK_SEGMENT_PATTERN.findall(text):
            for index, character in enumerate(segment):
                counts[character] = counts.get(character, 0) + 1
                if index + 1 < len(segment):
                    bigram = segment[index : index + 2]
                    counts[bigram] = counts.get(bigram, 0) + 1
        return [(token, 1.0 + math.log(count)) for token, count in counts.items()]
