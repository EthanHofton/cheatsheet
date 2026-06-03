import sqlite3
import struct
from typing import Optional


from .models import Entry, Group, Placeholder, Sheet

DEFAULT_GROUP = "default"
RESERVED_NAMES = frozenset({"show", "new", "list", "delete"})


# ---------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------


def create_sheet(conn: sqlite3.Connection, name: str) -> Sheet:
    if name in RESERVED_NAMES:
        raise ValueError(f"'{name}' is a reserved name; choose another.")
    try:
        cur = conn.execute(
            "INSERT INTO sheets (name) VALUES (?) RETURNING id, name, created_at",
            [name],
        )
        row = cur.fetchone()
        sheet = Sheet(id=row["id"], name=row["name"], created_at=row["created_at"])
    except sqlite3.IntegrityError:
        raise ValueError(f"Cheatsheet '{name}' already exists.")

    conn.execute("INSERT INTO groups (sheet_id, name) VALUES (?, ?)", [sheet.id, DEFAULT_GROUP])
    conn.commit()
    return sheet


def get_sheet(conn: sqlite3.Connection, name: str) -> Optional[Sheet]:
    row = conn.execute("SELECT id, name, created_at FROM sheets WHERE name = ?", [name]).fetchone()
    if row is None:
        return None
    return Sheet(id=row["id"], name=row["name"], created_at=row["created_at"])


def list_sheets(conn: sqlite3.Connection) -> list[tuple[Sheet, int]]:
    rows = conn.execute(
        """
        SELECT s.id, s.name, s.created_at, COUNT(e.id) AS entry_count
        FROM sheets s
        LEFT JOIN groups g ON g.sheet_id = s.id
        LEFT JOIN entries e ON e.group_id = g.id
        GROUP BY s.id
        ORDER BY s.name
        """
    ).fetchall()
    return [
        (Sheet(id=r["id"], name=r["name"], created_at=r["created_at"]), r["entry_count"])
        for r in rows
    ]


def delete_sheet(conn: sqlite3.Connection, name: str) -> bool:
    sheet = get_sheet(conn, name)
    if sheet is None:
        return False
    conn.execute(
        """
        DELETE FROM entry_embeddings
        WHERE entry_id IN (
            SELECT e.id FROM entries e
            JOIN groups g ON g.id = e.group_id
            WHERE g.sheet_id = ?
        )
        """,
        [sheet.id],
    )
    conn.execute("DELETE FROM sheets WHERE id = ?", [sheet.id])
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


def create_group(conn: sqlite3.Connection, sheet_id: int, name: str) -> Group:
    if name == DEFAULT_GROUP:
        raise ValueError("'default' is a reserved group name.")
    try:
        cur = conn.execute(
            "INSERT INTO groups (sheet_id, name) VALUES (?, ?) RETURNING id, sheet_id, name, created_at",
            [sheet_id, name],
        )
        row = cur.fetchone()
        conn.commit()
        return Group(id=row["id"], sheet_id=row["sheet_id"], name=row["name"], created_at=row["created_at"])
    except sqlite3.IntegrityError:
        raise ValueError(f"Group '{name}' already exists in this cheatsheet.")


def get_group(conn: sqlite3.Connection, sheet_id: int, name: str) -> Optional[Group]:
    row = conn.execute(
        "SELECT id, sheet_id, name, created_at FROM groups WHERE sheet_id = ? AND name = ?",
        [sheet_id, name],
    ).fetchone()
    if row is None:
        return None
    return Group(id=row["id"], sheet_id=row["sheet_id"], name=row["name"], created_at=row["created_at"])


def list_groups(conn: sqlite3.Connection, sheet_id: int) -> list[Group]:
    rows = conn.execute(
        "SELECT id, sheet_id, name, created_at FROM groups WHERE sheet_id = ? ORDER BY name",
        [sheet_id],
    ).fetchall()
    return [Group(id=r["id"], sheet_id=r["sheet_id"], name=r["name"], created_at=r["created_at"]) for r in rows]


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------


def add_entry(conn: sqlite3.Connection, group_id: int, description: str, command: str) -> Entry:
    cur = conn.execute(
        """
        INSERT INTO entries (group_id, description, command)
        VALUES (?, ?, ?)
        RETURNING id, group_id, description, command, created_at
        """,
        [group_id, description, command],
    )
    row = cur.fetchone()
    group_row = conn.execute(
        "SELECT g.name as gname, s.name as sname FROM groups g JOIN sheets s ON s.id = g.sheet_id WHERE g.id = ?",
        [group_id],
    ).fetchone()
    conn.commit()
    return Entry(
        id=row["id"],
        group_id=row["group_id"],
        group_name=group_row["gname"],
        sheet_name=group_row["sname"],
        description=row["description"],
        command=row["command"],
        created_at=row["created_at"],
    )


