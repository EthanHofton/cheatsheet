import pytest

from cheatsheet.store import (
    DEFAULT_GROUP,
    add_entry,
    create_group,
    create_sheet,
    delete_sheet,
    get_entries,
    get_group,
    get_sheet,
    list_sheets,
    store_embedding,
)


def test_create_sheet_creates_default_group(conn):
    sheet = create_sheet(conn, "tmux")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    assert grp is not None
    assert grp.name == DEFAULT_GROUP


def test_create_sheet_errors_on_duplicate(conn):
    create_sheet(conn, "tmux")
    with pytest.raises(ValueError, match="already exists"):
        create_sheet(conn, "tmux")


def test_create_sheet_errors_on_reserved_name(conn):
    with pytest.raises(ValueError, match="reserved"):
        create_sheet(conn, "add")


def test_create_group_unique_constraint(conn):
    sheet = create_sheet(conn, "tmux")
    create_group(conn, sheet.id, "pane")
    with pytest.raises(ValueError, match="already exists"):
        create_group(conn, sheet.id, "pane")


def test_create_group_rejects_default(conn):
    sheet = create_sheet(conn, "tmux")
    with pytest.raises(ValueError, match="reserved"):
        create_group(conn, sheet.id, DEFAULT_GROUP)


def test_add_entry_populates_id(conn):
    sheet = create_sheet(conn, "tmux")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    entry = add_entry(conn, grp.id, "Kill pane", "Ctrl+B x")
    assert entry.id > 0
    assert entry.description == "Kill pane"
    assert entry.command == "Ctrl+B x"
    assert entry.group_name == DEFAULT_GROUP


def test_store_and_query_embedding(conn):
    sheet = create_sheet(conn, "tmux")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    entry = add_entry(conn, grp.id, "Kill pane", "Ctrl+B x")
    vector = [0.1] * 384
    store_embedding(conn, entry.id, vector)
    row = conn.execute(
        "SELECT entry_id FROM entry_embeddings WHERE entry_id = ?", [entry.id]
    ).fetchone()
    assert row is not None


def test_get_entries_filters_by_group(conn):
    sheet = create_sheet(conn, "tmux")
    default_grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    pane_grp = create_group(conn, sheet.id, "pane")

    add_entry(conn, default_grp.id, "New window", "Ctrl+B c")
    add_entry(conn, pane_grp.id, "Kill pane", "Ctrl+B x")

    pane_entries = get_entries(conn, sheet.id, group_name="pane")
    assert len(pane_entries) == 1
    assert pane_entries[0].description == "Kill pane"

    all_entries = get_entries(conn, sheet.id)
    assert len(all_entries) == 2


def test_delete_sheet_removes_embeddings(conn):
    sheet = create_sheet(conn, "tmux")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    entry = add_entry(conn, grp.id, "Kill pane", "Ctrl+B x")
    store_embedding(conn, entry.id, [0.0] * 384)

    delete_sheet(conn, "tmux")

    row = conn.execute(
        "SELECT entry_id FROM entry_embeddings WHERE entry_id = ?", [entry.id]
    ).fetchone()
    assert row is None
    assert get_sheet(conn, "tmux") is None


def test_delete_sheet_returns_false_for_unknown(conn):
    assert delete_sheet(conn, "nonexistent") is False


def test_list_sheets_alphabetical_with_counts(conn):
    s1 = create_sheet(conn, "zsh")
    s2 = create_sheet(conn, "git")
    grp = get_group(conn, s2.id, DEFAULT_GROUP)
    add_entry(conn, grp.id, "Status", "git status")
    add_entry(conn, grp.id, "Commit", "git commit")

    sheets = list_sheets(conn)
    assert sheets[0][0].name == "git"
    assert sheets[0][1] == 2
    assert sheets[1][0].name == "zsh"
    assert sheets[1][1] == 0
