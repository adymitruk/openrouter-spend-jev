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


def _parse_utc_dt(s):
    """Parse a UTC ISO timestamp string into an aware datetime.

    OpenRouter's minute-granularity endpoint returns timestamps like
    '2026-09-27 18:20:00' (space separator, no tz marker). Hour and day
    granularity returns ISO format with T and possibly Z.
    Both are UTC — always force +00:00 when no tzinfo is present.
    """
    s = str(s).strip().replace("T", " ").replace("Z", "")
    # fromisoformat accepts the space-separated UTC form — add +00:00 if naive
    dt = datetime.datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def fetch():
    """Aggregate spend bucketed into local-timezone 5-minute windows."""
    now_aware = datetime.datetime.now().astimezone()
    local_tz = now_aware.tzinfo
    now_local = now_aware
    today_local = now_local.date()
    month_start_local = today_local.replace(day=1)
    next_month_local = (month_start_local.replace(day=28)
                        + datetime.timedelta(days=4)).replace(day=1)

    def local_midnight_utc(d):
        naive = datetime.datetime.combine(d, datetime.time.min)
        return naive.replace(tzinfo=local_tz).astimezone(datetime.timezone.utc)

    month_start_utc = local_midnight_utc(month_start_local)
    next_month_utc = local_midnight_utc(next_month_local)
    time_range = {
        "start": month_start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": next_month_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # --- Days: hourly buckets from the API, grouped into local calendar days
    #      by converting each UTC hour to local time.
    days_by_date = {}
    hour_rows = _analytics({
        "metrics": ["total_usage"],
        "granularity": "hour",
        "time_range": time_range,
        "limit": 1000,
    })
    if hour_rows is not None:
        for row in hour_rows:
            ts = _row_value(row, ["date__hour", "created_at__hour", "created_at"])
            if not ts:
                continue
            local_dt = _parse_utc_dt(ts).astimezone(local_tz)
            local_date_str = local_dt.strftime("%Y-%m-%d")
            days_by_date[local_date_str] = (
                days_by_date.get(local_date_str, 0.0)
                + _as_float(_row_value(row, ["total_usage"]))
            )
    days = [{"date": d, "total": round(t, 6)}
            for d, t in sorted(days_by_date.items(), reverse=True)]
    month_total = round(sum(d["total"] for d in days), 6) if days else 0.0

    # --- Spend per model for the month, most expensive first.
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
    models = [{"model": m, "total": round(v, 6)}
              for m, v in model_totals.items() if v > 0]
    models.sort(key=lambda x: x["total"], reverse=True)

    # --- 30-day series: per-model, per-local-day, from hourly API data.
    start30_local = today_local - datetime.timedelta(days=29)
    start30_utc = local_midnight_utc(start30_local)
    end_utc = local_midnight_utc(today_local + datetime.timedelta(days=1))

    series_rows = _analytics({
        "metrics": ["total_usage"],
        "dimensions": ["model"],
        "granularity": "hour",
        "time_range": {
            "start": start30_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "limit": 10000,
    })
    bydate = {}
    if series_rows is not None:
        for row in series_rows:
            ts = _row_value(row, ["date__hour", "created_at__hour", "created_at"])
            raw_model = _row_value(row, ["model", "model_name"])
            if not ts or not raw_model:
                continue
            local_date = _parse_utc_dt(ts).astimezone(local_tz).strftime("%Y-%m-%d")
            can = _canonical_model(raw_model)
            rec = bydate.setdefault(local_date, {})
            rec[can] = rec.get(can, 0.0) + _as_float(_row_value(row, ["total_usage"]))
    series = []
    for i in range(30):
        d = start30_local + datetime.timedelta(days=i)
        ds = d.isoformat()
        day_models = bydate.get(ds, {})
        segs = [{"model": m, "total": round(v, 6)}
                for m, v in day_models.items() if v > 0]
        segs.sort(key=lambda x: x["total"], reverse=True)
        series.append({
            "date": ds,
            "total": round(sum(day_models.values()), 6),
            "models": segs,
        })

    # --- Sliding last 24h: sum of UTC hours (no timezone needed — rolling
    #      window, not a calendar boundary).
    last24 = 0.0
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    hour24_rows = _analytics({
        "metrics": ["total_usage"],
        "granularity": "hour",
        "time_range": {
            "start": (now_utc - datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "limit": 1000,
    })
    if hour24_rows is not None:
        for row in hour24_rows:
            last24 += _as_float(_row_value(row, ["total_usage"]))

    # --- Last hour as 5-minute bars (local timezone).
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
                local_dt = _parse_utc_dt(key).astimezone(local_tz)
                slot_m = (local_dt.minute // 5) * 5
                slot_key = local_dt.strftime("%H") + f":{slot_m:02d}"
                can = _canonical_model(raw_model)
                bucket = by_min_model.setdefault(slot_key, {})
                bucket[can] = bucket.get(can, 0.0) + _as_float(_row_value(row, ["total_usage"]))

    # Back-fill all 60 minutes so no gaps in the bar array.
    last_hour_start = now_local - datetime.timedelta(minutes=60)
    minutes_60_local = []
    for i in range(60):
        t = last_hour_start + datetime.timedelta(minutes=i)
        slot_m = (t.minute // 5) * 5
        slot_key = t.strftime("%H") + f":{slot_m:02d}"
        models_map = by_min_model.get(slot_key, {})
        segs = [{"model": m, "total": round(v, 6)}
                for m, v in models_map.items() if v > 0]
        segs.sort(key=lambda x: x["total"], reverse=True)
        minutes_60_local.append({
            "t": t.strftime("%H:%M"),
            "total": round(sum(models_map.values()), 6),
            "models": segs,
        })
    last_hour = [
        {
            "t": minutes_60_local[b * 5]["t"],
            "total": round(sum(x["total"]
                         for x in minutes_60_local[b * 5:(b + 1) * 5]), 6),
            "models": _merge_hour_models(minutes_60_local[b * 5:(b + 1) * 5]),
        }
        for b in range(12)
    ]

    # --- Today's 5-minute buckets (local-timezone-aligned). Each bucket has a
    #      local HH:MM key, a total, and per-model segments.
    #      Note: OpenRouter's minute granularity is capped at a 3-hour window,
    #      so we chunk from local midnight to now.
    today_slots = []
    today_start_utc = local_midnight_utc(today_local)
    by_slot = {}

    def fetch_minute_chunk(chunk_start, chunk_end):
        rows = _analytics({
            "metrics": ["total_usage"],
            "dimensions": ["model"],
            "granularity": "minute",
            "time_range": {
                "start": chunk_start.strftime("%Y-%m-%dT%H:%M:00Z"),
                "end": chunk_end.strftime("%Y-%m-%dT%H:%M:00Z"),
            },
            "limit": 5000,
        })
        if rows is not None:
            for row in rows:
                key = _row_value(row, ["date__minute", "created_at__minute"])
                raw_model = _row_value(row, ["model", "model_name"])
                if key and raw_model:
                    local_dt = _parse_utc_dt(key).astimezone(local_tz)
                    slot_m = (local_dt.minute // 5) * 5
                    slot_key = local_dt.strftime("%H") + f":{slot_m:02d}"
                    can = _canonical_model(raw_model)
                    bucket = by_slot.setdefault(slot_key, {})
                    bucket[can] = bucket.get(can, 0.0) + _as_float(_row_value(row, ["total_usage"]))

    # Chunk in 3-hour windows from local midnight UTC to now UTC
    chunk = today_start_utc
    while chunk < now_utc:
        chunk_end = min(chunk + datetime.timedelta(hours=3), now_utc)
        fetch_minute_chunk(chunk, chunk_end)
        chunk = chunk_end

    # Emit every 5-min slot from local midnight to now (even empty ones).
    day_midnight_local = datetime.datetime.combine(
        today_local, datetime.time.min).replace(tzinfo=local_tz)
    elapsed_mins = int((now_local - day_midnight_local).total_seconds() // 60)
    n_slots = max(1, elapsed_mins // 5 + 1)
    for i in range(n_slots):
        slot_dt = day_midnight_local + datetime.timedelta(minutes=i * 5)
        slot_key = slot_dt.strftime("%H:%M")
        models_map = by_slot.get(slot_key, {})
        total = round(sum(models_map.values()), 6)
        segs = [{"model": m, "total": round(v, 6)}
                for m, v in models_map.items() if v > 0]
        segs.sort(key=lambda x: x["total"], reverse=True)
        today_slots.append({"t": slot_key, "total": total, "models": segs})

    out = {
        "month": month_start_local.strftime("%Y-%m"),
        "month_total": month_total,
        "last24h": round(last24, 6),
        "generated_at": int(now_local.timestamp()),
        "days": days,
        "models": models,
        "series": series,
        "lastHour": last_hour,
        "todaySlots": today_slots,
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
