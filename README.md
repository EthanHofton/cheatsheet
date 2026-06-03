# cheatsheet

Terminal cheatsheet manager with semantic search. Store commands grouped by topic, define reusable params, and find entries by meaning rather than exact wording.

## Installation

```bash
poetry install
```

This installs the `cheatsheet` CLI.

## Quick start

```bash
# Create from a TOML file
cheatsheet new tmux --from-file examples/tmux.toml

# Show the sheet
cheatsheet tmux

# Search by meaning
cheatsheet tmux query "kill a pane"

# Filter to one group
cheatsheet tmux --group window
```

## TOML import format

```toml
[metadata]
desc = "Tmux keybinding reference"

[params]
leader = "Ctrl-A"

[[entries]]
group = "pane"
description = "Close current pane"
command = "{leader} x"

[[entries]]
description = "New window"
command = "{leader} c"
```

All three sections are optional. Entries without a `group` go into the default group. Groups are created automatically.

Params are substituted at display time — `{leader} x` renders as `Ctrl-A x`.

## Commands

### Sheets

| Command | Description |
|---|---|
| `cheatsheet new <name>` | Create a cheatsheet |
| `cheatsheet new <name> --from-file <path>` | Create and import from TOML |
| `cheatsheet list` | List all cheatsheets |
| `cheatsheet delete <name>` | Delete a cheatsheet and all its entries |
| `cheatsheet <name>` | Display a cheatsheet |
| `cheatsheet <name> --group <group>` | Display filtered to one group |

### Search

```bash
cheatsheet <name> query "<text>"
cheatsheet <name> query "<text>" --top-k 5
cheatsheet <name> query "<text>" --tol 0.6          # minimum score threshold
cheatsheet <name> query "<text>" --group <group>    # restrict to a group
```

### Entries

```bash
cheatsheet <name> entry add "<description>" "<command>"
cheatsheet <name> entry add "<description>" "<command>" --group <group>
cheatsheet <name> entry add --interactive

cheatsheet <name> entry update <id> --description "New desc"
cheatsheet <name> entry update <id> --command "new cmd" --group <group>
cheatsheet <name> entry delete <id>
```

### Groups

```bash
cheatsheet <name> group                # list groups
cheatsheet <name> group add <name>
cheatsheet <name> group delete <name>
```

### Metadata

```bash
cheatsheet <name> meta                 # list metadata
cheatsheet <name> meta add <key> <value>
cheatsheet <name> meta edit <key> <value>
cheatsheet <name> meta delete <key>
```

### Params

```bash
cheatsheet <name> params               # list params
cheatsheet <name> params add <key> <value>
cheatsheet <name> params edit <key> <value>
cheatsheet <name> params delete <key>
```

## Development

```bash
poetry run pytest
poetry run pytest --cov=cheatsheet
```
