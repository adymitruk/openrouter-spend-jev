#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

# ----------------------------------------------------------------- omarchy bar
# Only meaningful where there is an Omarchy shell to place the widget in.
if [ -d "$HOME/.config/omarchy" ]; then
  echo "==> OpenRouter Spend — placement in bar"
  SHELL_JSON="$HOME/.config/omarchy/shell.json"
  if grep -q 'adam.openrouter-spend' "$SHELL_JSON" 2>/dev/null; then
    echo "    widget already in shell.json"
  else
    python3 - "$SHELL_JSON" <<'PY'
import json, sys
path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
center = d["bar"]["layout"]["center"]
for entry in center:
    if entry.get("id") == "adam.openrouter-spend":
        print("    widget already present")
        raise SystemExit(0)
# Insert before omarchy.tray (last center entry)
center.insert(-1, {
    "id": "adam.openrouter-spend",
    "config": {
        "refreshMinutes": 5,
        "popupWidth": 980,
        "popupHeight": 780,
        "marginX": 20,
        "marginY": 14,
        "sectionGap": 10,
        "heroHeight": 66,
        "heroGap": 14,
        "heroCaptionPad": 2,
        "chartHeaderPad": 20,
        "chartHeight": 150,
        "modelRowHeight": 34,
        "modelRowGap": 2,
        "dayRowHeight": 32,
        "dayRowGap": 0,
    },
})
with open(path, "w") as f:
    json.dump(d, f, indent=2)
    f.write("\n")
print("    widget added to shell.json center section")
PY
  fi
else
  echo "==> OpenRouter Spend — bar placement: SKIPPED (no Omarchy shell here)"
fi

echo ""
echo "==> Hermes — jev router alias"

# The alias MUST go under `model_aliases:` — Hermes reads that mapping
# (hermes_cli/config.py, hermes_cli/oneshot.py). An earlier version of this
# script appended a top-level `jev:` block, which the agent silently ignores.
#
# Never hand-edit config.yaml: `hermes config set` writes the YAML safely and a
# stray indent in that file can break the running gateway.
if command -v hermes >/dev/null 2>&1; then
  # Hermes prints a "not a recognized config key" notice for model_aliases.*
  # That is its nested-key validator being unaware of mapping sub-keys, not a
  # bad key: this build reads `model_aliases` (hermes_cli/config.py). The
  # suggested `model_overrides` is unrelated session state.
  echo "    (hermes will print a nested-key notice for model_aliases.* — safe to ignore)"
  hermes config set model_aliases.jev.model   jev-custom
  hermes config set model_aliases.jev.provider custom
  hermes config set model_aliases.jev.base_url http://127.0.0.1:4141/v1
  hermes config set model_aliases.jev.api_key  local-noop
  echo "    alias 'jev' written — switch with /model jev"
  echo "    to make it the default instead:"
  echo "      hermes config set model.default jev-custom"
  echo "      hermes config set model.provider custom"
  echo "      hermes config set model.base_url http://127.0.0.1:4141/v1"
else
  echo "    hermes CLI not found. Add this to ~/.hermes/config.yaml by hand:"
  cat <<'YAML'

model_aliases:
  jev:
    model: jev-custom
    provider: custom
    base_url: http://127.0.0.1:4141/v1
    api_key: local-noop
YAML
fi

echo ""
echo "For the OpenRouter spend widget, paste your management key (sk-or-...)"
echo "in the plugin's settings panel (right-click widget -> Configure)."
echo ""
echo "Config done."
