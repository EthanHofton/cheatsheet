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
desc = "Git reference"
author = "Ethan"

[params]
remote = "origin"

[[entries]]
group = "remote"
description = "Clone a repo into a directory"
command = "git clone <url> <dir>"
placeholders = [
  { name = "url", description = "Repository URL to clone" },
  { name = "dir", description = "Local directory name" },
]

[[entries]]
group = "remote"
description = "Push a branch"
command = "git push {remote} <branch>"
placeholders = [
  { name = "branch", description = "Branch to push" },
]

[[entries]]
group = "local"
description = "Show status"
command = "git status"
```

All three top-level sections are optional. Entries without a `group` go into the default group. Groups are created automatically.

### Two placeholder syntaxes

| Syntax | Scope | Behaviour |
|---|---|---|
| `{param}` | Sheet-level | Substituted at display time with a stored value (e.g. `{remote}` → `origin`) |
| `<placeholder>` | Entry-level | Highlighted to signal a value the user must supply; optional description per placeholder |

Both can appear in the same command: `git push {remote} <branch>` renders as `git push origin <branch>` with `<branch>` highlighted.

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

### Entry placeholders

```bash
cheatsheet <name> entry placeholder list <id>
cheatsheet <name> entry placeholder add <id> <name> "<description>"
cheatsheet <name> entry placeholder delete <id> <name>
```

Placeholders added via the CLI are stored and displayed alongside the entry. The `<name>` token in the command is highlighted automatically — the `placeholder add` command just attaches a description to it.

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
