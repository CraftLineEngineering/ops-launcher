"""Shared prompt helpers, formatting, and fuzzy matching utilities."""

from __future__ import annotations

import sys
from typing import TypeVar

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

# ---------------------------------------------------------------------------
# Console singletons
# ---------------------------------------------------------------------------

console = Console()
err_console = Console(stderr=True)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Fuzzy / substring matcher
# ---------------------------------------------------------------------------


def fuzzy_match(query: str, candidates: list[str]) -> list[tuple[int, str]]:
    """Return (index, candidate) pairs where *query* is a case-insensitive subsequence.

    Results are sorted: exact prefix matches first, then subsequence matches.
    """
    q = query.lower()
    prefix_matches: list[tuple[int, str]] = []
    subseq_matches: list[tuple[int, str]] = []

    for idx, candidate in enumerate(candidates):
        c = candidate.lower()
        if q in c:
            if c.startswith(q):
                prefix_matches.append((idx, candidate))
            else:
                subseq_matches.append((idx, candidate))
        elif _is_subsequence(q, c):
            subseq_matches.append((idx, candidate))

    return prefix_matches + subseq_matches


def _is_subsequence(needle: str, haystack: str) -> bool:
    """Check if needle chars appear in order within haystack."""
    it = iter(haystack)
    return all(ch in it for ch in needle)


# ---------------------------------------------------------------------------
# Selection prompt with filter
# ---------------------------------------------------------------------------


def select_with_filter(
    items: list[str],
    title: str = "Select",
    *,
    allow_back: bool = True,
    allow_exit: bool = True,
) -> int | None:
    """Present a filterable numbered list and return the selected index, or None for back/exit.

    Typing a number selects directly; typing text filters the list.
    An empty input with allow_back returns None (go back).
    """
    if not items:
        err_console.print("[red]No items to display.[/red]")
        return None

    filtered = list(enumerate(items))  # (original_idx, label)
    current_filter = ""

    while True:
        console.print()
        console.rule(f"[bold cyan]{title}[/bold cyan]")
        if current_filter:
            console.print(f"  [dim]Filter: {current_filter}[/dim]")

        for display_num, (orig_idx, label) in enumerate(filtered, start=1):
            console.print(f"  [bold green]{display_num:>3}[/bold green]  {label}")

        hints: list[str] = []
        if allow_back:
            hints.append("[dim]empty=back[/dim]")
        if allow_exit:
            hints.append("[dim]q=exit[/dim]")
        hints.append("[dim]text=filter[/dim]")

        hint_str = "  ".join(hints)
        console.print(f"\n  {hint_str}")

        raw = Prompt.ask("  [bold]>[/bold]", default="")
        choice = raw.strip()

        # Back
        if choice == "" and allow_back:
            return None

        # Exit
        if choice.lower() == "q" and allow_exit:
            console.print("[yellow]Exiting.[/yellow]")
            sys.exit(0)

        # Clear filter
        if choice.lower() == "/":
            current_filter = ""
            filtered = list(enumerate(items))
            continue

        # Numeric selection
        if choice.isdigit():
            num = int(choice)
            if 1 <= num <= len(filtered):
                return filtered[num - 1][0]  # return original index
            err_console.print(f"[red]Invalid number. Choose 1-{len(filtered)}.[/red]")
            continue

        # Text filter
        current_filter = choice
        matches = fuzzy_match(choice, items)
        if matches:
            filtered = matches
        else:
            err_console.print("[yellow]No matches. Showing all.[/yellow]")
            filtered = list(enumerate(items))
            current_filter = ""


# ---------------------------------------------------------------------------
# Confirmation prompt
# ---------------------------------------------------------------------------


def confirm_action(message: str, *, default: bool = False) -> bool:
    """Ask the user to confirm a potentially destructive action."""
    return Confirm.ask(f"  [bold yellow]⚠ {message}[/bold yellow]", default=default)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def print_command_preview(cmd: list[str]) -> None:
    """Show the command that is about to be executed in dim style."""
    cmd_str = " ".join(cmd)
    console.print(f"\n  [dim]$ {cmd_str}[/dim]\n")


def print_error(msg: str) -> None:
    """Print an error message to stderr."""
    err_console.print(f"[bold red]Error:[/bold red] {msg}")


def print_success(msg: str) -> None:
    console.print(f"[bold green]✓[/bold green] {msg}")


def print_info(msg: str) -> None:
    console.print(f"[bold blue]ℹ[/bold blue] {msg}")


def welcome_panel(config_path: str, host_count: int, client_count: int) -> None:
    """Display the welcome panel for interactive mode."""
    body = Text.from_markup(
        f"[bold]Config:[/bold]   {config_path}\n"
        f"[bold]Clients:[/bold]  {client_count}\n"
        f"[bold]Hosts:[/bold]    {host_count}\n"
        f"\n"
        f"[dim]Type a number to select, text to filter, q to quit.[/dim]"
    )
    panel = Panel(
        body,
        title="[bold magenta]⚡ Ops Launcher[/bold magenta]",
        subtitle="[dim]v0.1.0[/dim]",
        border_style="bright_blue",
        padding=(1, 2),
    )
    console.print(panel)
