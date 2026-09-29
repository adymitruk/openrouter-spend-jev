#!/usr/bin/env python3
"""
Local OpenAI-compatible Jev Router Proxy for Hermes Agent.
Routes between GLM 5.3 Flash (cheap), DeepSeek V4 Flash (fast_mid),
and DeepSeek V4 Pro (smart_pro) using typesafe/jev-1.13 on OpenRouter.

Reference design merged with two hard-won fixes:
  1. reasoning_effort:"none" -> "low" for the cheap lane (glm-flash mandates
     reasoning and rejects "none" with a 400).
  2. tool-loop lane pinning (reuse a lane across assistant<->tool turns so the
     conversation context is never routed to a different model mid-turn).
NOTE: "typesafe/jev-latest" does NOT exist on OpenRouter — use typesafe/jev-1.13.
"""
import os
import json
import time
import hashlib
import logging
from typing import Dict, Any, Tuple
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [JEV-ROUTER] %(levelname)s: %(message)s")
log = logging.getLogger("jev-router")

OPENROUTER_BASE = "https://openrouter.ai/api"
DECISIONS_URL = f"{OPENROUTER_BASE}/alpha/decisions"
CHAT_URL = f"{OPENROUTER_BASE}/v1/chat/completions"

# The REAL OpenRouter key used for upstream calls. Sourced from env or
# ~/.hermes/.env. The incoming local Authorization is only an access gate
# (Hermes's alias sends a placeholder) and is never trusted upstream.
def _load_key() -> str:
    k = os.getenv("OPENROUTER_API_KEY", "").strip().strip('"').strip("'")
    if k:
        return k
    try:
        for line in open(os.path.expanduser("~/.hermes/.env")):
            if line.strip().startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'").strip()
    except Exception:
        pass
    return ""

OPENROUTER_KEY = _load_key()

# Real Jev model slug (validated on OpenRouter). Do NOT use typesafe/jev-latest.
JEV_MODEL = os.getenv("JEV_MODEL", "typesafe/jev-1.13")

# Customize your 3 model lanes here
LANES: Dict[str, Dict[str, str]] = {
    "cheap": {
        "model": os.getenv("JEV_LANE_CHEAP", "z-ai/glm-5.3-flash"),
        "provider_sort": "price",       # Minimize cost for routine/background turns
    },
    "fast_mid": {
        "model": os.getenv("JEV_LANE_MID", "deepseek/deepseek-v4-flash"),
        "provider_sort": "throughput",  # daily driver
    },
    "smart_pro": {
        "model": os.getenv("JEV_LANE_PRO", "deepseek/deepseek-v4-pro"),
        "provider_sort": "throughput",  # heavy reasoning & debugging
    },
}

CONFIDENCE_THRESHOLD = float(os.getenv("JEV_MIN_CONFIDENCE", "0.72"))
JEV_TIMEOUT_SEC = float(os.getenv("JEV_TIMEOUT_SEC", "1.2"))
PIN_TTL_SEC = 300.0  # how long to pin a lane during a tool loop

# Per-token pricing (USD) for cost tracking, keyed by OpenRouter model slug.
PRICES = {
    "z-ai/glm-5.3-flash": (0.040e-6, 0.500e-6),
    "deepseek/deepseek-v4-flash": (0.047e-6, 0.094e-6),
    "deepseek/deepseek-v4-pro": (0.348e-6, 0.696e-6),
}

_balance = [0.0]  # cumulative forwarded-token cost this process lifetime
_ntokens = [0, 0]  # [cumulative_prompt, cumulative_completion]
_nturns = [0]      # count of routed chat calls


def _cost(model: str, pin: int, pout: int) -> float:
    p_in, p_out = PRICES.get(model, (0.0, 0.0))
    return pin * p_in + pout * p_out

app = FastAPI(title="Hermes Jev Custom Router")
http_client: httpx.AsyncClient = None
_pinned: Dict[str, Tuple[str, float]] = {}   # conv_key -> (lane, expiry_ts)


def _clean_pinned(now: float) -> None:
    for k in [k for k, (_, exp) in _pinned.items() if exp < now]:
        _pinned.pop(k, None)


def _record(model, lane, conf, jev_ms, pin, pout):
    c = _cost(model, pin, pout)
    _ntokens[0] += pin; _ntokens[1] += pout
    _nturns[0] += 1
    _balance[0] += c
    log.info("COST [%s] %s in=%d out=%d $%.6f (run: $%.5f, tok %d/%d, turns %d)",
             lane, model, pin, pout, c, _balance[0], _ntokens[0], _ntokens[1], _nturns[0])


