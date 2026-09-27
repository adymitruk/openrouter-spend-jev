#!/usr/bin/env python3
"""OpenRouter spend fetcher for the omarchy bar widget.

State is a directory tree:
  settings/openrouter-spend/<YYYY-MM-DD>/<HH:MM>/<canonical-model-slug>.json
Each file contains {"cost": <float>} for one model's spend in one 5-min slot.

Commands:
  fetch     Poll OpenRouter analytics, write per-slot per-model files.
  read      Scan the tree, print aggregated JSON to stdout.
  write-key <name> <value>   Write a key file.
"""

import datetime
import json
import os
import re
import secrets
import subprocess
import sys

MAX_RESPONSE = 256 * 1024
KEY_NAMES = {"openrouter-key"}
STATE_DIR_NAME = "openrouter-spend"


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


def state_dir_fd():
    fd = settings_fd()
    try:
        try:
            sfd = os.open(STATE_DIR_NAME, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        except FileNotFoundError:
            os.mkdir(STATE_DIR_NAME, 0o700, dir_fd=fd)
            sfd = os.open(STATE_DIR_NAME, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
        os.fchmod(sfd, 0o700)
        info = os.fstat(sfd)
        if not _is_dir(info.st_mode) or info.st_uid != os.getuid():
            os.close(sfd)
            raise OSError("unsafe state dir")
        return sfd, fd
    except BaseException:
        os.close(fd)
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


def _post(url, payload):
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
    parts = str(slug or "").rsplit("/", 1)
    if len(parts) == 2:
        name = re.sub(r"-\d{8}$", "", parts[1])
        return parts[0] + "/" + name
    return re.sub(r"-\d{8}$", "", str(slug or ""))


def _parse_utc_dt(s):
    s = str(s).strip().replace("T", " ").replace("Z", "")
    dt = datetime.datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def _safe_model_filename(model):
    s = model.replace("/", "_").replace(" ", "_")
    s = re.sub(r"[^a-zA-Z0-9_.-]", "_", s)
    if not s:
        s = "_"
    return s + ".json"


def write_slot_file(sfd, date_str, slot_key, model, cost):
    try:
        dfd = os.open(date_str, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=sfd)
    except FileNotFoundError:
        os.mkdir(date_str, 0o700, dir_fd=sfd)
        dfd = os.open(date_str, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=sfd)
    info = os.fstat(dfd)
    if not _is_dir(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        os.close(dfd)
        raise OSError("unsafe date dir")
    try:
        try:
            slotfd = os.open(slot_key, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dfd)
        except FileNotFoundError:
            os.mkdir(slot_key, 0o700, dir_fd=dfd)
            slotfd = os.open(slot_key, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dfd)
        info2 = os.fstat(slotfd)
        if not _is_dir(info2.st_mode) or info2.st_uid != os.getuid() or info2.st_mode & 0o022:
            os.close(slotfd)
            raise OSError("unsafe slot dir")
        fname = _safe_model_filename(model)
        f = -1
        tmp = None
        try:
            for _ in range(100):
                tmp = "." + fname + "." + secrets.token_hex(16)
                try:
                    f = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                                | os.O_CLOEXEC, 0o600, dir_fd=slotfd)
                    break
                except FileExistsError:
                    tmp = None
            else:
                raise OSError("no temp slot")
            data = json.dumps({"cost": round(cost, 6)}).encode("utf-8")
            off = 0
            while off < len(data):
                off += os.write(f, data[off:])
            os.fsync(f)
            os.replace(tmp, fname, src_dir_fd=slotfd, dst_dir_fd=slotfd)
            tmp = None
            os.close(f)
            f = -1
        finally:
            if f != -1:
                os.close(f)
            if tmp:
                try:
                    os.unlink(tmp, dir_fd=slotfd)
                except OSError:
                    pass
    finally:
        os.close(slotfd)
        os.close(dfd)


def fetch():
    now_aware = datetime.datetime.now().astimezone()
    local_tz = now_aware.tzinfo
    now_local = now_aware
    today_local = now_local.date()

    def local_midnight_utc(d):
        naive = datetime.datetime.combine(d, datetime.time.min)
        return naive.replace(tzinfo=local_tz).astimezone(datetime.timezone.utc)

    today_start_utc = local_midnight_utc(today_local)
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    sfd, parent_fd = state_dir_fd()
    try:
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
            if rows is None:
                return
            grouped = {}
            for row in rows:
                ts = _row_value(row, ["date__minute", "created_at__minute"])
                raw_model = _row_value(row, ["model", "model_name"])
                if not ts or not raw_model:
                    continue
                local_dt = _parse_utc_dt(ts).astimezone(local_tz)
                date_str = local_dt.strftime("%Y-%m-%d")
                slot_m = (local_dt.minute // 5) * 5
                slot_key = local_dt.strftime("%H") + f":{slot_m:02d}"
                can = _canonical_model(raw_model)
                key = (date_str, slot_key, can)
                grouped[key] = grouped.get(key, 0.0) + _as_float(_row_value(row, ["total_usage"]))
            for (date_str, slot_key, model), cost in grouped.items():
                try:
                    write_slot_file(sfd, date_str, slot_key, model, cost)
                except OSError:
                    pass

        chunk = today_start_utc
        while chunk < now_utc:
            chunk_end = min(chunk + datetime.timedelta(hours=3), now_utc)
            fetch_minute_chunk(chunk, chunk_end)
            chunk = chunk_end
    finally:
        os.close(sfd)
        os.close(parent_fd)
    return 0


def read():
    sfd, parent_fd = state_dir_fd()
    now_local = datetime.datetime.now().astimezone()
    local_tz = now_local.tzinfo
    today_local = now_local.date()
    month_start_local = today_local.replace(day=1)

    records = []
    try:
        for entry in os.listdir(sfd):
            if len(entry) != 10 or entry[4] != "-" or entry[7] != "-":
                continue
            date_str = entry
            try:
                dfd = os.open(date_str, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=sfd)
            except OSError:
                continue
            try:
                for slot_entry in os.listdir(dfd):
                    if len(slot_entry) != 5 or slot_entry[2] != ":":
                        continue
                    slot_key = slot_entry
                    try:
                        slotfd = os.open(slot_key, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dfd)
                    except OSError:
                        continue
                    try:
                        for model_file in os.listdir(slotfd):
                            if not model_file.endswith(".json"):
                                continue
                            try:
                                mf = os.open(model_file, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=slotfd)
                            except OSError:
                                continue
                            try:
                                raw = os.read(mf, 4096)
                                info = os.fstat(mf)
                                mtime = info.st_mtime if info else 0
                            finally:
                                os.close(mf)
                            try:
                                obj = json.loads(raw.decode("utf-8", "replace"))
                                cost = _as_float(obj.get("cost", 0))
                            except (ValueError, AttributeError):
                                cost = 0.0
                            slug = model_file[:-5].replace("_", "/")
                            records.append((date_str, slot_key, slug, cost, mtime))
                    finally:
                        os.close(slotfd)
            finally:
                os.close(dfd)
    finally:
        os.close(sfd)
        os.close(parent_fd)

    if not records:
        empty = {
            "month": month_start_local.strftime("%Y-%m"),
            "month_total": 0.0,
            "last24h": 0.0,
            "generated_at": int(now_local.timestamp()),
            "days": [],
            "models": [],
            "series": [],
            "lastHour": [],
            "todaySlots": [],
        }
        sys.stdout.write(json.dumps(empty))
        return

    # per day
    days_by_date = {}
    model_totals_all = {}
    for date_str, slot_key, model, cost, mtime in records:
        days_by_date[date_str] = days_by_date.get(date_str, 0.0) + cost
        model_totals_all[model] = model_totals_all.get(model, 0.0) + cost
    days = [{"date": d, "total": round(t, 6)} for d, t in sorted(days_by_date.items(), reverse=True)]
    month_total = round(sum(d["total"] for d in days), 6)
    models = [{"model": m, "total": round(t, 6)} for m, t in model_totals_all.items() if t > 0]
    models.sort(key=lambda x: x["total"], reverse=True)

    # 30-day series
    start30_local = today_local - datetime.timedelta(days=29)
    series_bydate = {}
    for date_str, slot_key, model, cost, mtime in records:
        try:
            d = datetime.date.fromisoformat(date_str)
        except ValueError:
            continue
        if d < start30_local or d > today_local:
            continue
        rec = series_bydate.setdefault(date_str, {})
        rec[model] = rec.get(model, 0.0) + cost
    series = []
    for i in range(30):
        d = start30_local + datetime.timedelta(days=i)
        ds = d.isoformat()
        day_models = series_bydate.get(ds, {})
        segs = [{"model": m, "total": round(v, 6)} for m, v in day_models.items() if v > 0]
        segs.sort(key=lambda x: x["total"], reverse=True)
        series.append({"date": ds, "total": round(sum(day_models.values()), 6), "models": segs})

    # last 24h
    cutoff_ts = now_local.timestamp() - 86400
    last24 = round(sum(cost for _, _, _, cost, mtime in records if mtime >= cutoff_ts), 6)

    # last hour
    hour_cutoff = now_local - datetime.timedelta(hours=1)
    last_hour_slots = {}
    for date_str, slot_key, model, cost, mtime in records:
        try:
            slot_dt = datetime.datetime.strptime(date_str + " " + slot_key, "%Y-%m-%d %H:%M").replace(tzinfo=local_tz)
        except ValueError:
            continue
        if slot_dt < hour_cutoff:
            continue
        bucket = last_hour_slots.setdefault(slot_key, {})
        bucket[model] = bucket.get(model, 0.0) + cost
    last_hour_start = now_local - datetime.timedelta(minutes=60)
    minutes_60_local = []
    for i in range(60):
        t = last_hour_start + datetime.timedelta(minutes=i)
        slot_m = (t.minute // 5) * 5
        slot_key = t.strftime("%H") + f":{slot_m:02d}"
        models_map = last_hour_slots.get(slot_key, {})
        segs = [{"model": m, "total": round(v, 6)} for m, v in models_map.items() if v > 0]
        segs.sort(key=lambda x: x["total"], reverse=True)
        minutes_60_local.append({"t": t.strftime("%H:%M"), "total": round(sum(models_map.values()), 6), "models": segs})
    last_hour = []
    for b in range(12):
        if b * 5 >= len(minutes_60_local):
            break
        merged = {}
        for m in minutes_60_local[b * 5:(b + 1) * 5]:
            for seg in m.get("models", []):
                merged[seg["model"]] = merged.get(seg["model"], 0.0) + seg["total"]
        segs = [{"model": m, "total": round(v, 6)} for m, v in merged.items() if v > 0]
        segs.sort(key=lambda x: x["total"], reverse=True)
        last_hour.append({
            "t": minutes_60_local[b * 5]["t"],
            "total": round(sum(x["total"] for x in minutes_60_local[b * 5:(b + 1) * 5]), 6),
            "models": segs,
        })

    # today slots
    today_slots = []
    day_midnight_local = datetime.datetime.combine(today_local, datetime.time.min).replace(tzinfo=local_tz)
    elapsed_mins = int((now_local - day_midnight_local).total_seconds() // 60)
    n_slots = max(1, elapsed_mins // 5 + 1)
    for i in range(n_slots):
        slot_dt = day_midnight_local + datetime.timedelta(minutes=i * 5)
        slot_key = slot_dt.strftime("%H:%M")
        models_map = {}
        for date_str, rec_slot, model, cost, mtime in records:
            if date_str == today_local.isoformat() and rec_slot == slot_key:
                models_map[model] = models_map.get(model, 0.0) + cost
        segs = [{"model": m, "total": round(v, 6)} for m, v in models_map.items() if v > 0]
        segs.sort(key=lambda x: x["total"], reverse=True)
        today_slots.append({"t": slot_key, "total": round(sum(models_map.values()), 6), "models": segs})

    out = {
        "month": month_start_local.strftime("%Y-%m"),
        "month_total": month_total,
        "last24h": last24,
        "generated_at": int(now_local.timestamp()),
        "days": days,
        "models": models,
        "series": series,
        "lastHour": last_hour,
        "todaySlots": today_slots,
    }
    sys.stdout.write(json.dumps(out))


def main():
    try:
        if len(sys.argv) >= 2 and sys.argv[1] == "fetch":
            return fetch()
        if sys.argv[1:2] == ["read"]:
            read()
            return 0
        if len(sys.argv) == 4 and sys.argv[1] == "write-key":
            write_key(sys.argv[2], sys.argv[3])
            return 0
    except (OSError, ValueError):
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
