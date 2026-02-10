"""Typer CLI application for ops-launcher.

Provides both interactive TUI mode (default) and non-interactive commands
for scripting: ssh, health, docker, compose, ls, config.
"""

from __future__ import annotations

from typing import Annotated, Optional

import typer
from rich.panel import Panel

from ops_launcher import __version__
from ops_launcher.config import (
    ConfigError,
    HostResolutionError,
    OpsConfig,
    load_config,
)
from ops_launcher.utils import console, print_error, print_info

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="ops",
    help="⚡ Ops Launcher — interactive terminal tool for managing infrastructure.",
    no_args_is_help=False,
    rich_markup_mode="rich",
    add_completion=True,
)

docker_app = typer.Typer(
    name="docker",
    help="Docker commands on remote hosts.",
    rich_markup_mode="rich",
)

compose_app = typer.Typer(
    name="compose",
    help="Docker Compose commands on remote hosts.",
    rich_markup_mode="rich",
)

# Future stubs
gcp_app = typer.Typer(
    name="gcp",
    help="[dim]Google Cloud Platform shortcuts (coming soon).[/dim]",
    rich_markup_mode="rich",
)

tf_app = typer.Typer(
    name="tf",
    help="[dim]Terraform shortcuts (coming soon).[/dim]",
    rich_markup_mode="rich",
)

app.add_typer(docker_app, name="docker")
app.add_typer(compose_app, name="compose")
app.add_typer(gcp_app, name="gcp")
app.add_typer(tf_app, name="tf")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_config_or_exit() -> OpsConfig:
    """Load config, printing a helpful error and exiting on failure."""
    try:
        return load_config()
    except ConfigError as exc:
        print_error(str(exc))
        raise typer.Exit(1)


def _resolve_host_or_exit(config: OpsConfig, host_ref: str):
    """Resolve a host reference, exiting with a clear message on failure."""
    try:
        return config.resolve_host(host_ref)
    except HostResolutionError as exc:
        print_error(str(exc))
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# Default callback — interactive TUI when no subcommand given
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool, typer.Option("--version", "-V", help="Show version and exit.")
    ] = False,
):
    """⚡ Ops Launcher — run with no arguments for interactive mode."""
    if version:
        console.print(f"ops-launcher [bold]{__version__}[/bold]")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        # Interactive TUI mode
        config = _load_config_or_exit()
        from ops_launcher.tui import run_tui

        run_tui(config)


# ---------------------------------------------------------------------------
# ops ls
# ---------------------------------------------------------------------------


@app.command("ls")
def cmd_ls(
    search: Annotated[
        Optional[str], typer.Argument(help="Optional search filter.")
    ] = None,
):
    """List all clients and hosts in a table."""
    config = _load_config_or_exit()

    if search:
        from ops_launcher.tui import print_hosts_table

        # Create a filtered config view
        matched = config.search_hosts(search)
        if not matched:
            print_info(f"No hosts matching '{search}'.")
            raise typer.Exit()

        # Group back into clients for display
        from ops_launcher.config import Client

        clients_map: dict[str, list] = {}
        for h in matched:
            clients_map.setdefault(h.client, []).append(h)

        filtered_clients = []
        for cname, hosts in clients_map.items():
            orig = config.get_client(cname)
            filtered_clients.append(
                Client(name=cname, description=orig.description if orig else "", hosts=hosts)
            )

        filtered_cfg = OpsConfig(
            version=config.version,
            ssh_defaults=config.ssh_defaults,
            clients=filtered_clients,
            config_path=config.config_path,
        )
        filtered_cfg._build_indexes()
        print_hosts_table(filtered_cfg)
    else:
        from ops_launcher.tui import print_hosts_table

        print_hosts_table(config)


# ---------------------------------------------------------------------------
# ops ssh
# ---------------------------------------------------------------------------


@app.command("ssh")
def cmd_ssh(
    host_ref: Annotated[str, typer.Argument(help="Host name or client:host.")],
):
    """Open an SSH session to a host."""
    config = _load_config_or_exit()
    host = _resolve_host_or_exit(config, host_ref)

    from ops_launcher.executor import exec_replace
    from ops_launcher.ssh import build_ssh_command

    cmd = build_ssh_command(host, config.ssh_defaults)
    exec_replace(cmd)


# ---------------------------------------------------------------------------
# ops health
# ---------------------------------------------------------------------------


