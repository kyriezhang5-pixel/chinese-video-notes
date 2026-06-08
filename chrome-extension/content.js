function detectPlatform(url) {
  const value = (url || "").toLowerCase();
  if (value.includes("bilibili.com") || value.includes("b23.tv")) return "bilibili";
  if (value.includes("douyin.com") || value.includes("iesdouyin.com")) return "douyin";
  if (value.includes("xiaohongshu.com") || value.includes("xhslink.com")) return "xiaohongshu";
  if (value.startsWith("http://") || value.startsWith("https://")) return "web";
  return "unknown";
}

function compactText(text, limit = 50000) {
  return (text || "").replace(/\s+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim().slice(0, limit);
}

function currentVideo() {
  const videos = Array.from(document.querySelectorAll("video"));
  if (!videos.length) return null;
  const active = videos.find((video) => !video.paused && !video.ended) || videos[0];
  return {
    currentTime: Number.isFinite(active.currentTime) ? Math.round(active.currentTime) : null,
    duration: Number.isFinite(active.duration) ? Math.round(active.duration) : null,
    paused: Boolean(active.paused)
  };
}

function visibleTextFromSelectors(selectors, limit = 30000) {
  const parts = [];
  for (const selector of selectors) {
    for (const el of document.querySelectorAll(selector)) {
      const text = compactText(el.innerText || el.textContent || "", 2000);
      if (text) parts.push(text);
    }
  }
  return compactText([...new Set(parts)].join("\n"), limit);
}

function collectTranscriptText() {
  const youtubeTranscript = visibleTextFromSelectors([
    "ytd-transcript-segment-renderer",
    "ytd-transcript-segment-list-renderer",
    "ytd-engagement-panel-section-list-renderer[target-id='engagement-panel-searchable-transcript']",
    "[id='segments-container']"
  ]);
  if (youtubeTranscript) return youtubeTranscript;

  const visibleCaptions = visibleTextFromSelectors([
    ".ytp-caption-segment",
    ".caption-window",
    ".bpx-player-subtitle-wrap",
    ".bpx-player-subtitle-panel-text",
    "[class*='subtitle']",
    "[class*='caption']"
  ], 12000);
  return visibleCaptions;
}

function collectBase() {
  const video = currentVideo();
  return {
    url: location.href,
    title: document.title || "",
    platform: detectPlatform(location.href),
    selected_text: compactText(String(window.getSelection?.() || ""), 20000),
    page_text: compactText(document.body?.innerText || "", 50000),
    video_time_seconds: video?.currentTime ?? null,
    notes: video
      ? `视频时间：${video.currentTime} 秒；总时长：${video.duration ?? "未知"} 秒；状态：${video.paused ? "暂停" : "播放中"}`
      : ""
  };
}

function collectVideoForSummary() {
  const base = collectBase();
  const transcriptText = collectTranscriptText();
  const hasVideo = base.video_time_seconds !== null && base.video_time_seconds !== undefined;
  return {
    ...base,
    source_type: "page_context",
    selected_text: compactText([
      hasVideo ? "已把当前视频加入整理。" : "已把当前页面加入整理。",
      transcriptText ? "页面里检测到可见字幕或转录，已一起保存。" : "页面里没有检测到可见字幕或转录，整理时会尝试用页面文字或音频转写补足。",
      base.selected_text ? `选中文字：${base.selected_text}` : ""
    ].filter(Boolean).join("\n"), 20000),
    transcript_text: transcriptText,
    notes: compactText([
      base.notes,
      "用途：后续生成整条视频/页面纪要，并把我的时间点笔记放回对应位置。"
    ].filter(Boolean).join("\n"), 20000)
  };
}

if (!window.__CHINESE_VIDEO_NOTES_LISTENER__) {
  window.__CHINESE_VIDEO_NOTES_LISTENER__ = true;
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || !message.type) return false;

    if (message.type === "COLLECT_SELECTION") {
      const base = collectBase();
      sendResponse({
        ok: true,
        payload: {
          ...base,
          source_type: "text",
          page_text: ""
        }
      });
      return true;
    }

    if (message.type === "COLLECT_PAGE_CONTEXT") {
      sendResponse({
        ok: true,
        payload: {
          ...collectBase(),
          source_type: "page_context"
        }
      });
      return true;
    }

    if (message.type === "COLLECT_VIDEO_MARKER") {
      const base = collectBase();
      sendResponse({
        ok: true,
        payload: {
          ...base,
          source_type: "video_marker",
          page_text: "",
          selected_text: base.selected_text || `记录当前视频时间点：${base.video_time_seconds ?? "未知"} 秒`
        }
      });
      return true;
    }

    if (message.type === "COLLECT_VIDEO_FOR_SUMMARY") {
      sendResponse({
        ok: true,
        payload: collectVideoForSummary()
      });
      return true;
    }

    return false;
  });
}
