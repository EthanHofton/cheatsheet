import sqlite3

import numpy as np

from .embeddings import embed
from .models import Entry, SearchResult
from .store import get_entries, get_sheet, load_embeddings


def semantic_search(
    conn: sqlite3.Connection,
    sheet_name: str,
    query: str,
    top_k: int = 8,
) -> list[SearchResult]:
    sheet = get_sheet(conn, sheet_name)
    if sheet is None:
        return []

    embeddings = load_embeddings(conn, sheet.id)
    if not embeddings:
        return []

    query_vec = np.array(embed(query), dtype=np.float32)
    entry_ids = [eid for eid, _ in embeddings]
    matrix = np.array([vec for _, vec in embeddings], dtype=np.float32)

    # Embeddings are already L2-normalised; dot product == cosine similarity.
    similarities = matrix @ query_vec
    distances = 1.0 - similarities

    order = np.argsort(distances)[:top_k]

    entries_by_id = {e.id: e for e in get_entries(conn, sheet.id)}

    results = []
    for idx in order:
        entry_id = entry_ids[idx]
        entry = entries_by_id.get(entry_id)
        if entry is not None:
            results.append(SearchResult(entry=entry, distance=float(distances[idx])))

    return results
