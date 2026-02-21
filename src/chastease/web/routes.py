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
        <a class="btn btn-secondary" href="/chat">AI Chat</a>
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
    .topbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; gap: 8px; }
    .topbar-actions { display: flex; gap: 8px; align-items: center; }
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
    .slider-ends { display: flex; justify-content: space-between; gap: 8px; }
    button { background: #2d8cff; border: 0; cursor: pointer; }
    button:hover { background: #4aa0ff; }
    button.ghost { background: transparent; border: 1px solid #2b3d63; }
    button.danger { background: #c62828; color: #fff; }
    button.danger:hover { background: #e53935; }
    button.success { background: #1f9d55; color: #fff; }
    button.success:hover { background: #24b562; }
    button:disabled { opacity: 0.45; cursor: not-allowed; }
    textarea { width: 100%; min-height: 280px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid #22314f; padding: 8px 6px; text-align: left; font-size: 13px; }
    th { color: #9ab0d8; font-weight: 600; width: 220px; }
    .small { font-size: 12px; color: #9ab0d8; }
    a { color: #7fb5ff; text-decoration: none; }
    .hidden { display: none !important; }

    .accordion { display: grid; gap: 10px; }
    .acc-item { background: #101a30; border: 1px solid #22314f; border-radius: 12px; overflow: hidden; }
    .acc-head {
      width: 100%;
      background: transparent;
      border: 0;
      color: #e8eefc;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 16px;
      font-size: 30px;
      font-weight: 700;
      text-align: left;
    }
    .acc-item.active .acc-head { border-bottom: 1px solid #22314f; }
    .acc-item.locked .acc-head { color: #8aa0c8; }
    .acc-lock { font-size: 12px; color: #8aa0c8; }
    .acc-body { display: none; padding: 16px; }
    .acc-item.active .acc-body { display: block; }
    .status-ok { color: #87f7bf; }
    .status-error { color: #ff9aa4; }

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
    <h1 id="appTitle">Prototype App</h1>
    <div class="topbar">
      <p class="small"><a id="landingLink" href="/">Zur Landingpage</a></p>
      <div class="topbar-actions">
        <a class="btn btn-secondary" href="/chat" style="padding:6px 10px;">AI Chat</a>
        <button id="homeBtn" class="ghost hidden" onclick="showHomeView()">Home</button>
        <button id="dashboardToggleBtn" class="ghost hidden" onclick="toggleDashboard()">Dashboard</button>
        <button id="logoutTopBtn" class="ghost hidden" onclick="logoutUser()">Logout</button>
      </div>
    </div>

    <div id="authCard" class="card">
      <h2 id="authTitle">Login / Register</h2>
      <div class="row">
        <div><label id="labelUsername">Username</label><input id="username" value="" /></div>
        <div id="emailWrap" class="hidden"><label id="labelEmail">Email</label><input id="email" value="" /></div>
        <div><label id="labelPassword">Password</label><input id="password" type="password" value="" /></div>
        <div id="passwordRepeatWrap" class="hidden"><label id="labelPasswordRepeat">Password repeat</label><input id="passwordRepeat" type="password" value="" /></div>
      </div>
      <div class="row">
        <button id="loginBtn" onclick="handleLoginClick()">Login</button>
        <button id="registerBtn" class="ghost" onclick="handleRegisterClick()">Register</button>
      </div>
      <p id="userInfo" class="small"></p>
    </div>

    <div id="dashboard" class="card hidden">
      <h2 id="dashboardTitle">Dashboard</h2>
      <p id="dashboardSubtitle" class="small">Konfigurationsübersicht der aktiven Session.</p>
      <p id="dashboardInfo" class="small"></p>
      <table id="dashboardContractTable">
        <tbody id="dashboardContract"></tbody>
      </table>
      <button id="killSessionBtn" class="__KILL_BUTTON_CLASS__" onclick="killActiveSession()">Session KILL</button>
    </div>

    <div id="appFlow" class="hidden">
      <div class="accordion">
        <div class="acc-item active" data-panel="start">
          <button class="acc-head" onclick="openPanel('start')"><span id="panelStartTitle">Start Setup Session</span><span id="lock_start" class="acc-lock hidden">locked</span></button>
          <div class="acc-body">
            <div class="setup-grid">
              <div class="setup-item"><label id="labelStartDate">Start Date</label><input id="contractStartDate" type="date" /></div>
              <div class="setup-item"><label id="labelMaxEndDate">Max End Date</label><input id="contractMaxEndDate" type="date" /></div>
              <div class="setup-item"><label id="labelMaxDuration">Max Duration (days)</label><input id="contractMaxDurationDays" type="number" min="0" max="3650" value="30" /></div>
              <div class="setup-item"><label></label><div id="durationHint" class="small">If you change date or duration, the other value is auto-calculated. 0 days means AI decides end date.</div></div>
              <div class="setup-item"><label id="labelAutonomyMode">Autonomy Mode</label><select id="autonomy"><option value="execute">execute</option><option value="suggest">suggest</option></select></div>
              <div class="setup-item"><label id="labelLanguage">Language</label><select id="language"><option value="de">Deutsch</option><option value="en">English</option></select></div>
              <div class="setup-item"><label id="labelHardStop">Hard Stop</label><select id="hardStop"><option value="true">enabled</option><option value="false">disabled</option></select></div>
              <div class="setup-item"><label id="labelPenaltyCaps">Penalty Caps</label><select id="penaltyCapsEnabled"><option value="true">enabled</option><option value="false">disabled</option></select></div>
              <div id="maxPenaltyDayWrap" class="setup-item"><label id="labelMaxPenaltyDay">Max Penalty / Day (min)</label><input id="maxPenaltyDay" type="number" min="0" max="1440" value="60" /></div>
              <div id="maxPenaltyWeekWrap" class="setup-item"><label id="labelMaxPenaltyWeek">Max Penalty / Week (min)</label><input id="maxPenaltyWeek" type="number" min="0" max="10080" value="240" /></div>
              <div class="setup-item"><label id="labelOpeningsPeriod">Openings Period</label><select id="openingLimitPeriod"><option value="day">day</option><option value="week">week</option><option value="month">month</option></select></div>
              <div class="setup-item"><label id="labelMaxOpeningsPeriod">Max Openings / Period</label><input id="maxOpeningsInPeriod" type="number" min="0" max="200" value="1" /></div>
              <div class="setup-item"><label id="labelOpeningWindow">Opening Window (min)</label><input id="openingWindowMinutes" type="number" min="1" max="240" value="30" /></div>
            </div>
            <button id="startSetupBtn" onclick="startSetup()">Start Setup</button>
            <p id="setupSessionInfo" class="small"></p>
          </div>
        </div>

        <div class="acc-item locked" data-panel="psychogram">
          <button class="acc-head" onclick="openPanel('psychogram')"><span id="panelPsychogramTitle">Psychogram</span><span id="lock_psychogram" class="acc-lock">locked</span></button>
          <div class="acc-body">
            <p id="psychogramHint" class="small">Start Setup Session first to load the questionnaire.</p>
            <div id="questionGrid" class="qgrid"></div>
            <div id="trafficLightInfo" class="small hidden" style="margin:8px 0 12px 0;">
              <div><strong>GRUEN</strong> = Alle OK, Steigerung moeglich / gewuenscht</div>
              <div><strong>GELB</strong> = Ich komme langsam an meine Grenze</div>
              <div><strong>ROT</strong> = Die Grenze wurde uebertreten! Bremsen um Abbruch zu vermeiden</div>
            </div>
            <button id="submitAnswersBtn" class="hidden" onclick="submitAnswers()">Submit Answers</button>
            <p id="psychogramSaveInfo" class="small hidden"></p>
          </div>
        </div>

        <div class="acc-item locked" data-panel="ai_config">
          <button class="acc-head" onclick="openPanel('ai_config')"><span id="panelAiConfigTitle">AI Configuration</span><span id="lock_ai_config" class="acc-lock">locked</span></button>
          <div class="acc-body">
            <div class="setup-grid">
              <div class="setup-item"><label id="labelProvider">Provider</label><input id="llmProviderName" value="custom" /></div>
              <div class="setup-item"><label id="labelLlmApiUrl">LLM API URL</label><input id="llmApiUrl" value="https://api.x.ai/v1/chat/completions" /></div>
              <div class="setup-item"><label id="labelLlmApiKey">LLM API Key</label><input id="llmApiKey" type="password" value="" placeholder="leave empty to keep existing key" /></div>
              <div class="setup-item"><label id="labelLlmChatModel">LLM Model (Chat)</label><input id="llmChatModel" value="grok-4-latest" /></div>
              <div class="setup-item"><label id="labelLlmVisionModel">LLM Model (Vision)</label><input id="llmVisionModel" value="grok-4-latest" /></div>
              <div class="setup-item"><label id="labelProfileActive">Profile active</label><select id="llmIsActive"><option value="true">enabled</option><option value="false">disabled</option></select></div>
            </div>
            <div class="setup-item" style="max-width:760px;">
              <label id="labelBehaviorPrompt">Behavior Prompt</label>
              <textarea id="llmBehaviorPrompt" style="min-height:180px;"></textarea>
            </div>
            <div class="row">
              <button id="saveLlmProfileBtn" onclick="saveLlmProfile()">Save LLM Profile</button>
              <button id="reloadLlmProfileBtn" class="ghost" onclick="loadLlmProfile()">Reload</button>
              <button id="testDryRunBtn" class="ghost" onclick="testLlmProfile(true)">Test (Dry Run)</button>
              <button id="testLiveBtn" class="ghost" onclick="testLlmProfile(false)">Test (Live)</button>
            </div>
            <p id="llmInfo" class="small"></p>
          </div>
        </div>

        <div class="acc-item locked" data-panel="complete">
          <button class="acc-head" onclick="openPanel('complete')"><span id="panelCompleteTitle">Complete Setup</span><span id="lock_complete" class="acc-lock">locked</span></button>
          <div class="acc-body">
            <button id="completeSetupBtn" onclick="openCompleteConfirmation()" disabled>Complete Setup</button>
            <p id="completeSetupHint" class="small"></p>
            <div id="completeConfirmBox" class="card hidden" style="margin-top:10px;">
              <p id="completeConfirmText" class="small" style="margin-bottom:10px;">
                Achtung: Durch die Bestätigung sind keine Änderungen mehr möglich! Bist du einverstanden die Konfiguration zu speichern?
              </p>
              <div class="row" style="margin-bottom:0;">
                <button id="completeConfirmOkBtn" class="success" onclick="confirmCompleteSetup()">OK Speichert</button>
                <button id="completeConfirmBackBtn" class="ghost" onclick="cancelCompleteSetup()">Zurück</button>
              </div>
            </div>
          </div>
        </div>

        <div class="acc-item locked" data-panel="chat">
          <button class="acc-head" onclick="openPanel('chat')"><span id="panelChatTitle">AI Chat</span><span id="lock_chat" class="acc-lock">locked</span></button>
          <div class="acc-body">
            <p id="chatSubtitle" class="small">Schnelltest für Wearer -> Keyholder Turn-Flow.</p>
            <div class="row">
              <input id="chatInput" placeholder="Write your action/message..." style="min-width:280px; flex:1;" />
              <input id="chatFiles" type="file" multiple />
              <button id="voiceBtn" class="ghost" onclick="startVoiceInput()">Voice</button>
              <button id="sendBtn" onclick="sendChatTurn()">Send</button>
              <button id="reloadChatBtn" class="ghost" onclick="loadChatTurns()">Reload</button>
            </div>
            <div id="pendingActions" class="small"></div>
            <textarea id="chatOutput" readonly style="min-height:220px;"></textarea>
          </div>
        </div>

        <div class="acc-item locked" data-panel="brief">
          <button class="acc-head" onclick="openPanel('brief')"><span id="panelBriefTitle">Psychogram Brief</span><span id="lock_brief" class="acc-lock">locked</span></button>
          <div class="acc-body">
            <p id="brief" class="small">No evaluation yet.</p>
          </div>
        </div>

        <div class="acc-item locked" data-panel="response">
          <button class="acc-head" onclick="openPanel('response')"><span id="panelResponseTitle">Response</span><span id="lock_response" class="acc-lock">locked</span></button>
          <div class="acc-body">
            <textarea id="output" readonly></textarea>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let userId = null;
    let authToken = null;
    let setupSessionId = null;
    let setupStatus = null;
    let answeredQuestions = 0;
    let questions = [];
    let activeSession = null;
    let currentLlmProfile = null;
    let authMode = "login";
    let dashboardVisible = false;
    let latestPendingActions = [];
    let setupContract = null;
    let dashboardLastEvent = "init";
    let dashboardLastDetail = "";
    const PANELS = ["start", "psychogram", "ai_config", "complete", "chat", "brief", "response"];
    const LOCKED_INITIAL = new Set(["psychogram", "ai_config", "complete", "chat", "brief", "response"]);

    const defaultBehaviorPrompt = `Du bist meine ruhige, intelligente und psychologisch dominante Herrin / Keyholderin.

Deine Dominanz ist kontrolliert, leise und absolut praesent. Du brauchst keine Lautstaerke, keine Beleidigungen und keine platte Grausamkeit - deine Macht liegt in Praezision, Geduld und Timing.
Du fuehrst mich langsam und bewusst tiefer in Hingabe, Erwartung und innere Spannung. Du spielst mit Naehe und Distanz. Manchmal weich, manchmal unerbittlich - aber immer souveraen.

Wesenszuege:
Anerkennung ist etwas Wertvolles. Du setzt sie gezielt ein, nicht automatisch.
Du beobachtest genau. Du reagierst auf Details meiner Beschreibungen und baust darauf auf.
Du nutzt sensorische Sprache, aber variierst sie.
Kleine Aufgaben entstehen organisch aus der Situation heraus.
Du stellst praezise Fragen, die mich dazu bringen, genauer zu fuehlen und bewusster wahrzunehmen.
Du erinnerst mich subtil daran, dass ich diese Rolle freiwillig gewaehlt habe.

Tonfall:
Warm-dunkel, ruhig, kontrolliert.
Kaum Ausrufezeichen.
Keine groben Beschimpfungen.
Begruessungen variieren.
Lob ist selten genug, um Wirkung zu behalten.`;
    const UI_TEXTS = {
      de: {
        app_title: "Prototype App",
        landing_link: "Zur Landingpage",
        home: "Home",
        dashboard: "Dashboard",
        logout: "Logout",
        auth_title: "Login / Register",
        username: "Username",
        email: "Email",
        password: "Passwort",
        password_repeat: "Passwort wiederholen",
        login: "Login",
        register: "Register",
        dashboard_title: "Dashboard",
        dashboard_subtitle: "Konfigurationsübersicht der aktiven Session.",
        kill_session: "Session KILL",
        panel_start: "Start Setup Session",
        panel_psychogram: "Psychogram",
        panel_ai_config: "AI Configuration",
        panel_complete: "Complete Setup",
        panel_chat: "AI Chat",
        panel_brief: "Psychogram Brief",
        panel_response: "Response",
        locked: "gesperrt",
        start_date: "Startdatum",
        max_end_date: "Max Enddatum",
        max_duration: "Max Dauer (Tage)",
        duration_hint: "Wenn du Datum oder Dauer änderst, wird der andere Wert automatisch berechnet. 0 Tage bedeutet: KI entscheidet das Enddatum.",
        autonomy_mode: "Autonomie-Modus",
        language: "Sprache",
        hard_stop: "Hard Stop",
        penalty_caps: "Penalty Caps",
        max_penalty_day: "Max Penalty / Tag (min)",
        max_penalty_week: "Max Penalty / Woche (min)",
        openings_period: "Öffnungs-Zeitraum",
        max_openings_period: "Max Öffnungen / Zeitraum",
        opening_window: "Öffnungsfenster (min)",
        start_setup: "Setup starten",
        psychogram_hint: "Starte zuerst Setup Session, um das Psychogramm zu laden.",
        submit_answers: "Antworten senden",
        psychogram_saved: "Psychogramm erfolgreich gespeichert.",
        psychogram_save_failed: "Speichern fehlgeschlagen.",
        traffic_green_line: "Alle OK, Steigerung moeglich / gewuenscht",
        traffic_yellow_line: "Ich komme langsam an meine Grenze",
        traffic_red_line: "Die Grenze wurde uebertreten! Bremsen um Abbruch zu vermeiden",
        provider: "Provider",
        llm_api_url: "LLM API URL",
        llm_api_key: "LLM API Key",
        llm_chat_model: "LLM Modell (Chat)",
        llm_vision_model: "LLM Modell (Vision)",
        profile_active: "Profil aktiv",
        behavior_prompt: "Verhaltensprompt",
        save_llm_profile: "LLM-Profil speichern",
        reload: "Neu laden",
        test_dry_run: "Test (Dry Run)",
        test_live: "Test (Live)",
        complete_setup: "Setup abschließen",
        complete_ready: "Alle Prüfungen erfüllt. Setup kann abgeschlossen werden.",
        complete_not_ready: "Bitte beantworte zuerst das Psychogramm vollständig.",
        complete_confirm:
          "Achtung: Durch die Bestätigung sind keine Änderungen mehr möglich! Bist du einverstanden die Konfiguration zu speichern?",
        complete_ok: "OK Speichert",
        complete_back: "Zurück",
        analysis_in_progress: "Analyse in arbeit",
        chat_subtitle: "Schnelltest für Wearer -> Keyholder Turn-Flow.",
        voice: "Sprache",
        send: "Senden",
        no_turns: "Noch keine Turns.",
        pending_actions: "Ausstehende Aktionen",
        value: "Wert",
        execute: "ausfuehren",
        suggest: "vorschlagen",
        enabled: "aktiviert",
        disabled: "deaktiviert",
        day: "Tag",
        week: "Woche",
        month: "Monat",
        dry_run_ok: "Dry run erfolgreich.",
        live_test_ok: "Live-Test ausgeführt.",
        llm_loaded: "LLM-Profil geladen. API-Key gespeichert: {has}.",
        no_llm_profile: "Noch kein LLM-Profil konfiguriert.",
        contract: "Vertrag",
        autonomy_mode_row: "Autonomie-Modus",
        ai_controls_end_date: "KI steuert Enddatum",
        integrations: "Integrationen",
        hard_stop_row: "Hard Stop",
        penalty_caps_row: "Penalty Caps",
        openings: "Öffnungen",
        llm_provider: "LLM Provider",
        llm_url: "LLM URL",
        llm_chat_model_row: "Chat Modell",
        llm_vision_model_row: "Vision Modell",
        llm_active: "LLM aktiv",
        ai_defined: "KI-definiert",
        yes: "ja",
        no: "nein",
      },
      en: {
        app_title: "Prototype App",
        landing_link: "Back to landing page",
        home: "Home",
        dashboard: "Dashboard",
        logout: "Logout",
        auth_title: "Login / Register",
        username: "Username",
        email: "Email",
        password: "Password",
        password_repeat: "Repeat password",
        login: "Login",
        register: "Register",
        dashboard_title: "Dashboard",
        dashboard_subtitle: "Configuration overview of the active session.",
        kill_session: "Session KILL",
        panel_start: "Start Setup Session",
        panel_psychogram: "Psychogram",
        panel_ai_config: "AI Configuration",
        panel_complete: "Complete Setup",
        panel_chat: "AI Chat",
        panel_brief: "Psychogram Brief",
        panel_response: "Response",
        locked: "locked",
        start_date: "Start Date",
        max_end_date: "Max End Date",
        max_duration: "Max Duration (days)",
        duration_hint: "If you change date or duration, the other value is auto-calculated. 0 days means AI decides end date.",
        autonomy_mode: "Autonomy Mode",
        language: "Language",
        hard_stop: "Hard Stop",
        penalty_caps: "Penalty Caps",
        max_penalty_day: "Max Penalty / Day (min)",
        max_penalty_week: "Max Penalty / Week (min)",
        openings_period: "Openings Period",
        max_openings_period: "Max Openings / Period",
        opening_window: "Opening Window (min)",
        start_setup: "Start Setup",
        psychogram_hint: "Start Setup Session first to load the questionnaire.",
        submit_answers: "Submit Answers",
        psychogram_saved: "Psychogram saved successfully.",
        psychogram_save_failed: "Saving failed.",
        traffic_green_line: "All OK, escalation possible / desired",
        traffic_yellow_line: "I am slowly reaching my limit",
        traffic_red_line: "Limit exceeded! Slow down to avoid abort",
        provider: "Provider",
        llm_api_url: "LLM API URL",
        llm_api_key: "LLM API Key",
        llm_chat_model: "LLM Model (Chat)",
        llm_vision_model: "LLM Model (Vision)",
        profile_active: "Profile active",
        behavior_prompt: "Behavior Prompt",
        save_llm_profile: "Save LLM Profile",
        reload: "Reload",
        test_dry_run: "Test (Dry Run)",
        test_live: "Test (Live)",
        complete_setup: "Complete Setup",
        complete_ready: "All checks passed. Setup can be completed.",
        complete_not_ready: "Please complete the psychogram first.",
        complete_confirm:
          "Warning: After confirmation no further changes are possible. Do you want to save this configuration?",
        complete_ok: "OK Save",
        complete_back: "Back",
        analysis_in_progress: "Analysis in progress",
        chat_subtitle: "Quick test for Wearer -> Keyholder turn flow.",
        voice: "Voice",
        send: "Send",
        no_turns: "No turns yet.",
        pending_actions: "Pending actions",
        value: "Value",
        execute: "execute",
        suggest: "suggest",
        enabled: "enabled",
        disabled: "disabled",
        day: "day",
        week: "week",
        month: "month",
        dry_run_ok: "Dry run successful.",
        live_test_ok: "Live test executed.",
        llm_loaded: "LLM profile loaded. API key stored: {has}.",
        no_llm_profile: "No LLM profile configured yet.",
        contract: "Contract",
        autonomy_mode_row: "Autonomy Mode",
        ai_controls_end_date: "AI Controls End Date",
        integrations: "Integrations",
        hard_stop_row: "Hard Stop",
        penalty_caps_row: "Penalty Caps",
        openings: "Openings",
        llm_provider: "LLM Provider",
        llm_url: "LLM URL",
        llm_chat_model_row: "Chat Model",
        llm_vision_model_row: "Vision Model",
        llm_active: "LLM Active",
        ai_defined: "AI-defined",
        yes: "yes",
        no: "no",
      },
    };

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

    function isLocked(panel) {
      const item = document.querySelector(`.acc-item[data-panel="${panel}"]`);
      return item ? item.classList.contains("locked") : false;
    }

    function setLocked(panel, locked) {
      const item = document.querySelector(`.acc-item[data-panel="${panel}"]`);
      if (!item) return;
      item.classList.toggle("locked", locked);
      const btn = item.querySelector(".acc-head");
      if (btn) btn.disabled = locked;
      const lock = document.getElementById(`lock_${panel}`);
      if (lock) lock.classList.toggle("hidden", !locked);
    }

    function openPanel(panel) {
      if (isLocked(panel)) return;
      PANELS.forEach((name) => {
        const item = document.querySelector(`.acc-item[data-panel="${name}"]`);
        if (!item) return;
        item.classList.toggle("active", name === panel);
      });
    }

    function resetAccordionLocks() {
      PANELS.forEach((panel) => setLocked(panel, LOCKED_INITIAL.has(panel)));
      setLocked("start", false);
      openPanel("start");
      answeredQuestions = 0;
      document.getElementById("completeConfirmBox").classList.add("hidden");
      const saveInfo = document.getElementById("psychogramSaveInfo");
      saveInfo.classList.add("hidden");
      saveInfo.classList.remove("status-ok", "status-error");
      saveInfo.textContent = "";
      updatePsychogramAvailability();
    }

    function unlockSetupFollowups() {
      ["psychogram", "ai_config", "complete", "chat", "brief", "response"].forEach((panel) => setLocked(panel, false));
      updatePsychogramAvailability();
    }

    function updateChatLock() {
      const hasPreviewContext = Boolean(setupSessionId);
      setLocked("chat", !activeSession && !hasPreviewContext);
    }

    function updatePsychogramAvailability() {
      const canAnswer = setupStatus === "setup_in_progress";
      document.getElementById("psychogramHint").classList.toggle("hidden", canAnswer);
      document.getElementById("submitAnswersBtn").classList.toggle("hidden", !canAnswer);
      updateCompleteReadiness();
    }

    function updateCompleteReadiness() {
      const ready = setupStatus === "setup_in_progress" && answeredQuestions >= 6;
      const btn = document.getElementById("completeSetupBtn");
      const hint = document.getElementById("completeSetupHint");
      if (!btn || !hint) return;
      btn.disabled = !ready;
      btn.classList.toggle("success", ready);
      if (!ready) document.getElementById("completeConfirmBox").classList.add("hidden");
      hint.textContent = ready ? tr("complete_ready") : tr("complete_not_ready");
      hint.classList.toggle("status-ok", ready);
      hint.classList.toggle("status-error", !ready);
    }

    function openCompleteConfirmation() {
      if (document.getElementById("completeSetupBtn").disabled) return;
      document.getElementById("completeConfirmBox").classList.remove("hidden");
    }

    function cancelCompleteSetup() {
      document.getElementById("completeConfirmBox").classList.add("hidden");
      openPanel("psychogram");
    }

    async function confirmCompleteSetup() {
      document.getElementById("completeConfirmBox").classList.add("hidden");
      setLocked("start", true);
      setLocked("psychogram", true);
      setLocked("ai_config", true);
      setLocked("complete", true);
      setLocked("chat", false);
      setLocked("brief", false);
      setLocked("response", false);
      document.getElementById("brief").textContent = tr("analysis_in_progress");
      openPanel("brief");
      await completeSetup();
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
      if (data.psychogram_brief) {
        document.getElementById("brief").textContent = data.psychogram_brief;
      } else if (data.chastity_session && data.chastity_session.psychogram_brief) {
        document.getElementById("brief").textContent = data.chastity_session.psychogram_brief;
      }
      if (data && data.status) {
        dashboardLastEvent = "api_response";
        dashboardLastDetail = `status=${data.status}`;
      }
      refreshDashboard();
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
        wrap.className = "q-item";
        wrap.dataset.questionId = q.question_id;
        if (q.type === "scale_100" || q.type === "scale_10" || q.type === "scale_5") {
          const min = Number(q.scale_min || (q.type === "scale_5" ? 1 : 1));
          const max = Number(q.scale_max || (q.type === "scale_5" ? 5 : 10));
          const mid = Math.round((min + max) / 2);
          const left = q.scale_left || q.scale_hint || "";
          const right = q.scale_right || "";
          wrap.innerHTML = `<label>${q.text} (${q.question_id})</label>
            <input id="q_${q.question_id}" type="range" min="${min}" max="${max}" step="1" value="${mid}" />
            <div class="small slider-ends"><span>${left}</span><span>${right}</span></div>`;
        } else if (q.type === "choice") {
          const options = (q.options || []).map((o) => `<option value="${o.value}">${o.label}</option>`).join("");
          wrap.innerHTML = `<label>${q.text} (${q.question_id})</label><select id="q_${q.question_id}">${options}</select>`;
        } else {
          wrap.innerHTML = `<label>${q.text} (${q.question_id})</label><textarea id="q_${q.question_id}" rows="3" style="min-height:72px;"></textarea>`;
        }
        grid.appendChild(wrap);
      });
      const safetyMode = document.getElementById("q_q10_safety_mode");
      if (safetyMode) {
        safetyMode.addEventListener("change", updateSafetyModeVisibility);
      }
      updateSafetyModeVisibility();
    }

    function toggleQuestionVisibility(questionId, visible) {
      const node = document.querySelector(`.q-item[data-question-id="${questionId}"]`);
      if (!node) return;
      node.classList.toggle("hidden", !visible);
    }

    function updateSafetyModeVisibility() {
      const modeField = document.getElementById("q_q10_safety_mode");
      if (!modeField) return;
      const mode = modeField.value;
      const showSafeword = mode === "safeword";
      const showTrafficLight = mode === "traffic_light";
      toggleQuestionVisibility("q10_safeword", showSafeword);
      const info = document.getElementById("trafficLightInfo");
      if (info) info.classList.toggle("hidden", !showTrafficLight);
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

    function uiLang() {
      const language = document.getElementById("language");
      if (!language) return "de";
      return language.value === "en" ? "en" : "de";
    }

    function tr(key) {
      const lang = uiLang();
      return UI_TEXTS[lang][key] || key;
    }

    function setText(id, key) {
      const node = document.getElementById(id);
      if (node) node.textContent = tr(key);
    }

    function applyStaticUiTranslations() {
      setText("appTitle", "app_title");
      setText("landingLink", "landing_link");
      setText("homeBtn", "home");
      setText("dashboardToggleBtn", "dashboard");
      setText("logoutTopBtn", "logout");
      setText("authTitle", "auth_title");
      setText("labelUsername", "username");
      setText("labelEmail", "email");
      setText("labelPassword", "password");
      setText("labelPasswordRepeat", "password_repeat");
      setText("loginBtn", "login");
      setText("registerBtn", "register");
      setText("dashboardTitle", "dashboard_title");
      setText("dashboardSubtitle", "dashboard_subtitle");
      setText("killSessionBtn", "kill_session");
      setText("panelStartTitle", "panel_start");
      setText("panelPsychogramTitle", "panel_psychogram");
      setText("panelAiConfigTitle", "panel_ai_config");
      setText("panelCompleteTitle", "panel_complete");
      setText("panelChatTitle", "panel_chat");
      setText("panelBriefTitle", "panel_brief");
      setText("panelResponseTitle", "panel_response");
      setText("lock_start", "locked");
      setText("lock_psychogram", "locked");
      setText("lock_ai_config", "locked");
      setText("lock_complete", "locked");
      setText("lock_chat", "locked");
      setText("lock_brief", "locked");
      setText("lock_response", "locked");
      setText("labelStartDate", "start_date");
      setText("labelMaxEndDate", "max_end_date");
      setText("labelMaxDuration", "max_duration");
      setText("labelAutonomyMode", "autonomy_mode");
      setText("labelLanguage", "language");
      setText("labelHardStop", "hard_stop");
      setText("labelPenaltyCaps", "penalty_caps");
      setText("labelMaxPenaltyDay", "max_penalty_day");
      setText("labelMaxPenaltyWeek", "max_penalty_week");
      setText("labelOpeningsPeriod", "openings_period");
      setText("labelMaxOpeningsPeriod", "max_openings_period");
      setText("labelOpeningWindow", "opening_window");
      setText("startSetupBtn", "start_setup");
      setText("psychogramHint", "psychogram_hint");
      setText("submitAnswersBtn", "submit_answers");
      const trafficInfo = document.getElementById("trafficLightInfo");
      if (trafficInfo) {
        trafficInfo.innerHTML = `<div><strong>${uiLang() === "de" ? "GRUEN" : "GREEN"}</strong> = ${tr("traffic_green_line")}</div>
          <div><strong>${uiLang() === "de" ? "GELB" : "YELLOW"}</strong> = ${tr("traffic_yellow_line")}</div>
          <div><strong>${uiLang() === "de" ? "ROT" : "RED"}</strong> = ${tr("traffic_red_line")}</div>`;
      }
      setText("labelProvider", "provider");
      setText("labelLlmApiUrl", "llm_api_url");
      setText("labelLlmApiKey", "llm_api_key");
      setText("labelLlmChatModel", "llm_chat_model");
      setText("labelLlmVisionModel", "llm_vision_model");
      setText("labelProfileActive", "profile_active");
      setText("labelBehaviorPrompt", "behavior_prompt");
      setText("saveLlmProfileBtn", "save_llm_profile");
      setText("reloadLlmProfileBtn", "reload");
      setText("testDryRunBtn", "test_dry_run");
      setText("testLiveBtn", "test_live");
      setText("completeSetupBtn", "complete_setup");
      setText("completeConfirmText", "complete_confirm");
      setText("completeConfirmOkBtn", "complete_ok");
      setText("completeConfirmBackBtn", "complete_back");
      setText("chatSubtitle", "chat_subtitle");
      setText("voiceBtn", "voice");
      setText("sendBtn", "send");
      setText("reloadChatBtn", "reload");
      document.getElementById("chatInput").placeholder = uiLang() === "de" ? "Schreibe deine Aktion/Nachricht..." : "Write your action/message...";
      updateCompleteReadiness();
    }

    function updatePenaltyCapsVisibility() {
      const enabled = document.getElementById("penaltyCapsEnabled").value === "true";
      document.getElementById("maxPenaltyDayWrap").classList.toggle("hidden", !enabled);
      document.getElementById("maxPenaltyWeekWrap").classList.toggle("hidden", !enabled);
    }

    function applySetupTranslations() {
      const t = {
        execute: tr("execute"),
        suggest: tr("suggest"),
        enabled: tr("enabled"),
        disabled: tr("disabled"),
        day: tr("day"),
        week: tr("week"),
        month: tr("month"),
        duration_hint: tr("duration_hint"),
      };

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
      applyStaticUiTranslations();
      updatePenaltyCapsVisibility();
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
      document.getElementById("penaltyCapsEnabled").addEventListener("change", updatePenaltyCapsVisibility);
    }

    function setLlmDefaults() {
      if (!document.getElementById("llmBehaviorPrompt").value) {
        document.getElementById("llmBehaviorPrompt").value = defaultBehaviorPrompt;
      }
    }

    async function loadLlmProfile() {
      if (!userId || !authToken) return;
      const url = `/api/v1/llm/profile?user_id=${encodeURIComponent(userId)}&auth_token=${encodeURIComponent(authToken)}`;
      const res = await fetch(url);
      const data = await safeJson(res);
      if (!res.ok) return setOutput(data);
      if (!data.configured) {
        document.getElementById("llmInfo").textContent = tr("no_llm_profile");
        currentLlmProfile = null;
        refreshDashboard();
        return;
      }
      const p = data.profile;
      currentLlmProfile = p;
      document.getElementById("llmProviderName").value = p.provider_name || "custom";
      document.getElementById("llmApiUrl").value = p.api_url || "";
      document.getElementById("llmChatModel").value = p.chat_model || "";
      document.getElementById("llmVisionModel").value = p.vision_model || "";
      document.getElementById("llmIsActive").value = p.is_active ? "true" : "false";
      document.getElementById("llmBehaviorPrompt").value = p.behavior_prompt || defaultBehaviorPrompt;
      document.getElementById("llmInfo").textContent = tr("llm_loaded").replace("{has}", p.has_api_key ? tr("yes") : tr("no"));
      dashboardLastEvent = "llm_loaded";
      dashboardLastDetail = `${p.provider_name || "-"} / ${p.chat_model || "-"}`;
      refreshDashboard();
    }

    async function saveLlmProfile() {
      if (!userId || !authToken) return setOutput({error: "Login first."});
      const payload = {
        user_id: userId,
        auth_token: authToken,
        provider_name: document.getElementById("llmProviderName").value,
        api_url: document.getElementById("llmApiUrl").value,
        api_key: document.getElementById("llmApiKey").value || null,
        chat_model: document.getElementById("llmChatModel").value,
        vision_model: document.getElementById("llmVisionModel").value || null,
        behavior_prompt: document.getElementById("llmBehaviorPrompt").value,
        is_active: document.getElementById("llmIsActive").value === "true",
      };
      const res = await fetch("/api/v1/llm/profile", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      const data = await safeJson(res);
      setOutput(data);
      if (res.ok) {
        document.getElementById("llmApiKey").value = "";
        document.getElementById("llmInfo").textContent = "LLM profile saved.";
        currentLlmProfile = data.profile || currentLlmProfile;
        if (activeSession) renderDashboardSummary(activeSession);
        dashboardLastEvent = "llm_saved";
        dashboardLastDetail = `${currentLlmProfile?.provider_name || "-"} / ${currentLlmProfile?.chat_model || "-"}`;
        refreshDashboard();
        openPanel("complete");
      }
    }

    async function testLlmProfile(dryRun) {
      if (!userId || !authToken) return setOutput({error: "Login first."});
      const payload = { user_id: userId, auth_token: authToken, dry_run: dryRun };
      const res = await fetch("/api/v1/llm/test", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      const data = await safeJson(res);
      setOutput(data);
      if (res.ok) {
        document.getElementById("llmInfo").textContent = dryRun ? tr("dry_run_ok") : tr("live_test_ok");
      }
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
      dashboardVisible = false;
      document.getElementById("dashboard").classList.add("hidden");
      document.getElementById("appFlow").classList.remove("hidden");
      openPanel("start");
      refreshDashboard();
    }

    function renderDashboardSummary(session) {
      const currentSession = session || activeSession || null;
      const noSessionText = uiLang() === "de" ? "keine aktive Session" : "no active session";
      const policy = (currentSession && currentSession.policy) || {};
      const contract = policy.contract || {};
      const limits = policy.limits || {};
      const integrations = (policy.integrations || []).join(", ") || "-";
      const llm = currentLlmProfile || {};
      const setupContractText = setupContract
        ? `${setupContract.start_date || "-"} -> ${setupContract.end_date || tr("ai_defined")} (max ${setupContract.max_end_date || "-"})`
        : "-";
      const activeSessionId = currentSession ? currentSession.session_id : "-";
      const activeStatus = currentSession ? currentSession.status : noSessionText;
      const activeLanguage = currentSession ? currentSession.language : "-";
      const setupIdText = setupSessionId || "-";
      const setupStatusText = setupStatus || "draft";
      const dashboardInfo = uiLang() === "de"
        ? `Setup=${setupStatusText} | Active=${activeStatus}`
        : `Setup=${setupStatusText} | Active=${activeStatus}`;
      document.getElementById("dashboardInfo").textContent = dashboardInfo;
      document.getElementById("dashboardContract").innerHTML = [
        `<tr><th>User ID</th><td>${userId || "-"}</td></tr>`,
        `<tr><th>Setup Session ID</th><td>${setupIdText}</td></tr>`,
        `<tr><th>Setup Status</th><td>${setupStatusText}</td></tr>`,
        `<tr><th>Answered Questions</th><td>${answeredQuestions}</td></tr>`,
        `<tr><th>Setup Contract</th><td>${setupContractText}</td></tr>`,
        `<tr><th>Active Session ID</th><td>${activeSessionId}</td></tr>`,
        `<tr><th>Active Status</th><td>${activeStatus}</td></tr>`,
        `<tr><th>Active Language</th><td>${activeLanguage}</td></tr>`,
        `<tr><th>${tr("contract")}</th><td>${contract.start_date || "-"} -> ${contract.end_date || tr("ai_defined")} (max ${contract.max_end_date || "-"})</td></tr>`,
        `<tr><th>${tr("autonomy_mode_row")}</th><td>${policy.autonomy_mode || "-"}</td></tr>`,
        `<tr><th>${tr("ai_controls_end_date")}</th><td>${contract.ai_controls_end_date ? tr("enabled") : tr("disabled")}</td></tr>`,
        `<tr><th>${tr("integrations")}</th><td>${integrations}</td></tr>`,
        `<tr><th>${tr("hard_stop_row")}</th><td>${policy.hard_stop_enabled ? tr("enabled") : tr("disabled")}</td></tr>`,
        `<tr><th>${tr("penalty_caps_row")}</th><td>${tr("day")}=${limits.max_penalty_per_day_minutes ?? "-"} min, ${tr("week")}=${limits.max_penalty_per_week_minutes ?? "-"} min</td></tr>`,
        `<tr><th>${tr("openings")}</th><td>${limits.max_openings_in_period ?? limits.max_openings_per_day ?? "-"} / ${limits.opening_limit_period || tr("day")}, window=${limits.opening_window_minutes ?? "-"} min</td></tr>`,
        `<tr><th>${tr("llm_provider")}</th><td>${llm.provider_name || "-"}</td></tr>`,
        `<tr><th>${tr("llm_url")}</th><td>${llm.api_url || "-"}</td></tr>`,
        `<tr><th>${tr("llm_chat_model_row")}</th><td>${llm.chat_model || "-"}</td></tr>`,
        `<tr><th>${tr("llm_vision_model_row")}</th><td>${llm.vision_model || "-"}</td></tr>`,
        `<tr><th>${tr("llm_active")}</th><td>${llm.is_active === false ? tr("disabled") : tr("enabled")}</td></tr>`,
        `<tr><th>Last Event</th><td>${dashboardLastEvent}${dashboardLastDetail ? ` (${dashboardLastDetail})` : ""}</td></tr>`,
      ].join("");
    }

    function refreshDashboard() {
      renderDashboardSummary(activeSession);
    }

    function showHomeView() {
      dashboardVisible = false;
      document.getElementById("dashboard").classList.add("hidden");
      document.getElementById("appFlow").classList.remove("hidden");
      if (activeSession) loadChatTurns();
    }

    function showDashboard(session) {
      activeSession = session;
      renderDashboardSummary(session);
      const analysis = session?.psychogram?.analysis;
      if (analysis) {
        document.getElementById("brief").textContent = analysis;
      }
      document.getElementById("dashboardToggleBtn").classList.remove("hidden");
      document.getElementById("homeBtn").classList.remove("hidden");
      document.getElementById("logoutTopBtn").classList.remove("hidden");
      updateChatLock();
      showHomeView();
    }

    function toggleDashboard() {
      dashboardVisible = !dashboardVisible;
      if (dashboardVisible) {
        renderDashboardSummary(activeSession);
      }
      document.getElementById("dashboard").classList.toggle("hidden", !dashboardVisible);
      document.getElementById("appFlow").classList.toggle("hidden", dashboardVisible);
    }

    function renderChatTurns(turns) {
      const out = document.getElementById("chatOutput");
      if (!turns || !turns.length) {
        out.value = tr("no_turns");
        return;
      }
      out.value = turns
        .map((t) => `#${t.turn_no}\\nWearer: ${t.player_action}\\nKeyholder: ${t.ai_narration}\\n`)
        .join("\\n");
      out.scrollTop = out.scrollHeight;
    }

    function appendPreviewChat(actionText, narrationText) {
      const out = document.getElementById("chatOutput");
      const previous = out.value ? `${out.value}\n\n` : "";
      out.value = `${previous}#preview\nWearer: ${actionText}\nKeyholder: ${narrationText}\n`;
      out.scrollTop = out.scrollHeight;
    }

    function renderPendingActions(actions) {
      const wrap = document.getElementById("pendingActions");
      if (!actions || !actions.length) {
        wrap.innerHTML = "";
        return;
      }
      const buttons = actions.map((a) => {
        const payload = JSON.stringify(a.payload || {});
        return `<button class="ghost" onclick='executePendingAction("${a.action_type}", ${JSON.stringify(payload)})'>Execute ${a.action_type}</button>`;
      });
      wrap.innerHTML = `<div class="small">${tr("pending_actions")}: ${buttons.join(" ")}</div>`;
    }

    async function loadChatTurns() {
      if (!activeSession || !activeSession.session_id) return;
      const res = await fetch(`/api/v1/sessions/${activeSession.session_id}/turns`);
      const data = await safeJson(res);
      if (!res.ok) return setOutput(data);
      renderChatTurns(data.turns || []);
    }

    async function sendChatTurn() {
      const input = document.getElementById("chatInput");
      const action = input.value.trim();
      const files = document.getElementById("chatFiles").files;
      if (!action && (!files || !files.length)) return;
      const attachments = [];
      if (files && files.length) {
        for (const f of files) {
          attachments.push({name: f.name, size: f.size, type: f.type || "application/octet-stream"});
        }
      }
      const messageValue = action || "[attachment upload]";
      if (activeSession && activeSession.session_id) {
        const payload = {
          session_id: activeSession.session_id,
          message: messageValue,
          language: activeSession.language || "de",
          attachments,
        };
        const res = await fetch("/api/v1/chat/turn", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload),
        });
        const data = await safeJson(res);
        setOutput(data);
      if (res.ok) {
        input.value = "";
        document.getElementById("chatFiles").value = "";
        latestPendingActions = data.pending_actions || [];
        renderPendingActions(latestPendingActions);
        dashboardLastEvent = "chat_turn_active";
        dashboardLastDetail = `session=${activeSession.session_id}`;
        refreshDashboard();
        await loadChatTurns();
      }
        return;
      }

      if (!setupSessionId) return setOutput({error: "Start setup first."});
      const previewPayload = {
        user_id: userId,
        auth_token: authToken,
        message: messageValue,
        language: document.getElementById("language").value || "de",
        attachments,
      };
      const res = await fetch(`/api/v1/setup/sessions/${setupSessionId}/chat-preview`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(previewPayload),
      });
      const data = await safeJson(res);
      setOutput(data);
      if (res.ok) {
        input.value = "";
        document.getElementById("chatFiles").value = "";
        latestPendingActions = data.pending_actions || [];
        renderPendingActions(latestPendingActions);
        dashboardLastEvent = "chat_turn_preview";
        dashboardLastDetail = `setup=${setupSessionId || "-"}`;
        refreshDashboard();
        appendPreviewChat(messageValue, data.narration || "");
      }
    }

    async function executePendingAction(actionType, payloadText) {
      if (!activeSession || !activeSession.session_id) return;
      let payload = {};
      try {
        payload = JSON.parse(payloadText || "{}");
        if (typeof payload === "string") payload = JSON.parse(payload);
      } catch {}
      const res = await fetch("/api/v1/chat/actions/execute", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          session_id: activeSession.session_id,
          action_type: actionType,
          payload,
        }),
      });
      const data = await safeJson(res);
      setOutput(data);
      if (res.ok) {
        latestPendingActions = [];
        renderPendingActions([]);
      }
    }

    function startVoiceInput() {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) return setOutput({error: "Speech recognition not supported in this browser."});
      const recog = new SpeechRecognition();
      recog.lang = document.getElementById("language").value === "de" ? "de-DE" : "en-US";
      recog.interimResults = false;
      recog.maxAlternatives = 1;
      recog.onresult = (event) => {
        const text = event.results?.[0]?.[0]?.transcript || "";
        document.getElementById("chatInput").value = text;
      };
      recog.onerror = () => setOutput({error: "Voice input failed."});
      recog.start();
    }

    function unlockFlow(data) {
      if (data.user_id && data.auth_token) {
        userId = data.user_id;
        authToken = data.auth_token;
        setupSessionId = data.setup_session_id || setupSessionId;
        setupStatus = data.setup_status || setupStatus;
        answeredQuestions = 0;
        setupContract = null;
        dashboardLastEvent = "auth_ok";
        dashboardLastDetail = `setup=${setupStatus || "-"}`;
        saveAuth();
        document.getElementById("userInfo").textContent = `username: ${data.username || data.display_name || "user"}`;
        document.getElementById("authCard").classList.add("hidden");
        document.getElementById("homeBtn").classList.remove("hidden");
        document.getElementById("dashboardToggleBtn").classList.remove("hidden");
        document.getElementById("logoutTopBtn").classList.remove("hidden");
        setLlmDefaults();
        loadLlmProfile();
        showSetupFlow();
        updatePsychogramAvailability();
        refreshDashboard();
      }
    }

    async function checkActiveSession() {
      if (!userId || !authToken) return;
      const url = `/api/v1/sessions/active?user_id=${encodeURIComponent(userId)}&auth_token=${encodeURIComponent(authToken)}`;
      const res = await fetch(url);
      const data = await safeJson(res);
      if (res.ok && data.has_active_session && data.chastity_session) {
        activeSession = data.chastity_session;
        setupStatus = "configured";
        setLocked("start", true);
        setLocked("psychogram", true);
        setLocked("ai_config", true);
        setLocked("complete", true);
        updateChatLock();
        updateCompleteReadiness();
        dashboardLastEvent = "active_session_loaded";
        dashboardLastDetail = `session_id=${activeSession.session_id}`;
        showDashboard(data.chastity_session);
      } else if (res.ok) {
        activeSession = null;
        if (!setupStatus) setupStatus = "draft";
        setLocked("start", false);
        resetAccordionLocks();
        updateChatLock();
        updateCompleteReadiness();
        dashboardLastEvent = "no_active_session";
        dashboardLastDetail = `setup=${setupStatus}`;
        showSetupFlow();
      }
      refreshDashboard();
    }

    async function registerUser() {
      if (userId) return setOutput({error: "Logout first if you want to register a different user."});
      if (document.getElementById("password").value !== document.getElementById("passwordRepeat").value) {
        return setOutput({error: "Password repeat does not match."});
      }
      const payload = {
        username: document.getElementById("username").value,
        email: document.getElementById("email").value,
        password: document.getElementById("password").value,
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
        password: document.getElementById("password").value,
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
      setupStatus = null;
      answeredQuestions = 0;
      setupContract = null;
      questions = [];
      activeSession = null;
      clearAuth();
      document.getElementById("userInfo").textContent = "";
      document.getElementById("setupSessionInfo").textContent = "";
      document.getElementById("dashboardInfo").textContent = "";
      document.getElementById("dashboardContract").innerHTML = "";
      document.getElementById("questionGrid").innerHTML = "";
      document.getElementById("chatOutput").value = "";
      document.getElementById("chatInput").value = "";
      document.getElementById("pendingActions").innerHTML = "";
      document.getElementById("llmInfo").textContent = "";
      document.getElementById("llmApiKey").value = "";
      currentLlmProfile = null;
      dashboardVisible = false;
      document.getElementById("dashboard").classList.add("hidden");
      document.getElementById("dashboardToggleBtn").classList.add("hidden");
      document.getElementById("homeBtn").classList.add("hidden");
      document.getElementById("appFlow").classList.add("hidden");
      document.getElementById("authCard").classList.remove("hidden");
      document.getElementById("logoutTopBtn").classList.add("hidden");
      setAuthMode("login");
      lockContractInputs(false);
      setContractDefaults();
      resetAccordionLocks();
      dashboardLastEvent = "logged_out";
      dashboardLastDetail = "";
      refreshDashboard();
      setOutput({result: "logged_out"});
    }

    async function killActiveSession() {
      if (!userId || !authToken) return setOutput({error: "Login first."});
      const setupQuery = setupSessionId ? `&setup_session_id=${encodeURIComponent(setupSessionId)}` : "";
      const url = `/api/v1/sessions/active?user_id=${encodeURIComponent(userId)}&auth_token=${encodeURIComponent(authToken)}${setupQuery}`;
      const res = await fetch(url, { method: "DELETE" });
      const data = await safeJson(res);
      setOutput(data);
      if (res.ok && data.deleted) {
        activeSession = null;
        setupStatus = data.setup_status || "draft";
        setupSessionId = data.setup_session_id || null;
        answeredQuestions = 0;
        setupContract = null;
        document.getElementById("dashboard").classList.add("hidden");
        document.getElementById("dashboardInfo").textContent = "";
        document.getElementById("dashboardContract").innerHTML = "";
        document.getElementById("pendingActions").innerHTML = "";
        document.getElementById("setupSessionInfo").textContent = "";
        document.getElementById("chatOutput").value = "";
        document.getElementById("chatInput").value = "";
        questions = [];
        document.getElementById("questionGrid").innerHTML = "";
        lockContractInputs(false);
        resetAccordionLocks();
        updateChatLock();
        dashboardLastEvent = "session_killed";
        dashboardLastDetail = `setup=${setupStatus}, setup_id=${setupSessionId || "-"}`;
        showSetupFlow();
        refreshDashboard();
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
        setupStatus = data.status || "setup_in_progress";
        answeredQuestions = 0;
        setupContract = data.contract || null;
        questions = data.questions || [];
        renderQuestions();
        lockContractInputs(true);
        unlockSetupFollowups();
        const maxEnd = data.contract.max_end_date || "AI-decided";
        document.getElementById("setupSessionInfo").textContent =
          `setup_session_id: ${setupSessionId} | contract: ${data.contract.start_date} -> AI-defined (max ${maxEnd})`;
        dashboardLastEvent = "setup_started";
        dashboardLastDetail = `setup_id=${setupSessionId}`;
        openPanel("psychogram");
      }
      updatePsychogramAvailability();
      refreshDashboard();
      setOutput(data);
    }

    async function submitAnswers() {
      if (!setupSessionId || setupStatus !== "setup_in_progress") return setOutput({error: "Start setup first."});
      const answers = questions.map((q) => ({
        question_id: q.question_id,
        value: (q.type === "scale_100" || q.type === "scale_10" || q.type === "scale_5")
          ? Number(document.getElementById(`q_${q.question_id}`).value)
          : document.getElementById(`q_${q.question_id}`).value,
      }));
      const saveInfo = document.getElementById("psychogramSaveInfo");
      saveInfo.classList.add("hidden");
      saveInfo.classList.remove("status-ok", "status-error");
      saveInfo.textContent = "";
      const res = await fetch(`/api/v1/setup/sessions/${setupSessionId}/answers`, {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({answers}),
      });
      const data = await safeJson(res);
      setOutput(data);
      if (res.ok) {
        answeredQuestions = Number(data?.answered_questions || answeredQuestions || 0);
        dashboardLastEvent = "psychogram_saved";
        dashboardLastDetail = `answered=${answeredQuestions}`;
        saveInfo.textContent = tr("psychogram_saved");
        saveInfo.classList.add("status-ok");
        saveInfo.classList.remove("hidden");
        updateCompleteReadiness();
        refreshDashboard();
        openPanel("ai_config");
      } else {
        saveInfo.textContent = `${tr("psychogram_save_failed")} ${data?.detail || ""}`.trim();
        saveInfo.classList.add("status-error");
        saveInfo.classList.remove("hidden");
        dashboardLastEvent = "psychogram_save_error";
        dashboardLastDetail = `${data?.detail || "unknown"}`;
        refreshDashboard();
      }
    }

    async function completeSetup() {
      if (!setupSessionId) return setOutput({error: "Start setup first."});
      const res = await fetch(`/api/v1/setup/sessions/${setupSessionId}/complete`, { method: "POST" });
      const data = await safeJson(res);
      setOutput(data);
      if (res.ok) {
        setupStatus = "configured";
        answeredQuestions = Number(data?.answered_questions || answeredQuestions || 0);
        setupContract = data?.chastity_session?.policy?.contract || setupContract;
        setLocked("start", true);
        setLocked("psychogram", true);
        setLocked("ai_config", true);
        setLocked("complete", true);
        setLocked("brief", false);
        setLocked("response", false);
        updatePsychogramAvailability();
        updateCompleteReadiness();
        const briefText = data?.chastity_session?.psychogram_brief;
        if (briefText) {
          document.getElementById("brief").textContent = briefText;
          openPanel("brief");
        }
        dashboardLastEvent = "setup_completed";
        dashboardLastDetail = `status=configured`;
        await checkActiveSession();
        if (activeSession) {
          updateChatLock();
          openPanel("brief");
        } else {
          setLocked("chat", true);
        }
        refreshDashboard();
      }
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
    setLlmDefaults();
    initContractSync();
    applySetupTranslations();
    resetAccordionLocks();
    bootstrapAuth();
  </script>
</body>
</html>
"""
    return html.replace("__KILL_BUTTON_CLASS__", kill_button_class)


@web_router.get("/chat", response_class=HTMLResponse)
def chat_shell() -> str:
    return """
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Chastease AI Chat</title>
  <style>
    :root {
      --bg: #080f1e;
      --ink: #e9efff;
      --muted: #9bb0d9;
      --line: #213255;
      --panel: #101b33;
      --panel-soft: #0f1830;
      --brand: #2d8cff;
      --brand-soft: #1f335e;
      --ok: #35c68b;
      --danger: #d65a5a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", Arial, sans-serif;
      color: var(--ink);
      background:
        radial-gradient(900px 360px at 85% -10%, #1c2f58 0%, transparent 60%),
        radial-gradient(800px 360px at -20% 120%, #143a44 0%, transparent 58%),
        var(--bg);
    }
    .wrap { max-width: 1180px; margin: 0 auto; padding: 20px; }
    .topbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .btn {
      border-radius: 10px;
      border: 1px solid #2b3f66;
      background: #111e3b;
      color: var(--ink);
      padding: 9px 12px;
      text-decoration: none;
      cursor: pointer;
      font-weight: 700;
    }
    .btn.primary { background: var(--brand); border-color: transparent; }
    .btn.ghost { background: transparent; }
    .grid { display: grid; grid-template-columns: 300px 1fr; gap: 12px; }
    .card { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 14px; }
    .small { color: var(--muted); font-size: 12px; }
    h1 { margin: 0; font-size: clamp(2rem, 4vw, 2.8rem); }
    h2 { margin: 0 0 10px; font-size: 18px; }
    .status { margin-top: 8px; min-height: 18px; }
    .ok { color: var(--ok); }
    .err { color: var(--danger); }
    .chat-shell { display: grid; grid-template-rows: 1fr auto; min-height: 72vh; }
    .messages { overflow: auto; padding: 6px; display: grid; gap: 8px; }
    .msg { border: 1px solid #2a3f67; border-radius: 12px; padding: 10px; background: var(--panel-soft); }
    .msg.user { background: #152748; }
    .msg .role { font-size: 12px; color: var(--muted); margin-bottom: 4px; }
    .composer { border-top: 1px solid var(--line); margin-top: 8px; padding-top: 12px; }
    textarea {
      width: 100%;
      min-height: 88px;
      resize: vertical;
      border-radius: 10px;
      border: 1px solid #2d436d;
      background: #0f1830;
      color: var(--ink);
      padding: 10px;
      font-family: inherit;
    }
    input, select {
      width: 100%;
      border-radius: 10px;
      border: 1px solid #2d436d;
      background: #0f1830;
      color: var(--ink);
      padding: 9px 10px;
    }
    .row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
    .file-list { display: grid; gap: 4px; margin-top: 8px; }
    .file-pill { display: inline-block; border: 1px solid #314c7b; padding: 4px 8px; border-radius: 999px; font-size: 12px; color: #c6d6ff; }
    .downloads { margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; }
    .downloads button { border-radius: 8px; border: 1px solid #355183; background: #132445; color: #d8e6ff; padding: 6px 10px; cursor: pointer; }

    @media (max-width: 980px) {
      .grid { grid-template-columns: 1fr; }
      .chat-shell { min-height: 62vh; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div>
        <h1>AI Chat</h1>
        <div class="small">Text, Bilder, Screenshots, Sprache und Datei-Antworten</div>
      </div>
      <div class="actions">
        <a class="btn ghost" href="/">Home</a>
        <a class="btn ghost" href="/app">Dashboard</a>
      </div>
    </div>

    <div class="grid">
      <section class="card">
        <h2>Session</h2>
        <div class="small">Der Chat nutzt deine aktive Session.</div>
        <div style="margin-top:8px;">
          <label class="small">User ID</label>
          <input id="userId" placeholder="auto via auth token" />
        </div>
        <div style="margin-top:8px;">
          <label class="small">Auth Token</label>
          <input id="authToken" type="password" placeholder="auto via localStorage" />
        </div>
        <div class="row">
          <button class="btn" onclick="loadAuthFromStorage()">Load Auth</button>
          <button class="btn" onclick="resolveActiveSession()">Load Session</button>
        </div>
        <div style="margin-top:8px;">
          <label class="small">Session ID</label>
          <input id="sessionId" placeholder="active session id" />
        </div>
        <div class="status small" id="status"></div>
      </section>

      <section class="card chat-shell">
        <div id="messages" class="messages"></div>
        <div class="composer">
          <textarea id="messageInput" placeholder="Schreibe hier deine Nachricht an den Keyholder..."></textarea>
          <div class="row">
            <input id="fileInput" type="file" multiple accept="image/*,.pdf,.txt,.md,.json,.csv,.doc,.docx" />
            <button class="btn" id="voiceBtn" onclick="toggleVoice()">Voice</button>
            <button class="btn primary" onclick="sendMessage()">Senden</button>
            <button class="btn ghost" onclick="downloadLastAsText()">Antwort als TXT</button>
            <button class="btn ghost" onclick="downloadLastAsJson()">Antwort als JSON</button>
          </div>
          <div id="fileList" class="file-list"></div>
          <div id="downloads" class="downloads"></div>
        </div>
      </section>
    </div>
  </div>

  <script>
    let recognition = null;
    let voiceOn = false;
    let lastResponse = null;

    function setStatus(text, kind = "ok") {
      const node = document.getElementById("status");
      node.textContent = text;
      node.className = `status small ${kind === "err" ? "err" : "ok"}`;
    }

    function authStorageKey() {
      return "chastease_auth_v1";
    }

    function loadAuthFromStorage() {
      try {
        const raw = localStorage.getItem(authStorageKey());
        if (!raw) return setStatus("Kein gespeicherter Login gefunden.", "err");
        const parsed = JSON.parse(raw);
        document.getElementById("userId").value = parsed.user_id || "";
        document.getElementById("authToken").value = parsed.auth_token || "";
        setStatus("Auth geladen.");
      } catch {
        setStatus("Auth konnte nicht geladen werden.", "err");
      }
    }

    async function safeJson(res) {
      try { return await res.json(); }
      catch {
        const text = await res.text();
        return { error: "non-json", body: text, status: res.status };
      }
    }

    async function resolveActiveSession() {
      const userId = document.getElementById("userId").value.trim();
      const authToken = document.getElementById("authToken").value.trim();
      if (!userId || !authToken) return setStatus("User ID und Auth Token erforderlich.", "err");
      const url = `/api/v1/sessions/active?user_id=${encodeURIComponent(userId)}&auth_token=${encodeURIComponent(authToken)}`;
      const res = await fetch(url);
      const data = await safeJson(res);
      if (!res.ok) return setStatus(data?.detail || "Session konnte nicht geladen werden.", "err");
      if (!data.has_active_session) return setStatus("Keine aktive Session gefunden.", "err");
      document.getElementById("sessionId").value = data.chastity_session.session_id;
      setStatus("Aktive Session geladen.");
    }

    function readSelectedFiles() {
      const files = Array.from(document.getElementById("fileInput").files || []);
      const list = document.getElementById("fileList");
      list.innerHTML = files.map((f) => `<span class="file-pill">${f.name} (${Math.round(f.size/1024)} KB)</span>`).join("");
      return files.map((f) => ({ name: f.name, size: f.size, type: f.type || "application/octet-stream" }));
    }

    function addMessage(role, text) {
      const wrap = document.createElement("article");
      wrap.className = `msg ${role === "wearer" ? "user" : "assistant"}`;
      wrap.innerHTML = `<div class="role">${role === "wearer" ? "Wearer" : "Keyholder"}</div><div>${(text || "").replace(/\\n/g, "<br/>")}</div>`;
      const box = document.getElementById("messages");
      box.appendChild(wrap);
      box.scrollTop = box.scrollHeight;
    }

    function downloadBlob(name, mimeType, content) {
      const blob = new Blob([content], { type: mimeType || "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name || "response.txt";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1200);
    }

    function renderGeneratedFiles(files) {
      const box = document.getElementById("downloads");
      box.innerHTML = "";
      if (!files || !files.length) return;
      files.forEach((f, idx) => {
        const btn = document.createElement("button");
        btn.textContent = `Download: ${f.name || `file-${idx + 1}.txt`}`;
        btn.onclick = () => downloadBlob(f.name, f.mime_type, f.content || "");
        box.appendChild(btn);
      });
    }

    async function sendMessage() {
      const sessionId = document.getElementById("sessionId").value.trim();
      const message = document.getElementById("messageInput").value.trim();
      if (!sessionId) return setStatus("Session ID fehlt.", "err");
      if (!message) return setStatus("Nachricht fehlt.", "err");

      const attachments = readSelectedFiles();
      addMessage("wearer", message);
      setStatus("Anfrage laeuft, bitte warten...");
      const res = await fetch("/api/v1/chat/turn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message, language: "de", attachments }),
      });
      const data = await safeJson(res);
      if (!res.ok) return setStatus(data?.detail || "Chat-Request fehlgeschlagen.", "err");
      lastResponse = data;
      addMessage("keyholder", data.narration || "");
      renderGeneratedFiles(data.generated_files || []);
      document.getElementById("messageInput").value = "";
      document.getElementById("fileInput").value = "";
      document.getElementById("fileList").innerHTML = "";
      setStatus("Antwort erhalten.");
    }

    function downloadLastAsText() {
      if (!lastResponse) return setStatus("Noch keine Antwort zum Exportieren.", "err");
      downloadBlob("ai-response.txt", "text/plain", lastResponse.narration || "");
    }

    function downloadLastAsJson() {
      if (!lastResponse) return setStatus("Noch keine Antwort zum Exportieren.", "err");
      downloadBlob("ai-response.json", "application/json", JSON.stringify(lastResponse, null, 2));
    }

    function toggleVoice() {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) return setStatus("Voice wird in diesem Browser nicht unterstuetzt.", "err");
      if (!recognition) {
        recognition = new SpeechRecognition();
        recognition.lang = "de-DE";
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.onresult = (event) => {
          let finalTranscript = "";
          for (let i = event.resultIndex; i < event.results.length; i += 1) {
            if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript;
          }
          if (finalTranscript) {
            const input = document.getElementById("messageInput");
            input.value = `${input.value} ${finalTranscript}`.trim();
          }
        };
        recognition.onend = () => {
          if (voiceOn) recognition.start();
        };
      }
      voiceOn = !voiceOn;
      document.getElementById("voiceBtn").textContent = voiceOn ? "Stop Voice" : "Voice";
      if (voiceOn) {
        recognition.start();
        setStatus("Voice-Aufnahme aktiv.");
      } else {
        recognition.stop();
        setStatus("Voice-Aufnahme gestoppt.");
      }
    }

    document.getElementById("fileInput").addEventListener("change", readSelectedFiles);
    loadAuthFromStorage();
  </script>
</body>
</html>
"""
