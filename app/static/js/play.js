/* play.js – Play Mode (v0.1.3) */
"use strict";

// -- State from server-rendered dataset --
const _shell = document.querySelector(".play-shell");
const SESSION_ID = Number(_shell?.dataset.sessionId || 0);
const WS_TOKEN = _shell?.dataset.wsToken || "";
const LOCK_END = _shell?.dataset.lockEnd || "";

let plSocket = null;

// -- DOM refs --
const countdownEl = document.getElementById("play-countdown");
const statusPillEl = document.getElementById("play-status-pill");
const statusTextEl = document.getElementById("play-status-text");
const chatTimeline = document.getElementById("play-chat-timeline");
const chatInput = document.getElementById("play-chat-input");
const taskBoard = document.getElementById("play-task-board");
const debugOut = document.getElementById("play-output");
const wsBtn = document.getElementById("play-connect-ws");

// -- Countdown timer --
function plFormatRemaining(isoStr) {
  if (!isoStr) return "—";
  const diff = new Date(isoStr).getTime() - Date.now();
  if (diff <= 0) return "Frei";
  const d = Math.floor(diff / 86400000);
  const h = Math.floor((diff % 86400000) / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  const s = Math.floor((diff % 60000) / 1000);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  return `${m}m ${s}s`;
}

if (LOCK_END && countdownEl) {
  const lockEndDisplay = document.getElementById("play-lock-end-display");
  if (lockEndDisplay) {
    try {
      lockEndDisplay.textContent = new Date(LOCK_END).toLocaleString("de-DE");
    } catch (_) {}
  }
  setInterval(() => {
    countdownEl.textContent = plFormatRemaining(LOCK_END);
  }, 1000);
  countdownEl.textContent = plFormatRemaining(LOCK_END);
}

// -- Debug output --
function plWrite(title, data) {
  if (!debugOut) return;
  debugOut.classList.add("is-visible");
  debugOut.textContent = `${title}\n${JSON.stringify(data, null, 2)}`;
  clearTimeout(plWrite._timer);
  plWrite._timer = setTimeout(() => debugOut.classList.remove("is-visible"), 6000);
}

// -- HTTP helpers --
async function plGet(url) {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(data));
  return data;
}

async function plPost(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(data));
  return data;
}

// -- Render chat --
function plRenderChat(items) {
  if (!chatTimeline) return;
  if (!Array.isArray(items) || !items.length) {
    chatTimeline.innerHTML = "<p>Noch keine Nachrichten.</p>";
    return;
  }
  chatTimeline.innerHTML = items
    .slice(-80)
    .map((item) => {
      const role = item.role || "system";
      const cssRole = role === "assistant" ? "from-ai" : "from-user";
      const content = String(item.content || "").replace(/</g, "&lt;");
      const ts = item.created_at ? new Date(item.created_at).toLocaleTimeString("de-DE") : "";
      return `
        <div class="chat-bubble ${cssRole}">
          <div class="bubble-body">${content}</div>
          <div class="bubble-meta">${role}${ts ? " &middot; " + ts : ""}</div>
        </div>`;
    })
    .join("");
  chatTimeline.scrollTop = chatTimeline.scrollHeight;
}

// -- Render tasks --
function plRenderTasks(items) {
  if (!taskBoard) return;
  if (!Array.isArray(items) || !items.length) {
    taskBoard.innerHTML = "<p>Noch keine Tasks.</p>";
    return;
  }
  taskBoard.innerHTML = items
    .map((item) => {
      const isDone = item.status === "completed";
      const isFailed = item.status === "failed";
      const disabled = item.status !== "pending" ? "disabled" : "";
      const title = String(item.title || "").replace(/</g, "&lt;");
      const extraClass = isDone ? "is-done" : isFailed ? "is-failed" : "";
      return `
        <div class="task-card ${extraClass}" data-task-id="${item.id}">
          <div class="task-card-title">${title}</div>
          <div class="task-card-actions">
            <button class="btn-done" data-action="complete" ${disabled}>&#10003; Done</button>
            <button class="btn-fail" data-action="fail" ${disabled}>&#10007; Fail</button>
          </div>
        </div>`;
    })
    .join("");

  taskBoard.querySelectorAll("button[data-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const card = btn.closest(".task-card");
      const taskId = card ? Number(card.dataset.taskId) : 0;
      if (!taskId || !SESSION_ID) return;
      const status = btn.dataset.action === "complete" ? "completed" : "failed";
      try {
        await plPost(`/api/sessions/${SESSION_ID}/tasks/${taskId}/status`, { status });
        await plListTasks();
      } catch (err) {
        plWrite("Fehler Task-Update", { error: String(err) });
      }
    });
  });
}

