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
  allowedFields: null,
  debugLog: [],
  renderCount: 0,
  chartRenderCount: 0,
  submitCount: 0,
  _speechInstance: null,
  _speechState: "idle",
};

const DEBUG = {
  snapshotStore: [],
  maxStore: 5000,
  logs: [],
  append(tag, detail) {
    const entry = { time: new Date().toLocaleTimeString(), tag, detail };
    this.logs.unshift(entry);
    if (state.debugLog.length < 200) state.debugLog.unshift(entry);
    const body = $("debug-body");
    if (body) body.prepend(`${entry.time} [${entry.tag}] ${entry.detail}\n`);
    console.log(`[${tag}]`, detail);
  },
  snapshot(name, payload) {
    const rec = { name, payload, time: new Date().toLocaleTimeString() };
    this.snapshotStore.unshift(rec);
    if (this.snapshotStore.length > this.maxStore) this.snapshotStore.length = this.maxStore;
    console.log(`[debug:snapshot:${name}]`, JSON.stringify(payload));
  },
  clear() {
    this.logs = [];
    state.debugLog = [];
    const body = $("debug-body");
    if (body) body.textContent = "";
  }
};

function _d_(fn) {
  return (...args) => {
    try { return fn(...args); }
    catch (err) { console.error(`[debug:err] ${fn.name}`, err, args); throw err; }
  };
}

function updateDebugFromAsk(data) {
  if (!data) return;
  if ($("debug-provider")) $("debug-provider").textContent = `provider=${data.provider || state.provider || "?"}`;
  if ($("debug-model")) $("debug-model").textContent = `model=${data.model || state.model || "?"}`;
  if ($("debug-latency")) $("debug-latency").textContent = `latency=${data.latency_ms ?? "?"}ms`;
  if ($("debug-fallback")) $("debug-fallback").textContent = `fallback=${data.fallback_mode ? "yes" : "no"}`;
  const raw = data.debug_log;
  if (Array.isArray(raw) && raw.length) {
    raw.forEach((entry) => DEBUG.append(entry.tag || "backend", entry.detail || JSON.stringify(entry)));
  }
}

