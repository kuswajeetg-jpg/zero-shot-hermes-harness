// Production Data Intelligence Command Center — Bilingual, Multi-CSV, & Multi-Chart Engine.
"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  token: localStorage.getItem("analyst_token"),
  user: null,
  sources: [],
  activeSource: null,
  lastAsk: null,
  lang: localStorage.getItem("analyst_lang") || "en",
  activeTab: "dashboard",
  currentRows: [],
  currentCols: [],
  currentSpec: null,
  selectedChartType: "bar",
  // field selection state
  allowedFields: null,
};

// ---------- Bilingual Dictionary ----------
const dict = {
  en: {
    navTitle: "UP Police Data Intelligence Agent",
    authTitle: "Analyst Portal Login",
    authSub: "UP Police Autonomous Data Intelligence Portal",
    labelEmail: "Email Address",
    labelPass: "Password",
    btnLogin: "Login",
    btnRegister: "Create Account",
    kpiSources: "Active Datasets",
    kpiRows: "Total Dataset Records",
    kpiEngine: "Query Execution Engine",
    kpiSecurity: "Privacy & Shielding",
    hdrSources: "Datasets & Data Sources",
    hdrSchema: "Schema Inspector",
    hdrAsk: "Ask Analytical Question",
    hdrAnswer: "Executive Intelligence Answer",
    hdrTable: "Structured Data Results",
    hdrChart: "Visual Analytics Chart",
    btnAddCsv: "+ Add CSV Dataset",
    askPlaceholder: "e.g., show top 5 records by city or average metrics",
    askBtn: "Ask Question",
    thCol: "Column",
    thType: "Type",
    thPii: "Privacy Flag",
    noSources: "No CSV datasets uploaded yet.",
    exportCsv: "Export CSV",
    exportMd: "Export Report",
  },
  hi: {
    navTitle: "उत्तर प्रदेश पुलिस डेटा इंटेलिजेंस एजेंट",
    authTitle: "विश्लेषक पोर्टल लॉगिन",
    authSub: "उत्तर प्रदेश पुलिस स्वायत्त डेटा विश्लेषक पोर्टल",
    labelEmail: "ईमेल पता",
    labelPass: "पासवर्ड",
    btnLogin: "लॉगिन करें",
    btnRegister: "नया खाता बनाएं",
    kpiSources: "सक्रिय डेटासेट",
    kpiRows: "कुल डेटा रिकॉर्ड",
    kpiEngine: "क्वेरी एक्ज़ीक्यूशन इंजन",
    kpiSecurity: "गोपनीयता एवं सुरक्षा",
    hdrSources: "डेटासेट एवं डेटा स्रोत",
    hdrSchema: "डेटा संरचना (स्कीमा)",
    hdrAsk: "विश्लेषणात्मक प्रश्न पूछें",
    hdrAnswer: "कार्यकारी इंटेलिजेंस उत्तर",
    hdrTable: "संरचित डेटा परिणाम",
    hdrChart: "दृश्य आलेख (चार्ट) विश्लेषण",
    btnAddCsv: "+ CSV डेटासेट जोड़ें",
    askPlaceholder: "उदा., शहर के अनुसार शीर्ष 5 रिकॉर्ड दिखाएं या औसत डेटा",
    askBtn: "प्रश्न पूछें",
    thCol: "फ़ील्ड (कॉलम)",
    thType: "प्रकार",
    thPii: "गोपनीयता ध्वज",
    noSources: "अभी तक कोई CSV डेटासेट अपलोड नहीं हुआ है।",
    exportCsv: "CSV डाउनलोड",
    exportMd: "रिपोर्ट डाउनलोड",
    answerColumnAnalysis: "कॉलम विश्लेषण:",
    answerNumericSummary: "संख्या सारांश:",
    answerCategoryDistribution: "श्रेणी वितरण:",
    answerPublished: "प्रकट हुआ",
    answerTotal: "कुल",
    answerAverage: "औसत",
    answerMin: "न्यूनतम",
    answerMax: "अधिकतम",
    answerPeakRecord: "शीर्ष रिकॉर्ड",
    chartDefaultTitle: "विश्लेषण",
    concentrationAlert: "केंद्रीकरण अलर्ट",
    accountsFor: "कुल मॉल के अनुसार",
    criticalVolume: "महत्वपूर्ण आयतन",
    spikeDetected: "स्पाइक पाया गया",
    approachesDataSetBaseline: "डेटासेट बेसलाइन तक पहुंचता है या उससे अधिक",
  }
};

