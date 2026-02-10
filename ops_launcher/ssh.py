"""SSH target building and connection utilities.

Builds SSH command lines from Host config, respecting ssh_alias,
custom ports, and global SSH default options. Never stores passwords.
"""

from __future__ import annotations

from ops_launcher.config import Host, SSHDefaults


def build_ssh_command(
    host: Host,
    ssh_defaults: SSHDefaults,
    *,
    extra_args: list[str] | None = None,
    remote_command: str | None = None,
    allocate_tty: bool = False,
) -> list[str]:
    """Build a complete ``ssh`` command list for the given host.

    Parameters
    ----------
    host:
        The target host config.
    ssh_defaults:
        Global SSH options from config.
    extra_args:
        Additional CLI flags to pass to ssh.
    remote_command:
        A command to execute on the remote host instead of opening a shell.
    allocate_tty:
        If True, pass ``-t`` to force TTY allocation (needed for interactive
        remote commands).
    """
    cmd: list[str] = ["ssh"]

    # Global default options
    cmd.extend(ssh_defaults.options)

    # Port (only if not default and not using alias)
    if not host.ssh_alias and host.port != 22:
        cmd.extend(["-p", str(host.port)])

    # TTY allocation
    if allocate_tty:
        cmd.append("-t")

    # Extra args
    if extra_args:
        cmd.extend(extra_args)

    # Target
    cmd.append(host.ssh_target)

    # Remote command
    if remote_command:
        cmd.append(remote_command)

    return cmd


def build_scp_command(
    host: Host,
    ssh_defaults: SSHDefaults,
    *,
    source: str,
    dest: str,
    recursive: bool = False,
) -> list[str]:
    """Build an ``scp`` command (placeholder for future use)."""
    cmd: list[str] = ["scp"]
    cmd.extend(ssh_defaults.options)

    if not host.ssh_alias and host.port != 22:
        cmd.extend(["-P", str(host.port)])

    if recursive:
        cmd.append("-r")

    cmd.extend([source, f"{host.ssh_target}:{dest}"])
    return cmd


def build_remote_command(
    host: Host,
    ssh_defaults: SSHDefaults,
    remote_cmd: str,
    *,
    allocate_tty: bool = False,
) -> list[str]:
    """Build an SSH command that executes a remote command."""
    return build_ssh_command(
        host,
        ssh_defaults,
        remote_command=remote_cmd,
        allocate_tty=allocate_tty,
    )
