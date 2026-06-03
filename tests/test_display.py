import io

from rich.console import Console

from cheatsheet.display import print_full_sheet, print_search_results, print_sheet_list
from cheatsheet.models import Entry, SearchResult, Sheet


def capture(fn, *args, **kwargs) -> str:
    buf = io.StringIO()
    c = Console(file=buf, highlight=False, markup=False)
    import cheatsheet.display as d
    original = d.console
    d.console = c
    try:
        fn(*args, **kwargs)
    finally:
        d.console = original
    return buf.getvalue()


def make_entry(id, group_name, description, command, sheet_name="tmux"):
    return Entry(
        id=id,
        group_id=1,
        group_name=group_name,
        sheet_name=sheet_name,
        description=description,
        command=command,
        created_at="2024-01-01",
    )


def test_print_full_sheet_default_group_first():
    entries = [
        make_entry(1, "pane", "Kill pane", "Ctrl+B x"),
        make_entry(2, "default", "New window", "Ctrl+B c"),
    ]
    output = capture(print_full_sheet, "tmux", entries)
    default_pos = output.find("DEFAULT")
    pane_pos = output.find("PANE")
    assert default_pos < pane_pos, "default group should appear before pane"


def test_print_full_sheet_empty():
    output = capture(print_full_sheet, "tmux", [])
    assert "No entries" in output


def test_print_search_results_shows_score():
    entry = make_entry(1, "pane", "Kill pane", "Ctrl+B x")
    results = [SearchResult(entry=entry, distance=0.1)]
    output = capture(print_search_results, results)
    assert "0.90" in output


def test_print_search_results_empty():
    output = capture(print_search_results, [])
    assert "No results" in output


def test_print_sheet_list_shows_names():
    sheets = [(Sheet(id=1, name="tmux", created_at="2024-01-01"), 5)]
    output = capture(print_sheet_list, sheets)
    assert "tmux" in output
    assert "5" in output


def test_print_sheet_list_empty():
    output = capture(print_sheet_list, [])
    assert "No cheatsheets" in output
