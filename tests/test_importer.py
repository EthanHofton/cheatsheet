import csv
import io
from pathlib import Path

import pytest

from cheatsheet.importer import CsvRow, bulk_import, parse_csv
from cheatsheet.store import create_sheet, get_entries, get_group
from cheatsheet.store import DEFAULT_GROUP


def write_csv(tmp_path, content: str) -> Path:
    p = tmp_path / "test.csv"
    p.write_text(content, encoding="utf-8")
    return p


def test_parse_csv_valid(tmp_path):
    path = write_csv(tmp_path, "group,description,command\npane,Kill pane,Ctrl+B x\n")
    rows = parse_csv(path)
    assert len(rows) == 1
    assert rows[0].group == "pane"
    assert rows[0].description == "Kill pane"
    assert rows[0].command == "Ctrl+B x"


def test_parse_csv_empty_group_becomes_none(tmp_path):
    path = write_csv(tmp_path, "group,description,command\n,New window,Ctrl+B c\n")
    rows = parse_csv(path)
    assert rows[0].group is None


def test_parse_csv_missing_group_column(tmp_path):
    path = write_csv(tmp_path, "description,command\nKill pane,Ctrl+B x\n")
    rows = parse_csv(path)
    assert rows[0].group is None


def test_parse_csv_missing_required_headers(tmp_path):
    path = write_csv(tmp_path, "group,description\npane,Kill pane\n")
    with pytest.raises(ValueError, match="command"):
        parse_csv(path)


def test_parse_csv_empty_description_raises(tmp_path):
    path = write_csv(tmp_path, "group,description,command\npane,,Ctrl+B x\n")
    with pytest.raises(ValueError, match="Row 2"):
        parse_csv(path)


def test_bulk_import_inserts_correct_count(conn, mock_embedder, tmp_path):
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
    pane_entries = get_entries(conn, sheet.id, group_name="pane")
    assert len(pane_entries) == 1
    session_entries = get_entries(conn, sheet.id, group_name="session")
    assert len(session_entries) == 1
