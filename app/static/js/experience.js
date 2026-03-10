let xpSessionId = null;
let xpWsToken = null;
let xpSocket = null;
let xpStep = 1;
let xpPersonaPresets = [];

const xpChatTimeline = document.getElementById("xp-chat-timeline");
const xpTaskBoard = document.getElementById("xp-task-board");

const statusEl = document.getElementById("onboarding-status");
const outputEl = document.getElementById("xp-output");
const contractEl = document.getElementById("xp-contract-preview");
const playCardEl = document.getElementById("play-card");
const sessionIdEl = document.getElementById("xp-session-id");
const sessionStatusEl = document.getElementById("xp-session-status");
const timerRemainingEl = document.getElementById("xp-timer-remaining");

function xpWrite(title, data) {
  outputEl.textContent = `${title}\n${JSON.stringify(data, null, 2)}`;
}

function xpRenderChat(items) {
  if (!Array.isArray(items) || !items.length) {
    xpChatTimeline.innerHTML = "<p>Noch keine Nachrichten.</p>";
    return;
  }

  const html = items
    .slice(-60)
    .map((item) => {
      const role = item.role || "system";
      const content = String(item.content || "").replace(/</g, "&lt;");
      return `<div class="chat-bubble ${role}"><strong>${role}</strong><br>${content}</div>`;
    })
    .join("");
  xpChatTimeline.innerHTML = html;
  xpChatTimeline.scrollTop = xpChatTimeline.scrollHeight;
}

function xpChipClass(status) {
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  if (status === "overdue") return "overdue";
  return "pending";
}

function xpRenderTasks(items) {
  if (!Array.isArray(items) || !items.length) {
    xpTaskBoard.innerHTML = "<p>Noch keine Tasks.</p>";
    return;
  }

  xpTaskBoard.innerHTML = items
    .map((item) => {
      const chip = xpChipClass(item.status);
      const disabled = item.status !== "pending" ? "disabled" : "";
      const title = String(item.title || "").replace(/</g, "&lt;");
      return `
        <article class="task-card" data-task-id="${item.id}">
          <div class="task-head">
            <span class="task-title">${title}</span>
            <span class="chip ${chip}">${item.status}</span>
          </div>
          <div class="task-actions">
            <button class="ok" data-action="complete" ${disabled}>Complete</button>
            <button class="fail" data-action="fail" ${disabled}>Fail</button>
          </div>
        </article>
      `;
    })
    .join("");

  xpTaskBoard.querySelectorAll("button[data-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const card = btn.closest(".task-card");
      const taskId = card ? Number(card.dataset.taskId) : 0;
      if (!taskId || !xpSessionId) return;
      const action = btn.dataset.action;
      const status = action === "complete" ? "completed" : "failed";
      try {
        const updated = await xpPost(`/api/sessions/${xpSessionId}/tasks/${taskId}/status`, { status });
        xpWrite(`Task ${status}`, updated);
        await xpListTasks();
      } catch (err) {
        xpWrite("Fehler Task-Update", { error: String(err) });
      }
    });
  });
}

function xpParseOptionalInt(v) {
  const raw = String(v ?? "").trim();
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? Math.trunc(n) : null;
}

async function xpGet(url) {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(data));
  return data;
}

async function xpPost(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(data));
  return data;
}

async function xpPut(url, payload) {
  const res = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(data));
  return data;
}

function xpSwitchStep(next) {
  xpStep = Math.max(1, Math.min(4, next));
  statusEl.textContent = `Schritt ${xpStep} von 4`;

  document.querySelectorAll(".step-tab").forEach((el) => {
    el.classList.toggle("is-active", Number(el.dataset.step) === xpStep);
  });
  document.querySelectorAll(".step-pane").forEach((el) => {
    el.classList.toggle("is-active", Number(el.dataset.step) === xpStep);
  });
}

