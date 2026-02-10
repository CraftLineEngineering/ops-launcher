"""Rich-based interactive TUI for ops-launcher.

Implements the guided interactive menu flow:
  Welcome → Select Client → Select Host → Select Action → Execute → Loop
"""

from __future__ import annotations

import sys

from rich.table import Table

from ops_launcher.actions import (
    Action,
    build_action_command,
    get_actions_for_host,
)
from ops_launcher.config import Host, OpsConfig
from ops_launcher.executor import run_capture_remote, run_interactive, run_streaming
from ops_launcher.ssh import build_remote_command
from ops_launcher.utils import (
    confirm_action,
    console,
    print_error,
    print_info,
    print_success,
    select_with_filter,
    welcome_panel,
)

# ---------------------------------------------------------------------------
# Interactive flow
# ---------------------------------------------------------------------------


def run_tui(config: OpsConfig) -> None:
    """Main interactive TUI entry point."""
    welcome_panel(
        config_path=str(config.config_path),
        host_count=len(config.all_hosts),
        client_count=len(config.clients),
    )

    while True:
        selection = _select_client_or_recent(config)
        if selection is None:
            console.print("[yellow]Goodbye![/yellow]")
            sys.exit(0)

        # If a Host was returned directly (from recent), skip to action loop
        if isinstance(selection, Host):
            host = selection
            while True:
                should_continue = _select_and_run_action(host, config)
                if not should_continue:
                    break
            continue

        # Otherwise it's a client index
        client = config.clients[selection]

        while True:
            host_idx = _select_host(client.hosts, client.name)
            if host_idx is None:
                break  # back to client selection

            host = client.hosts[host_idx]

            while True:
                should_continue = _select_and_run_action(host, config)
                if not should_continue:
                    break  # back to host selection


def _select_client_or_recent(config: OpsConfig) -> int | Host | None:
    """Show client selection menu with recent hosts at the top.

    Returns:
      - int: client index selected
      - Host: a recent host selected directly
      - None: user chose exit
    """
    recent_names = load_recent_hosts()
    recent_hosts: list[Host] = []
    for ref in recent_names:
        try:
            recent_hosts.append(config.resolve_host(ref))
        except Exception:
            continue  # stale entry, skip

    labels: list[str] = []
    # Map display index → either ("recent", Host) or ("client", int)
    index_map: list[tuple[str, Host | int]] = []

    if recent_hosts:
        for h in recent_hosts:
            tags_str = ", ".join(h.tags[:3]) if h.tags else ""
            labels.append(
                f"[bold yellow]⚡[/bold yellow] [bold]{h.display}[/bold]  "
                f"[cyan]{h.ssh_target}[/cyan]  [dim][{tags_str}][/dim]"
            )
            index_map.append(("recent", h))

    for i, c in enumerate(config.clients):
        host_count = len(c.hosts)
        desc = f" — {c.description}" if c.description else ""
        labels.append(f"[bold]{c.name}[/bold]  [dim]({host_count} hosts){desc}[/dim]")
        index_map.append(("client", i))

    idx = select_with_filter(
        labels,
        title="Select Client or Recent Host",
        allow_back=False,
        allow_exit=True,
    )
    if idx is None:
        return None

    kind, value = index_map[idx]
    if kind == "recent":
        assert isinstance(value, Host)
        return value
    assert isinstance(value, int)
    return value


def _select_host(hosts: list[Host], client_name: str) -> int | None:
    """Show host selection menu for a client. Returns index or None."""
    labels = []
    for h in hosts:
        tags_str = ", ".join(h.tags) if h.tags else "no tags"
        labels.append(
            f"[bold]{h.name}[/bold]  [cyan]{h.ssh_target}[/cyan]  [dim][{tags_str}][/dim]"
        )

    return select_with_filter(
        labels,
        title=f"Select Host — {client_name}",
        allow_back=True,
        allow_exit=True,
    )


def _select_and_run_action(host: Host, config: OpsConfig) -> bool:
    """Show action menu and execute. Returns True to stay on same host, False to go back."""
    actions = get_actions_for_host(host)
    if not actions:
        print_error(f"No actions available for {host.display}.")
        return False

    labels = []
    for a in actions:
        destructive_mark = " [red]⚠[/red]" if a.destructive else ""
        labels.append(f"[bold]{a.label}[/bold]{destructive_mark}  [dim]{a.description}[/dim]")

    action_idx = select_with_filter(
        labels,
        title=f"Action — {host.display}",
        allow_back=True,
        allow_exit=True,
    )

    if action_idx is None:
        return False  # back to host selection

    action = actions[action_idx]
    _execute_action(action, host, config)
    return True  # stay on same host's action menu


