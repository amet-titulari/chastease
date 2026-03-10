let sessionId = null;
let addendumId = null;
let openingId = null;
let verificationId = null;
let taskId = null;
let wsAuthToken = null;
let chatSocket = null;

const outputEl = document.getElementById("output");
const sessionIdEl = document.getElementById("session-id");
const addendumIdEl = document.getElementById("addendum-id");
const openingIdEl = document.getElementById("opening-id");

function writeOutput(title, data) {
  outputEl.textContent = `${title}\n${JSON.stringify(data, null, 2)}`;
}

function getAdminHeaders() {
  const field = document.getElementById("admin-secret");
  const value = field ? field.value : "";
  return value ? { "X-Admin-Secret": value } : {};
}

function syncIds() {
  sessionIdEl.textContent = sessionId ?? "-";
  addendumIdEl.textContent = addendumId ?? "-";
  openingIdEl.textContent = openingId ?? "-";
}

async function postJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(data));
  return data;
}

async function postJsonWithHeaders(url, payload, headers) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(data));
  return data;
}

async function getJson(url) {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(data));
  return data;
}

document.getElementById("create-session-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const formData = new FormData(e.target);
    const payload = {
      persona_name: formData.get("persona_name"),
      player_nickname: formData.get("player_nickname"),
      min_duration_seconds: Number(formData.get("min_duration_seconds")),
      max_duration_seconds: Number(formData.get("max_duration_seconds")),
    };
    const data = await postJson("/api/sessions", payload);
    sessionId = data.session_id;
    wsAuthToken = data.ws_auth_token ?? null;
    addendumId = null;
    openingId = null;
    syncIds();
    writeOutput("Session erstellt", data);
  } catch (err) {
    writeOutput("Fehler Session", { error: String(err) });
  }
});

document.getElementById("sign-contract-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const data = await postJson(`/api/sessions/${sessionId}/sign-contract`, {});
    wsAuthToken = data.ws_auth_token ?? wsAuthToken;
    writeOutput("Vertrag signiert", data);
  } catch (err) {
    writeOutput("Fehler Vertrag", { error: String(err) });
  }
});

document.getElementById("propose-addendum-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  if (!wsAuthToken) return writeOutput("Hinweis", { error: "WS-Token fehlt. Session neu laden/signieren." });
  try {
    const minSeconds = Number(document.getElementById("addendum-min-seconds").value);
    const data = await postJson(`/api/sessions/${sessionId}/contract/addenda`, {
      change_description: "Min duration adjustment",
      proposed_changes: { min_duration_seconds: minSeconds },
    });
    addendumId = data.addendum_id;
    syncIds();
    writeOutput("Addendum vorgeschlagen", data);
  } catch (err) {
    writeOutput("Fehler Addendum", { error: String(err) });
  }
});

async function consentAddendum(decision) {
  if (!sessionId || !addendumId) return writeOutput("Hinweis", { error: "Erst Addendum erstellen." });
  try {
    const data = await postJson(`/api/sessions/${sessionId}/contract/addenda/${addendumId}/consent`, { decision });
    writeOutput(`Addendum ${decision}`, data);
  } catch (err) {
    writeOutput("Fehler Consent", { error: String(err) });
  }
}

document.getElementById("approve-addendum-btn").addEventListener("click", () => consentAddendum("approved"));
document.getElementById("reject-addendum-btn").addEventListener("click", () => consentAddendum("rejected"));

document.getElementById("timer-status-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const data = await getJson(`/api/sessions/${sessionId}/timer`);
    writeOutput("Timer-Status", data);
  } catch (err) {
    writeOutput("Fehler Timer-Status", { error: String(err) });
  }
});

async function adjustTimer(mode) {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  const seconds = Number(document.getElementById("timer-seconds").value);
  if (!seconds || seconds < 1) return writeOutput("Hinweis", { error: "Ungueltige Sekunden." });
  try {
    const data = await postJson(`/api/sessions/${sessionId}/timer/${mode}`, { seconds });
    writeOutput(`Timer ${mode}`, data);
  } catch (err) {
    writeOutput(`Fehler Timer ${mode}`, { error: String(err) });
  }
}

document.getElementById("timer-add-btn").addEventListener("click", () => adjustTimer("add"));
document.getElementById("timer-remove-btn").addEventListener("click", () => adjustTimer("remove"));

