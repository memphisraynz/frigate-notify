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

// ─── Chip fields (cameras, labels, zones, hours) ───────────────────────────

function splitValues(value, separator = "default") {
  const normalized = value
    .replaceAll("\\r\\n", "\n")
    .replaceAll("\\n", "\n")
    .replaceAll("\r\n", "\n")
    .replaceAll("\r", "\n");
  const pattern = separator === "newline" ? /\n+/ : /[\n,]+/;
  return normalized.split(pattern).map((item) => item.trim()).filter(Boolean);
}

function setupChipField(field) {
  const textarea = field.querySelector(".chip-values");
  const list = field.querySelector(".chip-list");
  const input = field.querySelector(".chip-input");
  const add = field.querySelector(".chip-add");

  function values() {
    return splitValues(textarea.value, "default");
  }

  function save(items) {
    textarea.value = [...new Set(items)].join("\n");
  }

  function render() {
    list.innerHTML = "";
    values().forEach((item) => {
      const chip = document.createElement("span");
      chip.className = "chip inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-800 px-3 py-1 text-sm text-slate-100";
      chip.textContent = item;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "x";
      remove.className = "text-slate-400 hover:text-white";
      remove.addEventListener("click", () => {
        save(values().filter((v) => v !== item));
        render();
      });
      chip.appendChild(remove);
      list.appendChild(chip);
    });
  }

  function addValue() {
    const item = input.value.trim();
    if (!item) return;
    save([...values(), item]);
    input.value = "";
    render();
  }

  add.addEventListener("click", addValue);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addValue();
    }
  });
  render();
}

// ─── Severity checkboxes ───────────────────────────────────────────────────

function setupSeverityChecks() {
  const textarea = document.querySelector(".severity-values");
  const checks = [...document.querySelectorAll(".severity-check")];
  if (!textarea) return;
  function sync() {
    textarea.value = checks.filter((item) => item.checked).map((item) => item.value).join("\n");
  }
  checks.forEach((item) => item.addEventListener("change", sync));
  sync();
}

// ─── Device tokens (name + token key-pair table) ──────────────────────────

function setupTokenField(field) {
  const textarea = field.querySelector(".token-values");
  const list = field.querySelector(".token-list");
  const nameInput = field.querySelector(".token-name-input");
  const valueInput = field.querySelector(".token-value-input");
  const addBtn = field.querySelector(".token-add");

  function load() {
    try {
      const parsed = JSON.parse(textarea.value || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function save(entries) {
    textarea.value = JSON.stringify(entries);
  }

  function render() {
    list.innerHTML = "";
    const entries = load();
    if (!entries.length) {
      list.innerHTML = '<p class="text-xs text-slate-500 italic">No devices added yet.</p>';
      return;
    }
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
      removeBtn.type = "button";
      removeBtn.textContent = "×";
      removeBtn.className = "text-slate-500 hover:text-white text-lg leading-none";
      removeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const current = load();
        current.splice(index, 1);
        save(current);
        delete field.dataset.selectedToken;
        render();
      });

      row.appendChild(name);
      row.appendChild(token);
      row.appendChild(removeBtn);
      list.appendChild(row);
    });
  }

  function addEntry() {
    const name = nameInput.value.trim();
    const token = valueInput.value.trim();
    if (!token) return;
    const entries = load();
    entries.push({ name, token });
    save(entries);
    nameInput.value = "";
    valueInput.value = "";
    render();
  }

  addBtn.addEventListener("click", addEntry);
  [nameInput, valueInput].forEach((inp) => {
    inp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); addEntry(); }
    });
  });
  render();
}

function selectTokenRow(field, row) {
  field.querySelectorAll(".token-row").forEach((r) => {
    r.classList.remove("border-blue-400", "bg-blue-950", "ring-2", "ring-blue-500");
  });
  row.classList.add("border-blue-400", "bg-blue-950", "ring-2", "ring-blue-500");
  const entries = JSON.parse(field.querySelector(".token-values").value || "[]");
  const entry = entries[Number(row.dataset.index)];
  field.dataset.selectedToken = entry ? entry.token : "";
}

// ─── Key-value button rows (title + URL) ──────────────────────────────────

