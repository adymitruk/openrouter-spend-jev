# jev-proxy

Local OpenAI-compatible Jev Router Proxy for Hermes Agent.
Routes between GLM 5.3 Flash (cheap), DeepSeek V4 Flash (fast_mid),
and DeepSeek V4 Pro (smart_pro) using typesafe/jev-1.13 on OpenRouter.

Tiers only step up for a Hermes conversation: cheap → fast_mid → smart_pro.
Jev still classifies each new turn, but the proxy keeps the highest tier that
conversation has already used, so a later turn never downgrades off a hot
prompt cache. Tool-result turns reuse the current lane instead of switching
models mid-loop. The conversation id is the Hermes session id when the jev
plugin sends it, otherwise a hash of the opening user message.

**Setup:**
```bash
./deploy.sh
./config.sh
```
