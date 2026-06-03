import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

DEFAULT_GROUP = "default"


@dataclass
class CsvRow:
    group: str | None
    description: str
    command: str


def parse_csv(path: Path) -> list[CsvRow]:
    rows: list[CsvRow] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV file is empty.")

        normalised = {h.strip().lower() for h in reader.fieldnames}
        if "description" not in normalised or "command" not in normalised:
            raise ValueError("CSV must have 'description' and 'command' headers.")

        for i, raw in enumerate(reader, start=2):
            desc = raw.get("description", "").strip()
            cmd = raw.get("command", "").strip()
            grp = raw.get("group", "").strip() or None

            if not desc or not cmd:
                raise ValueError(f"Row {i}: 'description' and 'command' must not be empty.")

            rows.append(CsvRow(group=grp, description=desc, command=cmd))

    return rows


def bulk_import(
    conn: sqlite3.Connection,
    sheet_id: int,
    sheet_name: str,
    rows: list[CsvRow],
    embed_fn=None,
    store_embedding_fn=None,
) -> int:
    from .store import create_group, get_group, add_entry, store_embedding
    from .embeddings import embed

    if embed_fn is None:
        embed_fn = embed
    if store_embedding_fn is None:
        store_embedding_fn = store_embedding

    distinct_groups = {r.group for r in rows if r.group is not None}
    for grp_name in distinct_groups:
        if get_group(conn, sheet_id, grp_name) is None:
            try:
                create_group(conn, sheet_id, grp_name)
            except ValueError:
                pass

    try:
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task(f"Importing into '{sheet_name}'...", total=len(rows))
            count = _do_insert(conn, sheet_id, rows, embed_fn, store_embedding_fn, progress, task)
    except Exception:
        count = _do_insert(conn, sheet_id, rows, embed_fn, store_embedding_fn, None, None)

    return count


def _do_insert(conn, sheet_id, rows, embed_fn, store_embedding_fn, progress, task):
    from .store import get_group, add_entry

    count = 0
    for row in rows:
        grp_name = row.group or DEFAULT_GROUP
        group = get_group(conn, sheet_id, grp_name)
        if group is None:
            continue
        entry = add_entry(conn, group.id, row.description, row.command)
        vector = embed_fn(f"{row.description} {row.command}")
        store_embedding_fn(conn, entry.id, vector)
        count += 1
        if progress is not None and task is not None:
            progress.advance(task)
    return count
