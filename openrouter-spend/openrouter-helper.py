#!/usr/bin/env python3
"""OpenRouter spend fetcher for the omarchy bar widget.

Owns the only untrusted boundary (the OpenRouter HTTPS API) and the only disk
state (the aggregated spend JSON). The bar widget is pure display: it asks this
helper to `read` the aggregate it already wrote.

State and the management key live in the private omarchy settings dir
(~/.local/state/omarchy/settings/, mode 0700). The key is never echoed, never
put on a command line, and never written by the widget.

Commands:
  fetch     Poll OpenRouter /generations for the current calendar month and
            write openrouter-spend.json (month total, spend per day, spend per
            model, most expensive first).
  read <n>  Print a validated state file (openrouter-spend.json).
"""

import datetime
import json
import os
import re
import secrets
import subprocess
import sys

MAX_RESPONSE = 256 * 1024
MAX_STATE = 128 * 1024
STATE_NAMES = {"openrouter-spend.json"}
KEY_NAMES = {"openrouter-key"}


# ---- Secure state-directory access (same hardened pattern as the weather
#      widget's helper: walk HOME descriptor-first, never follow user-mutable
#      symlinks, keep the leaf private). -------------------------------------

def _is_dir(mode):
    return (mode & 0o170000) == 0o040000


def _stat_safe_open(parent_fd, name, label, create, private=False, owner=True):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        if not create:
            raise
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        fd = os.open(name, flags, dir_fd=parent_fd)
    info = os.fstat(fd)
    if not _is_dir(info.st_mode):
        os.close(fd)
        raise OSError("unsafe " + label)
    if owner and info.st_uid != os.getuid():
        os.close(fd)
        raise OSError("unsafe " + label)
    if info.st_mode & 0o022:
        os.close(fd)
        raise OSError("unsafe " + label)
    if private:
        os.fchmod(fd, 0o700)
    return fd


def settings_fd():
    root = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    current = root
    try:
        home = os.environ.get("HOME", "")
        if not home.startswith("/") or "." in home.split("/"):
            raise OSError("unsafe HOME")
        parts = [p for p in home.split("/") if p]
        for i, part in enumerate(parts):
            nxt = _stat_safe_open(current, part, "home", False, owner=(i == len(parts) - 1))
            os.close(current)
            current = nxt
        for part in (".local", "state", "omarchy", "settings"):
            nxt = _stat_safe_open(current, part, "state dir", True, private=(part == "settings"))
            os.close(current)
            current = nxt
        return current
    except BaseException:
        os.close(root)
        raise


def read_key():
    fd = settings_fd()
    try:
        try:
            kh = os.open("openrouter-key", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        except FileNotFoundError:
            return ""
        try:
            raw = os.read(kh, 512)
        finally:
            os.close(kh)
    finally:
        os.close(fd)
    key = raw.decode("utf-8", "replace").strip()
    if not key.startswith("sk-or-"):
        return ""
    return key


def write_key(name, value):
    """Write a named key file in the settings dir (e.g. openrouter-key)."""
    if name not in KEY_NAMES:
        return
    fd = settings_fd()
    f = -1
    tmp = None
    try:
        for _ in range(100):
            tmp = "." + name + "." + secrets.token_hex(16)
            try:
                f = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                            | os.O_CLOEXEC, 0o600, dir_fd=fd)
                break
            except FileExistsError:
                tmp = None
        else:
            raise OSError("no temp slot")
        data = (value or "").encode("utf-8")
        off = 0
        while off < len(data):
            off += os.write(f, data[off:])
        os.fsync(f)
        os.replace(tmp, name, src_dir_fd=fd, dst_dir_fd=fd)
        tmp = None
        os.close(f)
        f = -1
        os.fsync(fd)
    finally:
        if f != -1:
            os.close(f)
        if tmp:
            try:
                os.unlink(tmp, dir_fd=fd)
            except OSError:
                pass
        os.close(fd)


def read_state(name):
    if name not in STATE_NAMES:
        raise ValueError("invalid state name")
    fd = settings_fd()
    try:
        try:
            h = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        except FileNotFoundError:
            return
        try:
            info = os.fstat(h)
            if info.st_mode & 0o170000 != 0o100000 or info.st_uid != os.getuid():
                raise OSError("unsafe state file")
            if info.st_size > MAX_STATE:
                raise OSError("state too large")
            data = os.read(h, MAX_STATE + 1)
        finally:
            os.close(h)
    finally:
        os.close(fd)
    if len(data) > MAX_STATE:
        raise OSError("state too large")
    sys.stdout.buffer.write(data)


