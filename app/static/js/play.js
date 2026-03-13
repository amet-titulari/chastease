/* play.js – Play Mode (v0.1.5) */
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

// -- Attach-image state --
let plAttachedFile = null; // File | null

function plSetAttachedFile(file) {
  plAttachedFile = file;
  const preview = document.getElementById("play-attach-preview");
  const attachBtn = document.getElementById("play-attach");
  if (file) {
    preview.textContent = `📎 ${file.name}`;
    preview.style.display = "block";
    if (attachBtn) attachBtn.classList.add("has-attachment");
  } else {
    preview.textContent = "";
    preview.style.display = "none";
    if (attachBtn) attachBtn.classList.remove("has-attachment");
  }
}

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

// Pending tasks state – kept so plRenderChat can append cards after each reload
let _pendingTaskItems = [];
// Last known message list – used by plInstallInlineTaskCards for re-render without full HTTP reload
let _lastMessageItems = [];

// -- Render chat --
function plRenderChat(items) {
  if (!chatTimeline) return;
  _lastMessageItems = Array.isArray(items) ? items : [];
  if (!_lastMessageItems.length) {
    chatTimeline.innerHTML = "<p>Noch keine Nachrichten.</p>";
    plInstallInlineTaskCards();
    return;
  }
  chatTimeline.innerHTML = _lastMessageItems
    .slice(-80)
    .map((item) => {
      const role = item.role || "system";
      const cssRole = role === "assistant" ? "from-ai" : "from-user";
      const content = String(item.content || "").replace(/</g, "&lt;");
      const ts = item.created_at ? new Date(item.created_at).toLocaleTimeString("de-DE") : "";
      // Store task IDs on task_assigned bubbles so cards can be injected inline
      let taskAttr = "";
      if (item.message_type === "task_assigned") {
        const ids = (item.content || "").match(/\d+/g) || [];
        taskAttr = ` data-msg-type="task_assigned" data-task-ids="${ids.join(",")}"`;
      }
      return `
        <div class="chat-bubble ${cssRole}"${taskAttr}>
          <div class="bubble-body">${content}</div>
          <div class="bubble-meta">${role}${ts ? " &middot; " + ts : ""}</div>
        </div>`;
    })
    .join("");
  plInstallInlineTaskCards();
  chatTimeline.scrollTop = chatTimeline.scrollHeight;
}

// Insert task action cards inline after their task_assigned message (slide-up behaviour)
function plInstallInlineTaskCards() {
  if (!chatTimeline) return;
  chatTimeline.querySelectorAll(".play-action-cards").forEach((w) => w.remove());
  if (!_pendingTaskItems.length) return;

  const pendingById = {};
  _pendingTaskItems.forEach((t) => { pendingById[t.id] = t; });
  const renderedIds = new Set();

  // Place each card inline, right after its task_assigned system message
  chatTimeline.querySelectorAll("[data-msg-type='task_assigned']").forEach((bubble) => {
    const rawIds = (bubble.dataset.taskIds || "").split(",").map(Number).filter(Boolean);
    const cards = rawIds
      .filter((id) => pendingById[id] && !renderedIds.has(id))
      .map((id) => { renderedIds.add(id); return plBuildSingleActionCard(pendingById[id]); });
    if (!cards.length) return;
    const wrapper = document.createElement("div");
    wrapper.className = "play-action-cards";
    wrapper.innerHTML = cards.join("");
    bubble.after(wrapper);
    plAttachActionCardHandlers(wrapper);
  });

  // Fallback: tasks not yet linked to a task_assigned message (edge case)
  const unrendered = _pendingTaskItems.filter((t) => !renderedIds.has(t.id));
  if (!unrendered.length) return;
  const fallback = document.createElement("div");
  fallback.className = "play-action-cards";
  fallback.innerHTML = unrendered.map(plBuildSingleActionCard).join("");
  chatTimeline.appendChild(fallback);
  plAttachActionCardHandlers(fallback);
}

