import sqlite3
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from cheatsheet.db import _bootstrap_schema


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    _bootstrap_schema(c)
    yield c
    c.close()


@pytest.fixture
def mock_embedder():
    rng = np.random.default_rng(42)

    def fake_encode(texts, normalize_embeddings=True):
        vecs = np.array([rng.random(384).astype(np.float32) for _ in texts])
        if normalize_embeddings:
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            vecs = vecs / np.where(norms == 0, 1, norms)
        return vecs

    mock_model = MagicMock()
    mock_model.encode.side_effect = fake_encode

    with patch("cheatsheet.embeddings._MODEL", mock_model):
        yield mock_model
