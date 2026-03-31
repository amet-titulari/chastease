/* play.js – Play Mode (v0.5.0) */
"use strict";

// -- State from server-rendered dataset --
const _shell = document.querySelector(".play-shell");
const SESSION_ID = Number(_shell?.dataset.sessionId || 0);
const WS_TOKEN = _shell?.dataset.wsToken || "";
const LOCK_END = _shell?.dataset.lockEnd || "";
const PERSONA_NAME = _shell?.dataset.personaName || "Keyholderin";
const PLAYER_NAME = _shell?.dataset.playerName || "Du";
const APP_VERSION = _shell?.dataset.appVersion || "0.5.0";
const FOCUS_STORAGE_KEY = `chastease.play.focus.${SESSION_ID || "default"}.${APP_VERSION}`;
const plLovenseEnabled = String(_shell?.dataset.lovenseEnabled || "") === "1";
const plLovenseConfigured = String(_shell?.dataset.lovenseConfigured || "") === "1";
const plLovensePlatform = String(_shell?.dataset.lovensePlatform || "").trim();
const plLovenseAppType = String(_shell?.dataset.lovenseAppType || "connect").trim() || "connect";
const plLovenseDebug = String(_shell?.dataset.lovenseDebug || "") === "1";
const plLovenseSimulator = String(_shell?.dataset.lovenseSimulator || "") === "1";
const PL_LOVENSE_AUTO_INIT_KEY = `chastease.lovense.auto_init.${SESSION_ID || "default"}`;
const PL_LOVENSE_TOY_KEY = `chastease.lovense.toy.${SESSION_ID || "default"}`;

let plSocket = null;
let _personaAvatarUrl = null;
let plLovenseSdk = null;
let plLovenseBootstrap = null;
let plLovenseToys = [];
let plLovensePollHandle = null;
let plLovenseSequenceTimeout = null;
let plLovensePlanQueue = [];
let plLovensePlanRunning = false;
let plLovensePlanRunId = 0;
let plLovensePlanTitle = "";
let plLovensePlanTotal = 0;
let plLovensePlanCurrentIndex = 0;
let plLovensePlanCurrentCommand = "";
let plLovensePresetLibrary = { builtin: [], wearer: [], persona: [], combined: [] };
const plHandledClientActionKeys = new Set();
let plLovenseController = null;

const PL_LOVENSE_PRESETS = {
  tease_ramp: { interval: 220, pattern: (intensity) => {
    const level = Math.max(1, Math.min(20, intensity));
    const low = Math.max(1, Math.round(level * 0.35));
    const mid = Math.max(1, Math.round(level * 0.6));
    const high = Math.max(1, Math.round(level * 0.85));
    return `${low};${mid};${high};${level};${high};${mid}`;
  } },
  strict_pulse: { interval: 160, pattern: (intensity) => {
    const level = Math.max(1, Math.min(20, intensity));
    return `0;${level};0;${level};0;${Math.max(1, Math.round(level * 0.75))}`;
  } },
  wave_ladder: { interval: 210, pattern: (intensity) => {
    const level = Math.max(1, Math.min(20, intensity));
    const one = Math.max(1, Math.round(level * 0.3));
    const two = Math.max(1, Math.round(level * 0.5));
    const three = Math.max(1, Math.round(level * 0.7));
    return `${one};${two};${three};${level};${three};${two};${one};0`;
  } },
  deny_spikes: { interval: 150, pattern: (intensity) => {
    const level = Math.max(1, Math.min(20, intensity));
    const spike = Math.max(1, Math.round(level * 0.9));
    const low = Math.max(1, Math.round(level * 0.25));
    return `${low};${spike};0;${low};${level};0;${spike};0`;
  } },
};