@app.command("health")
def cmd_health(
    host_ref: Annotated[str, typer.Argument(help="Host name or client:host.")],
):
    """Run health checks on a remote host (uptime, disk, memory, load)."""
    config = _load_config_or_exit()
    host = _resolve_host_or_exit(config, host_ref)

    from ops_launcher.actions import BUILTIN_ACTIONS, build_action_command
    from ops_launcher.executor import run_streaming

    action = next(a for a in BUILTIN_ACTIONS if a.name == "health")
    cmd = build_action_command(action, host, config.ssh_defaults)
    exit_code = run_streaming(cmd)
    raise typer.Exit(exit_code)


# ---------------------------------------------------------------------------
# ops docker ps / logs / stats
# ---------------------------------------------------------------------------


@docker_app.command("ps")
def docker_ps(
    host_ref: Annotated[str, typer.Argument(help="Host name or client:host.")],
):
    """List running Docker containers on a remote host."""
    config = _load_config_or_exit()
    host = _resolve_host_or_exit(config, host_ref)

    from ops_launcher.actions import BUILTIN_ACTIONS, build_action_command
    from ops_launcher.executor import run_streaming

    action = next(a for a in BUILTIN_ACTIONS if a.name == "docker_ps")
    cmd = build_action_command(action, host, config.ssh_defaults)
    exit_code = run_streaming(cmd)
    raise typer.Exit(exit_code)


@docker_app.command("logs")
def docker_logs(
    host_ref: Annotated[str, typer.Argument(help="Host name or client:host.")],
    service: Annotated[str, typer.Argument(help="Container or service name.")],
    follow: Annotated[bool, typer.Option("--follow", "-f", help="Follow log output.")] = False,
):
    """Tail Docker logs for a container on a remote host."""
    config = _load_config_or_exit()
    host = _resolve_host_or_exit(config, host_ref)

    from ops_launcher.actions import BUILTIN_ACTIONS, build_action_command
    from ops_launcher.executor import run_interactive, run_streaming

    action = next(a for a in BUILTIN_ACTIONS if a.name == "docker_logs")
    cmd = build_action_command(action, host, config.ssh_defaults, service=service, follow=follow)

    if follow:
        exit_code = run_interactive(cmd)
    else:
        exit_code = run_streaming(cmd)
    raise typer.Exit(exit_code)


@docker_app.command("stats")
def docker_stats(
    host_ref: Annotated[str, typer.Argument(help="Host name or client:host.")],
):
    """Show Docker resource usage on a remote host."""
    config = _load_config_or_exit()
    host = _resolve_host_or_exit(config, host_ref)

    from ops_launcher.actions import BUILTIN_ACTIONS, build_action_command
    from ops_launcher.executor import run_streaming

    action = next(a for a in BUILTIN_ACTIONS if a.name == "docker_stats")
    cmd = build_action_command(action, host, config.ssh_defaults)
    exit_code = run_streaming(cmd)
    raise typer.Exit(exit_code)


# ---------------------------------------------------------------------------
# ops compose ps / up / down / restart / logs
# ---------------------------------------------------------------------------


def _compose_command(
    host_ref: str,
    action_name: str,
    compose_path: str | None = None,
):
    """Shared logic for compose subcommands."""
    config = _load_config_or_exit()
    host = _resolve_host_or_exit(config, host_ref)

    from ops_launcher.actions import BUILTIN_ACTIONS, build_action_command
    from ops_launcher.executor import run_interactive, run_streaming
    from ops_launcher.utils import confirm_action

    action = next(a for a in BUILTIN_ACTIONS if a.name == action_name)

    if action.destructive:
        if not confirm_action(f"Run '{action.label}' on {host.display}?"):
            print_info("Cancelled.")
            raise typer.Exit(0)

    cmd = build_action_command(
        action, host, config.ssh_defaults, compose_path=compose_path
    )

    if action_name == "compose_logs":
        exit_code = run_interactive(cmd)
    else:
        exit_code = run_streaming(cmd)
    raise typer.Exit(exit_code)


@compose_app.command("ps")
def compose_ps_cmd(
    host_ref: Annotated[str, typer.Argument(help="Host name or client:host.")],
    project_dir: Annotated[
        Optional[str], typer.Option("--project-dir", "-d", help="Remote compose project directory.")
    ] = None,
):
    """Show Docker Compose service status."""
    _compose_command(host_ref, "compose_ps", project_dir)


@compose_app.command("up")
def compose_up_cmd(
    host_ref: Annotated[str, typer.Argument(help="Host name or client:host.")],
    project_dir: Annotated[
        Optional[str], typer.Option("--project-dir", "-d", help="Remote compose project directory.")
    ] = None,
):
    """Start Docker Compose services (detached)."""
    _compose_command(host_ref, "compose_up", project_dir)