function applyLanguage(lang) {
  state.lang = lang;
  localStorage.setItem("analyst_lang", lang);
  const t = dict[lang] || dict.en;

  $("txt-nav-title").textContent = t.navTitle;
  $("txt-auth-title").textContent = t.authTitle;
  $("txt-auth-sub").textContent = t.authSub;
  $("txt-label-email").textContent = t.labelEmail;
  $("txt-label-pass").textContent = t.labelPass;
  $("auth-submit").textContent = t.btnLogin;
  $("auth-toggle").textContent = t.btnRegister;
  
  $("kpi-lbl-sources").textContent = t.kpiSources;
  $("kpi-lbl-rows").textContent = t.kpiRows;
  $("kpi-lbl-engine").textContent = t.kpiEngine;
  $("kpi-lbl-security").textContent = t.kpiSecurity;

  $("txt-hdr-sources").textContent = t.hdrSources;
  $("txt-hdr-schema").textContent = t.hdrSchema;
  $("txt-hdr-ask").textContent = t.hdrAsk;
  $("txt-hdr-answer").textContent = t.hdrAnswer;
  $("txt-hdr-table").textContent = t.hdrTable;
  $("txt-hdr-chart").textContent = t.hdrChart;

  $("upload-trigger").textContent = t.btnAddCsv;
  $("question").placeholder = t.askPlaceholder;
  $("ask-btn").textContent = t.askBtn;
  $("th-col").textContent = t.thCol;
  $("th-type").textContent = t.thType;
  $("th-pii").textContent = t.thPii;
  $("export-csv").textContent = t.exportCsv;
  $("export-md").textContent = t.exportMd;

  $("lang-en").classList.toggle("active", lang === "en");
  $("lang-hi").classList.toggle("active", lang === "hi");

  if (state.lastAsk && state.currentRows.length) {
    rerenderAnswerPanel(state.lastAsk.question || $("question").value, lang);
  }
}

function rerenderAnswerPanel(question, lang) {
  const t = dict[lang] || dict.en;
  const rows = state.currentRows;
  const cols = state.currentCols;
  if (!rows.length || !cols.length) return;

  const selectedType = state.selectedChartType || "bar";
  // ensure chart header contains axis controls
  ensureChartAxisSelectors();
  populateChartAxisSelectors(cols);

  const spec = state.currentSpec || { chart_type: selectedType, encoding: {} };
  const xSel = $("chart-x-axis");
  const ySel = $("chart-y-axis");

  // override encoding from selectors when available
  const effectiveSpec = { ...spec };
  if (xSel && ySel && xSel.value && ySel.value) {
    effectiveSpec.encoding = effectiveSpec.encoding || {};
    effectiveSpec.encoding.x_axis = effectiveSpec.encoding.x_axis || xSel.value;
    effectiveSpec.encoding.y_axis = effectiveSpec.encoding.y_axis || ySel.value;
  } else {
    effectiveSpec.encoding = effectiveSpec.encoding || {};
    if (!effectiveSpec.encoding.x_axis && cols[0]) effectiveSpec.encoding.x_axis = cols[0];
    if (!effectiveSpec.encoding.y_axis && cols[1]) effectiveSpec.encoding.y_axis = cols[1];
  }

  const text = _buildAnswerText(question, rows, cols, t);
  $("reply-text").textContent = text;
  renderData(cols, rows);
  updateChartTypeButtons(selectedType);
  renderChart(selectedType, effectiveSpec, rows, cols);
}

// ---------- Tab Switcher ----------
function switchTab(tabName) {
  state.activeTab = tabName;
  $("tab-dashboard").classList.toggle("active", tabName === "dashboard");
  $("tab-schema").classList.toggle("active", tabName === "schema");
  $("tab-audit").classList.toggle("active", tabName === "audit");

  $("view-tab-dashboard").hidden = tabName !== "dashboard";
  $("view-tab-schema").hidden = tabName !== "schema";
  $("view-tab-audit").hidden = tabName !== "audit";
}

