"""Action registry: defines available actions and maps them to executors.

Each action knows which tags it requires (if any), whether it's destructive,
and how to build the command(s) to execute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ops_launcher.config import Host, SSHDefaults
from ops_launcher.ssh import build_remote_command, build_ssh_command


class ActionCategory(str, Enum):
    SSH = "ssh"
    HEALTH = "health"
    DOCKER = "docker"
    COMPOSE = "compose"
    LOGS = "logs"
    GCP = "gcp"          # future
    TERRAFORM = "terraform"  # future


@dataclass(frozen=True, slots=True)
class Action:
    """An executable action."""

    name: str
    label: str
    category: ActionCategory
    required_tags: list[str] = field(default_factory=list)
    destructive: bool = False
    description: str = ""

    def is_available_for(self, host: Host) -> bool:
        """Check if this action is applicable for the given host's tags."""
        if not self.required_tags:
            return True  # universal action
        return all(tag in host.tags for tag in self.required_tags)


# ---------------------------------------------------------------------------
# Built-in actions
# ---------------------------------------------------------------------------

BUILTIN_ACTIONS: list[Action] = [
    Action(
        name="ssh",
        label="SSH Connect",
        category=ActionCategory.SSH,
        description="Open an interactive SSH session.",
    ),
    Action(
        name="health",
        label="Health Check",
        category=ActionCategory.HEALTH,
        description="Run basic health checks (uptime, disk, memory, load).",
    ),
    Action(
        name="docker_ps",
        label="Docker PS",
        category=ActionCategory.DOCKER,
        required_tags=["docker"],
        description="List running containers.",
    ),
    Action(
        name="docker_stats",
        label="Docker Stats",
        category=ActionCategory.DOCKER,
        required_tags=["docker"],
        description="Show live container resource usage.",
    ),
    Action(
        name="docker_logs",
        label="Docker Logs (select service)",
        category=ActionCategory.DOCKER,
        required_tags=["docker"],
        description="Tail logs for a docker compose service.",
    ),
    Action(
        name="compose_ps",
        label="Compose PS",
        category=ActionCategory.COMPOSE,
        required_tags=["docker"],
        description="Show compose service status.",
    ),
    Action(
        name="compose_up",
        label="Compose Up",
        category=ActionCategory.COMPOSE,
        required_tags=["docker"],
        destructive=False,
        description="Start compose services (detached).",
    ),
    Action(
        name="compose_down",
        label="Compose Down",
        category=ActionCategory.COMPOSE,
        required_tags=["docker"],
        destructive=True,
        description="Stop and remove compose services.",
    ),
    Action(
        name="compose_restart",
        label="Compose Restart",
        category=ActionCategory.COMPOSE,
        required_tags=["docker"],
        destructive=True,
        description="Restart compose services.",
    ),
    Action(
        name="compose_logs",
        label="Compose Logs (follow)",
        category=ActionCategory.COMPOSE,
        required_tags=["docker"],
        description="Tail all compose logs.",
    ),
    # --- Tag-specific actions ---
    Action(
        name="nginx_status",
        label="Nginx Status",
        category=ActionCategory.HEALTH,
        required_tags=["nginx"],
        description="Show nginx status and active connections.",
    ),
    Action(
        name="nginx_reload",
        label="Nginx Reload",
        category=ActionCategory.HEALTH,
        required_tags=["nginx"],
        destructive=True,
        description="Reload nginx configuration.",
    ),
    Action(
        name="postgres_status",
        label="PostgreSQL Status",
        category=ActionCategory.HEALTH,
        required_tags=["postgres"],
        description="Show PostgreSQL connections and DB sizes.",
    ),
    Action(
        name="redis_info",
        label="Redis Info",
        category=ActionCategory.HEALTH,
        required_tags=["redis"],
        description="Show Redis server info and memory usage.",
    ),
    Action(
        name="celery_inspect",
        label="Celery Inspect",
        category=ActionCategory.HEALTH,
        required_tags=["celery"],
        description="Show active Celery workers and queues.",
    ),
    Action(
        name="traefik_status",
        label="Traefik Status",
        category=ActionCategory.HEALTH,
        required_tags=["traefik"],
        description="Show Traefik routers and services.",
    ),
]


def get_actions_for_host(host: Host) -> list[Action]:
    """Return actions available for the given host based on its tags."""
    return [a for a in BUILTIN_ACTIONS if a.is_available_for(host)]


# ---------------------------------------------------------------------------
# Command builders for each action
# ---------------------------------------------------------------------------


