#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> OpenRouter Spend — omarchy plugin"
PLUGIN_DIR="$HOME/.config/omarchy/plugins/adam.openrouter-spend"
mkdir -p "$PLUGIN_DIR"
cp "$REPO_DIR"/openrouter-spend/* "$PLUGIN_DIR/"
echo "    files copied to $PLUGIN_DIR"

echo ""
echo "==> jev-proxy — user service"
mkdir -p "$HOME/.local/bin"
cp "$REPO_DIR"/jev-proxy/jev-proxy.service "$HOME/.config/systemd/user/"
cp "$REPO_DIR"/jev-proxy/jev-proxy.py "$HOME/.local/bin/"
echo "    service unit + script installed"

# Enable + start jev-proxy if not already running
if ! systemctl --user is-enabled jev-proxy &>/dev/null; then
  systemctl --user daemon-reload
  systemctl --user enable --now jev-proxy
  echo "    jev-proxy enabled and started"
else
  systemctl --user restart jev-proxy 2>/dev/null || true
  echo "    jev-proxy restarted"
fi

echo ""
echo "Done. The plugin hot-reloads; no shell restart needed."