/* play.js – Play Mode (v0.3.5) */
"use strict";

// -- State from server-rendered dataset --
const _shell = document.querySelector(".play-shell");
const SESSION_ID = Number(_shell?.dataset.sessionId || 0);
const WS_TOKEN = _shell?.dataset.wsToken || "";
const LOCK_END = _shell?.dataset.lockEnd || "";
const PERSONA_NAME = _shell?.dataset.personaName || "Keyholderin";
const PLAYER_NAME = _shell?.dataset.playerName || "Du";

let plSocket = null;
let plVoiceSocket = null;
let _personaAvatarUrl = null;
let plVoiceAudioCtx = null;
let plVoiceMicStream = null;
let plVoiceProcessor = null;
let plVoiceSessionReady = false;
let plVoicePlayCursor = 0;
let plVoiceAvailable = false;
let plVoiceMode = "realtime-manual";

// -- DOM refs --
const statusPillEl = document.getElementById("play-status-pill");
const chatTimeline = document.getElementById("play-chat-timeline");
const opsBannerEl = document.getElementById("play-ops-banner");
const chatInput = document.getElementById("play-chat-input");
const taskBoard = document.getElementById("play-task-board");
const debugOut = document.getElementById("play-output");
const wsBtn = document.getElementById("play-connect-ws");
const voiceStatusEl = document.getElementById("play-voice-status");
const voiceToggleBtn = document.getElementById("play-voice-toggle");

function plEscapeHtml(value) {
  return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function plRenderMessageHtml(value) {
  const escaped = plEscapeHtml(value);
  return escaped
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*\n]+)\*/g, "<em>$1</em>")
    .replace(/\n/g, "<br>");
}

function plIsVoiceRunning() {
  return Boolean(
    plVoiceSocket && (plVoiceSocket.readyState === WebSocket.OPEN || plVoiceSocket.readyState === WebSocket.CONNECTING)
  );
}

function plSetVoiceStatus(text) {
  if (voiceStatusEl) voiceStatusEl.textContent = text;
}

function plSyncVoiceToggleUi() {
  if (!voiceToggleBtn) return;
  const running = plIsVoiceRunning();
  voiceToggleBtn.setAttribute("aria-pressed", running ? "true" : "false");
  voiceToggleBtn.textContent = "🔊";
  voiceToggleBtn.title = running ? "Talk stoppen" : "Talk starten";
  voiceToggleBtn.setAttribute("aria-label", running ? "Talk stoppen" : "Talk starten");
  voiceToggleBtn.disabled = !plVoiceAvailable;
}

async function plInitVoiceAvailability() {
  plVoiceAvailable = false;
  plSetVoiceStatus("Voice: pruefe Verfuegbarkeit...");
  try {
    const data = await plGet(`/api/voice/realtime/${SESSION_ID}/status`);
    const enabled = Boolean(data && data.enabled);
    const hasApiKey = Boolean(data && data.has_api_key);
    const mode = (data && data.mode) || "realtime-manual";
    const hasAgentId = Boolean(data && data.has_agent_id);
    plVoiceMode = mode;
    plVoiceAvailable = enabled && hasApiKey && (mode !== "voice-agent" || hasAgentId);
    if (!enabled) {
      plSetVoiceStatus("Voice: deaktiviert (Server)");
    } else if (!hasApiKey) {
      plSetVoiceStatus("Voice: kein API-Key konfiguriert");
    } else if (mode === "voice-agent" && !hasAgentId) {
      plSetVoiceStatus("Voice: Agent-ID fehlt");
    } else {
      plSetVoiceStatus(mode === "voice-agent" ? "Voice: bereit (Agent)" : "Voice: bereit");
    }
  } catch (err) {
    plVoiceAvailable = false;
    plSetVoiceStatus(`Voice: Statusfehler (${String(err)})`);
  }
  plSyncVoiceToggleUi();
}