$("tab-dashboard").addEventListener("click", () => switchTab("dashboard"));
$("tab-schema").addEventListener("click", () => switchTab("schema"));
$("tab-audit").addEventListener("click", () => switchTab("audit"));

// ---------- API Wrapper ----------
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

// ---------- Views & Navigation ----------
function viewer() {
  if (!state.token) { showAuth(); return; }
  $("analyse-view").hidden = false;
  $("auth-view").hidden = true;
  $("user-email").textContent = state.user?.email || "";
  loadUploads();
}

function showAuth(mode) {
  state.token = state.user = state.sources = state.activeSource = state.lastAsk = null;
  localStorage.removeItem("analyst_token");
  $("analyse-view").hidden = true;
  $("auth-view").hidden = false;
  const form = $("auth-form");
  form.reset();
  $("auth-error").hidden = true;
  $("auth-submit").textContent = mode === "register" ? (dict[state.lang]?.btnRegister || "Create Account") : (dict[state.lang]?.btnLogin || "Login");
}

let authMode = "login";
$("auth-toggle").addEventListener("click", () => {
  authMode = authMode === "login" ? "register" : "login";
  $("auth-submit").textContent = authMode === "register" ? (dict[state.lang]?.btnRegister || "Create Account") : (dict[state.lang]?.btnLogin || "Login");
  $("auth-toggle").textContent = authMode === "register" ? "Switch to Login" : (dict[state.lang]?.btnRegister || "Create Account");
});

$("auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = $("auth-email").value.trim();
  const password = $("auth-password").value.trim();
  const errBox = $("auth-error");
  errBox.hidden = true;
  if (!email || !password) { errBox.textContent = "Please enter email and password."; errBox.hidden = false; return; }

  const path = authMode === "register" ? "/api/auth/register" : "/api/auth/login";
  try {
    const res = await api({ path, method: "POST", headers: { "content-type": "application/json" }, body: { email, password } });
    if (authMode === "register") {
      const loginRes = await api({ path: "/api/auth/login", method: "POST", headers: { "content-type": "application/json" }, body: { email, password } });
      state.token = loginRes.data.access_token;
    } else {
      state.token = res.data.access_token;
    }
    state.user = { email };
    localStorage.setItem("analyst_token", state.token);
    viewer();
  } catch (err) {
    errBox.textContent = err.message; errBox.hidden = false;
  }
});

$("logout-btn").addEventListener("click", () => showAuth("login"));

// ---------- Multi-CSV Datasets Manager ----------
async function loadUploads() {
  try {
    const res = await api(header("/api/uploads", "GET"));
    const items = res.data?.items || [];
    state.sources = items;
    renderSourceStrip(items);
    updateKpis();
    if (items.length > 0 && !state.activeSource) {
      selectSource(items[0]);
    }
  } catch (err) {
    console.error("Failed to load sources:", err);
  }
}

async function deleteDataset(uploadId, e) {
  if (e) e.stopPropagation();
  if (!confirm("Are you sure you want to remove this dataset?")) return;
  try {
    await api(header(`/api/uploads/${uploadId}`, "DELETE"));
    if (state.activeSource?.upload_id === uploadId) {
      state.activeSource = null;
    }
    await loadUploads();
    if (state.sources.length === 0) {
      renderSchema([], 0);
    }
  } catch (err) {
    alert("Failed to delete dataset: " + err.message);
  }
}

function renderSourceStrip(items) {
  const strip = $("source-strip");
  strip.innerHTML = "";
  if (!items.length) {
    strip.innerHTML = `<div class="hint">${dict[state.lang]?.noSources || "No CSV datasets uploaded yet."}</div>`;
    return;
  }
  items.forEach((item) => {
    const chip = document.createElement("div");
    chip.className = `source-chip ${state.activeSource?.upload_id === item.upload_id ? "active" : ""}`;
    chip.innerHTML = `
      <span style="flex: 1; display: flex; align-items: center; gap: 6px;">
        📄 ${item.filename} <span style="opacity: 0.6; font-size: 0.75rem;">(${item.rows.toLocaleString()} rows)</span>
      </span>
      <button class="del-btn" title="Remove Dataset" style="background: transparent; border: none; color: #f43f5e; padding: 2px 6px; font-size: 0.85rem; margin-top: 0; box-shadow: none; cursor: pointer;">🗑️</button>
    `;
    chip.addEventListener("click", () => selectSource(item));
    const delBtn = chip.querySelector(".del-btn");
    delBtn.addEventListener("click", (e) => deleteDataset(item.upload_id, e));
    strip.appendChild(chip);
  });
}