function feedbackCurrentRun(data) {
  DEBUG.append("feedback", `stub: feedbackCurrentRun for run_id=${data?.run_id}`);
}

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
    logout: "Logout",
    kpiSources: "Active Datasets",
    kpiRows: "Total Dataset Records",
    kpiEngine: "Query Execution Engine",
    kpiSecurity: "Privacy & Shielding",
    kpiSubSources: "Multi-CSV Ingestion Active",
    kpiSubRows: "In-Memory Engine",
    kpiSubEngine: "Zero-Trust Read-Only",
    kpiSubSecurity: "Zero Prompt Leaks",
    kpiValSecurity: "PII Protected",
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
    fieldSelectorTitle: "Select Fields for Analysis",
    fieldApply: "Apply Selected Fields",
    fieldReset: "Use All",
    sampleTitle: "Quick-Ask Sample Queries",
    sampleHint: "Click any sample question to run immediately:",
    tabDashboard: "📊 Query Dashboard",
    tabSchema: "🔍 Schema Inspector",
    tabAudit: "📜 Audit Trail & Query Memory",
    schemaEmpty: "Upload a CSV or select an active dataset first.",
    schemaMeta: "Columns",
    schemaRows: "Total Records",
    auditTitle: "Query Memory & Audit Trail",
    auditHint: "Historical execution logs, latency performance, and user feedback ratings for self-learning optimization.",
    auditColTime: "Timestamp",
    auditColQuestion: "Question",
    auditColLatency: "Execution Latency",
    auditColEngine: "Engine Status",
    auditColRating: "Rating Feedback",
    auditVerified: "👍 Verified",
    chartPlaceholder: "No chart specification generated for this query.",
    chartNotRecommended: "Chart not recommended for this result.",
    uploadStatus: "Uploading...",
    uploadSuccess: "Upload complete.",
    uploadErrorPrefix: "Upload failed",
    askError: "Please enter a valid query.",
    askStatusPrefix: "Running analysis...",
    askStatusDone: "Analysis complete.",
    micTooltip: "Dictate query",
    micListening: "Listening...",
    micUnsupported: "Speech input is not supported in this browser.",
    micError: "Microphone input failed.",
    reportTitle: "UP Police Data Analysis Report",
    reportSummary: "Executive Summary",
    reportFindings: "Key Findings",
    reportDetailed: "Detailed Analysis",
    reportChart: "Analytics Chart",
    reportTable: "Structured Data Sample",
    reportAudit: "Report Audit",
    reportGenerated: "Generated",
    reportId: "Report ID",
    reportClass: "Classification: Internal — Officer Review",
    answerColumnAnalysis: "Column Analysis:",
    answerNumericSummary: "Numeric Summary:",
    answerCategoryDistribution: "Category Distribution:",
    answerTotal: "Total",
    answerAverage: "Average",
    answerMin: "Min",
    answerMax: "Max",
    answerPeakRecord: "Peak Record",
    chartDefaultTitle: "Analytics",
    concentrationAlert: "Concentration Alert",
    accountsFor: "accounts for",
    criticalVolume: "Critical Volume",
    spikeDetected: "Spike detected",
    approachesDataSetBaseline: "approaches or exceeds dataset baseline",
    noData: "No data available.",
  },
  hi: {
    navTitle: "उत्तर प्रदेश पुलिस डेटा इंटेलिजेंस एजेंट",
    authTitle: "विश्लेषक पोर्टल लॉगिन",
    authSub: "उत्तर प्रदेश पुलिस स्वायत्त डेटा विश्लेषक पोर्टल",
    labelEmail: "ईमेल पता",
    labelPass: "पासवर्ड",
    btnLogin: "लॉगिन करें",
    btnRegister: "नया खाता बनाएं",
    logout: "लॉगआउट",
    kpiSources: "सक्रिय डेटासेट",
    kpiRows: "कुल डेटा रिकॉर्ड",
    kpiEngine: "क्वेरी एक्ज़ीक्यूशन इंजन",
    kpiSecurity: "गोपनीयता एवं सुरक्षा",
    kpiSubSources: "मल्टी-CSV इंजेस्शन सक्रिय",
    kpiSubRows: "इन-मेमोरी इंजन",
    kpiSubEngine: "जीरो-ट्रस्ट रीड-ओनली",
    kpiSubSecurity: "जीरो प्रॉम्प्ट लीक",
    kpiValSecurity: "पीआईआई सुरक्षित",
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
    fieldSelectorTitle: "विश्लेषण के लिए फ़ील्ड चुनें",
    fieldApply: "चयनित फ़ील्ड लागू करें",
    fieldReset: "सभी उपयोग करें",
    sampleTitle: "त्वरित प्रश्न उदाहरण",
    sampleHint: "तुरंत चलाने के लिए किसी भी प्रश्न पर क्लिक करें:",
    tabDashboard: "📊 क्वेरी डैशबोर्ड",
    tabSchema: "🔍 स्कीमा इंस्पेक्टर",
    tabAudit: "📜 ऑडिट ट्रेल एवं क्वेरी मेमोरी",
    schemaEmpty: "CSV अपलोड करें या पहले से एक सक्रिय डेटासेट चुनें।",
    schemaMeta: "कॉलम",
    schemaRows: "कुल रिकॉर्ड",
    auditTitle: "क्वेरी मेमोरी एवं ऑडिट ट्रेल",
    auditHint: "स्व-शिक्षण अनुकूलन के लिए ऐतिहासिक निष्पादन लॉग, लैटेंसी प्रदर्शन और उपयोगकर्ता प्रतिक्रिया रेटिंग।",
    auditColTime: "समय",
    auditColQuestion: "प्रश्न",
    auditColLatency: "निष्पादन लैटेंसी",
    auditColEngine: "इंजन स्थिति",
    auditColRating: "रेटिंग प्रतिक्रिया",
    auditVerified: "👍 सत्यापित",
    chartPlaceholder: " इस क्वेरी के लिए कोई चार्ट विनिर्देश उत्पन्न नहीं हुआ।",
    chartNotRecommended: "इस परिणाम के लिए चार्ट अनुशंसित नहीं है।",
    uploadStatus: "अपलोड हो रहा है...",
    uploadSuccess: "अपलोड पूर्ण हुआ।",
    uploadErrorPrefix: "अपलोड विफल",
    askError: "कृपया एक वैध प्रश्न दें।",
    askStatusPrefix: "विश्लेषण चल रहा है...",
    askStatusDone: "विश्लेषण पूर्ण हुआ।",
    micTooltip: "प्रश्न बोलें",
    micListening: "सुन रहा हूँ...",
    micUnsupported: "इस ब्राउज़र में स्पीच इंपुट समर्थित नहीं है।",
    micError: "माइक्रोफोन इंपुट विफल हुआ।",
    reportTitle: "उत्तर प्रदेश पुलिस डेटा विश्लेषण रिपोर्ट",
    reportSummary: "कार्यकारी सारांश",
    reportFindings: "प्रमुख निष्कर्ष",
    reportDetailed: "विस्तृत विश्लेषण",
    reportChart: "विश्लेषण आलेख",
    reportTable: "संरचित डेटा नमूना",
    reportAudit: "रिपोर्ट ऑडिट",
    reportGenerated: "उत्पन्न",
    reportId: "रिपोर्ट ID",
    reportClass: "वर्गीकरण: आंतरिक — अधिकारी समीक्षा",
    answerColumnAnalysis: "कॉलम विश्लेषण:",
    answerNumericSummary: "संख्या सारांश:",
    answerCategoryDistribution: "श्रेणी वितरण:",
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
    noData: "डेटा उपलब्ध नहीं है।",
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
  $("auth-submit").textContent = authMode === "register" ? (t.btnRegister || "Create Account") : (t.btnLogin || "Login");
  $("auth-toggle").textContent = authMode === "register" ? "Switch to Login" : (t.btnRegister || "Create Account");

  $("kpi-lbl-sources").textContent = t.kpiSources;
  $("kpi-lbl-rows").textContent = t.kpiRows;
  $("kpi-lbl-engine").textContent = t.kpiEngine;
  $("kpi-lbl-security").textContent = t.kpiSecurity;
  $("kpi-val-security").textContent = t.kpiValSecurity || "PII Protected";
  $("kpi-sub-sources").textContent = t.kpiSubSources;
  $("kpi-sub-rows").textContent = t.kpiSubRows;
  $("kpi-sub-engine").textContent = t.kpiSubEngine;
  $("kpi-sub-security").textContent = t.kpiSubSecurity;

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
  $("tab-dashboard").textContent = t.tabDashboard;
  $("tab-schema").textContent = t.tabSchema;
  $("tab-audit").textContent = t.tabAudit;
  $("logout-btn").textContent = t.logout;
  $("txt-no-sources").textContent = t.noSources;
  $("mic-btn")?.setAttribute("title", t.micTooltip || "Dictate query");
  $("speech-status") && ($("speech-status").textContent = "");

  const fieldPanel = $("field-selector");
  if (fieldPanel) {
    const titleEl = fieldPanel.querySelector("h2");
    if (titleEl) titleEl.textContent = t.fieldSelectorTitle;
    const applyBtn = $("field-apply-btn");
    const resetBtn = $("field-reset-btn");
    if (applyBtn) applyBtn.textContent = t.fieldApply;
    if (resetBtn) resetBtn.textContent = t.fieldReset;
  }

  const sampleTitle = $("sample-title");
  if (sampleTitle) sampleTitle.textContent = t.sampleTitle;
  const sampleHint = $("sample-hint");
  if (sampleHint) sampleHint.textContent = t.sampleHint;

  const auditTitle = $("audit-title");
  if (auditTitle) auditTitle.textContent = t.auditTitle;
  const auditHint = $("audit-hint");
  if (auditHint) auditHint.textContent = t.auditHint;

  const schemaEmpty = $("schema-empty");
  if (schemaEmpty) schemaEmpty.textContent = t.schemaEmpty;
  const schemaMeta = $("schema-meta");
  
  const chartPlaceholder = $("chart-placeholder");
  if (chartPlaceholder) chartPlaceholder.textContent = t.chartPlaceholder;

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

$("sidebar-toggle")?.addEventListener("click", () => {
  const sidebar = $("sidebar");
  if (!sidebar) return;
  const isMobile = window.matchMedia("(max-width: 980px)").matches;
  if (isMobile) {
    sidebar.classList.toggle("collapsed");
  } else {
    sidebar.classList.toggle("collapsed-tablet");
  }
});

// ---------- Tab Switcher ----------
function switchTab(tabName) {
  state.activeTab = tabName;
  $("tab-dashboard").classList.toggle("active", tabName === "dashboard");
  $("tab-schema").classList.toggle("active", tabName === "schema");
  $("tab-audit").classList.toggle("active", tabName === "audit");

  $("view-tab-dashboard").hidden = tabName !== "dashboard";
  $("view-tab-schema").hidden = tabName !== "schema";
  $("view-tab-audit").hidden = tabName !== "audit";

  if (tabName === "audit") loadQueryHistory();
  if (tabName === "schema") renderSchemaFromUpload();
}

// ---------- Query History Live Loader ----------
async function loadQueryHistory() {
  const tbody = $("audit-history-body");
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="5"><div class="hint">${dict[state.lang]?.noData || "No data available."}</div></tr>`;
  try {
    const res = await api(header("/api/analyst/query-history", "GET"));
    const items = res.data?.items || [];
    tbody.innerHTML = "";
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="5"><div class="hint">${dict[state.lang]?.noData || "No history yet."}</div></tr>`;
      return;
    }
    for (const item of items.slice(0, 50)) {
      const tr = document.createElement("tr");
      const time = item.time ? new Date(item.time).toLocaleString([], { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' }) : "";
      tr.innerHTML = `
        <td>${time}</td>
        <td>${item.question || ""}</td>
        <td>${item.latency_ms ?? "?"}ms</td>
        <td>${item.fallback_mode ? '<span class="badge">Fallback</span>' : '<span class="safe-badge">DuckDB Live SQL</span>'}</td>
        <td><span class="safe-badge">${item.status || "completed"}</span></td>
      `;
      tbody.appendChild(tr);
    }
  } catch (err) {
    DEBUG.append("audit", `loadQueryHistory failed: ${err.message}`);
    tbody.innerHTML = `<tr><td colspan="5"><div class="hint">Failed to load query history.</div></tr>`;
  }
}

// ---------- Schema Inspector Live Loader ----------
function renderSchemaFromUpload() {
  const schema = state.activeSource?.schema || [];
  const rows = state.activeSource?.rows || 0;
  renderSchema(schema, rows);
}

$("tab-dashboard").addEventListener("click", () => switchTab("dashboard"));
$("tab-schema").addEventListener("click", () => switchTab("schema"));
$("tab-audit").addEventListener("click", () => switchTab("audit"));

// ---------- API Wrapper ----------
function header(path, method = "GET", body) {
  const h = { "content-type": "application/json" };
  if (state.token) {
    h["authorization"] = `Bearer ${state.token}`;
  } else {
    DEBUG.append("auth-debug", `Warning: state.token is falsy (${state.token}) for path ${path}`);
  }
  return { path, method, body, headers: h };
}

async function api(input) {
  DEBUG.append("api-debug", `Request: ${input.method} ${input.path} | Headers: ${JSON.stringify(input.headers)}`);
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
  bindChartTypeButtons();
  DEBUG.append("sys", `viewer() token=${Boolean(state.token)} sources=${state.sources.length} active=${state.activeSource?.filename}`);
  if (state.activeSource) renderSchemaFromUpload();
  if (state.token) loadQueryHistory();
  void autoBootstrap();
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
    loadUploads();
    if (state.sources.length && !state.activeSource) {
      selectSource(state.sources[0]);
    }
  } catch (err) {
    errBox.textContent = err.message; errBox.hidden = false;
  }
});