document.getElementById("timer-freeze-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const data = await postJson(`/api/sessions/${sessionId}/timer/freeze`, {});
    writeOutput("Timer Freeze", data);
  } catch (err) {
    writeOutput("Fehler Timer Freeze", { error: String(err) });
  }
});

document.getElementById("timer-unfreeze-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const data = await postJson(`/api/sessions/${sessionId}/timer/unfreeze`, {});
    writeOutput("Timer Unfreeze", data);
  } catch (err) {
    writeOutput("Fehler Timer Unfreeze", { error: String(err) });
  }
});

document.getElementById("open-hygiene-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const duration_seconds = Number(document.getElementById("opening-duration-seconds").value);
    const old_seal_number = document.getElementById("old-seal").value || null;
    const data = await postJson(`/api/sessions/${sessionId}/hygiene/openings`, {
      duration_seconds,
      old_seal_number,
    });
    openingId = data.opening_id;
    syncIds();
    writeOutput("Hygiene-Oeffnung gestartet", data);
  } catch (err) {
    writeOutput("Fehler Hygiene Start", { error: String(err) });
  }
});

document.getElementById("hygiene-status-btn").addEventListener("click", async () => {
  if (!sessionId || !openingId) return writeOutput("Hinweis", { error: "Erst Hygiene-Oeffnung starten." });
  try {
    const data = await getJson(`/api/sessions/${sessionId}/hygiene/openings/${openingId}`);
    writeOutput("Hygiene-Status", data);
  } catch (err) {
    writeOutput("Fehler Hygiene Status", { error: String(err) });
  }
});

document.getElementById("relock-btn").addEventListener("click", async () => {
  if (!sessionId || !openingId) return writeOutput("Hinweis", { error: "Erst Hygiene-Oeffnung starten." });
  try {
    const new_seal_number = document.getElementById("new-seal").value || null;
    const data = await postJson(`/api/sessions/${sessionId}/hygiene/openings/${openingId}/relock`, {
      new_seal_number,
    });
    writeOutput("Wiederverschlossen", data);
  } catch (err) {
    writeOutput("Fehler Wiederverschliessen", { error: String(err) });
  }
});

async function traffic(color) {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const data = await postJsonWithHeaders(
      `/api/sessions/${sessionId}/safety/traffic-light`,
      { color },
      getAdminHeaders()
    );
    writeOutput(`Ampel ${color}`, data);
  } catch (err) {
    writeOutput("Fehler Ampel", { error: String(err) });
  }
}

document.getElementById("traffic-yellow-btn").addEventListener("click", () => traffic("yellow"));
document.getElementById("traffic-red-btn").addEventListener("click", () => traffic("red"));

document.getElementById("safeword-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const data = await postJson(`/api/sessions/${sessionId}/safety/safeword`, {});
    writeOutput("Safeword", data);
  } catch (err) {
    writeOutput("Fehler Safeword", { error: String(err) });
  }
});

document.getElementById("emergency-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const reason = document.getElementById("emergency-reason").value;
    const data = await postJsonWithHeaders(
      `/api/sessions/${sessionId}/safety/emergency-release`,
      { reason },
      getAdminHeaders()
    );
    writeOutput("Emergency Release", data);
  } catch (err) {
    writeOutput("Fehler Emergency", { error: String(err) });
  }
});

document.getElementById("safety-logs-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const data = await getJson(`/api/sessions/${sessionId}/safety/logs`);
    writeOutput("Safety Logs", data);
  } catch (err) {
    writeOutput("Fehler Safety Logs", { error: String(err) });
  }
});

document.getElementById("request-verification-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const requested_seal_number = document.getElementById("verification-requested-seal").value || null;
    const data = await postJson(`/api/sessions/${sessionId}/verifications/request`, { requested_seal_number });
    verificationId = data.verification_id;
    writeOutput("Verifikation angefordert", data);
  } catch (err) {
    writeOutput("Fehler Verifikation Request", { error: String(err) });
  }
});

