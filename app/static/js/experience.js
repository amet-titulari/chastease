let xpSessionId = null;
let xpWsToken = null;
let xpStep = 1;
let xpPersonaPresets = [];
let xpScenarioPresets = [];
let xpDbPersonas = [];       // DB personas with full data (id, name, ...)
let xpHardcodedPresets = []; // Presets not yet in DB
let xpEditPersonaId = null;  // null = new, int = edit
let xpEditScenarioId = null; // null = new or preset-derived, int = edit DB scenario
let xpCompletedTemplates = [];
let xpDraftSaveInFlight = false;
let xpDraftSaveQueued = false;
let xpPersonaAvatarMediaId = null;
let xpPlayerAvatarMediaId = null;

const statusEl = document.getElementById("onboarding-status");
const outputEl = document.getElementById("xp-output");
const contractEl = document.getElementById("xp-contract-preview");
const sessionIdEl = document.getElementById("xp-session-id");
const sessionStatusEl = document.getElementById("xp-session-status");
const gateEl = document.getElementById("xp-onboarding-gate");
const gateLoadPanelEl = document.getElementById("xp-gate-load-panel");
const onboardingBodyEl = document.getElementById("xp-onboarding-body");

function xpShowOnboardingBody(show) {
  if (!onboardingBodyEl) return;
  onboardingBodyEl.style.display = show ? "" : "none";
}

function xpWrite(title, data) {
  if (!outputEl) return;
  outputEl.textContent = `${title}\n${JSON.stringify(data, null, 2)}`;
}

function xpParseOptionalInt(v) {
  const raw = String(v ?? "").trim();
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? Math.trunc(n) : null;
}

function xpSlugifyScenarioKey(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "scenario";
}

function xpParseCommaList(value) {
  return String(value || "")
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
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

function xpSetAvatarPreview(prefix, url) {
  const img = document.getElementById(`${prefix}-preview`);
  const empty = document.getElementById(`${prefix}-empty`);
  if (!img || !empty) return;
  if (url) {
    img.src = url;
    img.style.display = "";
    empty.style.display = "none";
  } else {
    img.removeAttribute("src");
    img.style.display = "none";
    empty.style.display = "";
  }
}

async function xpUploadAvatar(fileInputId, target) {
  const input = document.getElementById(fileInputId);
  const file = input?.files?.[0];
  if (!file) {
    xpWrite("Avatar", { error: "Bitte zuerst ein Bild auswählen." });
    return;
  }
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("visibility", "private");
  const res = await fetch("/api/media/avatar", { method: "POST", body: form });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || res.statusText);
  if (target === "persona") {
    xpPersonaAvatarMediaId = data.id;
    xpSetAvatarPreview("xp-pe-avatar", data.content_url);
  } else if (target === "player") {
    xpPlayerAvatarMediaId = data.id;
    xpSetAvatarPreview("xp-player-avatar", data.content_url);
  }
  xpWrite("Avatar hochgeladen", { target, media_id: data.id });
}

// ---- localStorage persistence ----
const XP_STORAGE_KEY = "xp_onboarding_draft";
const XP_STORAGE_VERSION = "3"; // bump when HTML defaults change to discard stale drafts

const XP_PERSIST_FIELDS = [
  { id: "xp-pe-name",            type: "value" },
  { id: "xp-pe-tone",            type: "value" },
  { id: "xp-pe-dominance",       type: "value" },
  { id: "xp-pe-description",     type: "value" },
  { id: "xp-pe-system-prompt",   type: "value" },
  { id: "xp-scenario-preset",    type: "value" },
  { id: "xp-se-title",           type: "value" },
  { id: "xp-se-key",             type: "value" },
  { id: "xp-se-summary",         type: "value" },
  { id: "xp-se-tags",            type: "value" },
  { id: "xp-player-nickname",    type: "value" },
  { id: "xp-experience-level",   type: "value" },
  { id: "xp-hard-limits",        type: "value" },
  { id: "xp-penalty-multiplier", type: "value" },
  { id: "xp-gentle-mode",        type: "value" },
  { id: "xp-min-days",           type: "value" },
  { id: "xp-max-days",           type: "value" },
  { id: "xp-max-no-limit",       type: "checked" },
  { id: "xp-hygiene-day",        type: "value" },
  { id: "xp-hygiene-week",       type: "value" },
  { id: "xp-hygiene-month",      type: "value" },
  { id: "xp-hygiene-max-minutes", type: "value" },
  { id: "xp-penalty-default-value",  type: "value" },
  { id: "xp-penalty-default-unit",   type: "value" },
  { id: "xp-penalty-max-value",      type: "value" },
  { id: "xp-seal-enabled",       type: "checked" },
  { id: "xp-seal-number",        type: "value" },
  { id: "xp-contract-keyholder-title", type: "value" },
  { id: "xp-contract-wearer-title", type: "value" },
  { id: "xp-contract-goal",      type: "value" },
  { id: "xp-contract-method",    type: "value" },
  { id: "xp-contract-wearing-schedule", type: "value" },
  { id: "xp-contract-touch-rules", type: "value" },
  { id: "xp-contract-orgasm-rules", type: "value" },
  { id: "xp-contract-reward-policy", type: "value" },
  { id: "xp-contract-termination-policy", type: "value" },
  { id: "xp-llm-provider",       type: "value" },
  { id: "xp-llm-api-url",        type: "value" },
  { id: "xp-llm-api-key",        type: "value" },
  { id: "xp-llm-chat-model",     type: "value" },
  { id: "xp-llm-vision-model",   type: "value" },
];

function xpSaveDraft() {
  const draft = { _v: XP_STORAGE_VERSION };
  for (const { id, type } of XP_PERSIST_FIELDS) {
    const el = document.getElementById(id);
    if (!el) continue;
    draft[id] = type === "checked" ? el.checked : el.value;
  }
  try { localStorage.setItem(XP_STORAGE_KEY, JSON.stringify(draft)); } catch (_) {}
}

function xpRestoreDraft() {
  let draft;
  try { draft = JSON.parse(localStorage.getItem(XP_STORAGE_KEY) || "null"); } catch (_) { return; }
  if (!draft || draft._v !== XP_STORAGE_VERSION) {
    xpClearDraft(); // stale or version-mismatched draft → discard
    return;
  }
  for (const { id, type } of XP_PERSIST_FIELDS) {
    const el = document.getElementById(id);
    if (!el || !(id in draft)) continue;
    if (type === "checked") el.checked = !!draft[id];
    else el.value = draft[id];
  }
}

