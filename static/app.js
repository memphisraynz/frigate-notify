// ─── Style injection for dynamically-created controls ─────────────────────
// All controls now have the "control" class set in HTML directly.
// These helpers still apply classes to JS-generated rows inside chip/token/kv fields.

function applyControlClasses(el) {
  el.style.background    = "var(--neutral-secondary-medium)";
  el.style.border        = "1px solid var(--border-default-medium)";
  el.style.borderRadius  = "12px";
  el.style.padding       = "10px 14px";
  el.style.fontSize      = "14px";
  el.style.color         = "var(--heading)";
  el.style.fontFamily    = "'Roboto Flex', sans-serif";
  el.style.outline       = "none";
  el.style.transition    = "all 200ms";
  el.style.width         = "100%";
}

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
      chip.className = "chip";
      chip.textContent = item;
      const remove = document.createElement("button");
      remove.type = "button"; remove.textContent = "×";
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
    if (!entries.length) {
      list.innerHTML = '<p style="font-size:12px;color:var(--body-subtle);font-style:italic;padding:4px 0">No devices added yet.</p>';
      return;
    }
    entries.forEach((entry, index) => {
      const row = document.createElement("div");
      row.className = "token-row";
      row.dataset.index = index;
      row.addEventListener("click", () => selectTokenRow(field, row));

      const name = document.createElement("span");
      name.className = "token-row-name";
      name.textContent = entry.name || "(unnamed)";

      const token = document.createElement("span");
      token.className = "token-row-value";
      token.textContent = entry.token ? entry.token.slice(0, 16) + "…" : "(empty)";
      token.title = entry.token || "";

      const removeBtn = document.createElement("button");
      removeBtn.type = "button"; removeBtn.textContent = "×";
      removeBtn.style.cssText = "background:none;border:none;cursor:pointer;font-size:18px;line-height:1;color:var(--body-subtle);padding:0 4px";
      removeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const cur = load(); cur.splice(index, 1); save(cur);
        delete field.dataset.selectedToken; render();
      });
      removeBtn.addEventListener("mouseover", () => { removeBtn.style.color = "var(--fg-brand)"; });
      removeBtn.addEventListener("mouseout",  () => { removeBtn.style.color = "var(--body-subtle)"; });

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
  field.querySelectorAll(".token-row").forEach((r) => r.classList.remove("selected"));
  row.classList.add("selected");
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
      row.className = "kv-row";

      const ti = document.createElement("input"); ti.type = "text"; ti.placeholder = "Button label"; ti.value = entry.title || "";
      applyControlClasses(ti);
      ti.addEventListener("input", () => { const c = load(); c[index] = { ...c[index], title: ti.value }; save(c); });

      const ui = document.createElement("input"); ui.type = "text"; ui.placeholder = "URL or template"; ui.value = entry.url || "";
      applyControlClasses(ui); ui.style.fontFamily = "monospace"; ui.style.fontSize = "12px";
      ui.addEventListener("input", () => { const c = load(); c[index] = { ...c[index], url: ui.value }; save(c); });

      const rb = document.createElement("button"); rb.type = "button"; rb.textContent = "×";
      rb.className = "btn btn-ghost btn-sm"; rb.style.padding = "10px 14px"; rb.style.fontSize = "18px";
      rb.addEventListener("click", () => { const c = load(); c.splice(index, 1); save(c); render(); });

      row.appendChild(ti); row.appendChild(ui); row.appendChild(rb);
      list.appendChild(row);
    });
  }

  addBtn.addEventListener("click", () => { const e = load(); e.push({ title: "", url: "" }); save(e); render(); });
  render();
}

// ─── Top tab switching ─────────────────────────────────────────────────────

function setupTabs() {
  const buttons = [...document.querySelectorAll(".tab-button")];
  const panels  = [...document.querySelectorAll(".tab-panel")];
  const sidebar  = document.getElementById("config-sidebar");

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      buttons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      panels.forEach((p) => p.classList.remove("active"));
      document.getElementById(`${btn.dataset.tab}-tab`)?.classList.add("active");
      // Show/hide sidebar based on whether we're on config tab
      if (sidebar) {
        sidebar.style.display = btn.dataset.tab === "config" ? "" : "none";
      }
    });
  });
}

// ─── Config sidebar section switching ─────────────────────────────────────

function setupConfigSidebar() {
  const items    = [...document.querySelectorAll(".sidebar-item[data-section]")];
  const sections = [...document.querySelectorAll(".config-section")];

  items.forEach((item) => {
    item.addEventListener("click", () => {
      items.forEach((i) => i.classList.remove("active"));
      item.classList.add("active");
      sections.forEach((s) => s.classList.remove("active"));
      document.getElementById(`section-${item.dataset.section}`)?.classList.add("active");
    });
  });
}

// ─── Mobile sidebar toggle ─────────────────────────────────────────────────

document.getElementById("sidebar-toggle-btn")?.addEventListener("click", () => {
  const sidebar = document.getElementById("config-sidebar");
  if (sidebar) sidebar.classList.toggle("open");
});

// ─── Exclusive show/hide groups ────────────────────────────────────────────

function setupExclusiveGroup(selectId, attr) {
  const select = document.getElementById(selectId);
  if (!select) return;
  function sync() {
    document.querySelectorAll(`[${attr}]`).forEach((g) => {
      const matches = g.getAttribute(attr) === select.value;
      if (g.tagName === "DIV" && g.classList.contains("field-group")) {
        g.style.display = matches ? "" : "none";
      } else {
        g.classList.toggle("hidden", !matches);
      }
    });
  }
  select.addEventListener("change", sync); sync();
}

// ─── Live logs — incremental table (never re-renders existing rows) ────────