function plPcm16ToBase64(float32Array) {
  const int16 = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i += 1) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    int16[i] = s < 0 ? s * 32768 : s * 32767;
  }
  const bytes = new Uint8Array(int16.buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function plBase64ToFloat32Pcm16(base64) {
  const binary = atob(base64);
  const length = binary.length;
  const bytes = new Uint8Array(length);
  for (let i = 0; i < length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  const int16 = new Int16Array(bytes.buffer);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i += 1) {
    float32[i] = int16[i] / 32768;
  }
  return float32;
}

function plQueueVoiceAudioPcm(base64Pcm, sampleRate = 24000) {
  if (!plVoiceAudioCtx) return;
  const pcm = plBase64ToFloat32Pcm16(base64Pcm);
  const buffer = plVoiceAudioCtx.createBuffer(1, pcm.length, sampleRate);
  buffer.copyToChannel(pcm, 0);
  const source = plVoiceAudioCtx.createBufferSource();
  source.buffer = buffer;
  source.connect(plVoiceAudioCtx.destination);
  const now = plVoiceAudioCtx.currentTime;
  if (plVoicePlayCursor < now) plVoicePlayCursor = now;
  source.start(plVoicePlayCursor);
  plVoicePlayCursor += buffer.duration;
}

async function plStartVoiceMode() {
  if (!SESSION_ID) return;
  if (!plVoiceAvailable) {
    plSetVoiceStatus("Voice: nicht verfuegbar");
    plSyncVoiceToggleUi();
    return;
  }
  if (plVoiceSocket && (plVoiceSocket.readyState === WebSocket.OPEN || plVoiceSocket.readyState === WebSocket.CONNECTING)) {
    return;
  }

  plSetVoiceStatus("Voice: initialisiere...");
  if (voiceToggleBtn) voiceToggleBtn.disabled = true;

  try {
    const hasGetUserMedia = Boolean(
      typeof navigator !== "undefined" &&
      navigator.mediaDevices &&
      typeof navigator.mediaDevices.getUserMedia === "function"
    );
    if (!hasGetUserMedia) {
      const secureHint = (typeof window !== "undefined" && !window.isSecureContext)
        ? " (nur in HTTPS oder localhost verfuegbar)"
        : "";
      throw new Error(`Mikrofon-API nicht verfuegbar${secureHint}`);
    }

    const bootstrapResp = await fetch(`/api/voice/realtime/${SESSION_ID}/client-secret`, { method: "POST" });
    const bootstrap = await bootstrapResp.json();
    if (!bootstrapResp.ok) {
      throw new Error(bootstrap.detail || bootstrap.error || bootstrapResp.statusText);
    }

    const secret =
      bootstrap?.client_secret?.value ||
      bootstrap?.client_secret?.secret ||
      bootstrap?.client_secret?.token ||
      bootstrap?.client_secret?.client_secret?.value ||
      bootstrap?.client_secret?.client_secret?.secret ||
      bootstrap?.client_secret?.client_secret?.token;
    if (!secret) {
      throw new Error("Kein Ephemeral-Token erhalten");
    }

    const wsUrl = bootstrap.ws_url || "wss://api.x.ai/v1/realtime";
    plVoiceSocket = new WebSocket(wsUrl, [`xai-client-secret.${secret}`]);
    plVoiceSessionReady = false;

    plVoiceAudioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
    await plVoiceAudioCtx.resume();
    plVoicePlayCursor = plVoiceAudioCtx.currentTime;

    plVoiceMicStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const source = plVoiceAudioCtx.createMediaStreamSource(plVoiceMicStream);
    plVoiceProcessor = plVoiceAudioCtx.createScriptProcessor(4096, 1, 1);
    source.connect(plVoiceProcessor);
    plVoiceProcessor.connect(plVoiceAudioCtx.destination);

    plVoiceProcessor.onaudioprocess = (event) => {
      if (!plVoiceSessionReady || !plVoiceSocket || plVoiceSocket.readyState !== WebSocket.OPEN) return;
      const channel = event.inputBuffer.getChannelData(0);
      const chunk = new Float32Array(channel.length);
      chunk.set(channel);
      const base64 = plPcm16ToBase64(chunk);
      plVoiceSocket.send(JSON.stringify({ type: "input_audio_buffer.append", audio: base64 }));
    };

    plVoiceSocket.onopen = () => {
      plSetVoiceStatus("Voice: verbunden");
      if (bootstrap.session_update) {
        plVoiceSocket?.send(JSON.stringify(bootstrap.session_update));
      } else {
        plVoiceSessionReady = true;
        plSetVoiceStatus("Voice: bereit (Agent)");
      }
      plSyncVoiceToggleUi();
    };

    plVoiceSocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "session.updated") {
          plVoiceSessionReady = true;
          plSetVoiceStatus("Voice: bereit");
          plSyncVoiceToggleUi();
          return;
        }
        if (data.type === "conversation.item.input_audio_transcription.completed" && data.transcript) {
          if (chatTimeline) {
            chatTimeline.innerHTML += `\n<div class="chat-bubble from-user"><div class="bubble-body">${String(data.transcript).replace(/</g, "&lt;")}</div><div class="bubble-meta">${PLAYER_NAME} · Voice</div></div>`;
            chatTimeline.scrollTop = chatTimeline.scrollHeight;
          }
          return;
        }
        if (data.type === "response.output_audio.delta" && data.delta) {
          plQueueVoiceAudioPcm(data.delta, 24000);
          return;
        }
        if (data.type === "response.output_audio_transcript.delta" && data.delta) {
          plWrite("Voice Transcript", { delta: data.delta });
          return;
        }
      } catch (_) {}
    };

    plVoiceSocket.onerror = () => {
      plSetVoiceStatus("Voice: Fehler");
    };

    plVoiceSocket.onclose = () => {
      plSetVoiceStatus("Voice: getrennt");
      plVoiceSessionReady = false;
      plVoiceSocket = null;
      plSyncVoiceToggleUi();
    };
  } catch (err) {
    const errMsg = String(err);
    plSetVoiceStatus(`Voice: Fehler (${errMsg})`);
    plWrite("Voice Start Fehler", { error: errMsg });
    await plStopVoiceMode({ preserveStatus: true });
  } finally {
    plSyncVoiceToggleUi();
  }
}