function setupKvField(field) {
  const textarea = field.querySelector(".kv-values");
  const list = field.querySelector(".kv-list");
  const addBtn = field.querySelector(".kv-add");

  function load() {
    try {
      const parsed = JSON.parse(textarea.value || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function save(entries) {
    textarea.value = JSON.stringify(entries);
  }

  function render() {
    list.innerHTML = "";
    const entries = load();
    entries.forEach((entry, index) => {
      const row = document.createElement("div");
      row.className = "grid grid-cols-[1fr_2fr_auto] gap-2 items-start";

      const titleInput = document.createElement("input");
      titleInput.type = "text";
      titleInput.placeholder = "Button label";
      titleInput.value = entry.title || "";
      titleInput.className = "control w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-blue-500 text-sm";
      titleInput.addEventListener("input", () => {
        const current = load();
        current[index] = { ...current[index], title: titleInput.value };
        save(current);
      });

      const urlInput = document.createElement("input");
      urlInput.type = "text";
      urlInput.placeholder = "URL or template, e.g. {{ attachment }}";
      urlInput.value = entry.url || "";
      urlInput.className = "control w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-blue-500 text-sm font-mono";
      urlInput.addEventListener("input", () => {
        const current = load();
        current[index] = { ...current[index], url: urlInput.value };
        save(current);
      });

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.textContent = "×";
      removeBtn.className = "rounded-md border border-slate-700 px-3 py-2 text-slate-400 hover:text-white hover:bg-slate-800 text-lg leading-none";
      removeBtn.addEventListener("click", () => {
        const current = load();
        current.splice(index, 1);
        save(current);
        render();
      });

      row.appendChild(titleInput);
      row.appendChild(urlInput);
      row.appendChild(removeBtn);
      list.appendChild(row);
    });
  }

  addBtn.addEventListener("click", () => {
    const entries = load();
    entries.push({ title: "", url: "" });
    save(entries);
    render();
  });

  render();
}

// ─── Tab switching ─────────────────────────────────────────────────────────

function setupTabs() {
  const buttons = [...document.querySelectorAll(".tab-button")];
  const panels = [...document.querySelectorAll(".tab-panel")];
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      buttons.forEach((item) => item.classList.remove("bg-blue-600", "text-white"));
      buttons.forEach((item) => item.classList.add("text-slate-300"));
      button.classList.add("bg-blue-600", "text-white");
      button.classList.remove("text-slate-300");
      panels.forEach((panel) => panel.classList.add("hidden"));
      document.getElementById(`${button.dataset.tab}-tab`)?.classList.remove("hidden");
    });
  });
}

// ─── Exclusive show/hide groups (connection type, delivery method) ─────────

function setupExclusiveGroup(selectId, attr) {
  const select = document.getElementById(selectId);
  if (!select) return;
  function sync() {
    document.querySelectorAll(`[${attr}]`).forEach((group) => {
      group.classList.toggle("hidden", group.getAttribute(attr) !== select.value);
    });
  }
  select.addEventListener("change", sync);
  sync();
}

// ─── Live logs ─────────────────────────────────────────────────────────────

function renderLogs(logs) {
  const target = document.getElementById("log-list");
  if (!target) return;
  const selected = new Set([...document.querySelectorAll(".log-select:checked")].map((item) => item.closest(".log-entry")?.dataset.logId).filter(Boolean));
  if (!logs.length) {
    target.innerHTML = '<p class="p-4 text-sm text-slate-400">No logs yet.</p>';
    return;
  }
  target.innerHTML = logs.map((log, index) => {
    const id = logId(log, index);
    const text = logText(log);
    return `
    <article class="log-entry p-4" data-log-id="${escapeHtml(id)}" data-log-text="${escapeHtml(text)}">
      <div class="flex gap-3">
        <input type="checkbox" class="log-select mt-1 h-4 w-4 rounded border-slate-700 bg-slate-950" ${selected.has(id) ? "checked" : ""}>
        <div class="min-w-0 flex-1">
          <div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <p class="font-medium text-slate-100">${escapeHtml(log.message)}</p>
            <p class="text-xs text-slate-500">${escapeHtml(log.time)} | ${escapeHtml(log.level)}</p>
          </div>
          <pre class="mt-2 overflow-x-auto rounded-md bg-slate-950 p-3 text-xs text-slate-300">${escapeHtml(JSON.stringify(log.fields || {}, null, 2))}</pre>
        </div>
      </div>
    </article>
  `;
  }).join("");
}

function logId(log, index) {
  return `${log.time}|${log.level}|${log.message}|${index}`;
}