def store_embedding(conn: sqlite3.Connection, entry_id: int, vector: list[float]) -> None:
    blob = struct.pack(f"{len(vector)}f", *vector)
    conn.execute(
        "INSERT OR REPLACE INTO entry_embeddings (entry_id, embedding) VALUES (?, ?)",
        [entry_id, blob],
    )
    conn.commit()


def load_embeddings(conn: sqlite3.Connection, sheet_id: int) -> list[tuple[int, list[float]]]:
    rows = conn.execute(
        """
        SELECT emb.entry_id, emb.embedding
        FROM entry_embeddings emb
        JOIN entries e ON e.id = emb.entry_id
        JOIN groups g  ON g.id = e.group_id
        WHERE g.sheet_id = ?
        """,
        [sheet_id],
    ).fetchall()
    result = []
    for r in rows:
        n = len(r["embedding"]) // 4
        vec = list(struct.unpack(f"{n}f", r["embedding"]))
        result.append((r["entry_id"], vec))
    return result


def get_entry_by_id(conn: sqlite3.Connection, entry_id: int) -> Optional[Entry]:
    row = conn.execute(
        """
        SELECT e.id, e.group_id, g.name AS group_name, s.name AS sheet_name,
               e.description, e.command, e.created_at
        FROM entries e
        JOIN groups g ON g.id = e.group_id
        JOIN sheets s ON s.id = g.sheet_id
        WHERE e.id = ?
        """,
        [entry_id],
    ).fetchone()
    if row is None:
        return None
    entry = Entry(
        id=row["id"],
        group_id=row["group_id"],
        group_name=row["group_name"],
        sheet_name=row["sheet_name"],
        description=row["description"],
        command=row["command"],
        created_at=row["created_at"],
    )
    _hydrate_placeholders(conn, [entry])
    return entry


def delete_entry(conn: sqlite3.Connection, entry_id: int) -> bool:
    conn.execute("DELETE FROM entry_embeddings WHERE entry_id = ?", [entry_id])
    cur = conn.execute("DELETE FROM entries WHERE id = ?", [entry_id])
    conn.commit()
    return cur.rowcount > 0


def update_entry(
    conn: sqlite3.Connection,
    entry_id: int,
    description: Optional[str] = None,
    command: Optional[str] = None,
    group_id: Optional[int] = None,
) -> Entry:
    if description is not None:
        conn.execute("UPDATE entries SET description = ? WHERE id = ?", [description, entry_id])
    if command is not None:
        conn.execute("UPDATE entries SET command = ? WHERE id = ?", [command, entry_id])
    if group_id is not None:
        conn.execute("UPDATE entries SET group_id = ? WHERE id = ?", [group_id, entry_id])
    conn.commit()
    entry = get_entry_by_id(conn, entry_id)
    if entry is None:
        raise ValueError(f"Entry {entry_id} not found after update.")
    return entry