// -- DOM refs --
const statusPillEl = document.getElementById("play-status-pill");
const chatTimeline = document.getElementById("play-chat-timeline");
const opsBannerEl = document.getElementById("play-ops-banner");
const chatInput = document.getElementById("play-chat-input");
const debugOut = document.getElementById("play-output");
const wsBtn = document.getElementById("play-connect-ws");
const voiceStatusEl = document.getElementById("play-voice-status");
const voiceToggleBtn = document.getElementById("play-voice-toggle");
const focusToggleBtn = document.getElementById("play-focus-toggle");
const plRuntime = window.ChasteaseUiRuntime || {};
const lovenseConsoleEl = document.getElementById("play-lovense-console");
const lovenseCompactStatusEl = document.getElementById("play-lovense-compact-status");
const lovenseStatusEl = document.getElementById("play-lovense-status");
const lovenseToyEl = document.getElementById("play-lovense-toy");
const lovensePlanModeEl = document.getElementById("play-lovense-plan-mode");
const lovensePlanTitleEl = document.getElementById("play-lovense-plan-title");
const lovensePlanStepEl = document.getElementById("play-lovense-plan-step");
const lovensePlanCommandEl = document.getElementById("play-lovense-plan-command");
const lovenseNextStepEl = document.getElementById("play-lovense-next-step");

const plVoiceState = {
  socket: null,
  audioCtx: null,
  micStream: null,
  processor: null,
  sessionReady: false,
  playCursor: 0,
  available: false,
  mode: "realtime-manual",
};

let plLovensePlanState = "idle";
const plLovenseUiState = {
  planState: "idle",
  statusText: "Lovense: pruefe Verfuegbarkeit...",
  statusTone: "neutral",
  toyLabel: "Kein Toy verbunden",
  currentLabel: "",
};

function plSetLovenseStatus(text) {
  const lovenseUi = window.ChasteasePlayLovenseUI || {};
  if (typeof lovenseUi.setStatus === "function") {
    lovenseUi.setStatus({
      state: plLovenseUiState,
      text,
      hasToy: plLovenseToys.length > 0,
      queue: plLovensePlanQueue,
      planTitle: plLovensePlanTitle,
      planTotal: plLovensePlanTotal,
      planCurrentIndex: plLovensePlanCurrentIndex,
      refs: {
        consoleEl: lovenseConsoleEl,
        compactStatusEl: lovenseCompactStatusEl,
        statusEl: lovenseStatusEl,
        toyEl: lovenseToyEl,
        planModeEl: lovensePlanModeEl,
        planTitleEl: lovensePlanTitleEl,
        planStepEl: lovensePlanStepEl,
        planCommandEl: lovensePlanCommandEl,
        nextStepEl: lovenseNextStepEl,
      },
    });
  }
}

function plRememberLovenseAutoInit() {
  try {
    window.sessionStorage.setItem(PL_LOVENSE_AUTO_INIT_KEY, "1");
  } catch (_) {}
}

function plShouldAutoInitLovense() {
  try {
    return window.sessionStorage.getItem(PL_LOVENSE_AUTO_INIT_KEY) === "1";
  } catch (_) {
    return false;
  }
}

function plRememberSelectedToyId(toyId) {
  if (!toyId) return;
  try {
    window.sessionStorage.setItem(PL_LOVENSE_TOY_KEY, String(toyId));
  } catch (_) {}
}

function plRestoreSelectedToyId() {
  try {
    return String(window.sessionStorage.getItem(PL_LOVENSE_TOY_KEY) || "").trim();
  } catch (_) {
    return "";
  }
}

function plDescribeLovenseStep(step) {
  const lovenseUi = window.ChasteasePlayLovenseUI || {};
  if (typeof lovenseUi.describeStep === "function") {
    return lovenseUi.describeStep(step);
  }
  return "nichts geplant";
}

function plRenderLovenseConsole() {
  const lovenseUi = window.ChasteasePlayLovenseUI || {};
  if (typeof lovenseUi.renderConsole === "function") {
    lovenseUi.renderConsole({
      state: plLovenseUiState,
      hasToy: plLovenseToys.length > 0,
      queue: plLovensePlanQueue,
      planTitle: plLovensePlanTitle,
      planTotal: plLovensePlanTotal,
      planCurrentIndex: plLovensePlanCurrentIndex,
      refs: {
        consoleEl: lovenseConsoleEl,
        compactStatusEl: lovenseCompactStatusEl,
        toyEl: lovenseToyEl,
        planModeEl: lovensePlanModeEl,
        planTitleEl: lovensePlanTitleEl,
        planStepEl: lovensePlanStepEl,
        planCommandEl: lovensePlanCommandEl,
        nextStepEl: lovenseNextStepEl,
      },
    });
  }
}

