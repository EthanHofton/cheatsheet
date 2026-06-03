from dataclasses import dataclass


@dataclass
class Sheet:
    id: int
    name: str
    created_at: str


@dataclass
class Group:
    id: int
    sheet_id: int
    name: str
    created_at: str


@dataclass
class Entry:
    id: int
    group_id: int
    group_name: str
    sheet_name: str
    description: str
    command: str
    created_at: str


@dataclass
class SearchResult:
    entry: Entry
    distance: float
