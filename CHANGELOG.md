# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] — 2025-02-09

### Added
- Initial release.
- Interactive TUI mode with Rich-based menus (client → host → action flow).
- Non-interactive CLI commands: `ops ls`, `ops ssh`, `ops health`.
- Docker commands: `ops docker ps`, `ops docker logs`, `ops docker stats`.
- Compose commands: `ops compose ps/up/down/restart/logs`.
- Config validation: `ops config`.
- YAML config format with clients, hosts, tags, SSH defaults.
- Host resolution by unique name or `client:name` qualified form.
- Fuzzy/substring search and type-ahead filtering in interactive menus.
- Destructive action confirmation prompts.
- Command preview before execution (dim style).
- SSH key/agent based auth (no passwords in config).
- Future extension stubs: `ops gcp`, `ops tf`.
- Install script for config directory setup.
- Unit tests for config parsing and host resolution.