const LOG_INITIAL_ROWS = 50;
let activeLogLevel  = "all";
let activeLogSearch = "";
let showAllRows     = false;

const knownLogKeys = new Set();

document.querySelectorAll("#log-tbody .log-row[data-msgkey]").forEach((row) => {
  knownLogKeys.add(row.dataset.msgkey);
});

function makeLogKey(log) {
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
    if (typeof v === "object" && v !== null) {
      displayVal = `<span style="white-space:pre-wrap;color:var(--heading)">${escapeHtml(JSON.stringify(v, null, 2))}</span>`;
    } else {
      let parsed = v;
      if (typeof v === "string" && (v.trim().startsWith("{") || v.trim().startsWith("["))) {
        try { parsed = JSON.parse(v); } catch { /* keep as string */ }
      }
      if (typeof parsed === "object" && parsed !== null) {
        displayVal = `<span style="white-space:pre-wrap;color:var(--heading)">${escapeHtml(JSON.stringify(parsed, null, 2))}</span>`;
      } else {
        displayVal = `<span style="word-break:break-all">${escapeHtml(String(v))}</span>`;
      }
    }
    return `<tr style="border-bottom:1px solid rgba(74,69,79,.3)">
      <td style="padding:6px 12px;font-family:monospace;color:var(--body-subtle);white-space:nowrap;width:160px;vertical-align:top">${escapeHtml(k)}</td>
      <td style="padding:6px 12px;font-family:monospace;color:var(--heading)">${displayVal}</td>
    </tr>`;
  }).join("");
}

function levelBadgeHtml(level) {
  switch (level) {
    case "error": return '<span class="badge badge-error">ERR</span>';
    case "info":  return '<span class="badge badge-info">INFO</span>';
    default:      return '<span class="badge badge-debug">DBG</span>';
  }
}

function createRowPair(log) {
  const level     = (log.level || "debug").toLowerCase();
  const hasFields = log.fields && Object.keys(log.fields).length > 0;
  const summary   = buildSummary(log.fields);
  const key       = makeLogKey(log);

  const tr = document.createElement("tr");
  tr.className = `log-row${hasFields ? " cursor-pointer" : ""}`;
  tr.dataset.level     = level;
  tr.dataset.search    = (log.message + " " + JSON.stringify(log.fields || {})).toLowerCase();
  tr.dataset.expanded  = "false";
  tr.dataset.msgkey    = key;
  tr.dataset.hasFields = String(hasFields);

  tr.innerHTML = `
    <td style="padding:8px;color:var(--body-subtle);user-select:none;width:20px">
      ${hasFields ? `<svg class="expand-icon" width="12" height="12" viewBox="0 0 12 12" fill="none"
          stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"
          style="transition:transform 200ms">
        <path d="M4 2 L8 6 L4 10"/></svg>` : ""}
    </td>
    <td style="padding:8px 12px;font-family:monospace;color:var(--body-subtle);white-space:nowrap;vertical-align:top">${escapeHtml(log.time.slice(11))}</td>
    <td style="padding:8px 12px;white-space:nowrap;vertical-align:top">${levelBadgeHtml(level)}</td>
    <td style="padding:8px 12px;color:var(--heading);vertical-align:top;max-width:260px"><span style="word-break:break-word">${escapeHtml(log.message)}</span></td>
    <td style="padding:8px 12px;color:var(--body-subtle);vertical-align:top">${escapeHtml(summary)}</td>`;

  if (hasFields) {
    tr.addEventListener("click", () => toggleRow(tr));
  }

  let detailTr = null;
  if (hasFields) {
    detailTr = document.createElement("tr");
    detailTr.className = "log-detail-row hidden";
    detailTr.dataset.level = level;
    detailTr.innerHTML = `
      <td></td>
      <td colspan="4" style="padding:4px 12px 12px">
        <div style="border-radius:8px;border:1px solid var(--border-default-medium);background:var(--neutral-primary);overflow:hidden">
          <table style="width:100%;font-size:11px"><tbody>${buildDetailRows(log.fields)}</tbody></table>
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
      tbody.innerHTML = '<tr id="log-empty-placeholder"><td colspan="5" style="padding:40px 12px;text-align:center;color:var(--body-subtle)">No logs yet.</td></tr>';
    }
    updateLogCount(0);
    return;
  }

  placeholder?.remove();

  const newLogs = logs.filter((log) => !knownLogKeys.has(makeLogKey(log)));

  if (newLogs.length > 0) {
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
  const icon = row.querySelector(".expand-icon");
  if (icon) icon.style.transform = isOpen ? "" : "rotate(90deg)";
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
  if (bar) bar.style.display = capped === 0 ? "none" : "";
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
  const dot = document.getElementById("status-dot");
  if (dot) {
    dot.className = "status-dot" + (status.connected ? "" : " offline");
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

  showFcmTestStatus("Sending test notification…");
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
  if (el) { el.textContent = message; el.style.display = "inline"; }
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
  showTestPayloadStatus("Sending…");
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
  el.style.display = "inline";
  el.style.color = isError ? "var(--fg-danger)" : "var(--fg-brand)";
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
  el.textContent = message; el.style.display = "inline";
  setTimeout(() => { el.style.display = "none"; }, 2000);
}

// ─── Init ──────────────────────────────────────────────────────────────────

document.querySelectorAll(".chip-field").forEach(setupChipField);
document.querySelectorAll(".token-field").forEach(setupTokenField);
document.querySelectorAll(".kv-field").forEach(setupKvField);
setupSeverityChecks();
setupTabs();
setupConfigSidebar();
setupExclusiveGroup("connection-type", "data-connection-type");
setupExclusiveGroup("delivery-method", "data-delivery-method");

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
  if (status) status.style.display = "none";
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