def get_entries(
    conn: sqlite3.Connection,
    sheet_id: int,
    group_name: Optional[str] = None,
) -> list[Entry]:
    if group_name is not None:
        rows = conn.execute(
            """
            SELECT e.id, e.group_id, g.name AS group_name, s.name AS sheet_name,
                   e.description, e.command, e.created_at
            FROM entries e
            JOIN groups g ON g.id = e.group_id
            JOIN sheets s ON s.id = g.sheet_id
            WHERE g.sheet_id = ? AND g.name = ?
            ORDER BY e.id
            """,
            [sheet_id, group_name],
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT e.id, e.group_id, g.name AS group_name, s.name AS sheet_name,
                   e.description, e.command, e.created_at
            FROM entries e
            JOIN groups g ON g.id = e.group_id
            JOIN sheets s ON s.id = g.sheet_id
            WHERE g.sheet_id = ?
            ORDER BY g.name, e.id
            """,
            [sheet_id],
        ).fetchall()
    entries = [
        Entry(
            id=r["id"],
            group_id=r["group_id"],
            group_name=r["group_name"],
            sheet_name=r["sheet_name"],
            description=r["description"],
            command=r["command"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
    _hydrate_placeholders(conn, entries)
    return entries


def _hydrate_placeholders(conn: sqlite3.Connection, entries: list[Entry]) -> None:
    if not entries:
        return
    ids = [e.id for e in entries]
    ph_rows = conn.execute(
        f"SELECT entry_id, name, description FROM entry_placeholders "
        f"WHERE entry_id IN ({','.join('?' * len(ids))}) ORDER BY entry_id, position",
        ids,
    ).fetchall()
    by_entry: dict[int, list[Placeholder]] = {}
    for row in ph_rows:
        by_entry.setdefault(row["entry_id"], []).append(
            Placeholder(name=row["name"], description=row["description"])
        )
    for entry in entries:
        entry.placeholders = by_entry.get(entry.id, [])


# ---------------------------------------------------------------------------
# Params
# ---------------------------------------------------------------------------

def _kv_add(conn: sqlite3.Connection, table: str, sheet_id: int, key: str, value: str) -> None:
    try:
        conn.execute(f"INSERT INTO {table} (sheet_id, key, value) VALUES (?, ?, ?)", [sheet_id, key, value])
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"'{key}' already exists. Use edit to change it.")


def _kv_edit(conn: sqlite3.Connection, table: str, sheet_id: int, key: str, value: str) -> None:
    cur = conn.execute(f"UPDATE {table} SET value = ? WHERE sheet_id = ? AND key = ?", [value, sheet_id, key])
    conn.commit()
    if cur.rowcount == 0:
        raise ValueError(f"'{key}' not found. Use add to create it.")


def _kv_delete(conn: sqlite3.Connection, table: str, sheet_id: int, key: str) -> None:
    cur = conn.execute(f"DELETE FROM {table} WHERE sheet_id = ? AND key = ?", [sheet_id, key])
    conn.commit()
    if cur.rowcount == 0:
        raise ValueError(f"'{key}' not found.")


def _kv_get_all(conn: sqlite3.Connection, table: str, sheet_id: int) -> dict[str, str]:
    rows = conn.execute(f"SELECT key, value FROM {table} WHERE sheet_id = ? ORDER BY key", [sheet_id]).fetchall()
    return {r["key"]: r["value"] for r in rows}


def add_param(conn: sqlite3.Connection, sheet_id: int, key: str, value: str) -> None:
    _kv_add(conn, "sheet_params", sheet_id, key, value)

def edit_param(conn: sqlite3.Connection, sheet_id: int, key: str, value: str) -> None:
    _kv_edit(conn, "sheet_params", sheet_id, key, value)

def delete_param(conn: sqlite3.Connection, sheet_id: int, key: str) -> None:
    _kv_delete(conn, "sheet_params", sheet_id, key)

def get_params(conn: sqlite3.Connection, sheet_id: int) -> dict[str, str]:
    return _kv_get_all(conn, "sheet_params", sheet_id)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Placeholders
# ---------------------------------------------------------------------------


def add_placeholder(
    conn: sqlite3.Connection, entry_id: int, name: str, description: str
) -> Placeholder:
    row = conn.execute(
        "SELECT COALESCE(MAX(position) + 1, 0) AS next_pos FROM entry_placeholders WHERE entry_id = ?",
        [entry_id],
    ).fetchone()
    position = row["next_pos"]
    try:
        conn.execute(
            "INSERT INTO entry_placeholders (entry_id, name, description, position) VALUES (?, ?, ?, ?)",
            [entry_id, name, description, position],
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"Placeholder '{name}' already exists for this entry.")
    return Placeholder(name=name, description=description)


def delete_placeholder(conn: sqlite3.Connection, entry_id: int, name: str) -> None:
    cur = conn.execute(
        "DELETE FROM entry_placeholders WHERE entry_id = ? AND name = ?",
        [entry_id, name],
    )
    conn.commit()
    if cur.rowcount == 0:
        raise ValueError(f"Placeholder '{name}' not found.")


def get_placeholders(conn: sqlite3.Connection, entry_id: int) -> list[Placeholder]:
    rows = conn.execute(
        "SELECT name, description FROM entry_placeholders WHERE entry_id = ? ORDER BY position",
        [entry_id],
    ).fetchall()
    return [Placeholder(name=r["name"], description=r["description"]) for r in rows]


def set_placeholders(
    conn: sqlite3.Connection, entry_id: int, placeholders: list[dict]
) -> None:
    conn.execute("DELETE FROM entry_placeholders WHERE entry_id = ?", [entry_id])
    for i, ph in enumerate(placeholders):
        conn.execute(
            "INSERT INTO entry_placeholders (entry_id, name, description, position) VALUES (?, ?, ?, ?)",
            [entry_id, ph["name"], ph.get("description", ""), i],
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


def add_metadata(conn: sqlite3.Connection, sheet_id: int, key: str, value: str) -> None:
    _kv_add(conn, "sheet_metadata", sheet_id, key, value)

def edit_metadata(conn: sqlite3.Connection, sheet_id: int, key: str, value: str) -> None:
    _kv_edit(conn, "sheet_metadata", sheet_id, key, value)

def delete_metadata(conn: sqlite3.Connection, sheet_id: int, key: str) -> None:
    _kv_delete(conn, "sheet_metadata", sheet_id, key)

def get_metadata(conn: sqlite3.Connection, sheet_id: int) -> dict[str, str]:
    return _kv_get_all(conn, "sheet_metadata", sheet_id)