$("logout-btn").addEventListener("click", () => showAuth("login"));

// ---------- Multi-CSV Datasets Manager ----------
async function loadUploads() {
  const status = $("upload-status");
  const errBox = $("upload-error");
  try {
    const res = await api(header("/api/uploads", "GET"));
    const items = res.data?.items || [];
    state.sources = items;
    renderSourceStrip(items);
    updateKpis();
    if (items.length > 0 && !state.activeSource) {
      await selectSource(items[0]);
    }
    if (status) { status.textContent = ""; status.hidden = true; }
  } catch (err) {
    console.error("Failed to load sources:", err);
    if (errBox) { errBox.textContent = "Failed to load datasets: " + err.message; errBox.hidden = false; }
    if (status) { status.textContent = ""; status.hidden = true; }
  }
}

async function deleteDataset(uploadId, e) {
  if (e) e.stopPropagation();
  if (!confirm("Are you sure you want to remove this dataset?")) return;
  const status = $("upload-status");
  const errBox = $("upload-error");
  status.hidden = false;
  status.textContent = "Deleting...";
  errBox.hidden = true;
  try {
    await api(header(`/api/uploads/${uploadId}`, "DELETE"));
    if (state.activeSource?.upload_id === uploadId) {
      state.activeSource = null;
    }
    status.hidden = true;
    await loadUploads();
    if (state.sources.length === 0) {
      renderSchema([], 0);
    }
  } catch (err) {
    status.hidden = true;
    alert("Failed to delete dataset: " + err.message);
  }
}

function renderSourceStrip(items) {
  const strip = $("source-strip");
  if (!strip) return;
  strip.innerHTML = "";
  if (!items.length) {
    strip.innerHTML = `<div class="hint">${dict[state.lang]?.noSources || "No CSV datasets uploaded yet."}</div>`;
    return;
  }
  items.forEach((item) => {
    const chip = document.createElement("div");
    chip.className = `source-chip ${state.activeSource?.upload_id === item.upload_id ? "active" : ""}`;
    chip.innerHTML = `
      <span class="source-chip-main">
        📄 ${item.filename} <span class="source-chip-meta">(${item.rows.toLocaleString()} rows)</span>
      </span>
      <button class="del-btn" title="Remove Dataset">🗑️</button>
    `;
    chip.addEventListener("click", () => selectSource(item));
    const delBtn = chip.querySelector(".del-btn");
    delBtn.addEventListener("click", (e) => deleteDataset(item.upload_id, e));
    strip.appendChild(chip);
  });
  DEBUG.snapshot("renderSourceStrip", { items: items.map(i => ({ filename: i.filename, rows: i.rows, questions: i.suggested_questions?.length || 0, briefing: !!i.executive_briefing })) });
}

function selectSource(source) {
  state.activeSource = source;
  renderSourceStrip(state.sources);
  renderSchema(source.schema || [], source.rows || 0);
  // Update suggested questions
  let asked = false;
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

    if (!state.lastAsk) {
      quickAsk(source.suggested_questions[0]);
      asked = true;
    }
  }
  if (source.executive_briefing && source.executive_briefing.length) {
    const container = $("executive-briefing");
    if (container) {
      const ul = document.createElement("ul");
      ul.style.margin = "0";
      ul.style.paddingLeft = "1.2rem";
      source.executive_briefing.forEach(line => {
        const li = document.createElement("li");
        li.textContent = line;
        ul.appendChild(li);
      });
      container.innerHTML = "";
      container.appendChild(ul);
      container.hidden = false;
    }
  }
  DEBUG.snapshot("selectSource", { filename: source.filename, rows: source.rows, asked });
}