function selectSource(source) {
  state.activeSource = source;
  renderSourceStrip(state.sources);
  renderSchema(source.schema || [], source.rows || 0);
  // Update suggested questions
  if (source.suggested_questions && source.suggested_questions.length > 0) {
    const qInput = $("question");
    if (qInput) qInput.placeholder = `e.g. ${source.suggested_questions[0]}`;

    const sampleList = $("sample-pills");
    if (sampleList) {
      sampleList.innerHTML = "";
      source.suggested_questions.forEach(q => {
        const btn = document.createElement("div");
        btn.className = "sample-pill";
        btn.textContent = `✨ ${q}`;
        btn.onclick = () => quickAsk(q);
        sampleList.appendChild(btn);
      });
    }
  }
}

function renderSchema(schema, totalRows) {
  const table = $("schema-table");
  const body = $("schema-body");
  const empty = $("schema-empty");
  const meta = $("schema-meta");
  body.innerHTML = "";

  if (!schema.length) {
    table.hidden = true; empty.hidden = false; meta.textContent = ""; return;
  }
  empty.hidden = true; table.hidden = false;

  schema.forEach((col) => {
    const tr = document.createElement("tr");
    const isPii = col.pii === true || col.pii === "true";
    tr.innerHTML = `
      <td style="font-weight: 600;">${col.name}</td>
      <td style="color: var(--text-muted);">${col.type || "text"}</td>
      <td>${isPii ? '<span class="pii-badge">PII Protected</span>' : '<span class="safe-badge">Safe</span>'}</td>
    `;
    body.appendChild(tr);
  });

  meta.textContent = `${schema.length} Columns · ${totalRows.toLocaleString()} Total Records`;
}

// ---------- Post-upload field selector ----------
function renderFieldSelector(schema) {
  const panel = $("field-selector");
  const box = $("field-checkboxes");
  if (!panel || !box) return;
  box.innerHTML = "";
  if (!schema || !schema.length) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  schema.forEach((col) => {
    const id = `field-${col.name}`;
    const label = document.createElement("label");
    label.style.display = "flex";
    label.style.alignItems = "center";
    label.style.gap = "8px";
    label.style.marginBottom = "6px";
    label.innerHTML = `
      <input type="checkbox" class="field-check" value="${col.name}" checked style="accent-color: #3b82f6;" />
      <span style="font-size: 0.9rem;">${col.name} <span style="opacity: 0.6; font-size: 0.75rem;">(${col.type || "text"})</span></span>
    `;
    box.appendChild(label);
  });
}

function selectedFieldsFromUI() {
  const checks = document.querySelectorAll(".field-check:checked");
  const vals = Array.from(checks).map((el) => el.value);
  return vals.length ? vals : null;
}

function applyAllowedFields(fields) {
  if (!fields) return;
  document.querySelectorAll(".field-check").forEach((el) => {
    el.checked = fields.includes(el.value);
  });
}

function updateKpis() {
  const totalFiles = state.sources.length;
  const totalRows = state.sources.reduce((acc, curr) => acc + (curr.rows || 0), 0);
  $("kpi-val-sources").textContent = `${totalFiles} File${totalFiles === 1 ? "" : "s"}`;
  $("kpi-val-rows").textContent = `${totalRows.toLocaleString()} Rows`;
}

// ---------- Upload Handler ----------
$("upload-trigger").addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", async (e) => {
  const files = e.target.files;
  if (!files || !files.length) return;
  const status = $("upload-status");
  const errBox = $("upload-error");
  errBox.hidden = true; status.hidden = false;

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    status.textContent = `Uploading ${file.name} (${i + 1}/${files.length})…`;
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/upload", { method: "POST", body: form, headers: { "authorization": `Bearer ${state.token}` } });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    } catch (err) {
      errBox.textContent = err.message; errBox.hidden = false;
    }
  }
  status.hidden = true;
  await loadUploads();
});

