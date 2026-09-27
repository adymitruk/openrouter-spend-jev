## openrouter-spend-jev

Omarchy integration for OpenRouter spend tracking + Jev model router.

```
openrouter-spend-jev/
├── deploy.sh          # Copy files into place, enable services
├── config.sh          # Wire up bar placement and Hermes aliases
├── openrouter-spend/  # omarchy plugin (BarWidget, helper, manifest)
└── jev-proxy/         # Jev router service (proxy, systemd unit)
```

### Quick start

```bash
# 1. Deploy everything
./deploy.sh

# 2. Wire up shell.json + Hermes config
./config.sh

# 3. Set your management key
# Right-click the spend pill in the bar → Configure → paste sk-or-... key
```

### openrouter-spend

Bar widget that shows dollars spent this month on OpenRouter. Hover for a panel
with per-day and per-model breakdown, 30-day stacked chart, and last-hour bars.

### jev-proxy

Local OpenAI-compatible proxy that routes between model tiers using
Jev classification on OpenRouter. Runs as a user systemd service.