def write_state(name, data):
    if name not in STATE_NAMES:
        raise ValueError("invalid state name")
    if len(data) > MAX_STATE:
        raise OSError("state too large")
    fd = settings_fd()
    f = -1
    tmp = None
    try:
        try:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if info.st_mode & 0o170000 != 0o100000 or info.st_uid != os.getuid():
                raise OSError("unsafe target")
        except FileNotFoundError:
            pass
        for _ in range(100):
            tmp = "." + name + "." + secrets.token_hex(16)
            try:
                f = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                            | os.O_CLOEXEC, 0o600, dir_fd=fd)
                break
            except FileExistsError:
                tmp = None
        else:
            raise OSError("no temp slot")
        os.fchmod(f, 0o600)
        off = 0
        while off < len(data):
            off += os.write(f, data[off:])
        os.fsync(f)
        os.replace(tmp, name, src_dir_fd=fd, dst_dir_fd=fd)
        tmp = None
        os.close(f)
        f = -1
        os.fsync(fd)
    finally:
        if f != -1:
            os.close(f)
        if tmp:
            try:
                os.unlink(tmp, dir_fd=fd)
            except OSError:
                pass
        os.close(fd)


def _post(url, payload):
    """POST JSON with the key; return (status, data) or (None, None) on failure."""
    key = read_key()
    if not key:
        return None, None
    p = subprocess.Popen(
        ["curl", "-sS", "--max-time", "25", "-X", "POST", url,
         "-H", "Authorization: Bearer " + key,
         "-H", "Content-Type: application/json",
         "--data", json.dumps(payload)],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    body = p.stdout.read(MAX_RESPONSE + 1)
    p.wait()
    if p.returncode != 0 or len(body) > MAX_RESPONSE:
        return None, None
    return p.returncode, body


def _analytics(payload):
    """Run one analytics query against the management key; return its rows."""
    status, body = _post("https://openrouter.ai/api/v1/analytics/query", payload)
    if not body:
        return None
    try:
        wrapped = json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return None
    if isinstance(wrapped, dict) and wrapped.get("error"):
        return None
    data = wrapped.get("data") or {}
    if not isinstance(data, dict):
        return None
    rows = data.get("data")
    return rows if isinstance(rows, list) else None


def _row_value(row, keys):
    """First present value among candidate keys in a row."""
    if not row or not isinstance(row, dict):
        return None
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]
    return None


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _canonical_model(slug):
    """Collapse release-date variants into one canonical name.
    'deepseek/deepseek-v4-flash-20260731' -> 'deepseek/deepseek-v4-flash'
    """
    parts = str(slug or "").rsplit("/", 1)
    if len(parts) == 2:
        name = re.sub(r"-\d{8}$", "", parts[1])
        return parts[0] + "/" + name
    return re.sub(r"-\d{8}$", "", str(slug or ""))


def _merge_hour_models(minutes):
    """Merge per-minute model segments into 5-minute aggregates."""
    merged = {}
    for m in minutes:
        for seg in m.get("models", []):
            model = seg["model"]
            merged[model] = merged.get(model, 0.0) + seg["total"]
    segs = [{"model": m, "total": round(v, 6)} for m, v in merged.items() if v > 0]
    segs.sort(key=lambda x: x["total"], reverse=True)
    return segs