// -- Render tasks --
const taskDropBoard = document.getElementById("play-task-drop-board");
const tasksToggleBtn = document.getElementById("play-tasks-toggle");
const tasksBadge = document.getElementById("play-tasks-badge");

// Dropdown: read-only list of pending task names
function plBuildTaskCards(items) {
  const pending = Array.isArray(items) ? items.filter((i) => i.status === "pending") : [];
  if (!pending.length) return "<p>Keine offenen Tasks.</p>";
  return pending
    .map((item) => {
      const title = String(item.title || "").replace(/</g, "&lt;");
      const icon = item.requires_verification ? "&#128247;" : "&#128203;";
      return `<div class="task-card"><div class="task-card-title">${icon} ${title}</div></div>`;
    })
    .join("");
}

// Build a single action card HTML string
function plBuildSingleActionCard(item) {
  const title = String(item.title || "").replace(/</g, "&lt;");
  const criteria = String(item.verification_criteria || "").replace(/"/g, "&quot;");
  const isVerify = !!item.requires_verification;
  const criteriaHtml =
    isVerify && item.verification_criteria
      ? `<p class="ac-hint">&#128203; ${String(item.verification_criteria).replace(/</g, "&lt;")}</p>`
      : "";
  const actions = isVerify
    ? `<button class="ac-btn ac-btn--photo" data-action="verify">&#128247; Foto senden</button>
       <button class="ac-btn ac-btn--fail" data-action="fail">&#10007; Fail</button>`
    : `<button class="ac-btn ac-btn--done" data-action="complete">&#10003; Erledigt</button>
       <button class="ac-btn ac-btn--fail" data-action="fail">&#10007; Fail</button>`;
  const uploadArea = isVerify
    ? `<div class="ac-upload is-hidden">
        <p class="ac-seal-row" style="display:none">Plombe: <code class="ac-seal-code"></code></p>
        <label class="ac-file-label">
          <input type="file" accept="image/*" capture="environment" class="ac-file-input" />
          <span>Foto w&auml;hlen</span>
        </label>
        <button class="ac-submit-btn" type="button">Hochladen &amp; Pr&uuml;fen</button>
      </div>`
    : "";
  return `
    <div class="action-card ${isVerify ? "action-card--verify" : "action-card--task"}"
         data-task-id="${item.id}"
         data-requires-verification="${isVerify ? "1" : ""}"
         data-verification-criteria="${criteria}">
      <div class="ac-header">
        <span class="ac-label">${isVerify ? "&#128247; Verifikation" : "&#128203; Task"}</span>
        <span class="ac-title">${title}</span>
      </div>
      ${criteriaHtml}
      <div class="ac-actions">${actions}</div>
      ${uploadArea}
    </div>`;
}

// Action cards: full interactive cards rendered above the chat input
function plBuildActionCards(items) {
  const pending = Array.isArray(items) ? items.filter((i) => i.status === "pending") : [];
  return pending.map(plBuildSingleActionCard).join("");
}

async function plSubmitVerificationCard(card) {
  const taskId = Number(card.dataset.taskId || 0);
  const verifyId = card.dataset.verifyId;
  const sealNumber = card.dataset.verifySeal || null;
  if (!verifyId) return;
  const fileInput = card.querySelector(".ac-file-input");
  const file = fileInput?.files?.[0];
  if (!file) { plWrite("Hinweis", { error: "Kein Bild ausgewählt." }); return; }
  const submitBtn = card.querySelector(".ac-submit-btn");
  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Wird geprüft\u2026"; }
  try {
    const form = new FormData();
    form.append("file", file);
    if (sealNumber) form.append("observed_seal_number", sealNumber);
    const res = await fetch(`/api/sessions/${SESSION_ID}/verifications/${verifyId}/upload`, {
      method: "POST",
      body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    const pill =
      data.status === "confirmed"
        ? "<span class='verify-pill confirmed'>&#10003; Best&auml;tigt</span>"
        : data.status === "suspicious"
        ? "<span class='verify-pill suspicious'>&#9888; Verdacht</span>"
        : "<span class='verify-pill pending'>&#8987; Ausstehend</span>";
    const uploadArea = card.querySelector(".ac-upload");
    if (uploadArea) {
      uploadArea.innerHTML = `<div class="ac-result">${pill}${
        data.analysis ? `<p class="ac-hint">${String(data.analysis).replace(/</g, "&lt;")}</p>` : ""
      }</div>`;
    }
    // Pre-remove from pending so the card doesn't flash back on chat reload
    if (taskId && data.status === "confirmed") {
      _pendingTaskItems = _pendingTaskItems.filter((t) => t.id !== taskId);
    }
    await plLoadChat();   // shows backend result message in chat timeline
    await plListTasks();  // syncs pending list
    plWrite("Verifikation", data);
  } catch (err) {
    plWrite("Fehler Upload", { error: String(err) });
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Hochladen & Prüfen"; }
  }
}

function plAttachActionCardHandlers(container) {
  container.querySelectorAll(".action-card button[data-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const card = btn.closest(".action-card");
      const taskId = card ? Number(card.dataset.taskId) : 0;
      if (!taskId || !SESSION_ID) return;
      const action = btn.dataset.action;

      if (action === "verify") {
        btn.disabled = true;
        try {
          const criteria = card.dataset.verificationCriteria || null;
          let sealNumber = null;
          try {
            const sealData = await plGet(`/api/sessions/${SESSION_ID}/seal-history`);
            const active = (sealData.entries || []).find((s) => s.status === "active");
            if (active) sealNumber = active.seal_number;
          } catch (_) {}
          const data = await plPost(`/api/sessions/${SESSION_ID}/verifications/request`, {
            requested_seal_number: sealNumber,
            linked_task_id: taskId,
            verification_criteria: criteria,
          });
          card.dataset.verifyId = data.verification_id;
          card.dataset.verifySeal = sealNumber || "";
          const uploadArea = card.querySelector(".ac-upload");
          if (uploadArea) uploadArea.classList.remove("is-hidden");
          const sealRow = card.querySelector(".ac-seal-row");
          const sealCode = card.querySelector(".ac-seal-code");
          if (sealNumber && sealRow && sealCode) {
            sealCode.textContent = sealNumber;
            sealRow.style.display = "";
          }
          btn.style.display = "none";
          card.querySelector(".ac-submit-btn")?.addEventListener("click", () => plSubmitVerificationCard(card));
          card.querySelector(".ac-file-input")?.addEventListener("change", (e) => {
            const f = e.target?.files?.[0];
            const span = e.target?.closest(".ac-file-label")?.querySelector("span");
            if (span) span.textContent = f ? f.name : "Foto wählen";
          });
          chatTimeline?.scrollTo({ top: chatTimeline.scrollHeight, behavior: "smooth" });
          plWrite("Verifikation angefordert", data);
        } catch (err) {
          plWrite("Fehler Verifikation", { error: String(err) });
          btn.disabled = false;
        }
        return;
      }

      const status = action === "complete" ? "completed" : "failed";
      try {
        await plPost(`/api/sessions/${SESSION_ID}/tasks/${taskId}/status`, { status });
        // Immediately hide the card before reload to avoid flicker
        _pendingTaskItems = _pendingTaskItems.filter((t) => t.id !== taskId);
        await plLoadChat();   // shows task_reward / consequence message
        await plListTasks();  // syncs full pending list
      } catch (err) {
        plWrite("Fehler Task-Update", { error: String(err) });
      }
    });
  });
}

