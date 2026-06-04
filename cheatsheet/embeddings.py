import logging
import os

os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

from sentence_transformers import SentenceTransformer
from transformers import logging as transformers_logging

transformers_logging.set_verbosity_error()
transformers_logging.disable_progress_bar()
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

_MODEL: SentenceTransformer | None = None
MODEL_NAME = "BAAI/bge-base-en-v1.5"

# BGE asymmetric retrieval: prepend to queries only, not to indexed documents.
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def get_model() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(MODEL_NAME)
    return _MODEL


def embed(text: str) -> list[float]:
    """Embed a search query (adds asymmetric retrieval prefix)."""
    return get_model().encode([_QUERY_PREFIX + text], normalize_embeddings=True)[0].tolist()


def embed_doc(text: str) -> list[float]:
    """Embed a single document for indexing (no query prefix)."""
    return get_model().encode([text], normalize_embeddings=True)[0].tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple documents for indexing (no query prefix)."""
    return get_model().encode(texts, normalize_embeddings=True).tolist()


def entry_embed_text(
    sheet: str,
    group: str,
    description: str,
    placeholder_descriptions: list[str] | None = None,
) -> str:
    """Build the document text used to index a cheatsheet entry.

    Omits the raw command token — short sequences like :w, gd, Ctrl-A x are
    opaque to sentence models and add noise. The natural-language description
    carries all the semantic signal.
    """
    text = f"{sheet} {group}: {description}"
    if placeholder_descriptions:
        details = ", ".join(d for d in placeholder_descriptions if d)
        if details:
            text += f" — {details}"
    return text
