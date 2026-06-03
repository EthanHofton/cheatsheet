import click

from .db import get_connection
from .display import print_error, print_full_sheet, print_search_results, print_sheet_list, print_success
from .store import (
    DEFAULT_GROUP,
    RESERVED_NAMES,
    add_entry,
    create_group,
    create_sheet,
    delete_sheet,
    get_group,
    get_sheet,
    list_sheets,
    store_embedding,
)


class SmartGroup(click.Group):
    """Routes `cheatsheet <name>` to the hidden `show` command."""

    def parse_args(self, ctx, args):
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            args = ["show"] + list(args)
        return super().parse_args(ctx, args)


@click.group(cls=SmartGroup)
def cli():
    """Terminal cheatsheet manager with semantic search."""
    pass


# ---------------------------------------------------------------------------
# show (hidden — invoked by SmartGroup routing)
# ---------------------------------------------------------------------------


@cli.command(name="show", hidden=True)
@click.argument("sheet_name")
@click.option("--query", "-q", default=None, help="Semantic search query.")
@click.option("--group", "-g", default=None, help="Filter to a specific group.")
def show_cmd(sheet_name, query, group):
    """Display a cheatsheet or search within it."""
    with get_connection() as conn:
        sheet = get_sheet(conn, sheet_name)
        if sheet is None:
            print_error(f"No cheatsheet named '{sheet_name}'. Run 'cheatsheet list' to see available sheets.")
            raise SystemExit(1)

        if query:
            from .search import semantic_search

            results = semantic_search(conn, sheet_name, query)
            print_search_results(sheet_name, query, results)
        else:
            from .store import get_entries

            entries = get_entries(conn, sheet.id, group_name=group)
            if group and not entries:
                print_error(f"No group '{group}' in '{sheet_name}'.")
                raise SystemExit(1)
            print_full_sheet(sheet_name, entries)


# ---------------------------------------------------------------------------
# new
# ---------------------------------------------------------------------------


@cli.command(name="new")
@click.argument("sheet_name")
@click.option("--from-csv", "csv_path", default=None, type=click.Path(exists=True), help="Bulk import from CSV.")
def new_cmd(sheet_name, csv_path):
    """Create a new cheatsheet (auto-creates a 'default' group).

    \b
    CSV format (--from-csv):
      group,description,command
      pane,Kill current pane,Ctrl+B x
      pane,Split pane horizontal,Ctrl+B %
      ,New window,Ctrl+B c

    The 'group' column is optional — leave it blank to use the default group.
    Groups are created automatically from the CSV data.
    """
    with get_connection() as conn:
        try:
            sheet = create_sheet(conn, sheet_name)
        except ValueError as e:
            print_error(str(e))
            raise SystemExit(1)

        if csv_path:
            from pathlib import Path

            from .importer import bulk_import, parse_csv

            try:
                rows = parse_csv(Path(csv_path))
            except ValueError as e:
                print_error(str(e))
                raise SystemExit(1)

            count = bulk_import(conn, sheet.id, sheet.name, rows)
            print_success(f"Created '{sheet_name}' and imported {count} entries.")
        else:
            print_success(f"Created cheatsheet '{sheet_name}' with a 'default' group.")
            click.echo("  Add groups:   cheatsheet group <sheet> <group>")
            click.echo("  Add entries:  cheatsheet add <sheet> <description> <command>")


# ---------------------------------------------------------------------------
# group
# ---------------------------------------------------------------------------


@cli.command(name="group")
@click.argument("sheet_name")
@click.argument("group_name")
def group_cmd(sheet_name, group_name):
    """Add a new group to a cheatsheet."""
    with get_connection() as conn:
        sheet = get_sheet(conn, sheet_name)
        if sheet is None:
            print_error(f"No cheatsheet named '{sheet_name}'.")
            raise SystemExit(1)
        try:
            create_group(conn, sheet.id, group_name)
        except ValueError as e:
            print_error(str(e))
            raise SystemExit(1)
        print_success(f"Added group '{group_name}' to '{sheet_name}'.")


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


@cli.command(name="add")
@click.argument("sheet_name")
@click.argument("description", required=False)
@click.argument("command", required=False)
@click.option("--group", "-g", default=None, help="Group name (must already exist).")
@click.option("--interactive", "-i", is_flag=True, help="Interactive entry wizard.")
def add_cmd(sheet_name, description, command, group, interactive):
    """Add entries to a cheatsheet.

    \b
    Single-line:  cheatsheet add tmux "Kill pane" "Ctrl+B x" --group pane
    Interactive:  cheatsheet add tmux --interactive
    """
    with get_connection() as conn:
        sheet = get_sheet(conn, sheet_name)
        if sheet is None:
            print_error(f"No cheatsheet named '{sheet_name}'. Run 'cheatsheet new {sheet_name}' first.")
            raise SystemExit(1)

        if interactive:
            _add_interactive(conn, sheet)
        elif description and command:
            _add_single(conn, sheet, description, command, group)
        else:
            raise click.UsageError(
                "Provide DESCRIPTION and COMMAND arguments, or use --interactive."
            )


def _resolve_group(conn, sheet, group_name: str | None):
    name = group_name or DEFAULT_GROUP
    grp = get_group(conn, sheet.id, name)
    if grp is None:
        if group_name:
            raise click.ClickException(
                f"Group '{group_name}' does not exist in '{sheet.name}'. "
                f"Run: cheatsheet group {sheet.name} {group_name}"
            )
        raise click.ClickException(
            f"Default group missing for '{sheet.name}'. This shouldn't happen — please recreate the sheet."
        )
    return grp


def _add_single(conn, sheet, description: str, command: str, group_name: str | None):
    from .embeddings import embed

    grp = _resolve_group(conn, sheet, group_name)
    entry = add_entry(conn, grp.id, description, command)
    vector = embed(f"{description} {command}")
    store_embedding(conn, entry.id, vector)
    print_success(f"Added '{description}' to {sheet.name}/{grp.name}.")


def _add_interactive(conn, sheet):
    from .embeddings import embed

    click.echo(f"Adding entries to '{sheet.name}'. Press Ctrl+C or leave description blank to finish.\n")
    try:
        while True:
            description = click.prompt("Description (blank to finish)", default="", show_default=False)
            if not description.strip():
                break
            command = click.prompt("Command")
            group_name = click.prompt("Group (leave blank for default)", default="", show_default=False).strip() or None

            try:
                grp = _resolve_group(conn, sheet, group_name)
            except click.ClickException as e:
                click.echo(f"  [!] {e.format_message()}")
                continue

            entry = add_entry(conn, grp.id, description.strip(), command.strip())
            vector = embed(f"{description} {command}")
            store_embedding(conn, entry.id, vector)
            print_success(f"Added '{description}' to {sheet.name}/{grp.name}.")
            click.echo()
    except click.exceptions.Abort:
        click.echo("\nDone.")


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@cli.command(name="list")
def list_cmd():
    """List all cheatsheets."""
    with get_connection() as conn:
        sheets = list_sheets(conn)
        print_sheet_list(sheets)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@cli.command(name="delete")
@click.argument("sheet_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def delete_cmd(sheet_name, yes):
    """Delete a cheatsheet and all its entries."""
    if not yes:
        click.confirm(f"Delete cheatsheet '{sheet_name}' and all its entries?", abort=True)
    with get_connection() as conn:
        deleted = delete_sheet(conn, sheet_name)
        if deleted:
            print_success(f"Deleted '{sheet_name}'.")
        else:
            print_error(f"No cheatsheet named '{sheet_name}'.")
            raise SystemExit(1)