function plRenderTasks(items) {
  const pending = Array.isArray(items) ? items.filter((i) => i.status === "pending") : [];
  const count = pending.length;

  // Store for re-use when chat is re-rendered
  _pendingTaskItems = pending;

  // Re-install inline task cards in the current chat DOM
  plInstallInlineTaskCards();

  // Header dropdown (read-only overview)
  if (taskDropBoard) {
    taskDropBoard.innerHTML = plBuildTaskCards(items);
  }

  // Update badge/button
  if (tasksToggleBtn) {
    if (count > 0) {
      tasksToggleBtn.classList.add("has-pending");
    } else {
      tasksToggleBtn.classList.remove("has-pending");
    }
  }
  if (tasksBadge) {
    if (count > 0) {
      tasksBadge.textContent = count;
      tasksBadge.classList.remove("is-hidden");
    } else {
      tasksBadge.classList.add("is-hidden");
    }
  }
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
  plSocket.onmessage = async (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.message_type && payload.message_type !== "timer_tick") {
        await plLoadChat();   // chat first so AI message appears before task card
        await plListTasks();
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
document.getElementById("play-attach")?.addEventListener("click", () => {
  if (plAttachedFile) {
    plSetAttachedFile(null);
    const fi = document.getElementById("play-file-input");
    if (fi) fi.value = "";
  } else {
    document.getElementById("play-file-input")?.click();
  }
});

document.getElementById("play-file-input")?.addEventListener("change", (e) => {
  const file = e.target.files?.[0] || null;
  plSetAttachedFile(file);
});

document.getElementById("play-send")?.addEventListener("click", async () => {
  if (!SESSION_ID) return;
  const content = chatInput?.value?.trim() || "";
  if (!content && !plAttachedFile) return;
  const sendBtn = document.getElementById("play-send");
  sendBtn.disabled = true;
  const savedText = sendBtn.textContent;
  sendBtn.textContent = "…";
  if (chatInput) chatInput.value = "";
  const fileToSend = plAttachedFile;
  plSetAttachedFile(null);
  const fi = document.getElementById("play-file-input");
  if (fi) fi.value = "";
  try {
    let data;
    if (fileToSend) {
      const fd = new FormData();
      fd.append("content", content);
      fd.append("file", fileToSend, fileToSend.name);
      const resp = await fetch(`/api/sessions/${SESSION_ID}/messages/image`, {
        method: "POST",
        body: fd,
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || resp.statusText);
      }
      data = await resp.json();
    } else {
      data = await plPost(`/api/sessions/${SESSION_ID}/messages`, { content });
    }
    plWrite("Chat Reply", data);
    await plLoadChat();
    await plListTasks();
  } catch (err) {
    plWrite("Fehler Chat", { error: String(err) });
    if (chatInput && content) chatInput.value = content;
    if (fileToSend) plSetAttachedFile(fileToSend);
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
document.getElementById("play-connect-ws")?.addEventListener("click", plConnectWs);

document.getElementById("play-resume-session")?.addEventListener("click", async () => {
  if (!SESSION_ID) return;
  const btn = document.getElementById("play-resume-session");
  btn.disabled = true;
  try {
    const data = await plPost(`/api/sessions/${SESSION_ID}/safety/resume`, {});
    if (statusPillEl) statusPillEl.textContent = data.status;
    if (statusTextEl) statusTextEl.textContent = data.status;
    btn.remove(); // hide button once active again
    plWrite("Session reaktiviert", data);
  } catch (err) {
    plWrite("Fehler Reaktivierung", { error: String(err) });
    btn.disabled = false;
  }
});

// -- Tasks dropdown toggle --
const tasksDropdown = document.getElementById("play-tasks-dropdown");

function closeTasksDropdown() {
  tasksDropdown?.classList.remove("is-open");
  document.getElementById("play-tasks-toggle")?.setAttribute("aria-expanded", "false");
}

document.getElementById("play-tasks-toggle")?.addEventListener("click", (e) => {
  e.stopPropagation();
  const open = tasksDropdown.classList.toggle("is-open");
  document.getElementById("play-tasks-toggle").setAttribute("aria-expanded", String(open));
});

document.addEventListener("click", (e) => {
  if (!e.target.closest("#play-tasks-menu")) closeTasksDropdown();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeTasksDropdown();
});

// -- Safety dropdown toggle --
const safetyToggle = document.getElementById("play-safety-toggle");
const safetyDropdown = document.getElementById("play-safety-dropdown");

function closeSafetyDropdown() {
  safetyDropdown?.classList.remove("is-open");
  safetyToggle?.setAttribute("aria-expanded", "false");
}

safetyToggle?.addEventListener("click", (e) => {
  e.stopPropagation();
  const open = safetyDropdown.classList.toggle("is-open");
  safetyToggle.setAttribute("aria-expanded", String(open));
});

document.addEventListener("click", (e) => {
  if (!e.target.closest("#play-safety-menu")) closeSafetyDropdown();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeSafetyDropdown();
});

function updateSafetyToggleStyle(color) {
  if (!safetyToggle) return;
  safetyToggle.classList.remove("is-yellow", "is-red", "is-safeword");
  if (color === "yellow") safetyToggle.classList.add("is-yellow");
  else if (color === "red") safetyToggle.classList.add("is-red");
  else if (color === "safeword") safetyToggle.classList.add("is-safeword");
}

document.getElementById("play-safety-green")?.addEventListener("click", () => {
  closeSafetyDropdown();
  updateSafetyToggleStyle("green");
  plSafety("green");
});
document.getElementById("play-safety-yellow")?.addEventListener("click", () => {
  closeSafetyDropdown();
  updateSafetyToggleStyle("yellow");
  plSafety("yellow");
});
document.getElementById("play-safety-red")?.addEventListener("click", () => {
  closeSafetyDropdown();
  updateSafetyToggleStyle("red");
  plSafety("red");
});
document.getElementById("play-safety-safeword")?.addEventListener("click", () => {
  closeSafetyDropdown();
  updateSafetyToggleStyle("safeword");
  plSafeword();
});

// -- Hygiene opening --
let plHygieneOpeningId = null;
let plHygieneUsesSeal = false;

function plHygieneSetPhase(phase) {
  const openArea = document.getElementById("psd-hygiene-open-area");
  const relockArea = document.getElementById("psd-hygiene-relock-area");
  if (phase === "relock") {
    openArea?.classList.add("is-hidden");
    relockArea?.classList.remove("is-hidden");
  } else {
    openArea?.classList.remove("is-hidden");
    relockArea?.classList.add("is-hidden");
  }
  const sealRow = document.getElementById("psd-hygiene-seal-row");
  if (sealRow) sealRow.style.display = (phase === "relock" && plHygieneUsesSeal) ? "" : "none";
}

document.getElementById("psd-hygiene-open")?.addEventListener("click", async () => {
  const btn = document.getElementById("psd-hygiene-open");
  const statusEl = document.getElementById("psd-hygiene-status");
  btn.disabled = true;
  try {
    const durationMins = parseInt(document.getElementById("psd-hygiene-duration")?.value || "15", 10);
    let oldSealNumber = null;
    try {
      const sealData = await plGet(`/api/sessions/${SESSION_ID}/seal-history`);
      const active = (sealData.entries || []).find((s) => s.status === "active");
      if (active) oldSealNumber = active.seal_number;
    } catch (_) {}
    plHygieneUsesSeal = !!oldSealNumber;
    const data = await plPost(`/api/sessions/${SESSION_ID}/hygiene/openings`, {
      duration_seconds: durationMins * 60,
      old_seal_number: oldSealNumber,
    });
    plHygieneOpeningId = data.opening_id;
    if (statusEl) { statusEl.textContent = `⏱️ Rück bis: ${new Date(data.due_back_at).toLocaleTimeString("de-DE")}`; statusEl.style.color = "var(--color-warn,#ffb300)"; }
    plHygieneSetPhase("relock");
  } catch (err) {
    if (statusEl) { statusEl.textContent = `Fehler: ${err}`; statusEl.style.color = "var(--color-error,#f44)"; }
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("psd-hygiene-relock")?.addEventListener("click", async () => {
  if (!plHygieneOpeningId) return;
  const statusEl = document.getElementById("psd-hygiene-status");
  let newSeal = null;
  if (plHygieneUsesSeal) {
    newSeal = document.getElementById("psd-hygiene-new-seal")?.value?.trim();
    if (!newSeal) {
      if (statusEl) { statusEl.textContent = "Neue Plombennummer ist erforderlich."; statusEl.style.color = "var(--color-error,#f44)"; }
      return;
    }
  }
  const btn = document.getElementById("psd-hygiene-relock");
  btn.disabled = true;
  try {
    const data = await plPost(`/api/sessions/${SESSION_ID}/hygiene/openings/${plHygieneOpeningId}/relock`, {
      new_seal_number: newSeal,
    });
    plHygieneOpeningId = null;
    plHygieneUsesSeal = false;
    plHygieneSetPhase("open");
    const sealInput = document.getElementById("psd-hygiene-new-seal");
    if (sealInput) sealInput.value = "";
    if (statusEl) { statusEl.textContent = "Wiederverschlossen ✓"; statusEl.style.color = "var(--color-success,#81c784)"; }
    // Update active seal display in verification area
    if (data.new_seal_number) plSetVerifySeal(data.new_seal_number);
    plWrite("Hygiene Wiederverschluss", data);
  } catch (err) {
    if (statusEl) { statusEl.textContent = `Fehler: ${err}`; statusEl.style.color = "var(--color-error,#f44)"; }
  } finally {
    btn.disabled = false;
  }
});

// -- Verification --
let plPendingVerifyId = null;
let plVerifySealNumber = null;

function plSetVerifySeal(sealNumber) {
  plVerifySealNumber = sealNumber || null;
  const row = document.getElementById("play-verify-seal-row");
  const code = document.getElementById("play-verify-seal");
  if (plVerifySealNumber) {
    if (code) code.textContent = plVerifySealNumber;
    if (row) row.style.display = "";
  } else {
    if (row) row.style.display = "none";
  }
}

function plRenderVerifications(items) {
  const el = document.getElementById("play-verify-history");
  if (!el) return;
  if (!Array.isArray(items) || !items.length) {
    el.innerHTML = "<p class='verify-empty'>Noch keine Verifikationen.</p>";
    return;
  }
  const latest = items.slice(-1);
  el.innerHTML = latest
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
    // Try to get the active seal from history
    let sealNumber = null;
    try {
      const sealData = await plGet(`/api/sessions/${SESSION_ID}/seal-history`);
      const active = (sealData.entries || []).find((s) => s.status === "active");
      if (active) sealNumber = active.seal_number;
    } catch (_) {}

    const data = await plPost(`/api/sessions/${SESSION_ID}/verifications/request`, {
      requested_seal_number: sealNumber,
    });
    plPendingVerifyId = data.verification_id;

    plSetVerifySeal(sealNumber);
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
  const file = fileInput?.files?.[0];
  if (!file) { plWrite("Hinweis", { error: "Kein Bild ausgewählt." }); return; }

  const submitBtn = document.getElementById("play-verify-submit");
  submitBtn.disabled = true;
  submitBtn.textContent = "Wird geprüft…";

  try {
    const form = new FormData();
    form.append("file", file);
    if (plVerifySealNumber) form.append("observed_seal_number", plVerifySealNumber);

    const res = await fetch(
      `/api/sessions/${SESSION_ID}/verifications/${plPendingVerifyId}/upload`,
      { method: "POST", body: form }
    );
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));

    plPendingVerifyId = null;
    plVerifySealNumber = null;
    const uploadArea = document.getElementById("play-verify-upload-area");
    if (uploadArea) uploadArea.classList.add("is-hidden");
    if (fileInput) fileInput.value = "";
    const criteriaHint = document.getElementById("play-verify-criteria-hint");
    if (criteriaHint) { criteriaHint.textContent = ""; criteriaHint.style.display = "none"; }
    await plLoadVerifications();
    await plListTasks();
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

// ============================================================
// Settings Drawer
// ============================================================
const settingsDrawer = document.getElementById("play-settings-drawer");
const settingsOverlay = document.getElementById("play-settings-overlay");

function plOpenSettings() {
  settingsDrawer?.classList.add("is-open");
  settingsOverlay?.classList.add("is-open");
  settingsDrawer?.setAttribute("aria-hidden", "false");
  plLoadSettingsSummary();
}

function plCloseSettings() {
  settingsDrawer?.classList.remove("is-open");
  settingsOverlay?.classList.remove("is-open");
  settingsDrawer?.setAttribute("aria-hidden", "true");
}

document.getElementById("play-settings-open")?.addEventListener("click", plOpenSettings);
document.getElementById("play-settings-close")?.addEventListener("click", plCloseSettings);
settingsOverlay?.addEventListener("click", plCloseSettings);

async function plLoadSettingsSummary() {
  try {
    const data = await plGet("/api/settings/summary");
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val || "—"; };
    const fmtDate = (val) => {
      if (!val) return "—";
      try {
        return new Date(val).toLocaleString("de-DE");
      } catch (_) {
        return String(val);
      }
    };
    const fmtSecs = (secs) => {
      if (secs === null || secs === undefined || Number.isNaN(Number(secs))) return "—";
      const total = Math.max(0, Number(secs));
      const h = Math.floor(total / 3600);
      const m = Math.floor((total % 3600) / 60);
      const s = Math.floor(total % 60);
      if (h > 0) return `${h}h ${m}m ${s}s`;
      return `${m}m ${s}s`;
    };

    if (data.session) {
      const s = data.session;
      set("psd-session-id", s.session_id ? `#${s.session_id}` : "—");
      set("psd-lock-start", fmtDate(s.lock_start));
      set("play-lock-end-display", fmtDate(s.lock_end));
      set("psd-remaining", fmtSecs(s.remaining_seconds));
      set("play-status-text", s.status);
      set("psd-timer-frozen", s.timer_frozen ? "eingefroren" : "laufend");
      set("psd-min-duration", fmtSecs(s.min_duration_seconds));
      set("psd-max-duration", s.max_duration_seconds ? fmtSecs(s.max_duration_seconds) : "—");
      set("psd-active-seal", s.active_seal_number || "—");
      set("psd-last-opening", s.last_opening_status ? `${s.last_opening_status}${s.last_opening_due_back_at ? ` (Rueckgabe: ${fmtDate(s.last_opening_due_back_at)})` : ""}` : "—");
      set("psd-hygiene-limits", `Tag: ${s.hygiene_limit_daily ?? "—"}, Woche: ${s.hygiene_limit_weekly ?? "—"}, Monat: ${s.hygiene_limit_monthly ?? "—"}`);
      set("psd-task-stats", `Gesamt: ${s.task_total ?? 0} | pending: ${s.task_pending ?? 0} | completed: ${s.task_completed ?? 0} | overdue: ${s.task_overdue ?? 0} | failed: ${s.task_failed ?? 0}`);
      set("psd-task-penalty", fmtSecs(s.task_penalty_total_seconds));
      set("psd-hygiene-penalty", `${fmtSecs(s.hygiene_penalty_total_seconds)} (Overrun: ${fmtSecs(s.hygiene_overrun_total_seconds)})`);
    }

    set("psd-exp", data.experience_level);
    set("psd-style", data.style);
    set("psd-goal", data.goal);
    set("psd-boundary", data.boundary);
    if (data.llm) {
      const llm = data.llm;
      set("psd-llm-provider-display", llm.provider || "—");
      set("psd-llm-chat-display", llm.chat_model || "—");
      set("psd-llm-key-display", llm.api_key_stored ? "hinterlegt ✓" : "nicht gesetzt");
      const keyEl = document.getElementById("psd-llm-key-display");
      if (keyEl) keyEl.style.color = llm.api_key_stored ? "var(--color-success, #81c784)" : "var(--muted)";
    }
  } catch (err) {
    plWrite("Settings load error", { error: String(err) });
  }
}

