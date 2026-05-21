// Background service worker
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "open_popup") {
    chrome.action.openPopup?.();
  }
});

chrome.runtime.onInstalled.addListener(() => {
  console.log("ContractGuard AI installed");
});