def fetch():
    """Aggregate this calendar month's spend from the OpenRouter analytics API."""
    now = datetime.datetime.now().astimezone()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_start = (month_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    time_range = {
        "start": month_start.strftime("%Y-%m-%dT00:00:00Z"),
        "end": next_start.strftime("%Y-%m-%dT00:00:00Z"),
    }

    # --- Spend per day (total across all models).
    days = []
    daily_rows = _analytics({
        "metrics": ["total_usage"],
        "granularity": "day",
        "time_range": time_range,
        "limit": 1000,
    })
    if daily_rows is not None:
        for row in daily_rows:
            date_val = _row_value(row, ["date__day", "created_at__day", "created_at"])
            if not date_val:
                continue
            days.append({
                "date": str(date_val)[:10],
                "total": round(_as_float(_row_value(row, ["total_usage"])), 6),
            })
        days.sort(key=lambda x: x["date"], reverse=True)
        month_total = round(sum(d["total"] for d in days), 6)
    else:
        month_total = 0.0

    # --- Spend per model for the month, most expensive first.
    # Merge release-date variants (e.g. deepseek-v4-flash-20260731 and
    # deepseek-v4-flash-20260423) by canonical name.
    model_totals = {}
    model_rows = _analytics({
        "metrics": ["total_usage"],
        "dimensions": ["model"],
        "order_by": {"field": "total_usage", "direction": "desc"},
        "time_range": time_range,
        "limit": 1000,
    })
    if model_rows is not None:
        for row in model_rows:
            raw_model = _row_value(row, ["model", "model_name"])
            if not raw_model:
                continue
            model_totals[_canonical_model(raw_model)] = (
                model_totals.get(_canonical_model(raw_model), 0.0)
                + _as_float(_row_value(row, ["total_usage"]))
            )
    models = [{"model": m, "total": round(v, 6)} for m, v in model_totals.items() if v > 0]
    models.sort(key=lambda x: x["total"], reverse=True)

    if not days and not models:
        month_total = 0.0

    # --- Last 30 days, stacked by model, for the popup chart. Days are UTC
    #      calendar days to match the day buckets the API returns.
    series = []
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    today_utc = now_utc.date()
    start30 = today_utc - datetime.timedelta(days=29)
    series_rows = _analytics({
        "metrics": ["total_usage"],
        "dimensions": ["model"],
        "granularity": "day",
        "time_range": {
            "start": start30.strftime("%Y-%m-%dT00:00:00Z"),
            "end": (today_utc + datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z"),
        },
        "limit": 1000,
    })
    bydate = {}
    if series_rows is not None:
        for row in series_rows:
            date_val = _row_value(row, ["date__day", "created_at__day", "created_at"])
            raw_model = _row_value(row, ["model", "model_name"])
            if not date_val or not raw_model:
                continue
            d = str(date_val)[:10]
            can = _canonical_model(raw_model)
            rec = bydate.setdefault(d, {})
            rec[can] = rec.get(can, 0.0) + _as_float(_row_value(row, ["total_usage"]))
    for i in range(30):
        d = start30 + datetime.timedelta(days=i)
        ds = d.strftime("%Y-%m-%d")
        day_models = bydate.get(ds, {})
        segs = [{"model": m, "total": round(v, 6)} for m, v in day_models.items() if v > 0]
        segs.sort(key=lambda x: x["total"], reverse=True)
        series.append({
            "date": ds,
            "total": round(sum(v for v in day_models.values()), 6),
            "models": segs,
        })

    # --- Spend in the last 24 hours: sum the hourly buckets.
    last24 = 0.0
    hour_rows = _analytics({
        "metrics": ["total_usage"],
        "granularity": "hour",
        "time_range": {
            "start": (now_utc - datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "limit": 1000,
    })
    if hour_rows is not None:
        for row in hour_rows:
            last24 += _as_float(_row_value(row, ["total_usage"]))

    # --- Spend last hour as 5-minute bars for the "LAST HOUR" chart. Fetch
    #      minute buckets with per-model breakdown, then group every 5
    #      consecutive minutes into one bar with stacked model segments.
    by_min_model = {}
    min_rows = _analytics({
        "metrics": ["total_usage"],
        "dimensions": ["model"],
        "granularity": "minute",
        "time_range": {
            "start": (now_utc - datetime.timedelta(minutes=60)).strftime("%Y-%m-%dT%H:%M:00Z"),
            "end": now_utc.strftime("%Y-%m-%dT%H:%M:00Z"),
        },
        "limit": 2000,
    })
    if min_rows is not None:
        for row in min_rows:
            key = _row_value(row, ["date__minute", "created_at__minute"])
            raw_model = _row_value(row, ["model", "model_name"])
            if key and raw_model:
                hm = str(key)[11:16]  # "HH:MM" from "YYYY-MM-DD HH:MM:00"
                can = _canonical_model(raw_model)
                bucket = by_min_model.setdefault(hm, {})
                bucket[can] = bucket.get(can, 0.0) + _as_float(_row_value(row, ["total_usage"]))
    minutes_60 = []
    for i in range(60):
        t = now_utc - datetime.timedelta(minutes=59 - i)  # oldest first
        hm = t.strftime("%H:%M")
        models_map = by_min_model.get(hm, {})
        total = round(sum(models_map.values()), 6)
        segs = [{"model": m, "total": round(v, 6)} for m, v in models_map.items() if v > 0]
        segs.sort(key=lambda x: x["total"], reverse=True)
        minutes_60.append({"t": hm, "total": total, "models": segs})
    last_hour = [
        {
            "t": minutes_60[b * 5]["t"],
            "total": round(sum(x["total"] for x in minutes_60[b * 5:(b + 1) * 5]), 6),
            "models": _merge_hour_models(minutes_60[b * 5:(b + 1) * 5]),
        }
        for b in range(12)
    ]

    out = {
        "month": month_start.strftime("%Y-%m"),
        "month_total": month_total,
        "last24h": round(last24, 6),
        "generated_at": int(now.timestamp()),
        "days": days,
        "models": models,
        "series": series,
        "lastHour": last_hour,
    }
    write_state("openrouter-spend.json", json.dumps(out).encode("utf-8"))
    return 0


def main():
    try:
        if len(sys.argv) >= 2 and sys.argv[1] == "fetch":
            return fetch()
        if len(sys.argv) == 3 and sys.argv[1] == "read":
            read_state(sys.argv[2])
            return 0
        if len(sys.argv) == 4 and sys.argv[1] == "write-key":
            write_key(sys.argv[2], sys.argv[3])
            return 0
    except (OSError, ValueError):
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
