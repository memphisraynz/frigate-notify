document.querySelectorAll(".control").forEach((item) => {
  item.classList.add("w-full", "rounded-md", "border", "border-slate-700", "bg-slate-950", "px-3", "py-2", "text-slate-100", "outline-none", "focus:border-blue-500");
});
document.querySelectorAll(".field").forEach((item) => {
  item.classList.add("block", "text-sm", "font-medium", "text-slate-300");
});
document.querySelectorAll(".hint").forEach((item) => {
  item.classList.add("mt-1", "block", "text-xs", "font-normal", "leading-5", "text-slate-400");
});
document.querySelectorAll(".btn").forEach((item) => {
  item.classList.add("rounded-md", "bg-blue-600", "px-4", "py-2", "text-sm", "font-medium", "text-white", "hover:bg-blue-500");
});
document.querySelectorAll(".check-card").forEach((item) => {
  item.classList.add("inline-flex", "items-center", "gap-2", "rounded-md", "border", "border-slate-700", "bg-slate-950", "px-3", "py-2", "text-sm", "text-slate-200");
});

// ─── Chip fields ───────────────────────────────────────────────────────────

function splitValues(value, separator = "default") {
  const normalized = value
    .replaceAll("\\r\\n", "\n").replaceAll("\\n", "\n")
    .replaceAll("\r\n", "\n").replaceAll("\r", "\n");
  const pattern = separator === "newline" ? /\n+/ : /[\n,]+/;
  return normalized.split(pattern).map((item) => item.trim()).filter(Boolean);
}

function setupChipField(field) {
  const textarea = field.querySelector(".chip-values");
  const list     = field.querySelector(".chip-list");
  const input    = field.querySelector(".chip-input");
  const add      = field.querySelector(".chip-add");

  function values() { return splitValues(textarea.value); }
  function save(items) { textarea.value = [...new Set(items)].join("\n"); }

  function render() {
    list.innerHTML = "";
    values().forEach((item) => {
      const chip   = document.createElement("span");
      chip.className = "chip inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-800 px-3 py-1 text-sm text-slate-100";
      chip.textContent = item;
      const remove = document.createElement("button");
      remove.type = "button"; remove.textContent = "x";
      remove.className = "text-slate-400 hover:text-white";
      remove.addEventListener("click", () => { save(values().filter((v) => v !== item)); render(); });
      chip.appendChild(remove);
      list.appendChild(chip);
    });
  }

  function addValue() {
    const item = input.value.trim();
    if (!item) return;
    save([...values(), item]); input.value = ""; render();
  }

  add.addEventListener("click", addValue);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addValue(); } });
  render();
}

// ─── Severity checkboxes ───────────────────────────────────────────────────

function setupSeverityChecks() {
  const textarea = document.querySelector(".severity-values");
  const checks   = [...document.querySelectorAll(".severity-check")];
  if (!textarea) return;
  function sync() { textarea.value = checks.filter((c) => c.checked).map((c) => c.value).join("\n"); }
  checks.forEach((c) => c.addEventListener("change", sync));
  sync();
}

// ─── Device tokens ─────────────────────────────────────────────────────────

function setupTokenField(field) {
  const textarea   = field.querySelector(".token-values");
  const list       = field.querySelector(".token-list");
  const nameInput  = field.querySelector(".token-name-input");
  const valueInput = field.querySelector(".token-value-input");
  const addBtn     = field.querySelector(".token-add");

  function load() { try { const p = JSON.parse(textarea.value || "[]"); return Array.isArray(p) ? p : []; } catch { return []; } }
  function save(e) { textarea.value = JSON.stringify(e); }

  function render() {
    list.innerHTML = "";
    const entries = load();
    if (!entries.length) { list.innerHTML = '<p class="text-xs text-slate-500 italic">No devices added yet.</p>'; return; }
    entries.forEach((entry, index) => {
      const row = document.createElement("div");
      row.className = "token-row grid grid-cols-[1fr_2fr_auto] gap-2 items-center rounded-md border border-slate-700 bg-slate-950 px-3 py-2 cursor-pointer";
      row.dataset.index = index;
      row.addEventListener("click", () => selectTokenRow(field, row));

      const name = document.createElement("span");
      name.className = "text-sm text-slate-200 truncate";
      name.textContent = entry.name || "(unnamed)";

      const token = document.createElement("span");
      token.className = "text-xs font-mono text-slate-400 truncate";
      token.textContent = entry.token ? entry.token.slice(0, 12) + "..." : "(empty)";
      token.title = entry.token || "";

      const removeBtn = document.createElement("button");
      removeBtn.type = "button"; removeBtn.textContent = "×";
      removeBtn.className = "text-slate-500 hover:text-white text-lg leading-none";
      removeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const cur = load(); cur.splice(index, 1); save(cur);
        delete field.dataset.selectedToken; render();
      });

      row.appendChild(name); row.appendChild(token); row.appendChild(removeBtn);
      list.appendChild(row);
    });
  }

  function addEntry() {
    const name = nameInput.value.trim(); const token = valueInput.value.trim();
    if (!token) return;
    const entries = load(); entries.push({ name, token }); save(entries);
    nameInput.value = ""; valueInput.value = ""; render();
  }

  addBtn.addEventListener("click", addEntry);
  [nameInput, valueInput].forEach((inp) => inp.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addEntry(); } }));
  render();
}

