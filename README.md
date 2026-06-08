# Chinese Video Notes

一套本地优先的中文视频与网页边看边记工具，由 Chrome 扩展、本地采集服务和 Codex Skill 组成。

打开 B 站、抖音、小红书或普通网页后，可以在 Chrome 侧边栏中：

- 将当前视频或网页加入一个独立学习项目
- 保存选中文字、整页文字、视频时间点和当前截图
- 记录自己的即时笔记，并保留对应页面和视频位置
- 在 Codex 中用一句话整理为 Markdown 学习笔记和 Word 文档

## 工作方式

```text
Chrome 扩展
    ↓ 只访问 127.0.0.1:8765
本地 Python 采集服务
    ↓ 保存 JSONL、截图与会话信息
~/Documents/VideoNotes
    ↓
chinese-video-notes Skill
    ↓
Markdown 笔记 + DOCX 导出
```

所有采集内容默认只保存在本机。服务仅监听 `127.0.0.1`，并拒绝普通网页来源的跨域写入。

## 快速安装

完整步骤见 [INSTALL.md](INSTALL.md)。

macOS 用户可以在项目目录运行：

```bash
bash install.sh
```

然后在 Chrome 的 `chrome://extensions` 页面开启开发者模式，加载 `chrome-extension` 文件夹，或解压 `dist/chinese-video-notes-extension-v1.0.0.zip` 后加载。

安装完成后，在 Codex 中说：

```text
用 chinese-video-notes 整理最近采集
```

也可以指定侧边栏中的项目名称：

```text
用 chinese-video-notes 整理 Codex 零基础教程
```

## 仓库结构

```text
chrome-extension/  Chrome Manifest V3 扩展
service/           本地采集服务与自动启动脚本
skill/             可安装到 Codex 的 chinese-video-notes Skill
scripts/           安装与打包脚本
tests/             核心端到端测试
dist/              可直接下载和解压的扩展包
```

## 可选能力

基础采集与整理只需要 Python 3 和 `python-docx`。当网页没有可用字幕、需要从视频音频转写时，还需要：

- `yt-dlp`
- `ffmpeg`
- `whisper`、`mlx-whisper` 或兼容的本地 FunASR 环境

扩展不会上传浏览历史、采集内容、截图或笔记。视频音频只在明确需要转写时临时下载，处理结束后会清理。

## 开发与验证

```bash
python3 -m pip install -r requirements.txt
python3 tests/test_core.py
bash scripts/package_extension.sh
```

## License

[MIT](LICENSE)
