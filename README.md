# ⚡ Ops Launcher

A fast, interactive terminal tool for DevOps engineers who manage multiple clients, hosts, and infrastructure. Built with **Rich** for beautiful TUI and **Typer** for a professional CLI.

```
╭──────────────────── ⚡ Ops Launcher ────────────────────╮
│                                                        │
│  Config:   ~/.config/ops-launcher/hosts.yaml           │
│  Clients:  4                                           │
│  Hosts:    9                                           │
│                                                        │
│  Type a number to select, text to filter, q to quit.   │
│                                                        │
╰─────────────────────── v0.1.0 ─────────────────────────╯

──────────────── Select Client ─────────────────
    1  Acme Corp (production infrastructure) (4 hosts) — Corporate infrastructure
    2  TechCorp (systems administration) (2 hosts) — Systems administration
    3  Startup Inc (staging environments) (2 hosts) — Staging environments
    4  Personal server (myserver.dev) (1 hosts) — Personal server

  empty=back  q=exit  text=filter
  >
```

## Features

- **Interactive TUI** — guided flow: Client → Host → Action → Execute → Loop
- **Non-interactive CLI** — `ops ssh acme-prod`, `ops health techcorp-vps`, etc.
- **Searchable lists** — type-ahead fuzzy filtering in all menus
- **Docker & Compose** — `docker ps`, `logs`, `stats`, `compose up/down/restart`
- **Health checks** — uptime, disk, memory, load in one command
- **Safety first** — destructive actions require confirmation; commands previewed before execution
- **YAML config** — one file defines all clients, hosts, tags, SSH options
- **No secrets** — SSH key/agent auth only; no passwords in config
- **Portable** — install via `pipx` or `uv tool install` on any machine
- **Extensible** — stubs for GCP (`ops gcp`) and Terraform (`ops tf`) ready

## Install

### Prerequisites

- Python 3.11+
- SSH keys configured (agent or `~/.ssh/config`)

### Quick Install

```bash
# Clone the repo
git clone https://github.com/ops-launcher/ops-launcher.git
cd ops-launcher

# Set up config directory
bash scripts/install.sh

# Install with pipx (recommended)
pipx install -e .

# Or with uv
uv tool install -e .

# Or plain pip in a venv
pip install -e .
```

### Verify

```bash
ops --version
ops config
```

## Quickstart

```bash
# Interactive mode — opens the TUI
ops

# List all hosts
ops ls

# SSH into a host
ops ssh acme-prod

# Health check
ops health techcorp-vps

# Docker commands
ops docker ps acme-stg
ops docker logs acme-stg web --follow
ops docker stats acme-prod

# Compose commands
ops compose ps acme-stg
ops compose up acme-stg --project-dir /srv/app
ops compose down acme-stg        # requires confirmation
ops compose restart acme-stg     # requires confirmation
ops compose logs acme-stg

# Validate config
ops config
```

## Config

Config lives at `~/.config/ops-launcher/hosts.yaml` (override with `OPS_CONFIG` env var).

### Structure