function selectTokenRow(field, row) {
  field.querySelectorAll(".token-row").forEach((r) => r.classList.remove("border-blue-400", "bg-blue-950", "ring-2", "ring-blue-500"));
  row.classList.add("border-blue-400", "bg-blue-950", "ring-2", "ring-blue-500");
  const entries = JSON.parse(field.querySelector(".token-values").value || "[]");
  const entry   = entries[Number(row.dataset.index)];
  field.dataset.selectedToken = entry ? entry.token : "";
}

// ─── Key-value button rows ─────────────────────────────────────────────────

function setupKvField(field) {
  const textarea = field.querySelector(".kv-values");
  const list     = field.querySelector(".kv-list");
  const addBtn   = field.querySelector(".kv-add");

  function load() { try { const p = JSON.parse(textarea.value || "[]"); return Array.isArray(p) ? p : []; } catch { return []; } }
  function save(e) { textarea.value = JSON.stringify(e); }

  function render() {
    list.innerHTML = "";
    load().forEach((entry, index) => {
      const row = document.createElement("div");
      row.className = "grid grid-cols-[1fr_2fr_auto] gap-2 items-start";

      const ti = document.createElement("input"); ti.type = "text"; ti.placeholder = "Button label"; ti.value = entry.title || "";
      ti.className = "control w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-blue-500 text-sm";
      ti.addEventListener("input", () => { const c = load(); c[index] = { ...c[index], title: ti.value }; save(c); });

      const ui = document.createElement("input"); ui.type = "text"; ui.placeholder = "URL or template"; ui.value = entry.url || "";
      ui.className = "control w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-blue-500 text-sm font-mono";
      ui.addEventListener("input", () => { const c = load(); c[index] = { ...c[index], url: ui.value }; save(c); });

      const rb = document.createElement("button"); rb.type = "button"; rb.textContent = "×";
      rb.className = "rounded-md border border-slate-700 px-3 py-2 text-slate-400 hover:text-white hover:bg-slate-800 text-lg leading-none";
      rb.addEventListener("click", () => { const c = load(); c.splice(index, 1); save(c); render(); });

      row.appendChild(ti); row.appendChild(ui); row.appendChild(rb);
      list.appendChild(row);
    });
  }

  addBtn.addEventListener("click", () => { const e = load(); e.push({ title: "", url: "" }); save(e); render(); });
  render();
}

// ─── Tab switching ─────────────────────────────────────────────────────────

function setupTabs() {
  const buttons = [...document.querySelectorAll(".tab-button")];
  const panels  = [...document.querySelectorAll(".tab-panel")];
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => { b.classList.remove("bg-blue-600", "text-white"); b.classList.add("text-slate-300"); });
      btn.classList.add("bg-blue-600", "text-white"); btn.classList.remove("text-slate-300");
      panels.forEach((p) => p.classList.add("hidden"));
      document.getElementById(`${btn.dataset.tab}-tab`)?.classList.remove("hidden");
    });
  });
}

// ─── Exclusive show/hide groups ────────────────────────────────────────────

