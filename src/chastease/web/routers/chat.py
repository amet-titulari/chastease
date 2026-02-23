from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["web-chat"])


@router.get("/chat", response_class=HTMLResponse)
def chat_shell() -> str:
    return """
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Chastease AI Chat (Text)</title>
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
    .icon-btn {
      width: 34px;
      height: 34px;
      border-radius: 999px;
      padding: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 16px;
      line-height: 1;
    }
    .grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
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
    .msg .meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 4px; }
    .msg .role { font-size: 12px; color: var(--muted); }
    .msg .ts { font-size: 12px; color: #86a2d4; font-variant-numeric: tabular-nums; }
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
    input {
      width: 100%;
      border-radius: 10px;
      border: 1px solid #2d436d;
      background: #0f1830;
      color: var(--ink);
      padding: 9px 10px;
    }
    .row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
    .note {
      margin-top: 8px;
      padding: 8px 10px;
      border-radius: 10px;
      border: 1px dashed #2e4774;
      color: #a8bde6;
      font-size: 12px;
    }
    .hidden { display: none !important; }

    @media (max-width: 980px) {
      .chat-shell { min-height: 62vh; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div>
        <h1>AI Chat</h1>
        <div class="small">Reiner Text-Chat (Prototyp)</div>
      </div>
      <div class="actions">
        <button class="btn ghost icon-btn" onclick="toggleInfoPanel()" title="Session-Info anzeigen/ausblenden" aria-label="Session-Info">
          (i)
        </button>
        <a class="btn ghost" href="/">Home</a>
        <a class="btn ghost" href="/app">Dashboard</a>
      </div>
    </div>

    <section id="sessionPanel" class="card hidden" style="margin-bottom:12px;">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
        <h2 style="margin:0;">Session</h2>
        <button class="btn ghost" onclick="toggleInfoPanel(true)">Schliessen</button>
      </div>
      <div class="small">Der Chat nutzt deine aktive Session.</div>
      <div style="margin-top:8px;">
        <label class="small">User ID</label>
        <input id="userId" name="chat_user_id" placeholder="auto via auth token" autocomplete="off" data-bwignore="true" data-1p-ignore="true" />
      </div>
      <div style="margin-top:8px;">
        <label class="small">Auth Token</label>
        <input id="authToken" name="chat_auth_token" type="password" placeholder="auto via localStorage" autocomplete="new-password" data-bwignore="true" data-1p-ignore="true" />
      </div>
      <div class="row">
        <button class="btn" onclick="loadAuthFromStorage()">Load Auth</button>
        <button class="btn" onclick="resolveActiveSession()">Load Session</button>
      </div>
      <div style="margin-top:8px;">
        <label class="small">Session ID</label>
        <input id="sessionId" name="chat_session_id" placeholder="active session id" autocomplete="off" data-bwignore="true" data-1p-ignore="true" />
      </div>
      <div class="note">Nur Text aktiviert. Upload, Voice und Datei-Export sind temporär deaktiviert.</div>
    </section>

    <div class="grid">
      <section class="card chat-shell">
        <div id="messages" class="messages"></div>
        <div class="composer">
          <div class="status small" id="status"></div>
          <textarea id="messageInput" name="chat_message" placeholder="Schreibe hier deine Nachricht an den Keyholder..." autocomplete="off" data-bwignore="true" data-1p-ignore="true"></textarea>
          <div class="row">
            <button class="btn primary" onclick="sendMessage()">Senden</button>
          </div>
        </div>
      </section>
    </div>
  </div>

  <script>
    let sending = false;
    let infoOpen = false;

    function toggleInfoPanel(forceClose = false) {
      if (forceClose) {
        infoOpen = false;
      } else {
        infoOpen = !infoOpen;
      }
      document.getElementById("sessionPanel").classList.toggle("hidden", !infoOpen);
    }

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
      await loadTurns();
      setStatus("Aktive Session geladen.");
    }

    function formatTimestamp(dateLike = null) {
      const d = dateLike ? new Date(dateLike) : new Date();
      if (Number.isNaN(d.getTime())) return "--.--.--";
      const hh = String(d.getHours()).padStart(2, "0");
      const mm = String(d.getMinutes()).padStart(2, "0");
      const ss = String(d.getSeconds()).padStart(2, "0");
      return `${hh}.${mm}.${ss}`;
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function addMessage(role, text, ts = null) {
      const wrap = document.createElement("article");
      wrap.className = `msg ${role === "wearer" ? "user" : "assistant"}`;
      wrap.innerHTML = `
        <div class="meta">
          <div class="role">${role === "wearer" ? "Wearer" : "Keyholder"}</div>
          <div class="ts">${formatTimestamp(ts)}</div>
        </div>
        <div>${escapeHtml(text || "").replace(/\\n/g, "<br/>")}</div>
      `;
      const box = document.getElementById("messages");
      box.appendChild(wrap);
      box.scrollTop = box.scrollHeight;
    }

    function renderTurns(turns) {
      const box = document.getElementById("messages");
      box.innerHTML = "";
      (turns || []).forEach((turn) => {
        const actionText = String(turn.player_action || "");
        const isSystem = actionText.startsWith("[SYSTEM]");
        if (!isSystem && actionText) {
          addMessage("wearer", actionText, turn.created_at);
        }
        addMessage("keyholder", turn.ai_narration || "", turn.created_at);
      });
    }

    async function loadTurns() {
      const sessionId = document.getElementById("sessionId").value.trim();
      if (!sessionId) return;
      const res = await fetch(`/api/v1/sessions/${encodeURIComponent(sessionId)}/turns`);
      const data = await safeJson(res);
      if (!res.ok) return setStatus(data?.detail || "Verlauf konnte nicht geladen werden.", "err");
      renderTurns(data.turns || []);
    }

    async function sendMessage() {
      if (sending) return;
      const sessionId = document.getElementById("sessionId").value.trim();
      const input = document.getElementById("messageInput");
      const message = input.value.trim();
      if (!sessionId) return setStatus("Session ID fehlt.", "err");
      if (!message) return setStatus("Nachricht fehlt.", "err");
      const startedAtWallclock = new Date();
      const startedAt = performance.now();
      addMessage("wearer", message);
      input.value = "";
      setStatus(`Anfrage gestellt (${formatTimestamp(startedAtWallclock)}). Bitte warten...`);
      sending = true;
      try {
        const res = await fetch("/api/v1/chat/turn", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, message, language: "de" }),
        });
        const data = await safeJson(res);
        if (!res.ok) return setStatus(data?.detail || "Chat-Request fehlgeschlagen.", "err");
        await loadTurns();
        const elapsedMs = Math.max(0, performance.now() - startedAt);
        setStatus(`Antwort erhalten. Antwortzeit: ${(elapsedMs / 1000).toFixed(2)}s.`);
      } finally {
        sending = false;
      }
    }

    async function runPostSetupAnalysisFlow() {
      const params = new URLSearchParams(window.location.search);
      if (params.get("mode") !== "analysis") return;

      addMessage("keyholder", "Der Vertrag wird generiert...");
      setStatus("Der Vertrag wird generiert...");

      let payload = null;
      try {
        const raw = sessionStorage.getItem("chastease_post_setup_bootstrap");
        if (raw) payload = JSON.parse(raw);
      } catch {}

      if (payload?.session_id) {
        document.getElementById("sessionId").value = payload.session_id;
      } else {
        await resolveActiveSession();
      }

      const userId = document.getElementById("userId").value.trim();
      const authToken = document.getElementById("authToken").value.trim();
      const setupSessionId = payload?.setup_session_id;
      if (!setupSessionId) {
        setStatus("Setup Session ID fehlt fuer Vertragsgenerierung.", "err");
        return;
      }
      const res = await fetch(`/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}/artifacts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, auth_token: authToken }),
      });
      const data = await safeJson(res);
      if (!res.ok) {
        setStatus(data?.detail || "Vertragsgenerierung fehlgeschlagen.", "err");
      } else {
        if (data?.session_id) document.getElementById("sessionId").value = data.session_id;
        await loadTurns();
        setStatus("Vertrag und Analyse sind erstellt.");
      }
      sessionStorage.removeItem("chastease_post_setup_bootstrap");
    }

    document.getElementById("messageInput").addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    });

    loadAuthFromStorage();
    resolveActiveSession();
    runPostSetupAnalysisFlow();
  </script>
</body>
</html>
"""


