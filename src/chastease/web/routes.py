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
        <a class="btn btn-primary" href="/app">Zur Prototype App</a>
        <a class="btn btn-secondary" href="/docs">API Docs</a>
      </div>
      <div class="grid">
        <article class="card">
          <strong>1. User Setup</strong>
          <p>User anlegen/laden, optional Character erfassen, dann Session vorbereiten.</p>
        </article>
        <article class="card">
          <strong>2. Session Vertrag</strong>
          <p>Setup-Fragen + Psychogramm + Policy-Preview bilden die Session-Basis.</p>
        </article>
        <article class="card">
          <strong>3. Persistenter Verlauf</strong>
          <p>Story-Turns werden pro Session fortlaufend gespeichert und abrufbar gemacht.</p>
          <span class="badge">de/en unterstützt</span>
        </article>
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
    textarea { width: 100%; min-height: 280px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .small { font-size: 12px; color: #9ab0d8; }
    a { color: #7fb5ff; text-decoration: none; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Prototype App</h1>
    <p class="small"><a href="/">Zur Landingpage</a></p>

    <div class="card">
      <h2>0) Create / Load User</h2>
      <div class="row">
        <div><label>Email</label><input id="email" value="wearer@example.com" /></div>
        <div><label>Display Name</label><input id="displayName" value="Wearer Demo" /></div>
      </div>
      <button onclick="createUser()">Create / Load User</button>
      <p id="userInfo" class="small"></p>
    </div>

    <div class="card">
      <h2>1) Start Setup Session</h2>
      <div class="row">
        <div><label>User ID</label><input id="userId" placeholder="Create user first" /></div>
        <div><label>Autonomy Mode</label><select id="autonomy"><option value="execute">execute</option><option value="suggest">suggest</option></select></div>
        <div><label>Language</label><select id="language"><option value="de">Deutsch</option><option value="en">English</option></select></div>
        <div><label>Hard Stop</label><select id="hardStop"><option value="true">enabled</option><option value="false">disabled</option></select></div>
      </div>
      <button onclick="startSetup()">Start Setup</button>
      <p id="setupSessionInfo" class="small"></p>
    </div>

    <div class="card">
      <h2>2) Answer Questionnaire</h2>
      <p class="small">Questions are loaded dynamically from the setup endpoint.</p>
      <div id="questionGrid" class="qgrid"></div>
      <button onclick="submitAnswers()">Submit Answers</button>
    </div>

    <div class="card">
      <h2>3) Complete Setup</h2>
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

  <script>
    let userId = null;
    let setupSessionId = null;
    let questions = [];

    function setOutput(data) {
      document.getElementById("output").value = JSON.stringify(data, null, 2);
      if (data.psychogram_brief) document.getElementById("brief").textContent = data.psychogram_brief;
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

    async function createUser() {
      const payload = { email: document.getElementById("email").value, display_name: document.getElementById("displayName").value };
      const res = await fetch("/api/v1/users", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
      const data = await res.json();
      if (data.user_id) {
        userId = data.user_id;
        document.getElementById("userId").value = userId;
        document.getElementById("userInfo").textContent = `user_id: ${userId} (${data.email})`;
      }
      setOutput(data);
    }

    async function startSetup() {
      const selectedUserId = document.getElementById("userId").value || userId;
      if (!selectedUserId) return setOutput({error: "Create/load user first."});
      const payload = {
        user_id: selectedUserId,
        autonomy_mode: document.getElementById("autonomy").value,
        hard_stop_enabled: document.getElementById("hardStop").value === "true",
        language: document.getElementById("language").value,
        integrations: ["ttlock"]
      };
      const res = await fetch("/api/v1/setup/sessions", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload) });
      const data = await res.json();
      if (data.setup_session_id) {
        setupSessionId = data.setup_session_id;
        questions = data.questions || [];
        renderQuestions();
        document.getElementById("setupSessionInfo").textContent = "setup_session_id: " + setupSessionId;
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
      setOutput(await res.json());
    }

    async function completeSetup() {
      if (!setupSessionId) return setOutput({error: "Start setup first."});
      const res = await fetch(`/api/v1/setup/sessions/${setupSessionId}/complete`, { method: "POST" });
      setOutput(await res.json());
    }
  </script>
</body>
</html>
"""
