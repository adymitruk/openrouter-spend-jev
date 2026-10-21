#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

# ----------------------------------------------------------------- omarchy bar
# This half is the Omarchy/Quickshell bar widget. Installed unconditionally it
# creates ~/.config/omarchy on machines that have no Omarchy shell (e.g. a KDE
# box) and drops files nothing will ever read. Only do it where Omarchy lives.
if [ -d "$HOME/.config/omarchy" ] || command -v omarchy >/dev/null 2>&1; then
  echo "==> OpenRouter Spend — omarchy plugin"
  PLUGIN_DIR="$HOME/.config/omarchy/plugins/adam.openrouter-spend"
  mkdir -p "$PLUGIN_DIR"
  cp "$REPO_DIR"/openrouter-spend/* "$PLUGIN_DIR/"
  echo "    files copied to $PLUGIN_DIR"
else
  echo "==> OpenRouter Spend — omarchy plugin: SKIPPED (no Omarchy shell here)"
  echo "    for KDE Plasma use cachyos-kde-widget/ instead (see its readme)"
fi

echo ""
echo "==> jev-proxy — user service"
mkdir -p "$HOME/.local/bin" "$HOME/.config/systemd/user"
cp "$REPO_DIR"/jev-proxy/jev-proxy.service "$HOME/.config/systemd/user/"
cp "$REPO_DIR"/jev-proxy/jev-proxy.py "$HOME/.local/bin/"
echo "    service unit + script installed"

# The unit ships ExecStart=/usr/bin/python3. Prove that interpreter can import
# the dependencies before wiring anything up: on PEP 668 distros (Ubuntu 24.04
# and friends) /usr/bin/python3 is externally managed and has none of them, and
# a dependency that imports in the *current* shell proves nothing — that is
# usually a project or tool venv, not the interpreter the unit will use.
VENV="$HOME/.local/share/jev-proxy/venv"
UNIT_PYTHON="/usr/bin/python3"

if "$UNIT_PYTHON" -c 'import fastapi, uvicorn, httpx' >/dev/null 2>&1; then
  echo "    $UNIT_PYTHON already provides fastapi/uvicorn/httpx — no venv needed"
else
  echo "    $UNIT_PYTHON cannot import fastapi/uvicorn/httpx — building a venv"
  "$UNIT_PYTHON" -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet -r "$REPO_DIR"/jev-proxy/requirements.txt
  "$VENV/bin/python" -c 'import fastapi, uvicorn, httpx'
  echo "    venv ready: $VENV"

  # Retarget ExecStart with a drop-in so the shipped unit stays byte-identical
  # to the repo (a later `git pull` still applies cleanly). The bare
  # `ExecStart=` line must come first to clear the inherited value.
  OVERRIDE_DIR="$HOME/.config/systemd/user/jev-proxy.service.d"
  mkdir -p "$OVERRIDE_DIR"
  cat > "$OVERRIDE_DIR/override.conf" <<'EOF'
[Service]
ExecStart=
ExecStart=%h/.local/share/jev-proxy/venv/bin/python %h/.local/bin/jev-proxy.py
EOF
  echo "    drop-in written: $OVERRIDE_DIR/override.conf"
fi

systemctl --user daemon-reload
if ! systemctl --user is-enabled jev-proxy &>/dev/null; then
  systemctl --user enable --now jev-proxy
  echo "    jev-proxy enabled and started"
else
  systemctl --user restart jev-proxy
  echo "    jev-proxy restarted"
fi

# A just-restarted uvicorn is not instantly listening — poll before reporting.
for _ in $(seq 1 20); do
  ss -ltn 2>/dev/null | grep -q ':4141' && break
  sleep 0.5
done
if ss -ltnp 2>/dev/null | grep -q ':4141'; then
  echo "    now listening:"
  ss -ltnp 2>/dev/null | grep -E ':4141' | sed 's/^/      /'
else
  echo "    WARNING: port 4141 is not bound — check: journalctl --user -u jev-proxy -n 30"
fi

echo ""
echo "Done. The plugin hot-reloads; no shell restart needed."
echo "Proxy log: journalctl --user -u jev-proxy -f"
