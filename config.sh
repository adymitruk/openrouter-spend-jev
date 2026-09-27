#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> OpenRouter Spend — placement in bar"
# The widget goes in the center section, after weather and before tray
SHELL_JSON="$HOME/.config/omarchy/shell.json"
if grep -q 'adam.openrouter-spend' "$SHELL_JSON" 2>/dev/null; then
  echo "    widget already in shell.json"
else
  # Insert before omarchy.tray (last center entry)
  python3 -c "
import json
with open('$SHELL_JSON') as f:
    d = json.load(f)
center = d['bar']['layout']['center']
# Check if already present
for entry in center:
    if entry.get('id') == 'adam.openrouter-spend':
        print('present')
        raise SystemExit(0)
# Add default config
center.insert(-1, {
    'id': 'adam.openrouter-spend',
    'config': {
        'refreshMinutes': 5,
        'popupWidth': 980,
        'popupHeight': 780,
        'marginX': 20,
        'marginY': 14,
        'sectionGap': 10,
        'heroHeight': 66,
        'heroGap': 14,
        'heroCaptionPad': 2,
        'chartHeaderPad': 20,
        'chartHeight': 150,
        'modelRowHeight': 34,
        'modelRowGap': 2,
        'dayRowHeight': 32,
        'dayRowGap': 0
    }
})
with open('$SHELL_JSON', 'w') as f:
    json.dump(d, f, indent=2)
    f.write('\n')
print('added')
" 2>/dev/null
  echo "    widget added to shell.json center section"
fi

echo ""
echo "==> jev-proxy — Hermes config alias"
HERMES_CONFIG="$HOME/.hermes/config.yaml"
if grep -q 'jev:' "$HERMES_CONFIG" 2>/dev/null; then
  echo "    jev alias already in hermes config"
else
  echo "" >> "$HERMES_CONFIG"
  echo "  # jev-proxy local router" >> "$HERMES_CONFIG"
  echo "  jev:" >> "$HERMES_CONFIG"
  echo "    model: jev" >> "$HERMES_CONFIG"
  echo "    provider: custom" >> "$HERMES_CONFIG"
  echo "    base_url: http://127.0.0.1:4141/v1" >> "$HERMES_CONFIG"
  echo "    api_key: local-noop" >> "$HERMES_CONFIG"
  echo "    jev alias added to hermes config"
fi

echo ""
echo "For the OpenRouter spend widget, paste your management key (sk-or-...)"
echo "in the plugin's settings panel (right-click widget -> Configure)."
echo ""
echo "Config done."