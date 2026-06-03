from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cheatsheet.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "cheatsheet.db"
    monkeypatch.setattr("cheatsheet.cli.get_connection", lambda: _open_conn(db_path))
    monkeypatch.setattr("cheatsheet.store.get_connection", lambda: _open_conn(db_path))
    return db_path


def _open_conn(db_path: Path):
    import sqlite3
    from cheatsheet.db import _bootstrap_schema
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    _bootstrap_schema(c)
    return c


def _patch_embed(monkeypatch):
    import numpy as np
    rng = np.random.default_rng(0)
    def fake_embed(text):
        v = rng.random(384).astype(float).tolist()
        return v
    monkeypatch.setattr("cheatsheet.cli.store_embedding", lambda conn, eid, vec: None)
    monkeypatch.setattr("cheatsheet.embeddings.embed", fake_embed)


def test_smart_group_routes_sheet_name(runner, tmp_path, monkeypatch, mock_embedder):
    db_path = tmp_path / "cs.db"

    def fake_conn():
        return _open_conn(db_path)

    monkeypatch.setattr("cheatsheet.cli.get_connection", fake_conn)

    result = runner.invoke(cli, ["new", "tmux"])
    assert result.exit_code == 0

    result = runner.invoke(cli, ["tmux"])
    assert result.exit_code == 0
    assert "tmux" in result.output


def test_new_errors_on_duplicate(runner, tmp_path, monkeypatch):
    db_path = tmp_path / "cs.db"
    monkeypatch.setattr("cheatsheet.cli.get_connection", lambda: _open_conn(db_path))
    runner.invoke(cli, ["new", "tmux"])
    result = runner.invoke(cli, ["new", "tmux"])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_new_errors_on_reserved_name(runner, tmp_path, monkeypatch):
    db_path = tmp_path / "cs.db"
    monkeypatch.setattr("cheatsheet.cli.get_connection", lambda: _open_conn(db_path))
    result = runner.invoke(cli, ["new", "add"])
    assert result.exit_code != 0
    assert "reserved" in result.output


def test_group_errors_on_unknown_sheet(runner, tmp_path, monkeypatch):
    db_path = tmp_path / "cs.db"
    monkeypatch.setattr("cheatsheet.cli.get_connection", lambda: _open_conn(db_path))
    result = runner.invoke(cli, ["group", "tmux", "pane"])
    assert result.exit_code != 0
    assert "No cheatsheet" in result.output


def test_add_unknown_group_gives_helpful_error(runner, tmp_path, monkeypatch, mock_embedder):
    db_path = tmp_path / "cs.db"
    monkeypatch.setattr("cheatsheet.cli.get_connection", lambda: _open_conn(db_path))
    runner.invoke(cli, ["new", "tmux"])
    result = runner.invoke(cli, ["add", "tmux", "Kill pane", "Ctrl+B x", "--group", "pane"])
    assert result.exit_code != 0
    assert "cheatsheet group" in result.output


def test_add_no_args_gives_usage_error(runner, tmp_path, monkeypatch):
    db_path = tmp_path / "cs.db"
    monkeypatch.setattr("cheatsheet.cli.get_connection", lambda: _open_conn(db_path))
    runner.invoke(cli, ["new", "tmux"])
    result = runner.invoke(cli, ["add", "tmux"])
    assert result.exit_code != 0


def test_list_shows_sheet_names(runner, tmp_path, monkeypatch):
    db_path = tmp_path / "cs.db"
    monkeypatch.setattr("cheatsheet.cli.get_connection", lambda: _open_conn(db_path))
    runner.invoke(cli, ["new", "tmux"])
    runner.invoke(cli, ["new", "git"])
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "tmux" in result.output
    assert "git" in result.output


def test_delete_with_yes_flag_skips_prompt(runner, tmp_path, monkeypatch):
    db_path = tmp_path / "cs.db"
    monkeypatch.setattr("cheatsheet.cli.get_connection", lambda: _open_conn(db_path))
    runner.invoke(cli, ["new", "tmux"])
    result = runner.invoke(cli, ["delete", "tmux", "--yes"])
    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_delete_unknown_sheet_errors(runner, tmp_path, monkeypatch):
    db_path = tmp_path / "cs.db"
    monkeypatch.setattr("cheatsheet.cli.get_connection", lambda: _open_conn(db_path))
    result = runner.invoke(cli, ["delete", "tmux", "--yes"])
    assert result.exit_code != 0
