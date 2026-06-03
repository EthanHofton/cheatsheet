import click

from .db import get_connection
from .display import (
    console,
    print_error,
    print_full_sheet,
    print_kv_table,
    print_metadata_only,
    print_placeholders,
    print_search_results,
    print_sheet_list,
    print_success,
)
from .store import (
    DEFAULT_GROUP,
    add_entry,
    add_metadata,
    add_param,
    add_placeholder,
    create_group,
    create_sheet,
    delete_entry,
    delete_metadata,
    delete_param,
    delete_placeholder,
    delete_sheet,
    edit_metadata,
    edit_param,
    get_entry_by_id,
    get_group,
    get_metadata,
    get_params,
    get_placeholders,
    get_sheet,
    list_groups,
    list_sheets,
    store_embedding,
    update_entry,
)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

class SmartGroup(click.Group):
    """Routes `cheatsheet <sheet-name> [...]` to the hidden `show` command.

    The sheet name is stored in ctx.obj and stripped from args so that
    show_cmd carries no positional argument — this avoids Click's
    allow_interspersed_args=False restriction on Groups, which would
    otherwise block options like --group appearing after the sheet name.
    """

    def parse_args(self, ctx, args):
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            ctx.obj = args[0]               # store sheet name for show_cmd
            args = ["show"] + list(args[1:])  # drop it from the arg list
        return super().parse_args(ctx, args)


@click.group(cls=SmartGroup, epilog=(
    "Access a sheet by name:\n\n\b\n"
    "  cheatsheet tmux                   show the tmux cheatsheet\n"
    "  cheatsheet tmux query 'kill pane' semantic search\n"
    "  cheatsheet tmux entry add ...     add an entry\n"
    "  cheatsheet tmux --help            show all sheet subcommands\n"
))
def cli():
    """Terminal cheatsheet manager with semantic search."""
    pass


# ---------------------------------------------------------------------------
# Top-level: new / list / delete
# ---------------------------------------------------------------------------

@cli.command("new")
@click.argument("sheet_name")
@click.option("--from-file", "toml_path", default=None, type=click.Path(exists=True),
              help="Import entries, params, and metadata from a TOML file.")
def new_cmd(sheet_name, toml_path):
    """Create a new cheatsheet.

    Use --from-file to bulk-import from a TOML file. All three sections are
    optional and can appear in any combination.

    \b
    [metadata]   — free-form key/value info shown at the top of the sheet
    [params]     — sheet-level values substituted into commands at display time (e.g. {leader})
    [[entries]]  — one block per entry; repeat as many times as needed

    \b
    TOML example:
      [metadata]
      desc = "Git reference"
      [params]
      remote = "origin"
      [[entries]]
      group = "remote"
      description = "Clone a repo"
      command = "git clone <url> <dir>"
      placeholders = [
        { name = "url", description = "Repository URL" },
        { name = "dir", description = "Local directory name" },
      ]
      [[entries]]
      description = "Push branch"
      command = "git push {remote} <branch>"

    Each [[entries]] block requires 'description' and 'command'. The 'group'
    field is optional — entries without one go into the default group. Groups
    are created automatically; no need to pre-create them.

    \b
    Two placeholder syntaxes serve different purposes:
      {param}       — sheet-level, substituted at display time (e.g. {remote} → origin)
      <placeholder> — entry-level, marks values the user must supply (e.g. <branch>)

    \b
    Param substitution:
      Define  →  cheatsheet git params add remote "origin"
      Use     →  command = "git push {remote} <branch>"
      Display →  git push origin <branch>   (param substituted; placeholder highlighted)
    """
    with get_connection() as conn:
        try:
            sheet = create_sheet(conn, sheet_name)
        except ValueError as e:
            print_error(str(e))
            raise SystemExit(1)

        if toml_path:
            from pathlib import Path
            from .importer import bulk_import_file, parse_toml
            try:
                sheet_file = parse_toml(Path(toml_path))
            except ValueError as e:
                print_error(str(e))
                raise SystemExit(1)
            meta_n, param_n, entry_n = bulk_import_file(conn, sheet.id, sheet.name, sheet_file)
            parts = []
            if entry_n:
                parts.append(f"{entry_n} entries")
            if meta_n:
                parts.append(f"{meta_n} metadata fields")
            if param_n:
                parts.append(f"{param_n} params")
            summary = ", ".join(parts) if parts else "nothing to import"
            print_success(f"Created '{sheet_name}' and imported {summary}.")
        else:
            print_success(f"Created cheatsheet '{sheet_name}'.")
            click.echo("  cheatsheet tmux group add <group>")
            click.echo("  cheatsheet tmux entry add <description> <command>")


