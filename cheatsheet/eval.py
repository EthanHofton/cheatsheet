"""Search quality evaluation — run before and after model/embedding changes.

Usage:
    cheatsheet-eval
    cheatsheet-eval --tol 0.3
    cheatsheet-eval -v          # show passing cases
    cheatsheet-eval -vv         # show passing cases with top result
    cheatsheet-eval --sheet tmux
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

from .db import get_connection
from .search import semantic_search


@dataclass
class Case:
    sheet: str
    query: str
    # Substring of the expected description (case-insensitive).
    expected: str
    # Look for expected within the first top_k results.
    top_k: int = 3


TEST_CASES: list[Case] = [
    # ── tmux (35) ────────────────────────────────────────────────────────────
    Case("tmux", "close kill a pane", "Close current pane", 1),
    Case("tmux", "split pane left and right side by side", "Split vertically", 1),
    Case("tmux", "split pane top and bottom", "Split horizontally", 1),
    Case("tmux", "zoom pane to full screen", "Zoom pane fullscreen", 1),
    Case("tmux", "move focus to the left pane", "Move pane focus left (vim-tmux-navigator)", 3),
    Case("tmux", "move focus to the right pane", "Move pane focus right (vim-tmux-navigator)", 3),
    Case("tmux", "move focus to the pane above", "Move pane focus up", 3),
    Case("tmux", "move focus to the pane below", "Move pane focus down", 3),
    Case("tmux", "resize pane to the right", "Resize pane right", 3),
    Case("tmux", "resize pane upward", "Resize pane up", 3),
    Case("tmux", "resize pane downward", "Resize pane down", 3),
    Case("tmux", "resize pane to the left", "Resize pane left", 3),
    Case("tmux", "show pane numbers and jump to one", "Flash pane numbers and jump", 3),
    Case("tmux", "cycle rotate through all panes", "Cycle through panes", 3),
    Case("tmux", "move pane into its own window", "Break pane into its own window", 3),
    Case("tmux", "change rearrange pane layout", "Cycle through pane layouts", 3),
    Case("tmux", "swap move pane position", "Swap pane with", 5),
    Case("tmux", "create a new window", "Create new window", 1),
    Case("tmux", "switch to next window", "Next window", 3),
    Case("tmux", "switch to previous window", "Previous window", 3),
    Case("tmux", "rename the current window", "Rename current window", 1),
    Case("tmux", "kill close the current window", "Kill current window", 3),
    Case("tmux", "jump back to the last used window", "Jump to last used window", 3),
    Case("tmux", "list all open windows", "Interactive window list", 3),
    Case("tmux", "detach disconnect from session", "Detach from session", 1),
    Case("tmux", "rename the current session", "Rename current session", 1),
    Case("tmux", "switch between sessions interactively", "Interactive session switcher", 3),
    Case("tmux", "attach connect to an existing session", "Attach to session", 3),
    Case("tmux", "create a new named session", "Create named session", 3),
    Case("tmux", "list all sessions", "List sessions", 3),
    Case("tmux", "enter scroll and copy mode", "Enter copy/scroll mode", 1),
    Case("tmux", "copy selected text", "Copy selection and exit", 3),
    Case("tmux", "paste from the copy buffer", "Paste copied text", 3),
    Case("tmux", "show all keybindings", "Show all keybindings", 1),
    Case("tmux", "open the tmux command prompt", "Open command prompt", 3),
    # ── vim (35) ─────────────────────────────────────────────────────────────
    Case("vim", "undo last change", "Undo the last change", 1),
    Case("vim", "redo an undone change", "Redo an undone change", 3),
    Case("vim", "save the file to disk", "Write the current buffer to disk", 3),
    Case("vim", "quit exit vim", "Close the current window or exit Vim", 3),
    Case("vim", "save and quit", "Write the buffer to disk and exit Vim", 3),
    Case("vim", "force quit without saving changes", "Force quit discarding any unsaved changes", 3),
    Case("vim", "go to the first line of the file", "Jump to the very first line of the file", 3),
    Case("vim", "go to the last line of the file", "Jump to the very last line of the file", 3),
    Case("vim", "jump to a specific line number", "Jump directly to a specific line number", 1),
    Case("vim", "jump to the start of the line", "Jump to the first non-whitespace character on the current line", 3),
    Case("vim", "jump to the end of the line", "Jump to the last character on the current line", 3),
    Case("vim", "move forward by one word", "Jump forward to the start of the next word", 3),
    Case("vim", "move backward by one word", "Jump backward to the start of the previous word", 3),
    Case("vim", "delete the current line", "Cut the entire current line into the default register", 3),
    Case("vim", "delete to the end of the line", "Delete from the cursor to the end of the line", 3),
    Case("vim", "yank copy the current line", "Copy the entire current line into the default register", 3),
    Case("vim", "paste below or after the cursor", "Paste register contents after the cursor or below the current line", 3),
    Case("vim", "search find text forward", "Open the search prompt and find text forward in the buffer", 3),
    Case("vim", "search find text backward", "Open the search prompt and find text backward in the buffer", 3),
    Case("vim", "global find and replace all occurrences in file", "Global find and replace throughout the entire file", 3),
    Case("vim", "replace all occurrences on the current line", "Replace all occurrences of a pattern on the current line", 3),
    Case("vim", "enter insert mode at cursor", "Enter insert mode and start typing at the cursor position", 3),
    Case("vim", "insert at the start of the line", "Move to the start of the line and enter insert mode", 3),
    Case("vim", "append insert after the cursor", "Enter insert mode and start typing one position after the cursor", 3),
    Case("vim", "open a blank line below and start editing", "Insert a blank line below the current line and start editing", 3),
    Case("vim", "repeat the last edit action", "Replay the most recent edit operation", 3),
    Case("vim", "start recording a macro", "Begin recording keystrokes as a reusable macro into a register", 3),
    Case("vim", "execute a recorded macro", "Execute a recorded macro stored in a register", 3),
    Case("vim", "jump to matching bracket or brace", "Jump between matching brackets, parentheses, or braces", 3),
    Case("vim", "set a named bookmark mark", "Save the current cursor position as a named bookmark", 3),
    Case("vim", "jump to the exact position of a mark", "Jump to the exact line and column where a named mark was set", 3),
    Case("vim", "show line numbers in the gutter", "Enable line number display in the gutter", 3),
    Case("vim", "select the inner word text object", "Select the current word, excluding surrounding whitespace", 3),
    Case("vim", "copy text to the system clipboard", "Copy text into the system clipboard via the + register", 3),
    Case("vim", "paste from the system clipboard", "Paste text from the OS system clipboard", 3),
    # ── nvim (30) ────────────────────────────────────────────────────────────
    Case("nvim", "open the file explorer tree sidebar", "Open or close the nvim-tree file explorer sidebar", 1),
    Case("nvim", "fuzzy find open files by name", "Fuzzy find and open files by name across the project", 1),
    Case("nvim", "live grep search text across project", "Search for text across all project files with live grep", 1),
    Case("nvim", "go to definition of function or variable", "Jump to where a function or variable is defined", 3),
    Case("nvim", "find all references usages of symbol", "List all usages and references of the symbol under cursor", 3),
    Case("nvim", "rename refactor symbol across project", "Rename a symbol across the whole project via LSP", 3),
    Case("nvim", "show hover documentation for symbol", "Show inline documentation popup for symbol under cursor", 3),
    Case("nvim", "auto format the current buffer", "Auto-format the current buffer or visual selection", 3),
    Case("nvim", "show diagnostic error or warning details", "Show diagnostic error or warning details in a popup", 3),
    Case("nvim", "jump to the next diagnostic error", "Jump to the next LSP diagnostic in the buffer", 3),
    Case("nvim", "jump to the previous diagnostic error", "Jump to the previous LSP diagnostic in the buffer", 3),
    Case("nvim", "comment out the current line", "Comment or uncomment the current line", 1),
    Case("nvim", "wrap line in a block comment", "Wrap the current line in a block comment", 3),
    Case("nvim", "comment region covered by motion", "Comment or uncomment lines covered by a motion", 3),
    Case("nvim", "open vertical split pane side by side", "Open a new vertical split pane side by side", 3),
    Case("nvim", "open horizontal split pane above and below", "Open a new horizontal split pane above and below", 3),
    Case("nvim", "make all split windows equal size", "Make all open split windows the same size", 3),
    Case("nvim", "close the current split window", "Close and remove the current split window", 3),
    Case("nvim", "create open a new tab", "Create a new editor tab", 3),
    Case("nvim", "close the current tab", "Close the current active tab", 1),
    Case("nvim", "accept the highlighted autocomplete suggestion", "Accept the currently highlighted completion suggestion", 3),
    Case("nvim", "move down through autocomplete suggestions", "Move down to the next autocomplete suggestion", 3),
    Case("nvim", "dismiss close the autocomplete popup", "Dismiss and close the completion popup without confirming", 3),
    Case("nvim", "surround wrap word with brackets or quotes", "Wrap a text object or motion with a surrounding character", 3),
    Case("nvim", "remove delete surrounding character", "Remove surrounding brackets, quotes, or tags entirely", 3),
    Case("nvim", "replace change surrounding bracket or quote", "Replace an existing surrounding bracket, quote, or tag with a new one", 3),
    Case("nvim", "switch between open buffers", "Browse and switch between open buffers", 3),
    Case("nvim", "search neovim help documentation", "Search Neovim help documentation with Telescope", 3),
    Case("nvim", "jump to symbol declaration via LSP", "Jump to the symbol's declaration via LSP", 3),
    Case("nvim", "jump to the type definition of a symbol", "Jump to the type definition of the symbol under cursor", 3),
    # ── harder cases: paraphrases / vocabulary mismatch / counterintuitive ──
    # tmux (10)
    Case("tmux", "make this pane take up the entire terminal", "Zoom pane fullscreen", 3),
    Case("tmux", "where can I see all available shortcuts", "Show all keybindings", 3),
    Case("tmux", "start a fresh workspace with a label", "Create named session", 3),
    Case("tmux", "disconnect from the current workspace", "Detach from session", 3),
    Case("tmux", "display the clock in tmux", "Show clock", 3),
    Case("tmux", "view tmux notifications and messages", "Show tmux messages", 3),
    Case("tmux", "split with a vertical divider creating two side-by-side panes", "Split vertically", 3),
    Case("tmux", "highlight pane numbers so I can jump to one", "Flash pane numbers and jump", 3),
    Case("tmux", "launch a shared group session linked to another", "Create grouped session", 3),
    Case("tmux", "reorder swap the position of adjacent panes", "Swap pane with", 5),
    # vim (10)
    Case("vim", "commit current work to storage", "Write the current buffer to disk", 3),
    Case("vim", "abandon all edits and close immediately", "Force quit discarding any unsaved changes", 3),
    Case("vim", "go to the top of the document", "Jump to the very first line of the file", 3),
    Case("vim", "go to the bottom of the document", "Jump to the very last line of the file", 3),
    Case("vim", "toggle the case of the character at the cursor", "Flip the character under the cursor between upper and lowercase", 3),
    Case("vim", "inspect all clipboard register contents", "List the contents of all named and special registers", 3),
    Case("vim", "go back through jump navigation history", "Go back to the previous cursor position in the jump list", 3),
    Case("vim", "indent the current line one level to the right", "Shift the current line one indent level to the right", 3),
    Case("vim", "rectangular column visual selection", "Start a block-wise rectangular column selection", 3),
    Case("vim", "center the current line vertically on screen", "Scroll the view so the cursor line is vertically centered", 3),
    # nvim (10)
    Case("nvim", "find where this interface is implemented", "Jump to the interface implementation via LSP", 3),
    Case("nvim", "choose a python virtual environment for this project", "Pick and activate a Python virtual environment for the project", 3),
    Case("nvim", "maximize the focused split to fill the screen", "Toggle zoom to maximize or restore the current split", 3),
    Case("nvim", "delete without clobbering what I copied", "Delete character without overwriting the yank register", 3),
    Case("nvim", "remove the search highlight from the buffer", "Remove highlight from last search results", 3),
    Case("nvim", "escape back to normal mode from insert mode", "Return to normal mode from insert mode", 3),
    Case("nvim", "add brackets or quotes around a text object", "Wrap a text object or motion with a surrounding character", 3),
    Case("nvim", "send telescope results to quickfix for bulk editing", "Send selected Telescope results to the quickfix list", 3),
    Case("nvim", "look up inline docs without leaving the editor", "Show inline documentation popup for symbol under cursor", 3),
    Case("nvim", "apply a quick fix or suggested code action", "Show available code actions and quick fixes via LSP", 3),
]


@dataclass
class _SheetStats:
    passed: int = 0
    failed: int = 0


@dataclass
class _Failure:
    n: int
    sheet: str
    query: str
    expected: str
    top_k: int
    got: str
    got_score: float
    all_results: list[tuple[str, float]] = field(default_factory=list)


def _run(
    sheet_filter: str | None = None,
    tol: float | None = None,
    verbosity: int = 0,
) -> int:
    cases = [c for c in TEST_CASES if sheet_filter is None or c.sheet == sheet_filter]
    if not cases:
        print(f"No test cases for sheet {sheet_filter!r}.", file=sys.stderr)
        return 1

    stats: dict[str, _SheetStats] = {}
    failures: list[_Failure] = []

    with get_connection() as conn:
        for i, case in enumerate(cases, 1):
            results = semantic_search(conn, case.sheet, case.query, top_k=case.top_k, tol=tol)
            descriptions = [r.entry.description for r in results]
            scores = [1.0 - r.distance for r in results]

            matched = any(case.expected.lower() in d.lower() for d in descriptions)

            s = stats.setdefault(case.sheet, _SheetStats())
            if matched:
                s.passed += 1
                if verbosity >= 1:
                    top = f"{descriptions[0]!r} ({scores[0]:.2f})" if descriptions else "(none)"
                    marker = "✓" if verbosity >= 2 else ""
                    print(f"  {'✓ ' if verbosity >= 2 else ''}[{i:03d}] {case.query!r}")
                    if verbosity >= 2:
                        print(f"         → {top}")
            else:
                s.failed += 1
                got = descriptions[0] if descriptions else "(no results)"
                got_score = scores[0] if scores else 0.0
                failures.append(_Failure(
                    n=i,
                    sheet=case.sheet,
                    query=case.query,
                    expected=case.expected,
                    top_k=case.top_k,
                    got=got,
                    got_score=got_score,
                    all_results=list(zip(descriptions, scores)),
                ))

    total = len(cases)
    passed = sum(s.passed for s in stats.values())
    failed = total - passed

    W = 62
    print(f"\n{'═' * W}")
    print(f"  Search Quality Report")
    print(f"{'═' * W}")
    print(f"  Total : {total}")
    print(f"  Passed: {passed}  ({100 * passed / total:.1f}%)")
    print(f"  Failed: {failed}  ({100 * failed / total:.1f}%)")
    print()

    print("  Per-sheet breakdown:")
    for sheet, s in sorted(stats.items()):
        n = s.passed + s.failed
        pct = 100 * s.passed / n if n else 0.0
        filled = round(pct / 5)
        bar = "█" * filled + "░" * (20 - filled)
        print(f"    {sheet:<8} [{bar}] {s.passed}/{n} ({pct:.0f}%)")
    print()

    if failures:
        print(f"  Failures ({len(failures)}):")
        print(f"  {'─' * (W - 2)}")
        for f in failures:
            print(f"  [{f.n:03d}] sheet={f.sheet!r}  top_k={f.top_k}")
            print(f"        query    : {f.query!r}")
            print(f"        expected : {f.expected!r}")
            print(f"        got      : {f.got!r} (score={f.got_score:.2f})")
            if f.all_results:
                print(f"        top-{f.top_k} returned:")
                for desc, score in f.all_results[:f.top_k]:
                    hit = "✓" if f.expected.lower() in desc.lower() else " "
                    print(f"          [{hit}] {score:.2f}  {desc!r}")
            print()
    else:
        print("  All cases passed! ✓")

    print("═" * W)
    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cheatsheet-eval",
        description="Evaluate semantic search quality across all cheatsheets.",
    )
    parser.add_argument(
        "--sheet", "-s", default=None,
        help="Restrict evaluation to a single sheet (tmux, vim, nvim).",
    )
    parser.add_argument(
        "--tol", type=float, default=None,
        help="Minimum cosine similarity (0–1) to count a result. "
             "Results below this threshold are filtered out.",
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0,
        help="Show passing cases (-v) or passing cases with the top result (-vv).",
    )
    args = parser.parse_args()
    sys.exit(_run(sheet_filter=args.sheet, tol=args.tol, verbosity=args.verbose))