function xpClearDraft() {
  try { localStorage.removeItem(XP_STORAGE_KEY); } catch (_) {}
}
// ----------------------------------

function xpApplyQuickStart() {
  const personaSelect = document.getElementById("xp-persona-preset");
  if (personaSelect && !personaSelect.value && personaSelect.options.length > 0) {
    personaSelect.value = personaSelect.options[0].value;
  }
  if (personaSelect && personaSelect.value) {
    xpFillPersonaEditor(personaSelect.value);
  }

  const scenarioSelect = document.getElementById("xp-scenario-preset");
  if (scenarioSelect && !scenarioSelect.value && scenarioSelect.options.length > 0) {
    scenarioSelect.value = scenarioSelect.options[0].value;
  }
  if (scenarioSelect && scenarioSelect.value) {
    xpUpdateScenarioDetail(scenarioSelect.value);
    xpFillScenarioEditor(scenarioSelect.value);
  }

  const expEl = document.getElementById("xp-experience-level");
  if (expEl && !expEl.value) expEl.value = "beginner";
  const gentleEl = document.getElementById("xp-gentle-mode");
  if (gentleEl && !gentleEl.value) gentleEl.value = "false";
  const llmProviderEl = document.getElementById("xp-llm-provider");
  if (llmProviderEl && !llmProviderEl.value) llmProviderEl.value = "custom";

  gateEl?.classList.add("is-hidden");
  xpShowOnboardingBody(true);
  if (statusEl) {
    statusEl.textContent = "Quick Start aktiv: reduzierte Vorkonfiguration, direkt zur Session-Erstellung.";
  }
  xpSaveDraft();
  xpSaveDraftToServer();
  xpSwitchStep(5);
}

function xpBuildServerDraftPayload() {
  const noLimit = document.getElementById("xp-max-no-limit")?.checked;
  const minSecs = xpDateToSeconds(document.getElementById("xp-min-date")?.value) || xpDaysToSeconds(document.getElementById("xp-min-days")?.value || "7");
  const maxSecs = noLimit ? null : (xpDateToSeconds(document.getElementById("xp-max-date")?.value) || xpDaysToSeconds(document.getElementById("xp-max-days")?.value || "30"));
  const sealEnabled = document.getElementById("xp-seal-enabled")?.checked || false;
  const unitSeconds = parseInt(document.getElementById("xp-penalty-default-unit")?.value || "3600", 10);
  const defaultPenaltyValue = parseFloat(document.getElementById("xp-penalty-default-value")?.value || "0");
  const maxPenaltyValue = parseFloat(document.getElementById("xp-penalty-max-value")?.value || "0");
  return {
    persona_name: document.getElementById("xp-pe-name")?.value || "",
    persona_tone: document.getElementById("xp-pe-tone")?.value || "",
    persona_dominance: document.getElementById("xp-pe-dominance")?.value || "",
    persona_description: document.getElementById("xp-pe-description")?.value || "",
    persona_system_prompt: document.getElementById("xp-pe-system-prompt")?.value || "",
    scenario_preset: document.getElementById("xp-scenario-preset")?.value || null,
    wearer_nickname: document.getElementById("xp-player-nickname")?.value || "",
    experience_level: document.getElementById("xp-experience-level")?.value || "beginner",
    hard_limits: document.getElementById("xp-hard-limits")?.value || "",
    min_duration_seconds: Math.max(60, minSecs),
    max_duration_seconds: maxSecs === null ? null : Math.max(60, maxSecs),
    no_max_limit: !!noLimit,
    hygiene_limit_daily: xpParseOptionalInt(document.getElementById("xp-hygiene-day")?.value),
    hygiene_limit_weekly: xpParseOptionalInt(document.getElementById("xp-hygiene-week")?.value),
    hygiene_limit_monthly: xpParseOptionalInt(document.getElementById("xp-hygiene-month")?.value),
    penalty_multiplier: Number(document.getElementById("xp-penalty-multiplier")?.value || "1"),
    default_penalty_seconds: defaultPenaltyValue > 0 ? Math.round(defaultPenaltyValue * unitSeconds) : null,
    max_penalty_seconds: maxPenaltyValue > 0 ? Math.round(maxPenaltyValue * unitSeconds) : null,
    gentle_mode: document.getElementById("xp-gentle-mode")?.value === "true",
    hygiene_opening_max_duration_seconds: Math.max(1, Math.round(Number(document.getElementById("xp-hygiene-max-minutes")?.value || "15") * 60)),
    seal_enabled: sealEnabled,
    initial_seal_number: sealEnabled ? (document.getElementById("xp-seal-number")?.value || "") : null,
    contract_keyholder_title: document.getElementById("xp-contract-keyholder-title")?.value || "",
    contract_wearer_title: document.getElementById("xp-contract-wearer-title")?.value || "",
    contract_goal: document.getElementById("xp-contract-goal")?.value || "",
    contract_method: document.getElementById("xp-contract-method")?.value || "",
    contract_wearing_schedule: document.getElementById("xp-contract-wearing-schedule")?.value || "",
    contract_touch_rules: document.getElementById("xp-contract-touch-rules")?.value || "",
    contract_orgasm_rules: document.getElementById("xp-contract-orgasm-rules")?.value || "",
    contract_reward_policy: document.getElementById("xp-contract-reward-policy")?.value || "",
    contract_termination_policy: document.getElementById("xp-contract-termination-policy")?.value || "",
    llm_provider: document.getElementById("xp-llm-provider")?.value || "stub",
    llm_api_url: document.getElementById("xp-llm-api-url")?.value || "",
    llm_api_key: document.getElementById("xp-llm-api-key")?.value || "",
    llm_chat_model: document.getElementById("xp-llm-chat-model")?.value || "",
    llm_vision_model: document.getElementById("xp-llm-vision-model")?.value || "",
    llm_active: true,
  };
}

async function xpSaveDraftToServer() {
  if (xpDraftSaveInFlight) {
    xpDraftSaveQueued = true;
    return;
  }
  xpDraftSaveInFlight = true;
  try {
    await xpPost("/api/experience/draft", xpBuildServerDraftPayload());
  } catch (err) {
    xpWrite("Warnung: Auto-Save", { error: String(err) });
  } finally {
    xpDraftSaveInFlight = false;
    if (xpDraftSaveQueued) {
      xpDraftSaveQueued = false;
      xpSaveDraftToServer();
    }
  }
}

