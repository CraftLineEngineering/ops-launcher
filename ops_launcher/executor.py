"""Subprocess runner with streaming output and error handling.

Wraps subprocess calls to provide consistent UX: command preview,
live streaming output, proper exit code propagation, and Rich formatting.
"""

from __future__ import annotations

import os
import subprocess
import sys

from ops_launcher.utils import console, err_console, print_command_preview


def run_interactive(cmd: list[str], *, preview: bool = True) -> int:
    """Run a command interactively, inheriting the terminal's stdin/stdout/stderr.

    Used for SSH sessions and other commands that need full terminal control.
    Returns the process exit code.
    """
    if preview:
        print_command_preview(cmd)

    try:
        result = subprocess.run(cmd, env=os.environ.copy())
        return result.returncode
    except FileNotFoundError:
        err_console.print(f"[bold red]Command not found:[/bold red] {cmd[0]}")
        return 127
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        return 130


def run_streaming(cmd: list[str], *, preview: bool = True) -> int:
    """Run a command and stream its stdout/stderr to the console in real time.

    Used for health checks, docker commands, and other non-interactive operations.
    Returns the process exit code.
    """
    if preview:
        print_command_preview(cmd)

    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=os.environ.copy(),
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            console.print(line, end="", highlight=False)
        proc.wait()
        return proc.returncode
    except FileNotFoundError:
        err_console.print(f"[bold red]Command not found:[/bold red] {cmd[0]}")
        return 127
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
        if proc is not None and proc.poll() is None:
            proc.terminate()
        return 130


def run_capture(cmd: list[str], *, preview: bool = False) -> tuple[int, str]:
    """Run a command and capture its output as a string.

    Returns (exit_code, combined_output).
    """
    if preview:
        print_command_preview(cmd)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=os.environ.copy(),
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 124, "Command timed out after 30 seconds."
    except FileNotFoundError:
        return 127, f"Command not found: {cmd[0]}"


def run_capture_remote(
    cmd: list[str], *, timeout: int = 15
) -> tuple[int, str]:
    """Run a command and capture output silently (no preview).

    Like run_capture but with a configurable timeout and no preview.
    Returns (exit_code, stdout_text).
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
        return result.returncode, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return 124, ""
    except FileNotFoundError:
        return 127, ""


def exec_replace(cmd: list[str], *, preview: bool = True) -> None:
    """Replace the current process with the given command (exec).

    Used for SSH to hand off the terminal completely.
    Does not return on success.
    """
    if preview:
        print_command_preview(cmd)

    try:
        os.execvp(cmd[0], cmd)
    except FileNotFoundError:
        err_console.print(f"[bold red]Command not found:[/bold red] {cmd[0]}")
        sys.exit(127)