```yaml
version: 1

defaults:
  ssh_options:
    - "-o"
    - "ConnectTimeout=10"
    - "-o"
    - "ServerAliveInterval=60"

clients:
  acme:
    description: "Acme Corp infrastructure"
    hosts:
      - name: "acme-prod"         # unique identifier
        host: "prod.acme.io"      # hostname or IP
        user: "ubuntu"            # SSH user (default: root)
        port: 22                  # SSH port (default: 22)
        tags: ["prod", "docker", "django", "postgres"]
        ssh_alias: null           # optional ~/.ssh/config alias
        docker_user: "appuser"    # Run docker commands as appuser via sudo -u

      - name: "acme-stg"
        host: "stg.acme.io"
        user: "ubuntu"
        port: 22
        tags: ["stg", "docker", "django"]
        ssh_alias: null

      - name: "acme-worker"
        host: "worker.acme.io"
        user: "ubuntu"
        port: 22
        tags: ["prod", "docker", "celery"]
        ssh_alias: null

      - name: "acme-db"
        host: "db.acme.io"
        user: "ubuntu"
        port: 22
        tags: ["prod", "postgres", "backups"]
        ssh_alias: null

  techcorp:
    description: "TechCorp — systems administration"
    hosts:
      - name: "techcorp-main"
        host: "main.techcorp.com"
        user: "root"
        port: 22
        tags: ["prod", "docker", "monitoring", "nginx"]
        ssh_alias: null

      - name: "techcorp-dev"
        host: "dev.techcorp.com"
        user: "deploy"
        port: 2222
        tags: ["stg", "docker", "django"]
        ssh_alias: null

  startup:
    description: "Startup Inc"
    hosts:
      - name: "startup-large"
        host: "large.startup.io"
        user: "ubuntu"
        port: 22
        tags: ["stg", "docker", "monitoring", "django"]
        ssh_alias: null

      - name: "startup-small"
        host: "small.startup.io"
        user: "ubuntu"
        port: 22
        tags: ["stg", "docker"]
        ssh_alias: null

  personal:
    description: "Personal server — myserver.dev"
    hosts:
      - name: "myserver"
        host: "myserver.dev"
        user: "user"
        port: 22
        tags: ["prod", "docker", "nginx", "personal"]
        ssh_alias: "myserver"     # uses SSH config alias instead
```

### Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `name` | ✅ | — | Unique host identifier |
| `host` | ✅ | — | Hostname, domain, or IP |
| `user` | ❌ | `root` | SSH username |
| `port` | ❌ | `22` | SSH port |
| `tags` | ❌ | `[]` | Tags for filtering and action availability |
| `ssh_alias` | ❌ | `null` | Use an SSH config alias instead of user@host |

### Tags

Tags control which actions are available for each host:

- **`docker`** — enables Docker and Compose actions
- **`prod`** / **`stg`** — informational, shown in listings
- Any custom tags for your own use

### Host Resolution

- If a host name is **globally unique**, use it directly: `ops ssh aire-stg-big`
- If **ambiguous** (same name in multiple clients), qualify it: `ops ssh aire:aire-stg-big`

## Adding Hosts

1. Edit `~/.config/ops-launcher/hosts.yaml`
2. Add a new entry under the appropriate client
3. Run `ops config` to validate
4. Run `ops ls` to verify

## Security Notes

- **No passwords** are stored in config or code — SSH key/agent auth only.
- Use `~/.ssh/config` for complex SSH setups (jump hosts, custom keys, ProxyJump) and reference them via `ssh_alias`.
- The `ssh_options` defaults include `ConnectTimeout=10` to fail fast on unreachable hosts.
- **Destructive actions** (`compose down`, `compose restart`, `nginx reload`, future `terraform apply`) always require interactive confirmation.
- Commands are **previewed** before execution so you can verify what will run.
- Config file should have restrictive permissions: `chmod 600 ~/.config/ops-launcher/hosts.yaml`.

See [SECURITY.md](SECURITY.md) for the full security policy.

## Project Structure

```
ops-launcher/
├── pyproject.toml          # PEP 621 packaging
├── README.md
├── LICENSE                 # MIT
├── SECURITY.md             # security policy
├── CHANGELOG.md
├── Makefile                # dev tasks: test, lint, format
├── ops_launcher/
│   ├── __init__.py         # version
│   ├── cli.py              # Typer app, all commands
│   ├── tui.py              # Rich interactive menus
│   ├── config.py           # YAML loader, validation, host resolution
│   ├── actions.py          # action registry & command builders
│   ├── executor.py         # subprocess runner, streaming output
│   ├── ssh.py              # SSH command building
│   ├── history.py          # recent host usage tracking
│   └── utils.py            # prompts, fuzzy match, formatting
├── examples/
│   └── hosts.yaml          # sample config
├── scripts/
│   └── install.sh          # config directory setup
└── tests/
    └── test_config.py      # config parsing & resolution tests
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
make test

# Lint
make lint

# Format
make format

# All checks
make check
```

## Future Roadmap

- **`ops gcp`** — gcloud auth, set-project, list-clusters
- **`ops tf`** — terraform init/plan/apply with confirmation
- Custom actions in YAML config
- SSH multiplexing / connection reuse
- Host status dashboard (parallel health checks)

## License

MIT — see [LICENSE](LICENSE).