function plRenderLovensePlanStatus(options = {}) {
  plLovensePlanState = String(options.state || "").trim().toLowerCase() || "idle";
  plLovensePlanTitle = String(options.title || "").trim() || "Session-Plan";
  plLovensePlanTotal = Math.max(0, Number(options.total) || 0);
  plLovensePlanCurrentIndex = Math.max(0, Number(options.current) || 0);
  plLovenseUiState.planState = plLovensePlanState;
  const lovenseUi = window.ChasteasePlayLovenseUI || {};
  if (typeof lovenseUi.renderPlanStatus === "function") {
    lovenseUi.renderPlanStatus({
      state: plLovenseUiState,
      planState: plLovensePlanState,
      planTitle: plLovensePlanTitle,
      planTotal: plLovensePlanTotal,
      planCurrentIndex: plLovensePlanCurrentIndex,
      command: options.command,
      hasToy: plLovenseToys.length > 0,
      queue: plLovensePlanQueue,
      refs: {
        consoleEl: lovenseConsoleEl,
        compactStatusEl: lovenseCompactStatusEl,
        toyEl: lovenseToyEl,
        planModeEl: lovensePlanModeEl,
        planTitleEl: lovensePlanTitleEl,
        planStepEl: lovensePlanStepEl,
        planCommandEl: lovensePlanCommandEl,
        nextStepEl: lovenseNextStepEl,
      },
    });
  }
}

function plResetLovensePlanStatus() {
  plLovensePlanTotal = 0;
  plLovensePlanCurrentIndex = 0;
  plLovensePlanCurrentCommand = "";
  const lovenseUi = window.ChasteasePlayLovenseUI || {};
  if (typeof lovenseUi.resetPlanStatus === "function") {
    lovenseUi.resetPlanStatus({
      state: plLovenseUiState,
      hasToy: plLovenseToys.length > 0,
      queue: plLovensePlanQueue,
      refs: {
        consoleEl: lovenseConsoleEl,
        compactStatusEl: lovenseCompactStatusEl,
        toyEl: lovenseToyEl,
        planModeEl: lovensePlanModeEl,
        planTitleEl: lovensePlanTitleEl,
        planStepEl: lovensePlanStepEl,
        planCommandEl: lovensePlanCommandEl,
        nextStepEl: lovenseNextStepEl,
      },
    });
  }
  plLovensePlanState = "idle";
}

function plSetLovensePlanQueued(title, total) {
  plLovensePlanTitle = String(title || "").trim();
  plLovensePlanTotal = Math.max(0, Number(total) || 0);
  plLovensePlanCurrentIndex = 0;
  plLovensePlanCurrentCommand = "";
  const lovenseUi = window.ChasteasePlayLovenseUI || {};
  if (typeof lovenseUi.setPlanQueued === "function") {
    lovenseUi.setPlanQueued({
      state: plLovenseUiState,
      planTitle: plLovensePlanTitle || "Session-Plan",
      planTotal: plLovensePlanTotal,
      planCurrentIndex: 0,
      hasToy: plLovenseToys.length > 0,
      queue: plLovensePlanQueue,
      refs: {
        consoleEl: lovenseConsoleEl,
        compactStatusEl: lovenseCompactStatusEl,
        toyEl: lovenseToyEl,
        planModeEl: lovensePlanModeEl,
        planTitleEl: lovensePlanTitleEl,
        planStepEl: lovensePlanStepEl,
        planCommandEl: lovensePlanCommandEl,
        nextStepEl: lovenseNextStepEl,
      },
    });
  }
  plLovensePlanState = "queued";
}

