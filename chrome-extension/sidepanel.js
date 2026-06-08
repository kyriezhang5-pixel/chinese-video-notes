const API_BASE = "http://127.0.0.1:8765";
const ORGANIZE_COMMAND_PREFIX = "用 chinese-video-notes 整理";
const IS_PREVIEW = !globalThis.chrome?.tabs;

const els = {
  status: document.querySelector("#service-status"),
  statusWrap: document.querySelector("#service-state"),
  latest: document.querySelector("#latest-list"),
  latestCount: document.querySelector("#latest-count"),
  notePanel: document.querySelector(".note"),
  quickNote: document.querySelector("#quick-note"),
  noteCount: document.querySelector("#note-count"),
  sessionSelect: document.querySelector("#session-select"),
  newSession: document.querySelector("#new-session"),
  newSessionForm: document.querySelector("#new-session-form"),
  sessionName: document.querySelector("#session-name"),
  confirmSession: document.querySelector("#confirm-session"),
  cancelSession: document.querySelector("#cancel-session"),
  captureSelection: document.querySelector("#capture-selection"),
  capturePage: document.querySelector("#capture-page"),
  captureVideo: document.querySelector("#capture-video"),
  captureVideoNote: document.querySelector("#capture-video-note"),
  captureScreenshot: document.querySelector("#capture-screenshot"),
  saveManualNote: document.querySelector("#save-manual-note"),
  currentPageTitle: document.querySelector("#current-page-title"),
  currentPageDomain: document.querySelector("#current-page-domain"),
  copyCommand: document.querySelector("#copy-command"),
  organizeHint: document.querySelector("#organize-hint")
};

let latestItems = [];
let editingId = "";
let activeSession = null;
let isBusy = false;
let activeBusyControl = null;
let sessionsAvailable = false;
let previewSessions = [
  {
    id: "preview-session",
    name: "Codex 零基础教程",
    count: 4,
    created_at: new Date().toISOString()
  }
];

const captureControls = [
  els.captureSelection,
  els.capturePage,
  els.captureVideo,
  els.captureVideoNote,
  els.captureScreenshot,
  els.saveManualNote,
  els.quickNote
];

const previewRecords = [
  {
    id: "preview-page",
    source_type: "page_context",
    platform: "douyin",
    title: "40分钟学会 Codex！零基础终级教程",
    selected_text: "已把当前视频加入整理，页面章节和可见文字会作为学习笔记的主要素材。",
    notes: "视频内容",
    video_time_seconds: 15,
    created_at: new Date(Date.now() - 1000 * 60 * 8).toISOString()
  },
  {
    id: "preview-note",
    source_type: "video_marker",
    platform: "douyin",
    title: "40分钟学会 Codex！零基础终级教程",
    selected_text: "重点理解 Skill、插件和 MCP 的区别，以及它们如何组合成完整工作流。",
    notes: "我的时间点笔记",
    video_time_seconds: 1951,
    created_at: new Date(Date.now() - 1000 * 60 * 4).toISOString()
  },
  {
    id: "preview-shot",
    source_type: "screenshot",
    platform: "douyin",
    title: "Codex 自动化定时任务",
    selected_text: "",
    notes: "当前画面截图",
    video_time_seconds: 2222,
    created_at: new Date(Date.now() - 1000 * 60).toISOString()
  }
];

function setStatus(message, state = "success") {
  const resolvedState = typeof state === "string" ? state : state ? "error" : "success";
  els.status.textContent = message;
  els.statusWrap.classList.remove("loading", "success", "error");
  els.statusWrap.classList.add(resolvedState);
}

function syncControlState() {
  const captureDisabled = isBusy || !activeSession;
  for (const control of captureControls) {
    if (control) control.disabled = captureDisabled;
  }
  els.newSession.disabled = isBusy;
  els.sessionSelect.disabled = isBusy || !sessionsAvailable;
  els.copyCommand.disabled = isBusy || !activeSession;
  updateOrganizeCommandDisplay();
}

