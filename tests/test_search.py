import pytest

from cheatsheet.search import semantic_search
from cheatsheet.store import add_entry, create_group, create_sheet, get_group, store_embedding
from cheatsheet.store import DEFAULT_GROUP
from cheatsheet.embeddings import embed


def _seed_entry(conn, group_id, description, command, mock_embedder):
    entry = add_entry(conn, group_id, description, command)
    vector = embed(f"{description} {command}")
    store_embedding(conn, entry.id, vector)
    return entry


def test_search_returns_results_ordered_by_distance(conn, mock_embedder):
    sheet = create_sheet(conn, "tmux")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)

    _seed_entry(conn, grp.id, "Kill pane", "Ctrl+B x", mock_embedder)
    _seed_entry(conn, grp.id, "Split horizontal", "Ctrl+B %", mock_embedder)
    _seed_entry(conn, grp.id, "New window", "Ctrl+B c", mock_embedder)

    results = semantic_search(conn, "tmux", "kill pane")
    assert len(results) > 0
    distances = [r.distance for r in results]
    assert distances == sorted(distances)


def test_search_is_scoped_to_sheet(conn, mock_embedder):
    tmux = create_sheet(conn, "tmux")
    git = create_sheet(conn, "git")

    tmux_grp = get_group(conn, tmux.id, DEFAULT_GROUP)
    git_grp = get_group(conn, git.id, DEFAULT_GROUP)

    _seed_entry(conn, tmux_grp.id, "Kill pane", "Ctrl+B x", mock_embedder)
    _seed_entry(conn, git_grp.id, "Commit", "git commit", mock_embedder)

    results = semantic_search(conn, "tmux", "commit")
    for r in results:
        assert r.entry.sheet_name == "tmux"


def test_search_empty_sheet_returns_empty(conn, mock_embedder):
    create_sheet(conn, "empty")
    results = semantic_search(conn, "empty", "anything")
    assert results == []


def test_search_top_k_limits_results(conn, mock_embedder):
    sheet = create_sheet(conn, "tmux")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    for i in range(10):
        _seed_entry(conn, grp.id, f"Entry {i}", f"cmd {i}", mock_embedder)

    results = semantic_search(conn, "tmux", "entry", top_k=3)
    assert len(results) <= 3
