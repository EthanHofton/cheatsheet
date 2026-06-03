from collections import defaultdict

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import Entry, SearchResult, Sheet

console = Console()

DEFAULT_GROUP = "default"


def print_full_sheet(sheet_name: str, entries: list[Entry]) -> None:
    if not entries:
        console.print(f"[dim]No entries in '{sheet_name}'.[/]")
        return

    grouped: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.group_name].append(entry)

    sorted_groups = sorted(
        grouped.keys(),
        key=lambda g: (g != DEFAULT_GROUP, g),
    )

    renderables = []
    for group_name in sorted_groups:
        group_entries = grouped[group_name]
        label = Text(group_name.upper(), style="bold yellow")

        table = Table(box=box.SIMPLE_HEAD, show_header=True, pad_edge=False)
        table.add_column("Description", style="white", no_wrap=False)
        table.add_column("Command", style="bold cyan", no_wrap=False)

        for e in group_entries:
            table.add_row(e.description, e.command)

        renderables.append(label)
        renderables.append(table)

    from rich.console import Group as RenderGroup

    console.print(Panel(RenderGroup(*renderables), title=f"[bold]{sheet_name}[/]", expand=False))


def print_search_results(sheet_name: str, query: str, results: list[SearchResult]) -> None:
    console.print(f"\n[bold]Searching '[cyan]{sheet_name}[/]' for:[/] {query}\n")

    if not results:
        console.print("[dim]No results found.[/]")
        return

    table = Table(box=box.SIMPLE_HEAD, show_header=True)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Group", style="yellow")
    table.add_column("Description", style="white")
    table.add_column("Command", style="bold cyan")

    for result in results:
        score = 1.0 - result.distance
        if score > 0.8:
            score_style = "bold green"
        elif score > 0.6:
            score_style = "yellow"
        else:
            score_style = "red"
        table.add_row(
            Text(f"{score:.2f}", style=score_style),
            result.entry.group_name,
            result.entry.description,
            result.entry.command,
        )

    console.print(table)


def print_sheet_list(sheets: list[tuple[Sheet, int]]) -> None:
    if not sheets:
        console.print("[dim]No cheatsheets yet. Run [bold]cheatsheet new <name>[/] to create one.[/]")
        return

    table = Table(box=box.SIMPLE_HEAD, show_header=True)
    table.add_column("Sheet", style="bold cyan")
    table.add_column("Entries", justify="right")

    for sheet, count in sheets:
        table.add_row(sheet.name, str(count))

    console.print(table)


def print_error(message: str) -> None:
    console.print(f"[bold red]Error:[/] {message}")


def print_success(message: str) -> None:
    console.print(f"[bold green]✓[/] {message}")