function setupExclusiveGroup(selectId, attr) {
  const select = document.getElementById(selectId);
  if (!select) return;
  function sync() {
    document.querySelectorAll(`[${attr}]`).forEach((g) => g.classList.toggle("hidden", g.getAttribute(attr) !== select.value));
  }
  select.addEventListener("change", sync); sync();
}

// ─── Live logs — incremental table (never re-renders existing rows) ────────
//
// The root cause of selection being destroyed was innerHTML rebuilding the
// entire tbody on every poll. The fix: track which log entries are already
// in the DOM by a stable key, and only prepend genuinely new rows.
// Existing rows are never touched, so text selections survive indefinitely.

const LOG_INITIAL_ROWS = 50;
let activeLogLevel  = "all";
let activeLogSearch = "";
let showAllRows     = false;

// Set of keys for rows already rendered — survives across refreshes
const knownLogKeys = new Set();

// Seed known keys from server-rendered rows so the first poll doesn't duplicate them
document.querySelectorAll("#log-tbody .log-row[data-msgkey]").forEach((row) => {
  knownLogKeys.add(row.dataset.msgkey);
});

function makeLogKey(log) {
  // Stable identity: timestamp + message. Both are fixed once logged.
  return log.time + "\x00" + log.message;
}

const SUMMARY_FIELDS = ["camera", "label", "review_id", "error", "device", "method", "status_code", "topic", "host", "url", "type", "severity"];

function buildSummary(fields) {
  if (!fields || !Object.keys(fields).length) return "";
  const parts = [];
  for (const key of SUMMARY_FIELDS) {
    if (fields[key] == null || fields[key] === "") continue;
    let val = String(fields[key]);
    if (key === "review_id") val = val.slice(0, 12);
    if (key === "url" || key === "error") val = val.length > 60 ? val.slice(0, 60) + "…" : val;
    parts.push(key === "status_code" ? `HTTP ${val}` : `${key}: ${val}`);
    if (parts.length >= 4) break;
  }
  if (!parts.length) {
    const [k, v] = Object.entries(fields)[0];
    parts.push(`${k}: ${String(v).slice(0, 60)}`);
  }
  return parts.join(" · ");
}

function buildDetailRows(fields) {
  if (!fields) return "";
  return Object.entries(fields).map(([k, v]) => {
    let displayVal;
    // Objects and arrays: pretty-print as JSON
    if (typeof v === "object" && v !== null) {
      displayVal = `<span class="whitespace-pre-wrap text-slate-300">${escapeHtml(JSON.stringify(v, null, 2))}</span>`;
    } else {
      // Strings: try to parse as JSON — if it succeeds, render formatted
      let parsed = v;
      if (typeof v === "string" && (v.trim().startsWith("{") || v.trim().startsWith("["))) {
        try { parsed = JSON.parse(v); } catch { /* keep as string */ }
      }
      if (typeof parsed === "object" && parsed !== null) {
        displayVal = `<span class="whitespace-pre-wrap text-slate-300">${escapeHtml(JSON.stringify(parsed, null, 2))}</span>`;
      } else {
        displayVal = `<span class="break-all">${escapeHtml(String(v))}</span>`;
      }
    }
    return `<tr class="border-b border-slate-800/60 last:border-0">
      <td class="px-3 py-1.5 font-mono text-slate-500 whitespace-nowrap w-[160px] align-top">${escapeHtml(k)}</td>
      <td class="px-3 py-1.5 font-mono">${displayVal}</td>
    </tr>`;
  }).join("");
}

function levelBadgeHtml(level) {
  switch (level) {
    case "error": return '<span class="inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase bg-red-950 text-red-400 border border-red-800">ERR</span>';
    case "info":  return '<span class="inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase bg-blue-950 text-blue-400 border border-blue-800">INFO</span>';
    default:      return '<span class="inline-block rounded px-1.5 py-0.5 text-[10px] font-bold uppercase bg-slate-800 text-slate-500 border border-slate-700">DBG</span>';
  }
}

