import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_GROUP = "default"


@dataclass
class CsvRow:
    group: str | None
    description: str
    command: str
    placeholders: list[dict] = field(default_factory=list)


@dataclass
class SheetFile:
    metadata: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    entries: list[CsvRow] = field(default_factory=list)


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
    from .store import get_group, add_entry, set_placeholders

    count = 0
    for row in rows:
        grp_name = row.group or DEFAULT_GROUP
        group = get_group(conn, sheet_id, grp_name)
        if group is None:
            continue
        entry = add_entry(conn, group.id, row.description, row.command)
        if row.placeholders:
            set_placeholders(conn, entry.id, row.placeholders)
        vector = embed_fn(f"{row.description} {row.command}")
        store_embedding_fn(conn, entry.id, vector)
        count += 1
        if progress is not None and task is not None:
            progress.advance(task)
    return count


def parse_toml(path: Path) -> SheetFile:
    import tomllib

    with open(path, "rb") as f:
        data = tomllib.load(f)

    metadata = {k: str(v) for k, v in data.get("metadata", {}).items()}
    params = {k: str(v) for k, v in data.get("params", {}).items()}

    entries: list[CsvRow] = []
    for i, row in enumerate(data.get("entries", []), start=1):
        if "description" not in row:
            raise ValueError(f"Entry {i} missing required field 'description'.")
        if "command" not in row:
            raise ValueError(f"Entry {i} missing required field 'command'.")
        desc = str(row["description"]).strip()
        cmd = str(row["command"]).strip()
        if not desc or not cmd:
            raise ValueError(f"Entry {i}: 'description' and 'command' must not be empty.")
        placeholders = []
        for j, ph in enumerate(row.get("placeholders", []), start=1):
            if "name" not in ph:
                raise ValueError(f"Entry {i} placeholder {j} missing required field 'name'.")
            placeholders.append({
                "name": str(ph["name"]),
                "description": str(ph.get("description", "")),
            })
        entries.append(CsvRow(
            group=str(row.get("group", "")).strip() or None,
            description=desc,
            command=cmd,
            placeholders=placeholders,
        ))

    return SheetFile(metadata=metadata, params=params, entries=entries)


def bulk_import_file(
    conn: sqlite3.Connection,
    sheet_id: int,
    sheet_name: str,
    sheet_file: SheetFile,
    embed_fn=None,
    store_embedding_fn=None,
) -> tuple[int, int, int]:
    from .store import add_metadata, add_param

    for k, v in sheet_file.metadata.items():
        add_metadata(conn, sheet_id, k, v)

    for k, v in sheet_file.params.items():
        add_param(conn, sheet_id, k, v)

    entry_count = 0
    if sheet_file.entries:
        entry_count = bulk_import(
            conn, sheet_id, sheet_name, sheet_file.entries, embed_fn, store_embedding_fn
        )

    return len(sheet_file.metadata), len(sheet_file.params), entry_count
