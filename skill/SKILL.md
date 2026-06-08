---
name: chinese-video-notes
description: Use when the user asks to整理最近采集, summarize a Chinese video/webpage, generate Chinese learning notes from Bilibili/Douyin/Xiaohongshu/Chrome captures, or export recent captures to Markdown/Word. Reads the VIDEO_NOTES_HOME data directory, writes Markdown and DOCX notes, and preserves sources/timecodes while deleting temporary audio/video files.
---

# Chinese Video Notes

Turn recent Chinese web/video captures into study notes.

## When to use

Use this skill for:

- `整理最近采集`
- `用 chinese-video-notes 整理最近采集`
- `帮我整理这个视频/网页`
- `把最近采集导出成 Word`
- notes from Bilibili, Douyin, Xiaohongshu, screenshots, selected text, or Chrome captures
- especially when captures include `page_context` records from the side panel's `把当前视频加入整理` button or `video_marker` records from `保存我的笔记`

## Data locations

Preferred final-note root. `VIDEO_NOTES_HOME` overrides this location:

`~/Documents/VideoNotes`

LaunchAgent capture fallback root, used when macOS blocks background Python from Documents:

`~/Library/Application Support/ChineseVideoNotes/VideoNotes`

Subfolders:

- `inbox`: JSONL captures from the Chrome side panel
- `inbox/sessions.json`: named capture sessions and the active session
- `notes`: Markdown notes and drafts
- `exports`: Word exports
- `tmp`: temporary downloads only

Never keep source video/audio in `tmp` after processing. If a script downloads media for transcription, it must delete it in `finally` or equivalent cleanup.

## Workflow

1. Read the latest capture session:
   - Use `scripts/build_draft.py --latest` to produce a raw Markdown draft, or inspect the latest `inbox/*.jsonl` directly.
   - Check both the Documents root and the LaunchAgent fallback root.
   - Read the active named session from `inbox/sessions.json`; do not merge records from other sessions.
   - Preserve URL, title, platform, screenshots, selected text, visible transcript text, page text, and video timestamps.
2. If the user gives a video URL and the inbox does not contain enough content:
   - Use `scripts/video_transcript.py <url>` before writing the note.
   - Try platform or creator subtitles first because they are the smallest and most faithful source.
   - If subtitles are unavailable or unusable, download audio only, preferably the lowest adequate bitrate, and transcribe it locally. Do not download video frames unless the task specifically requires visual analysis.
   - A request to整理、总结或制作所选视频笔记 is standing permission to make a temporary audio-only download for transcription. Do not ask again unless installation, payment, account access, or another material risk is involved.
   - Delete temporary audio and converted segments after transcription, including on failure.
3. When recent captures include the same video/page URL, merge them into one document:
   - Treat the selected video as the authoritative source. Use creator/platform subtitles or an audio transcription as the main evidence for the video's claims and progression.
   - Reject false transcript captures such as subtitle settings, navigation text, comments, recommendations, or a visible `暂无字幕` panel. Do not treat UI text as spoken content.
   - Use page chapters, screenshots, selected text, timestamps, and user notes only to locate or clarify parts of the video. They do not replace the spoken content.
   - Use `我的笔记` or `手动笔记` as the user's own thinking, not as source claims.
   - Use the video's chapter order to preserve the original progression, but do not display timestamps by default.
   - Do not generate a complete video tutorial from screenshots, chapter names, page descriptions, or external documentation when the video itself has not been transcribed.
   - Do not use official documentation, web search, or general knowledge to fill missing parts of the selected video by default. External verification may correct a clearly identified factual issue, but it must remain a brief annotation and must never replace, expand, or rewrite what the video actually says.
   - Before drafting, make an internal evidence check: every substantive section must be supported by transcript content from its matching time range. If evidence is insufficient, continue extraction or stop and report the exact blocker instead of guessing.