// -- Load functions --
async function plLoadChat() {
  if (!SESSION_ID) return;
  try {
    const data = await plGet(`/api/sessions/${SESSION_ID}/messages`);
    plRenderChat(data.items || []);
  } catch (err) {
    plWrite("Fehler Verlauf", { error: String(err) });
  }
}

async function plListTasks() {
  if (!SESSION_ID) return;
  try {
    const data = await plGet(`/api/sessions/${SESSION_ID}/tasks`);
    plRenderTasks(data.items || []);
  } catch (err) {
    plWrite("Fehler Tasks", { error: String(err) });
  }
}

// -- WebSocket --
function plConnectWs() {
  if (!SESSION_ID || !WS_TOKEN) return plWrite("WS", { error: "Session/Token fehlt." });
  if (plSocket && plSocket.readyState === WebSocket.OPEN) return;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  plSocket = new WebSocket(
    `${proto}://${window.location.host}/api/sessions/${SESSION_ID}/chat/ws?token=${encodeURIComponent(WS_TOKEN)}&stream_timer=1`
  );
  plSocket.onopen = () => {
    plWrite("WebSocket", { status: "verbunden" });
    if (wsBtn) wsBtn.classList.add("is-connected");
  };
  plSocket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.message_type && payload.message_type !== "timer_tick") {
        plLoadChat();
        plListTasks();
      }
    } catch (_) {}
  };
  plSocket.onclose = () => {
    plWrite("WebSocket", { status: "getrennt" });
    if (wsBtn) wsBtn.classList.remove("is-connected");
    plSocket = null;
  };
}

// -- Safety --
async function plSafety(color) {
  if (!SESSION_ID) return;
  try {
    const data = await plPost(`/api/sessions/${SESSION_ID}/safety/traffic-light`, { color });
    if (statusPillEl) statusPillEl.textContent = data.status;
    if (statusTextEl) statusTextEl.textContent = data.status;
    plWrite(`Safety ${color}`, data);
  } catch (err) {
    plWrite("Fehler Safety", { error: String(err) });
  }
}

async function plSafeword() {
  if (!SESSION_ID) return;
  try {
    const data = await plPost(`/api/sessions/${SESSION_ID}/safety/safeword`, {});
    if (statusPillEl) statusPillEl.textContent = data.status;
    if (statusTextEl) statusTextEl.textContent = data.status;
    plWrite("Safeword", data);
  } catch (err) {
    plWrite("Fehler Safeword", { error: String(err) });
  }
}

// -- Event wiring --
document.getElementById("play-send")?.addEventListener("click", async () => {
  if (!SESSION_ID) return;
  const content = chatInput?.value?.trim() || "";
  if (!content) return;
  const sendBtn = document.getElementById("play-send");
  sendBtn.disabled = true;
  const savedText = sendBtn.textContent;
  sendBtn.textContent = "…";
  if (chatInput) chatInput.value = "";
  try {
    const data = await plPost(`/api/sessions/${SESSION_ID}/messages`, { content });
    plWrite("Chat Reply", data);
    await plLoadChat();
    await plListTasks();
  } catch (err) {
    plWrite("Fehler Chat", { error: String(err) });
    if (chatInput) chatInput.value = content;
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = savedText;
  }
});

chatInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    document.getElementById("play-send")?.click();
  }
});

document.getElementById("play-regenerate")?.addEventListener("click", async () => {
  if (!SESSION_ID) return;
  try {
    const data = await plPost(`/api/sessions/${SESSION_ID}/messages/regenerate`, {});
    plWrite("Regenerate", data);
    await plLoadChat();
    await plListTasks();
  } catch (err) {
    plWrite("Fehler Regenerate", { error: String(err) });
  }
});

document.getElementById("play-load-chat")?.addEventListener("click", plLoadChat);
document.getElementById("play-load-tasks")?.addEventListener("click", plListTasks);
document.getElementById("play-connect-ws")?.addEventListener("click", plConnectWs);

document.getElementById("play-safety-green")?.addEventListener("click", () => plSafety("green"));
document.getElementById("play-safety-yellow")?.addEventListener("click", () => plSafety("yellow"));
document.getElementById("play-safety-red")?.addEventListener("click", () => plSafety("red"));
document.getElementById("play-safety-safeword")?.addEventListener("click", plSafeword);

