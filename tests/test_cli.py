from pathlib import Path

import pytest
from click.testing import CliRunner

from cheatsheet.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def _open_conn(db_path: Path):
    import sqlite3
    from cheatsheet.db import _bootstrap_schema
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    _bootstrap_schema(c)
    return c


def _db(tmp_path, monkeypatch):
    db_path = tmp_path / "cs.db"
    monkeypatch.setattr("cheatsheet.cli.get_connection", lambda: _open_conn(db_path))
    return db_path


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def test_smart_group_routes_sheet_name(runner, tmp_path, monkeypatch, mock_embedder):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    result = runner.invoke(cli, ["tmux"])
    assert result.exit_code == 0
    assert "tmux" in result.output


# ---------------------------------------------------------------------------
# new / list / delete
# ---------------------------------------------------------------------------

def test_new_errors_on_duplicate(runner, tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    result = runner.invoke(cli, ["new", "tmux"])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_new_errors_on_reserved_name(runner, tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["new", "list"])
    assert result.exit_code != 0
    assert "reserved" in result.output


def test_list_shows_sheet_names(runner, tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    runner.invoke(cli, ["new", "git"])
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "tmux" in result.output
    assert "git" in result.output


def test_delete_with_yes_flag(runner, tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    result = runner.invoke(cli, ["delete", "tmux", "--yes"])
    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_delete_unknown_sheet_errors(runner, tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["delete", "tmux", "--yes"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# entry subcommands
# ---------------------------------------------------------------------------

def test_entry_add_single(runner, tmp_path, monkeypatch, mock_embedder):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    result = runner.invoke(cli, ["tmux", "entry", "add", "Kill pane", "Ctrl-A x"])
    assert result.exit_code == 0
    assert "Added" in result.output


def test_entry_add_unknown_group_gives_helpful_error(runner, tmp_path, monkeypatch, mock_embedder):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    result = runner.invoke(cli, ["tmux", "entry", "add", "Kill pane", "Ctrl-A x", "--group", "pane"])
    assert result.exit_code != 0
    assert "group add" in result.output


def test_entry_add_no_args_gives_usage_error(runner, tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    result = runner.invoke(cli, ["tmux", "entry", "add"])
    assert result.exit_code != 0


def test_entry_update(runner, tmp_path, monkeypatch, mock_embedder):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    runner.invoke(cli, ["tmux", "entry", "add", "Kill pane", "Ctrl-A x"])
    # get the entry id from the sheet display
    result = runner.invoke(cli, ["tmux"])
    assert result.exit_code == 0
    # update by known id (1 for first entry in fresh db)
    result = runner.invoke(cli, ["tmux", "entry", "update", "1", "--description", "Close pane"])
    assert result.exit_code == 0


def test_entry_delete(runner, tmp_path, monkeypatch, mock_embedder):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    runner.invoke(cli, ["tmux", "entry", "add", "Kill pane", "Ctrl-A x"])
    result = runner.invoke(cli, ["tmux", "entry", "delete", "1", "--yes"])
    assert result.exit_code == 0
    assert "Deleted" in result.output


# ---------------------------------------------------------------------------
# group subcommands
# ---------------------------------------------------------------------------

def test_group_add(runner, tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    result = runner.invoke(cli, ["tmux", "group", "add", "pane"])
    assert result.exit_code == 0
    assert "Added" in result.output


def test_group_add_errors_on_unknown_sheet(runner, tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["tmux", "group", "add", "pane"])
    assert result.exit_code != 0
    assert "No cheatsheet" in result.output


# ---------------------------------------------------------------------------
# query subcommand
# ---------------------------------------------------------------------------

def test_query_subcommand(runner, tmp_path, monkeypatch, mock_embedder):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    runner.invoke(cli, ["tmux", "entry", "add", "Kill pane", "Ctrl-A x"])
    result = runner.invoke(cli, ["tmux", "query", "kill"])
    assert result.exit_code == 0


def test_query_top_k(runner, tmp_path, monkeypatch, mock_embedder):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    for i in range(5):
        runner.invoke(cli, ["tmux", "entry", "add", f"Entry {i}", f"cmd {i}"])
    result = runner.invoke(cli, ["tmux", "query", "entry", "--top-k", "2"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# meta / params subcommands
# ---------------------------------------------------------------------------

def test_meta_add_edit_delete(runner, tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    result = runner.invoke(cli, ["tmux", "meta", "add", "desc", "my tmux"])
    assert result.exit_code == 0
    result = runner.invoke(cli, ["tmux", "meta", "edit", "desc", "updated"])
    assert result.exit_code == 0
    result = runner.invoke(cli, ["tmux", "meta", "delete", "desc"])
    assert result.exit_code == 0


def test_params_add_edit_delete(runner, tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    result = runner.invoke(cli, ["tmux", "params", "add", "leader", "Ctrl-A"])
    assert result.exit_code == 0
    result = runner.invoke(cli, ["tmux", "params", "edit", "leader", "Ctrl-B"])
    assert result.exit_code == 0
    result = runner.invoke(cli, ["tmux", "params", "delete", "leader"])
    assert result.exit_code == 0


def test_meta_add_duplicate_errors(runner, tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    runner.invoke(cli, ["new", "tmux"])
    runner.invoke(cli, ["tmux", "meta", "add", "desc", "x"])
    result = runner.invoke(cli, ["tmux", "meta", "add", "desc", "y"])
    assert result.exit_code != 0
    assert "already exists" in result.output