async function xpLoadPersonaPresets() {
  const select = document.getElementById("xp-persona-preset");
  select.innerHTML = "";
  try {
    const data = await xpGet("/api/personas/presets");
    xpPersonaPresets = data.items || [];
    if (!xpPersonaPresets.length) {
      select.innerHTML = '<option value="">Keine Presets</option>';
      return;
    }
    xpPersonaPresets.forEach((preset) => {
      const opt = document.createElement("option");
      opt.value = preset.key;
      opt.textContent = preset.name;
      select.appendChild(opt);
    });
    const initial = xpPersonaPresets.find((item) => item.name === "Ballet Sub Ella") || xpPersonaPresets[0];
    select.value = initial.key;
    document.getElementById("xp-persona-name").value = initial.name;
  } catch (err) {
    select.innerHTML = '<option value="">Preset-Fehler</option>';
    xpWrite("Fehler Persona Presets", { error: String(err) });
  }
}

async function xpLoadChat() {
  if (!xpSessionId) return;
  try {
    const data = await xpGet(`/api/sessions/${xpSessionId}/messages`);
    xpRenderChat(data.items || []);
    xpWrite("Chat Verlauf", { count: (data.items || []).length });
  } catch (err) {
    xpWrite("Fehler Verlauf", { error: String(err) });
  }
}

async function xpListTasks() {
  if (!xpSessionId) return;
  try {
    const data = await xpGet(`/api/sessions/${xpSessionId}/tasks`);
    xpRenderTasks(data.items || []);
    xpWrite("Tasks", { count: (data.items || []).length });
  } catch (err) {
    xpWrite("Fehler Tasks", { error: String(err) });
  }
}

document.getElementById("xp-persona-preset").addEventListener("change", (e) => {
  const preset = xpPersonaPresets.find((item) => item.key === e.target.value);
  if (preset) {
    document.getElementById("xp-persona-name").value = preset.name;
  }
});

document.querySelectorAll(".step-tab").forEach((btn) => {
  btn.addEventListener("click", () => xpSwitchStep(Number(btn.dataset.step)));
});

document.getElementById("xp-prev-step").addEventListener("click", () => xpSwitchStep(xpStep - 1));
document.getElementById("xp-next-step").addEventListener("click", () => xpSwitchStep(xpStep + 1));

document.getElementById("xp-create-session").addEventListener("click", async () => {
  try {
    const payload = {
      persona_name: document.getElementById("xp-persona-name").value,
      player_nickname: document.getElementById("xp-player-nickname").value,
      min_duration_seconds: Number(document.getElementById("xp-min-seconds").value),
      max_duration_seconds: Number(document.getElementById("xp-max-seconds").value),
      hygiene_limit_daily: xpParseOptionalInt(document.getElementById("xp-hygiene-day").value),
      hygiene_limit_weekly: xpParseOptionalInt(document.getElementById("xp-hygiene-week").value),
      hygiene_limit_monthly: xpParseOptionalInt(document.getElementById("xp-hygiene-month").value),
    };
    const created = await xpPost("/api/sessions", payload);
    xpSessionId = created.session_id;
    xpWsToken = created.ws_auth_token;
    sessionIdEl.textContent = String(xpSessionId);
    sessionStatusEl.textContent = created.status;
    contractEl.textContent = created.contract_preview || "(keine Vorschau)";

    const profilePayload = {
      experience_level: document.getElementById("xp-experience-level").value,
      hard_limits: String(document.getElementById("xp-hard-limits").value)
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean),
      reaction_patterns: {
        penalty_multiplier: Number(document.getElementById("xp-penalty-multiplier").value || "1"),
      },
      needs: {
        gentle_mode: document.getElementById("xp-gentle-mode").value === "true",
      },
    };
    await xpPut(`/api/sessions/${xpSessionId}/player-profile`, profilePayload);

    xpSwitchStep(4);
    xpWrite("Session erstellt", created);
  } catch (err) {
    xpWrite("Fehler Session", { error: String(err) });
  }
});

document.getElementById("xp-sign-contract").addEventListener("click", async () => {
  if (!xpSessionId) return xpWrite("Hinweis", { error: "Erst Session erstellen." });
  try {
    const signed = await xpPost(`/api/sessions/${xpSessionId}/sign-contract`, {});
    xpWsToken = signed.ws_auth_token || xpWsToken;
    sessionStatusEl.textContent = signed.status;
    playCardEl.classList.add("is-live");
    xpWrite("Session aktiv", signed);
    await xpLoadChat();
    await xpListTasks();
  } catch (err) {
    xpWrite("Fehler Signatur", { error: String(err) });
  }
});