function createRowPair(log) {
  const level     = (log.level || "debug").toLowerCase();
  const hasFields = log.fields && Object.keys(log.fields).length > 0;
  const summary   = buildSummary(log.fields);
  const key       = makeLogKey(log);

  // Main row
  const tr = document.createElement("tr");
  tr.className = `log-row border-b border-slate-800/40${hasFields ? " cursor-pointer hover:bg-slate-800/20" : ""}`;
  tr.dataset.level    = level;
  tr.dataset.search   = (log.message + " " + JSON.stringify(log.fields || {})).toLowerCase();
  tr.dataset.expanded = "false";
  tr.dataset.msgkey   = key;
  tr.dataset.hasFields = String(hasFields);

  tr.innerHTML = `
    <td class="px-2 py-2.5 text-slate-600 select-none w-5">
      ${hasFields ? `<svg class="expand-icon w-3 h-3 transition-transform" viewBox="0 0 12 12" fill="none"
          stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 2 L8 6 L4 10"/></svg>` : ""}
    </td>
    <td class="px-3 py-2.5 font-mono text-slate-500 whitespace-nowrap align-top">${escapeHtml(log.time.slice(11))}</td>
    <td class="px-3 py-2.5 whitespace-nowrap align-top">${levelBadgeHtml(level)}</td>
    <td class="px-3 py-2.5 text-slate-200 align-top max-w-[240px]"><span class="break-words">${escapeHtml(log.message)}</span></td>
    <td class="px-3 py-2.5 text-slate-400 align-top">${escapeHtml(summary)}</td>`;

  if (hasFields) {
    tr.addEventListener("click", () => toggleRow(tr));
  }

  // Detail row (hidden by default)
  let detailTr = null;
  if (hasFields) {
    detailTr = document.createElement("tr");
    detailTr.className = "log-detail-row hidden border-b border-slate-800";
    detailTr.dataset.level = level;
    detailTr.innerHTML = `
      <td></td>
      <td colspan="4" class="px-3 pb-3 pt-1">
        <div class="rounded border border-slate-700 bg-slate-950 overflow-hidden">
          <table class="w-full text-xs"><tbody>${buildDetailRows(log.fields)}</tbody></table>
        </div>
      </td>`;
  }

  return { tr, detailTr };
}

function renderLogs(logs) {
  const tbody = document.getElementById("log-tbody");
  if (!tbody) return;

  const placeholder = document.getElementById("log-empty-placeholder");

  if (!logs.length) {
    if (!knownLogKeys.size && !placeholder) {
      tbody.innerHTML = '<tr id="log-empty-placeholder"><td colspan="5" class="px-3 py-8 text-center text-slate-500">No logs yet.</td></tr>';
    }
    updateLogCount(0);
    return;
  }

  // Remove placeholder if data arrives
  placeholder?.remove();

  // Only process logs we haven't seen yet (API returns newest-first)
  const newLogs = logs.filter((log) => !knownLogKeys.has(makeLogKey(log)));

  if (newLogs.length > 0) {
    // Build a fragment with all new rows, then insert before the oldest existing row.
    // This keeps the table newest-first without touching any existing row.
    const fragment = document.createDocumentFragment();
    newLogs.forEach((log) => {
      const { tr, detailTr } = createRowPair(log);
      fragment.appendChild(tr);
      if (detailTr) fragment.appendChild(detailTr);
      knownLogKeys.add(makeLogKey(log));
    });

    const firstExisting = tbody.querySelector(".log-row");
    if (firstExisting) {
      tbody.insertBefore(fragment, firstExisting);
    } else {
      tbody.appendChild(fragment);
    }
  }

  // Trim rows that have aged off the server's 500-entry deque
  const serverKeys = new Set(logs.map(makeLogKey));
  [...tbody.querySelectorAll(".log-row")].forEach((row) => {
    if (!serverKeys.has(row.dataset.msgkey)) {
      const next = row.nextElementSibling;
      if (next?.classList.contains("log-detail-row")) next.remove();
      row.remove();
      knownLogKeys.delete(row.dataset.msgkey);
    }
  });

  applyFilters();
}

function toggleRow(row) {
  const detailRow = row.nextElementSibling;
  if (!detailRow?.classList.contains("log-detail-row")) return;
  const isOpen = row.dataset.expanded === "true";
  row.dataset.expanded = isOpen ? "false" : "true";
  detailRow.classList.toggle("hidden", isOpen);
  row.querySelector(".expand-icon")?.classList.toggle("rotate-90", !isOpen);
}

// ─── Filtering ─────────────────────────────────────────────────────────────

function applyFilters() {
  const rows        = [...document.querySelectorAll("#log-tbody .log-row")];
  const searchLower = activeLogSearch.toLowerCase();
  let visible = 0;
  let capped  = 0;

  rows.forEach((row) => {
    const levelMatch  = activeLogLevel === "all" || row.dataset.level === activeLogLevel;
    const searchMatch = !searchLower || (row.dataset.search || "").includes(searchLower);
    const passes      = levelMatch && searchMatch;
    const detailRow   = row.nextElementSibling?.classList.contains("log-detail-row")
                          ? row.nextElementSibling : null;

    if (passes) {
      visible++;
      const overLimit = !showAllRows && visible > LOG_INITIAL_ROWS;
      row.classList.toggle("hidden", overLimit);
      if (detailRow) detailRow.classList.toggle("hidden", overLimit || row.dataset.expanded !== "true");
      if (overLimit) capped++;
    } else {
      row.classList.add("hidden");
      if (detailRow) detailRow.classList.add("hidden");
    }
  });

  const bar = document.getElementById("log-show-more");
  const cnt = document.getElementById("log-hidden-count");
  if (bar) bar.classList.toggle("hidden", capped === 0);
  if (cnt) cnt.textContent = capped;

  updateLogCount(visible);
}

function updateLogCount(visible) {
  const el    = document.getElementById("log-count");
  const total = document.querySelectorAll("#log-tbody .log-row").length;
  if (el) el.textContent = visible < total ? `${visible} / ${total}` : `${total} entries`;
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function visibleLogText() {
  return [...document.querySelectorAll("#log-tbody .log-row:not(.hidden)")].map((row) => {
    const cells = [...row.querySelectorAll("td")];
    const time    = cells[1]?.textContent.trim() || "";
    const level   = cells[2]?.textContent.trim() || "";
    const message = cells[3]?.textContent.trim() || "";
    const summary = cells[4]?.textContent.trim() || "";
    return `${time} [${level}] ${message}${summary ? " — " + summary : ""}`;
  }).join("\n");
}

// ─── Refresh ───────────────────────────────────────────────────────────────

async function refreshLogs() {
  const response = await fetch("/api/logs");
  if (!response.ok) return;
  const data = await response.json();
  renderLogs(data.logs || []);
  const status = data.status || {};
  const line   = document.getElementById("status-line");
  if (line) {
    line.textContent = `${(status.connection_type || "mqtt").toUpperCase()}: ${Boolean(status.connected)} | Sent: ${status.sent || 0} | Error: ${status.last_error || "none"}`;
  }
}

// ─── FCM test ──────────────────────────────────────────────────────────────

async function sendFcmTest(mode) {
  const field = document.querySelector(".token-field");
  let entries = [];
  try { entries = JSON.parse(field?.querySelector(".token-values")?.value || "[]"); } catch { /* */ }
  const selectedToken = field?.dataset.selectedToken;

  if (mode === "all" && !entries.length)  { showFcmTestStatus("No device tokens configured"); return; }
  if (mode !== "all" && !selectedToken)   { showFcmTestStatus("Select a device row first, or use Test all devices"); return; }

  showFcmTestStatus("Sending test notification...");
  try {
    const body = mode === "all"
      ? { all: true, tokens: entries.map((e) => e.token).filter(Boolean) }
      : { token: selectedToken };
    const response = await fetch("/api/test-fcm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const result   = await response.json();
    if (!response.ok) throw new Error(result.error || "Test failed");
    showFcmTestStatus(`Sent ${result.sent ?? 1} test notification${(result.sent ?? 1) === 1 ? "" : "s"}`);
    refreshLogs();
  } catch (err) { showFcmTestStatus(err.message || "Test failed"); }
}

function showFcmTestStatus(message) {
  const el = document.getElementById("fcm-test-status");
  if (el) { el.textContent = message; el.classList.remove("hidden"); }
}

// ─── Saved test payload ────────────────────────────────────────────────────

async function saveCurrentPayload() {
  const input = document.getElementById("test-payload-input");
  if (!input) return;
  const raw = input.value.trim();
  if (!raw) { showTestPayloadStatus("Nothing to save — editor is empty", true); return; }
  let parsed;
  try { parsed = JSON.parse(raw); } catch (err) { showTestPayloadStatus(`Cannot save — invalid JSON: ${err.message}`, true); return; }
  const response = await fetch("/api/saved-payload", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(parsed) });
  showTestPayloadStatus(response.ok ? "Payload saved" : "Save failed", !response.ok);
}

const SAMPLE_PAYLOAD = document.getElementById("test-payload-input")?.value || "";

async function sendTestPayload() {
  const input = document.getElementById("test-payload-input");
  if (!input) return;
  let payload;
  try { payload = JSON.parse(input.value); } catch (err) { showTestPayloadStatus(`JSON parse error: ${err.message}`, true); return; }
  showTestPayloadStatus("Sending...");
  try {
    const response = await fetch("/api/test", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const result   = await response.json();
    if (!response.ok) throw new Error(result.error || "Request failed");
    showTestPayloadStatus("Payload sent — check logs for result");
    refreshLogs();
  } catch (err) { showTestPayloadStatus(`Error: ${err.message}`, true); }
}

function showTestPayloadStatus(message, isError = false) {
  const el = document.getElementById("test-payload-status");
  if (!el) return;
  el.textContent = message;
  el.classList.remove("hidden", "text-red-400", "text-blue-200");
  el.classList.add(isError ? "text-red-400" : "text-blue-200");
}

// ─── Log polling ───────────────────────────────────────────────────────────

let logRefreshMs     = 3000;
let logRefreshPaused = false;
let logRefreshTimer  = null;

function scheduleLogRefresh() {
  window.clearInterval(logRefreshTimer);
  if (!logRefreshPaused && logRefreshMs > 0) {
    logRefreshTimer = window.setInterval(refreshLogs, logRefreshMs);
  }
}

async function copyText(text) {
  if (!text.trim()) { showCopyStatus("Nothing to copy"); return; }
  await navigator.clipboard.writeText(text);
  showCopyStatus("Copied");
}

function showCopyStatus(message) {
  const el = document.getElementById("copy-log-status");
  if (!el) return;
  el.textContent = message; el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 2000);
}

// ─── Init ──────────────────────────────────────────────────────────────────

document.querySelectorAll(".chip-field").forEach(setupChipField);
document.querySelectorAll(".token-field").forEach(setupTokenField);
document.querySelectorAll(".kv-field").forEach(setupKvField);
setupSeverityChecks();
setupTabs();
setupExclusiveGroup("connection-type", "data-connection-type");
setupExclusiveGroup("delivery-method", "data-delivery-method");

// Wire click handlers on server-rendered rows (already in the DOM on load)
document.querySelectorAll("#log-tbody .log-row[data-has-fields='true']").forEach((row) => {
  row.addEventListener("click", () => toggleRow(row));
});

applyFilters();

document.getElementById("log-search")?.addEventListener("input", (e) => {
  activeLogSearch = e.target.value; showAllRows = false; applyFilters();
});
document.getElementById("log-level-filter")?.addEventListener("change", (e) => {
  activeLogLevel = e.target.value; showAllRows = false; applyFilters();
});
document.getElementById("log-show-more-btn")?.addEventListener("click", () => {
  showAllRows = true; applyFilters();
});
document.getElementById("refresh-logs")?.addEventListener("click", refreshLogs);
document.getElementById("copy-visible-logs")?.addEventListener("click", () => copyText(visibleLogText()));
document.getElementById("test-selected-fcm-token")?.addEventListener("click", () => sendFcmTest("selected"));
document.getElementById("test-all-fcm-tokens")?.addEventListener("click", () => sendFcmTest("all"));
document.getElementById("send-test-payload")?.addEventListener("click", sendTestPayload);
document.getElementById("save-test-payload")?.addEventListener("click", saveCurrentPayload);
document.getElementById("reset-test-payload")?.addEventListener("click", () => {
  const input = document.getElementById("test-payload-input");
  if (input) input.value = SAMPLE_PAYLOAD;
  const status = document.getElementById("test-payload-status");
  if (status) status.classList.add("hidden");
});
document.getElementById("log-refresh-interval")?.addEventListener("change", (e) => {
  logRefreshMs = Number(e.target.value) || 0; scheduleLogRefresh();
});
document.getElementById("toggle-log-refresh")?.addEventListener("click", (e) => {
  logRefreshPaused = !logRefreshPaused;
  e.target.textContent = logRefreshPaused ? "Resume" : "Pause";
  scheduleLogRefresh();
});

scheduleLogRefresh();
