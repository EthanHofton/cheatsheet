from collections import defaultdict

from rich import box
from rich.console import Console, Group as RenderGroup
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import Entry, SearchResult, Sheet

console = Console()

DEFAULT_GROUP = "default"


def _apply_params(text: str, params: dict[str, str]) -> str:
    for key, value in params.items():
        text = text.replace(f"{{{key}}}", value)
    return text


def print_full_sheet(
    sheet_name: str,
    entries: list[Entry],
    metadata: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> None:
    params = params or {}
    metadata = metadata or {}
    renderables = []

    if metadata:
        meta_table = Table(box=box.SIMPLE_HEAD, show_header=False, pad_edge=False)
        meta_table.add_column("Key", style="dim")
        meta_table.add_column("Value", style="white")
        for k, v in metadata.items():
            meta_table.add_row(k, v)
        renderables.append(meta_table)

    if not entries:
        if not metadata:
            console.print(f"[dim]No entries in '{sheet_name}'.[/]")
            return
    else:
        grouped: dict[str, list[Entry]] = defaultdict(list)
        for entry in entries:
            grouped[entry.group_name].append(entry)

        sorted_groups = sorted(grouped.keys(), key=lambda g: (g != DEFAULT_GROUP, g))

        for group_name in sorted_groups:
            group_entries = grouped[group_name]
            renderables.append(Text(group_name.upper(), style="bold yellow"))

            table = Table(box=box.SIMPLE_HEAD, show_header=True, pad_edge=False)
            table.add_column("ID", style="dim", width=5, justify="right")
            table.add_column("Description", style="white", no_wrap=False)
            table.add_column("Command", style="bold cyan", no_wrap=False)

            for e in group_entries:
                table.add_row(str(e.id), e.description, _apply_params(e.command, params))

            renderables.append(table)

    console.print(Panel(RenderGroup(*renderables), title=f"[bold]{sheet_name}[/]", expand=False))


def print_metadata_only(sheet_name: str, metadata: dict[str, str], params: dict[str, str]) -> None:
    renderables = []

    if metadata:
        renderables.append(Text("METADATA", style="bold yellow"))
        t = Table(box=box.SIMPLE_HEAD, show_header=False, pad_edge=False)
        t.add_column("Key", style="dim")
        t.add_column("Value", style="white")
        for k, v in metadata.items():
            t.add_row(k, v)
        renderables.append(t)

    if params:
        renderables.append(Text("PARAMS", style="bold yellow"))
        t = Table(box=box.SIMPLE_HEAD, show_header=False, pad_edge=False)
        t.add_column("Key", style="dim")
        t.add_column("Value", style="bold cyan")
        for k, v in params.items():
            t.add_row(f"{{{k}}}", v)
        renderables.append(t)

    if not renderables:
        console.print(f"[dim]No metadata or params set for '{sheet_name}'.[/]")
        return

    console.print(Panel(RenderGroup(*renderables), title=f"[bold]{sheet_name}[/] — info", expand=False))


def print_kv_table(title: str, data: dict[str, str], value_style: str = "white") -> None:
    if not data:
        console.print(f"[dim]No {title.lower()} set.[/]")
        return
    table = Table(box=box.SIMPLE_HEAD, show_header=True)
    table.add_column("Key", style="dim")
    table.add_column("Value", style=value_style)
    for k, v in data.items():
        table.add_row(k, v)
    console.print(table)


def print_search_results(results: list[SearchResult]) -> None:
    if not results:
        console.print("[dim]No results found.[/]")
        return

    table = Table(box=box.SIMPLE_HEAD, show_header=True)
    table.add_column("Score", justify="right", width=6)
    table.add_column("ID", style="dim", width=5, justify="right")
    table.add_column("Group", style="yellow")
    table.add_column("Description", style="white")
    table.add_column("Command", style="bold cyan")

    for result in results:
        score = 1.0 - result.distance
        score_style = "bold green" if score > 0.8 else ("yellow" if score > 0.6 else "red")
        table.add_row(
            Text(f"{score:.2f}", style=score_style),
            str(result.entry.id),
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