function renderSchema(schema, totalRows) {
  state.renderCount += 1;
  DEBUG.snapshot("renderSchema", { schemaCount: schema.length, totalRows });
  const table = $("schema-table");
  const body = $("schema-body");
  const empty = $("schema-empty");
  const meta = $("schema-meta");
  if (!table || !body) return;
  body.innerHTML = "";

  if (!schema.length) {
    table.hidden = true; empty.hidden = false; meta.textContent = ""; return;
  }
  empty.hidden = true; table.hidden = false;

  schema.forEach((col) => {
    const tr = document.createElement("tr");
    const isPii = col.pii === true || col.pii === "true";
    tr.innerHTML = `
      <td class="schema-name">${col.name}</td>
      <td class="schema-type">${col.type || "text"}</td>
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
      <input type="checkbox" class="field-check" value="${col.name}" checked />
      <span class="field-name">${col.name} <span class="field-meta">(${col.type || "text"})</span></span>
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
      if (!res.ok) {
        const txt = await res.text().catch(() => "");
        throw new Error(`Upload failed: ${res.status} ${txt}`);
      }
    } catch (err) {
      errBox.textContent = err.message; errBox.hidden = false;
    }
  }
  status.hidden = true;
  await loadUploads();
});

// ---------- Demo Bootstrap ----------
async function autoBootstrap() {
  DEBUG.append("sys", "autoBootstrap start");
  try {
    const res = await api(header("/api/uploads", "GET"));
    const items = res.data?.items || [];
    DEBUG.append("api", `uploads list items=${items.length}`);
    if (!items.length) {
DEBUG.append("sys", "no items, creating demo uploads");
      const demos = [
        { filename: "sample-5mb.csv", file: "/sample-5mb.csv" },
        { filename: "fir_registrations.csv", file: "/fir_registrations.csv" },
      ];
      for (const demo of demos) {
        try {
          const r = await fetch(demo.file);
          if (!r.ok) continue;
          const raw = await r.text();
          const form = new FormData();
          form.append("file", new Blob([raw], { type: "text/csv" }), demo.filename);
          await fetch("/api/upload", { method: "POST", body: form, headers: { "authorization": `Bearer ${state.token || ""}` } });
        } catch (err) {
          console.warn("Demo upload failed:", demo.filename, err);
        }
      }
    }

    await loadUploads();
    const src = state.sources[0];
    if (src) {
      await selectSource(src);
      const q = src.suggested_questions?.[0] || "Show the top 5 districts with the highest number of incidents";
      $("question").value = q;
      // await submitQuestion(); // Prevent automatic execution on login
    }
  } catch (err) {
    console.warn("Auto bootstrap skipped:", err);
  }
}

function quickAsk(q) {
  if (!q) return;
  $("question").value = q;
  submitQuestion();
}

function downloadText(filename, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function buildExportText(format) {
  const rows = state.currentRows || [];
  const cols = state.currentCols || [];
  const question = ($("question")?.value || state.lastAsk?.question || "analysis").trim() || "analysis";
  const safeName = question.replace(/[^\w\-]+/g, "_").slice(0, 40) || "analysis";
  const ts = new Date().toISOString().slice(0,19).replace(/[T:]/g,"-");
  if (format === "csv") {
    if (!rows.length || !cols.length) return "No data available.";
    const header = cols.join(",");
    const body = rows.map(r => cols.map(c => {
      const v = r?.[c];
      const s = String(v ?? "");
      return /[,"\n]/.test(s) ? `"${s.replace(/"/g,'""')}"` : s;
    }).join(","));
    return header + "\n" + body.join("\n");
  }
  const answer = ($("reply-text")?.textContent || "").trim();
  const tablePreview = rows.slice(0, 50).map(r => cols.map(c => r?.[c] ?? "").join(" | ")).join("\n");
  return [
    `# ${question}`,
    `Generated: ${new Date().toLocaleString()}`,
    "",
    "## Executive Intelligence Answer",
    answer || "(No answer text available.)",
    "",
    "## Structured Data Results",
    tablePreview || "(No rows available.)",
    "",
    "## Export Details",
    `Run ID: ${state.lastAsk?.run_id || "-"}`,
    `Source: ${state.activeSource?.filename || "-"}`,
    `Rows: ${rows.length}`,
    `Columns: ${cols.join(", ")}`,
  ].join("\n");
}

async function exportCsv() {
  DEBUG.append("ui", "exportCsv start");
  const runId = state.lastAsk?.run_id;
  if (runId) {
    try {
      const data = await api(header(`/api/export`, "POST", { query_run_id: runId, format: "csv", user_id: state.user?.email || "local" }));
      const url = data?.data?.url;
      if (url) {
        window.open(url, "_blank");
        DEBUG.append("ui", "exportCsv backend ok");
        return;
      }
    } catch (err) {
      DEBUG.append("ui", `exportCsv backend failed: ${err.message}`);
    }
  }
  const text = buildExportText("csv");
  downloadText(`analysis_${Date.now()}.csv`, text);
  DEBUG.append("ui", "exportCsv client fallback");
}
async function exportReport() {
  DEBUG.append("ui", "exportReport start");
  const runId = state.lastAsk?.run_id;
  if (runId) {
    try {
      const body = {
        title: ($("question")?.value || "analysis").trim() || "analysis",
        rows: state.currentRows || [],
        columns: state.currentCols || [],
        chart_type: state.selectedChartType || "bar",
        chart_title: state.currentSpec?.title || "Analytics",
        summary_text: ($("reply-text")?.textContent || "").trim(),
        detailed: [],
        findings: [],
        fmt: "md",
        filename_hint: `report_${runId}`,
      };
      const data = await api(header(`/api/analyst/report/analysis`, "POST", body));
      const url = data?.data?.url || data?.path;
      if (url) {
        window.open(url, "_blank");
        DEBUG.append("ui", "exportReport backend ok");
        return;
      }
    } catch (err) {
      DEBUG.append("ui", `exportReport backend failed: ${err.message}`);
    }
  }
  const text = buildExportText("md");
  downloadText(`report_${Date.now()}.md`, text);
  DEBUG.append("ui", "exportReport client fallback");
}

$("export-csv").addEventListener("click", exportCsv);
$("export-md").addEventListener("click", exportReport);
$("copy-answer").addEventListener("click", () => {
  const text = ($("reply-text")?.textContent || "").trim();
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    const btn = $("copy-answer");
    const prev = btn.textContent; btn.textContent = "Copied";
    setTimeout(() => { btn.textContent = prev; }, 1200);
  });
});

