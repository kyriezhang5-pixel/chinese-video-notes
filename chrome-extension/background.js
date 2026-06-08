chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "CAPTURE_VISIBLE_TAB") {
    return false;
  }

  chrome.tabs.captureVisibleTab(
    sender.tab?.windowId,
    { format: "jpeg", quality: 65 },
    (dataUrl) => {
      if (chrome.runtime.lastError) {
        sendResponse({ ok: false, error: chrome.runtime.lastError.message });
        return;
      }
      sendResponse({ ok: true, dataUrl });
    }
  );
  return true;
});
