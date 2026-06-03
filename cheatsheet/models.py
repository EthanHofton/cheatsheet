from dataclasses import dataclass, field


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
class Placeholder:
    name: str
    description: str


@dataclass
class Entry:
    id: int
    group_id: int
    group_name: str
    sheet_name: str
    description: str
    command: str
    created_at: str
    placeholders: list[Placeholder] = field(default_factory=list)


@dataclass
class SearchResult:
    entry: Entry
    distance: float
