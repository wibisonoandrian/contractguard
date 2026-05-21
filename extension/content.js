// Content script — auto-inject risk badge on Etherscan-family pages
(async function () {
  const match = window.location.pathname.match(/\/address\/(0x[a-fA-F0-9]{40})/i);
  if (!match) return;
  const address = match[1].toLowerCase();
  const host = window.location.hostname;
  const chainMap = {
    "etherscan.io": "ethereum",
    "bscscan.com": "bsc",
    "basescan.org": "base",
    "arbiscan.io": "arbitrum",
    "polygonscan.com": "polygon",
  };
  const chain = chainMap[host];
  if (!chain) return;

  // Inject placeholder badge
  const badge = document.createElement("div");
  badge.id = "contractguard-badge";
  badge.innerHTML = `
    <span class="cg-icon">🛡️</span>
    <span class="cg-text">ContractGuard analyzing...</span>
  `;
  badge.className = "cg-loading";
  document.body.appendChild(badge);

  // Get API URL
  const { apiUrl } = await chrome.storage.sync.get("apiUrl");
  const url = apiUrl || "http://localhost:8766";

  try {
    const r = await fetch(`${url}/analyze/${chain}/${address}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();

    badge.className = `cg-${data.verdict.toLowerCase()}`;
    badge.innerHTML = `
      <span class="cg-icon">${data.verdict === "SAFE" ? "✅" : data.verdict === "CAUTION" ? "⚠️" : "🚨"}</span>
      <span class="cg-text"><b>${data.verdict}</b> · ${data.risk_score}/100 · ${data.issues?.length || 0} issues</span>
      <span class="cg-arrow">→</span>
    `;
    badge.title = data.summary || "";
    badge.style.cursor = "pointer";
    badge.addEventListener("click", () => {
      chrome.runtime.sendMessage({ type: "open_popup" });
    });
  } catch (e) {
    badge.className = "cg-error";
    badge.innerHTML = `
      <span class="cg-icon">⚠️</span>
      <span class="cg-text">ContractGuard offline</span>
    `;
    badge.title = `Server error: ${e.message}`;
  }
})();