@compose_app.command("down")
def compose_down_cmd(
    host_ref: Annotated[str, typer.Argument(help="Host name or client:host.")],
    project_dir: Annotated[
        Optional[str], typer.Option("--project-dir", "-d", help="Remote compose project directory.")
    ] = None,
):
    """Stop and remove Docker Compose services. [red]Destructive.[/red]"""
    _compose_command(host_ref, "compose_down", project_dir)


@compose_app.command("restart")
def compose_restart_cmd(
    host_ref: Annotated[str, typer.Argument(help="Host name or client:host.")],
    project_dir: Annotated[
        Optional[str], typer.Option("--project-dir", "-d", help="Remote compose project directory.")
    ] = None,
):
    """Restart Docker Compose services. [red]Destructive.[/red]"""
    _compose_command(host_ref, "compose_restart", project_dir)


@compose_app.command("logs")
def compose_logs_cmd(
    host_ref: Annotated[str, typer.Argument(help="Host name or client:host.")],
    project_dir: Annotated[
        Optional[str], typer.Option("--project-dir", "-d", help="Remote compose project directory.")
    ] = None,
):
    """Tail Docker Compose logs (follow mode)."""
    _compose_command(host_ref, "compose_logs", project_dir)


# ---------------------------------------------------------------------------
# ops config
# ---------------------------------------------------------------------------


@app.command("config")
def cmd_config():
    """Show active config path and validate it."""
    from ops_launcher.config import get_config_path, validate_config_file

    path = get_config_path()
    console.print(Panel(
        f"[bold]Config path:[/bold] {path}\n"
        f"[bold]Env var:[/bold]    {('OPS_CONFIG=' + str(path)) if 'OPS_CONFIG' in __import__('os').environ else '[dim]not set[/dim]'}",
        title="[bold]ops-launcher config[/bold]",
        border_style="blue",
    ))

    ok, msg = validate_config_file()
    if ok:
        console.print(f"[green]✓ {msg}[/green]")
    else:
        print_error(msg)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# GCP stubs (future)
# ---------------------------------------------------------------------------


@gcp_app.callback(invoke_without_command=True)
def gcp_main(ctx: typer.Context):
    """Google Cloud Platform shortcuts."""
    if ctx.invoked_subcommand is None:
        console.print("[yellow]GCP subcommands coming soon. See `ops gcp --help`.[/yellow]")


@gcp_app.command("auth")
def gcp_auth():
    """[dim]TODO: gcloud auth login[/dim]"""
    # TODO: Implement gcloud auth login
    console.print("[yellow]Not implemented yet. Will run: gcloud auth login[/yellow]")
    raise typer.Exit(0)


@gcp_app.command("set-project")
def gcp_set_project(
    project_id: Annotated[str, typer.Argument(help="GCP project ID.")],
):
    """[dim]TODO: gcloud config set project[/dim]"""
    # TODO: Implement gcloud config set project
    console.print(f"[yellow]Not implemented yet. Will run: gcloud config set project {project_id}[/yellow]")
    raise typer.Exit(0)


@gcp_app.command("clusters")
def gcp_clusters():
    """[dim]TODO: gcloud container clusters list[/dim]"""
    # TODO: Implement gcloud container clusters list
    console.print("[yellow]Not implemented yet. Will run: gcloud container clusters list[/yellow]")
    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# Terraform stubs (future)
# ---------------------------------------------------------------------------


@tf_app.callback(invoke_without_command=True)
def tf_main(ctx: typer.Context):
    """Terraform shortcuts."""
    if ctx.invoked_subcommand is None:
        console.print("[yellow]Terraform subcommands coming soon. See `ops tf --help`.[/yellow]")


@tf_app.command("init")
def tf_init():
    """[dim]TODO: terraform init[/dim]"""
    # TODO: Implement terraform init
    console.print("[yellow]Not implemented yet. Will run: terraform init[/yellow]")
    raise typer.Exit(0)


@tf_app.command("plan")
def tf_plan():
    """[dim]TODO: terraform plan[/dim]"""
    # TODO: Implement terraform plan
    console.print("[yellow]Not implemented yet. Will run: terraform plan[/yellow]")
    raise typer.Exit(0)


@tf_app.command("apply")
def tf_apply():
    """[dim]TODO: terraform apply (requires confirmation)[/dim]"""
    # TODO: Implement terraform apply with confirmation
    from ops_launcher.utils import confirm_action

    if not confirm_action("Run terraform apply?"):
        print_info("Cancelled.")
        raise typer.Exit(0)
    console.print("[yellow]Not implemented yet. Will run: terraform apply[/yellow]")
    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def app_entry() -> None:
    """Console script entry point for ``ops``."""
    app()
