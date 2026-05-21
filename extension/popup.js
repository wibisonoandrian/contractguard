// ContractGuard popup logic
const $ = (id) => document.getElementById(id);

const SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"];

async function getApiUrl() {
  const { apiUrl } = await chrome.storage.sync.get("apiUrl");
  return apiUrl || "http://localhost:8766";
}

async function setApiUrl(url) {
  await chrome.storage.sync.set({ apiUrl: url });
}

async function loadFromActiveTab() {
  // Auto-detect address from current tab URL (Etherscan-style)
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.url) return;
    const match = tab.url.match(/(etherscan|bscscan|basescan|arbiscan|polygonscan)\.[a-z]+\/(address|token)\/(0x[a-fA-F0-9]{40})/);
    if (match) {
      const domainToChain = {
        "etherscan": "ethereum", "bscscan": "bsc",
        "basescan": "base", "arbiscan": "arbitrum", "polygonscan": "polygon",
      };
      $("chain").value = domainToChain[match[1]] || "ethereum";
      $("address").value = match[3];
    }
  } catch (e) {
    // no permission, ignore
  }
}

async function analyze() {
  const chain = $("chain").value;
  const address = $("address").value.trim();

  if (!/^0x[a-fA-F0-9]{40}$/.test(address)) {
    showError("Invalid address format. Must be 0x followed by 40 hex chars.");
    return;
  }

  hideAll();
  $("loader").classList.remove("hidden");

  try {
    const apiUrl = await getApiUrl();
    const r = await fetch(`${apiUrl}/analyze/${chain}/${address}`);
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${r.status}`);
    }
    const data = await r.json();
    renderResult(data);
  } catch (e) {
    showError(`Analysis failed: ${e.message}\n\nMake sure the ContractGuard server is running:\npython -m contractguard.cli serve`);
  }
}

function renderResult(data) {
  $("loader").classList.add("hidden");
  $("result").classList.remove("hidden");

  const verdict = $("verdict");
  verdict.textContent = data.verdict;
  verdict.className = `verdict ${data.verdict}`;

  $("score").textContent = `${data.risk_score}/100`;
  $("contract-name").textContent = data.contract_name || "(unknown contract)";
  $("summary").textContent = data.summary || "";

  // Issues
  const issuesEl = $("issues");
  issuesEl.innerHTML = "";
  const sortedIssues = (data.issues || []).sort(
    (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
  );
  for (const issue of sortedIssues.slice(0, 8)) {
    const div = document.createElement("div");
    div.className = `issue ${issue.severity}`;
    div.innerHTML = `
      <div class="issue-header">
        <span class="issue-sev ${issue.severity}">${issue.severity}</span>
        ${escapeHtml(issue.title || "")}
      </div>
      <div class="issue-desc">${escapeHtml(issue.description || "")}</div>
    `;
    issuesEl.appendChild(div);
  }

  // Owner privileges
  const privsEl = $("privileges");
  if (data.owner_privileges?.length) {
    privsEl.innerHTML = `<div class="privileges-title">⚠ Owner can:</div><ul>${data.owner_privileges.slice(0, 6).map(p => `<li>${escapeHtml(p)}</li>`).join("")}</ul>`;
    privsEl.classList.remove("hidden");
  } else {
    privsEl.classList.add("hidden");
  }

  // Meta flags
  const metaEl = $("meta");
  metaEl.innerHTML = "";
  const flags = [
    [data.verified, "✓ Verified", "✗ Unverified"],
    [data.is_proxy, "🔄 Proxy", null],
    [data.is_renounced, "🔓 Renounced", null],
    [data.is_honeypot_likely, "🍯 Honeypot risk", null],
  ];
  for (const [val, on, off] of flags) {
    if (val === true) {
      const s = document.createElement("span");
      s.textContent = on;
      s.className = data.is_honeypot_likely ? "bad" : "ok";
      metaEl.appendChild(s);
    } else if (val === false && off) {
      const s = document.createElement("span");
      s.textContent = off;
      s.className = "bad";
      metaEl.appendChild(s);
    }
  }

  $("explorer-link").href = data.explorer_url || "#";
}

function showError(msg) {
  hideAll();
  $("error").textContent = msg;
  $("error").classList.remove("hidden");
}

function hideAll() {
  for (const id of ["result", "loader", "error", "settings"]) $(id).classList.add("hidden");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Init
document.addEventListener("DOMContentLoaded", async () => {
  await loadFromActiveTab();
  $("analyze").addEventListener("click", analyze);
  $("address").addEventListener("keypress", e => { if (e.key === "Enter") analyze(); });
  $("settings-btn").addEventListener("click", async () => {
    const cur = await getApiUrl();
    $("api-url").value = cur;
    $("settings").classList.toggle("hidden");
  });
  $("save-settings").addEventListener("click", async () => {
    await setApiUrl($("api-url").value.trim() || "http://localhost:8766");
    $("api-endpoint").textContent = (await getApiUrl()).replace(/^https?:\/\//, "");
    $("settings").classList.add("hidden");
  });
  const cur = await getApiUrl();
  $("api-endpoint").textContent = cur.replace(/^https?:\/\//, "");
});