document.getElementById("xp-refresh-timer").addEventListener("click", async () => {
  if (!xpSessionId) return;
  try {
    const timer = await xpGet(`/api/sessions/${xpSessionId}/timer`);
    timerRemainingEl.textContent = String(timer.remaining_seconds);
    xpWrite("Timer", timer);
  } catch (err) {
    xpWrite("Fehler Timer", { error: String(err) });
  }
});

document.getElementById("xp-connect-ws").addEventListener("click", () => {
  if (!xpSessionId || !xpWsToken) return xpWrite("Hinweis", { error: "Session/Token fehlt." });
  if (xpSocket && xpSocket.readyState === WebSocket.OPEN) return;

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  xpSocket = new WebSocket(
    `${protocol}://${window.location.host}/api/sessions/${xpSessionId}/chat/ws?token=${encodeURIComponent(xpWsToken)}&stream_timer=1`
  );
  xpSocket.onopen = () => xpWrite("WebSocket", { status: "verbunden" });
  xpSocket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.message_type === "timer_tick") {
      timerRemainingEl.textContent = String(payload.remaining_seconds);
    }
    if (payload.message_type && payload.message_type !== "timer_tick") {
      xpLoadChat();
      xpListTasks();
    }
    xpWrite("Live Event", payload);
  };
  xpSocket.onclose = () => xpWrite("WebSocket", { status: "getrennt" });
});

document.getElementById("xp-send-chat").addEventListener("click", async () => {
  if (!xpSessionId) return;
  try {
    const content = document.getElementById("xp-chat-input").value;
    const data = await xpPost(`/api/sessions/${xpSessionId}/messages`, { content });
    xpWrite("Chat Reply", data);
    await xpLoadChat();
    await xpListTasks();
  } catch (err) {
    xpWrite("Fehler Chat", { error: String(err) });
  }
});

document.getElementById("xp-load-chat").addEventListener("click", async () => {
  await xpLoadChat();
});

document.getElementById("xp-create-task").addEventListener("click", async () => {
  if (!xpSessionId) return;
  try {
    const data = await xpPost(`/api/sessions/${xpSessionId}/tasks`, {
      title: document.getElementById("xp-task-title").value,
      deadline_minutes: 15,
    });
    xpWrite("Task erstellt", data);
    await xpListTasks();
  } catch (err) {
    xpWrite("Fehler Task", { error: String(err) });
  }
});

document.getElementById("xp-list-tasks").addEventListener("click", async () => {
  await xpListTasks();
});

async function xpSafety(color) {
  if (!xpSessionId) return;
  try {
    const data = await xpPost(`/api/sessions/${xpSessionId}/safety/traffic-light`, { color });
    sessionStatusEl.textContent = data.status;
    xpWrite(`Safety ${color}`, data);
  } catch (err) {
    xpWrite("Fehler Safety", { error: String(err) });
  }
}

document.getElementById("xp-safety-yellow").addEventListener("click", () => xpSafety("yellow"));
document.getElementById("xp-safety-red").addEventListener("click", () => xpSafety("red"));
document.getElementById("xp-safety-safeword").addEventListener("click", async () => {
  if (!xpSessionId) return;
  try {
    const data = await xpPost(`/api/sessions/${xpSessionId}/safety/safeword`, {});
    sessionStatusEl.textContent = data.status;
    xpWrite("Safeword", data);
  } catch (err) {
    xpWrite("Fehler Safeword", { error: String(err) });
  }
});

document.getElementById("xp-dock-yellow").addEventListener("click", () => xpSafety("yellow"));
document.getElementById("xp-dock-red").addEventListener("click", () => xpSafety("red"));
document.getElementById("xp-dock-safeword").addEventListener("click", async () => {
  if (!xpSessionId) return;
  try {
    const data = await xpPost(`/api/sessions/${xpSessionId}/safety/safeword`, {});
    sessionStatusEl.textContent = data.status;
    xpWrite("Safeword", data);
  } catch (err) {
    xpWrite("Fehler Safeword", { error: String(err) });
  }
});

xpLoadPersonaPresets();
xpSwitchStep(1);
xpRenderChat([]);
xpRenderTasks([]);