function logText(log) {
  return `${log.time} | ${log.level} | ${log.message}\n${JSON.stringify(log.fields || {}, null, 2)}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function refreshLogs() {
  const response = await fetch("/api/logs");
  if (!response.ok) return;
  const data = await response.json();
  renderLogs(data.logs || []);
  const status = data.status || {};
  const line = document.getElementById("status-line");
  if (line) {
    line.textContent = `${(status.connection_type || "mqtt").toUpperCase()}: ${Boolean(status.connected)} | Sent: ${status.sent || 0} | Error: ${status.last_error || "none"}`;
  }
}

// ─── FCM test (selected device or all) ────────────────────────────────────

async function sendFcmTest(mode) {
  const field = document.querySelector(".token-field");

  let entries = [];
  try {
    entries = JSON.parse(field?.querySelector(".token-values")?.value || "[]");
  } catch { /* ignore */ }

  const selectedToken = field?.dataset.selectedToken;

  if (mode === "all" && entries.length === 0) {
    showFcmTestStatus("No device tokens configured");
    return;
  }
  if (mode !== "all" && !selectedToken) {
    showFcmTestStatus("Select a device row first, or use Test all devices");
    return;
  }

  showFcmTestStatus("Sending test notification...");
  try {
    const body = mode === "all"
      ? { all: true, tokens: entries.map((e) => e.token).filter(Boolean) }
      : { token: selectedToken };

    const response = await fetch("/api/test-fcm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Test failed");
    showFcmTestStatus(`Sent ${result.sent ?? 1} test notification${(result.sent ?? 1) === 1 ? "" : "s"}`);
    refreshLogs();
  } catch (error) {
    showFcmTestStatus(error.message || "Test failed");
  }
}

function showFcmTestStatus(message) {
  const status = document.getElementById("fcm-test-status");
  if (!status) return;
  status.textContent = message;
  status.classList.remove("hidden");
}

// ─── Saved test payload (server-side) ────────────────────────────────────

async function saveCurrentPayload() {
  const input = document.getElementById("test-payload-input");
  if (!input) return;
  const raw = input.value.trim();
  if (!raw) {
    showTestPayloadStatus("Nothing to save — editor is empty", true);
    return;
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    showTestPayloadStatus(`Cannot save — invalid JSON: ${err.message}`, true);
    return;
  }
  const response = await fetch("/api/saved-payload", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(parsed),
  });
  if (response.ok) {
    showTestPayloadStatus("Payload saved");
  } else {
    showTestPayloadStatus("Save failed", true);
  }
}

// ─── Test payload tab ──────────────────────────────────────────────────────

const SAMPLE_PAYLOAD = document.getElementById("test-payload-input")?.value || "";

async function sendTestPayload() {
  const input = document.getElementById("test-payload-input");
  if (!input) return;

  let payload;
  try {
    payload = JSON.parse(input.value);
  } catch (err) {
    showTestPayloadStatus(`JSON parse error: ${err.message}`, true);
    return;
  }

  showTestPayloadStatus("Sending...");
  try {
    const response = await fetch("/api/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Request failed");
    showTestPayloadStatus("Payload sent — check logs for result");
    refreshLogs();
  } catch (err) {
    showTestPayloadStatus(`Error: ${err.message}`, true);
  }
}

function showTestPayloadStatus(message, isError = false) {
  const el = document.getElementById("test-payload-status");
  if (!el) return;
  el.textContent = message;
  el.classList.remove("hidden", "text-red-400", "text-blue-200");
  el.classList.add(isError ? "text-red-400" : "text-blue-200");
}

// ─── Log polling ───────────────────────────────────────────────────────────

let logRefreshMs = 3000;
let logRefreshPaused = false;
let logRefreshTimer = null;

function scheduleLogRefresh() {
  window.clearInterval(logRefreshTimer);
  if (!logRefreshPaused) {
    logRefreshTimer = window.setInterval(refreshLogs, logRefreshMs);
  }
}

async function copyText(text) {
  if (!text.trim()) { showCopyStatus("No logs selected"); return; }
  await navigator.clipboard.writeText(text);
  showCopyStatus("Copied");
}

function showCopyStatus(message) {
  const status = document.getElementById("copy-log-status");
  if (!status) return;
  status.textContent = message;
  status.classList.remove("hidden");
  window.setTimeout(() => status.classList.add("hidden"), 2000);
}

function selectedLogText() {
  return [...document.querySelectorAll(".log-select:checked")]
    .map((item) => item.closest(".log-entry")?.dataset.logText || "")
    .filter(Boolean).join("\n\n");
}

function visibleLogText() {
  return [...document.querySelectorAll(".log-entry")]
    .map((item) => item.dataset.logText || "")
    .filter(Boolean).join("\n\n");
}

// ─── Init ──────────────────────────────────────────────────────────────────

document.querySelectorAll(".chip-field").forEach(setupChipField);
document.querySelectorAll(".token-field").forEach(setupTokenField);
document.querySelectorAll(".kv-field").forEach(setupKvField);
setupSeverityChecks();
setupTabs();
setupExclusiveGroup("connection-type", "data-connection-type");
setupExclusiveGroup("delivery-method", "data-delivery-method");

document.getElementById("refresh-logs")?.addEventListener("click", refreshLogs);
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
document.getElementById("copy-selected-logs")?.addEventListener("click", () => copyText(selectedLogText()));
document.getElementById("copy-visible-logs")?.addEventListener("click", () => copyText(visibleLogText()));
document.getElementById("log-refresh-interval")?.addEventListener("change", (event) => {
  logRefreshMs = Number(event.target.value) || 3000;
  scheduleLogRefresh();
});
document.getElementById("toggle-log-refresh")?.addEventListener("click", (event) => {
  logRefreshPaused = !logRefreshPaused;
  event.target.textContent = logRefreshPaused ? "Resume" : "Pause";
  scheduleLogRefresh();
});
scheduleLogRefresh();