// ---------- Quick Ask Pills ----------
document.querySelectorAll(".sample-pill").forEach((pill) => {
  pill.addEventListener("click", () => {
    const q = pill.getAttribute("data-query");
    if (q) {
      $("question").value = q;
      submitQuestion();
    }
  });
});

// ---------- Ask Question Execution ----------
async function submitQuestion() {
  const errBox = $("ask-error");
  const q = $("question").value.trim();
  errBox.hidden = true;
  if (!q) { errBox.textContent = "Please enter a valid query."; errBox.hidden = false; return; }

  const activeSrc = state.activeSource;
  const sourceId = activeSrc ? `csv_${activeSrc.upload_id}` : "csv_latest";
  const allowed = selectedFieldsFromUI();
  // temporarily store allowed for answer rendering fallbacks
  state.pendingAllowedFields = allowed;

  const btn = $("ask-btn");
  const status = $("ask-status");
  btn.disabled = true; status.hidden = false; status.textContent = "Executing DuckDB SQL query…";

  try {
    const bodyInput = { session_token: sourceId, source_id: sourceId, question: q, user_id: state.user?.email || "local" };
    const body = await api({ path: "/api/ask", method: "POST", headers: { "content-type": "application/json" }, body: bodyInput });
    const data = body.data || {};
    state.lastAsk = { run_id: data.run_id, source_id: sourceId };

    $("answer-panel").hidden = false;
    $("reply-text").textContent = data.answer_text || "(Analysis Complete)";
    $("run-meta").textContent = `Run ID: ${data.run_id} · Latency: ${data.latency_ms ?? "?"}ms${data.fallback_mode ? " · Fallback Mode" : " · Gemini LLM Engine"}`;

    // Advisor Alert Banner
    if (data.advisor) {
      $("advisor-banner").hidden = false;
      $("advisor-headline-text").textContent = data.advisor.headline || "Executive Intelligence Advisory";
      $("advisor-text").innerHTML = (data.advisor.insights || []).map(ins => `<p style="margin-top: 4px;">${ins}</p>`).join("");
    } else {
      $("advisor-banner").hidden = true;
    }

    // Results Table & Chart State
    const cols = data?.query_result?.columns || [];
    const rows = data?.query_result?.rows || [];
    
    // Apply allowed fields post-filter if applicable
    let effectiveCols = Array.isArray(cols) ? cols : [];
    let effectiveRows = Array.isArray(rows) ? rows : [];
    if (allowed && allowed.length && effectiveRows.length) {
      const allowedSet = new Set(allowed);
      effectiveCols = effectiveCols.filter(c => allowedSet.has(c));
      effectiveRows = effectiveRows.map(r => {
        const out = {};
        for (const c of effectiveCols) out[c] = r[c];
        return out;
      });
    }
    
    state.currentCols = effectiveCols;
    state.currentRows = effectiveRows;
    state.currentSpec = data.chart_spec;
    state.selectedChartType = data?.chart_spec?.chart_type || data?.chart_spec?.type || "bar";
    if (!state.currentCols.length && data?.query_result?.columns?.length) {
      state.currentCols = data.query_result.columns;
      state.currentRows = data.query_result.rows;
    }

    renderData(state.currentCols, state.currentRows);
    updateChartTypeButtons(state.selectedChartType);
    renderChart(state.selectedChartType, state.currentSpec, state.currentRows, state.currentCols);
    $("field-selector").hidden = true;

    $("fallback-badge").hidden = !data.fallback_mode;

    addAuditEntry(q, `${data.latency_ms ?? "?"}ms`, data.fallback_mode);
  } catch (err) {
    errBox.textContent = err.message; errBox.hidden = false;
    $("answer-panel").hidden = true;
  } finally {
    btn.disabled = false; status.hidden = true;
  }
}

$("ask-btn").addEventListener("click", submitQuestion);
$("question").addEventListener("keydown", (e) => { if (e.key === "Enter") submitQuestion(); });

