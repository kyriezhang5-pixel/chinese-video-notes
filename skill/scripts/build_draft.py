#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


PRIMARY_HOME = Path(
    os.environ.get("VIDEO_NOTES_HOME", str(Path.home() / "Documents" / "VideoNotes"))
).expanduser()
FALLBACK_HOME = Path(
    os.environ.get(
        "VIDEO_NOTES_FALLBACK_HOME",
        str(Path.home() / "Library" / "Application Support" / "ChineseVideoNotes" / "VideoNotes"),
    )
).expanduser()


def candidate_homes() -> list[Path]:
    homes = [PRIMARY_HOME]
    if FALLBACK_HOME not in homes:
        homes.append(FALLBACK_HOME)
    return homes


def read_session_state(home: Path) -> dict | None:
    path = home / "inbox" / "sessions.json"
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return state if isinstance(state, dict) else None


def latest_session_source() -> tuple[Path | None, dict | None]:
    candidates: list[tuple[str, float, Path, dict]] = []
    for home in candidate_homes():
        state = read_session_state(home)
        if not state:
            continue
        active_id = str(state.get("active_session_id") or "")
        session = next(
            (item for item in state.get("sessions", []) if isinstance(item, dict) and item.get("id") == active_id),
            None,
        )
        if not session:
            continue
        source = home / "inbox" / str(session.get("file") or "")
        if source.exists():
            candidates.append(
                (
                    str(session.get("updated_at") or session.get("created_at") or ""),
                    source.stat().st_mtime,
                    source,
                    session,
                )
            )
    if candidates:
        _, _, source, session = max(candidates, key=lambda item: (item[0], item[1]))
        return source, session

    files = []
    for home in candidate_homes():
        files.extend((home / "inbox").glob("*.jsonl"))
        files.extend((home / "inbox" / "sessions").glob("*.jsonl"))
    files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    return (files[0], None) if files else (None, None)


def read_records(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def fmt_time(seconds) -> str:
    if seconds is None:
        return ""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return ""
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def record_text(record: dict) -> str:
    chunks = []
    if record.get("selected_text"):
        chunks.append(str(record["selected_text"]).strip())
    if record.get("notes"):
        chunks.append("补充：" + str(record["notes"]).strip())
    if record.get("transcript_text"):
        chunks.append("页面可见字幕/转录：\n" + str(record["transcript_text"]).strip()[:12000])
    if record.get("page_text") and record.get("source_type") == "page_context":
        chunks.append("页面可见文本节选：\n" + str(record["page_text"]).strip()[:8000])
    if record.get("screenshot_path"):
        chunks.append(f"截图：{record['screenshot_path']}")
    return "\n\n".join(chunk for chunk in chunks if chunk)


def session_name_from(records: list[dict], source_path: Path, session: dict | None) -> str:
    if session and session.get("name"):
        return str(session["name"]).strip()
    for record in records:
        if record.get("session_name"):
            return str(record["session_name"]).strip()
    return source_path.stem


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", value).strip(" .")
    return cleaned[:100] or "未命名采集"


def build_markdown(records: list[dict], source_path: Path, session_name: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    counts = Counter(record.get("source_type", "unknown") for record in records)
    platforms = Counter(record.get("platform", "unknown") for record in records)
    lines = [
        f"# {session_name}",
        "",
        f"生成时间：{now}",
        f"采集名称：{session_name}",
        f"来源文件：{source_path}",
        "",
        "## 采集概况",
        "",
        f"- 记录数：{len(records)}",
        f"- 类型：{', '.join(f'{k} {v}' for k, v in counts.items()) or '无'}",
        f"- 平台：{', '.join(f'{k} {v}' for k, v in platforms.items()) or '无'}",
        "",
        "## 待总结",
        "",
        "请整理为固定学习讲义格式：实际视频题目、一句话总结，随后按照视频原有顺序拆成详细的主题知识章节。不要显示时间节点。每章应梳理概念、解决的问题、核心能力、与旧方式的差异、实际用法、适用人群和限制；章节信息过薄时，可用最新一手资料核实并补充，但不能把补充内容伪装成视频逐字稿。把每一条用户笔记分别插入对应主题，标注“我的笔记”。不要添加“视频时间线”、理解、待确认、观察框架、清单或来源等额外章节。",
        "",
        "额外整理要求：凡是工具、产品、方法或工作流，要重点总结三件事：能做什么；从准备、执行到完成和验证的大概操作步骤；关键前提、权限、选择、易错点和成功标准是什么。操作步骤要按先后顺序写清楚，但不能编造采集内容或一手资料中没有的按钮、命令和流程。",
        "",
        "## 采集记录",
        "",
    ]
    for index, record in enumerate(records, start=1):
        title_value = record.get("title") or record.get("url") or "未命名来源"
        timestamp = fmt_time(record.get("video_time_seconds"))
        lines.extend(
            [
                f"### {index}. {title_value}",
                "",
                f"- 类型：{record.get('source_type', '')}",
                f"- 平台：{record.get('platform', '')}",
                f"- 时间：{record.get('created_at', '')}",
                f"- 链接：{record.get('url', '')}",
            ]
        )
        if timestamp:
            lines.append(f"- 视频时间点：{timestamp}")
        body = record_text(record)
        if body:
            lines.extend(["", body])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", action="store_true", help="Use the newest inbox JSONL file")
    parser.add_argument("--input", type=Path, help="Specific JSONL file")
    parser.add_argument("--out", type=Path, help="Markdown output path")
    args = parser.parse_args()

    session = None
    if args.input:
        source = args.input
    else:
        source, session = latest_session_source()
    if not source or not source.exists():
        searched = ", ".join(str(home / "inbox") for home in candidate_homes())
        raise SystemExit(f"No capture session found under: {searched}")
    records = read_records(source)
    session_name = session_name_from(records, source, session)
    output_home = PRIMARY_HOME if PRIMARY_HOME.exists() else source.parents[1]
    out = args.out or output_home / "notes" / f"{safe_filename(session_name)}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_markdown(records, source, session_name), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
