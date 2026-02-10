#!/usr/bin/env bash
# ops-launcher install helper
# Creates config directory and copies sample config if missing.
set -euo pipefail

CONFIG_DIR="${HOME}/.config/ops-launcher"
CONFIG_FILE="${CONFIG_DIR}/hosts.yaml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLE_FILE="${SCRIPT_DIR}/../examples/hosts.yaml"

echo "⚡ ops-launcher — install helper"
echo "================================"
echo ""

# Create config directory
if [ ! -d "${CONFIG_DIR}" ]; then
    mkdir -p "${CONFIG_DIR}"
    echo "✓ Created ${CONFIG_DIR}"
else
    echo "· Config directory already exists: ${CONFIG_DIR}"
fi

# Copy sample config if missing
if [ ! -f "${CONFIG_FILE}" ]; then
    if [ -f "${EXAMPLE_FILE}" ]; then
        cp "${EXAMPLE_FILE}" "${CONFIG_FILE}"
        echo "✓ Copied sample config to ${CONFIG_FILE}"
    else
        echo "⚠ Example file not found at ${EXAMPLE_FILE}"
        echo "  You'll need to create ${CONFIG_FILE} manually."
    fi
else
    echo "· Config file already exists: ${CONFIG_FILE}"
    echo "  (Not overwriting. Delete it first if you want a fresh copy.)"
fi

echo ""
echo "Next steps:"
echo "  1. Edit your config:    \$EDITOR ${CONFIG_FILE}"
echo "  2. Install ops-launcher: pipx install -e .   (from the repo root)"
echo "     Or:                   uv tool install -e . (if using uv)"
echo "  3. Run:                  ops"
echo ""
echo "Done! 🚀"
