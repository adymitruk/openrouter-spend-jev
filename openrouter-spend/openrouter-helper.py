#!/usr/bin/env python3
"""OpenRouter spend fetcher for the omarchy bar widget.

State is a directory tree under settings/openrouter-spend/:

  last-month/<YYYY-MM-DD>/<canonical-model>.json
      {"cost": <float>, "model": "<slug>"}
      One file per model per local day. Source for the month total,
      the per-day and per-model lists, and the 30-day chart.

  last-month/hours/<YYYY-MM-DD>/<HH>/<canonical-model>.json
      Same payload, one local clock-hour, kept ~26h. Source for last-24h.

  last-hour/<YYYY-MM-DD>/<HH:MM>/<canonical-model>.json
      Same payload, one 5-minute local slot, kept ~70min. Source for
      the last-hour bars.

Commands:
  fetch     Poll OpenRouter analytics and refresh the tree.
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


def _write_model_file(parent_fd, date_str, model, cost):
    """Write <parent>/<date_str>/<model>.json, creating the date dir if needed."""
    try:
        dfd = _stat_safe_open(parent_fd, date_str, "date dir", True)
    except OSError:
        return False
    try:
        fname = _safe_model_filename(model)
        f = -1
        tmp = None
        try:
            for _ in range(100):
                tmp = "." + fname + "." + secrets.token_hex(16)
                try:
                    f = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                                | os.O_CLOEXEC, 0o600, dir_fd=dfd)
                    break
                except FileExistsError:
                    tmp = None
            else:
                raise OSError("no temp slot")
            data = json.dumps({"cost": round(cost, 6), "model": model}).encode("utf-8")
            off = 0
            while off < len(data):
                off += os.write(f, data[off:])
            os.fsync(f)
            os.replace(tmp, fname, src_dir_fd=dfd, dst_dir_fd=dfd)
            tmp = None
            os.close(f)
            f = -1
        finally:
            if f != -1:
                os.close(f)
            if tmp:
                try:
                    os.unlink(tmp, dir_fd=dfd)
                except OSError:
                    pass
        return True
    finally:
        os.close(dfd)


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
            data = json.dumps({"cost": round(cost, 6), "model": model}).encode("utf-8")
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


def _is_date_name(name):
    return (
        len(name) == 10
        and name[4] == "-"
        and name[7] == "-"
        and name[:4].isdigit()
        and name[5:7].isdigit()
        and name[8:].isdigit()
    )


def _is_slot_name(name):
    return len(name) == 5 and name[2] == ":" and name[:2].isdigit() and name[3:].isdigit()


def _is_hour_name(name):
    return len(name) == 2 and name.isdigit()


def _model_from_filename(filename):
    stem = filename[:-5] if filename.endswith(".json") else filename
    if "_" in stem:
        author, name = stem.split("_", 1)
        return author + "/" + name
    return stem


def _read_cost_model(dir_fd, filename):
    try:
        mf = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dir_fd)
    except OSError:
        return None
    try:
        raw = os.read(mf, 4096)
    finally:
        os.close(mf)
    model = _model_from_filename(filename)
    cost = 0.0
    try:
        obj = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        obj = None
    if isinstance(obj, dict):
        cost = _as_float(obj.get("cost", 0))
        if obj.get("model"):
            model = str(obj["model"])
    return model, cost


def _rm_tree(parent_fd, name):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent_fd)
    except OSError:
        return
    try:
        info = os.fstat(fd)
        if not _is_dir(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            return
        for entry in list(os.listdir(fd)):
            if not entry or entry in (".", "..") or "/" in entry:
                continue
            try:
                st = os.stat(entry, dir_fd=fd, follow_symlinks=False)
            except OSError:
                continue
            if _is_dir(st.st_mode):
                _rm_tree(fd, entry)
            else:
                try:
                    os.unlink(entry, dir_fd=fd)
                except OSError:
                    pass
    finally:
        os.close(fd)
    try:
        os.rmdir(name, dir_fd=parent_fd)
    except OSError:
        pass


def _clear_extra_json(dir_fd, keep):
    for fn in list(os.listdir(dir_fd)):
        if fn.endswith(".json") and not fn.startswith(".") and fn not in keep:
            try:
                os.unlink(fn, dir_fd=dir_fd)
            except OSError:
                pass


def _open_named(parent_fd, name, create):
    return _stat_safe_open(parent_fd, name, name, create, private=True)


def _scan_daily(month_fd):
    records = []
    for date_str in os.listdir(month_fd):
        if not _is_date_name(date_str):
            continue
        try:
            dfd = os.open(date_str, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=month_fd)
        except OSError:
            continue
        try:
            info = os.fstat(dfd)
            if not _is_dir(info.st_mode) or info.st_uid != os.getuid():
                continue
            for model_file in os.listdir(dfd):
                if model_file.startswith(".") or not model_file.endswith(".json"):
                    continue
                parsed = _read_cost_model(dfd, model_file)
                if not parsed:
                    continue
                model, cost = parsed
                records.append((date_str, model, cost))
        finally:
            os.close(dfd)
    return records


def _scan_hours(month_fd):
    records = []
    try:
        hours_fd = os.open("hours", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=month_fd)
    except OSError:
        return records
    try:
        info = os.fstat(hours_fd)
        if not _is_dir(info.st_mode) or info.st_uid != os.getuid():
            return records
        for date_str in os.listdir(hours_fd):
            if not _is_date_name(date_str):
                continue
            try:
                dfd = os.open(date_str, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=hours_fd)
            except OSError:
                continue
            try:
                for hour in os.listdir(dfd):
                    if not _is_hour_name(hour):
                        continue
                    try:
                        hfd = os.open(hour, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dfd)
                    except OSError:
                        continue
                    try:
                        hinfo = os.fstat(hfd)
                        if not _is_dir(hinfo.st_mode) or hinfo.st_uid != os.getuid():
                            continue
                        for model_file in os.listdir(hfd):
                            if model_file.startswith(".") or not model_file.endswith(".json"):
                                continue
                            parsed = _read_cost_model(hfd, model_file)
                            if not parsed:
                                continue
                            model, cost = parsed
                            records.append((date_str, hour, model, cost))
                    finally:
                        os.close(hfd)
            finally:
                os.close(dfd)
    finally:
        os.close(hours_fd)
    return records


def _scan_slots(hour_root_fd):
    records = []
    for date_str in os.listdir(hour_root_fd):
        if not _is_date_name(date_str):
            continue
        try:
            dfd = os.open(date_str, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=hour_root_fd)
        except OSError:
            continue
        try:
            info = os.fstat(dfd)
            if not _is_dir(info.st_mode) or info.st_uid != os.getuid():
                continue
            for slot_key in os.listdir(dfd):
                if not _is_slot_name(slot_key):
                    continue
                try:
                    slotfd = os.open(slot_key, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dfd)
                except OSError:
                    continue
                try:
                    sinfo = os.fstat(slotfd)
                    if not _is_dir(sinfo.st_mode) or sinfo.st_uid != os.getuid():
                        continue
                    for model_file in os.listdir(slotfd):
                        if model_file.startswith(".") or not model_file.endswith(".json"):
                            continue
                        parsed = _read_cost_model(slotfd, model_file)
                        if not parsed:
                            continue
                        model, cost = parsed
                        records.append((date_str, slot_key, model, cost))
                finally:
                    os.close(slotfd)
        finally:
            os.close(dfd)
    return records


def _migrate_legacy(sfd, month_fd, lasthour_fd, now_local):
    """Copy the old day/ tree and recent 5-min slots into the new layout."""
    cutoff = now_local - datetime.timedelta(minutes=70)
    tz = now_local.tzinfo
    try:
        day_fd = os.open("day", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=sfd)
    except OSError:
        day_fd = -1
    if day_fd != -1:
        try:
            for date_str in os.listdir(day_fd):
                if not _is_date_name(date_str):
                    continue
                try:
                    dfd = os.open(date_str, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=day_fd)
                except OSError:
                    continue
                try:
                    for model_file in os.listdir(dfd):
                        if model_file.startswith(".") or not model_file.endswith(".json"):
                            continue
                        parsed = _read_cost_model(dfd, model_file)
                        if not parsed:
                            continue
                        model, cost = parsed
                        _write_model_file(month_fd, date_str, model, cost)
                finally:
                    os.close(dfd)
        finally:
            os.close(day_fd)
    for date_str in os.listdir(sfd):
        if not _is_date_name(date_str):
            continue
        try:
            dfd = os.open(date_str, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=sfd)
        except OSError:
            continue
        try:
            for slot_key in os.listdir(dfd):
                if not _is_slot_name(slot_key):
                    continue
                try:
                    slot_dt = datetime.datetime.strptime(
                        date_str + " " + slot_key, "%Y-%m-%d %H:%M"
                    ).replace(tzinfo=tz)
                except ValueError:
                    continue
                if slot_dt < cutoff:
                    continue
                try:
                    slotfd = os.open(slot_key, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=dfd)
                except OSError:
                    continue
                try:
                    for model_file in os.listdir(slotfd):
                        if model_file.startswith(".") or not model_file.endswith(".json"):
                            continue
                        parsed = _read_cost_model(slotfd, model_file)
                        if not parsed:
                            continue
                        model, cost = parsed
                        try:
                            write_slot_file(lasthour_fd, date_str, slot_key, model, cost)
                        except OSError:
                            pass
                finally:
                    os.close(slotfd)
        finally:
            os.close(dfd)


def _prune_daily(month_fd, today_local):
    cutoff = (today_local - datetime.timedelta(days=32)).isoformat()
    for entry in list(os.listdir(month_fd)):
        if _is_date_name(entry) and entry < cutoff:
            _rm_tree(month_fd, entry)


def _prune_hours(hours_fd, now_local):
    cutoff = now_local - datetime.timedelta(hours=26)
    tz = now_local.tzinfo
    for date_str in list(os.listdir(hours_fd)):
        if not _is_date_name(date_str):
            continue
        try:
            dfd = os.open(date_str, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=hours_fd)
        except OSError:
            continue
        empty = False
        try:
            for hour in list(os.listdir(dfd)):
                if not _is_hour_name(hour):
                    continue
                try:
                    start = datetime.datetime.strptime(
                        date_str + " " + hour, "%Y-%m-%d %H"
                    ).replace(tzinfo=tz)
                except ValueError:
                    continue
                if start < cutoff:
                    _rm_tree(dfd, hour)
            empty = not os.listdir(dfd)
        finally:
            os.close(dfd)
        if empty:
            try:
                os.rmdir(date_str, dir_fd=hours_fd)
            except OSError:
                pass


def _prune_slots(hour_root_fd, now_local):
    cutoff = now_local - datetime.timedelta(minutes=70)
    tz = now_local.tzinfo
    for date_str in list(os.listdir(hour_root_fd)):
        if not _is_date_name(date_str):
            continue
        try:
            day = datetime.date.fromisoformat(date_str)
        except ValueError:
            continue
        if day < (now_local.date() - datetime.timedelta(days=2)):
            _rm_tree(hour_root_fd, date_str)
            continue
        try:
            dfd = os.open(date_str, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=hour_root_fd)
        except OSError:
            continue
        empty = False
        try:
            for slot_key in list(os.listdir(dfd)):
                if not _is_slot_name(slot_key):
                    continue
                try:
                    slot_dt = datetime.datetime.strptime(
                        date_str + " " + slot_key, "%Y-%m-%d %H:%M"
                    ).replace(tzinfo=tz)
                except ValueError:
                    continue
                if slot_dt < cutoff:
                    _rm_tree(dfd, slot_key)
            empty = not os.listdir(dfd)
        finally:
            os.close(dfd)
        if empty:
            try:
                os.rmdir(date_str, dir_fd=hour_root_fd)
            except OSError:
                pass


def _remove_legacy(sfd):
    for entry in list(os.listdir(sfd)):
        if entry == "day" or _is_date_name(entry):
            _rm_tree(sfd, entry)


def _drop_stale_daily(month_fd, start_date, end_date, written, failed):
    day = start_date
    while day <= end_date:
        date_str = day.isoformat()
        day += datetime.timedelta(days=1)
        if date_str in failed:
            continue
        try:
            dfd = os.open(date_str, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=month_fd)
        except OSError:
            continue
        try:
            _clear_extra_json(dfd, written.get(date_str, set()))
        finally:
            os.close(dfd)


def fetch():
    now_local = datetime.datetime.now().astimezone()
    local_tz = now_local.tzinfo
    today_local = now_local.date()
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    sfd, parent_fd = state_dir_fd()
    try:
        month_fd = _open_named(sfd, "last-month", True)
        hour_fd = _open_named(sfd, "last-hour", True)
        try:
            _migrate_legacy(sfd, month_fd, hour_fd, now_local)

            month_ok = True
            rows = []
            window_start = now_utc - datetime.timedelta(days=30)
            chunk = window_start
            while chunk < now_utc:
                chunk_end = min(chunk + datetime.timedelta(days=7), now_utc)
                part = _analytics({
                    "metrics": ["total_usage"],
                    "dimensions": ["model"],
                    "granularity": "hour",
                    "time_range": {
                        "start": chunk.strftime("%Y-%m-%dT%H:%M:00Z"),
                        "end": chunk_end.strftime("%Y-%m-%dT%H:%M:00Z"),
                    },
                    "limit": 5000,
                })
                if part is None:
                    month_ok = False
                    break
                rows.extend(part)
                chunk = chunk_end

            if month_ok:
                by_date_model = {}
                recent_hours = {}
                hour_cutoff = now_local - datetime.timedelta(hours=26)
                for row in rows:
                    ts = _row_value(row, ["date__hour", "created_at__hour", "created_at"])
                    raw_model = _row_value(row, ["model", "model_name"])
                    if not ts or not raw_model:
                        continue
                    local_dt = _parse_utc_dt(ts).astimezone(local_tz)
                    date_str = local_dt.strftime("%Y-%m-%d")
                    can = _canonical_model(raw_model)
                    cost = _as_float(_row_value(row, ["total_usage"]))
                    key = (date_str, can)
                    by_date_model[key] = by_date_model.get(key, 0.0) + cost
                    hour_start = local_dt.replace(minute=0, second=0, microsecond=0)
                    if hour_start >= hour_cutoff:
                        hk = hour_start.strftime("%H")
                        hkey = (date_str, hk, can)
                        recent_hours[hkey] = recent_hours.get(hkey, 0.0) + cost
                written_daily = {}
                failed_dates = set()
                for (date_str, model), cost in by_date_model.items():
                    if _write_model_file(month_fd, date_str, model, cost):
                        written_daily.setdefault(date_str, set()).add(_safe_model_filename(model))
                    else:
                        failed_dates.add(date_str)
                for date_str in failed_dates:
                    written_daily.pop(date_str, None)
                _drop_stale_daily(
                    month_fd,
                    today_local - datetime.timedelta(days=30),
                    today_local,
                    written_daily,
                    failed_dates,
                )
                try:
                    hours_fd = _open_named(month_fd, "hours", True)
                except OSError:
                    hours_fd = -1
                if hours_fd != -1:
                    try:
                        written_hours = {}
                        for (date_str, hour, model), cost in recent_hours.items():
                            try:
                                write_slot_file(hours_fd, date_str, hour, model, cost)
                            except OSError:
                                continue
                            written_hours.setdefault((date_str, hour), set()).add(
                                _safe_model_filename(model)
                            )
                        for (date_str, hour), keep in written_hours.items():
                            try:
                                dfd = os.open(
                                    date_str,
                                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                    dir_fd=hours_fd,
                                )
                            except OSError:
                                continue
                            try:
                                hfd = os.open(
                                    hour,
                                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                    dir_fd=dfd,
                                )
                            except OSError:
                                os.close(dfd)
                                continue
                            try:
                                _clear_extra_json(hfd, keep)
                            finally:
                                os.close(hfd)
                                os.close(dfd)
                        _prune_hours(hours_fd, now_local)
                    finally:
                        os.close(hours_fd)
                _prune_daily(month_fd, today_local)
                _remove_legacy(sfd)

            minute_ok = True
            minute_rows = _analytics({
                "metrics": ["total_usage"],
                "dimensions": ["model"],
                "granularity": "minute",
                "time_range": {
                    "start": (now_utc - datetime.timedelta(minutes=70)).strftime("%Y-%m-%dT%H:%M:00Z"),
                    "end": now_utc.strftime("%Y-%m-%dT%H:%M:00Z"),
                },
                "limit": 5000,
            })
            if minute_rows is None:
                minute_ok = False
            else:
                grouped = {}
                slot_cutoff = now_local - datetime.timedelta(minutes=70)
                for row in minute_rows:
                    ts = _row_value(row, ["date__minute", "created_at__minute"])
                    raw_model = _row_value(row, ["model", "model_name"])
                    if not ts or not raw_model:
                        continue
                    local_dt = _parse_utc_dt(ts).astimezone(local_tz)
                    slot_m = (local_dt.minute // 5) * 5
                    slot_dt = local_dt.replace(minute=slot_m, second=0, microsecond=0)
                    if slot_dt < slot_cutoff:
                        continue
                    date_str = slot_dt.strftime("%Y-%m-%d")
                    slot_key = slot_dt.strftime("%H:%M")
                    can = _canonical_model(raw_model)
                    key = (date_str, slot_key, can)
                    grouped[key] = grouped.get(key, 0.0) + _as_float(_row_value(row, ["total_usage"]))
                for (date_str, slot_key, model), cost in grouped.items():
                    try:
                        write_slot_file(hour_fd, date_str, slot_key, model, cost)
                    except OSError:
                        minute_ok = False
                if minute_ok:
                    _prune_slots(hour_fd, now_local)
        finally:
            os.close(month_fd)
            os.close(hour_fd)
    finally:
        os.close(sfd)
        os.close(parent_fd)
    return 0


def read():
    now_local = datetime.datetime.now().astimezone()
    local_tz = now_local.tzinfo
    today_local = now_local.date()
    month_start_local = today_local.replace(day=1)

    sfd, parent_fd = state_dir_fd()
    daily = []
    hours = []
    slots = []
    try:
        try:
            month_fd = _open_named(sfd, "last-month", False)
        except OSError:
            month_fd = -1
        if month_fd != -1:
            try:
                daily = _scan_daily(month_fd)
                hours = _scan_hours(month_fd)
            finally:
                os.close(month_fd)
        try:
            hour_fd = _open_named(sfd, "last-hour", False)
        except OSError:
            hour_fd = -1
        if hour_fd != -1:
            try:
                slots = _scan_slots(hour_fd)
            finally:
                os.close(hour_fd)
    finally:
        os.close(sfd)
        os.close(parent_fd)

    if not daily and not hours and not slots:
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

    month_threshold = month_start_local.isoformat()
    days_by_date = {}
    model_totals = {}
    for date_str, model, cost in daily:
        days_by_date[date_str] = days_by_date.get(date_str, 0.0) + cost
        if date_str >= month_threshold:
            model_totals[model] = model_totals.get(model, 0.0) + cost
    days = [{"date": d, "total": round(t, 6)} for d, t in sorted(days_by_date.items(), reverse=True)]
    month_total = round(sum(t for d, t in days_by_date.items() if d >= month_threshold), 6)
    models = [{"model": m, "total": round(t, 6)} for m, t in model_totals.items() if t > 0]
    models.sort(key=lambda x: x["total"], reverse=True)

    start30_local = today_local - datetime.timedelta(days=29)
    series_bydate = {}
    for date_str, model, cost in daily:
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

    cutoff_24 = now_local - datetime.timedelta(hours=24)
    last24 = 0.0
    if hours:
        for date_str, hour, _model, cost in hours:
            try:
                start = datetime.datetime.strptime(
                    date_str + " " + hour, "%Y-%m-%d %H"
                ).replace(tzinfo=local_tz)
            except ValueError:
                continue
            end = start + datetime.timedelta(hours=1)
            if end > cutoff_24 and start <= now_local:
                last24 += cost
    else:
        today_str = today_local.isoformat()
        last24 = sum(cost for date_str, _model, cost in daily if date_str == today_str)
    last24 = round(last24, 6)

    # One bar per 5-minute slot whose start falls in the last 60 minutes.
    # Each slot file is the whole bucket, so it is counted once.
    # Floor to the 5-minute slot that contains "60 minutes ago" so a bucket
    # straddling the cutoff is included once, not dropped.
    window_start = now_local - datetime.timedelta(minutes=60)
    minute = (window_start.minute // 5) * 5
    boundary = window_start.replace(minute=minute, second=0, microsecond=0)
    by_slot = {}
    for date_str, slot_key, model, cost in slots:
        try:
            slot_dt = datetime.datetime.strptime(
                date_str + " " + slot_key, "%Y-%m-%d %H:%M"
            ).replace(tzinfo=local_tz)
        except ValueError:
            continue
        if slot_dt < boundary or slot_dt > now_local:
            continue
        bucket = by_slot.setdefault((date_str, slot_key), {})
        bucket[model] = bucket.get(model, 0.0) + cost
    last_hour = []
    slot_dt = boundary
    while slot_dt <= now_local and len(last_hour) < 13:
        date_str = slot_dt.strftime("%Y-%m-%d")
        slot_key = slot_dt.strftime("%H:%M")
        models_map = by_slot.get((date_str, slot_key), {})
        segs = [{"model": m, "total": round(v, 6)} for m, v in models_map.items() if v > 0]
        segs.sort(key=lambda x: x["total"], reverse=True)
        last_hour.append({
            "t": slot_key,
            "total": round(sum(models_map.values()), 6),
            "models": segs,
        })
        slot_dt += datetime.timedelta(minutes=5)

    today_slots = []
    day_midnight_local = datetime.datetime.combine(today_local, datetime.time.min).replace(tzinfo=local_tz)
    elapsed_mins = int((now_local - day_midnight_local).total_seconds() // 60)
    n_slots = max(1, elapsed_mins // 5 + 1)
    today_str = today_local.isoformat()
    for i in range(n_slots):
        slot_dt = day_midnight_local + datetime.timedelta(minutes=i * 5)
        slot_key = slot_dt.strftime("%H:%M")
        models_map = {}
        for date_str, rec_slot, model, cost in slots:
            if date_str == today_str and rec_slot == slot_key:
                models_map[model] = models_map.get(model, 0.0) + cost
        segs = [{"model": m, "total": round(v, 6)} for m, v in models_map.items() if v > 0]
        segs.sort(key=lambda x: x["total"], reverse=True)
        today_slots.append({
            "t": slot_key,
            "total": round(sum(models_map.values()), 6),
            "models": segs,
        })

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