def _pick_remote_service(host: Host, config: OpsConfig) -> str | None:
    """Discover running services/containers on a remote host and let the user pick one.

    Tries docker compose ps --services first (if compose_path is set or auto-detected),
    then falls back to docker ps --format to list running containers.
    Returns the selected service/container name or None.
    """
    from rich.prompt import Prompt

    services: list[str] = []

    # Try docker compose ps --services first
    cd_prefix = f"cd {host.compose_path} && " if host.compose_path else ""
    compose_cmd = build_remote_command(
        host, config.ssh_defaults,
        f"{cd_prefix}docker compose ps --services 2>/dev/null",
    )
    console.print("  [dim]Discovering compose services...[/dim]")
    rc, output = run_capture_remote(compose_cmd)
    if rc == 0 and output.strip():
        services = [s.strip() for s in output.strip().splitlines() if s.strip()]

    # Fallback: list running container names
    if not services:
        docker_cmd = build_remote_command(
            host, config.ssh_defaults,
            "docker ps --format '{{.Names}}' 2>/dev/null",
        )
        console.print("  [dim]Discovering running containers...[/dim]")
        rc, output = run_capture_remote(docker_cmd)
        if rc == 0 and output.strip():
            services = [s.strip() for s in output.strip().splitlines() if s.strip()]

    if not services:
        print_error("No running services or containers found on this host.")
        # Allow manual entry as last resort
        manual = Prompt.ask("  Enter container name manually (empty to cancel)", default="")
        return manual if manual else None

    labels = [f"[bold]{svc}[/bold]" for svc in services]
    idx = select_with_filter(labels, title="Select Service / Container")
    if idx is None:
        return None
    return services[idx]


def _execute_action(action: Action, host: Host, config: OpsConfig) -> None:
    """Execute the selected action."""
    # Destructive actions require confirmation
    if action.destructive and not confirm_action(f"Run '{action.label}' on {host.display}?"):
        print_info("Cancelled.")
        return

    # For docker logs, discover services remotely and let user pick
    service: str | None = None
    if action.name == "docker_logs":
        service = _pick_remote_service(host, config)
        if not service:
            print_info("No service selected, cancelled.")
            return

    # Use host's compose_path if available and no explicit override
    compose_path = host.compose_path

    cmd = build_action_command(
        action,
        host,
        config.ssh_defaults,
        service=service,
        follow=(action.name in ("docker_logs", "compose_logs")),
        compose_path=compose_path,
    )

    # Record host usage for recent history
    record_host_usage(host.name)

    # SSH action uses exec-style (interactive), others use streaming
    exit_code = run_interactive(cmd) if action.name == "ssh" else run_streaming(cmd)

    if exit_code == 0:
        print_success(f"{action.label} completed successfully.")
    else:
        print_error(f"{action.label} exited with code {exit_code}.")


# ---------------------------------------------------------------------------
# Table display (used by `ops ls`)
# ---------------------------------------------------------------------------


def print_hosts_table(config: OpsConfig) -> None:
    """Print a Rich table of all clients and hosts."""
    table = Table(
        title="Ops Launcher — All Hosts",
        show_header=True,
        header_style="bold magenta",
        border_style="bright_blue",
        show_lines=False,
    )
    table.add_column("Client", style="bold", min_width=10)
    table.add_column("Host", style="cyan", min_width=15)
    table.add_column("SSH Target", min_width=20)
    table.add_column("Port", justify="right", min_width=5)
    table.add_column("Tags", style="green", min_width=15)

    for client in config.clients:
        for i, host in enumerate(client.hosts):
            client_cell = client.name if i == 0 else ""
            tags = ", ".join(host.tags) if host.tags else "—"
            table.add_row(
                client_cell,
                host.name,
                host.ssh_target,
                str(host.port),
                tags,
            )
        # Add visual separator between clients (except after the last one)
        if client != config.clients[-1]:
            table.add_row("", "", "", "", "")

    console.print()
    console.print(table)
    console.print()
