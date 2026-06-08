#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path


NOTES_HOME = Path(
    os.environ.get("VIDEO_NOTES_HOME", str(Path.home() / "Documents" / "VideoNotes"))
).expanduser()
LANG_PREFS = ("zh-Hans", "zh-CN", "zh", "zh-Hant", "en")
GPT_SOVITS_ROOT = Path(
    os.environ.get("GPT_SOVITS_ROOT", str(Path.home() / "Desktop" / "GPT-SoVITS"))
).expanduser()


def require(command: str) -> str:
    path = shutil.which(command)
    if not path:
        raise SystemExit(f"Missing dependency: {command}")
    return path


def run_json(command: list[str]) -> dict:
    proc = subprocess.run(command, check=True, text=True, capture_output=True)
    return json.loads(proc.stdout)


def choose_subtitle(info: dict) -> dict | None:
    buckets = [info.get("subtitles") or {}, info.get("automatic_captions") or {}]
    for lang in LANG_PREFS:
        for bucket in buckets:
            entries = bucket.get(lang) or []
            if entries:
                return entries[0]
    for bucket in buckets:
        for entries in bucket.values():
            if entries:
                return entries[0]
    return None


def strip_subtitle(text: str) -> str:
    text = re.sub(r"WEBVTT.*?\n", "", text, flags=re.S)
    text = re.sub(r"\d\d:\d\d:\d\d[.,]\d+\s+-->\s+\d\d:\d\d:\d\d[.,]\d+.*", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    lines = []
    seen = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.isdigit() or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return "\n".join(lines)


def fetch_subtitle(url: str) -> str:
    with urllib.request.urlopen(url, timeout=20) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return strip_subtitle(raw)


def format_time(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def chapter_ranges(info: dict, max_chunk_seconds: int = 600) -> list[tuple[float, float, str]]:
    duration = float(info.get("duration") or 0)
    chapters = info.get("chapters") or []
    ranges = []
    for chapter in chapters:
        start = float(chapter.get("start_time") or 0)
        end = float(chapter.get("end_time") or duration)
        if end > start:
            ranges.append((start, end, chapter.get("title") or "视频内容"))
    if ranges:
        return ranges
    if duration <= 0:
        return [(0, max_chunk_seconds, "视频内容")]
    count = max(1, math.ceil(duration / max_chunk_seconds))
    return [
        (
            index * max_chunk_seconds,
            min(duration, (index + 1) * max_chunk_seconds),
            f"第 {index + 1} 段",
        )
        for index in range(count)
    ]


def transcribe_with_gpt_sovits(audio_path: Path, tmp_dir: Path, info: dict) -> str | None:
    runtime_python = GPT_SOVITS_ROOT / "runtime/bin/python"
    script = GPT_SOVITS_ROOT / "tools/asr/funasr_asr.py"
    model = (
        GPT_SOVITS_ROOT
        / "tools/asr/models/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch/model.pt"
    )
    ffmpeg = shutil.which("ffmpeg")
    if not (runtime_python.exists() and script.exists() and model.exists() and ffmpeg):
        return None

    segment_dir = tmp_dir / "segments"
    result_dir = tmp_dir / "asr"
    segment_dir.mkdir()
    result_dir.mkdir()
    ranges = chapter_ranges(info)
    for index, (start, end, _) in enumerate(ranges):
        segment_path = segment_dir / f"{index:03d}.wav"
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(start),
                "-t",
                str(end - start),
                "-i",
                str(audio_path),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(segment_path),
            ],
            check=True,
        )

    subprocess.run(
        [
            str(runtime_python),
            str(script),
            "-i",
            str(segment_dir),
            "-o",
            str(result_dir),
            "-l",
            "zh",
        ],
        cwd=GPT_SOVITS_ROOT,
        check=True,
    )
    result_file = result_dir / f"{segment_dir.name}.list"
    if not result_file.exists():
        return None
    texts = {}
    for line in result_file.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            texts[Path(parts[0]).stem] = parts[3].strip()
    blocks = []
    for index, (start, end, title) in enumerate(ranges):
        text = texts.get(f"{index:03d}", "")
        if text:
            blocks.extend(
                [
                    f"### {format_time(start)} - {format_time(end)} {title}",
                    "",
                    text,
                    "",
                ]
            )
    return "\n".join(blocks).strip() or None


def transcribe_with_local_tool(audio_path: Path, out_dir: Path) -> str:
    whisper = shutil.which("whisper")
    mlx = shutil.which("mlx-whisper")
    if whisper:
        subprocess.run(
            [whisper, str(audio_path), "--model", "small", "--language", "Chinese", "--output_dir", str(out_dir), "--output_format", "txt"],
            check=True,
        )
        txt_files = sorted(out_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        if txt_files:
            return txt_files[0].read_text(encoding="utf-8", errors="replace")
    if mlx:
        proc = subprocess.run([mlx, str(audio_path), "--model", "mlx-community/whisper-small"], check=True, text=True, capture_output=True)
        return proc.stdout
    raise SystemExit("No local transcription command found. Install whisper or mlx-whisper, or capture subtitles/text instead.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--allow-audio", action="store_true", help="Allow temporary audio download when no online subtitles exist")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    yt_dlp = require("yt-dlp")
    info = run_json([yt_dlp, "--dump-single-json", "--skip-download", "--no-warnings", args.url])
    title = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", info.get("title") or "video").strip("-")[:80]
    out = args.out or NOTES_HOME / "notes" / f"transcript-{title}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    subtitle = choose_subtitle(info)
    if subtitle and subtitle.get("url"):
        transcript = fetch_subtitle(subtitle["url"])
        source = "online subtitles"
    elif args.allow_audio:
        tmp_root = NOTES_HOME / "tmp"
        tmp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=tmp_root) as tmp:
            tmp_dir = Path(tmp)
            audio_tpl = str(tmp_dir / "audio.%(ext)s")
            subprocess.run(
                [
                    yt_dlp,
                    "-f",
                    "worstaudio[ext=m4a]/worstaudio",
                    "-x",
                    "--audio-format",
                    "m4a",
                    "-o",
                    audio_tpl,
                    args.url,
                ],
                check=True,
            )
            audio_files = list(tmp_dir.glob("audio.*"))
            if not audio_files:
                raise SystemExit("Audio download failed")
            transcript = transcribe_with_gpt_sovits(audio_files[0], tmp_dir, info)
            if transcript:
                source = "temporary low-bitrate audio transcription with local FunASR"
            else:
                transcript = transcribe_with_local_tool(audio_files[0], tmp_dir)
                source = "temporary audio transcription"
    else:
        raise SystemExit("No online subtitles found. Re-run with --allow-audio to allow temporary audio download and local transcription.")

    text = "\n".join(
        [
            f"# {info.get('title') or '视频转录'}",
            "",
            f"- 链接：{args.url}",
            f"- 来源：{source}",
            f"- 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
            "",
            "## 转录",
            "",
            transcript.strip(),
            "",
        ]
    )
    out.write_text(text, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