4. Write the note in this fixed study-guide structure:
   - The document title is the actual video/topic title.
   - Immediately below it, write `一句话总结`.
   - After the one-sentence summary, organize the video's full content into detailed thematic sections in the same order as the video.
   - Do not display timestamps or add headings such as `视频时间线`, `时间线笔记`, or `内容纪要`, unless the user explicitly asks for time navigation.
   - Each thematic section should explain: what the concept/product is, what problem it solves, its important capabilities, how it differs from the previous approach, concrete use cases, suitable users, and important limitations or availability constraints.
   - For every tool, product, method, or workflow, prioritize an operational summary inside its matching thematic section:
     - `能做什么`: state the practical result or task it can accomplish.
     - `大概操作步骤`: summarize the main actions in execution order, from preparation through completion and verification.
     - `关键是什么`: highlight prerequisites, permissions, decisive choices, common failure points, and how to judge whether the operation succeeded.
   - Treat `能做什么`, `大概操作步骤`, and `关键是什么` as a coverage checklist, not mandatory visible headings. Weave them naturally into the explanation unless separate labels genuinely make that section easier to use.
   - Default to a tutorial voice for practical topics: explain why the reader needs the concept, walk through what to do in a sensible order, and place warnings or verification advice beside the step where they matter.
   - Write from the user's note-taking perspective, as if the user is recording useful knowledge and instructions for their future self. State the concept, action, example, or caution directly.
   - Avoid source-commentary narration such as `视频中提到`, `作者介绍了`, `视频演示了`, `这一段讲的是`, or repeated references to what the presenter did. Mention the source only when attribution is genuinely necessary to distinguish a claim, limitation, or uncertainty.
   - Do not repeat the same subsection pattern in every chapter. Use numbered steps only when sequence matters, bullets for short comparisons or lookup, and ordinary paragraphs for explanation.
   - Before finalizing, run a human-writing pass: vary sentence length, prefer direct everyday Chinese, remove slogan-like conclusions and repeated phrases such as `核心价值`, `关键是什么`, or `成功标准`, and make sure the note reads naturally aloud.
   - Keep operational steps concrete enough that the reader can understand how to start, but do not invent button names, commands, or procedures absent from the capture or verified primary sources.
   - Expand every captured chapter into a structured knowledge map. Prefer clear subheadings and concise bullets over a short generic paragraph.
   - Insert every user-authored note inside the matching thematic section, labeled `我的笔记`. Timestamps may be used internally to place notes but should not appear in the final document.
   - If multiple user notes belong to the same section, preserve and display each one separately in their original order.
   - Do not add extra sections such as `我的理解`, `待确认`, `观察框架`, `可执行清单`, `信息边界`, or `来源` unless the user explicitly asks.
5. Save Markdown to `notes`.
   - Use the capture session name as the Markdown title and filename.
6. Export Word to `exports`:
   - Use `scripts/export_docx.py <note.md>`.
   - Use the same capture session name as the Word filename.
   - For polished or important output, use the Documents skill render QA before final delivery.
7. After the Markdown note and Word export are complete and verified:
   - Delete every downloaded audio file, converted WAV file, transcription chunk, and other temporary media created for this task.
   - Scan the task workspace and temporary directories for common media extensions to confirm that no downloaded source audio or intermediate segment remains.
   - Keep only the transcript text, final Markdown, final Word export, and deliberately retained screenshots.
   - Do not report the note as complete until this cleanup check has passed.

## Writing rules

- Write like a study note, not a generic summary.
- Make it read like a useful tutorial written by a person, not an encyclopedia entry or an outline generated from a template.
- Make the final note feel self-authored: it should sound like knowledge the user has already absorbed and reorganized for personal review, not a report describing a video from the outside.
- Prefer direct phrasing such as `先准备`, `可以这样做`, `需要注意`, and `是否完成要看` over repeated narration about the video, creator, presenter, or demonstration.
- Preserve technical accuracy while using plain explanations, concrete examples, and direct transitions. Avoid forcing every idea into parallel bullet lists.
- Keep the user's own notes and selected text visible.
- Preserve every user-authored note, including short, repeated, placeholder-like, or test-looking text. Never omit a user note based on an assumption about its importance.
- Default output must contain only: title, one-sentence summary, detailed thematic knowledge sections following the video's progression, and user notes inserted into their matching sections.
- The default goal is faithful learning value, not artificial completeness. Cover the selected video's actual content first; omit unsupported detail rather than making the note look fuller.
- Give extra weight to actionable knowledge. When the source describes something the viewer can use or perform, the note must preserve what it can do, the approximate operating sequence, and the key conditions for doing it correctly.
- Never expose timestamps in the final note unless the user asks for them. Use timestamps only as hidden placement metadata.
- Do not invent claims not supported by captures/transcripts.
- Keep three evidence classes separate: video transcript, user-authored notes, and optional factual correction. Never blend them into one narrator voice.
- If transcription remains incomplete after the available subtitle and audio routes have been tried, do not publish or overwrite the final note. Keep the previous final files intact and report what failed.
- No emojis.
- No em dashes or en dashes.
- Keep source links and video timestamps in the underlying capture data, but omit them from the visible default note unless the user asks.

## Failure handling

- If Chrome captures are empty but contain a selected video URL, try extracting that video before asking the user to capture more.
- If `yt-dlp` is missing, explain that video subtitle/audio extraction needs `yt-dlp`.
- If a platform blocks extraction, try its official subtitle/API surface or the user's already-open authenticated page without reading browser credentials. If those fail, ask for a user-provided local video/audio file.
- If local transcription tools are missing, check for an existing local ASR runtime before proposing an installation. Keep downloaded media deleted if transcription cannot proceed.
- Screenshots, page text, chapters, and user notes are not an acceptable fallback for pretending that an untranscribed video has been fully summarized.