// ---------- Data Table Renderer ----------
function renderData(columns, rows) {
  const thead = $("data-head");
  const tbody = $("data-body");
  const table = $("data-table");
  const placeholder = $("table-placeholder");
  thead.innerHTML = ""; tbody.innerHTML = "";

  if (!columns.length || !rows.length) { table.hidden = true; placeholder.hidden = false; return; }
  placeholder.hidden = true; table.hidden = false;

  const tr = document.createElement("tr");
  for (const c of columns) {
    const th = document.createElement("th");
    const properColName = c.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    th.textContent = properColName;
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
}

function numberFormat(n) {
  try { return Number(n).toLocaleString(); } catch { return String(n); }
}

function _buildAnswerText(question, rows, columns, t) {
  const total = Array.isArray(rows) ? rows.length : 0;
  const colCount = Array.isArray(columns) ? columns.length : 0;
  let text = `"${question}" returned ${numberFormat(total)} record(s).\n\nThis dataset contains ${numberFormat(total)} record(s) across ${numberFormat(colCount)} column(s).\n\n`;
  text += `${t.answerColumnAnalysis || "Column Analysis:"}\n`;

  const sampleSize = Math.min(total, 50);
  const sample = total ? rows.slice(0, sampleSize) : [];
  const textCols = [];
  const numericCols = [];
  for (const c of columns) {
    const values = sample.map(r => r[c]).filter(v => v !== null && v !== undefined && v !== "");
    if (!values.length) {
      text += `- ${c}: empty / no data\n`;
      continue;
    }
    const numericValues = values.filter(v => !isNaN(Number(v)) && String(v).trim() !== "");
    if (numericValues.length) {
      numericCols.push(c);
      const nums = numericValues.map(Number);
      const unique = new Set(nums).size;
      text += `- ${c}: numeric data, range ${numberFormat(Math.min(...nums))} to ${numberFormat(Math.max(...nums))}, `;
      text += `average ${(nums.reduce((a, b) => a + b, 0) / nums.length).toFixed(2)}, ${unique} unique value(s)\n`;
    } else {
      textCols.push(c);
      const unique = Array.from(new Set(values.map(String))).slice(0, 8);
      text += `- ${c}: categorical with ${unique.length} unique value(s) — ${unique.join(", ")}\n`;
    }
  }

  if (numericCols.length) {
    text += `\n${t.answerNumericSummary || "Numeric Summary:"}\n`;
    for (const c of numericCols.slice(0, 3)) {
      const nums = sample.map(r => r[c]).filter(v => !isNaN(Number(v)) && String(v).trim() !== "").map(Number);
      if (!nums.length) continue;
      text += `- ${c}: total ${numberFormat(nums.reduce((a, b) => a + b, 0))}, average ${(nums.reduce((a, b) => a + b, 0) / nums.length).toFixed(2)}, min ${numberFormat(Math.min(...nums))}, max ${numberFormat(Math.max(...nums))}\n`;
    }
  }

  if (textCols.length) {
    text += `\n${t.answerCategoryDistribution || "Category Distribution:"}\n`;
    for (const c of textCols.slice(0, 3)) {
      const counts = {};
      for (const r of sample) {
        const v = String(r[c] ?? "");
        if (v === "") continue;
        counts[v] = (counts[v] || 0) + 1;
      }
      const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 5);
      if (top.length) {
        text += `- ${c} distribution: ` + top.map(([k, v]) => `${k} (${v})`).join("; ") + "\n";
      }
    }
  }

  const maxVal = Math.max(...Object.values(counts || {}), 0);
  const metaCount = total > 0 ? total : (rows ? rows.length : 0);
  const alerts = [];
  for (const [c, ccounts] of Object.entries(counts || {})) {
    const cMax = Math.max(...Object.values(ccounts), 0);
    if (cMax && metaCount && cMax / metaCount >= 0.5) {
      alerts.push(`${t.concentrationAlert || "Concentration Alert"}: ${c}='${Object.keys(ccounts).find(k => ccounts[k] === cMax)}' ${t.accountsFor || "accounts for"} ${(cMax/metaCount*100).toFixed(1)}% ${t.answerTotal || "of total count"}.`);
    }
  }
  if (alerts.length) {
    text += `\n**Advisory Notes**\n` + alerts.map(a => `📌 ${a}`).join("\n");
  }

  return text;
}

