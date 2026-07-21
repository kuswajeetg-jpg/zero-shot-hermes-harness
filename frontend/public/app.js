// Analyst Phase 1 — vanilla JS, zero build.
"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  token: localStorage.getItem("analyst_token"),
  user: null,
  source: null,
  lastAsk: null,
};

// ---------- utils ----------
function setText(id, text) {
  const el = $(`${id}`);
  if (!el) return;
  if (!text) el.hidden = true;
  else { el.textContent = text; el.hidden = false; }
}

function header(path, method = "GET", body) {
  const h = { "content-type": "application/json" };
  if (state.token) h["authorization"] = `Bearer ${state.token}`;
  return { path, method, body, headers: h };
}

async function api(input) {
  const res = await fetch(input.path, {
    method: input.method,
    headers: input.headers,
    body: input.body ? JSON.stringify(input.body) : undefined,
  });
  const text = await res.text();
  let body;
  try { body = text ? JSON.parse(text) : {}; } catch { body = { raw: text }; }
  if (!res.ok) {
    const msg = body?.detail?.message || body?.detail || body?.raw || `HTTP ${res.status}`;
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return body;
}

function viewer() {
  if (!state.token) { showAuth(); return; }
  $("analyse-view").hidden = false;
  $("auth-view").hidden = true;
  $("user-email").textContent = state.user?.email || "";
}

function showAuth(mode) {
  state.token = state.user = state.source = state.lastAsk = null;
  localStorage.removeItem("analyst_token");
  $("analyse-view").hidden = true;
  $("auth-view").hidden = false;
  const form = $("auth-form");
  form.reset();
  $("auth-error").hidden = true;
  $("auth-submit").textContent = mode === "register" ? "Register" : "Login";
  $("auth-toggle").textContent = mode === "register" ? "Have an account? Login" : "Create account";
  $("auth-form").dataset.mode = mode || "login";
}

// ---------- auth ----------
async function submitAuth(e) {
  e.preventDefault();
  const errBox = $("auth-error");
  errBox.hidden = true;

  const email = $("auth-email").value.trim();
  const password = $("auth-password").value;
  const mode = $("auth-form").dataset.mode || "login";
  const path = mode === "register" ? "/api/auth/register" : "/api/auth/login";

  $("auth-submit").disabled = true;
  $("auth-submit").textContent = mode === "register" ? "Creating…" : "Logging in…";
  try {
    const body = await api({ path, method: "POST", headers: { "content-type": "application/json" }, body: { email, password } });
    state.token = body.data?.access_token;
    state.user = { email };
    localStorage.setItem("analyst_token", state.token);
    viewer();
    renderSources();
  } catch (err) {
    setText("auth-error", err.message);
  } finally {
    $("auth-submit").disabled = false;
    $("auth-submit").textContent = mode === "register" ? "Register" : "Login";
  }
}

$("auth-toggle").addEventListener("click", () => {
  const mode = ($("auth-form").dataset.mode || "login") === "login" ? "register" : "login";
  $("auth-form").reset();
  $("auth-error").hidden = true;
  $("auth-submit").textContent = mode === "register" ? "Register" : "Login";
  $("auth-toggle").textContent = mode === "register" ? "Have an account? Login" : "Create account";
  $("auth-form").dataset.mode = mode;
});

$("auth-form").addEventListener("submit", submitAuth);

$("logout-btn").addEventListener("click", showAuth);

// ---------- sources ----------
function chips(sources, activeId) {
  const strip = $("source-strip");
  strip.innerHTML = "";
  if (!sources?.length) {
    strip.innerHTML = '<span class="muted">No sources yet.</span>';
    return;
  }
  for (const s of sources) {
    const c = document.createElement("button");
    c.className = "chip" + (s.id === activeId ? " active" : "");
    c.textContent = s.display_name || s.id;
    c.title = s.kind === "csv" ? "Local CSV upload" : "ICP-local MsSQL";
    c.addEventListener("click", () => pickSource(s));
    strip.appendChild(c);
  }
}

function pickSource(s) {
  state.source = s;
  renderSources();
  renderSchemaForSource(s);
}

function renderSources() {
  const local = getLocalSource();
  const chipsArr = [];
  if (local) chipsArr.push({ id: local.id, display_name: local.name, kind: "csv" });
  chips(chipsArr, state.source?.id);
}

function getLocalSource() {
  const raw = localStorage.getItem("analyst_local_source");
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

function setLocalSource(s) { localStorage.setItem("analyst_local_source", JSON.stringify(s)); }

function renderSchemaForSource(source) {
  const tbody = $("schema-body");
  const meta = $("schema-meta");
  const table = $("schema-table");
  const empty = $("schema-empty");
  tbody.innerHTML = "";
  meta.textContent = "";
  table.hidden = true;
  empty.hidden = true;

  const schema = source?.schema;
  if (!schema || !schema.length) {
    empty.hidden = false;
    return;
  }
  table.hidden = false;
  for (const col of schema) {
    const tr = document.createElement("tr");
    const tdName = document.createElement("td");
    tdName.textContent = col.name;
    const tdType = document.createElement("td");
    tdType.textContent = col.type || "";
    const tdPii = document.createElement("td");
    tdPii.innerHTML = col.pii ? `<span class="pill">PII</span>` : '<span class="muted">—</span>';
    tr.append(tdName, tdType, tdPii);
    tbody.appendChild(tr);
  }
  meta.textContent = `${schema.length} columns · ${source.rows ?? "?"} rows`;
}

// ---------- upload ----------
$("upload-trigger").addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const status = $("upload-status");
  const errBox = $("upload-error");
  errBox.hidden = true;
  status.hidden = false;
  status.textContent = `Uploading ${file.name}…`;
  try {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/upload", { method: "POST", body: form, headers: { "authorization": `Bearer ${state.token}` } });
    const text = await res.text();
    let body;
    try { body = JSON.parse(text); } catch { body = { raw: text }; }
    if (!res.ok) throw new Error(body?.detail?.message || body?.raw || `Upload failed: ${res.status}`);
    const data = body.data || {};
    const source = {
      id: `csv_${data.upload_id}`,
      name: file.name,
      kind: "csv",
      schema: data.schema,
      rows: data.rows,
      warnings: data.warnings,
    };
    setLocalSource(source);
    setText("upload-status", `Uploaded ${file.name}`);
    state.source = source;
    renderSources();
    renderSchemaForSource(source);
  } catch (err) {
    setText("upload-error", err.message);
    setText("upload-status", "");
  } finally {
    $("file-input").value = "";
  }
});