function xpSwitchStep(next) {
  xpSaveDraft();
  xpSaveDraftToServer();
  xpStep = Math.max(1, Math.min(6, next));
  const onboardingCard = document.getElementById("onboarding-card");
  if (onboardingCard) onboardingCard.dataset.activeStep = String(xpStep);

  document.querySelectorAll(".step-tab").forEach((el) => {
    el.classList.toggle("is-active", Number(el.dataset.step) === xpStep);
  });
  document.querySelectorAll(".step-pane").forEach((el) => {
    el.classList.toggle("is-active", Number(el.dataset.step) === xpStep);
  });

  // Hide "Weiter" on step 5 ("Session erstellen" is the action) and step 6.
  const nextBtn = document.getElementById("xp-next-step");
  if (nextBtn) nextBtn.style.display = xpStep >= 5 ? "none" : "";
}

// --- Duration helpers ---
function xpDateToSeconds(dateStr) {
  if (!dateStr) return null;
  const diff = new Date(dateStr).getTime() - Date.now();
  return diff > 0 ? Math.round(diff / 1000) : null;
}

function xpSecondsToDateLocal(seconds) {
  const d = new Date(Date.now() + seconds * 1000);
  // datetime-local requires "YYYY-MM-DDTHH:MM"
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function xpDaysToSeconds(days) {
  return Math.round(parseFloat(days) * 86400);
}

function xpFormatDuration(seconds) {
  if (!seconds || seconds <= 0) return "";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const parts = [];
  if (d > 0) parts.push(`${d}d`);
  if (h > 0) parts.push(`${h}h`);
  if (m > 0 && d === 0) parts.push(`${m}m`);
  return parts.join(" ");
}

function xpWireDuration(dateId, daysId, summaryId) {
  const dateEl = document.getElementById(dateId);
  const daysEl = document.getElementById(daysId);
  const summaryEl = document.getElementById(summaryId);
  if (!dateEl || !daysEl) return;

  dateEl.addEventListener("change", () => {
    const secs = xpDateToSeconds(dateEl.value);
    if (secs) {
      daysEl.value = Math.round(secs / 86400);
      if (summaryEl) summaryEl.textContent = xpFormatDuration(secs);
    }
  });
  daysEl.addEventListener("input", () => {
    const val = parseInt(daysEl.value, 10);
    if (!isNaN(val) && val > 0) {
      const secs = xpDaysToSeconds(val);
      dateEl.value = xpSecondsToDateLocal(secs);
      if (summaryEl) summaryEl.textContent = xpFormatDuration(secs);
    }
  });
}

function xpInitDurationDefaults() {
  // Min default: 7 days
  const minSecs = 7 * 86400;
  const minDateEl = document.getElementById("xp-min-date");
  const minDaysEl = document.getElementById("xp-min-days");
  if (minDateEl) minDateEl.value = xpSecondsToDateLocal(minSecs);
  if (minDaysEl) minDaysEl.value = "7";

  // Max default: 30 days
  const maxSecs = 30 * 86400;
  const maxDateEl = document.getElementById("xp-max-date");
  const maxDaysEl = document.getElementById("xp-max-days");
  if (maxDateEl) maxDateEl.value = xpSecondsToDateLocal(maxSecs);
  if (maxDaysEl) maxDaysEl.value = "30";
}

function xpWireNoLimit() {
  const cb = document.getElementById("xp-max-no-limit");
  const dateEl = document.getElementById("xp-max-date");
  const daysEl = document.getElementById("xp-max-days");
  const summaryEl = document.getElementById("xp-max-summary");
  if (!cb) return;
  cb.addEventListener("change", () => {
    const disabled = cb.checked;
    if (dateEl) dateEl.disabled = disabled;
    if (daysEl) daysEl.disabled = disabled;
    if (summaryEl) summaryEl.textContent = disabled ? "Kein Limit gesetzt" : "";
  });
}

async function xpLoadPersonaPresets(selectName) {
  const select = document.getElementById("xp-persona-preset");
  select.innerHTML = "";
  try {
    const [dbData, presetData] = await Promise.all([
      xpGet("/api/personas"),
      xpGet("/api/personas/presets"),
    ]);
    xpDbPersonas = dbData.items || [];
    const hardcoded = presetData.items || [];
    const dbNames = new Set(xpDbPersonas.map((p) => p.name));
    xpHardcodedPresets = hardcoded.filter((p) => !dbNames.has(p.name));

    // DB personas first, then hardcoded presets not yet in DB
    const dbOpts = xpDbPersonas.map((p) => p.name);
    const hcOpts = xpHardcodedPresets.map((p) => p.name);
    const merged = [...dbOpts, ...hcOpts];
    xpPersonaPresets = merged.map((name) => ({ name }));

    if (!merged.length) {
      select.innerHTML = '<option value="">Keine Keyholderinnen vorhanden</option>';
      return;
    }

    if (dbOpts.length) {
      const grpDb = document.createElement("optgroup");
      grpDb.label = "Meine Keyholderinnen";
      dbOpts.forEach((name) => {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        grpDb.appendChild(opt);
      });
      select.appendChild(grpDb);
    }
    if (hcOpts.length) {
      const grpHc = document.createElement("optgroup");
      grpHc.label = "Integrierte Keyholderinnen";
      hcOpts.forEach((name) => {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        grpHc.appendChild(opt);
      });
      select.appendChild(grpHc);
    }

    const chosen = selectName || merged.find((n) => n === "Ametara Titulari") || merged[0];
    if (merged.includes(chosen)) select.value = chosen;
    if (select.value) xpFillPersonaEditor(select.value);
  } catch (err) {
    select.innerHTML = '<option value="">Fehler beim Laden</option>';
    xpWrite("Fehler Keyholderin Laden", { error: String(err) });
  }
}

// ── Inline Persona Editor ────────────────────────────────────────────────────

// Fill the always-visible editor with data for the given persona name
function xpFillPersonaEditor(selectedName) {
  const title = document.getElementById("xp-persona-editor-title");
  const dbPersona = xpDbPersonas.find((p) => p.name === selectedName);
  if (dbPersona) {
    xpEditPersonaId = dbPersona.id;
    title.textContent = dbPersona.name;
    document.getElementById("xp-pe-name").value = dbPersona.name || "";
    document.getElementById("xp-pe-tone").value = dbPersona.speech_style_tone || "";
    document.getElementById("xp-pe-dominance").value = dbPersona.speech_style_dominance || "gentle-dominant";
    document.getElementById("xp-pe-description").value = dbPersona.description || "";
    document.getElementById("xp-pe-system-prompt").value = dbPersona.system_prompt || "";
    xpPersonaAvatarMediaId = dbPersona.avatar_media_id || null;
    xpSetAvatarPreview("xp-pe-avatar", dbPersona.avatar_url || null);
  } else {
    const hc = xpHardcodedPresets.find((p) => p.name === selectedName);
    xpEditPersonaId = null;
    title.textContent = hc ? hc.name : (selectedName || "Neue Persona");
    document.getElementById("xp-pe-name").value = hc ? hc.name : (selectedName || "");
    document.getElementById("xp-pe-tone").value = hc ? (hc.speech_style_tone || "") : "";
    document.getElementById("xp-pe-dominance").value = hc ? (hc.speech_style_dominance || "gentle-dominant") : "gentle-dominant";
    document.getElementById("xp-pe-description").value = hc ? (hc.description || "") : "";
    document.getElementById("xp-pe-system-prompt").value = hc ? (hc.system_prompt || "") : "";
    xpPersonaAvatarMediaId = null;
    xpSetAvatarPreview("xp-pe-avatar", null);
  }
}

// Clear editor for a new persona
function xpClearPersonaEditor() {
  xpEditPersonaId = null;
  document.getElementById("xp-persona-editor-title").textContent = "Neue Keyholderin";
  document.getElementById("xp-pe-name").value = "";
  document.getElementById("xp-pe-tone").value = "";
  document.getElementById("xp-pe-dominance").value = "gentle-dominant";
  document.getElementById("xp-pe-description").value = "";
  document.getElementById("xp-pe-system-prompt").value = "";
  xpPersonaAvatarMediaId = null;
  xpSetAvatarPreview("xp-pe-avatar", null);
  document.getElementById("xp-persona-preset").value = "";
  document.getElementById("xp-pe-name").focus();
}

async function xpSavePersonaEditor() {
  const name = document.getElementById("xp-pe-name").value.trim();
  if (!name) {
    xpWrite("Hinweis", { error: "Bitte einen Namen eingeben." });
    return;
  }
  const dominance = document.getElementById("xp-pe-dominance").value;
  const payload = {
    name,
    speech_style_tone: document.getElementById("xp-pe-tone").value.trim() || null,
    speech_style_dominance: dominance || null,
    description: document.getElementById("xp-pe-description").value.trim() || null,
    system_prompt: document.getElementById("xp-pe-system-prompt").value.trim() || null,
    avatar_media_id: xpPersonaAvatarMediaId,
  };
  const saveBtn = document.getElementById("xp-pe-save-btn");
  saveBtn.disabled = true;
  try {
    let saved;
    if (xpEditPersonaId !== null) {
      // Update existing
      const res = await fetch(`/api/personas/${xpEditPersonaId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(data));
      saved = data;
    } else {
      // Create new
      const res = await fetch("/api/personas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(data));
      saved = data;
    }
    xpWrite("Keyholderin gespeichert", { name: saved.name, id: saved.id });
    // Reload dropdown and select saved persona (also refills editor)
    await xpLoadPersonaPresets(saved.name);
  } catch (err) {
    xpWrite("Fehler Keyholderin speichern", { error: String(err) });
  } finally {
    saveBtn.disabled = false;
  }
}

async function xpLoadScenarioPresets(preferredKey = null) {
  const select = document.getElementById("xp-scenario-preset");
  if (!select) return;
  select.innerHTML = "";
  try {
    // Load DB scenarios and hardcoded presets, merge with DB taking priority
    const [dbData, presetData] = await Promise.all([
      xpGet("/api/scenarios"),
      xpGet("/api/scenarios/presets"),
    ]);
    const dbItems = (dbData.items || []).map((s) => ({ ...s, _source: "db" }));
    const presetItems = (presetData.items || []).map((s) => ({ ...s, _source: "preset" }));
    const dbKeys = new Set(dbItems.map((s) => s.key));
    const merged = [...dbItems, ...presetItems.filter((p) => !dbKeys.has(p.key))];
    xpScenarioPresets = merged;

    if (!xpScenarioPresets.length) {
      select.innerHTML = '<option value="">Keine Scenarios</option>';
      return;
    }

    // Build optgroups: DB scenarios first, then hardcoded presets
    const dbOnes = merged.filter((s) => s._source === "db");
    const presetOnes = merged.filter((s) => s._source === "preset");
    if (dbOnes.length) {
      const grp = document.createElement("optgroup");
      grp.label = "Meine Scenarios";
      dbOnes.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.key;
        opt.textContent = s.title;
        grp.appendChild(opt);
      });
      select.appendChild(grp);
    }
    if (presetOnes.length) {
      const grp = document.createElement("optgroup");
      grp.label = "Vorgefertigte Scenarios";
      presetOnes.forEach((s) => {
        const opt = document.createElement("option");
        opt.value = s.key;
        opt.textContent = s.title;
        grp.appendChild(opt);
      });
      select.appendChild(grp);
    }

    const preferred = ["ametara_titulari_devotion_protocol", "amet_titulari_devotion_protocol"];
    const initialScenario = xpScenarioPresets.find((s) => s.key === preferredKey)
      || xpScenarioPresets.find((s) => preferred.includes(s.key))
      || xpScenarioPresets[0];
    if (initialScenario) {
      select.value = initialScenario.key;
      xpUpdateScenarioDetail(initialScenario.key);
      xpFillScenarioEditor(initialScenario.key);
    }
  } catch (err) {
    select.innerHTML = '<option value="">Scenario-Fehler</option>';
    xpWrite("Fehler Scenario Presets", { error: String(err) });
  }
}

async function xpLoadCompletedTemplates() {
  const select = document.getElementById("xp-template-session");
  if (!select) return;
  select.innerHTML = '<option value="">Keine Vorlage</option>';
  try {
    const data = await xpGet("/api/sessions/blueprints/completed");
    xpCompletedTemplates = data.items || [];
    xpCompletedTemplates.forEach((item) => {
      const opt = document.createElement("option");
      opt.value = String(item.session_id);
      opt.textContent = `#${item.session_id} · ${item.persona_name} / ${item.player_nickname}`;
      select.appendChild(opt);
    });

    if (xpCompletedTemplates.length > 0) {
      gateEl?.classList.remove("is-hidden");
      gateLoadPanelEl?.classList.add("is-hidden");
      xpShowOnboardingBody(false);
    } else {
      gateEl?.classList.add("is-hidden");
      xpShowOnboardingBody(true);
    }
  } catch (err) {
    xpWrite("Fehler Vorlagen", { error: String(err) });
    gateEl?.classList.add("is-hidden");
    xpShowOnboardingBody(true);
  }
}

async function xpApplyTemplateSession(sessionId) {
  if (!sessionId) return;
  const data = await xpGet(`/api/sessions/blueprints/${sessionId}`);

  if (data.persona_name) {
    const personaSelect = document.getElementById("xp-persona-preset");
    if (personaSelect) {
      const matching = Array.from(personaSelect.options).find((o) => o.value === data.persona_name || o.textContent.trim() === data.persona_name);
      if (matching) {
        personaSelect.value = matching.value;
        xpFillPersonaEditor(matching.value);
      } else {
        document.getElementById("xp-pe-name").value = data.persona_name;
      }
    }
  }

  if (data.player_nickname) document.getElementById("xp-player-nickname").value = data.player_nickname;
  if (data.experience_level) document.getElementById("xp-experience-level").value = data.experience_level;
  if (Array.isArray(data.hard_limits)) document.getElementById("xp-hard-limits").value = data.hard_limits.join(", ");
  if (data.penalty_multiplier != null) document.getElementById("xp-penalty-multiplier").value = String(data.penalty_multiplier);
  document.getElementById("xp-gentle-mode").value = data.gentle_mode ? "true" : "false";

  if (data.scenario_preset) {
    const sc = document.getElementById("xp-scenario-preset");
    sc.value = data.scenario_preset;
    xpUpdateScenarioDetail(data.scenario_preset);
    xpFillScenarioEditor(data.scenario_preset);
  }
  if (data.contract_preferences) {
    document.getElementById("xp-contract-keyholder-title").value = data.contract_preferences.keyholder_title || "";
    document.getElementById("xp-contract-wearer-title").value = data.contract_preferences.wearer_title || "";
    document.getElementById("xp-contract-goal").value = data.contract_preferences.goal || "";
    document.getElementById("xp-contract-method").value = data.contract_preferences.method || "";
    document.getElementById("xp-contract-wearing-schedule").value = data.contract_preferences.wearing_schedule || "";
    document.getElementById("xp-contract-touch-rules").value = data.contract_preferences.touch_rules || "";
    document.getElementById("xp-contract-orgasm-rules").value = data.contract_preferences.orgasm_rules || "";
    document.getElementById("xp-contract-reward-policy").value = data.contract_preferences.reward_policy || "";
    document.getElementById("xp-contract-termination-policy").value = data.contract_preferences.termination_policy || "";
  }

  if (data.min_duration_seconds) {
    document.getElementById("xp-min-days").value = String(Math.max(1, Math.round(data.min_duration_seconds / 86400)));
    document.getElementById("xp-min-date").value = xpSecondsToDateLocal(data.min_duration_seconds);
  }
  if (data.max_duration_seconds) {
    document.getElementById("xp-max-no-limit").checked = false;
    document.getElementById("xp-max-days").value = String(Math.max(1, Math.round(data.max_duration_seconds / 86400)));
    document.getElementById("xp-max-date").value = xpSecondsToDateLocal(data.max_duration_seconds);
  } else {
    document.getElementById("xp-max-no-limit").checked = true;
  }

  if (data.hygiene_limit_daily != null) document.getElementById("xp-hygiene-day").value = String(data.hygiene_limit_daily);
  if (data.hygiene_limit_weekly != null) document.getElementById("xp-hygiene-week").value = String(data.hygiene_limit_weekly);
  if (data.hygiene_limit_monthly != null) document.getElementById("xp-hygiene-month").value = String(data.hygiene_limit_monthly);
  if (data.hygiene_opening_max_duration_seconds != null) {
    document.getElementById("xp-hygiene-max-minutes").value = String(Math.max(1, Math.round(data.hygiene_opening_max_duration_seconds / 60)));
  }

  if (data.llm) {
    if (data.llm.provider) document.getElementById("xp-llm-provider").value = data.llm.provider;
    if (data.llm.api_url) document.getElementById("xp-llm-api-url").value = data.llm.api_url;
    if (data.llm.chat_model) document.getElementById("xp-llm-chat-model").value = data.llm.chat_model;
    if (data.llm.vision_model) document.getElementById("xp-llm-vision-model").value = data.llm.vision_model;
    // llm_active is always true — no checkbox anymore
  }

  gateEl?.classList.add("is-hidden");
  xpShowOnboardingBody(true);
  xpSwitchStep(1);
  xpWrite("Vorlage geladen", { session_id: data.session_id });
}

function xpUpdateScenarioDetail(key) {
  const scenario = xpScenarioPresets.find((p) => p.key === key);
  const titleEl = document.getElementById("xp-scenario-title");
  const summaryEl = document.getElementById("xp-scenario-summary");
  const focusEl = document.getElementById("xp-scenario-focus");
  const phasesEl = document.getElementById("xp-scenario-phases");
  const lorebookEl = document.getElementById("xp-scenario-lorebook");
  const itemsEl = document.getElementById("xp-scenario-items");
  if (!titleEl) return;
  if (!scenario) {
    titleEl.textContent = "";
    summaryEl.textContent = "";
    if (focusEl) focusEl.innerHTML = "";
    if (phasesEl) phasesEl.innerHTML = "";
    if (lorebookEl) lorebookEl.innerHTML = "";
    if (itemsEl) itemsEl.innerHTML = "";
    return;
  }
  titleEl.textContent = scenario.title;
  summaryEl.textContent = scenario.summary || "";

  // Tags / focus chips
  const tags = scenario.tags || scenario.focus || [];
  if (focusEl) {
    focusEl.innerHTML = tags.map((f) => `<span class="xp-focus-chip">${f}</span>`).join("");
  }

  // Phases list
  const phases = scenario.phases || [];
  if (phasesEl) {
    if (phases.length) {
      phasesEl.innerHTML = `<p class="xp-scenario-phases-label">Phasen (${phases.length})</p>` +
        phases.map((ph, i) =>
          `<div class="xp-phase-item">
            <span class="xp-phase-num">${i + 1}</span>
            <div>
              <strong>${ph.title || "Phase " + (i + 1)}</strong>
              ${ph.objective ? `<br><span class="xp-phase-obj">${ph.objective}</span>` : ""}
            </div>
          </div>`
        ).join("");
    } else {
      phasesEl.innerHTML = "";
    }
  }

  // Lorebook info
  const lorebook = scenario.lorebook || [];
  if (lorebookEl) {
    lorebookEl.innerHTML = lorebook.length
      ? `<span class="xp-scenario-meta-badge">&#x1F4DA; ${lorebook.length} Lore-Eintrag/-Einträge</span>`
      : "";
  }

  xpLoadScenarioInventoryPreview(scenario, itemsEl);
}

function xpFillScenarioEditor(key) {
  const titleEl = document.getElementById("xp-scenario-editor-title");
  const deleteBtn = document.getElementById("xp-se-delete-btn");
  const scenario = xpScenarioPresets.find((p) => p.key === key);
  if (!titleEl) return;

  if (!scenario) {
    xpEditScenarioId = null;
    titleEl.textContent = "Neues Scenario";
    document.getElementById("xp-se-title").value = "";
    document.getElementById("xp-se-key").value = "";
    document.getElementById("xp-se-summary").value = "";
    document.getElementById("xp-se-tags").value = "";
    if (deleteBtn) deleteBtn.disabled = true;
    return;
  }

  const isDbScenario = scenario._source === "db" && Number.isInteger(scenario.id);
  xpEditScenarioId = isDbScenario ? scenario.id : null;
  titleEl.textContent = isDbScenario ? `Scenario: ${scenario.title}` : `Preset kopieren: ${scenario.title}`;
  document.getElementById("xp-se-title").value = scenario.title || "";
  document.getElementById("xp-se-key").value = scenario.key || "";
  document.getElementById("xp-se-summary").value = scenario.summary || "";
  document.getElementById("xp-se-tags").value = (scenario.tags || []).join(", ");
  if (deleteBtn) deleteBtn.disabled = !isDbScenario;
}

function xpClearScenarioEditor() {
  xpEditScenarioId = null;
  document.getElementById("xp-scenario-editor-title").textContent = "Neues Scenario";
  document.getElementById("xp-se-title").value = "";
  document.getElementById("xp-se-key").value = "";
  document.getElementById("xp-se-summary").value = "";
  document.getElementById("xp-se-tags").value = "";
  document.getElementById("xp-scenario-preset").value = "";
  const deleteBtn = document.getElementById("xp-se-delete-btn");
  if (deleteBtn) deleteBtn.disabled = true;
  document.getElementById("xp-se-title").focus();
}

async function xpSaveScenarioEditor() {
  const title = document.getElementById("xp-se-title").value.trim();
  if (!title) {
    xpWrite("Hinweis", { error: "Bitte einen Scenario-Titel eingeben." });
    return;
  }

  const selectedKey = document.getElementById("xp-scenario-preset").value;
  const currentScenario = xpScenarioPresets.find((p) => p.key === selectedKey) || null;
  const payload = {
    title,
    key: document.getElementById("xp-se-key").value.trim() || xpSlugifyScenarioKey(title),
    summary: document.getElementById("xp-se-summary").value.trim() || null,
    tags: xpParseCommaList(document.getElementById("xp-se-tags").value),
    phases: currentScenario?.phases || [],
    lorebook: currentScenario?.lorebook || [],
  };

  const saveBtn = document.getElementById("xp-se-save-btn");
  saveBtn.disabled = true;
  try {
    let saved;
    if (xpEditScenarioId !== null) {
      saved = await xpPut(`/api/scenarios/${xpEditScenarioId}`, payload);
    } else {
      saved = await xpPost("/api/scenarios", payload);
    }
    xpWrite("Scenario gespeichert", { title: saved.title, key: saved.key, id: saved.id });
    await xpLoadScenarioPresets(saved.key);
  } catch (err) {
    xpWrite("Fehler Scenario speichern", { error: String(err) });
  } finally {
    saveBtn.disabled = false;
  }
}

async function xpDeleteScenarioEditor() {
  if (xpEditScenarioId === null) return;
  const title = document.getElementById("xp-se-title").value.trim() || "dieses Scenario";
  if (!window.confirm(`Scenario wirklich loeschen: ${title}?`)) return;

  const deleteBtn = document.getElementById("xp-se-delete-btn");
  deleteBtn.disabled = true;
  try {
    const res = await fetch(`/api/scenarios/${xpEditScenarioId}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    xpWrite("Scenario geloescht", { id: xpEditScenarioId, title });
    xpClearScenarioEditor();
    await xpLoadScenarioPresets();
  } catch (err) {
    xpWrite("Fehler Scenario loeschen", { error: String(err) });
  }
}

async function xpLoadScenarioInventoryPreview(scenario, targetEl) {
  if (!targetEl) return;
  if (!scenario || !scenario.id) {
    targetEl.innerHTML = "";
    return;
  }
  try {
    const data = await xpGet(`/api/inventory/scenarios/${scenario.id}/items`);
    const items = data.items || [];
    if (!items.length) {
      targetEl.innerHTML = "<span class='xp-scenario-meta-badge'>Keine Inventar-Items hinterlegt</span>";
      return;
    }
    targetEl.innerHTML = `<span class='xp-scenario-meta-badge'>🧰 ${items.length} Inventar-Item(s)</span>`;
  } catch (_) {
    targetEl.innerHTML = "";
  }
}

document.getElementById("xp-persona-preset").addEventListener("change", (e) => {
  if (e.target.value) {
    xpFillPersonaEditor(e.target.value);
  }
});

document.getElementById("xp-scenario-preset").addEventListener("change", (e) => {
  xpUpdateScenarioDetail(e.target.value);
  xpFillScenarioEditor(e.target.value);
});

document.getElementById("xp-new-persona-btn").addEventListener("click", xpClearPersonaEditor);
document.getElementById("xp-pe-save-btn").addEventListener("click", xpSavePersonaEditor);
document.getElementById("xp-new-scenario-btn").addEventListener("click", xpClearScenarioEditor);
document.getElementById("xp-se-save-btn").addEventListener("click", xpSaveScenarioEditor);
document.getElementById("xp-se-delete-btn").addEventListener("click", xpDeleteScenarioEditor);
document.getElementById("xp-gate-new")?.addEventListener("click", () => {
  gateEl?.classList.add("is-hidden");
  xpShowOnboardingBody(true);
  xpSwitchStep(1);
});
document.getElementById("xp-gate-quick")?.addEventListener("click", xpApplyQuickStart);
document.getElementById("xp-quick-start")?.addEventListener("click", xpApplyQuickStart);
document.getElementById("xp-gate-load")?.addEventListener("click", () => {
  gateLoadPanelEl?.classList.remove("is-hidden");
});
document.getElementById("xp-load-template-btn")?.addEventListener("click", async () => {
  const id = Number(document.getElementById("xp-template-session")?.value || 0);
  if (!id) return;
  try {
    await xpApplyTemplateSession(id);
  } catch (err) {
    xpWrite("Fehler Vorlage", { error: String(err) });
  }
});

document.querySelectorAll(".step-tab").forEach((btn) => {
  btn.addEventListener("click", () => xpSwitchStep(Number(btn.dataset.step)));
});

document.getElementById("xp-prev-step").addEventListener("click", () => xpSwitchStep(xpStep - 1));
document.getElementById("xp-next-step").addEventListener("click", () => {
  xpSwitchStep(xpStep + 1);
});

document.getElementById("xp-seal-enabled")?.addEventListener("change", (e) => {
  const field = document.getElementById("xp-seal-field");
  if (field) field.classList.toggle("is-hidden", !e.target.checked);
});

function xpMarkdownToHtml(md) {
  return md
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/^#{3}\s+(.+)$/gm, "<h4>$1</h4>")
    .replace(/^#{2}\s+(.+)$/gm, "<h3>$1</h3>")
    .replace(/^#{1}\s+(.+)$/gm, "<h2>$1</h2>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/^[-–]\s+(.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>\n?)+/g, (m) => "<ul>" + m + "</ul>")
    .replace(/^\|(.+)\|$/gm, (_, row) => {
      // Skip separator rows like |---|---|---|
      if (row.split("|").every((c) => /^[:\- ]+$/.test(c.trim()))) return "";
      const cells = row.split("|").map((c) => `<td>${c.trim()}</td>`).join("");
      return `<tr>${cells}</tr>`;
    })
    .replace(/(<tr>.*<\/tr>\n?)+/g, (m) => {
      // Promote first <tr> to a header row with <th>
      let first = true;
      return "<table>" + m.replace(/<tr>(.*?)<\/tr>/g, (_, cells) => {
        if (first) { first = false; return "<thead><tr>" + cells.replace(/<td>/g, "<th>").replace(/<\/td>/g, "</th>") + "</tr></thead><tbody>"; }
        return `<tr>${cells}</tr>`;
      }) + "</tbody></table>";
    })
    .replace(/^-{3,}$/gm, "<hr>")
    .replace(/\n{2,}/g, "</p><p>")
    .replace(/^(?!<[a-z])(.*)/gm, (_, line) => line ? line : "")
    .replace(/^(.+)$/gm, (m) => m.startsWith("<") ? m : m);
}

function xpRefreshCreateButton() {
  const createBtn = document.getElementById("xp-create-session");
  if (!createBtn) return;
  const label = createBtn.querySelector(".btn-label");
  if (!label) return;
  label.textContent = xpSessionId ? "Vertragsvorschau aktualisieren" : "Session erstellen";
}

document.getElementById("xp-create-session").addEventListener("click", async () => {
  const createBtn = document.getElementById("xp-create-session");
  createBtn.disabled = true;
  createBtn.classList.add("is-loading");
  try {
    const scenarioPreset = document.getElementById("xp-scenario-preset")?.value || null;
    const noLimit = document.getElementById("xp-max-no-limit")?.checked;
    const minSecs = xpDateToSeconds(document.getElementById("xp-min-date")?.value) || xpDaysToSeconds(document.getElementById("xp-min-days")?.value || "7");
    const maxSecs = noLimit ? 0 : (xpDateToSeconds(document.getElementById("xp-max-date")?.value) || xpDaysToSeconds(document.getElementById("xp-max-days")?.value || "30"));
    const sealEnabled = document.getElementById("xp-seal-enabled")?.checked || false;
    const sealNumber = sealEnabled ? (document.getElementById("xp-seal-number")?.value?.trim() || null) : null;
    const payload = {
      persona_name: document.getElementById("xp-pe-name").value.trim(),
      player_nickname: document.getElementById("xp-player-nickname").value,
      min_duration_seconds: Math.max(60, minSecs),
      max_duration_seconds: noLimit ? null : Math.max(60, maxSecs),
      hygiene_limit_daily: xpParseOptionalInt(document.getElementById("xp-hygiene-day").value),
      hygiene_limit_weekly: xpParseOptionalInt(document.getElementById("xp-hygiene-week").value),
      hygiene_limit_monthly: xpParseOptionalInt(document.getElementById("xp-hygiene-month").value),
      hygiene_opening_max_duration_seconds: Math.max(1, Math.round(Number(document.getElementById("xp-hygiene-max-minutes")?.value || "15") * 60)),
      experience_level: document.getElementById("xp-experience-level").value || "beginner",
      hard_limits: String(document.getElementById("xp-hard-limits").value)
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean),
      scenario_preset: scenarioPreset,
      initial_seal_number: sealNumber,
      contract_keyholder_title: document.getElementById("xp-contract-keyholder-title")?.value?.trim() || null,
      contract_wearer_title: document.getElementById("xp-contract-wearer-title")?.value?.trim() || null,
      contract_goal: document.getElementById("xp-contract-goal")?.value?.trim() || null,
      contract_method: document.getElementById("xp-contract-method")?.value?.trim() || null,
      contract_wearing_schedule: document.getElementById("xp-contract-wearing-schedule")?.value?.trim() || null,
      contract_touch_rules: document.getElementById("xp-contract-touch-rules")?.value?.trim() || null,
      contract_orgasm_rules: document.getElementById("xp-contract-orgasm-rules")?.value?.trim() || null,
      contract_reward_policy: document.getElementById("xp-contract-reward-policy")?.value?.trim() || null,
      contract_termination_policy: document.getElementById("xp-contract-termination-policy")?.value?.trim() || null,
      template_session_id: xpParseOptionalInt(document.getElementById("xp-template-session")?.value || ""),
      llm_provider: document.getElementById("xp-llm-provider")?.value || null,
      llm_api_url: document.getElementById("xp-llm-api-url")?.value?.trim() || null,
      llm_api_key: document.getElementById("xp-llm-api-key")?.value?.trim() || null,
      llm_chat_model: document.getElementById("xp-llm-chat-model")?.value?.trim() || null,
      llm_vision_model: document.getElementById("xp-llm-vision-model")?.value?.trim() || null,
      llm_active: true,
    };
    const created = xpSessionId
      ? await xpPut(`/api/sessions/${xpSessionId}/draft`, payload)
      : await xpPost("/api/sessions", payload);
    xpSessionId = created.session_id;
    xpWsToken = created.ws_auth_token;
    xpRefreshCreateButton();
    sessionIdEl.textContent = String(xpSessionId);
    sessionStatusEl.textContent = created.status;
    contractEl.innerHTML = `<div class="md-body">${xpMarkdownToHtml(created.contract_preview || "(keine Vorschau)")}</div>`;

    const profilePayload = {
      experience_level: document.getElementById("xp-experience-level").value,
      preferences: {
        scenario_preset: document.getElementById("xp-scenario-preset")?.value || null,
        wearer_style: document.getElementById("xp-pe-tone")?.value?.trim() || null,
        wearer_goal: document.getElementById("xp-contract-goal")?.value?.trim() || null,
        wearer_boundary: document.getElementById("xp-hard-limits")?.value?.trim() || null,
        hygiene_opening_max_duration_seconds: Math.max(1, Math.round(Number(document.getElementById("xp-hygiene-max-minutes")?.value || "15") * 60)),
        contract: {
          keyholder_title: document.getElementById("xp-contract-keyholder-title")?.value?.trim() || null,
          wearer_title: document.getElementById("xp-contract-wearer-title")?.value?.trim() || null,
          goal: document.getElementById("xp-contract-goal")?.value?.trim() || null,
          method: document.getElementById("xp-contract-method")?.value?.trim() || null,
          wearing_schedule: document.getElementById("xp-contract-wearing-schedule")?.value?.trim() || null,
          touch_rules: document.getElementById("xp-contract-touch-rules")?.value?.trim() || null,
          orgasm_rules: document.getElementById("xp-contract-orgasm-rules")?.value?.trim() || null,
          reward_policy: document.getElementById("xp-contract-reward-policy")?.value?.trim() || null,
          termination_policy: document.getElementById("xp-contract-termination-policy")?.value?.trim() || null,
        },
      },
      hard_limits: String(document.getElementById("xp-hard-limits").value)
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean),
      reaction_patterns: {
        penalty_multiplier: Number(document.getElementById("xp-penalty-multiplier").value || "1"),
        default_penalty_seconds: (function() {
          const h = parseFloat(document.getElementById("xp-penalty-default-value")?.value || "0");
          const unit = parseInt(document.getElementById("xp-penalty-default-unit")?.value || "3600", 10);
          return h > 0 ? Math.round(h * unit) : null;
        })(),
        max_penalty_seconds: (function() {
          const h = parseFloat(document.getElementById("xp-penalty-max-value")?.value || "0");
          const unit = parseInt(document.getElementById("xp-penalty-default-unit")?.value || "3600", 10);
          return h > 0 ? Math.round(h * unit) : null;
        })(),
      },
      needs: {
        gentle_mode: document.getElementById("xp-gentle-mode").value === "true",
      },
      avatar_media_id: xpPlayerAvatarMediaId,
    };
    await xpPut(`/api/sessions/${xpSessionId}/player-profile`, profilePayload);

    xpSwitchStep(6);
    const contractStep = document.querySelector('.step-pane[data-step="6"]');
    contractStep?.scrollIntoView({ behavior: "smooth", block: "start" });
    xpWrite(created.updated ? "Draft-Session aktualisiert" : "Session erstellt", created);
  } catch (err) {
    xpWrite("Fehler Session", { error: String(err) });
  } finally {
    createBtn.disabled = false;
    createBtn.classList.remove("is-loading");
  }
});

document.getElementById("xp-llm-test").addEventListener("click", async () => {
  const btn = document.getElementById("xp-llm-test");
  const testStatus = document.getElementById("xp-llm-test-status");
  btn.disabled = true;
  btn.classList.add("is-loading");
  testStatus.textContent = "Teste\u2026";
  testStatus.className = "";
  try {
    const res = await fetch("/api/llm/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider: document.getElementById("xp-llm-provider")?.value,
        api_url: document.getElementById("xp-llm-api-url")?.value?.trim(),
        api_key: document.getElementById("xp-llm-api-key")?.value?.trim(),
        chat_model: document.getElementById("xp-llm-chat-model")?.value?.trim(),
      }),
    });
    const data = await res.json();
    if (data.ok) {
      testStatus.textContent = "\u2713 Verbindung OK";
      testStatus.className = "llm-test-ok";
    } else {
      testStatus.textContent = `\u2717 ${data.error || "Fehler"}`;
      testStatus.className = "llm-test-fail";
    }
  } catch (e) {
    testStatus.textContent = `\u2717 ${String(e)}`;
    testStatus.className = "llm-test-fail";
  } finally {
    btn.disabled = false;
    btn.classList.remove("is-loading");
  }
});

document.getElementById("xp-sign-contract").addEventListener("click", async () => {
  if (!xpSessionId) return xpWrite("Hinweis", { error: "Erst Session erstellen." });
  const signBtn = document.getElementById("xp-sign-contract");
  signBtn.disabled = true;
  signBtn.textContent = "Wird gestartet\u2026";
  try {
    await xpPost(`/api/sessions/${xpSessionId}/sign-contract`, {});
    xpClearDraft();
    window.location.href = `/play/${xpSessionId}`;
  } catch (err) {
    xpWrite("Fehler Signatur", { error: String(err) });
    signBtn.disabled = false;
    signBtn.textContent = "Vertrag signieren und Play-Mode starten";
  }
});

xpRefreshCreateButton();

document.getElementById("xp-pe-avatar-upload")?.addEventListener("click", async () => {
  try {
    await xpUploadAvatar("xp-pe-avatar-file", "persona");
  } catch (err) {
    xpWrite("Fehler Persona-Avatar", { error: String(err) });
  }
});

document.getElementById("xp-player-avatar-upload")?.addEventListener("click", async () => {
  try {
    await xpUploadAvatar("xp-player-avatar-file", "player");
  } catch (err) {
    xpWrite("Fehler Player-Avatar", { error: String(err) });
  }
});



xpLoadPersonaPresets();
xpLoadScenarioPresets();
xpLoadCompletedTemplates();
xpInitDurationDefaults();
xpWireDuration("xp-min-date", "xp-min-days", "xp-min-summary");
xpWireDuration("xp-max-date", "xp-max-days", "xp-max-summary");
xpWireNoLimit();
xpRestoreDraft();
xpSwitchStep(1);