async function submitQuestion() {
  DEBUG.append("ui", "submitQuestion start");
  state.submitCount += 1;
  DEBUG.snapshot("submitQuestion", { count: state.submitCount, question: $("question").value.trim(), sourceId: state.activeSource?.upload_id || "none", allowed: selectedFieldsFromUI()?.join(",") || "*" });
  const errBox = $("ask-error");
  const q = $("question").value.trim();
  errBox.hidden = true;
  if (!q) { errBox.textContent = "Please enter a valid query."; errBox.hidden = false; return; }

  const activeSrc = state.activeSource;
  const sourceId = activeSrc ? `csv_${activeSrc.upload_id}` : "csv_latest";
  const allowed = selectedFieldsFromUI();
  state.pendingAllowedFields = allowed;
  DEBUG.append("ui", `question="${q}" source=${sourceId} allowed=${allowed?.join(",") || "*"}`);

  const btn = $("ask-btn");
  const status = $("ask-status");
  const stepper = $("progress-stepper");
  btn.disabled = true; status.hidden = true;
  if (stepper) { stepper.hidden = false; setStepperStep(1); }

  try {
    const bodyInput = { session_token: sourceId, source_id: sourceId, question: q, user_id: state.user?.email || "local" };
    const body = await api(header("/api/ask", "POST", bodyInput));
    const data = body.data || {};
    if (data.checkpoint) {
      const map = { plan: 2, execute: 3, chart: 3, answer: 4 };
      const step = map[data.checkpoint] || 4;
      setStepperStep(step);
    } else {
      setStepperStep(4);
    }
    DEBUG.append("api", `/ask response status=200 provider=${data.provider || "?"} model=${data.model || "?"} run_id=${data.run_id} latency=${data.latency_ms ?? "?"}ms checkpoint=${data.checkpoint || "?"}`);
    state.lastAsk = { run_id: data.run_id, source_id: sourceId };

    $("answer-panel").hidden = false;
    const rawAnswer = data.answer_text || "(Analysis Complete)";
    $("reply-text").innerHTML = rawAnswer
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .split("\n\n").map(block => {
        const trimmed = block.trim();
        if (!trimmed) return "";
        if (/^Advisory Notes$/i.test(trimmed)) {
          return `<div class="advisor-banner"><div class="advisor-headline">📌 Executive Advisor Alert</div><div class="advisor-body"><ul>${trimmed.replace(/^Advisory Notes$/i, "").split("\n").filter(Boolean).map(line => `<li>${line.replace(/^- /, "")}</li>`).join("")}</ul></div></div>`;
        }
        const lines = trimmed.split("\n");
        const html = lines.map(line => {
          if (line.trim().startsWith("- ")) {
            return `<li>${line.trim().slice(2)}</li>`;
          }
          if (line.trim().startsWith("## ")) {
            return `<h4>${line.trim().slice(3)}</h4>`;
          }
          return `<p>${line}</p>`;
        }).join("");
        return `<div class="answer-block">${html}</div>`;
      }).join("");
    $("run-meta").textContent = `Run ID: ${data.run_id} · Latency: ${data.latency_ms ?? "?"}ms · ${data.fallback_mode ? "Rule-based Fallback" : `${data.provider || "LLM"} / ${data.model || "model"}`}`;
    updateDebugFromAsk(data);
    $("fallback-badge").hidden = !data.fallback_mode;

    feedbackCurrentRun(data);

    if (data.advisor) {
      $("advisor-banner").hidden = false;
      $("advisor-headline-text").textContent = data.advisor.headline || "Executive Intelligence Advisory";
      $("advisor-text").innerHTML = (data.advisor.insights || []).map(ins => `<p class="advisor-insight">${ins}</p>`).join("");
    } else {
      $("advisor-banner").hidden = true;
    }

    // Results Table & Chart State
    const cols = Array.isArray(data?.query_result?.columns) ? data.query_result.columns : (Array.isArray(data?.columns) ? data.columns : []);
    const rows = Array.isArray(data?.query_result?.rows) ? data.query_result.rows : (Array.isArray(data?.rows) ? data.rows : []);
    DEBUG.append("data", `raw columns=${cols.length} rows=${rows.length} shape=${Array.isArray(data?.query_result?.columns) ? "nested" : (Array.isArray(data?.columns) ? "flat" : "none")}`);
    DEBUG.append("data", `first_row=${rows[0] != null ? JSON.stringify(rows[0]).slice(0, 200) : "(null)"}`);
    DEBUG.append("data", `chart_spec=${JSON.stringify(data.chart_spec || state.currentSpec || {}).slice(0, 300)}`);
    
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
    if (state.currentRows.length) {
      renderChart(state.selectedChartType, state.currentSpec, state.currentRows, state.currentCols);
    } else {
      const canvas = $("chart-canvas");
      const placeholder = $("chart-placeholder");
      canvas.hidden = true;
      placeholder.hidden = false;
      placeholder.textContent = "No data available for visualization.";
    }
    $("field-selector").hidden = true;
    $("fallback-badge").hidden = !data.fallback_mode;
    addAuditEntry(q, `${data.latency_ms ?? "?"}ms`, data.fallback_mode);
    DEBUG.append("render", `rendered cols=${state.currentCols.length} type=${state.selectedChartType}`);
  } catch (err) {
    errBox.textContent = err.message; errBox.hidden = false;
    $("answer-panel").hidden = true;
    DEBUG.append("error", err.message);
  } finally {
    btn.disabled = false; status.hidden = true;
  }
}

$("ask-btn").addEventListener("click", submitQuestion);
$("question").addEventListener("keydown", (e) => { if (e.key === "Enter") submitQuestion(); });
$("mic-btn").addEventListener("click", () => startSpeechDictation());

// ---------- Speech Recognition / Mic Dictation ----------
const SPEECH_RECOGNITION_STATES = {
  IDLE: "idle",
  LISTENING: "listening",
};

const speechRecognitionByLang = {
  en: { code: "en-IN", label: "English (India)", normalizedTo: "en" },
  hi: { code: "hi-IN", label: "Hindi (India)", normalizedTo: "hi" },
};

const spokenQueryNormalization = {
  // Hindi spoken forms -> analytical English equivalents
  "सबसे ऊपर रिकॉर्ड": "top records",
  "शीर्ष 5": "top 5",
  "औसत मान": "average value",
  "जिले के अनुसार": "by district",
  "शहर के अनुसार": "by city",
  "तारीख के अनुसार": "by date",
  "कुल रिकॉर्ड": "total records",
  "दिखाओ": "show",
  "देखाओ": "show",
  "गणना करो": "calculate",
  "औसत": "average",
  "कुल": "total",
  "संख्या": "count",
  "अधिकतम": "maximum",
  "न्यूनतम": "minimum",
};

function _resolveSpeechRecognition() {
  const win = window;
  const SpeechRecognition = win.SpeechRecognition || win.webkitSpeechRecognition;
  return SpeechRecognition || null;
}

function normalizeSpokenQuery(text = "", lang = "en") {
  if (!text) return "";
  let normalized = text.trim();
  if (lang === "hi") {
    const map = spokenQueryNormalization;
    for (const [src, dst] of Object.entries(map)) {
      if (!src) continue;
      normalized = normalized.split(src).join(dst);
    }
  }
  normalized = normalized
    .replace(/\s+/g, " ")
    .replace(/\b(?:कृपया|please|kindly|भी|also|तो|so)\b/gi, "")
    .trim();
  return normalized;
}

function setSpeechStatus(message = "") {
  const el = $("speech-status");
  if (el) {
    el.hidden = !message;
    el.textContent = message;
  }
}

function setStepperStep(step) {
  const stepper = $("progress-stepper");
  if (!stepper) return;
  stepper.hidden = false;
  stepper.querySelectorAll(".step").forEach((node) => {
    const s = Number(node.getAttribute("data-step"));
    node.classList.remove("active", "done");
    if (s === step) node.classList.add("active");
    else if (s < step) node.classList.add("done");
  });
  stepper.querySelectorAll(".step-line").forEach((line, idx) => {
    line.classList.toggle("done", (idx + 1) < step);
  });
}