def build_action_command(
    action: Action,
    host: Host,
    ssh_defaults: SSHDefaults,
    *,
    service: str | None = None,
    follow: bool = False,
    compose_path: str | None = None,
) -> list[str]:
    """Build the command list for the given action and host.

    Returns the full command to execute locally (typically an ssh invocation).
    """
    match action.name:
        case "ssh":
            return build_ssh_command(host, ssh_defaults)

        case "health":
            remote = (
                "echo '=== Uptime ===' && uptime && "
                "echo '\\n=== OS ===' && "
                "(cat /etc/os-release 2>/dev/null | head -2 "
                "|| sw_vers 2>/dev/null || uname -a) && "
                "echo '\\n=== Disk ===' && df -h / && "
                "echo '\\n=== Memory ===' && "
                "(free -h 2>/dev/null || vm_stat 2>/dev/null) && "
                "echo '\\n=== Load ===' && "
                "(cat /proc/loadavg 2>/dev/null "
                "|| sysctl -n vm.loadavg 2>/dev/null || uptime) && "
                "echo '\\n=== Docker ===' && "
                + _docker_command(
                    host,
                    'docker ps --format "table {{.Names}}\\t{{.Status}}" '
                    '2>/dev/null || echo "Docker not available"'
                )
            )
            return build_remote_command(host, ssh_defaults, remote)

        case "docker_ps":
            docker_ps_fmt = _docker_command(
                host,
                "docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'"
            )
            return build_remote_command(
                host, ssh_defaults, docker_ps_fmt,
            )

        case "docker_stats":
            docker_stats_fmt = _docker_command(
                host,
                "docker stats --no-stream --format 'table {{.Name}}\\t{{.CPUPerc}}\\t{{.MemUsage}}'"
            )
            return build_remote_command(
                host, ssh_defaults, docker_stats_fmt,
            )

        case "docker_logs":
            svc = service or ""
            docker_cmd = f"docker logs --tail 100 {'-f' if follow else ''} {svc}".strip()
            tail_cmd = _docker_command(host, docker_cmd)
            return build_remote_command(host, ssh_defaults, tail_cmd, allocate_tty=follow)

        case "compose_ps":
            cd_prefix = _compose_cd(compose_path)
            compose_cmd = f"{cd_prefix}docker compose ps"
            docker_cmd = _docker_command(host, compose_cmd)
            return build_remote_command(host, ssh_defaults, docker_cmd)

        case "compose_up":
            cd_prefix = _compose_cd(compose_path)
            compose_cmd = f"{cd_prefix}docker compose up -d"
            docker_cmd = _docker_command(host, compose_cmd)
            return build_remote_command(host, ssh_defaults, docker_cmd)

        case "compose_down":
            cd_prefix = _compose_cd(compose_path)
            compose_cmd = f"{cd_prefix}docker compose down"
            docker_cmd = _docker_command(host, compose_cmd)
            return build_remote_command(host, ssh_defaults, docker_cmd)

        case "compose_restart":
            cd_prefix = _compose_cd(compose_path)
            compose_cmd = f"{cd_prefix}docker compose restart"
            docker_cmd = _docker_command(host, compose_cmd)
            return build_remote_command(host, ssh_defaults, docker_cmd)

        case "compose_logs":
            cd_prefix = _compose_cd(compose_path)
            compose_cmd = f"{cd_prefix}docker compose logs --tail 100 -f"
            docker_cmd = _docker_command(host, compose_cmd)
            return build_remote_command(
                host, ssh_defaults, docker_cmd,
                allocate_tty=True,
            )

        # --- Tag-specific actions ---
        case "nginx_status":
            remote = (
                "echo '=== Nginx Status ===' && "
                "sudo nginx -t 2>&1 && "
                "echo '\\n=== Active Connections ===' && "
                "curl -s http://localhost/nginx_status 2>/dev/null "
                "|| echo 'stub_status not enabled'"
            )
            return build_remote_command(host, ssh_defaults, remote)

        case "nginx_reload":
            return build_remote_command(
                host, ssh_defaults, "sudo nginx -s reload",
            )

        case "postgres_status":
            remote = (
                "echo '=== PostgreSQL Connections ===' && "
                "sudo -u postgres psql -c "
                "\"SELECT state, count(*) FROM pg_stat_activity "
                "GROUP BY state;\" 2>/dev/null && "
                "echo '\\n=== Database Sizes ===' && "
                "sudo -u postgres psql -c "
                "\"SELECT datname, pg_size_pretty("
                "pg_database_size(datname)) FROM pg_database "
                "ORDER BY pg_database_size(datname) DESC;\" "
                "2>/dev/null"
            )
            return build_remote_command(host, ssh_defaults, remote)

        case "redis_info":
            remote = (
                "echo '=== Redis Info ===' && "
                "redis-cli info server 2>/dev/null | head -15 && "
                "echo '\\n=== Memory ===' && "
                "redis-cli info memory 2>/dev/null | head -10 && "
                "echo '\\n=== Clients ===' && "
                "redis-cli info clients 2>/dev/null | head -5"
            )
            return build_remote_command(host, ssh_defaults, remote)

        case "celery_inspect":
            cd_prefix = _compose_cd(compose_path)
            remote = (
                f"{cd_prefix}"
                "docker compose exec -T worker "
                "celery -A config inspect active 2>/dev/null "
                "|| echo 'Celery inspect not available'"
            )
            return build_remote_command(host, ssh_defaults, remote)

        case "traefik_status":
            remote = (
                "echo '=== Traefik Routers ===' && "
                "curl -s http://localhost:8080/api/http/routers "
                "2>/dev/null | python3 -m json.tool 2>/dev/null "
                "|| echo 'Traefik API not available'"
            )
            return build_remote_command(host, ssh_defaults, remote)

        case _:
            raise ValueError(f"Unknown action: {action.name}")


def _docker_command(host: Host, command: str) -> str:
    """Build a docker command, optionally with sudo -u docker_user."""
    if host.docker_user:
        return f"sudo -n -u {host.docker_user} {command}"
    return command


def _compose_cd(compose_path: str | None) -> str:
    """Build a cd prefix for compose commands if a path is specified."""
    if compose_path:
        return f"cd {compose_path} && "
    return ""


# ---------------------------------------------------------------------------
# Future extension stubs
# ---------------------------------------------------------------------------


def get_gcp_actions() -> list[Action]:
    """Placeholder for GCP actions.

    TODO: Implement gcloud subcommands:
      - ops gcp auth         — gcloud auth login
      - ops gcp set-project  — gcloud config set project <id>
      - ops gcp clusters     — gcloud container clusters list
    """
    return []


def get_terraform_actions() -> list[Action]:
    """Placeholder for Terraform actions.

    TODO: Implement terraform subcommands:
      - ops tf init   — terraform init
      - ops tf plan   — terraform plan
      - ops tf apply  — terraform apply (destructive, requires confirmation)
    """
    return []
