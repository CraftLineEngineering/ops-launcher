"""Configuration loader, validation, and host resolution for ops-launcher.

Loads YAML config from ~/.config/ops-launcher/hosts.yaml (or OPS_CONFIG env override).
Provides typed dataclasses, validation, and fast host lookup by name or client:name.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_NAME = "ops-launcher"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / APP_NAME
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "hosts.yaml"
ENV_CONFIG_VAR = "OPS_CONFIG"
SUPPORTED_CONFIG_VERSION = 1

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Host:
    """A single managed host."""

    name: str
    host: str
    user: str = "root"
    port: int = 22
    tags: list[str] = field(default_factory=list)
    ssh_alias: str | None = None
    client: str = ""  # back-reference populated at load time
    compose_path: str | None = None  # remote path to docker-compose project dir
    stack_name: str | None = None    # docker compose project/stack name
    project_dir: str | None = None   # general-purpose remote project directory

    @property
    def display(self) -> str:
        return f"{self.client}:{self.name}" if self.client else self.name

    @property
    def ssh_target(self) -> str:
        """Return the SSH destination string."""
        if self.ssh_alias:
            return self.ssh_alias
        return f"{self.user}@{self.host}"


@dataclass(frozen=True, slots=True)
class Client:
    """A client grouping of hosts."""

    name: str
    description: str = ""
    hosts: list[Host] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SSHDefaults:
    """Default SSH options applied globally."""

    options: list[str] = field(default_factory=lambda: ["-o", "ConnectTimeout=10"])


@dataclass(slots=True)
class OpsConfig:
    """Top-level ops-launcher configuration."""

    version: int = SUPPORTED_CONFIG_VERSION
    ssh_defaults: SSHDefaults = field(default_factory=SSHDefaults)
    clients: list[Client] = field(default_factory=list)
    config_path: Path = DEFAULT_CONFIG_PATH

    # ---------- lookup caches (built once) ----------
    _hosts_by_name: dict[str, list[Host]] = field(default_factory=dict, repr=False)
    _all_hosts: list[Host] = field(default_factory=list, repr=False)

    def _build_indexes(self) -> None:
        """Build fast lookup indexes after loading."""
        self._hosts_by_name.clear()
        self._all_hosts.clear()
        for client in self.clients:
            for host in client.hosts:
                self._all_hosts.append(host)
                self._hosts_by_name.setdefault(host.name, []).append(host)

    @property
    def all_hosts(self) -> list[Host]:
        return list(self._all_hosts)

    def resolve_host(self, ref: str) -> Host:
        """Resolve a host reference.

        Accepts:
          - ``name``          — unique host name across all clients
          - ``client:name``   — fully qualified

        Raises ``HostResolutionError`` on ambiguity or missing host.
        """
        if ":" in ref:
            client_name, host_name = ref.split(":", 1)
            for client in self.clients:
                if client.name == client_name:
                    for host in client.hosts:
                        if host.name == host_name:
                            return host
            raise HostResolutionError(
                f"Host '{host_name}' not found under client '{client_name}'."
            )

        matches = self._hosts_by_name.get(ref, [])
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            clients = ", ".join(h.client for h in matches)
            raise HostResolutionError(
                f"Ambiguous host name '{ref}' exists in clients: {clients}. "
                f"Use client:host format (e.g. '{matches[0].client}:{ref}')."
            )
        raise HostResolutionError(
            f"Unknown host '{ref}'. Run `ops ls` to see available hosts."
        )

    def search_hosts(self, query: str) -> list[Host]:
        """Simple case-insensitive substring search across name, host, tags."""
        q = query.lower()
        results: list[Host] = []
        for host in self._all_hosts:
            haystack = f"{host.name} {host.host} {host.client} {' '.join(host.tags)}".lower()
            if q in haystack:
                results.append(host)
        return results

    def get_client(self, name: str) -> Client | None:
        for c in self.clients:
            if c.name == name:
                return c
        return None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Raised when the configuration file is invalid or missing."""


class HostResolutionError(Exception):
    """Raised when a host reference cannot be resolved."""


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def get_config_path() -> Path:
    """Determine which config file to use."""
    env = os.environ.get(ENV_CONFIG_VAR)
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_CONFIG_PATH


def _parse_host(data: dict[str, Any], client_name: str) -> Host:
    """Parse a single host entry from YAML."""
    name = data.get("name")
    if not name:
        raise ConfigError(f"Host under client '{client_name}' is missing required field 'name'.")
    hostname = data.get("host")
    if not hostname:
        raise ConfigError(f"Host '{name}' under client '{client_name}' is missing 'host' field.")
    return Host(
        name=str(name),
        host=str(hostname),
        user=str(data.get("user", "root")),
        port=int(data.get("port", 22)),
        tags=[str(t) for t in data.get("tags", [])],
        ssh_alias=data.get("ssh_alias"),
        client=client_name,
        compose_path=data.get("compose_path"),
        stack_name=data.get("stack_name"),
        project_dir=data.get("project_dir"),
    )


def _parse_client(name: str, data: dict[str, Any]) -> Client:
    """Parse a single client entry from YAML."""
    hosts_data = data.get("hosts", [])
    if not isinstance(hosts_data, list):
        raise ConfigError(f"Client '{name}' 'hosts' must be a list.")
    hosts = [_parse_host(h, name) for h in hosts_data]
    return Client(
        name=name,
        description=str(data.get("description", "")),
        hosts=hosts,
    )


def load_config(path: Path | None = None) -> OpsConfig:
    """Load, validate, and return OpsConfig from a YAML file."""
    config_path = path or get_config_path()

    if not config_path.exists():
        raise ConfigError(
            f"Config file not found at {config_path}\n"
            f"Run the install script or copy examples/hosts.yaml to {DEFAULT_CONFIG_PATH}\n"
            f"You can also set {ENV_CONFIG_VAR} environment variable."
        )

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Config file {config_path} must be a YAML mapping at the top level.")

    version = raw.get("version", SUPPORTED_CONFIG_VERSION)
    if version != SUPPORTED_CONFIG_VERSION:
        raise ConfigError(
            f"Unsupported config version {version}. Expected {SUPPORTED_CONFIG_VERSION}."
        )

    # SSH defaults
    defaults_raw = raw.get("defaults", {})
    ssh_opts = defaults_raw.get("ssh_options", ["-o", "ConnectTimeout=10"])
    ssh_defaults = SSHDefaults(options=list(ssh_opts))

    # Clients
    clients_raw = raw.get("clients", {})
    if not isinstance(clients_raw, dict):
        raise ConfigError("'clients' must be a mapping of client_name -> {description, hosts}.")
    clients = [_parse_client(cname, cdata) for cname, cdata in clients_raw.items()]

    config = OpsConfig(
        version=version,
        ssh_defaults=ssh_defaults,
        clients=clients,
        config_path=config_path,
    )
    config._build_indexes()
    return config


def validate_config_file(path: Path | None = None) -> tuple[bool, str]:
    """Validate a config file and return (ok, message)."""
    try:
        cfg = load_config(path)
        host_count = len(cfg.all_hosts)
        client_count = len(cfg.clients)
        return True, (
            f"Config OK — {client_count} client(s), {host_count} host(s) "
            f"loaded from {cfg.config_path}"
        )
    except ConfigError as exc:
        return False, str(exc)