async function plStopVoiceMode(options = {}) {
  const preserveStatus = Boolean(options.preserveStatus);
  if (plVoiceProcessor) {
    try { plVoiceProcessor.disconnect(); } catch (_) {}
    plVoiceProcessor.onaudioprocess = null;
    plVoiceProcessor = null;
  }
  if (plVoiceMicStream) {
    plVoiceMicStream.getTracks().forEach((track) => {
      try { track.stop(); } catch (_) {}
    });
    plVoiceMicStream = null;
  }
  if (plVoiceSocket) {
    try { plVoiceSocket.close(); } catch (_) {}
    plVoiceSocket = null;
  }
  if (plVoiceAudioCtx) {
    try { await plVoiceAudioCtx.close(); } catch (_) {}
    plVoiceAudioCtx = null;
  }
  plVoiceSessionReady = false;
  if (!preserveStatus) plSetVoiceStatus("Voice: aus");
  plSyncVoiceToggleUi();
}

async function plToggleVoiceMode() {
  if (plIsVoiceRunning()) {
    await plStopVoiceMode();
    return;
  }
  await plStartVoiceMode();
}

// -- Attach-image state --
let plAttachedFile = null; // File | null

function plSetAttachedFile(file) {
  plAttachedFile = file;
  const preview = document.getElementById("play-attach-preview");
  const attachBtn = document.getElementById("play-attach");
  if (file) {
    const kind = String(file.type || "").startsWith("audio/") ? "🎵" : "📎";
    preview.textContent = `${kind} ${file.name}`;
    preview.style.display = "block";
    if (attachBtn) attachBtn.classList.add("has-attachment");
  } else {
    preview.textContent = "";
    preview.style.display = "none";
    if (attachBtn) attachBtn.classList.remove("has-attachment");
  }
}