function resetStepper() {
  const stepper = $("progress-stepper");
  if (!stepper) return;
  stepper.hidden = true;
  stepper.querySelectorAll(".step").forEach((node) => node.classList.remove("active", "done"));
  stepper.querySelectorAll(".step-line").forEach((line) => line.classList.remove("done"));
}

async function startSpeechDictation() {
  const SpeechRecognition = _resolveSpeechRecognition();
  if (!SpeechRecognition) {
    const t = dict[state.lang] || dict.en;
    setSpeechStatus(t.micUnsupported || "Speech input is not supported in this browser.");
    return;
  }
  const langKey = state.lang === "hi" ? "hi" : "en";
  const langMeta = speechRecognitionByLang[langKey];
  const t = dict[state.lang] || dict.en;

  if (state._speechState === SPEECH_RECOGNITION_STATES.LISTENING) {
    setSpeechStatus("");
    state._speechInstance?.stop?.();
    state._speechState = SPEECH_RECOGNITION_STATES.IDLE;
    $("mic-btn")?.classList.remove("recording");
    return;
  }

  try {
    const recognition = new SpeechRecognition();
    recognition.lang = langMeta.code;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.continuous = false;

    let finalTranscript = "";
    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          finalTranscript = result[0].transcript;
        } else {
          interim += result[0].transcript;
        }
      }
      const display = [finalTranscript, interim].filter(Boolean).join(" ").trim();
      if (display) {
        $("question").value = display;
        setSpeechStatus(`${t.micListening || "Listening..."} · ${display}`);
      }
    };

    recognition.onspeechend = () => {
      recognition.stop();
    };
    recognition.onerror = (event) => {
      const errorMessage = event.error === "not-allowed"
        ? "Microphone permission denied."
        : (t.micError || "Microphone input failed.");
      setSpeechStatus(errorMessage);
      $("mic-btn")?.classList.remove("recording");
      state._speechState = SPEECH_RECOGNITION_STATES.IDLE;
    };
    recognition.onend = () => {
      const cleaned = normalizeSpokenQuery($("question")?.value || "", langKey);
      if (cleaned) $("question").value = cleaned;
      setSpeechStatus("");
      $("mic-btn")?.classList.remove("recording");
      state._speechState = SPEECH_RECOGNITION_STATES.IDLE;
      if (cleaned) submitQuestion();
    };

    state._speechInstance = recognition;
    state._speechState = SPEECH_RECOGNITION_STATES.LISTENING;
    $("mic-btn")?.classList.add("recording");
    setSpeechStatus(t.micListening || "Listening...");
    recognition.start();
  } catch (err) {
    const t = dict[state.lang] || dict.en;
    setSpeechStatus(`${t.micError || "Microphone input failed."}: ${err.message}`);
    $("mic-btn")?.classList.remove("recording");
    state._speechState = SPEECH_RECOGNITION_STATES.IDLE;
  }
}