// ---------- Chart Type Selector Buttons ----------
// row/column select controls
function ensureChartAxisSelectors() {
  if ($("chart-x-axis")) return;
  const header = $("chart-header");
  const wrap = document.createElement("div");
  wrap.style.display = "flex";
  wrap.style.gap = "8px";
  wrap.style.alignItems = "center";
  wrap.style.flexWrap = "wrap";
  wrap.style.marginTop = "8px";
  wrap.innerHTML = `
    <select id="chart-x-axis" class="axis-select" style="background:#0b1220; color:#e2e8f0; border:1px solid #233045; padding:6px 8px; border-radius:6px;"></select>
    <select id="chart-y-axis" class="axis-select" style="background:#0b1220; color:#e2e8f0; border:1px solid #233045; padding:6px 8px; border-radius:6px;"></select>
    <button id="chart-render-btn" class="primary small">Render Chart</button>
  `;
  header?.parentNode?.insertBefore(wrap, header.nextSibling);

  document.getElementById("chart-render-btn")?.addEventListener("click", () => {
    const type = state.selectedChartType || "bar";
    renderChart(type, state.currentSpec, state.currentRows, state.currentCols);
  });

  document.getElementById("chart-x-axis")?.addEventListener("change", () => document.getElementById("chart-render-btn")?.click());
  document.getElementById("chart-y-axis")?.addEventListener("change", () => document.getElementById("chart-render-btn")?.click());
}

function populateChartAxisSelectors(columns) {
  const x = $("chart-x-axis");
  const y = $("chart-y-axis");
  if (!x || !y) return;
  x.innerHTML = "";
  y.innerHTML = "";
  const opts = columns.length ? columns : ["(none)"];
  opts.forEach((c, i) => {
    const ox = document.createElement("option");
    ox.value = c; ox.textContent = c;
    x.appendChild(ox);
    const oy = document.createElement("option");
    oy.value = c; oy.textContent = c;
    y.appendChild(oy);
  });
  if (opts.length >= 2) y.selectedIndex = 1;
}

// chart type bar + extra types
function updateChartTypeButtons(activeType) {
  activeType = activeType || "bar";
  const allowed = ["bar","line","doughnut","pie","polarArea","scatter","area","histogram","box","radar"];
  if (!allowed.includes(activeType)) activeType = "bar";
  const bar = document.getElementById("chart-type-bar");
  if (bar && !state.chartBarInitialized) {
    bar.innerHTML = `
      <button class="chart-type-btn ${activeType==="bar"?"active":""}" data-chart="bar">📊 Bar</button>
      <button class="chart-type-btn ${activeType==="line"?"active":""}" data-chart="line">📈 Line</button>
      <button class="chart-type-btn ${activeType==="scatter"?"active":""}" data-chart="scatter">🔗 Scatter</button>
      <button class="chart-type-btn ${activeType==="doughnut"?"active":""}" data-chart="doughnut">🍩 Doughnut</button>
      <button class="chart-type-btn ${activeType==="pie"?"active":""}" data-chart="pie">🥧 Pie</button>
      <button class="chart-type-btn ${activeType==="polarArea"?"active":""}" data-chart="polarArea">🎯 Polar</button>
      <button class="chart-type-btn ${activeType==="area"?"active":""}" data-chart="area">📉 Area</button>
      <button class="chart-type-btn ${activeType==="histogram"?"active":""}" data-chart="histogram">📊 Histogram</button>
      <button class="chart-type-btn ${activeType==="box"?"active":""}" data-chart="box">📦 Box</button>
      <button class="chart-type-btn ${activeType==="radar"?"active":""}" data-chart="radar">🕸️ Radar</button>
    `;
    state.chartBarInitialized = true;
    bindChartTypeButtons();
  }
  document.querySelectorAll(".chart-type-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-chart") === activeType);
  });
}

function bindChartTypeButtons() {
  document.querySelectorAll(".chart-type-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cType = btn.getAttribute("data-chart");
      if (cType && state.currentRows.length) {
        state.selectedChartType = cType;
        updateChartTypeButtons(cType);
        renderChart(cType, state.currentSpec, state.currentRows, state.currentCols);
      }
    });
  });
}

// ---------- Multi-Type Chart Renderer ----------
let chartInstance = null;

