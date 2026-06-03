import pytest

from cheatsheet.store import (
    DEFAULT_GROUP,
    add_entry,
    add_placeholder,
    create_group,
    create_sheet,
    delete_placeholder,
    delete_sheet,
    get_entries,
    get_group,
    get_placeholders,
    get_sheet,
    list_sheets,
    set_placeholders,
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
        create_sheet(conn, "list")


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


def test_add_placeholder(conn):
    sheet = create_sheet(conn, "git")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    entry = add_entry(conn, grp.id, "Clone repo", "git clone <url> <dir>")
    ph = add_placeholder(conn, entry.id, "url", "Repository URL")
    assert ph.name == "url"
    assert ph.description == "Repository URL"


def test_add_placeholder_duplicate_raises(conn):
    sheet = create_sheet(conn, "git")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    entry = add_entry(conn, grp.id, "Clone", "git clone <url>")
    add_placeholder(conn, entry.id, "url", "Repository URL")
    with pytest.raises(ValueError, match="already exists"):
        add_placeholder(conn, entry.id, "url", "Duplicate")


def test_get_placeholders_empty(conn):
    sheet = create_sheet(conn, "git")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    entry = add_entry(conn, grp.id, "Status", "git status")
    assert get_placeholders(conn, entry.id) == []


def test_delete_placeholder(conn):
    sheet = create_sheet(conn, "git")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    entry = add_entry(conn, grp.id, "Clone", "git clone <url>")
    add_placeholder(conn, entry.id, "url", "Repository URL")
    delete_placeholder(conn, entry.id, "url")
    assert get_placeholders(conn, entry.id) == []


def test_delete_placeholder_not_found_raises(conn):
    sheet = create_sheet(conn, "git")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    entry = add_entry(conn, grp.id, "Status", "git status")
    with pytest.raises(ValueError, match="not found"):
        delete_placeholder(conn, entry.id, "missing")


def test_set_placeholders_replaces(conn):
    sheet = create_sheet(conn, "git")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    entry = add_entry(conn, grp.id, "Clone", "git clone <url> <dir>")
    set_placeholders(conn, entry.id, [
        {"name": "url", "description": "Repo URL"},
        {"name": "dir", "description": "Local dir"},
    ])
    phs = get_placeholders(conn, entry.id)
    assert [p.name for p in phs] == ["url", "dir"]
    set_placeholders(conn, entry.id, [{"name": "url", "description": "Updated"}])
    phs = get_placeholders(conn, entry.id)
    assert len(phs) == 1
    assert phs[0].description == "Updated"


def test_get_entries_hydrates_placeholders(conn):
    sheet = create_sheet(conn, "git")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    entry = add_entry(conn, grp.id, "Clone", "git clone <url> <dir>")
    set_placeholders(conn, entry.id, [
        {"name": "url", "description": "Repo URL"},
        {"name": "dir", "description": "Local dir"},
    ])
    entries = get_entries(conn, sheet.id)
    assert len(entries[0].placeholders) == 2
    assert entries[0].placeholders[0].name == "url"
    assert entries[0].placeholders[1].name == "dir"


def test_get_entries_no_placeholders_returns_empty_list(conn):
    sheet = create_sheet(conn, "git")
    grp = get_group(conn, sheet.id, DEFAULT_GROUP)
    add_entry(conn, grp.id, "Status", "git status")
    entries = get_entries(conn, sheet.id)
    assert entries[0].placeholders == []


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