// ---------- ask ----------
async function submitQuestion() {
  const source = state.source || getLocalSource();
  if (!source) { setText("ask-error", "Select or upload a source first."); return; }

  const errBox = $("ask-error");
  const q = $("question").value.trim();
  errBox.hidden = true;
  if (!q) { setText("ask-error", "Please enter a question."); return; }

  const btn = $("ask-btn");
  const status = $("ask-status");
  btn.disabled = true;
  setText("ask-status", "Running…");
  try {
    const bodyInput = { session_token: source.id, source_id: source.id, question: q };
    const body = await api({ path: "/api/ask", method: "POST", headers: { "content-type": "application/json" }, body: bodyInput });
    const data = body.data || {};
    state.lastAsk = { run_id: data.run_id, source_id: source.id };

    $("answer-panel").hidden = false;
    setText("reply-text", data.answer_text || "(no text)");
    setText("run-meta", `run ${data.run_id} · latency ${data.latency_ms ?? "?"}ms${data.fallback_mode ? " · fallback mode" : ""}`);

    // sheet
    const cols = data?.query_result?.columns;
    const rows = data?.query_result?.rows || [];
    renderData(Array.isArray(cols) ? cols : [], rows);

    // chart
    renderChart(data.chart_spec);

    // fallback badge
    $("fallback-badge").hidden = !data.fallback_mode;
  } catch (err) {
    setText("ask-error", err.message);
    $("answer-panel").hidden = true;
  } finally {
    btn.disabled = false;
    setText("ask-status", "");
  }
}

$("ask-btn").addEventListener("click", submitQuestion);
$("question").addEventListener("keydown", (e) => { if (e.key === "Enter") submitQuestion(); });

function renderData(columns, rows) {
  const thead = $("data-head");
  const tbody = $("data-body");
  const table = $("data-table");
  const placeholder = $("table-placeholder");
  thead.innerHTML = "";
  tbody.innerHTML = "";

  if (!columns.length) { table.hidden = true; placeholder.hidden = false; return; }
  placeholder.hidden = true;
  table.hidden = false;

  const tr = document.createElement("tr");
  for (const c of columns) {
    const th = document.createElement("th");
    th.textContent = c;
    tr.appendChild(th);
  }
  thead.appendChild(tr);

  const limit = rows.slice(0, 200);
  for (const row of limit) {
    const tr = document.createElement("tr");
    for (const c of columns) {
      const td = document.createElement("td");
      td.textContent = row?.[c] ?? "";
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  if (rows.length > 200) {
    const info = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = columns.length;
    td.className = "meta";
    td.textContent = `Showing 200 of ${rows.length} rows. Export for the full set.`;
    info.appendChild(td);
    tbody.appendChild(info);
  }
}

// ---------- chart ----------
function renderChart(spec) {
  const canvas = $("chart-canvas");
  const placeholder = $("chart-placeholder");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!spec || !spec.type) {
    canvas.hidden = true;
    placeholder.hidden = false;
    return;
  }
  canvas.hidden = false;
  placeholder.hidden = true;

  // Baseline bar/area/line without a charting library.
  const chart = JSON.stringify(spec).slice(0, 140);
  ctx.fillStyle = "#e8eaf0";
  ctx.fillText(`Chart ${spec.type} · ${chart}`, 16, 24);
  ctx.strokeStyle = "#2b3245";
  ctx.strokeRect(16, 36, canvas.width - 32, canvas.height - 52);
  ctx.fillStyle = "#9aa3b2";
  ctx.fillText("Chart canvas: wire backend chart spec or plug a renderer.", 24, 66);
}

// ---------- export ----------
async function doExport(fmt) {
  if (!state.lastAsk?.run_id) { alert("Run a question first."); return; }
  const wrap = $("export-link-wrap");
  wrap.textContent = "Preparing…";
  try {
    const input = header("/api/export", "POST", { query_run_id: state.lastAsk.run_id, format: fmt });
    const body = await api(input);
    const data = body.data || {};
    if (data.url) wrap.innerHTML = `Saved · expires ${data.expires_at || "soon"} · <a class="link" href="${data.url}" target="_blank">download</a>`;
    else wrap.textContent = "No export URL returned.";
  } catch (err) {
    wrap.textContent = err.message;
  }
}
$("export-csv").addEventListener("click", () => doExport("csv"));
$("export-md").addEventListener("click", () => doExport("md"));

// ---------- init ----------
(function init() {
  if (state.token) viewer();
  else showAuth();
});