function renderChart(chartType, spec, rows = [], columns = []) {
  const specType = spec?.chart_type || spec?.type || chartType;
  const canvas = $("chart-canvas");
  const placeholder = $("chart-placeholder");

  if (!rows.length || specType === "none") {
    canvas.hidden = true; placeholder.hidden = false;
    if (chartInstance) { chartInstance.destroy(); chartInstance = null; }
    placeholder.textContent = rows.length ? "Chart not recommended for this result." : "No chart specification generated for this query.";
    return;
  }
  canvas.hidden = false; placeholder.hidden = true;

  ensureChartAxisSelectors();
  populateChartAxisSelectors(columns);

  const xSel = $("chart-x-axis");
  const ySel = $("chart-y-axis");
  const enc = spec?.encoding || {};
  let xCol = enc.x_axis || enc.x || (xSel ? xSel.value : null) || (columns[0] || "category");
  let yCol = enc.y_axis || enc.y || (ySel ? ySel.value : null) || (columns[1] || columns[0] || "value");

  if (!columns.includes(xCol)) xCol = columns[0] || xCol;
  if (!columns.includes(yCol)) yCol = columns.find(c => c !== xCol) || yCol;

  const properXCol = String(xCol).replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  const properYCol = String(yCol).replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

  const labels = rows.map(r => String(r[xCol] ?? ""));
  const dataVals = rows.map(r => (typeof r[yCol] === "number" ? r[yCol] : (parseFloat(r[yCol]) || 0)));

  const colors = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444", "#06b6d4", "#ec4899", "#6366f1", "#14b8a6", "#f97316"];

  if (!window.Chart) {
    placeholder.hidden = false;
    placeholder.textContent = "Chart engine unavailable.";
    return;
  }
  if (chartInstance) chartInstance.destroy();

  const isPieOrDoughnut = ["doughnut","pie","polarArea"].includes(specType);
  const allowAxisLabels = !isPieOrDoughnut;
  const singular = rows.length === 1;

  chartInstance = new window.Chart(canvas, {
    type: singular && specType === "bar" ? "bar" : specType,
    data: {
      labels,
      datasets: [{
        label: spec?.title || `${properYCol} by ${properXCol}`,
        data: dataVals,
        backgroundColor: isPieOrDoughnut ? colors.slice(0, labels.length) : (specType === "line" ? "rgba(59, 130, 246, 0.2)" : colors),
        borderColor: specType === "line" ? "#3b82f6" : "transparent",
        borderWidth: specType === "line" ? 3 : 0,
        tension: specType === "line" ? 0.38 : 0,
        fill: specType === "line",
        borderRadius: isPieOrDoughnut || singular ? 0 : 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: isPieOrDoughnut, labels: { color: "#94a3b8", font: { family: "Inter" } } },
        title: { display: true, text: spec?.title || `Analytics (${specType.toUpperCase()})`, color: "#f8fafc", font: { family: "Inter", size: 14 } },
        tooltip: {
          callbacks: {
            label: (ctx) => `${properYCol}: ${Number(ctx.raw).toLocaleString()}`
          }
        }
      },
      scales: allowAxisLabels ? {
        x: { title: { display: allowAxisLabels, text: properXCol, color: "#f8fafc" }, ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
        y: { title: { display: allowAxisLabels, text: properYCol, color: "#f8fafc" }, ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } }
      } : {}
    }
  });
}

// ---------- Audit Entry Generator ----------
function addAuditEntry(q, latency, isFallback) {
  const tbody = $("audit-history-body");
  if (!tbody) return;
  const tr = document.createElement("tr");
  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  tr.innerHTML = `
    <td>${timeStr}</td>
    <td>${q}</td>
    <td>${latency}</td>
    <td>${isFallback ? '<span class="badge">Fallback Engine</span>' : '<span class="safe-badge">DuckDB Live SQL</span>'}</td>
    <td><button class="ghost small">👍 Verified</button></td>
  `;
  tbody.insertBefore(tr, tbody.firstChild);
}

// ---------- Language Toggle Handlers ----------
$("lang-en").addEventListener("click", () => applyLanguage("en"));
$("lang-hi").addEventListener("click", () => applyLanguage("hi"));

// ---------- Init ----------
(function init() {
  applyLanguage(state.lang);
  if (state.token) viewer();
  else showAuth("login");
})();