// -- Verification --
let plPendingVerifyId = null;

function plRenderVerifications(items) {
  const el = document.getElementById("play-verify-history");
  if (!el) return;
  if (!Array.isArray(items) || !items.length) {
    el.innerHTML = "<p class='verify-empty'>Noch keine Verifikationen.</p>";
    return;
  }
  el.innerHTML = items
    .slice(-5)
    .reverse()
    .map((v) => {
      const pill = v.status === "confirmed"
        ? "<span class='verify-pill confirmed'>&#10003; Best&auml;tigt</span>"
        : v.status === "suspicious"
        ? "<span class='verify-pill suspicious'>&#9888; Verdacht</span>"
        : "<span class='verify-pill pending'>&#8987; Ausstehend</span>";
      const analysis = v.analysis ? `<p class='verify-analysis'>${String(v.analysis).replace(/</g, "&lt;")}</p>` : "";
      const seal = v.requested_seal_number ? `<span class='verify-seal-tag'>#${v.requested_seal_number}</span>` : "";
      return `<div class="verify-card">${pill}${seal}${analysis}</div>`;
    })
    .join("");
}

async function plLoadVerifications() {
  if (!SESSION_ID) return;
  try {
    const data = await plGet(`/api/sessions/${SESSION_ID}/verifications`);
    plRenderVerifications(data.items || []);
  } catch (err) {
    plWrite("Fehler Verifikation", { error: String(err) });
  }
}

document.getElementById("play-verify-file")?.addEventListener("change", (e) => {
  const file = e.target?.files?.[0];
  const label = e.target?.closest(".verify-file-label")?.querySelector("span");
  if (label) label.textContent = file ? file.name : "Foto wählen";
});

document.getElementById("play-request-verify")?.addEventListener("click", async () => {
  if (!SESSION_ID) return;
  const btn = document.getElementById("play-request-verify");
  btn.disabled = true;
  try {
    const sealEl = document.getElementById("play-verify-seal");
    // Try to get the active seal from history
    let sealNumber = null;
    try {
      const sealData = await plGet(`/api/sessions/${SESSION_ID}/seal-history`);
      const active = (sealData.items || []).find((s) => s.status === "active");
      if (active) sealNumber = active.seal_number;
    } catch (_) {}

    const data = await plPost(`/api/sessions/${SESSION_ID}/verifications/request`, {
      requested_seal_number: sealNumber,
    });
    plPendingVerifyId = data.verification_id;

    if (sealEl) sealEl.textContent = sealNumber || "—";
    const uploadArea = document.getElementById("play-verify-upload-area");
    if (uploadArea) uploadArea.classList.remove("is-hidden");
    plWrite("Verifikation angefordert", data);
  } catch (err) {
    plWrite("Fehler Verifikation", { error: String(err) });
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("play-verify-submit")?.addEventListener("click", async () => {
  if (!SESSION_ID || !plPendingVerifyId) return;
  const fileInput = document.getElementById("play-verify-file");
  const sealInput = document.getElementById("play-verify-seal-input");
  const file = fileInput?.files?.[0];
  if (!file) { plWrite("Hinweis", { error: "Kein Bild ausgewählt." }); return; }

  const submitBtn = document.getElementById("play-verify-submit");
  submitBtn.disabled = true;
  submitBtn.textContent = "Wird geprüft…";

  try {
    const form = new FormData();
    form.append("file", file);
    if (sealInput?.value?.trim()) form.append("observed_seal_number", sealInput.value.trim());

    const res = await fetch(
      `/api/sessions/${SESSION_ID}/verifications/${plPendingVerifyId}/upload`,
      { method: "POST", body: form }
    );
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));

    plPendingVerifyId = null;
    const uploadArea = document.getElementById("play-verify-upload-area");
    if (uploadArea) uploadArea.classList.add("is-hidden");
    if (fileInput) fileInput.value = "";
    if (sealInput) sealInput.value = "";
    await plLoadVerifications();
    plWrite("Verifikation", data);
  } catch (err) {
    plWrite("Fehler Upload", { error: String(err) });
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Hochladen & Prüfen";
  }
});

// -- Auto-load on page ready --
document.addEventListener("DOMContentLoaded", async () => {
  if (!SESSION_ID) return;
  await plLoadChat();
  await plListTasks();
  await plLoadVerifications();
  plConnectWs();
});

