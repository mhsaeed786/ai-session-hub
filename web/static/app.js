"use strict";

const API = "";
let currentSession = null;
let browsePage = 1;
let searchPage = 1;

function navigate(view) {
  ["dashboard", "browse", "session", "search", "categorize"].forEach(v => {
    document.getElementById("view-" + v).classList.add("hidden");
  });
  document.getElementById("view-" + view).classList.remove("hidden");
  if (view === "dashboard") loadStats();
  if (view === "browse") { loadToolFilters(); loadSessions(1); }
  if (view === "categorize") loadCategoryStats();
  window.scrollTo(0, 0);
}

function esc(s) {
  return (s || "").toString().replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

async function api(path, opts) {
  const res = await fetch(API + path, opts);
  return res.json();
}

function fmtSize(b) {
  if (!b) return "—";
  if (b < 1024) return b + " B";
  if (b < 1048576) return (b / 1024).toFixed(1) + " KB";
  return (b / 1048576).toFixed(1) + " MB";
}

// ---------- Dashboard ----------
async function loadStats() {
  const s = await api("/api/stats");
  document.getElementById("stats-grid").innerHTML = `
    <div class="stat-card"><div class="num">${s.total_sessions}</div><div class="label">Sessions</div></div>
    <div class="stat-card"><div class="num">${s.total_messages}</div><div class="label">Messages</div></div>
    <div class="stat-card"><div class="num">${s.tools_with_data}</div><div class="label">Tools</div></div>
    <div class="stat-card"><div class="num">${s.total_size_mb} MB</div><div class="label">Total size</div></div>`;
  const recent = s.recent_sessions.map(renderSessionCard).join("");
  document.getElementById("recent-sessions").innerHTML =
    recent || '<p class="muted">No sessions yet — hit <b>Sync</b> to scan your tools.</p>';
}

function renderSessionCard(x) {
  const cat = x.category ? `<span class="badge cat">${esc(x.category)}</span>` : "";
  const tool = `<span class="badge tool">${esc(x.tool)}</span>`;
  const date = x.started_at ? new Date(x.started_at).toLocaleString() : "";
  const count = x.message_count ? `${x.message_count} msgs` : "";
  return `<div class="session-card" onclick="openSession('${esc(x.id)}')">
    <div class="row1"><span class="title">${esc(x.title) || "(untitled)"}</span>${tool}${cat}</div>
    <div class="meta"><span>${esc(x.tool)}</span><span>${esc(date)}</span><span>${count}</span>
    <span>${esc(x.project_path) || ""}</span></div></div>`;
}

// ---------- Browse ----------
async function loadToolFilters() {
  const s = await api("/api/stats");
  const tools = s.by_tool.map(t => `<option value="${esc(t.tool)}">${esc(t.tool)} (${t.count})</option>`).join("");
  document.getElementById("filter-tool").innerHTML = `<option value="">All tools</option>${tools}`;
}

async function loadSessions(page) {
  browsePage = page || 1;
  const params = new URLSearchParams({ page: browsePage, per_page: 25 });
  const tool = document.getElementById("filter-tool").value;
  const cat = document.getElementById("filter-category").value;
  const from = document.getElementById("filter-from").value;
  const to = document.getElementById("filter-to").value;
  const proj = document.getElementById("filter-project").value;
  if (tool) params.set("tool", tool);
  if (cat) params.set("category", cat);
  if (from) params.set("date_from", from);
  if (to) params.set("date_to", to);
  if (proj) params.set("project", proj);

  const d = await api("/api/sessions?" + params.toString());
  document.getElementById("browse-sessions").innerHTML =
    d.sessions.length ? d.sessions.map(renderSessionCard).join("")
                      : '<p class="muted">No sessions match.</p>';

  const pages = d.total_pages || 1;
  let p = "";
  for (let i = 1; i <= pages && i <= 20; i++) {
    p += `<button class="${i === d.page ? "active" : ""}" onclick="loadSessions(${i})">${i}</button>`;
  }
  document.getElementById("browse-pagination").innerHTML =
    `<button onclick="loadSessions(1)">«</button>${p}<button onclick="loadSessions(${d.page + 1})">»</button>`;
}

async function loadCategoryStats() {
  const s = await api("/api/stats");
  document.getElementById("category-stats").innerHTML =
    (s.by_category || []).map(c => `<span class="chip">${esc(c.category)} · ${c.count}</span>`).join("") ||
    '<span class="muted">Run Categorize to populate.</span>';
}

// ---------- Session detail ----------
async function openSession(id) {
  const d = await api("/api/sessions/" + encodeURIComponent(id));
  currentSession = d.session;
  const s = d.session;
  document.getElementById("session-header").innerHTML = `
    <h1>${esc(s.title) || "(untitled)"}</h1>
    <div class="meta">
      <span class="badge tool">${esc(s.tool)}</span>
      ${s.category ? `<span class="badge cat">${esc(s.category)}</span>` : ""}
      ${s.tags ? `<span class="muted">${esc(s.tags)}</span>` : ""}
      <div style="margin-top:8px">${esc(s.project_path) || ""} · ${s.started_at || ""} ·
      ${s.message_count} msgs · ${fmtSize(s.file_size_bytes)}</div>
    </div>
    <div style="margin-top:12px; display:flex; gap:8px; flex-wrap:wrap; align-items:center">
      <input id="rename-input" value="${esc(s.title) || ""}" placeholder="Rename…"
        style="padding:6px 10px;border-radius:6px;border:1px solid var(--border);background:var(--panel-2);color:var(--text);width:260px">
      <input id="cat-input" value="${esc(s.category) || ""}" placeholder="Category…"
        style="padding:6px 10px;border-radius:6px;border:1px solid var(--border);background:var(--panel-2);color:var(--text);width:140px">
      <button class="btn btn-sm" onclick="saveMeta()">Save rename/category</button>
    </div>`;

  document.getElementById("message-thread").innerHTML = d.messages.map(renderMessage).join("") ||
    '<p class="muted">(no readable messages in this session)</p>';
  document.getElementById("master-prompt-box").style.display = "none";
  document.getElementById("export-panel").style.display = "none";
  navigate("session");
}

function renderMessage(m) {
  const role = m.role === "tool" ? "tool" : m.role === "system" ? "system" : m.role;
  const cls = m.content_type === "thinking" ? "thinking" : role;
  return `<div class="msg ${esc(cls)}">
    <div class="mrole">${esc(role)}</div>${esc(m.content_text) || ""}
    ${m.model ? `<div class="mtools">${esc(m.model)}</div>` : ""}
  </div>`;
}

async function saveMeta() {
  const body = {
    title: document.getElementById("rename-input").value,
    category: document.getElementById("cat-input").value,
  };
  await api("/api/sessions/" + encodeURIComponent(currentSession.id), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  currentSession.title = body.title;
  currentSession.category = body.category;
  document.getElementById("session-header").querySelector("h1").textContent = body.title || "(untitled)";
}

// ---------- Master prompt ----------
async function showMasterPrompt() {
  const d = await api(`/api/sessions/${encodeURIComponent(currentSession.id)}/master-prompt?mode=replicate`);
  const box = document.getElementById("master-prompt-box");
  box.textContent = d.master_prompt;
  box.style.display = "block";
  box.scrollIntoView();
}

// ---------- Export ----------
async function openExport() {
  const box = document.getElementById("export-panel");
  const targets = await api("/api/targets");
  box.innerHTML = `
    <h3>Export this session to another tool</h3>
    <select id="export-target">${targets.tools.map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join("")}</select>
    <button class="btn btn-sm" onclick="runExport()">Export</button>
    <div id="export-result" class="muted" style="margin-top:8px"></div>`;
  box.style.display = "block";
}

async function runExport() {
  const target = document.getElementById("export-target").value;
  const r = await api("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: currentSession.id, target_tool: target }),
  });
  document.getElementById("export-result").textContent =
    r.status === "ok" ? `✓ Exported to ${target} → ${r.path}` : `✗ ${r.error}`;
}

// ---------- Categorize ----------
async function runCategorize() {
  const box = document.getElementById("categorize-result");
  box.textContent = "Working…";
  const r = await api("/api/categorize", { method: "POST" });
  box.textContent = `✓ Updated ${r.updated} sessions (category + title).`;
  loadCategoryStats();
}

// ---------- Search ----------
async function doSearch(q) {
  if (!q) return;
  searchPage = 1;
  await loadSearch(q);
}

async function loadSearch(q) {
  const d = await api(`/api/search?q=${encodeURIComponent(q)}&page=${searchPage}&per_page=20`);
  document.getElementById("search-title").textContent = `Search: ${q} (${d.total})`;
  document.getElementById("search-results").innerHTML = d.results.map(r => `
    <div class="result-card" onclick="openSession('${esc(r.session_fk)}')">
      <div><b>${esc(r.session_title)}</b> <span class="badge tool">${esc(r.tool)}</span>
      <span class="badge cat">${esc(r.role)}</span></div>
      <div class="rtext">${esc(r.content_text)}</div>
    </div>`).join("") || '<p class="muted">No results.</p>';
  document.getElementById("search-pagination").innerHTML =
    d.total_pages > 1 ? `<button onclick="searchPage--;loadSearch('${esc(q)}')">Prev</button>
    <button onclick="searchPage++;loadSearch('${esc(q)}')">Next</button>` : "";
  navigate("search");
}

// ---------- Sync ----------
async function triggerSync() {
  const btn = document.getElementById("sync-btn");
  btn.disabled = true; btn.textContent = "⟳ Syncing…";
  const r = await api("/api/sync", { method: "POST" });
  btn.disabled = false; btn.textContent = "⟳ Sync";
  if (r.status === "ok") {
    alert("Sync complete.\n" + Object.entries(r.results)
      .map(([t, s]) => `${t}: ${s.found} found, ${s.new} new`).join("\n"));
  } else {
    alert("Sync error: " + (r.error || "unknown"));
  }
  loadStats();
}

// ---------- Init ----------
navigate("dashboard");
