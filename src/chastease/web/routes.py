from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

web_router = APIRouter()


@web_router.get("/", response_class=HTMLResponse)
def landing_page() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Chastease</title>
  <style>
    :root {
      --bg: #f4f6fb;
      --ink: #0f172a;
      --muted: #5b6478;
      --card: #ffffff;
      --line: #d8deec;
      --brand: #1565c0;
      --brand-2: #0ea5a0;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(1200px 500px at 85% -20%, #cfe0ff 0%, transparent 60%),
        radial-gradient(900px 500px at -10% 120%, #c8f2e8 0%, transparent 55%),
        var(--bg);
      font-family: "Avenir Next", "Segoe UI", Arial, sans-serif;
    }
    .wrap { max-width: 1060px; margin: 0 auto; padding: 28px 20px 60px; }
    .hero {
      background: linear-gradient(145deg, #ffffff, #eef3ff);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 34px;
      box-shadow: 0 16px 40px rgba(20, 40, 80, 0.08);
    }
    h1 { margin: 0 0 10px; font-size: clamp(2rem, 4.5vw, 3rem); line-height: 1.05; }
    p { margin: 0; color: var(--muted); line-height: 1.5; }
    .actions { margin-top: 22px; display: flex; gap: 10px; flex-wrap: wrap; }
    .btn {
      display: inline-block;
      border-radius: 12px;
      padding: 11px 16px;
      text-decoration: none;
      font-weight: 700;
      border: 1px solid transparent;
    }
    .btn-primary { background: var(--brand); color: #fff; }
    .btn-secondary { background: #fff; border-color: var(--line); color: var(--ink); }
    .grid {
      margin-top: 18px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
    }
    .card strong { display: block; margin-bottom: 6px; }
    .badge {
      display: inline-block;
      margin-top: 8px;
      padding: 4px 8px;
      border-radius: 999px;
      background: #eaf2ff;
      color: #13407d;
      font-size: 12px;
      font-weight: 700;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>Chastease</h1>
      <p>Evolutionäres Prototyping für ein KI-gestütztes Session-Rollenspiel mit User-Setup, Psychogramm und persistentem Turn-Flow.</p>
      <div class="actions">
        <a class="btn btn-primary" href="/app?mode=login">Login</a>
        <a class="btn btn-secondary" href="/app?mode=register">Register</a>
      </div>
    </section>
  </div>
</body>
</html>
"""


@web_router.get("/app", response_class=HTMLResponse)
def app_shell(request: Request) -> str:
    session_kill_enabled = bool(getattr(request.app.state.config, "ENABLE_SESSION_KILL", False))
    kill_button_class = "danger" if session_kill_enabled else "hidden"
    html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Chastease Prototype App</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: "Avenir Next", "Segoe UI", Arial, sans-serif; margin: 0; background: #0b1220; color: #e8eefc; }
    .wrap { max-width: 1024px; margin: 0 auto; padding: 24px; }
    .card { background: #101a30; border: 1px solid #22314f; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
    h1, h2 { margin: 0 0 10px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
    .topbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
    .setup-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(220px, 1fr));
      gap: 10px 12px;
      max-width: 760px;
      margin-bottom: 12px;
      margin-right: auto;
    }
    .setup-item label {
      display: block;
      margin-bottom: 4px;
      font-size: 13px;
      color: #a9b9da;
      line-height: 1.2;
    }
    .setup-item input,
    .setup-item select {
      width: 100%;
      min-width: 0;
      max-width: 100%;
    }
    .setup-item input[type="date"] { max-width: 100%; }
    .qgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; }
    label { display: block; font-size: 13px; color: #a9b9da; margin-bottom: 4px; }
    input, select, button, textarea { border-radius: 8px; border: 1px solid #2b3d63; background: #0f1930; color: #e8eefc; padding: 8px 10px; }
    input[type=range] { width: 100%; padding: 0; }
    button { background: #2d8cff; border: 0; cursor: pointer; }
    button:hover { background: #4aa0ff; }
    button.ghost { background: transparent; border: 1px solid #2b3d63; }
    button.danger { background: #c62828; color: #fff; }
    button.danger:hover { background: #e53935; }
    textarea { width: 100%; min-height: 280px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .small { font-size: 12px; color: #9ab0d8; }
    a { color: #7fb5ff; text-decoration: none; }
    .hidden { display: none; }
    @media (max-width: 820px) {
      .setup-grid {
        grid-template-columns: 1fr;
        max-width: 100%;
      }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Prototype App</h1>
    <div class="topbar">
      <p class="small"><a href="/">Zur Landingpage</a></p>
      <button id="logoutTopBtn" class="ghost hidden" onclick="logoutUser()">Logout</button>
    </div>

    <div id="authCard" class="card">
      <h2>0) Login / Register</h2>
      <div class="row">
        <div><label>Username</label><input id="username" value="" /></div>
        <div id="emailWrap" class="hidden"><label>Email</label><input id="email" value="" /></div>
        <div><label>Password</label><input id="password" type="password" value="" /></div>
        <div id="passwordRepeatWrap" class="hidden"><label>Password repeat</label><input id="passwordRepeat" type="password" value="" /></div>
      </div>
      <div class="row">
        <button id="loginBtn" onclick="handleLoginClick()">Login</button>
        <button id="registerBtn" class="ghost" onclick="handleRegisterClick()">Register</button>
      </div>
      <p id="userInfo" class="small"></p>
    </div>

    <div id="dashboard" class="card hidden">
      <h2>1) Dashboard</h2>
      <p class="small">Aktive Session gefunden. Neue Registrierung und neues Setup sind gesperrt.</p>
      <p id="dashboardInfo" class="small"></p>
      <div id="dashboardContract" class="small"></div>
      <button id="killSessionBtn" class="__KILL_BUTTON_CLASS__" onclick="killActiveSession()">Session KILL</button>
    </div>

    <div id="appFlow" class="hidden">
    <div class="card">
      <h2>2) Start Setup Session</h2>
      <div class="setup-grid">
        <div class="setup-item"><label>Start Date</label><input id="contractStartDate" type="date" /></div>
        <div class="setup-item"><label>Max End Date</label><input id="contractMaxEndDate" type="date" /></div>
        <div class="setup-item"><label>Max Duration (days)</label><input id="contractMaxDurationDays" type="number" min="0" max="3650" value="30" /></div>
        <div class="setup-item"><label></label><div id="durationHint" class="small">If you change date or duration, the other value is auto-calculated. 0 days means AI decides end date.</div></div>
        <div class="setup-item"><label>Autonomy Mode</label><select id="autonomy"><option value="execute">execute</option><option value="suggest">suggest</option></select></div>
        <div class="setup-item"><label>Language</label><select id="language"><option value="de">Deutsch</option><option value="en">English</option></select></div>
        <div class="setup-item"><label>Hard Stop</label><select id="hardStop"><option value="true">enabled</option><option value="false">disabled</option></select></div>
        <div class="setup-item"><label>Penalty Caps</label><select id="penaltyCapsEnabled"><option value="true">enabled</option><option value="false">disabled</option></select></div>
        <div class="setup-item"><label>Max Penalty / Day (min)</label><input id="maxPenaltyDay" type="number" min="0" max="1440" value="60" /></div>
        <div class="setup-item"><label>Max Penalty / Week (min)</label><input id="maxPenaltyWeek" type="number" min="0" max="10080" value="240" /></div>
        <div class="setup-item"><label>Openings Period</label><select id="openingLimitPeriod"><option value="day">day</option><option value="week">week</option><option value="month">month</option></select></div>
        <div class="setup-item"><label>Max Openings / Period</label><input id="maxOpeningsInPeriod" type="number" min="0" max="200" value="1" /></div>
        <div class="setup-item"><label>Opening Window (min)</label><input id="openingWindowMinutes" type="number" min="1" max="240" value="30" /></div>
      </div>
      <button onclick="startSetup()">Start Setup</button>
      <p id="setupSessionInfo" class="small"></p>
    </div>

    <div class="card">
      <h2>3) Answer Questionnaire</h2>
      <p class="small">Questions are loaded dynamically from the setup endpoint.</p>
      <div id="questionGrid" class="qgrid"></div>
      <button onclick="submitAnswers()">Submit Answers</button>
    </div>

    <div class="card">
      <h2>4) Complete Setup</h2>
      <button onclick="completeSetup()">Complete Setup</button>
    </div>

    <div class="card">
      <h2>Psychogram Brief</h2>
      <p id="brief" class="small">No evaluation yet.</p>
    </div>

    <div class="card">
      <h2>Response</h2>
      <textarea id="output" readonly></textarea>
    </div>
    </div>
  </div>

  <script>
    let userId = null;
    let authToken = null;
    let setupSessionId = null;
    let questions = [];
    let activeSession = null;
    let authMode = "login";

    function authStorageKey() {
      return "chastease_auth_v1";
    }

    function saveAuth() {
      if (userId && authToken) {
        localStorage.setItem(authStorageKey(), JSON.stringify({ user_id: userId, auth_token: authToken }));
      }
    }

    function clearAuth() {
      localStorage.removeItem(authStorageKey());
    }

    function setAuthMode(mode) {
      authMode = mode === "register" ? "register" : "login";
      const registerMode = authMode === "register";
      document.getElementById("emailWrap").classList.toggle("hidden", !registerMode);
      document.getElementById("passwordRepeatWrap").classList.toggle("hidden", !registerMode);
      document.getElementById("loginBtn").classList.toggle("ghost", registerMode);
      document.getElementById("registerBtn").classList.toggle("ghost", !registerMode);
    }

    function handleLoginClick() {
      setAuthMode("login");
      loginUser();
    }

    function handleRegisterClick() {
      if (authMode !== "register") {
        setAuthMode("register");
        setOutput({info: "Register mode enabled. Please enter email and password repeat, then click Register again."});
        return;
      }
      registerUser();
    }

    function setOutput(data) {
      document.getElementById("output").value = JSON.stringify(data, null, 2);
      if (data.psychogram_brief) document.getElementById("brief").textContent = data.psychogram_brief;
    }

    async function safeJson(res) {
      try {
        return await res.json();
      } catch {
        const text = await res.text();
        return { error: "Server returned non-JSON response", status: res.status, body: text };
      }
    }

    function renderQuestions() {
      const grid = document.getElementById("questionGrid");
      grid.innerHTML = "";
      questions.forEach((q) => {
        const wrap = document.createElement("div");
        if (q.type === "scale_10" || q.type === "scale_5") {
          const mid = q.type === "scale_5" ? 3 : 5;
          wrap.innerHTML = `<label>${q.text} (${q.question_id})</label>
            <input id="q_${q.question_id}" type="range" min="${q.scale_min}" max="${q.scale_max}" step="1" value="${mid}" oninput="document.getElementById('v_${q.question_id}').textContent=this.value" />
            <div class="small">${q.scale_hint || ""}</div>
            <div class="small">Wert: <strong id="v_${q.question_id}">${mid}</strong></div>`;
        } else if (q.type === "choice") {
          const options = (q.options || []).map((o) => `<option value="${o.value}">${o.label}</option>`).join("");
          wrap.innerHTML = `<label>${q.text} (${q.question_id})</label><select id="q_${q.question_id}">${options}</select>`;
        } else {
          wrap.innerHTML = `<label>${q.text} (${q.question_id})</label><textarea id="q_${q.question_id}" rows="3" style="min-height:72px;"></textarea>`;
        }
        grid.appendChild(wrap);
      });
    }

    function setContractDefaults() {
      const now = new Date();
      const start = now.toISOString().slice(0, 10);
      const maxEnd = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
      document.getElementById("contractStartDate").value = start;
      document.getElementById("contractMaxEndDate").value = maxEnd;
      document.getElementById("contractMaxDurationDays").value = "30";
    }

    function selectOptionsByValue(id) {
      const map = {};
      Array.from(document.getElementById(id).options).forEach((opt) => {
        map[opt.value] = opt;
      });
      return map;
    }

    function applySetupTranslations() {
      const lang = document.getElementById("language").value;
      const de = {
        execute: "ausfuehren",
        suggest: "vorschlagen",
        enabled: "aktiviert",
        disabled: "deaktiviert",
        day: "Tag",
        week: "Woche",
        month: "Monat",
        duration_hint: "Wenn du Datum oder Dauer aenderst, wird der andere Wert automatisch berechnet. 0 Tage bedeutet: KI entscheidet das Enddatum.",
      };
      const en = {
        execute: "execute",
        suggest: "suggest",
        enabled: "enabled",
        disabled: "disabled",
        day: "day",
        week: "week",
        month: "month",
        duration_hint: "If you change date or duration, the other value is auto-calculated. 0 days means AI decides end date.",
      };
      const t = lang === "de" ? de : en;

      const autonomy = selectOptionsByValue("autonomy");
      autonomy.execute.textContent = t.execute;
      autonomy.suggest.textContent = t.suggest;

      const hardStop = selectOptionsByValue("hardStop");
      hardStop.true.textContent = t.enabled;
      hardStop.false.textContent = t.disabled;

      const penaltyCaps = selectOptionsByValue("penaltyCapsEnabled");
      penaltyCaps.true.textContent = t.enabled;
      penaltyCaps.false.textContent = t.disabled;

      const openingPeriod = selectOptionsByValue("openingLimitPeriod");
      openingPeriod.day.textContent = t.day;
      openingPeriod.week.textContent = t.week;
      openingPeriod.month.textContent = t.month;

      document.getElementById("durationHint").textContent = t.duration_hint;
    }

    function parseDateInput(id) {
      const raw = document.getElementById(id).value;
      if (!raw) return null;
      const date = new Date(`${raw}T00:00:00`);
      return Number.isNaN(date.getTime()) ? null : date;
    }

    function formatDateInput(date) {
      return date.toISOString().slice(0, 10);
    }

    function syncDurationFromEndDate() {
      const start = parseDateInput("contractStartDate");
      const end = parseDateInput("contractMaxEndDate");
      if (!start || !end) {
        document.getElementById("contractMaxDurationDays").value = "0";
        return;
      }
      const diffMs = end.getTime() - start.getTime();
      const diffDays = Math.max(0, Math.round(diffMs / (24 * 60 * 60 * 1000)));
      document.getElementById("contractMaxDurationDays").value = String(diffDays);
    }

    function syncEndDateFromDuration() {
      const start = parseDateInput("contractStartDate");
      const duration = Number(document.getElementById("contractMaxDurationDays").value);
      if (!start || Number.isNaN(duration)) return;
      const safeDuration = Math.max(0, duration);
      if (safeDuration === 0) {
        document.getElementById("contractMaxEndDate").value = "";
        return;
      }
      const end = new Date(start.getTime() + safeDuration * 24 * 60 * 60 * 1000);
      document.getElementById("contractMaxEndDate").value = formatDateInput(end);
    }

    function initContractSync() {
      document.getElementById("contractStartDate").addEventListener("change", syncEndDateFromDuration);
      document.getElementById("contractMaxEndDate").addEventListener("change", syncDurationFromEndDate);
      document.getElementById("contractMaxDurationDays").addEventListener("input", syncEndDateFromDuration);
      document.getElementById("language").addEventListener("change", applySetupTranslations);
    }

    function lockContractInputs(locked) {
      const ids = [
        "contractStartDate",
        "contractMaxEndDate",
        "contractMaxDurationDays",
        "autonomy",
        "language",
        "hardStop",
        "maxPenaltyDay",
        "maxPenaltyWeek",
        "penaltyCapsEnabled",
        "openingLimitPeriod",
        "maxOpeningsInPeriod",
        "openingWindowMinutes",
      ];
      ids.forEach((id) => {
        const node = document.getElementById(id);
        if (node) node.disabled = locked;
      });
    }

    function showSetupFlow() {
      document.getElementById("dashboard").classList.add("hidden");
      document.getElementById("appFlow").classList.remove("hidden");
    }

    function showDashboard(session) {
      activeSession = session;
      document.getElementById("dashboard").classList.remove("hidden");
      document.getElementById("appFlow").classList.add("hidden");
      document.getElementById("dashboardInfo").textContent =
        `session_id: ${session.session_id}, status: ${session.status}, language: ${session.language}`;
      const policy = session.policy || {};
      const contract = policy.contract || {};
      const limits = policy.limits || {};
      document.getElementById("dashboardContract").innerHTML = [
        `<p>Vertrag: ${contract.start_date || "-"} -> ${contract.end_date || "AI-defined"} (max ${contract.max_end_date || "-"})</p>`,
        `<p>Hard-Stop: ${policy.hard_stop_enabled ? "enabled" : "disabled"}</p>`,
        `<p>Penalty caps: day=${limits.max_penalty_per_day_minutes ?? "-"} min, week=${limits.max_penalty_per_week_minutes ?? "-"} min</p>`,
        `<p>Openings: ${limits.max_openings_in_period ?? limits.max_openings_per_day ?? "-"} / ${limits.opening_limit_period || "day"}, window=${limits.opening_window_minutes ?? "-"} min</p>`,
      ].join("");
    }

    function unlockFlow(data) {
      if (data.user_id && data.auth_token) {
        userId = data.user_id;
        authToken = data.auth_token;
        saveAuth();
        document.getElementById("userInfo").textContent = `username: ${data.username || data.display_name || "user"}`;
        document.getElementById("authCard").classList.add("hidden");
        document.getElementById("logoutTopBtn").classList.remove("hidden");
      }
    }

    async function checkActiveSession() {
      if (!userId || !authToken) return;
      const url = `/api/v1/sessions/active?user_id=${encodeURIComponent(userId)}&auth_token=${encodeURIComponent(authToken)}`;
      const res = await fetch(url);
      const data = await safeJson(res);
      if (res.ok && data.has_active_session && data.chastity_session) {
        showDashboard(data.chastity_session);
      } else if (res.ok) {
        showSetupFlow();
      }
    }

    async function registerUser() {
      if (userId) return setOutput({error: "Logout first if you want to register a different user."});
      if (document.getElementById("password").value !== document.getElementById("passwordRepeat").value) {
        return setOutput({error: "Password repeat does not match."});
      }
      const payload = {
        username: document.getElementById("username").value,
        email: document.getElementById("email").value,
        password: document.getElementById("password").value
      };
      const res = await fetch("/api/v1/auth/register", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
      const data = await safeJson(res);
      unlockFlow(data);
      if (res.ok) await checkActiveSession();
      setOutput(data);
    }

    async function loginUser() {
      const payload = {
        username: document.getElementById("username").value,
        password: document.getElementById("password").value
      };
      const res = await fetch("/api/v1/auth/login", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
      const data = await safeJson(res);
      unlockFlow(data);
      if (res.ok) await checkActiveSession();
      setOutput(data);
    }

    function logoutUser() {
      userId = null;
      authToken = null;
      setupSessionId = null;
      questions = [];
      activeSession = null;
      clearAuth();
      document.getElementById("userInfo").textContent = "";
      document.getElementById("setupSessionInfo").textContent = "";
      document.getElementById("dashboardInfo").textContent = "";
      document.getElementById("dashboardContract").innerHTML = "";
      document.getElementById("questionGrid").innerHTML = "";
      document.getElementById("dashboard").classList.add("hidden");
      document.getElementById("appFlow").classList.add("hidden");
      document.getElementById("authCard").classList.remove("hidden");
      document.getElementById("logoutTopBtn").classList.add("hidden");
      setAuthMode("login");
      lockContractInputs(false);
      setContractDefaults();
      setOutput({result: "logged_out"});
    }

    async function killActiveSession() {
      if (!userId || !authToken) return setOutput({error: "Login first."});
      const url = `/api/v1/sessions/active?user_id=${encodeURIComponent(userId)}&auth_token=${encodeURIComponent(authToken)}`;
      const res = await fetch(url, { method: "DELETE" });
      const data = await safeJson(res);
      setOutput(data);
      if (res.ok && data.deleted) {
        activeSession = null;
        document.getElementById("dashboard").classList.add("hidden");
        document.getElementById("dashboardInfo").textContent = "";
        document.getElementById("dashboardContract").innerHTML = "";
        document.getElementById("setupSessionInfo").textContent = "";
        setupSessionId = null;
        questions = [];
        document.getElementById("questionGrid").innerHTML = "";
        lockContractInputs(false);
        await checkActiveSession();
      }
    }

    async function startSetup() {
      if (!userId || !authToken) return setOutput({error: "Login/Register first."});
      const penaltyEnabled = document.getElementById("penaltyCapsEnabled").value === "true";
      const payload = {
        user_id: userId,
        auth_token: authToken,
        autonomy_mode: document.getElementById("autonomy").value,
        hard_stop_enabled: document.getElementById("hardStop").value === "true",
        language: document.getElementById("language").value,
        integrations: ["ttlock"],
        contract_start_date: document.getElementById("contractStartDate").value,
        contract_max_end_date: Number(document.getElementById("contractMaxDurationDays").value) === 0
          ? null
          : document.getElementById("contractMaxEndDate").value,
        ai_controls_end_date: true,
        max_penalty_per_day_minutes: penaltyEnabled ? Number(document.getElementById("maxPenaltyDay").value) : 0,
        max_penalty_per_week_minutes: penaltyEnabled ? Number(document.getElementById("maxPenaltyWeek").value) : 0,
        opening_limit_period: document.getElementById("openingLimitPeriod").value,
        max_openings_in_period: Number(document.getElementById("maxOpeningsInPeriod").value),
        opening_window_minutes: Number(document.getElementById("openingWindowMinutes").value),
      };
      const res = await fetch("/api/v1/setup/sessions", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
      const data = await safeJson(res);
      if (res.status === 409) {
        await checkActiveSession();
      }
      if (data.setup_session_id) {
        setupSessionId = data.setup_session_id;
        questions = data.questions || [];
        renderQuestions();
        lockContractInputs(true);
        const maxEnd = data.contract.max_end_date || "AI-decided";
        document.getElementById("setupSessionInfo").textContent =
          `setup_session_id: ${setupSessionId} | contract: ${data.contract.start_date} -> AI-defined (max ${maxEnd})`;
      }
      setOutput(data);
    }

    async function submitAnswers() {
      if (!setupSessionId) return setOutput({error: "Start setup first."});
      const answers = questions.map((q) => ({
        question_id: q.question_id,
        value: (q.type === "scale_10" || q.type === "scale_5")
          ? Number(document.getElementById(`q_${q.question_id}`).value)
          : document.getElementById(`q_${q.question_id}`).value,
      }));
      const res = await fetch(`/api/v1/setup/sessions/${setupSessionId}/answers`, {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({answers})
      });
      setOutput(await safeJson(res));
    }

    async function completeSetup() {
      if (!setupSessionId) return setOutput({error: "Start setup first."});
      const res = await fetch(`/api/v1/setup/sessions/${setupSessionId}/complete`, { method: "POST" });
      const data = await safeJson(res);
      setOutput(data);
      if (res.ok) await checkActiveSession();
    }

    async function bootstrapAuth() {
      const mode = new URLSearchParams(window.location.search).get("mode");
      if (mode === "register" || mode === "login") {
        setAuthMode(mode);
      } else {
        setAuthMode("login");
      }
      const raw = localStorage.getItem(authStorageKey());
      if (!raw) return;
      try {
        const parsed = JSON.parse(raw);
        if (!parsed.auth_token || !parsed.user_id) return;
        const res = await fetch(`/api/v1/auth/me?auth_token=${encodeURIComponent(parsed.auth_token)}`);
        const me = await safeJson(res);
        if (!res.ok) return clearAuth();
        unlockFlow({ ...me, auth_token: parsed.auth_token });
        await checkActiveSession();
      } catch {
        clearAuth();
      }
    }

    setContractDefaults();
    initContractSync();
    applySetupTranslations();
    bootstrapAuth();
  </script>
</body>
</html>
"""
    return html.replace("__KILL_BUTTON_CLASS__", kill_button_class)