// ---------- Data Table Renderer ----------
function renderData(columns, rows, labelFilter) {
  DEBUG.snapshot("renderData", { columns: columns.length, rows: rows.length, columns, firstRow: rows[0] || null, labelFilter });
  state.renderCount += 1;
  const thead = $("data-head");
  const tbody = $("data-body");
  const table = $("data-table");
  const placeholder = $("table-placeholder");
  thead.innerHTML = ""; tbody.innerHTML = "";

  const source = Array.isArray(rows) ? rows : [];
  const filtered = typeof labelFilter === "function"
    ? source.filter(labelFilter)
    : source;

  if (!columns.length || !filtered.length) { table.hidden = true; placeholder.hidden = false; return; }
  placeholder.hidden = true; table.hidden = false;

  const tr = document.createElement("tr");
  for (const c of columns) {
    const th = document.createElement("th");
    const properColName = c.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    th.textContent = properColName;
    tr.appendChild(th);
  }
  thead.appendChild(tr);

  const limit = filtered.slice(0, 200);
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
    const allCounts = {};
    for (const c of textCols.slice(0, 3)) {
      const counts = {};
      for (const r of sample) {
        const v = String(r[c] ?? "");
        if (v === "") continue;
        counts[v] = (counts[v] || 0) + 1;
      }
      allCounts[c] = counts;
      const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 5);
      if (top.length) {
        text += `- ${c} distribution: ` + top.map(([k, v]) => `${k} (${v})`).join("; ") + "\n";
      }
    }
  }

  const metaCount = total > 0 ? total : (rows ? rows.length : 0);
  const alerts = [];
  for (const [c, ccounts] of Object.entries(allCounts || {})) {
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
    <select id="chart-x-axis" class="axis-select"></select>
    <select id="chart-y-axis" class="axis-select"></select>
    <button id="chart-render-btn" class="primary small">Render Chart</button>
  `;
  header?.parentNode?.insertBefore(wrap, header.nextSibling);

  document.getElementById("chart-render-btn")?.addEventListener("click", () => {
    const type = state.selectedChartType || "bar";
    renderChart(type, state.currentSpec, state.currentRows, state.currentCols);
  });

  document.getElementById("chart-x-axis")?.addEventListener("change", () => {
    const type = state.selectedChartType || "bar";
    renderChart(type, state.currentSpec, state.currentRows, state.currentCols);
  });
  document.getElementById("chart-y-axis")?.addEventListener("change", () => {
    const type = state.selectedChartType || "bar";
    renderChart(type, state.currentSpec, state.currentRows, state.currentCols);
  });
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

function updateChartTypeButtons(activeType) {
  activeType = activeType || "bar";
  const allowed = ["bar","line","doughnut","pie","polarArea","scatter","area","histogram","box","radar"];
  if (!allowed.includes(activeType)) activeType = "bar";
  document.querySelectorAll(".chart-type-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-chart") === activeType);
  });
}

let _chartButtonsBound = false;
function bindChartTypeButtons() {
  if (_chartButtonsBound) return;
  DEBUG.append("chart", "bindChartTypeButtons() wiring now");
  document.querySelectorAll(".chart-type-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const cType = btn.getAttribute("data-chart");
      DEBUG.append("chart", `chart click type=${cType} rows=${state.currentRows.length}`);
      if (cType && state.currentRows.length) {
        state.selectedChartType = cType;
        updateChartTypeButtons(cType);
        renderChart(cType, state.currentSpec, state.currentRows, state.currentCols);
      } else {
        DEBUG.append("chart", "blocked: no chart type or empty rows");
      }
    });
  });
  _chartButtonsBound = true;
}

// ---------- Multi-Type Chart Renderer ----------
let chartInstance = null;

function _buildChartDataset(specType, labels, dataVals, colors, properYCol, title) {
  const isPieOrDoughnut = ["doughnut", "pie", "polarArea"].includes(specType);
  const isLine = ["line", "area"].includes(specType);
  const isScatter = specType === "scatter";
  const isRadar = specType === "radar";
  const isHistogram = specType === "histogram";
  const isBox = specType === "box";

  if (isScatter) {
    const points = dataVals.map((v, idx) => ({ x: idx, y: v }));
    return {
      label: title || `${properYCol}`,
      data: points,
      backgroundColor: "#3b82f6",
      borderColor: "#3b82f6",
      pointRadius: 4,
    };
  }

  if (isHistogram) {
    const vals = dataVals.filter(v => Number.isFinite(v));
    if (!vals.length) return { label: title || properYCol, data: [] };
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const binCount = Math.min(20, Math.max(5, Math.ceil(Math.sqrt(vals.length))));
    const step = max > min ? (max - min) / binCount : 1;
    const bins = Array.from({ length: binCount }, () => 0);
    vals.forEach(v => {
      let idx = Math.floor((v - min) / step);
      if (idx >= binCount) idx = binCount - 1;
      if (idx < 0) idx = 0;
      bins[idx] += 1;
    });
    const binLabels = bins.map((_, i) => {
      const lo = min + i * step;
      const hi = lo + step;
      return `${Math.round(lo)}-${Math.round(hi)}`;
    });
    return {
      label: title || properYCol,
      data: bins,
      backgroundColor: colors.slice(0, bins.length),
      borderColor: "transparent",
      borderWidth: 0,
    };
  }

  if (isBox) {
    const grouped = new Map();
    const groupCol = columns.find((c) => c !== String(yCol)) || columns[0];
    rows.forEach((r, idx) => {
      const key = String(r[groupCol] ?? `bin-${idx}`);
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key).push(Number(r[yCol]) || 0);
    });
    const groups = Array.from(grouped.entries()).slice(0, 64);
    const stats = groups.map(([_k, vals]) => {
      const sorted = vals.slice().sort((a, b) => a - b);
      const q1 = sorted[Math.floor(sorted.length * 0.25)] || sorted[0] || 0;
      const median = sorted[Math.floor(sorted.length * 0.5)] || 0;
      const q3 = sorted[Math.floor(sorted.length * 0.75)] || sorted[sorted.length - 1] || 0;
      const min = sorted[0] || 0;
      const max = sorted[sorted.length - 1] || 0;
      const iqr = q3 - q1 || 1;
      const outliers = sorted.filter((v) => v < q1 - 1.5 * iqr || v > q3 + 1.5 * iqr);
      return { min, q1, median, q3, max, outliers };
    });
    return {
      label: title || `${properYCol} by ${groupCol}`,
      data: stats,
      backgroundColor: "rgba(59,130,246,0.25)",
      borderColor: "#3b82f6",
      borderWidth: 1,
    };
  }

  if (isRadar) {
    const sample = dataVals.slice(0, 12);
    return {
      label: title || properYCol,
      data: sample,
      backgroundColor: "rgba(59,130,246,0.25)",
      borderColor: "#3b82f6",
      borderWidth: 2,
      pointBackgroundColor: "#3b82f6",
      pointRadius: 3,
    };
  }

  if (specType === "heatmap") {
    const vals = dataVals.filter(v => Number.isFinite(v));
    if (!vals.length) return { label: title || properYCol, data: [] };
    // Use all source rows so dataLen matches query result
    const heatLabels = labels.slice(0, dataVals.length);
    const heatBackground = dataVals.slice(0, dataVals.length).map((v, i) => {
      const max = Math.max(...dataVals, 1);
      const intensity = Number.isFinite(v) ? v / max : 0;
      return `rgba(59,130,246,${(0.2 + 0.6 * Math.min(intensity, 1)).toFixed(3)})`;
    });
    return {
      label: title || `${properYCol} heatmap`,
      data: heatLabels.map((label, i) => ({ x: label, y: Number(dataVals[i] || 0), intensity: Number.isFinite(heatBackground[i]) ? parseFloat(heatBackground[i]) : 0 })),
      backgroundColor: heatBackground,
      borderColor: "rgba(15,23,42,0.9)",
      borderWidth: 1,
    };
  }

  return {
    label: title || `${properYCol} by ${properYCol}`,
    data: dataVals,
    backgroundColor: isPieOrDoughnut ? colors.slice(0, labels.length) : (isLine ? "rgba(59, 130, 246, 0.2)" : colors),
    borderColor: isLine ? "#3b82f6" : "transparent",
    borderWidth: isLine ? 3 : 0,
    tension: isLine ? 0.38 : 0,
    fill: isLine,
    borderRadius: isPieOrDoughnut ? 0 : 6,
  };
}

function renderChart(chartType, spec, rows = [], columns = []) {
  DEBUG.append("chart", `renderChart start type=${chartType} rows=${rows.length} cols=${columns.length}`);
  const requestedType = chartType || "bar";
  DEBUG.append("chart", `renderChart raw args type=${requestedType} rows=${rows.length}`);
  const map = { bar:"bar", line:"line", area:"line", doughnut:"doughnut", pie:"pie", polarArea:"polarArea", scatter:"scatter", histogram:"bar", box:"bar", radar:"radar", heatmap:"bar" };
  const safeType = map[requestedType] || "bar";
  const specType = spec?.chart_type || spec?.type || safeType;
  const canvas = $("chart-canvas");
  const placeholder = $("chart-placeholder");

  if (!rows.length || requestedType === "none") {
    canvas.hidden = true; placeholder.hidden = false;
    if (chartInstance) { try { chartInstance.destroy(); } catch {} chartInstance = null; }
    placeholder.textContent = rows.length ? "Chart not recommended for this result." : "No chart specification generated for this query.";
    DEBUG.append("chart", "renderChart exit empty/none");
    return;
  }
  canvas.hidden = false; placeholder.hidden = true;

  ensureChartAxisSelectors();
  populateChartAxisSelectors(columns);

  const xSel = $("chart-x-axis");
  const ySel = $("chart-y-axis");
  const enc = spec?.encoding || {};
  const preferredX = enc.x_axis || enc.x || null;
  const preferredY = enc.y_axis || enc.y || null;
  let xCol = preferredX || (xSel ? xSel.value : null) || _bestAxis(columns, rows, "x") || (columns[0] || "category");
  let yCol = preferredY || (ySel ? ySel.value : null) || _bestAxis(columns, rows, "y") || (columns[1] || columns[0] || "value");

  // If spec points to placeholder axes not present in actual data, replace with real columns
  if (!columns.includes(xCol)) xCol = _bestAxis(columns, rows, "x") || columns[0] || xCol;
  if (!columns.includes(yCol)) yCol = _bestAxis(columns, rows, "y") || (columns[1] || columns[0] || yCol);

  DEBUG.append("chart", `axis selected x=${xCol} y=${yCol}`);

  const properXCol = String(xCol).replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  const properYCol = String(yCol).replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

  const labels = rows.map(r => String(r[xCol] ?? ""));
  const dataVals = rows.map(r => (typeof r[yCol] === "number" ? r[yCol] : (parseFloat(r[yCol]) || 0)));

  const colors = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444", "#06b6d4", "#ec4899", "#6366f1", "#14b8a6", "#f97316"];

  if (!window.Chart) {
    placeholder.hidden = false;
    placeholder.textContent = "Chart engine unavailable.";
    DEBUG.append("error", "Chart engine unavailable");
    return;
  }
  if (chartInstance) {
    try { chartInstance.destroy(); } catch (e) { DEBUG.append("chart", `destroy old chart failed: ${e.message}`); }
    chartInstance = null;
  }

  const effectiveType = safeType === "area" ? "line" : safeType;
  const title = spec && spec.title;
  const dataset = _buildChartDataset(requestedType, labels, dataVals, colors, properYCol, title);
  DEBUG.append("chart", `dataset type=${requestedType} mapped=${safeType} dataLen=${dataset?.data?.length ?? "?"}`);

  let chartData;
  const isPieOrDoughnut = ["doughnut","pie","polarArea"].includes(requestedType);
  chartData = {
    labels,
    datasets: [dataset],
  };

  let chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: isPieOrDoughnut || ["bar","line","area"].includes(effectiveType) },
      title: {
        display: true,
        text: title || `Analytics (${requestedType.toUpperCase()})`,
        color: "#f8fafc",
        font: { family: "Inter", size: 14 }
      },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const raw = ctx.raw;
            if (requestedType === "scatter" && typeof raw === "object" && raw !== null) {
              return `X: ${raw.x}, Y: ${Number(raw.y).toLocaleString()}`;
            }
            if (requestedType === "heatmap" && typeof raw === "object" && raw !== null) {
              return `${raw.x}: ${Number(raw.y).toLocaleString()} (intensity ${(raw.intensity * 100).toFixed(0)}%)`;
            }
            if (requestedType === "box" && Array.isArray(raw)) {
              const item = raw[0];
              return `Min: ${item.min}, Q1: ${item.q1}, Median: ${item.median}, Q3: ${item.q3}, Max: ${item.max} · Outliers: ${item.outliers.length}`;
            }
            return `${properYCol}: ${Number(ctx.raw).toLocaleString()}`;
          }
        }
      }
    },
    scales: ["doughnut","pie","polarArea","radar"].includes(requestedType) ? {} : {
      x: { title: { display: true, text: properXCol, color: "#f8fafc" }, ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } },
      y: { title: { display: true, text: properYCol, color: "#f8fafc" }, ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" } }
    }
  };

  if (requestedType === "scatter" || requestedType === "heatmap") {
    chartData = {
      datasets: [
        {
          label: title || properYCol,
          data: dataset.data,
          backgroundColor: dataset.backgroundColor,
          borderColor: dataset.borderColor,
          borderWidth: dataset.borderWidth,
          pointBackgroundColor: "#3b82f6",
          pointRadius: requestedType === "scatter" ? 4 : 0,
        }
      ]
    };
  }

  if (requestedType === "radar") {
    chartData = {
      labels,
      datasets: [
        {
          label: title || properYCol,
          data: dataset.data,
          backgroundColor: dataset.backgroundColor,
          borderColor: dataset.borderColor,
          borderWidth: dataset.borderWidth,
          pointBackgroundColor: "#3b82f6",
          pointRadius: 3,
        }
      ]
    };
  }

  try {
    chartInstance = new window.Chart(canvas, {
      type: effectiveType,
      data: chartData,
      options: chartOptions,
    });

    if (canvas && requestedType !== "scatter" && requestedType !== "heatmap" && requestedType !== "radar") {
      canvas.onclick = (evt) => {
        try {
          const points = chartInstance.getElementsAtEventForMode(evt, "nearest", { intersect: true }, false);
          if (!points.length) return;
          const pt = points[0];
          const dsIndex = pt.datasetIndex;
          const label = chartInstance.data.labels?.[pt.index];
          if (label === undefined || label === null) return;

          const current = state._chartFilter || {};
          const key = `${requestedType}::${xCol}`;
          const active = current.key === key ? current.label : null;
          if (active === String(label)) {
            state._chartFilter = null;
            renderData(columns, rows);
            addAuditEntry(`clear chart filter: ${xCol}`, "-", false);
            DEBUG.append("chart", `click filter cleared ${xCol}=${label}`);
            return;
          }

          state._chartFilter = { key, label: String(label), xCol, yCol, requestedType };
          const filterFn = (r) => String(r[xCol] ?? "") === String(label);
          renderData(columns, rows, filterFn);
          addAuditEntry(`filter chart: ${xCol}=${label}`, "-", false);
          DEBUG.append("chart", `click filter applied ${xCol}=${label}`);
        } catch (err) {
          DEBUG.append("error", `chart click filter failed: ${err.message}`);
        }
      };
    }
    DEBUG.append("chart", "renderChart ok");
  } catch (err) {
    console.error(`Chart render failed for ${requestedType}:`, err);
    placeholder.hidden = false;
    placeholder.textContent = `Chart failed: ${err.message}`;
    DEBUG.append("error", `Chart render failed: ${err.message}`);
  }
}

function _bestAxis(columns, rows, side) {
  if (!columns.length || !rows.length) return null;
  const idLike = /^(id|_id|code|number|no|num|sl|sr$|date|dt)$/i;
  const textCols = [];
  const numCols = [];
  for (const c of columns) {
    const sample = rows.slice(0, 20).find((r) => {
      const v = r[c];
      return v !== null && v !== undefined && v !== "";
    });
    const val = sample ? sample[c] : null;
    if (val === null || val === undefined || val === "") continue;
    if (typeof val === "number") {
      numCols.push(c);
    } else {
      if (!idLike.test(c)) textCols.push(c);
    }
  }
  let fallbackForY = null;
  if (numCols.length) fallbackForY = numCols[0];
  else if (textCols.length) fallbackForY = textCols[0];
  else fallbackForY = columns.find((c) => !idLike.test(c)) || columns[0];

  if (side === "x") {
    return textCols[0] || fallbackForY || columns[0];
  }
  return fallbackForY;
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

// ---------- Debug Panel ----------
function updateDebugPanelMeta(data) {
  try {
    if ($("debug-provider")) $("debug-provider").textContent = `provider=${data?.provider || state.provider || "?"}`;
    if ($("debug-model")) $("debug-model").textContent = `model=${data?.model || state.model || "?"}`;
    if ($("debug-latency")) $("debug-latency").textContent = `latency=${data?.latency_ms ?? "?"}ms`;
    if ($("debug-fallback")) $("debug-fallback").textContent = `fallback=${data?.fallback_mode ? "yes" : "no"}`;
  } catch {}
}
const debugClearBtn = $("debug-clear");
if (debugClearBtn) debugClearBtn.addEventListener("click", () => DEBUG.clear());

// ---------- Init ----------
(function init() {
  applyLanguage(state.lang);
  if (state.token) viewer();
  else showAuth("login");
})();
