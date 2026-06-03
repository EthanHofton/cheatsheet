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
    tol: float | None = None,
    filter_group: str | None = None,
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

    # Embeddings are L2-normalised; dot product == cosine similarity.
    similarities = matrix @ query_vec
    distances = 1.0 - similarities

    order = np.argsort(distances)
    entries_by_id = {e.id: e for e in get_entries(conn, sheet.id)}

    results = []
    for idx in order:
        if len(results) == top_k:
            break
        entry_id = entry_ids[idx]
        entry = entries_by_id.get(entry_id)
        if entry is None:
            continue
        distance = float(distances[idx])
        if tol is not None and (1.0 - distance) < tol:
            continue
        if filter_group is not None and entry.group_name != filter_group:
            continue
        results.append(SearchResult(entry=entry, distance=distance))

    return results
