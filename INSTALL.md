# 安装说明

本项目包含三个部分，缺一不可：

1. Chrome 扩展负责边看边采集。
2. 本地服务负责把采集内容保存到电脑。
3. Codex Skill 负责读取采集内容并整理、导出。

## 环境要求

- Chrome 或 Chromium 浏览器
- Python 3.10 或更高版本
- 已安装 Codex，并存在 `~/.codex` 目录
- macOS、Windows 或 Linux

## macOS 一键安装

下载仓库并进入项目目录后运行：

```bash
bash install.sh
```

脚本会完成：

- 安装 `python-docx`
- 将 Skill 安装到 `~/.codex/skills/chinese-video-notes`
- 注册并启动 macOS LaunchAgent
- 创建默认数据目录
- 生成 Chrome 扩展 ZIP

检查服务：

```bash
curl http://127.0.0.1:8765/health
```

看到 `"ok": true` 即表示服务正常。

## Windows 与 Linux

先安装 Python 依赖：

```bash
python3 -m pip install --user -r requirements.txt
```

将 `skill` 文件夹复制到：

```text
~/.codex/skills/chinese-video-notes
```

Linux 可以直接运行：

```bash
bash service/start_service.sh
```

Windows PowerShell 可以运行：

```powershell
python .\service\video_notes_service.py
```

请保持这个终端窗口运行。需要自动启动时，可以把相同命令加入系统的登录启动项。

## 安装 Chrome 扩展

1. 打开 `chrome://extensions`。
2. 开启右上角的“开发者模式”。
3. 点击“加载已解压的扩展程序”。
4. 选择仓库中的 `chrome-extension` 文件夹。

也可以下载 `dist/chinese-video-notes-extension-v1.0.0.zip`，先解压，再选择解压后的文件夹。Chrome 不能直接加载 ZIP。

扩展安装后，点击工具栏中的“中文边看边记”，侧边栏顶部应显示“本地服务已连接”。

## 第一次使用

1. 在侧边栏点击“新建”，输入学习项目名称。
2. 打开要学习的视频或网页。
3. 点击“加入当前视频或网页”。
4. 看到重点时，在“我的笔记”中记录并保存。
5. 看完后点击底部指令，将它粘贴到 Codex。

示例：

```text
用 chinese-video-notes 整理 Codex 零基础教程
```

Skill 会在默认目录生成：

```text
~/Documents/VideoNotes/notes      Markdown 笔记
~/Documents/VideoNotes/exports    Word 文档
```

macOS 自动启动服务默认把原始采集保存到：

```text
~/Library/Application Support/ChineseVideoNotes/VideoNotes
```

Skill 会同时检查这个目录和 `~/Documents/VideoNotes`。

## 自定义数据目录

启动服务和使用 Skill 前设置同一个环境变量：

```bash
export VIDEO_NOTES_HOME="$HOME/Documents/MyVideoNotes"
```

macOS 一键安装时可以这样指定：

```bash
VIDEO_NOTES_HOME="$HOME/Documents/MyVideoNotes" bash install.sh
```

## 可选的视频转写能力

页面没有在线字幕时，Skill 可以临时下载低码率音频并在本地转写。需要自行安装：

```bash
brew install yt-dlp ffmpeg
python3 -m pip install openai-whisper
```

Apple Silicon 也可以使用 `mlx-whisper`。这些依赖不是基础采集和 Word 导出的必需项。

## 更新与卸载

更新：

```bash
git pull
bash install.sh
```

macOS 卸载自动启动服务：

```bash
bash service/uninstall_launch_agent.sh
```

删除 Skill：

```bash
rm -rf "${CODEX_HOME:-$HOME/.codex}/skills/chinese-video-notes"
```

数据目录不会在卸载时自动删除，避免误删个人笔记。

## 常见问题

### 侧边栏显示“本地服务未启动”

确认 `http://127.0.0.1:8765/health` 可以访问。macOS 日志位于：

```text
/tmp/chinese-video-notes.out.log
/tmp/chinese-video-notes.err.log
```

### 刚安装扩展后无法读取已经打开的网页

刷新网页后重试。Chrome 不允许扩展读取 `chrome://`、扩展商店等内部页面。

### Word 导出提示缺少 `docx`

运行：

```bash
python3 -m pip install --user python-docx
```

### Codex 没有触发 Skill

确认文件存在：

```text
~/.codex/skills/chinese-video-notes/SKILL.md
```

重新启动 Codex，然后明确输入：

```text
用 chinese-video-notes 整理最近采集
```