function plRenderHygieneQuota(quotaData) {
  const el = document.getElementById("psd-hygiene-quota");
  const nextEl = document.getElementById("psd-hygiene-next-allowed");
  if (!el || !quotaData) return;

  const limits = quotaData.limits || {};
  const used = quotaData.used || {};
  const remaining = quotaData.remaining || {};
  const nextAllowedAt = quotaData.next_allowed_at || {};
  const fmt = (v) => (v === null || v === undefined ? "unbegrenzt" : String(v));

  el.textContent =
    `Kontingent - Tag: ${fmt(used.daily)}/${fmt(limits.daily)} (rest ${fmt(remaining.daily)}), ` +
    `Woche: ${fmt(used.weekly)}/${fmt(limits.weekly)} (rest ${fmt(remaining.weekly)}), ` +
    `Monat: ${fmt(used.monthly)}/${fmt(limits.monthly)} (rest ${fmt(remaining.monthly)})`;

  if (!nextEl) return;

  // Show next reset times for all limited periods, not just when exhausted
  function fmtNextReset(isoStr, label) {
    if (!isoStr) return null;
    try {
      const diff = new Date(isoStr).getTime() - Date.now();
      if (diff <= 0) return null;
      const d = Math.floor(diff / 86400000);
      const h = Math.floor((diff % 86400000) / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      let countdown = d > 0 ? `${d}T ${h}h ${m}m` : h > 0 ? `${h}h ${m}m` : `${m}m`;
      const dateStr = new Date(isoStr).toLocaleString("de-DE", {
        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit"
      });
      return `${label}: ${dateStr} (in ${countdown})`;
    } catch (_) { return null; }
  }

  const overallIso = nextAllowedAt.overall;
  if (overallIso) {
    // Quota exhausted — show when next opening is allowed
    const formatted = fmtNextReset(overallIso, "Nächste Öffnung erlaubt ab");
    if (formatted) {
      nextEl.textContent = formatted;
      nextEl.style.color = "var(--color-warn, #ffb300)";
      return;
    }
  }

  // Quota not exhausted — show when periods reset for limited quotas
  const nextPeriodStart = quotaData.next_period_start || {};
  const resetLines = [];
  if (nextPeriodStart.daily) {
    const r = fmtNextReset(nextPeriodStart.daily, "Tageslimit setzt zurück");
    if (r) resetLines.push(r);
  }
  if (nextPeriodStart.weekly) {
    const r = fmtNextReset(nextPeriodStart.weekly, "Wochenlimit setzt zurück");
    if (r) resetLines.push(r);
  }
  if (nextPeriodStart.monthly) {
    const r = fmtNextReset(nextPeriodStart.monthly, "Monatslimit setzt zurück");
    if (r) resetLines.push(r);
  }
  if (resetLines.length > 0) {
    nextEl.textContent = resetLines.join(" · ");
    nextEl.style.color = "";
  } else {
    nextEl.textContent = "";
  }
}

async function plLoadHygieneQuota() {
  if (!SESSION_ID) return;
  try {
    const data = await plGet(`/api/sessions/${SESSION_ID}/hygiene/quota`);
    plRenderHygieneQuota(data);
  } catch (err) {
    const el = document.getElementById("psd-hygiene-quota");
    if (el) el.textContent = `Kontingent konnte nicht geladen werden (${String(err)}).`;
  }
}

function plFormatMessageTime(value) {
  if (!value) return "";
  const raw = String(value).trim();
  if (!raw) return "";

  // Backends often return naive timestamps; interpret them as UTC to avoid shifted local display.
  const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(raw) ? raw : `${raw.replace(" ", "T")}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
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

function plFormatPromptMeta(item) {
  if (!item || item.role !== "assistant" || !item.prompt_version) return "";
  return `Prompt ${item.prompt_version}`;
}

function plFormatSpeakerName(item) {
  if (item && item.speaker_name) return String(item.speaker_name);
  const role = String(item?.role || "system").toLowerCase();
  if (role === "assistant") return PERSONA_NAME;
  if (role === "user") return PLAYER_NAME;
  return "System";
}

function plRenderRoleplayState(roleplayState, relationshipMemory = {}) {
  const relationship = roleplayState?.relationship || {};
  const protocol = roleplayState?.protocol || {};
  const scene = roleplayState?.scene || {};
  const sceneTitleRaw = String(scene.title || "").trim();
  const sceneHeading = sceneTitleRaw || "Einstimmung";
  const growthBaseline = {
    trust: 55,
    obedience: 50,
    resistance: 20,
    favor: 40,
    strictness: 68,
    frustration: 18,
    attachment: 46,
  };

  const setText = (id, value, fallback = "—") => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(value || fallback);
  };
  const setHtml = (id, html, fallback = "—") => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = html || fallback;
  };
  const nextPhase = (score, key) => {
    const safe = Math.max(0, Math.min(100, Number(score) || 0));
    if (key === "resistance") {
      const targets = [15, 10, 5, 0];
      const target = targets.find((item) => safe > item);
      if (target == null) return { label: "Naechste Phase: erreicht", target: null };
      return { label: `Naechste Phase: ${target} (${safe - target} Punkte weniger)`, target };
    }
    const targets = [60, 70, 80, 90, 100];
    const target = targets.find((item) => safe < item);
    if (!target) return { label: "Naechste Phase: erreicht", target: null };
    return { label: `Naechste Phase: ${target} (${target - safe} Punkte)`, target };
  };
  const metric = (label, value, key) => {
    const num = Number(value);
    const safe = Number.isFinite(num) ? Math.max(0, Math.min(100, num)) : 0;
    const baseline = Number(growthBaseline[key]);
    const baseSafe = Math.max(0, Math.min(100, Number.isFinite(baseline) ? baseline : 0));
    const delta = Number.isFinite(baseline) ? safe - baseline : 0;
    const deltaText = delta > 0 ? `+${delta}` : `${delta}`;
    const deltaClass = delta > 0 ? "is-up" : (delta < 0 ? "is-down" : "is-flat");
    const resistanceClass = key === "resistance" ? " is-resistance" : "";
    const phase = nextPhase(safe, key);
    const baseWidth = Math.min(safe, baseSafe);
    const growthWidth = Math.max(0, safe - baseSafe);
    const targetMarker = Number.isFinite(Number(phase.target)) ? Math.max(0, Math.min(100, Number(phase.target))) : null;
    return `
      <div class="roleplay-meter">
        <div class="roleplay-meter-top">
          <span>${plEscapeHtml(label)}</span>
          <strong>${safe}</strong>
        </div>
        <div class="roleplay-meter-track">
          <span class="roleplay-meter-fill roleplay-meter-fill--base" style="width:${baseWidth}%"></span>
          ${growthWidth > 0 ? `<span class="roleplay-meter-fill roleplay-meter-fill--growth" style="left:${baseWidth}%;width:${growthWidth}%"></span>` : ""}
          ${targetMarker != null ? `<span class="roleplay-meter-target" style="left:${targetMarker}%"></span>` : ""}
        </div>
        <div class="roleplay-meter-meta">
          <span class="roleplay-meter-delta ${deltaClass}${resistanceClass}">Seit Start: ${deltaText}</span>
          <span class="roleplay-meter-phase">${plEscapeHtml(phase.label)}</span>
        </div>
      </div>
    `;
  };
  const pillList = (items, emptyText) => {
    const list = Array.isArray(items) ? items.filter(Boolean) : [];
    if (!list.length) return `<span class="roleplay-empty">${plEscapeHtml(emptyText)}</span>`;
    return list.map((item) => `<span class="roleplay-pill">${plEscapeHtml(item)}</span>`).join("");
  };

  setText("play-scene-pressure", scene.pressure || "—");
  setText("play-scene-title", sceneHeading);
  setText("play-scene-objective", scene.objective || "—");
  setText("play-scene-next-beat", scene.next_beat || "—");
  setText("play-scene-consequence", scene.last_consequence || "keine");
  setText("play-control-level", relationship.control_level || "structured");
  setText("play-roleplay-scene-mini", sceneHeading);
  setText("play-roleplay-mini-chip", relationship.control_level || scene.pressure || "Status");

  setHtml(
    "play-relationship-meters",
    [
      ["Trust", "trust"],
      ["Obedience", "obedience"],
      ["Resistance", "resistance"],
      ["Favor", "favor"],
      ["Strictness", "strictness"],
      ["Frustration", "frustration"],
      ["Attachment", "attachment"],
    ].map(([label, key]) => metric(label, relationship[key], key)).join("")
  );
  setHtml("play-active-rules", pillList(protocol.active_rules, "Keine aktiven Regeln"));
  setHtml("play-open-orders", pillList(protocol.open_orders, "Keine offenen Anweisungen"));
  const sessionsConsidered = Number(relationshipMemory?.sessions_considered || 0);
  setText("play-memory-count", sessionsConsidered);
  setText("play-memory-control", relationshipMemory?.dominant_control_level || "noch offen");
  setText(
    "play-memory-summary",
    sessionsConsidered > 0
      ? relationshipMemory?.summary || "Langzeitdynamik verfuegbar."
      : "Noch keine abgeschlossenen Vergleichssessions."
  );
  setHtml(
    "play-memory-highlights",
    pillList(
      relationshipMemory?.highlights,
      sessionsConsidered > 0 ? "Noch keine markante Tendenz" : "Keine Langzeitdaten"
    )
  );
}

function plRenderOperationalState(items) {
  const warnings = Array.isArray(items)
    ? items.filter((item) => String(item?.message_type || "") === "system_warning" && String(item?.content || "").trim())
    : [];
  const latestWarning = warnings.length ? warnings[warnings.length - 1] : null;
  const warningText = latestWarning ? String(latestWarning.content || "").trim() : "";
  if (opsBannerEl) {
    if (warningText) {
      opsBannerEl.textContent = warningText;
      opsBannerEl.classList.remove("is-hidden");
    } else {
      opsBannerEl.textContent = "";
      opsBannerEl.classList.add("is-hidden");
    }
  }
  if (statusPillEl) {
    statusPillEl.classList.toggle("is-degraded", Boolean(warningText));
  }
}

// -- Render chat --
function plRenderChat(items) {
  if (!chatTimeline) return;
  _lastMessageItems = Array.isArray(items) ? items : [];
  plRenderOperationalState(_lastMessageItems);
  if (!_lastMessageItems.length) {
    chatTimeline.innerHTML = "<p>Noch keine Nachrichten.</p>";
    plInstallInlineTaskCards();
    return;
  }
  chatTimeline.innerHTML = _lastMessageItems
    .slice(-80)
    .map((item) => {
      const role = item.role || "system";
      const cssRole = role === "user" ? "from-user" : "from-ai";
      const content = plRenderMessageHtml(item.content || "");
      const ts = plFormatMessageTime(item.created_at);
      const promptMeta = plFormatPromptMeta(item);
      const speakerName = plFormatSpeakerName(item);
      // Store task IDs on task_assigned bubbles so cards can be injected inline
      let taskAttr = "";
      if (item.message_type === "task_assigned") {
        const ids = (item.content || "").match(/\d+/g) || [];
        taskAttr = ` data-msg-type="task_assigned" data-task-ids="${ids.join(",")}"`;
      }
      const avatarHtml = (cssRole === "from-ai" && _personaAvatarUrl)
        ? `<img class="bubble-avatar" src="${_personaAvatarUrl}" alt="" aria-hidden="true" />`
        : "";
      const bodyRow = avatarHtml
        ? `<div class="bubble-row">${avatarHtml}<div class="bubble-body">${content}</div></div>`
        : `<div class="bubble-body">${content}</div>`;
      return `
        <div class="chat-bubble ${cssRole}"${taskAttr}>
          ${bodyRow}
          <div class="bubble-meta">${speakerName}${ts ? " · " + ts : ""}${promptMeta ? " · " + promptMeta : ""}</div>
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
      return `<div class="task-card"><div class="task-card-title">${icon} <span class="task-num">#${item.id}</span> ${title}</div></div>`;
    })
    .join("");
}