document.getElementById("upload-verification-btn").addEventListener("click", async () => {
  if (!sessionId || !verificationId) return writeOutput("Hinweis", { error: "Erst Verifikation anfordern." });
  const fileInput = document.getElementById("verification-file");
  if (!fileInput.files || fileInput.files.length === 0) {
    return writeOutput("Hinweis", { error: "Bitte Bilddatei waehlen." });
  }

  try {
    const form = new FormData();
    form.append("file", fileInput.files[0]);
    form.append("observed_seal_number", document.getElementById("verification-observed-seal").value || "");
    const res = await fetch(`/api/sessions/${sessionId}/verifications/${verificationId}/upload`, {
      method: "POST",
      headers: getAdminHeaders(),
      body: form,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    writeOutput("Verifikation hochgeladen", data);
  } catch (err) {
    writeOutput("Fehler Verifikation Upload", { error: String(err) });
  }
});

document.getElementById("chat-send-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const content = document.getElementById("chat-input").value;
    const data = await postJson(`/api/sessions/${sessionId}/messages`, { content });
    writeOutput("Chat Antwort", data);
  } catch (err) {
    writeOutput("Fehler Chat", { error: String(err) });
  }
});

document.getElementById("chat-list-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const data = await getJson(`/api/sessions/${sessionId}/messages`);
    writeOutput("Chat Verlauf", data);
  } catch (err) {
    writeOutput("Fehler Chat Verlauf", { error: String(err) });
  }
});

document.getElementById("chat-ws-rotate-token-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const headers = getAdminHeaders();
    const data = await postJsonWithHeaders(`/api/sessions/${sessionId}/chat/ws-token/rotate`, {}, headers);
    wsAuthToken = data.ws_auth_token;
    if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
      chatSocket.close();
      chatSocket = null;
    }
    writeOutput("WS-Token rotiert", data);
  } catch (err) {
    writeOutput("Fehler WS-Token Rotation", { error: String(err) });
  }
});

document.getElementById("chat-ws-connect-btn").addEventListener("click", () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
    return writeOutput("WebSocket", { status: "bereits verbunden" });
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  chatSocket = new WebSocket(
    `${protocol}://${window.location.host}/api/sessions/${sessionId}/chat/ws?token=${encodeURIComponent(wsAuthToken)}`
  );

  chatSocket.onopen = () => writeOutput("WebSocket", { status: "verbunden" });
  chatSocket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      writeOutput("Live Chat Event", payload);
    } catch (err) {
      writeOutput("WebSocket Parse Fehler", { error: String(err) });
    }
  };
  chatSocket.onerror = () => writeOutput("WebSocket", { status: "fehler" });
  chatSocket.onclose = () => writeOutput("WebSocket", { status: "getrennt" });
});

document.getElementById("chat-ws-disconnect-btn").addEventListener("click", () => {
  if (!chatSocket) return writeOutput("WebSocket", { status: "nicht verbunden" });
  chatSocket.close();
  chatSocket = null;
});

document.getElementById("task-create-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const payload = {
      title: document.getElementById("task-title").value,
      description: document.getElementById("task-description").value,
      deadline_minutes: Number(document.getElementById("task-deadline").value),
    };
    const data = await postJson(`/api/sessions/${sessionId}/tasks`, payload);
    taskId = data.task_id;
    document.getElementById("task-id").value = taskId;
    writeOutput("Task erstellt", data);
  } catch (err) {
    writeOutput("Fehler Task", { error: String(err) });
  }
});

document.getElementById("task-list-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const data = await getJson(`/api/sessions/${sessionId}/tasks`);
    writeOutput("Tasks", data);
  } catch (err) {
    writeOutput("Fehler Task Liste", { error: String(err) });
  }
});

document.getElementById("task-evaluate-overdue-btn").addEventListener("click", async () => {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  try {
    const data = await postJson(`/api/sessions/${sessionId}/tasks/evaluate-overdue`, {});
    writeOutput("Task Overdue-Auswertung", data);
  } catch (err) {
    writeOutput("Fehler Task Overdue", { error: String(err) });
  }
});

async function updateTaskStatus(status) {
  if (!sessionId) return writeOutput("Hinweis", { error: "Erst Session erstellen." });
  const selectedTaskId = Number(document.getElementById("task-id").value || taskId);
  if (!selectedTaskId) return writeOutput("Hinweis", { error: "Task-ID fehlt." });
  try {
    const data = await postJson(`/api/sessions/${sessionId}/tasks/${selectedTaskId}/status`, { status });
    writeOutput(`Task ${status}`, data);
  } catch (err) {
    writeOutput("Fehler Task Status", { error: String(err) });
  }
}

document.getElementById("task-complete-btn").addEventListener("click", () => updateTaskStatus("completed"));
document.getElementById("task-fail-btn").addEventListener("click", () => updateTaskStatus("failed"));

syncIds();
