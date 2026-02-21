from fastapi import APIRouter
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
def app_shell() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Chastease Prototype App</title>
  <style>
    body { font-family: "Avenir Next", "Segoe UI", Arial, sans-serif; margin: 0; background: #0b1220; color: #e8eefc; }
    .wrap { max-width: 1024px; margin: 0 auto; padding: 24px; }
    .card { background: #101a30; border: 1px solid #22314f; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
    h1, h2 { margin: 0 0 10px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
    .qgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; }
    label { display: block; font-size: 13px; color: #a9b9da; margin-bottom: 4px; }
    input, select, button, textarea { border-radius: 8px; border: 1px solid #2b3d63; background: #0f1930; color: #e8eefc; padding: 8px 10px; }
    input[type=range] { width: 100%; padding: 0; }
    button { background: #2d8cff; border: 0; cursor: pointer; }
    button:hover { background: #4aa0ff; }
    button.ghost { background: transparent; border: 1px solid #2b3d63; }
    textarea { width: 100%; min-height: 280px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .small { font-size: 12px; color: #9ab0d8; }
    a { color: #7fb5ff; text-decoration: none; }
    .hidden { display: none; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Prototype App</h1>
    <p class="small"><a href="/">Zur Landingpage</a></p>

    <div class="card">
      <h2>0) Login / Register</h2>
      <div class="row">
        <button id="modeLoginBtn" onclick="setAuthMode('login')">Login</button>
        <button id="modeRegisterBtn" class="ghost" onclick="setAuthMode('register')">Register</button>
      </div>
      <div class="row">
        <div><label>Username</label><input id="username" value="wearer_demo" /></div>
        <div id="emailWrap" class="hidden"><label>Email</label><input id="email" value="wearer@example.com" /></div>
        <div><label>Password</label><input id="password" type="password" value="demo-pass-123" /></div>
        <div id="passwordRepeatWrap" class="hidden"><label>Password repeat</label><input id="passwordRepeat" type="password" value="demo-pass-123" /></div>
      </div>
      <button id="authActionBtn" onclick="loginUser()">Login</button>
      <button class="ghost" onclick="logoutUser()">Logout</button>
      <p id="userInfo" class="small"></p>
    </div>

    <div id="dashboard" class="card hidden">
      <h2>1) Dashboard</h2>
      <p class="small">Aktive Session gefunden. Neue Registrierung und neues Setup sind gesperrt.</p>
      <p id="dashboardInfo" class="small"></p>
      <div id="dashboardContract" class="small"></div>
    </div>

    <div id="appFlow" class="hidden">
    <div class="card">
      <h2>2) Start Setup Session</h2>
      <div class="row">
        <div><label>Start Date</label><input id="contractStartDate" type="date" /></div>
        <div><label>Max End Date</label><input id="contractMaxEndDate" type="date" /></div>
        <div><label>Autonomy Mode</label><select id="autonomy"><option value="execute">execute</option><option value="suggest">suggest</option></select></div>
        <div><label>Language</label><select id="language"><option value="de">Deutsch</option><option value="en">English</option></select></div>
        <div><label>Hard Stop</label><select id="hardStop"><option value="true">enabled</option><option value="false">disabled</option></select></div>
        <div><label>Max Penalty / Day (min)</label><input id="maxPenaltyDay" type="number" min="0" max="1440" value="60" /></div>
        <div><label>Max Penalty / Week (min)</label><input id="maxPenaltyWeek" type="number" min="0" max="10080" value="240" /></div>
        <div><label>Penalty Caps</label><select id="penaltyCapsEnabled"><option value="true">enabled</option><option value="false">disabled</option></select></div>
        <div><label>Openings Period</label><select id="openingLimitPeriod"><option value="day">day</option><option value="week">week</option><option value="month">month</option></select></div>
        <div><label>Max Openings / Period</label><input id="maxOpeningsInPeriod" type="number" min="0" max="200" value="1" /></div>
        <div><label>Opening Window (min)</label><input id="openingWindowMinutes" type="number" min="1" max="240" value="30" /></div>
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
      document.getElementById("authActionBtn").textContent = registerMode ? "Register" : "Login";
      document.getElementById("authActionBtn").onclick = registerMode ? registerUser : loginUser;
      document.getElementById("modeLoginBtn").classList.toggle("ghost", registerMode);
      document.getElementById("modeRegisterBtn").classList.toggle("ghost", !registerMode);
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
    }

    function lockContractInputs(locked) {
      const ids = [
        "contractStartDate",
        "contractMaxEndDate",
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
      lockContractInputs(false);
      setContractDefaults();
      setOutput({result: "logged_out"});
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
        contract_max_end_date: document.getElementById("contractMaxEndDate").value,
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
        document.getElementById("setupSessionInfo").textContent =
          `setup_session_id: ${setupSessionId} | contract: ${data.contract.start_date} -> AI-defined (max ${data.contract.max_end_date})`;
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
    bootstrapAuth();
  </script>
</body>
</html>
"""
