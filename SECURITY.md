# Security Policy

## Authentication

**ops-launcher never stores, transmits, or handles passwords.** All SSH authentication relies exclusively on:

- **SSH key pairs** (`~/.ssh/id_ed25519`, `~/.ssh/id_rsa`, etc.)
- **SSH agent** (`ssh-agent`, `gpg-agent`, or macOS Keychain)
- **SSH config aliases** (`~/.ssh/config`) for complex setups (jump hosts, custom keys, ProxyJump, etc.)

## Configuration

- The YAML config file (`~/.config/ops-launcher/hosts.yaml`) contains **only connection metadata**: hostnames, usernames, ports, and tags.
- **No secrets** should ever be placed in the config file.
- The config file should have restrictive permissions: `chmod 600 ~/.config/ops-launcher/hosts.yaml`.

## Destructive Actions

All destructive operations require **interactive confirmation** before execution:

- `docker compose down`
- `docker compose restart`
- `nginx reload`
- Future: `terraform apply`

Commands are always **previewed** in the terminal before execution so you can verify exactly what will run.

## SSH Best Practices

1. **Use Ed25519 keys** — `ssh-keygen -t ed25519`
2. **Use ssh-agent** — avoid typing passphrases repeatedly
3. **Use `~/.ssh/config`** for complex setups (jump hosts, per-host keys)
4. **Set `ConnectTimeout`** — ops-launcher defaults to 10 seconds to fail fast
5. **Disable password auth** on your servers — `PasswordAuthentication no` in `sshd_config`

## Reporting Vulnerabilities

If you discover a security issue, please open a private issue or contact the maintainers directly. Do not disclose vulnerabilities publicly until a fix is available.

## Scope

ops-launcher is a **local CLI tool** that executes SSH commands on your behalf. It does not:

- Run a web server or listen on any port
- Store credentials or tokens
- Make API calls (except future GCP/Terraform stubs, which will use your local `gcloud`/`terraform` auth)
- Transmit any data to third parties