// Build a single action card HTML string
function plFmtDeadline(deadlineAt) {
  if (!deadlineAt) return "";
  try {
    const d = new Date(deadlineAt);
    const now = new Date();
    const diffMs = d - now;
    if (diffMs < 0) return `<span class="ac-deadline ac-deadline--overdue">&#9201; &uuml;berf&auml;llig</span>`;
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 60) return `<span class="ac-deadline ac-deadline--soon">&#9201; noch ${diffMin}&nbsp;Min</span>`;
    const sameDay = d.toDateString() === now.toDateString();
    const time = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    if (sameDay) return `<span class="ac-deadline">&#9201; heute ${time}</span>`;
    const date = d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
    return `<span class="ac-deadline">&#9201; ${date}&nbsp;${time}</span>`;
  } catch (_) { return ""; }
}

function plBuildSingleActionCard(item) {
  const title = String(item.title || "").replace(/</g, "&lt;");
  const criteria = String(item.verification_criteria || "").replace(/"/g, "&quot;");
  const isVerify = !!item.requires_verification;
  const criteriaHtml =
    isVerify && item.verification_criteria
      ? `<p class="ac-hint">&#128203; ${String(item.verification_criteria).replace(/</g, "&lt;")}</p>`
      : "";
  const actions = isVerify
    ? `<button class="ac-btn ac-btn--photo" data-action="verify">&#128247; Fotoverifikation</button>
       <button class="ac-btn ac-btn--fail" data-action="fail">&#10007; Fail</button>`
    : `<button class="ac-btn ac-btn--done" data-action="complete">&#10003; Best&auml;tigung</button>
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
        <div class="ac-header-row">
          <span class="ac-label">${isVerify ? "&#128247; Verifikation" : "&#128203; Task"}</span>
          <span class="ac-num">#${item.id}</span>
          ${plFmtDeadline(item.deadline_at)}
        </div>
        <div class="ac-title">${title}</div>
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

  // Header dropdown – interactive action cards
  if (taskDropBoard) {
    if (pending.length) {
      taskDropBoard.innerHTML = pending.map(plBuildSingleActionCard).join("");
      plAttachActionCardHandlers(taskDropBoard);
    } else {
      taskDropBoard.innerHTML = "<p>Keine offenen Tasks.</p>";
    }
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

async function plLoadSessionState() {
  if (!SESSION_ID) return;
  try {
    const data = await plGet(`/api/sessions/${SESSION_ID}`);
    if (statusPillEl) statusPillEl.textContent = data.status || "—";
    plRenderRoleplayState(data.roleplay_state || {}, data.relationship_memory || {});
  } catch (err) {
    plWrite("Fehler Roleplay-State", { error: String(err) });
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
        await plLoadSessionState();
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
      const resp = await fetch(`/api/sessions/${SESSION_ID}/messages/media`, {
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
    await plLoadSessionState();
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

document.getElementById("play-connect-ws")?.addEventListener("click", plConnectWs);
document.getElementById("play-voice-toggle")?.addEventListener("click", plToggleVoiceMode);

document.getElementById("play-resume-session")?.addEventListener("click", async () => {
  if (!SESSION_ID) return;
  const btn = document.getElementById("play-resume-session");
  btn.disabled = true;
  try {
    const data = await plPost(`/api/sessions/${SESSION_ID}/safety/resume`, {});
    if (statusPillEl) statusPillEl.textContent = data.status;
    btn.remove(); // hide button once active again
    plWrite("Session reaktiviert", data);
  } catch (err) {
    plWrite("Fehler Reaktivierung", { error: String(err) });
    btn.disabled = false;
  }
});

// -- Roleplay dropdown toggle --
const roleplayToggle = document.getElementById("play-roleplay-toggle");
const roleplayDropdown = document.getElementById("play-roleplay-dropdown");
const roleplayMenu = document.getElementById("play-roleplay-menu");

function closeRoleplayDropdown() {
  roleplayDropdown?.classList.remove("is-open");
  roleplayMenu?.classList.remove("is-open-mobile");
  roleplayToggle?.setAttribute("aria-expanded", "false");
}

roleplayToggle?.addEventListener("click", (e) => {
  e.stopPropagation();
  const open = roleplayDropdown.classList.toggle("is-open");
  if (window.innerWidth <= 820) {
    roleplayMenu?.classList.toggle("is-open-mobile", open);
  }
  roleplayToggle.setAttribute("aria-expanded", String(open));
});

document.addEventListener("click", (e) => {
  if (!e.target.closest("#play-roleplay-menu")) closeRoleplayDropdown();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeRoleplayDropdown();
  }
});

// -- Tasks dropdown toggle --
const tasksDropdown = document.getElementById("play-tasks-dropdown");
const tasksMenu = document.getElementById("play-tasks-menu");

function closeTasksDropdown() {
  tasksDropdown?.classList.remove("is-open");
  tasksMenu?.classList.remove("is-open-mobile");
  document.getElementById("play-tasks-toggle")?.setAttribute("aria-expanded", "false");
}

document.getElementById("play-tasks-toggle")?.addEventListener("click", (e) => {
  e.stopPropagation();
  const open = tasksDropdown.classList.toggle("is-open");
  if (window.innerWidth <= 820) {
    tasksMenu?.classList.toggle("is-open-mobile", open);
  }
  document.getElementById("play-tasks-toggle").setAttribute("aria-expanded", String(open));
});

document.addEventListener("click", (e) => {
  if (!e.target.closest("#play-tasks-menu")) closeTasksDropdown();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeTasksDropdown();
  }
});

// -- Safety dropdown toggle --
const safetyToggle = document.getElementById("play-safety-toggle");
const safetyDropdown = document.getElementById("play-safety-dropdown");
const safetyMenu = document.getElementById("play-safety-menu");

function closeSafetyDropdown() {
  safetyDropdown?.classList.remove("is-open");
  safetyMenu?.classList.remove("is-open-mobile");
  safetyToggle?.setAttribute("aria-expanded", "false");
}

safetyToggle?.addEventListener("click", (e) => {
  e.stopPropagation();
  const open = safetyDropdown.classList.toggle("is-open");
  if (window.innerWidth <= 820) {
    safetyMenu?.classList.toggle("is-open-mobile", open);
  }
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
let plHygieneConfiguredDurationSeconds = 900;

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
    let oldSealNumber = null;
    try {
      const sealData = await plGet(`/api/sessions/${SESSION_ID}/seal-history`);
      const active = (sealData.entries || []).find((s) => s.status === "active");
      if (active) oldSealNumber = active.seal_number;
    } catch (_) {}
    plHygieneUsesSeal = !!oldSealNumber;
    const data = await plPost(`/api/sessions/${SESSION_ID}/hygiene/openings`, {
      duration_seconds: Math.max(60, Math.round(Number(plHygieneConfiguredDurationSeconds) || 900)),
      old_seal_number: oldSealNumber,
    });
    plHygieneOpeningId = data.opening_id;
    if (statusEl) { statusEl.textContent = `⏱️ Rück bis: ${new Date(data.due_back_at).toLocaleTimeString("de-DE")}`; statusEl.style.color = "var(--color-warn,#ffb300)"; }
    plRenderHygieneQuota(data.quota);
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
    await plLoadHygieneQuota();
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
  await plInitVoiceAvailability();
  // Pre-load persona avatar for chat rendering
  try {
    const summary = await plGet(`/api/settings/summary?session_id=${SESSION_ID}`);
    _personaAvatarUrl = summary?.session?.persona_avatar_url || null;
  } catch (_) {}
  await plLoadSessionState();
  await plLoadChat();
  await plListTasks();
  await plLoadVerifications();
  await plLoadHygieneQuota();
  setInterval(() => {
    plLoadSessionState().catch(() => {});
  }, 8000);
  plConnectWs();
});