function plSetLovensePlanProgress(command, index, total, title) {
  plLovensePlanTitle = String(title || plLovensePlanTitle || "").trim();
  plLovensePlanCurrentCommand = String(command || "").trim();
  plLovensePlanCurrentIndex = Math.max(0, Number(index) || 0);
  plLovensePlanTotal = Math.max(plLovensePlanCurrentIndex, Number(total) || 0);
  const lovenseUi = window.ChasteasePlayLovenseUI || {};
  if (typeof lovenseUi.setPlanProgress === "function") {
    lovenseUi.setPlanProgress({
      state: plLovenseUiState,
      command: plLovensePlanCurrentCommand,
      planTitle: plLovensePlanTitle || "Session-Plan",
      planTotal: plLovensePlanTotal,
      planCurrentIndex: plLovensePlanCurrentIndex,
      hasToy: plLovenseToys.length > 0,
      queue: plLovensePlanQueue,
      refs: {
        consoleEl: lovenseConsoleEl,
        compactStatusEl: lovenseCompactStatusEl,
        toyEl: lovenseToyEl,
        planModeEl: lovensePlanModeEl,
        planTitleEl: lovensePlanTitleEl,
        planStepEl: lovensePlanStepEl,
        planCommandEl: lovensePlanCommandEl,
        nextStepEl: lovenseNextStepEl,
      },
    });
  }
  plLovensePlanState = "running";
}

function plApplyFocusMode(enabled) {
  if (!_shell) return;
  _shell.classList.toggle("is-focus-mode", Boolean(enabled));
  document.body.classList.toggle("play-focus-mode", Boolean(enabled));
  if (focusToggleBtn) {
    focusToggleBtn.setAttribute("aria-pressed", enabled ? "true" : "false");
    focusToggleBtn.textContent = enabled ? "Fokus an" : "Fokus";
  }
}

function plInitFocusMode() {
  let enabled = false;
  try {
    enabled = window.localStorage.getItem(FOCUS_STORAGE_KEY) === "1";
  } catch (_) {}
  plApplyFocusMode(enabled);
}

function plToggleFocusMode() {
  const enabled = !_shell?.classList.contains("is-focus-mode");
  plApplyFocusMode(enabled);
  closeRoleplayDropdown();
  closeTasksDropdown();
  closeSafetyDropdown();
  try {
    window.localStorage.setItem(FOCUS_STORAGE_KEY, enabled ? "1" : "0");
  } catch (_) {}
}

async function plInitVoiceAvailability() {
  const voiceUi = window.ChasteasePlayVoiceUI || {};
  if (typeof voiceUi.initVoiceAvailability === "function") {
    await voiceUi.initVoiceAvailability({
      state: plVoiceState,
      sessionId: SESSION_ID,
      voiceStatusEl,
      voiceToggleBtn,
      get: plGet,
    });
  }
}

async function plToggleVoiceMode() {
  const voiceUi = window.ChasteasePlayVoiceUI || {};
  if (typeof voiceUi.toggleVoiceMode === "function") {
    const chatUi = window.ChasteasePlayChatUI || {};
    await voiceUi.toggleVoiceMode({
      state: plVoiceState,
      sessionId: SESSION_ID,
      voiceStatusEl,
      voiceToggleBtn,
      write: plWrite,
      appendVoiceTranscript: (transcript) => {
        if (typeof chatUi.appendVoiceTranscript === "function") {
          chatUi.appendVoiceTranscript(chatTimeline, transcript, PLAYER_NAME);
        }
      },
    });
  }
}

async function plLoadLovensePresetLibrary() {
  const controller = plEnsureLovenseController();
  if (controller?.loadPresetLibrary) {
    await controller.loadPresetLibrary();
  }
}

async function plHandleClientActions(actions, messageId = null) {
  const controller = plEnsureLovenseController();
  if (controller?.handleClientActions) {
    await controller.handleClientActions(actions, messageId);
  }
}