@app.on_event("startup")
async def startup_event():
    global http_client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=300.0, write=30.0, pool=10.0),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
    )


@app.on_event("shutdown")
async def shutdown_event():
    if http_client:
        await http_client.aclose()


def extract_compact_state(messages: list, has_tools: bool) -> str:
    """Only the latest user goal and turn context, so Jev evaluates <400 tokens."""
    last_user_text = ""
    latest_role = "unknown"
    latest_text = ""

    def content_to_str(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content or "")

    for msg in reversed(messages):
        role = msg.get("role", "")
        text = content_to_str(msg.get("content", "")).strip()
        if not latest_text and text:
            latest_role = role
            latest_text = text[:1200]
        if role == "user" and text:
            last_user_text = text[:1200]
            break

    return (
        f"Tools enabled: {has_tools}\n"
        f"Latest turn role: {latest_role}\n"
        f"User objective: {last_user_text}\n"
        f"Latest turn snippet: {latest_text}"
    )


async def classify_with_jev(state_text: str, api_key: str) -> Tuple[str, float, float]:
    """Calls /alpha/decisions; returns (selected_lane_key, confidence, latency_ms)."""
    t0 = time.perf_counter()
    payload = {
        "model": JEV_MODEL,
        "state": state_text,
        "questions": {
            "lane": {
                "type": "choice",
                "instructions": (
                    "Classify this agent turn into the most cost-effective model tier "
                    "capable of succeeding without errors."
                ),
                "criteria": {
                    "cheap": (
                        "Simple summarization, formatting, log extraction, status report, "
                        "trivial shell command, or wrapping up a completed tool output."
                    ),
                    "fast_mid": (
                        "Standard multi-step tool calling, bash/awk scripting, file edits, "
                        "data pipeline orchestration, or routine code changes."
                    ),
                    "smart_pro": (
                        "Complex algorithm design, C++/CUDA kernels, subtle bug/traceback "
                        "diagnosis, quantitative math, concurrency, or deep architecture."
                    ),
                },
            }
        },
    }
    try:
        bearer = api_key if api_key.startswith("Bearer ") else f"Bearer {api_key}"
        resp = await http_client.post(
            DECISIONS_URL,
            headers={"Authorization": bearer, "Content-Type": "application/json"},
            json=payload,
            timeout=JEV_TIMEOUT_SEC,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        resp.raise_for_status()
        data = resp.json()
        lane_ans = data.get("answers", {}).get("lane", {})
        choice = lane_ans.get("choice", "fast_mid")
        confidence = float(lane_ans.get("confidence", 0.0))

        # If Jev picks 'cheap' with low confidence, play it safe with 'fast_mid'
        if choice == "cheap" and confidence < CONFIDENCE_THRESHOLD:
            log.info(f"Low confidence ({confidence:.2f}) on 'cheap' -> bumping to 'fast_mid'")
            return "fast_mid", confidence, elapsed_ms
        if choice not in LANES:
            return "fast_mid", confidence, elapsed_ms
        return choice, confidence, elapsed_ms
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        log.warning(f"Jev decision fallback ({elapsed_ms:.0f}ms): {exc} -> 'fast_mid'")
        return "fast_mid", 0.0, elapsed_ms


def conv_key(messages: list) -> str:
    """Stable key for one turn: hash of the first user message."""
    for msg in messages:
        if msg.get("role") == "user":
            c = msg.get("content", "")
            if isinstance(c, list):
                c = " ".join(p.get("text", "") for p in c if isinstance(p, dict))
            return hashlib.sha256(str(c).encode()).hexdigest()[:16]
    return "nouser"


def is_tool_continuation(messages: list) -> bool:
    return bool(messages) and messages[-1].get("role") == "tool"


async def route_turn(messages: list, has_tools: bool, api_key: str) -> Tuple[str, str, float, float]:
    """Returns (lane_key, conv_key, confidence, latency_ms). Pins mid-loop."""
    key = conv_key(messages)
    now = time.time()
    _clean_pinned(now)
    if is_tool_continuation(messages):
        pinned = _pinned.get(key)
        if pinned and pinned[1] > now:
            return pinned[0], key, 1.0, 0.0   # reuse lane, no Jev call
    compact = extract_compact_state(messages, has_tools)
    lane, conf, ms = await classify_with_jev(compact, api_key)
    _pinned[key] = (lane, now + PIN_TTL_SEC)
    return lane, key, conf, ms


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def proxy_chat_completions(request: Request):
    auth_header = request.headers.get("Authorization")   # access gate only
    api_key = OPENROUTER_KEY or (auth_header or "").replace("Bearer ", "").strip()

    body = None
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": {
                "type": "invalid_request_error",
                "code": "invalid_json",
                "message": "Request body must be valid JSON.",
            }},
        )
    requested_model = body.get("model", "jev-custom")
    messages = body.get("messages", [])
    has_tools = bool(body.get("tools"))

    # Only run Jev classification if Hermes asks for the router model
    if requested_model in ("jev", "jev-custom", "auto", "typesafe/jev-router"):
        lane_key, _, conf, jev_ms = await route_turn(messages, has_tools, api_key)
        lane_cfg = LANES[lane_key]
        target_model = lane_cfg["model"]
        body["model"] = target_model

        # Merge OpenRouter provider sorting preference if not already set
        provider_cfg = body.get("provider", {})
        if "sort" not in provider_cfg:
            provider_cfg["sort"] = lane_cfg["provider_sort"]
        body["provider"] = provider_cfg

        log.info(f"Routed -> [{lane_key.upper()}] {target_model} (conf={conf:.2f}, jev={jev_ms:.0f}ms, sort={lane_cfg['provider_sort']})")

        # FIX #1: cheap lane (glm-flash) mandates reasoning. Hermes sends
        # reasoning_effort:"none" to disable it, which upstream rejects with 400.
        if lane_key == "cheap":
            if isinstance(body.get("reasoning"), dict) and body["reasoning"].get("enabled") is False:
                del body["reasoning"]
            reff = body.get("reasoning_effort")
            if isinstance(reff, str) and reff.lower() in ("none", "off", "false"):
                log.info("cheap lane: upscale reasoning_effort %r -> low", reff)
                body["reasoning_effort"] = "low"
    else:
        log.info(f"Direct pass-through -> {requested_model}")

    forward_headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": request.headers.get("HTTP-Referer", "https://hermes-agent.local"),
        "X-Title": request.headers.get("X-Title", "Hermes-Jev-Proxy"),
    }
    is_stream = body.get("stream", False)

    # Routing metadata for cost logging (always defined; pass-through keeps defaults)
    lane_key = lane_key if requested_model in ("jev", "jev-custom", "auto", "typesafe/jev-router") else "passthrough"
    conf = conf if requested_model in ("jev", "jev-custom", "auto", "typesafe/jev-router") else 0.0
    jev_ms = jev_ms if requested_model in ("jev", "jev-custom", "auto", "typesafe/jev-router") else 0.0
    target_model = target_model if requested_model in ("jev", "jev-custom", "auto", "typesafe/jev-router") else requested_model

    if is_stream:
        req = http_client.build_request("POST", CHAT_URL, headers=forward_headers, json=body)
        upstream_resp = await http_client.send(req, stream=True)

        async def stream_generator():
            usage = None
            try:
                async for rawb in upstream_resp.aiter_raw():
                    txt = rawb.decode("utf-8", "ignore")
                    if "usage" in txt:
                        for line in txt.splitlines():
                            if line.startswith("data:") and '"usage"' in line:
                                try:
                                    obj = json.loads(line[5:].strip())
                                    usage = obj.get("usage")
                                except Exception:
                                    pass
                    yield rawb
            finally:
                if usage:
                    pin = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
                    pout = usage.get("completion_tokens") or usage.get("output_tokens") or 0
                    _record(target_model, lane_key, conf, jev_ms, pin, pout)
                await upstream_resp.aclose()

        return StreamingResponse(
            stream_generator(),
            status_code=upstream_resp.status_code,
            media_type=upstream_resp.headers.get("content-type", "text/event-stream"),
        )
    else:
        upstream_resp = await http_client.post(CHAT_URL, headers=forward_headers, json=body)
        data = upstream_resp.json()
        if "usage" in data and data["usage"]:
            u = data["usage"]
            pin = u.get("prompt_tokens") or u.get("input_tokens") or 0
            pout = u.get("completion_tokens") or u.get("output_tokens") or 0
            _record(target_model, lane_key, conf, jev_ms, pin, pout)
        return JSONResponse(content=data, status_code=upstream_resp.status_code)


@app.get("/v1/models")
@app.get("/models")
async def list_models():
    """Satisfies Hermes model validation checks."""
    return {
        "object": "list",
        "data": [
            {"id": "jev-custom", "object": "model", "owned_by": "local-jev-router"},
            *[{"id": cfg["model"], "object": "model", "owned_by": "openrouter"} for cfg in LANES.values()],
        ],
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("JEV_PROXY_PORT", "4141"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")