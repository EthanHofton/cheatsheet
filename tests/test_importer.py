from pathlib import Path

import pytest

from cheatsheet.importer import CsvRow, SheetFile, bulk_import, bulk_import_file, parse_toml
from cheatsheet.store import create_sheet, get_entries, get_metadata, get_params
from cheatsheet.store import DEFAULT_GROUP


def write_toml(tmp_path, content: str) -> Path:
    p = tmp_path / "test.toml"
    p.write_text(content, encoding="utf-8")
    return p


def test_parse_toml_full(tmp_path):
    path = write_toml(tmp_path, """
[metadata]
desc = "Tmux reference"

[params]
leader = "Ctrl-A"

[[entries]]
group = "pane"
description = "Kill pane"
command = "{leader} x"

[[entries]]
description = "New window"
command = "{leader} c"
""")
    sf = parse_toml(path)
    assert sf.metadata == {"desc": "Tmux reference"}
    assert sf.params == {"leader": "Ctrl-A"}
    assert len(sf.entries) == 2
    assert sf.entries[0].group == "pane"
    assert sf.entries[1].group is None


def test_parse_toml_entries_only(tmp_path):
    path = write_toml(tmp_path, """
[[entries]]
description = "Status"
command = "git status"
""")
    sf = parse_toml(path)
    assert sf.metadata == {}
    assert sf.params == {}
    assert len(sf.entries) == 1


def test_parse_toml_metadata_and_params_only(tmp_path):
    path = write_toml(tmp_path, """
[metadata]
desc = "reference"

[params]
leader = "Ctrl-A"
""")
    sf = parse_toml(path)
    assert sf.metadata == {"desc": "reference"}
    assert sf.params == {"leader": "Ctrl-A"}
    assert sf.entries == []


def test_parse_toml_missing_description_raises(tmp_path):
    path = write_toml(tmp_path, """
[[entries]]
command = "git status"
""")
    with pytest.raises(ValueError, match="description"):
        parse_toml(path)


def test_parse_toml_missing_command_raises(tmp_path):
    path = write_toml(tmp_path, """
[[entries]]
description = "Status"
""")
    with pytest.raises(ValueError, match="command"):
        parse_toml(path)


def test_parse_toml_empty_description_raises(tmp_path):
    path = write_toml(tmp_path, """
[[entries]]
description = ""
command = "git status"
""")
    with pytest.raises(ValueError, match="empty"):
        parse_toml(path)


def test_bulk_import_inserts_correct_count(conn, mock_embedder):
    sheet = create_sheet(conn, "tmux")
    rows = [
        CsvRow(group="pane", description="Kill pane", command="Ctrl+B x"),
        CsvRow(group=None, description="New window", command="Ctrl+B c"),
    ]
    count = bulk_import(conn, sheet.id, sheet.name, rows)
    assert count == 2


def test_bulk_import_auto_creates_groups(conn, mock_embedder):
    sheet = create_sheet(conn, "tmux")
    rows = [
        CsvRow(group="pane", description="Kill pane", command="Ctrl+B x"),
        CsvRow(group="session", description="New session", command="tmux new"),
    ]
    bulk_import(conn, sheet.id, sheet.name, rows)
    assert len(get_entries(conn, sheet.id, group_name="pane")) == 1
    assert len(get_entries(conn, sheet.id, group_name="session")) == 1


def test_bulk_import_file_imports_all(conn, mock_embedder):
    sheet = create_sheet(conn, "tmux")
    sf = SheetFile(
        metadata={"desc": "my sheet"},
        params={"leader": "Ctrl-A"},
        entries=[CsvRow(group=None, description="New window", command="{leader} c")],
    )
    meta_n, param_n, entry_n = bulk_import_file(conn, sheet.id, sheet.name, sf)
    assert meta_n == 1
    assert param_n == 1
    assert entry_n == 1
    assert get_metadata(conn, sheet.id) == {"desc": "my sheet"}
    assert get_params(conn, sheet.id) == {"leader": "Ctrl-A"}
    assert len(get_entries(conn, sheet.id)) == 1


def test_bulk_import_file_empty_sheet_file(conn, mock_embedder):
    sheet = create_sheet(conn, "tmux")
    meta_n, param_n, entry_n = bulk_import_file(conn, sheet.id, sheet.name, SheetFile())
    assert meta_n == 0
    assert param_n == 0
    assert entry_n == 0
