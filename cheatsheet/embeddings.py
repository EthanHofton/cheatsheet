import logging
import os

os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

from sentence_transformers import SentenceTransformer
from transformers import logging as transformers_logging

transformers_logging.set_verbosity_error()
transformers_logging.disable_progress_bar()
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

_MODEL: SentenceTransformer | None = None
MODEL_NAME = "all-MiniLM-L6-v2"


def get_model() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(MODEL_NAME)
    return _MODEL


def embed(text: str) -> list[float]:
    return get_model().encode([text], normalize_embeddings=True)[0].tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    return get_model().encode(texts, normalize_embeddings=True).tolist()


def entry_embed_text(
    group: str,
    description: str,
    command: str,
    placeholder_descriptions: list[str] | None = None,
) -> str:
    parts = [group, description, command]
    if placeholder_descriptions:
        parts.extend(d for d in placeholder_descriptions if d)
    return " ".join(parts)