function plEnsureLovenseController() {
  if (plLovenseController) return plLovenseController;
  const controllerApi = window.ChasteasePlayLovenseController || {};
  if (typeof controllerApi.createController !== "function") return null;
  plLovenseController = controllerApi.createController({
    appType: plLovenseAppType,
    builtinPresets: PL_LOVENSE_PRESETS,
    configured: plLovenseConfigured,
    debug: plLovenseDebug,
    describeStep: plDescribeLovenseStep,
    enabled: plLovenseEnabled,
    get: plGet,
    getBootstrap: () => plLovenseBootstrap,
    getPlanCurrentCommand: () => plLovensePlanCurrentCommand,
    getPlanCurrentIndex: () => plLovensePlanCurrentIndex,
    getPlanQueue: () => plLovensePlanQueue,
    getPlanRunId: () => plLovensePlanRunId,
    getPlanRunning: () => plLovensePlanRunning,
    getPlanTitle: () => plLovensePlanTitle,
    getPlanTotal: () => plLovensePlanTotal,
    getPollHandle: () => plLovensePollHandle,
    getPresetLibrary: () => plLovensePresetLibrary,
    getSdk: () => plLovenseSdk,
    getSequenceTimeout: () => plLovenseSequenceTimeout,
    getToys: () => plLovenseToys,
    getUiState: () => plLovenseUiState,
    handledKeys: plHandledClientActionKeys,
    platform: plLovensePlatform,
    post: plPost,
    rememberAutoInit: plRememberLovenseAutoInit,
    rememberSelectedToyId: plRememberSelectedToyId,
    renderConsole: plRenderLovenseConsole,
    renderPlanStatus: plRenderLovensePlanStatus,
    resetPlanStatus: plResetLovensePlanStatus,
    restoreSelectedToyId: plRestoreSelectedToyId,
    sessionId: SESSION_ID,
    setBootstrap: (value) => { plLovenseBootstrap = value; },
    setPlanCurrentCommand: (value) => { plLovensePlanCurrentCommand = String(value || ""); },
    setPlanCurrentIndex: (value) => { plLovensePlanCurrentIndex = Math.max(0, Number(value) || 0); },
    setPlanProgress: plSetLovensePlanProgress,
    setPlanQueue: (value) => { plLovensePlanQueue = Array.isArray(value) ? value : []; },
    setPlanQueued: plSetLovensePlanQueued,
    setPlanRunId: (value) => { plLovensePlanRunId = Math.max(0, Number(value) || 0); },
    setPlanRunning: (value) => { plLovensePlanRunning = Boolean(value); },
    setPlanTitle: (value) => { plLovensePlanTitle = String(value || ""); },
    setPlanTotal: (value) => { plLovensePlanTotal = Math.max(0, Number(value) || 0); },
    setPollHandle: (value) => { plLovensePollHandle = value; },
    setPresetLibrary: (value) => { plLovensePresetLibrary = value || { builtin: [], wearer: [], persona: [], combined: [] }; },
    setSdk: (value) => { plLovenseSdk = value; },
    setSequenceTimeout: (value) => { plLovenseSequenceTimeout = value; },
    setStatus: plSetLovenseStatus,
    setToys: (value) => { plLovenseToys = Array.isArray(value) ? value : []; },
    simulator: plLovenseSimulator,
    write: plWrite,
  });
  return plLovenseController;
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
  const sessionUi = window.ChasteasePlaySessionUI || {};
  if (typeof sessionUi.renderHygieneQuota === "function") {
    sessionUi.renderHygieneQuota(quotaData);
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
  if (typeof plRuntime.formatRemaining === "function") {
    return plRuntime.formatRemaining(isoStr, { expiredLabel: "Frei", fallback: "—" });
  }
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
  if (typeof plRuntime.jsonGet === "function") {
    return plRuntime.jsonGet(url);
  }
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(data));
  return data;
}

