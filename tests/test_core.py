#!/usr/bin/env python3
from __future__ import annotations

import base64
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def import_service(notes_home: Path):
    os.environ["VIDEO_NOTES_HOME"] = str(notes_home)
    path = ROOT / "service" / "video_notes_service.py"
    spec = importlib.util.spec_from_file_location("video_notes_service", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    module.NOTES_HOME = notes_home
    return module


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        notes_home = Path(tmp) / "VideoNotes"
        service = import_service(notes_home)
        assert service.is_allowed_origin("")
        assert service.is_allowed_origin("chrome-extension://test-extension")
        assert not service.is_allowed_origin("https://example.com")

        service.ensure_dirs()
        first_session = service.create_session({"name": "测试视频学习"})

        tiny_png = base64.b64encode(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                "1f15c4890000000a49444154789c636000000200015d0b2a0000000000"
                "49454e44ae426082"
            )
        ).decode("ascii")

        text_record = service.append_record(
            {
                "source_type": "text",
                "url": "https://www.bilibili.com/video/BVtest",
                "title": "测试视频",
                "selected_text": "这是一条测试摘录",
            }
        )
        screenshot = service.append_record(
            {
                "source_type": "screenshot",
                "url": "https://www.xiaohongshu.com/explore/test",
                "title": "测试图文",
                "screenshot_data_url": f"data:image/png;base64,{tiny_png}",
            }
        )
        assert Path(screenshot["screenshot_path"]).exists()

        updated = service.update_record(
            {
                "id": text_record["id"],
                "selected_text": "这是一条编辑后的测试摘录",
            }
        )
        assert updated and updated["selected_text"] == "这是一条编辑后的测试摘录"

        deleted = service.delete_record({"id": screenshot["id"]})
        assert deleted and deleted["id"] == screenshot["id"]
        assert not Path(screenshot["screenshot_path"]).exists()

        second_session = service.create_session({"name": "另一场采集"})
        service.append_record(
            {
                "source_type": "text",
                "url": "https://example.com/second",
                "title": "第二场内容",
                "selected_text": "这条内容只属于第二场采集",
            }
        )
        latest = service.latest_session()
        assert latest["count"] == 1
        assert latest["session"]["id"] == second_session["id"]

        activated = service.activate_session({"id": first_session["id"]})
        assert activated and activated["name"] == "测试视频学习"
        latest = service.latest_session()
        assert latest["count"] == 1
        assert latest["recent"][0]["platform"] == "bilibili"

        env = {
            **os.environ,
            "VIDEO_NOTES_HOME": str(notes_home),
            "VIDEO_NOTES_FALLBACK_HOME": str(Path(tmp) / "NoFallback"),
        }
        build_script = ROOT / "skill" / "scripts" / "build_draft.py"
        proc = subprocess.run(
            [PYTHON, str(build_script), "--latest"],
            check=True,
            text=True,
            capture_output=True,
            env=env,
        )
        draft = Path(proc.stdout.strip())
        text = draft.read_text(encoding="utf-8")
        assert draft.name == "测试视频学习.md"
        assert text.startswith("# 测试视频学习")
        assert "这是一条编辑后的测试摘录" in text
        assert "这条内容只属于第二场采集" not in text
        assert screenshot["screenshot_path"] not in text

        export_script = ROOT / "skill" / "scripts" / "export_docx.py"
        proc = subprocess.run(
            [PYTHON, str(export_script), str(draft)],
            check=True,
            text=True,
            capture_output=True,
            env=env,
        )
        exported = Path(proc.stdout.strip())
        assert exported.exists()
        assert exported.name == "测试视频学习.docx"

    print("core tests passed")


if __name__ == "__main__":
    main()
