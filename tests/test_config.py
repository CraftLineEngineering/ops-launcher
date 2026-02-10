"""Tests for ops_launcher.config — YAML loading, validation, host resolution."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from ops_launcher.config import (
    ConfigError,
    HostResolutionError,
    load_config,
    validate_config_file,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_YAML = textwrap.dedent("""\
    version: 1
    defaults:
      ssh_options:
        - "-o"
        - "ConnectTimeout=5"
    clients:
      acme:
        description: "Acme Corp"
        hosts:
          - name: "acme-prod"
            host: "prod.acme.io"
            user: "deploy"
            port: 22
            tags: ["prod", "docker", "django"]
          - name: "acme-stg"
            host: "stg.acme.io"
            user: "ubuntu"
            port: 2222
            tags: ["stg", "docker"]
      personal:
        description: "Personal"
        hosts:
          - name: "myserver"
            host: "my.server.dev"
            user: "user"
            tags: ["prod", "personal"]
            ssh_alias: "myalias"
""")

MINIMAL_YAML = textwrap.dedent("""\
    version: 1
    clients:
      test:
        hosts:
          - name: "t1"
            host: "t1.example.com"
""")

BAD_VERSION_YAML = textwrap.dedent("""\
    version: 99
    clients: {}
""")

MISSING_HOST_FIELD_YAML = textwrap.dedent("""\
    version: 1
    clients:
      broken:
        hosts:
          - name: "no-host-field"
""")

DUPLICATE_NAME_YAML = textwrap.dedent("""\
    version: 1
    clients:
      alpha:
        hosts:
          - name: "shared"
            host: "a.example.com"
      beta:
        hosts:
          - name: "shared"
            host: "b.example.com"
""")


@pytest.fixture()
def sample_config(tmp_path: Path) -> Path:
    p = tmp_path / "hosts.yaml"
    p.write_text(SAMPLE_YAML)
    return p


@pytest.fixture()
def minimal_config(tmp_path: Path) -> Path:
    p = tmp_path / "hosts.yaml"
    p.write_text(MINIMAL_YAML)
    return p


@pytest.fixture()
def bad_version_config(tmp_path: Path) -> Path:
    p = tmp_path / "hosts.yaml"
    p.write_text(BAD_VERSION_YAML)
    return p


@pytest.fixture()
def missing_field_config(tmp_path: Path) -> Path:
    p = tmp_path / "hosts.yaml"
    p.write_text(MISSING_HOST_FIELD_YAML)
    return p


@pytest.fixture()
def duplicate_config(tmp_path: Path) -> Path:
    p = tmp_path / "hosts.yaml"
    p.write_text(DUPLICATE_NAME_YAML)
    return p


# ---------------------------------------------------------------------------
# Tests — loading
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_load_sample(self, sample_config: Path):
        cfg = load_config(sample_config)
        assert cfg.version == 1
        assert len(cfg.clients) == 2
        assert len(cfg.all_hosts) == 3

    def test_ssh_defaults(self, sample_config: Path):
        cfg = load_config(sample_config)
        assert "-o" in cfg.ssh_defaults.options
        assert "ConnectTimeout=5" in cfg.ssh_defaults.options

    def test_host_fields(self, sample_config: Path):
        cfg = load_config(sample_config)
        host = cfg.resolve_host("acme-prod")
        assert host.host == "prod.acme.io"
        assert host.user == "deploy"
        assert host.port == 22
        assert "docker" in host.tags
        assert host.client == "acme"

    def test_ssh_alias(self, sample_config: Path):
        cfg = load_config(sample_config)
        host = cfg.resolve_host("myserver")
        assert host.ssh_alias == "myalias"
        assert host.ssh_target == "myalias"

    def test_ssh_target_without_alias(self, sample_config: Path):
        cfg = load_config(sample_config)
        host = cfg.resolve_host("acme-prod")
        assert host.ssh_target == "deploy@prod.acme.io"

    def test_minimal_config(self, minimal_config: Path):
        cfg = load_config(minimal_config)
        assert len(cfg.all_hosts) == 1
        host = cfg.all_hosts[0]
        assert host.user == "root"  # default
        assert host.port == 22  # default

    def test_missing_file(self, tmp_path: Path):
        with pytest.raises(ConfigError, match="Config file not found"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_bad_version(self, bad_version_config: Path):
        with pytest.raises(ConfigError, match="Unsupported config version"):
            load_config(bad_version_config)

    def test_missing_host_field(self, missing_field_config: Path):
        with pytest.raises(ConfigError, match="missing 'host' field"):
            load_config(missing_field_config)

    def test_invalid_yaml(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text(":\n  :\n    - [\n")
        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_config(p)

    def test_non_mapping_yaml(self, tmp_path: Path):
        p = tmp_path / "list.yaml"
        p.write_text("- item1\n- item2\n")
        with pytest.raises(ConfigError, match="must be a YAML mapping"):
            load_config(p)


# ---------------------------------------------------------------------------
# Tests — host resolution
# ---------------------------------------------------------------------------


class TestHostResolution:
    def test_resolve_unique_name(self, sample_config: Path):
        cfg = load_config(sample_config)
        host = cfg.resolve_host("acme-stg")
        assert host.name == "acme-stg"

    def test_resolve_qualified(self, sample_config: Path):
        cfg = load_config(sample_config)
        host = cfg.resolve_host("acme:acme-prod")
        assert host.name == "acme-prod"

    def test_resolve_unknown(self, sample_config: Path):
        cfg = load_config(sample_config)
        with pytest.raises(HostResolutionError, match="Unknown host"):
            cfg.resolve_host("nonexistent")

    def test_resolve_ambiguous(self, duplicate_config: Path):
        cfg = load_config(duplicate_config)
        with pytest.raises(HostResolutionError, match="Ambiguous"):
            cfg.resolve_host("shared")

    def test_resolve_ambiguous_with_qualifier(self, duplicate_config: Path):
        cfg = load_config(duplicate_config)
        host = cfg.resolve_host("alpha:shared")
        assert host.host == "a.example.com"

    def test_resolve_bad_qualifier(self, sample_config: Path):
        cfg = load_config(sample_config)
        with pytest.raises(HostResolutionError, match="not found under client"):
            cfg.resolve_host("nonexistent:acme-prod")


# ---------------------------------------------------------------------------
# Tests — search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_by_name(self, sample_config: Path):
        cfg = load_config(sample_config)
        results = cfg.search_hosts("acme")
        assert len(results) == 2

    def test_search_by_tag(self, sample_config: Path):
        cfg = load_config(sample_config)
        results = cfg.search_hosts("django")
        assert len(results) == 1
        assert results[0].name == "acme-prod"

    def test_search_by_host(self, sample_config: Path):
        cfg = load_config(sample_config)
        results = cfg.search_hosts("server.dev")
        assert len(results) == 1

    def test_search_no_match(self, sample_config: Path):
        cfg = load_config(sample_config)
        results = cfg.search_hosts("zzzznotfound")
        assert len(results) == 0


# ---------------------------------------------------------------------------
# Tests — validation helper
# ---------------------------------------------------------------------------


class TestValidation:
    def test_validate_ok(self, sample_config: Path):
        ok, msg = validate_config_file(sample_config)
        assert ok is True
        assert "2 client(s)" in msg
        assert "3 host(s)" in msg

    def test_validate_bad(self, tmp_path: Path):
        ok, msg = validate_config_file(tmp_path / "missing.yaml")
        assert ok is False
        assert "not found" in msg