async function plPost(url, payload) {
  if (typeof plRuntime.jsonSend === "function") {
    return plRuntime.jsonSend(url, "POST", payload);
  }
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

function plTaskUiOptions(items = _pendingTaskItems) {
  return {
    sessionId: SESSION_ID,
    pendingItems: Array.isArray(items) ? items : [],
    chatTimeline,
    taskDropBoard,
    tasksToggleBtn,
    tasksBadge,
    get: plGet,
    post: plPost,
    write: plWrite,
    loadChat: plLoadChat,
    listTasks: plListTasks,
    setPendingItems: (nextItems) => {
      _pendingTaskItems = Array.isArray(nextItems) ? nextItems : [];
    },
    getPendingItems: () => _pendingTaskItems,
  };
}

function plRenderRoleplayState(roleplayState, relationshipMemory = {}, phaseProgress = {}) {
  const roleplayStateUi = window.ChasteasePlayRoleplayStateUI || {};
  if (typeof roleplayStateUi.renderRoleplayState === "function") {
    roleplayStateUi.renderRoleplayState({
      roleplayState,
      relationshipMemory,
      phaseProgress,
      roleplayToggle,
    });
    return;
  }
}

// -- Render chat --
function plRenderChat(items) {
  if (!chatTimeline) return;
  _lastMessageItems = Array.isArray(items) ? items : [];
  const chatUi = window.ChasteasePlayChatUI || {};
  const tasksUi = window.ChasteasePlayTasksUI || {};
  if (typeof chatUi.renderChat === "function") {
    chatUi.renderChat(_lastMessageItems, {
      chatTimeline,
      opsBannerEl,
      statusPillEl,
      personaAvatarUrl: _personaAvatarUrl,
      personaName: PERSONA_NAME,
      playerName: PLAYER_NAME,
      formatMessageTime: plFormatMessageTime,
      installInlineTaskCards: () => {
        if (typeof tasksUi.installInlineTaskCards === "function") {
          tasksUi.installInlineTaskCards(plTaskUiOptions());
        }
      },
    });
    return;
  }
  chatTimeline.innerHTML = "<p>Noch keine Nachrichten.</p>";
}

// -- Render tasks --
const taskDropBoard = document.getElementById("play-task-drop-board");
const tasksToggleBtn = document.getElementById("play-tasks-toggle");
const tasksBadge = document.getElementById("play-tasks-badge");

function plRenderTasks(items) {
  const tasksUi = window.ChasteasePlayTasksUI || {};
  if (typeof tasksUi.renderTasks === "function") {
    tasksUi.renderTasks({
      ...plTaskUiOptions(items),
      items,
    });
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
    plRenderRoleplayState(data.roleplay_state || {}, data.relationship_memory || {}, data.phase_progress || {});
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
      if (payload.client_actions) {
        await plHandleClientActions(payload.client_actions, payload.message_id || null);
      }
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

document.getElementById("play-lovense-init")?.addEventListener("click", () => {
  const controller = plEnsureLovenseController();
  controller?.init().catch((err) => plSetLovenseStatus(`Lovense: Start fehlgeschlagen (${String(err)})`));
});

document.getElementById("play-lovense-compact-init")?.addEventListener("click", () => {
  const controller = plEnsureLovenseController();
  controller?.init().catch((err) => plSetLovenseStatus(`Lovense: Start fehlgeschlagen (${String(err)})`));
});

document.getElementById("play-lovense-open-app")?.addEventListener("click", () => {
  if (plLovenseSdk && typeof plLovenseSdk.connectLovenseAPP === "function") {
    Promise.resolve(plLovenseSdk.connectLovenseAPP()).catch((err) => {
      plSetLovenseStatus(`Lovense: Connect App konnte nicht geoeffnet werden (${String(err)})`);
    });
    return;
  }
  plSetLovenseStatus("Lovense: Connect-App-Funktion ist noch nicht verfuegbar.");
});

document.getElementById("play-lovense-stop")?.addEventListener("click", () => {
  const controller = plEnsureLovenseController();
  controller?.cancelPlan(true);
  controller?.stopAction().catch((err) => plSetLovenseStatus(`Lovense: Stop fehlgeschlagen (${String(err)})`));
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
    await plHandleClientActions(data.client_actions || [], data.reply_message_id || null);
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
focusToggleBtn?.addEventListener("click", plToggleFocusMode);

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

// -- Tasks dropdown toggle --
const tasksDropdown = document.getElementById("play-tasks-dropdown");
const tasksMenu = document.getElementById("play-tasks-menu");

function closeTasksDropdown() {
  tasksDropdown?.classList.remove("is-open");
  tasksMenu?.classList.remove("is-open-mobile");
  document.getElementById("play-tasks-toggle")?.setAttribute("aria-expanded", "false");
}

// -- Safety dropdown toggle --
const safetyToggle = document.getElementById("play-safety-toggle");
const safetyDropdown = document.getElementById("play-safety-dropdown");
const safetyMenu = document.getElementById("play-safety-menu");

function closeSafetyDropdown() {
  safetyDropdown?.classList.remove("is-open");
  safetyMenu?.classList.remove("is-open-mobile");
  safetyToggle?.setAttribute("aria-expanded", "false");
}

function updateSafetyToggleStyle(color) {
  if (!safetyToggle) return;
  safetyToggle.classList.remove("is-yellow", "is-red", "is-safeword");
  if (color === "yellow") safetyToggle.classList.add("is-yellow");
  else if (color === "red") safetyToggle.classList.add("is-red");
  else if (color === "safeword") safetyToggle.classList.add("is-safeword");
}

function plBindSessionUi() {
  const sessionUi = window.ChasteasePlaySessionUI || {};
  if (typeof sessionUi.bindSessionControls !== "function") return;
  sessionUi.bindSessionControls({
    state: {
      get hygieneOpeningId() { return plHygieneOpeningId; },
      set hygieneOpeningId(value) { plHygieneOpeningId = value; },
      get hygieneUsesSeal() { return plHygieneUsesSeal; },
      set hygieneUsesSeal(value) { plHygieneUsesSeal = Boolean(value); },
      get hygieneConfiguredDurationSeconds() { return plHygieneConfiguredDurationSeconds; },
      set hygieneConfiguredDurationSeconds(value) { plHygieneConfiguredDurationSeconds = Number(value) || 900; },
      get pendingVerifyId() { return plPendingVerifyId; },
      set pendingVerifyId(value) { plPendingVerifyId = value == null ? null : Number(value); },
      get verifySealNumber() { return plVerifySealNumber; },
      set verifySealNumber(value) { plVerifySealNumber = value || null; },
    },
    sessionId: SESSION_ID,
    get: plGet,
    post: plPost,
    write: plWrite,
    loadHygieneQuota: plLoadHygieneQuota,
    loadVerifications: plLoadVerifications,
    listTasks: plListTasks,
    onSafety: plSafety,
    onSafeword: plSafeword,
    closeSafetyDropdown,
    updateSafetyToggleStyle,
  });
}

// -- Hygiene opening --
let plHygieneOpeningId = null;
let plHygieneUsesSeal = false;
let plHygieneConfiguredDurationSeconds = 900;

// -- Verification --
let plPendingVerifyId = null;
let plVerifySealNumber = null;

async function plLoadVerifications() {
  if (!SESSION_ID) return;
  try {
    const data = await plGet(`/api/sessions/${SESSION_ID}/verifications`);
    const sessionUi = window.ChasteasePlaySessionUI || {};
    if (typeof sessionUi.renderVerifications === "function") {
      sessionUi.renderVerifications(data.items || []);
    }
  } catch (err) {
    plWrite("Fehler Verifikation", { error: String(err) });
  }
}

// -- Auto-load on page ready --
function plBindMenus() {
  const shellUi = window.ChasteasePlayShellUI || {};
  if (typeof shellUi.bindMenu !== "function") return;
  shellUi.bindMenu({ menuId: "play-roleplay-menu", toggleId: "play-roleplay-toggle", dropdownId: "play-roleplay-dropdown" });
  shellUi.bindMenu({ menuId: "play-tasks-menu", toggleId: "play-tasks-toggle", dropdownId: "play-tasks-dropdown" });
  shellUi.bindMenu({ menuId: "play-safety-menu", toggleId: "play-safety-toggle", dropdownId: "play-safety-dropdown" });
}

async function plBoot() {
  if (!SESSION_ID) return;
  plInitFocusMode();
  plResetLovensePlanStatus();
  await plLoadLovensePresetLibrary().catch(() => {});
  await plInitVoiceAvailability();
  plSetLovenseStatus(
    !plLovenseEnabled
      ? "Lovense: serverseitig deaktiviert."
      : (!plLovenseConfigured && !plLovenseSimulator ? "Lovense: Konfiguration unvollstaendig." : "Lovense: bereit. Verbinde den Edge 2 fuer KI-Steuerung.")
  );
  if (plLovenseEnabled && (plLovenseConfigured || plLovenseSimulator)) {
    if (plShouldAutoInitLovense()) {
      const controller = plEnsureLovenseController();
      controller?.init().catch(() => {});
    }
  }
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
  if (typeof plRuntime.startPolling === "function") {
    plRuntime.startPolling(plLoadSessionState, 8000);
  } else {
    setInterval(() => {
      plLoadSessionState().catch(() => {});
    }, 8000);
  }
  plConnectWs();
}

plBindMenus();
plBindSessionUi();
document.addEventListener("DOMContentLoaded", () => {
  plBoot().catch(() => {});
});