@cli.command("list")
def list_cmd():
    """List all cheatsheets."""
    with get_connection() as conn:
        print_sheet_list(list_sheets(conn))


@cli.command("delete")
@click.argument("sheet_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def delete_cmd(sheet_name, yes):
    """Delete a cheatsheet and all its entries."""
    if not yes:
        click.confirm(f"Delete '{sheet_name}' and all its entries?", abort=True)
    with get_connection() as conn:
        if delete_sheet(conn, sheet_name):
            print_success(f"Deleted '{sheet_name}'.")
        else:
            print_error(f"No cheatsheet named '{sheet_name}'.")
            raise SystemExit(1)


# ---------------------------------------------------------------------------
# Sheet root: cheatsheet <sheet> [--group filter]
# ---------------------------------------------------------------------------

@cli.group("show", hidden=True, invoke_without_command=True)
@click.option("--group", "-g", default=None, help="Filter display to a specific group.")
@click.pass_context
def show_cmd(ctx, group):
    """Display a cheatsheet."""
    sheet_name = ctx.obj

    if ctx.invoked_subcommand is not None:
        return

    with get_connection() as conn:
        sheet = get_sheet(conn, sheet_name)
        if sheet is None:
            print_error(f"No cheatsheet named '{sheet_name}'. Run 'cheatsheet list'.")
            raise SystemExit(1)
        if group and not get_group(conn, sheet.id, group):
            print_error(f"No group '{group}' in '{sheet_name}'.")
            raise SystemExit(1)
        from .store import get_entries
        entries = get_entries(conn, sheet.id, group_name=group)
        print_full_sheet(sheet_name, entries,
                         metadata=get_metadata(conn, sheet.id),
                         params=get_params(conn, sheet.id))


# helper used by all sub-commands to load + validate the sheet
def _require_sheet(conn, sheet_name: str):
    sheet = get_sheet(conn, sheet_name)
    if sheet is None:
        print_error(f"No cheatsheet named '{sheet_name}'. Run 'cheatsheet list'.")
        raise SystemExit(1)
    return sheet


# ---------------------------------------------------------------------------
# cheatsheet tmux query
# ---------------------------------------------------------------------------

@show_cmd.command("query")
@click.argument("query_text")
@click.option("--top-k", "top_k", default=8, show_default=True,
              help="Maximum results to return.")
@click.option("--tol", default=None, type=float,
              help="Minimum score 0–1; hides results below this threshold.")
@click.option("--group", "-g", "filter_group", default=None,
              help="Restrict search to a specific group.")
@click.pass_context
def query_cmd(ctx, query_text, top_k, tol, filter_group):
    """Semantic search within the cheatsheet."""
    from rich.status import Status
    from .search import semantic_search

    sheet_name = ctx.obj
    console.print(f"\n[bold]Searching '[cyan]{sheet_name}[/]' for:[/] {query_text}\n")
    with get_connection() as conn:
        with Status("[dim]Loading model…[/]", console=console):
            results = semantic_search(conn, sheet_name, query_text,
                                      top_k=top_k, tol=tol, filter_group=filter_group)
    print_search_results(results)


# ---------------------------------------------------------------------------
# cheatsheet tmux entry [add / update / delete]
# ---------------------------------------------------------------------------

@show_cmd.group("entry", invoke_without_command=True)
@click.option("--group", "-g", default=None, help="Filter to a specific group.")
@click.pass_context
def entry_group(ctx, group):
    """List entries, or manage them with a subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    sheet_name = ctx.obj
    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        from .store import get_entries
        entries = get_entries(conn, sheet.id, group_name=group)
        if group and not entries:
            print_error(f"No group '{group}' in '{sheet_name}'.")
            raise SystemExit(1)
        print_full_sheet(sheet_name, entries,
                         metadata=get_metadata(conn, sheet.id),
                         params=get_params(conn, sheet.id))


@entry_group.command("add")
@click.argument("description", required=False)
@click.argument("command", required=False)
@click.option("--group", "-g", default=None, help="Group name (must already exist).")
@click.option("--interactive", "-i", is_flag=True, help="Interactive entry wizard.")
@click.pass_context
def entry_add(ctx, description, command, group, interactive):
    """Add one or more entries.

    \b
    Single:       cheatsheet tmux entry add "Kill pane" "{leader} x" --group pane
    Interactive:  cheatsheet tmux entry add --interactive
    """
    sheet_name = ctx.obj
    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        if interactive:
            _interactive_add(conn, sheet)
        elif description and command:
            _single_add(conn, sheet, description, command, group)
        else:
            raise click.UsageError("Provide DESCRIPTION and COMMAND, or use --interactive.")


@entry_group.command("update")
@click.argument("entry_id", type=int)
@click.option("--description", "-d", default=None, help="New description.")
@click.option("--command", "-c", default=None, help="New command.")
@click.option("--group", "-g", default=None, help="Move to a different group.")
@click.pass_context
def entry_update(ctx, entry_id, description, command, group):
    """Update an entry by its ID."""
    from rich.status import Status

    sheet_name = ctx.obj
    if not any([description, command, group]):
        raise click.UsageError("Provide at least one of --description, --command, or --group.")

    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        entry = get_entry_by_id(conn, entry_id)
        if entry is None or entry.sheet_name != sheet_name:
            print_error(f"Entry #{entry_id} not found in '{sheet_name}'.")
            raise SystemExit(1)

        new_group_id = None
        if group is not None:
            grp = get_group(conn, sheet.id, group)
            if grp is None:
                print_error(f"Group '{group}' does not exist in '{sheet_name}'.")
                raise SystemExit(1)
            new_group_id = grp.id

        updated = update_entry(conn, entry_id, description=description,
                               command=command, group_id=new_group_id)

        if description is not None or command is not None:
            from .embeddings import embed
            with Status("[dim]Re-embedding…[/]", console=console):
                vector = embed(f"{updated.description} {updated.command}")
            store_embedding(conn, entry_id, vector)

    print_success(f"Updated entry #{entry_id}.")


@entry_group.command("delete")
@click.argument("entry_id", type=int)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def entry_delete(ctx, entry_id, yes):
    """Delete an entry by its ID."""
    sheet_name = ctx.obj
    with get_connection() as conn:
        entry = get_entry_by_id(conn, entry_id)
        if entry is None or entry.sheet_name != sheet_name:
            print_error(f"Entry #{entry_id} not found in '{sheet_name}'.")
            raise SystemExit(1)
        if not yes:
            click.confirm(f"Delete entry #{entry_id} ('{entry.description}')?", abort=True)
        delete_entry(conn, entry_id)
    print_success(f"Deleted entry #{entry_id}.")


# ---------------------------------------------------------------------------
# cheatsheet tmux entry placeholder [add / delete / list]
# ---------------------------------------------------------------------------

@entry_group.group("placeholder")
def placeholder_group():
    """Manage placeholders for an entry."""
    pass


@placeholder_group.command("add")
@click.argument("entry_id", type=int)
@click.argument("name")
@click.argument("description", default="")
@click.pass_context
def placeholder_add(ctx, entry_id, name, description):
    """Add a placeholder to an entry.

    \b
    Example:
      cheatsheet git entry placeholder add 5 url "Repository URL to clone"
    """
    sheet_name = ctx.obj
    with get_connection() as conn:
        entry = get_entry_by_id(conn, entry_id)
        if entry is None or entry.sheet_name != sheet_name:
            print_error(f"Entry #{entry_id} not found in '{sheet_name}'.")
            raise SystemExit(1)
        try:
            add_placeholder(conn, entry_id, name, description)
        except ValueError as e:
            print_error(str(e))
            raise SystemExit(1)
    print_success(f"Added placeholder '{name}' to entry #{entry_id}.")


@placeholder_group.command("delete")
@click.argument("entry_id", type=int)
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def placeholder_delete(ctx, entry_id, name, yes):
    """Delete a placeholder from an entry."""
    sheet_name = ctx.obj
    with get_connection() as conn:
        entry = get_entry_by_id(conn, entry_id)
        if entry is None or entry.sheet_name != sheet_name:
            print_error(f"Entry #{entry_id} not found in '{sheet_name}'.")
            raise SystemExit(1)
        if not yes:
            click.confirm(f"Delete placeholder '{name}' from entry #{entry_id}?", abort=True)
        try:
            delete_placeholder(conn, entry_id, name)
        except ValueError as e:
            print_error(str(e))
            raise SystemExit(1)
    print_success(f"Deleted placeholder '{name}' from entry #{entry_id}.")


@placeholder_group.command("list")
@click.argument("entry_id", type=int)
@click.pass_context
def placeholder_list(ctx, entry_id):
    """List placeholders for an entry."""
    sheet_name = ctx.obj
    with get_connection() as conn:
        entry = get_entry_by_id(conn, entry_id)
        if entry is None or entry.sheet_name != sheet_name:
            print_error(f"Entry #{entry_id} not found in '{sheet_name}'.")
            raise SystemExit(1)
        placeholders = get_placeholders(conn, entry_id)
    print_placeholders(entry_id, entry.description, placeholders)


# ---------------------------------------------------------------------------
# cheatsheet tmux group [add / delete]
# ---------------------------------------------------------------------------

@show_cmd.group("group", invoke_without_command=True)
@click.pass_context
def group_group(ctx):
    """List groups, or manage them with a subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    sheet_name = ctx.obj
    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        groups = list_groups(conn, sheet.id)
    if not groups:
        console.print("[dim]No groups yet.[/]")
        return
    from rich import box
    from rich.table import Table
    t = Table(box=box.SIMPLE_HEAD, show_header=True)
    t.add_column("Group", style="bold yellow")
    for g in groups:
        t.add_row(g.name)
    console.print(t)


@group_group.command("add")
@click.argument("group_name")
@click.pass_context
def group_add(ctx, group_name):
    """Add a new group."""
    sheet_name = ctx.obj
    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        try:
            create_group(conn, sheet.id, group_name)
        except ValueError as e:
            print_error(str(e))
            raise SystemExit(1)
    print_success(f"Added group '{group_name}' to '{sheet_name}'.")


@group_group.command("delete")
@click.argument("group_name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def group_delete(ctx, group_name, yes):
    """Delete a group and all its entries."""
    sheet_name = ctx.obj
    if group_name == DEFAULT_GROUP:
        print_error("Cannot delete the default group.")
        raise SystemExit(1)
    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        grp = get_group(conn, sheet.id, group_name)
        if grp is None:
            print_error(f"Group '{group_name}' not found in '{sheet_name}'.")
            raise SystemExit(1)
        if not yes:
            click.confirm(
                f"Delete group '{group_name}' and all its entries from '{sheet_name}'?", abort=True
            )
        conn.execute(
            "DELETE FROM entry_embeddings WHERE entry_id IN "
            "(SELECT id FROM entries WHERE group_id = ?)", [grp.id]
        )
        conn.execute("DELETE FROM groups WHERE id = ?", [grp.id])
        conn.commit()
    print_success(f"Deleted group '{group_name}'.")


# ---------------------------------------------------------------------------
# cheatsheet tmux meta [add / edit / delete]
# ---------------------------------------------------------------------------

@show_cmd.group("meta", invoke_without_command=True)
@click.pass_context
def meta_group(ctx):
    """List metadata, or manage it with a subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    sheet_name = ctx.obj
    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        metadata = get_metadata(conn, sheet.id)
        params = get_params(conn, sheet.id)
    print_metadata_only(sheet_name, metadata, params)


@meta_group.command("add")
@click.argument("key")
@click.argument("value")
@click.pass_context
def meta_add(ctx, key, value):
    """Add a metadata field."""
    sheet_name = ctx.obj
    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        try:
            add_metadata(conn, sheet.id, key, value)
        except ValueError as e:
            print_error(str(e))
            raise SystemExit(1)
    print_success(f"Added metadata: {key} = {value}")


@meta_group.command("edit")
@click.argument("key")
@click.argument("value")
@click.pass_context
def meta_edit(ctx, key, value):
    """Update an existing metadata field."""
    sheet_name = ctx.obj
    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        try:
            edit_metadata(conn, sheet.id, key, value)
        except ValueError as e:
            print_error(str(e))
            raise SystemExit(1)
    print_success(f"Updated metadata: {key} = {value}")


@meta_group.command("delete")
@click.argument("key")
@click.pass_context
def meta_delete(ctx, key):
    """Delete a metadata field."""
    sheet_name = ctx.obj
    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        try:
            delete_metadata(conn, sheet.id, key)
        except ValueError as e:
            print_error(str(e))
            raise SystemExit(1)
    print_success(f"Deleted metadata field '{key}'.")


# ---------------------------------------------------------------------------
# cheatsheet tmux params [add / edit / delete]
# ---------------------------------------------------------------------------

@show_cmd.group("params", invoke_without_command=True)
@click.pass_context
def params_group(ctx):
    """List params, or manage them with a subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    sheet_name = ctx.obj
    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        params = get_params(conn, sheet.id)
    print_kv_table("params", {f"{{{k}}}": v for k, v in params.items()}, value_style="bold cyan")


@params_group.command("add")
@click.argument("key")
@click.argument("value")
@click.pass_context
def params_add(ctx, key, value):
    """Add a parameter."""
    sheet_name = ctx.obj
    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        try:
            add_param(conn, sheet.id, key, value)
        except ValueError as e:
            print_error(str(e))
            raise SystemExit(1)
    print_success(f"Added param: {{{key}}} = {value}")


@params_group.command("edit")
@click.argument("key")
@click.argument("value")
@click.pass_context
def params_edit(ctx, key, value):
    """Update an existing parameter."""
    sheet_name = ctx.obj
    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        try:
            edit_param(conn, sheet.id, key, value)
        except ValueError as e:
            print_error(str(e))
            raise SystemExit(1)
    print_success(f"Updated param: {{{key}}} = {value}")


@params_group.command("delete")
@click.argument("key")
@click.pass_context
def params_delete(ctx, key):
    """Delete a parameter."""
    sheet_name = ctx.obj
    with get_connection() as conn:
        sheet = _require_sheet(conn, sheet_name)
        try:
            delete_param(conn, sheet.id, key)
        except ValueError as e:
            print_error(str(e))
            raise SystemExit(1)
    print_success(f"Deleted param '{{{key}}}'.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_group(conn, sheet, group_name: str | None):
    name = group_name or DEFAULT_GROUP
    grp = get_group(conn, sheet.id, name)
    if grp is None:
        if group_name:
            raise click.ClickException(
                f"Group '{group_name}' does not exist in '{sheet.name}'. "
                f"Run: cheatsheet {sheet.name} group add {group_name}"
            )
        raise click.ClickException(
            f"Default group missing for '{sheet.name}'. Try recreating the sheet."
        )
    return grp


def _single_add(conn, sheet, description: str, command: str, group_name: str | None):
    from .embeddings import embed
    grp = _resolve_group(conn, sheet, group_name)
    entry = add_entry(conn, grp.id, description, command)
    vector = embed(f"{description} {command}")
    store_embedding(conn, entry.id, vector)
    print_success(f"Added '{description}' → {sheet.name}/{grp.name} (#{entry.id})")


def _interactive_add(conn, sheet):
    from .embeddings import embed
    params = get_params(conn, sheet.id)
    click.echo(f"Adding entries to '{sheet.name}'. Leave description blank to finish.\n")
    if params:
        click.echo("  Available params:")
        for k, v in params.items():
            click.echo(f"    {{{k}}} = {v}")
        click.echo()
    try:
        while True:
            description = click.prompt("Description (blank to finish)", default="", show_default=False)
            if not description.strip():
                break
            command = click.prompt("Command")
            group_name = click.prompt("Group (blank for default)", default="", show_default=False).strip() or None
            try:
                grp = _resolve_group(conn, sheet, group_name)
            except click.ClickException as e:
                click.echo(f"  ! {e.format_message()}")
                continue
            entry = add_entry(conn, grp.id, description.strip(), command.strip())
            vector = embed(f"{description} {command}")
            store_embedding(conn, entry.id, vector)
            print_success(f"Added '{description}' → {sheet.name}/{grp.name} (#{entry.id})")
            click.echo()
    except click.exceptions.Abort:
        click.echo("\nDone.")