function currentOrganizeCommand() {
  const sessionName = activeSession?.name?.trim();
  return sessionName ? `${ORGANIZE_COMMAND_PREFIX}${sessionName}` : "";
}

function updateOrganizeCommandDisplay() {
  const command = currentOrganizeCommand();
  const code = els.copyCommand.querySelector("code");
  code.textContent = command ? `整理${activeSession.name.trim()}` : "请先新建采集";
  els.copyCommand.title = command ? `复制：${command}` : "请先新建并命名采集";
  els.organizeHint.textContent = command
    ? `在 Codex 中说：${command}`
    : "新建并命名采集后，可复制对应的整理指令。";
}

function setBusy(value, control = null) {
  activeBusyControl?.classList.remove("is-loading");
  activeBusyControl = value ? control : null;
  activeBusyControl?.classList.add("is-loading");
  isBusy = value;
  document.body.dataset.busy = value ? "true" : "false";
  syncControlState();
}

function updateNoteCount() {
  const count = els.quickNote.value.length;
  els.noteCount.textContent = `${count} / 2000`;
  els.noteCount.dataset.nearLimit = count > 1800 ? "true" : "false";
  els.notePanel?.classList.toggle("has-content", count > 0);
}

async function refreshCurrentTab() {
  if (IS_PREVIEW) {
    els.currentPageTitle.textContent = "第19集：40分钟学会 Codex！零基础终级教程";
    els.currentPageDomain.textContent = "douyin.com · 抖音";
    return;
  }

  try {
    const tab = await activeTab();
    const url = new URL(tab.url || "");
    els.currentPageTitle.textContent = tab.title || "未命名页面";
    els.currentPageDomain.textContent = `${url.hostname.replace(/^www\./, "")} · ${platformLabel(detectPlatform(tab.url))}`;
  } catch (_error) {
    els.currentPageTitle.textContent = "暂时无法读取当前页面";
    els.currentPageDomain.textContent = "切换到普通网页后重试";
  }
}

async function activeTab() {
  if (IS_PREVIEW) {
    return {
      id: 1,
      title: "第19集：40分钟学会 Codex！零基础终级教程",
      url: "https://www.douyin.com/video/preview"
    };
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("没有找到当前标签页");
  return tab;
}

function detectPlatform(url) {
  const value = (url || "").toLowerCase();
  if (value.includes("bilibili.com") || value.includes("b23.tv")) return "bilibili";
  if (value.includes("douyin.com") || value.includes("iesdouyin.com")) return "douyin";
  if (value.includes("xiaohongshu.com") || value.includes("xhslink.com")) return "xiaohongshu";
  if (value.startsWith("http://") || value.startsWith("https://")) return "web";
  return "unknown";
}

function isInjectableTab(tab) {
  return /^https?:\/\//.test(tab.url || "") || /^file:\/\//.test(tab.url || "");
}

function chromeErrorToChinese(message = "") {
  if (message.includes("Receiving end does not exist") || message.includes("Could not establish connection")) {
    return "当前页面还没有连接到插件。请刷新网页后重试。";
  }
  if (message.includes("Cannot access") || message.includes("permission") || message.includes("Cannot inject")) {
    return "这个页面不允许插件读取，请切换到普通网页、B站、小红书或抖音网页版。";
  }
  if (message.includes("No tab")) return "没有找到当前标签页。";
  return message || "页面采集失败";
}

function apiErrorToChinese(message = "") {
  if (message.includes("record not found")) return "没有找到这条采集记录，可能已经被删除。";
  if (message.includes("invalid request size")) return "这次采集内容太大，请减少页面内容或改用截图、选中文字。";
  if (message.includes("local requests only")) return "本地服务只允许本机访问。";
  if (message.includes("missing id")) return "缺少记录 ID，无法操作。";
  if (message.includes("nothing to update")) return "没有可更新的内容。";
  if (message.includes("请先新建采集")) return "请先点击“新建”并给学习项目起一个名称。";
  if (message.includes("采集名称不能为空")) return "请填写项目名称。";
  if (message.includes("没有找到这个采集")) return "没有找到这个学习项目，它可能已经不存在。";
  return message || "操作失败";
}

async function sendToContent(tab, type) {
  try {
    return await chrome.tabs.sendMessage(tab.id, { type });
  } catch (error) {
    if (!isInjectableTab(tab)) {
      throw new Error("这个页面不允许插件读取，请切换到普通网页、B站、小红书或抖音网页版。");
    }
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["content.js"]
      });
      return await chrome.tabs.sendMessage(tab.id, { type });
    } catch (retryError) {
      throw new Error(chromeErrorToChinese(retryError.message || error.message));
    }
  }
}

