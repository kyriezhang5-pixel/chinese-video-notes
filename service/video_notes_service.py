#!/usr/bin/env python3
"""
Lightweight local capture service for Chinese Video Notes.

The service intentionally uses only Python's standard library. It accepts
captures from the Chrome extension, stores JSONL records, and writes screenshots
as small image files. It does not keep captures in memory.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import sys
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


HOST = "127.0.0.1"
PORT = int(os.environ.get("VIDEO_NOTES_PORT", "8765"))
NOTES_HOME = Path(
    os.environ.get("VIDEO_NOTES_HOME", str(Path.home() / "Documents" / "VideoNotes"))
).expanduser()
BODY_LIMIT_BYTES = 18 * 1024 * 1024
TEXT_LIMIT = 50000
VALID_SOURCE_TYPES = {"text", "screenshot", "video_marker", "page_context", "transcript"}
VALID_PLATFORMS = {"bilibili", "douyin", "xiaohongshu", "web", "unknown"}
SESSIONS_LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ensure_dirs() -> None:
    for name in ("inbox", "notes", "exports", "tmp"):
        (NOTES_HOME / name).mkdir(parents=True, exist_ok=True)
    (NOTES_HOME / "inbox" / "assets").mkdir(parents=True, exist_ok=True)
    (NOTES_HOME / "inbox" / "sessions").mkdir(parents=True, exist_ok=True)
    ensure_session_state()


def cleanup_tmp(max_age_seconds: int = 3600) -> int:
    tmp = NOTES_HOME / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    removed = 0
    cutoff = time.time() - max_age_seconds
    for path in tmp.iterdir():
        try:
            if path.stat().st_mtime < cutoff:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                removed += 1
        except FileNotFoundError:
            continue
    return removed


def truncate(value: Any, limit: int = TEXT_LIMIT) -> Any:
    if not isinstance(value, str):
        return value
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...[truncated]"


def detect_platform(url: str) -> str:
    host = url.lower()
    if "bilibili.com" in host or "b23.tv" in host:
        return "bilibili"
    if "douyin.com" in host or "iesdouyin.com" in host:
        return "douyin"
    if "xiaohongshu.com" in host or "xhslink.com" in host:
        return "xiaohongshu"
    if host.startswith(("http://", "https://")):
        return "web"
    return "unknown"


def is_allowed_origin(origin: str) -> bool:
    return not origin or origin.startswith("chrome-extension://")


def sessions_path() -> Path:
    return NOTES_HOME / "inbox" / "sessions.json"


def count_records(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def legacy_session_name(path: Path) -> str:
    try:
        parsed = datetime.strptime(path.stem, "%Y-%m-%d")
        return f"历史采集 {parsed.strftime('%Y年%m月%d日')}"
    except ValueError:
        return f"历史采集 {path.stem}"


def ensure_session_state() -> None:
    path = sessions_path()
    if path.exists():
        return

    sessions: list[dict[str, Any]] = []
    legacy_files = sorted(
        (NOTES_HOME / "inbox").glob("*.jsonl"),
        key=lambda item: item.stat().st_mtime,
    )
    for legacy in legacy_files:
        timestamp = datetime.fromtimestamp(legacy.stat().st_mtime).astimezone().isoformat(timespec="seconds")
        sessions.append(
            {
                "id": f"legacy-{legacy.stem}",
                "name": legacy_session_name(legacy),
                "created_at": timestamp,
                "updated_at": timestamp,
                "file": legacy.name,
                "count": count_records(legacy),
                "legacy": True,
            }
        )

    state = {
        "active_session_id": sessions[-1]["id"] if sessions else "",
        "sessions": sessions,
    }
    write_session_state(state)


def load_session_state() -> dict[str, Any]:
    ensure_session_state()
    try:
        state = json.loads(sessions_path().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        state = {"active_session_id": "", "sessions": []}
    if not isinstance(state, dict):
        return {"active_session_id": "", "sessions": []}
    if not isinstance(state.get("sessions"), list):
        state["sessions"] = []
    return state


def write_session_state(state: dict[str, Any]) -> None:
    path = sessions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def normalize_session_name(value: Any) -> str:
    name = re.sub(r"\s+", " ", str(value or "")).strip()
    if not name:
        raise ValueError("采集名称不能为空")
    return name[:80]


def session_path(session: dict[str, Any]) -> Path:
    relative = Path(str(session.get("file") or ""))
    target = (NOTES_HOME / "inbox" / relative).resolve()
    inbox = (NOTES_HOME / "inbox").resolve()
    if target != inbox and inbox not in target.parents:
        raise ValueError("采集文件路径无效")
    return target


def active_session_from_state(state: dict[str, Any]) -> dict[str, Any] | None:
    active_id = str(state.get("active_session_id") or "")
    return next((item for item in state["sessions"] if item.get("id") == active_id), None)


def create_session(payload: dict[str, Any]) -> dict[str, Any]:
    name = normalize_session_name(payload.get("name"))
    now = now_iso()
    session_id = str(uuid.uuid4())
    session = {
        "id": session_id,
        "name": name,
        "created_at": now,
        "updated_at": now,
        "file": f"sessions/{session_id}.jsonl",
        "count": 0,
        "legacy": False,
    }
    with SESSIONS_LOCK:
        state = load_session_state()
        state["sessions"].append(session)
        state["active_session_id"] = session_id
        session_file = session_path(session)
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.touch(exist_ok=True)
        write_session_state(state)
    return session


def activate_session(payload: dict[str, Any]) -> dict[str, Any] | None:
    session_id = str(payload.get("id") or "")
    if not session_id:
        raise ValueError("缺少采集 ID")
    with SESSIONS_LOCK:
        state = load_session_state()
        session = next((item for item in state["sessions"] if item.get("id") == session_id), None)
        if session is None:
            return None
        state["active_session_id"] = session_id
        write_session_state(state)
    return session


def list_sessions() -> dict[str, Any]:
    with SESSIONS_LOCK:
        state = load_session_state()
    sessions = sorted(
        state["sessions"],
        key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""),
        reverse=True,
    )
    return {
        "active_session_id": state.get("active_session_id") or "",
        "sessions": sessions,
    }


def require_active_session() -> dict[str, Any]:
    state = load_session_state()
    session = active_session_from_state(state)
    if session is None:
        raise ValueError("请先新建采集")
    return session


def update_session_stats(session_id: str, count_delta: int = 0, source_path: Path | None = None) -> None:
    with SESSIONS_LOCK:
        state = load_session_state()
        session = next((item for item in state["sessions"] if item.get("id") == session_id), None)
        if session is None and source_path is not None:
            source_resolved = source_path.resolve()
            session = next(
                (
                    item
                    for item in state["sessions"]
                    if session_path(item).resolve() == source_resolved
                ),
                None,
            )
        if session is None:
            return
        session["updated_at"] = now_iso()
        session["count"] = max(0, int(session.get("count") or 0) + count_delta)
        write_session_state(state)


def write_screenshot(record_id: str, data_url: str) -> str | None:
    match = re.match(r"^data:image/(png|jpeg|jpg);base64,(.+)$", data_url, re.S)
    if not match:
        return None
    ext = "jpg" if match.group(1) in {"jpeg", "jpg"} else "png"
    raw = base64.b64decode(match.group(2), validate=True)
    asset_dir = NOTES_HOME / "inbox" / "assets" / datetime.now().strftime("%Y-%m-%d")
    asset_dir.mkdir(parents=True, exist_ok=True)
    out = asset_dir / f"{record_id}.{ext}"
    out.write_bytes(raw)
    return str(out)


def append_record(payload: dict[str, Any]) -> dict[str, Any]:
    session = require_active_session()
    record_id = str(uuid.uuid4())
    url = str(payload.get("url") or "")
    source_type = str(payload.get("source_type") or "page_context")
    platform = str(payload.get("platform") or detect_platform(url))
    if source_type not in VALID_SOURCE_TYPES:
        source_type = "page_context"
    if platform not in VALID_PLATFORMS:
        platform = detect_platform(url)

    record: dict[str, Any] = {
        "id": record_id,
        "session_id": session["id"],
        "session_name": session["name"],
        "created_at": now_iso(),
        "source_type": source_type,
        "platform": platform,
        "url": url,
        "title": truncate(str(payload.get("title") or ""), 500),
        "selected_text": truncate(payload.get("selected_text") or ""),
        "video_time_seconds": payload.get("video_time_seconds"),
        "screenshot_path": "",
        "notes": truncate(payload.get("notes") or ""),
    }

    for optional in ("page_text", "transcript_text", "author", "description"):
        if optional in payload:
            record[optional] = truncate(payload.get(optional) or "")

    data_url = payload.get("screenshot_data_url")
    if source_type == "screenshot" and isinstance(data_url, str) and data_url:
        record["screenshot_path"] = write_screenshot(record_id, data_url) or ""

    target = session_path(session)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    update_session_stats(str(session["id"]), 1)
    return record


def inbox_files() -> list[Path]:
    inbox = NOTES_HOME / "inbox"
    files = list(inbox.glob("*.jsonl")) + list((inbox / "sessions").glob("*.jsonl"))
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def rewrite_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp.replace(path)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
    return records


def update_record(payload: dict[str, Any]) -> dict[str, Any] | None:
    record_id = str(payload.get("id") or "")
    if not record_id:
        raise ValueError("missing id")
    allowed = {"title", "selected_text", "notes"}
    updates = {key: truncate(payload[key], 20000 if key != "title" else 500) for key in allowed if key in payload}
    if not updates:
        raise ValueError("nothing to update")
    updates["updated_at"] = now_iso()

    for path in inbox_files():
        records = load_jsonl(path)
        for record in records:
            if record.get("id") == record_id:
                record.update(updates)
                rewrite_jsonl(path, records)
                return record
    return None


def delete_record(payload: dict[str, Any]) -> dict[str, Any] | None:
    record_id = str(payload.get("id") or "")
    if not record_id:
        raise ValueError("missing id")

    for path in inbox_files():
        records = load_jsonl(path)
        kept = []
        removed: dict[str, Any] | None = None
        for record in records:
            if record.get("id") == record_id:
                removed = record
            else:
                kept.append(record)
        if removed is not None:
            rewrite_jsonl(path, kept)
            screenshot_path = removed.get("screenshot_path")
            if isinstance(screenshot_path, str) and screenshot_path:
                target = Path(screenshot_path)
                try:
                    if target.exists() and target.is_file() and target.is_relative_to(NOTES_HOME):
                        target.unlink()
                except (OSError, ValueError):
                    pass
            session_id = str(removed.get("session_id") or "")
            update_session_stats(session_id, -1, path)
            return removed
    return None


def latest_session() -> dict[str, Any]:
    with SESSIONS_LOCK:
        state = load_session_state()
        session = active_session_from_state(state)
    if session is None:
        return {
            "notes_home": str(NOTES_HOME),
            "session": None,
            "session_file": "",
            "count": 0,
            "recent": [],
        }
    session_file = session_path(session)
    count = 0
    recent: list[dict[str, Any]] = []
    if session_file.exists():
        with session_file.open("r", encoding="utf-8") as f:
            for line in f:
                count += 1
                if len(recent) >= 20:
                    recent.pop(0)
                try:
                    recent.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return {
        "notes_home": str(NOTES_HOME),
        "session": session,
        "session_file": str(session_file),
        "count": count,
        "recent": recent,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "ChineseVideoNotes/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (now_iso(), fmt % args))

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        origin = self.headers.get("Origin", "")
        if origin.startswith("chrome-extension://"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _local_only(self) -> bool:
        host = self.client_address[0]
        return host in {"127.0.0.1", "::1"}

    def _origin_allowed(self) -> bool:
        return is_allowed_origin(self.headers.get("Origin", ""))

    def do_OPTIONS(self) -> None:
        if not self._local_only() or not self._origin_allowed():
            self._send_json(403, {"ok": False, "error": "request origin not allowed"})
            return
        self._send_json(200, {"ok": True})

    def do_GET(self) -> None:
        if not self._local_only() or not self._origin_allowed():
            self._send_json(403, {"ok": False, "error": "request origin not allowed"})
            return
        if self.path == "/health":
            self._send_json(200, {"ok": True, "notes_home": str(NOTES_HOME)})
            return
        if self.path == "/sessions/latest":
            self._send_json(200, {"ok": True, **latest_session()})
            return
        if self.path == "/sessions":
            self._send_json(200, {"ok": True, **list_sessions()})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if not self._local_only() or not self._origin_allowed():
            self._send_json(403, {"ok": False, "error": "request origin not allowed"})
            return
        if self.path not in {
            "/capture",
            "/records/update",
            "/records/delete",
            "/sessions/create",
            "/sessions/activate",
        }:
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > BODY_LIMIT_BYTES:
            self._send_json(413, {"ok": False, "error": "invalid request size"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            if self.path == "/capture":
                record = append_record(payload)
                response = {"ok": True, "record": record}
            elif self.path == "/sessions/create":
                session = create_session(payload)
                response = {"ok": True, "session": session}
            elif self.path == "/sessions/activate":
                session = activate_session(payload)
                if session is None:
                    self._send_json(404, {"ok": False, "error": "没有找到这个采集"})
                    return
                response = {"ok": True, "session": session}
            elif self.path == "/records/update":
                record = update_record(payload)
                if record is None:
                    self._send_json(404, {"ok": False, "error": "record not found"})
                    return
                response = {"ok": True, "record": record}
            else:
                record = delete_record(payload)
                if record is None:
                    self._send_json(404, {"ok": False, "error": "record not found"})
                    return
                response = {"ok": True, "deleted": record}
            cleanup_tmp()
            self._send_json(200, response)
        except Exception as exc:
            self._send_json(400, {"ok": False, "error": str(exc)})


def main() -> None:
    ensure_dirs()
    cleanup_tmp()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Chinese Video Notes service listening on http://{HOST}:{PORT}")
    print(f"Notes home: {NOTES_HOME}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping service")
    finally:
        cleanup_tmp(0)
        server.server_close()


if __name__ == "__main__":
    main()