async function collect(type) {
  if (IS_PREVIEW) {
    const now = Math.floor(Date.now() / 1000);
    return {
      url: "https://www.douyin.com/video/preview",
      title: "第19集：40分钟学会 Codex！零基础终级教程",
      platform: "douyin",
      source_type: type === "COLLECT_SELECTION" ? "text" : type === "COLLECT_VIDEO_MARKER" ? "video_marker" : "page_context",
      selected_text: type === "COLLECT_SELECTION" ? "这是一段选中的示例文字。" : "",
      page_text: "页面文字示例",
      video_time_seconds: now % 2400,
      notes: ""
    };
  }
  const tab = await activeTab();
  const response = await sendToContent(tab, type);
  if (!response?.ok) throw new Error(chromeErrorToChinese(response?.error || "页面采集失败"));
  return response.payload;
}

async function postCapture(payload) {
  if (!activeSession) throw new Error("请先点击“新建”并给学习项目起一个名称。");
  const note = els.quickNote.value.trim();
  const body = {
    ...payload,
    notes: [payload.notes, note].filter(Boolean).join("\n")
  };

  if (IS_PREVIEW) {
    const record = {
      ...body,
      id: `preview-${Date.now()}`,
      created_at: new Date().toISOString()
    };
    latestItems.push(record);
    activeSession.count = latestItems.length;
    els.quickNote.value = "";
    updateNoteCount();
    renderLatest(latestItems);
    renderSessions(previewSessions, activeSession.id);
    await new Promise((resolve) => setTimeout(resolve, 280));
    return record;
  }

  const response = await fetch(`${API_BASE}/capture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(apiErrorToChinese(data.error || "保存失败"));
  els.quickNote.value = "";
  updateNoteCount();
  await refreshLatest();
  await refreshSessions();
  return data.record;
}

async function postRecordAction(path, payload) {
  if (IS_PREVIEW) {
    await new Promise((resolve) => setTimeout(resolve, 180));
    if (path === "/sessions/create") {
      const session = {
        id: `preview-session-${Date.now()}`,
        name: payload.name,
        count: 0,
        created_at: new Date().toISOString()
      };
      previewSessions.push(session);
      activeSession = session;
      latestItems = [];
      return { ok: true, session };
    }
    if (path === "/sessions/activate") {
      activeSession = previewSessions.find((session) => session.id === payload.id) || previewSessions[0];
      latestItems = activeSession.id === "preview-session" ? [...previewRecords] : [];
      return { ok: true, session: activeSession };
    }
    if (path === "/records/update") {
      latestItems = latestItems.map((item) => (
        item.id === payload.id ? { ...item, selected_text: payload.selected_text } : item
      ));
      return { ok: true };
    }
    if (path === "/records/delete") {
      latestItems = latestItems.filter((item) => item.id !== payload.id);
      activeSession.count = latestItems.length;
      return { ok: true };
    }
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(apiErrorToChinese(data.error || "操作失败"));
  return data;
}

async function capture(type, label, control) {
  try {
    setBusy(true, control);
    setStatus(`${label}中...`, "loading");
    const payload = await collect(type);
    if (payload.source_type === "text" && !payload.selected_text) {
      throw new Error("请先在页面上选中一段文字");
    }
    const record = await postCapture(payload);
    setStatus(`已保存${sourceTypeLabel(record.source_type)}`, "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function captureScreenshot() {
  try {
    setBusy(true, els.captureScreenshot);
    setStatus("正在保存当前画面...", "loading");
    const payload = await collect("COLLECT_PAGE_CONTEXT");
    let screenshotDataUrl = "";
    if (!IS_PREVIEW) {
      const response = await chrome.runtime.sendMessage({ type: "CAPTURE_VISIBLE_TAB" });
      if (!response?.ok) throw new Error(response?.error || "截图失败");
      screenshotDataUrl = response.dataUrl;
    }
    await postCapture({
      ...payload,
      source_type: "screenshot",
      page_text: "",
      screenshot_data_url: screenshotDataUrl
    });
    setStatus("当前截图已保存", "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function captureVideoNote() {
  try {
    setBusy(true, els.captureVideoNote);
    setStatus("正在读取当前内容...", "loading");
    const payload = await collect("COLLECT_VIDEO_FOR_SUMMARY");
    const hasVideoTime = payload.video_time_seconds !== null && payload.video_time_seconds !== undefined;
    await postCapture({
      ...payload,
      source_type: "page_context"
    });
    setStatus(`${hasVideoTime ? "视频" : "网页"}已加入当前采集`, "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function saveManualNote() {
  try {
    const note = els.quickNote.value.trim();
    if (!note) {
      els.quickNote.focus();
      throw new Error("先写一点笔记再保存");
    }
    setBusy(true, els.saveManualNote);
    setStatus("正在保存你的笔记...", "loading");
    const payload = await collect("COLLECT_PAGE_CONTEXT");
    const hasVideoTime = payload.video_time_seconds !== null && payload.video_time_seconds !== undefined;
    await postCapture({
      ...payload,
      source_type: hasVideoTime ? "video_marker" : "text",
      page_text: "",
      selected_text: note,
      notes: hasVideoTime ? "我的时间点笔记" : "我的笔记"
    });
    setStatus("笔记已保存到当前采集", "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function checkHealth() {
  if (IS_PREVIEW) {
    setStatus("本地服务已连接", "success");
    els.statusWrap.title = "预览模式";
    return true;
  }
  try {
    setStatus("正在检查本地服务", "loading");
    const response = await fetch(`${API_BASE}/health`);
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error("服务未启动");
    setStatus("本地服务已连接", "success");
    els.statusWrap.title = data.notes_home || "";
    return true;
  } catch (_error) {
    setStatus("本地服务未启动，请先启动采集服务", "error");
    return false;
  }
}

function renderSessions(sessions, activeSessionId) {
  els.sessionSelect.innerHTML = "";
  sessionsAvailable = Boolean(sessions?.length);
  if (!sessionsAvailable) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "还没有学习项目，请先新建";
    els.sessionSelect.append(option);
    activeSession = null;
    syncControlState();
    return;
  }

  for (const session of sessions) {
    const option = document.createElement("option");
    option.value = session.id;
    option.textContent = `${session.name} · ${session.count || 0} 条`;
    option.selected = session.id === activeSessionId;
    els.sessionSelect.append(option);
  }
  activeSession = sessions.find((item) => item.id === activeSessionId) || sessions[0];
  els.sessionSelect.value = activeSession.id;
  syncControlState();
  updateLatestCount();
}

async function refreshSessions() {
  if (IS_PREVIEW) {
    renderSessions(previewSessions, activeSession?.id || previewSessions[0]?.id);
    return { sessions: previewSessions, active_session_id: activeSession?.id };
  }
  try {
    const response = await fetch(`${API_BASE}/sessions`);
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "读取采集失败");
    renderSessions(data.sessions, data.active_session_id);
    return data;
  } catch (error) {
    activeSession = null;
    sessionsAvailable = false;
    syncControlState();
    setStatus(apiErrorToChinese(error.message), "error");
    return null;
  }
}

function showNewSessionForm() {
  els.newSessionForm.hidden = false;
  els.newSession.setAttribute("aria-expanded", "true");
  els.sessionName.value = "";
  els.sessionName.focus();
}

function hideNewSessionForm() {
  els.newSessionForm.hidden = true;
  els.newSession.setAttribute("aria-expanded", "false");
  els.sessionName.value = "";
}

async function createNewSession(event) {
  event.preventDefault();
  const name = els.sessionName.value.trim();
  if (!name) {
    setStatus("请填写项目名称", "error");
    els.sessionName.focus();
    return;
  }
  try {
    setBusy(true, els.confirmSession);
    setStatus("正在创建学习项目...", "loading");
    const data = await postRecordAction("/sessions/create", { name });
    hideNewSessionForm();
    activeSession = data.session;
    await refreshSessions();
    await refreshLatest();
    setStatus(`已创建：${data.session.name}`, "success");
  } catch (error) {
    setStatus(apiErrorToChinese(error.message), "error");
  } finally {
    setBusy(false);
  }
}

async function switchSession() {
  const sessionId = els.sessionSelect.value;
  if (!sessionId || sessionId === activeSession?.id) return;
  try {
    setBusy(true);
    setStatus("正在切换学习项目...", "loading");
    const data = await postRecordAction("/sessions/activate", { id: sessionId });
    activeSession = data.session;
    editingId = "";
    await refreshSessions();
    await refreshLatest();
    setStatus(`当前采集：${data.session.name}`, "success");
  } catch (error) {
    setStatus(apiErrorToChinese(error.message), "error");
  } finally {
    setBusy(false);
  }
}

function updateLatestCount() {
  const count = activeSession?.count ?? latestItems.length;
  els.latestCount.textContent = `${count || 0} 条`;
}

function renderEmptyState() {
  els.latest.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "empty-state";
  const mark = document.createElement("span");
  mark.setAttribute("aria-hidden", "true");
  mark.textContent = activeSession ? "记" : "新";
  const title = document.createElement("strong");
  title.textContent = activeSession ? "还没有保存内容" : "先新建一个学习项目";
  const description = document.createElement("p");
  description.textContent = activeSession
    ? "从上方加入当前视频、网页或随手笔记。"
    : "每个项目会独立保存素材和笔记。";
  empty.append(mark, title, description);
  els.latest.append(empty);
}

function renderLatest(items) {
  latestItems = items || [];
  updateLatestCount();
  if (!latestItems.length) {
    renderEmptyState();
    return;
  }

  els.latest.innerHTML = "";
  for (const [index, item] of latestItems.slice(-5).reverse().entries()) {
    const card = document.createElement("article");
    card.className = "latest-item";
    card.dataset.recordId = item.id;
    card.style.setProperty("--record-index", index);

    const kind = document.createElement("div");
    kind.className = "record-kind";
    kind.dataset.kind = item.source_type || "unknown";
    kind.setAttribute("aria-hidden", "true");
    kind.textContent = recordKindCharacter(item);

    const body = document.createElement("div");
    body.className = "record-body";

    const heading = document.createElement("div");
    heading.className = "record-heading";
    const title = document.createElement("strong");
    title.textContent = recordTitle(item);
    const date = document.createElement("span");
    date.textContent = formatRecordDate(item.created_at);
    heading.append(title, date);

    const meta = document.createElement("div");
    meta.className = "record-meta";
    for (const label of recordMetaLabels(item)) {
      const chip = document.createElement("span");
      chip.textContent = label;
      meta.append(chip);
    }

    const source = document.createElement("div");
    source.className = "record-source";
    source.title = item.title || item.url || "";
    source.textContent = item.title || item.url || "未识别来源";

    const previewSource = item.selected_text || item.notes || item.url || "";
    body.append(heading, meta, source);

    if (item.id === editingId) {
      const editor = document.createElement("textarea");
      editor.className = "record-editor";
      editor.rows = 5;
      editor.value = previewSource;
      editor.setAttribute("aria-label", "编辑采集内容");
      const editControls = document.createElement("div");
      editControls.className = "record-controls";

      const saveButton = makeSmallButton("保存修改", "primary-button", () => updateRecord(item, editor.value));
      const cancelButton = makeSmallButton("取消", "", () => {
        editingId = "";
        renderLatest(latestItems);
      });
      editControls.append(saveButton, cancelButton);
      body.append(editor, editControls);
      requestAnimationFrame(() => editor.focus());
    } else {
      if (previewSource) {
        const preview = document.createElement("p");
        preview.className = "record-preview";
        preview.textContent = previewSource;
        body.append(preview);
      }
      const controls = document.createElement("div");
      controls.className = "record-controls";
      const editButton = makeSmallButton("编辑", "", () => {
        editingId = item.id;
        renderLatest(latestItems);
      });
      const deleteButton = makeSmallButton("删除", "danger-button", () => deleteRecord(item));
      controls.append(editButton, deleteButton);
      body.append(controls);
    }

    card.append(kind, body);
    els.latest.append(card);
  }
}

function makeSmallButton(label, extraClass, handler) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `small-button ${extraClass}`.trim();
  button.textContent = label;
  button.addEventListener("click", handler);
  return button;
}

function recordKindCharacter(item) {
  if (item.source_type === "screenshot") return "图";
  if (item.source_type === "transcript") return "字";
  if (item.source_type === "video_marker") return "记";
  if (item.source_type === "text") return /我的.*笔记|手动笔记/.test(item.notes || "") ? "记" : "摘";
  if (item.source_type === "page_context") return item.video_time_seconds != null ? "视" : "页";
  return "录";
}

function recordTitle(item) {
  if (item.source_type === "screenshot") return "当前画面截图";
  if (item.source_type === "transcript") return "视频转录";
  if (item.source_type === "video_marker") {
    return /我的.*笔记|手动笔记/.test(item.notes || "") ? "我的时间点笔记" : "视频时间点";
  }
  if (item.source_type === "text") {
    return /我的.*笔记|手动笔记/.test(item.notes || "") ? "我的笔记" : "文字摘录";
  }
  if (item.source_type === "page_context") {
    return item.video_time_seconds != null ? "待整理视频" : "待整理网页";
  }
  return "采集内容";
}

function recordMetaLabels(item) {
  const labels = [platformLabel(item.platform), sourceTypeLabel(item.source_type)];
  if (item.video_time_seconds != null) labels.push(formatVideoTime(item.video_time_seconds));
  return labels;
}

function sourceTypeLabel(value) {
  return {
    text: "文字",
    screenshot: "截图",
    video_marker: "时间点笔记",
    page_context: "主要素材",
    transcript: "转录"
  }[value] || "记录";
}

function platformLabel(value) {
  return {
    bilibili: "B站",
    douyin: "抖音",
    xiaohongshu: "小红书",
    web: "网页",
    unknown: "未知来源"
  }[value] || "网页";
}

function formatVideoTime(seconds) {
  const total = Math.max(0, Number(seconds) || 0);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = Math.floor(total % 60);
  if (hours) return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

function formatRecordDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
  }
  return date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

async function updateRecord(item, value) {
  try {
    const text = value.trim();
    if (!text) throw new Error("内容不能为空");
    setBusy(true);
    setStatus("正在更新记录...", "loading");
    await postRecordAction("/records/update", {
      id: item.id,
      selected_text: text
    });
    editingId = "";
    await refreshLatest();
    setStatus("记录已更新", "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function deleteRecord(item) {
  try {
    const title = item.title || item.selected_text || item.id;
    if (!confirm(`删除这条采集？\n${title}`)) return;
    setBusy(true);
    setStatus("正在删除记录...", "loading");
    await postRecordAction("/records/delete", { id: item.id });
    if (editingId === item.id) editingId = "";
    await refreshLatest();
    await refreshSessions();
    setStatus("记录已删除", "success");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
  }
}

async function refreshLatest() {
  if (IS_PREVIEW) {
    renderLatest(latestItems);
    return;
  }
  try {
    const response = await fetch(`${API_BASE}/sessions/latest`);
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || "读取记录失败");
    if (data.session) activeSession = data.session;
    renderLatest(data.recent);
  } catch (_error) {
    renderLatest([]);
  }
}

async function copyOrganizeCommand() {
  const command = currentOrganizeCommand();
  if (!command) {
    setStatus("请先新建并命名采集", "error");
    return;
  }
  try {
    await navigator.clipboard.writeText(command);
    setStatus("整理指令已复制，可以粘贴到 Codex", "success");
    const code = els.copyCommand.querySelector("code");
    code.textContent = "已复制";
    setTimeout(() => {
      updateOrganizeCommandDisplay();
    }, 1400);
  } catch (_error) {
    setStatus(`请复制这句话：${command}`, "error");
  }
}

function bindEvents() {
  els.newSession.setAttribute("aria-expanded", "false");
  els.newSession.addEventListener("click", () => {
    if (els.newSessionForm.hidden) showNewSessionForm();
    else hideNewSessionForm();
  });
  els.newSessionForm.addEventListener("submit", createNewSession);
  els.cancelSession.addEventListener("click", hideNewSessionForm);
  els.sessionSelect.addEventListener("change", switchSession);
  els.captureSelection.addEventListener("click", () => capture("COLLECT_SELECTION", "正在保存摘录", els.captureSelection));
  els.capturePage.addEventListener("click", () => capture("COLLECT_PAGE_CONTEXT", "正在保存整页文字", els.capturePage));
  els.captureVideo.addEventListener("click", () => capture("COLLECT_VIDEO_MARKER", "正在记录时间点", els.captureVideo));
  els.captureVideoNote.addEventListener("click", captureVideoNote);
  els.captureScreenshot.addEventListener("click", captureScreenshot);
  els.saveManualNote.addEventListener("click", saveManualNote);
  els.copyCommand.addEventListener("click", copyOrganizeCommand);
  els.quickNote.addEventListener("input", updateNoteCount);
  els.quickNote.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      if (!els.saveManualNote.disabled) saveManualNote();
    }
  });
}

function initializeMotion() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const shell = document.querySelector(".app-shell");
  if (!shell || !matchMedia("(pointer: fine)").matches) return;

  let frame = 0;
  shell.addEventListener("pointermove", (event) => {
    if (frame) cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const x = (event.clientX / window.innerWidth - 0.5) * 8;
      const y = (event.clientY / window.innerHeight - 0.5) * 6;
      shell.style.setProperty("--scene-x", `${x.toFixed(2)}px`);
      shell.style.setProperty("--scene-y", `${y.toFixed(2)}px`);
      shell.style.setProperty("--light-x", `${(event.clientX / window.innerWidth) * 100}%`);
      shell.style.setProperty("--light-y", `${(event.clientY / window.innerHeight) * 100}%`);
      frame = 0;
    });
  });

  shell.addEventListener("pointerleave", () => {
    shell.style.setProperty("--scene-x", "0px");
    shell.style.setProperty("--scene-y", "0px");
    shell.style.setProperty("--light-x", "50%");
    shell.style.setProperty("--light-y", "25%");
  });
}

async function initialize() {
  bindEvents();
  initializeMotion();
  updateNoteCount();
  syncControlState();
  await refreshCurrentTab();

  if (IS_PREVIEW) {
    latestItems = [...previewRecords];
    activeSession = previewSessions[0];
    renderSessions(previewSessions, activeSession.id);
    renderLatest(latestItems);
    await checkHealth();
    return;
  }

  const ok = await checkHealth();
  if (!ok) return;
  await refreshSessions();
  await refreshLatest();
}

initialize();
