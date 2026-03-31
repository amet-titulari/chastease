"use strict";

const dashShell = document.querySelector(".dashboard-shell");
const DASH_SESSION_ID = Number(dashShell?.dataset.sessionId || 0);
let dashPersonaId = Number(dashShell?.dataset.personaId || 0);
let dashPersonaMissing = String(dashShell?.dataset.personaMissing || "") === "1";
let dashLockEnd = dashShell?.dataset.lockEnd || "";
let dashHygieneOpeningId = null;
let dashHygieneUsesSeal = false;
let dashHygieneConfiguredDurationSeconds = 900;
const dashRuntime = window.ChasteaseUiRuntime || {};

function dashEsc(value) {
  return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function dashGet(url) {
  if (typeof dashRuntime.jsonGet === "function") {
    return dashRuntime.jsonGet(url);
  }
  const resp = await fetch(url);
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}

async function dashPost(url, payload) {
  if (typeof dashRuntime.jsonSend === "function") {
    return dashRuntime.jsonSend(url, "POST", payload);
  }
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}

async function dashPut(url, payload) {
  if (typeof dashRuntime.jsonSend === "function") {
    return dashRuntime.jsonSend(url, "PUT", payload);
  }
  const resp = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}

function dashSetText(id, value, fallback = "—") {
  const el = document.getElementById(id);
  if (el) el.textContent = value == null || value === "" ? fallback : String(value);
}

function dashSetPersonaLabel(name) {
  dashSetText("dash-keyholder", name);
  dashSetText("dash-hero-persona", name);
  if (dashShell) dashShell.dataset.personaName = name || "";
}

function dashFmtDate(value) {
  if (typeof dashRuntime.formatDateTime === "function") {
    return dashRuntime.formatDateTime(value, "de-DE", "—");
  }
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("de-DE");
  } catch (_) {
    return String(value);
  }
}

function dashFmtSecs(secs) {
  if (typeof dashRuntime.formatDurationSeconds === "function") {
    return dashRuntime.formatDurationSeconds(secs, "—");
  }
  if (secs == null || Number.isNaN(Number(secs))) return "—";
  const total = Math.max(0, Number(secs));
  const d = Math.floor(total / 86400);
  const h = Math.floor((total % 86400) / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = Math.floor(total % 60);
  return `${d}d ${h}h ${m}m ${s}s`;
}

function dashFmtRemaining(isoStr) {
  if (typeof dashRuntime.formatRemaining === "function") {
    return dashRuntime.formatRemaining(isoStr, { expiredLabel: "Frei", fallback: "—" });
  }
  if (!isoStr) return "—";
  const diff = new Date(isoStr).getTime() - Date.now();
  if (diff <= 0) return "Frei";
  const d = Math.floor(diff / 86400000);
  const h = Math.floor((diff % 86400000) / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  const s = Math.floor((diff % 60000) / 1000);
  if (h > 0) return `${h}h ${m}m ${s}s`;
  return `${m}m ${s}s`;
}

function dashUpdateCountdown() {
  dashSetText("dash-countdown", dashFmtRemaining(dashLockEnd));
}

function dashSetAvatar(id, url) {
  const img = document.getElementById(id);
  if (!img) return;
  if (url) {
    img.src = url;
    img.classList.remove("is-hidden");
  } else {
    img.classList.add("is-hidden");
  }
}

function dashRenderRoleplayState(roleplayState, phaseProgress = {}) {
  const roleplayUi = window.ChasteaseDashboardRoleplayUI || {};
  if (typeof roleplayUi.renderRoleplayState === "function") {
    roleplayUi.renderRoleplayState(roleplayState, phaseProgress, {
      escapeHtml: dashEsc,
      setText: dashSetText,
    });
  }
}

function dashRenderRelationshipMemory(memory) {
  const roleplayUi = window.ChasteaseDashboardRoleplayUI || {};
  if (typeof roleplayUi.renderRelationshipMemory === "function") {
    roleplayUi.renderRelationshipMemory(memory, { setText: dashSetText });
  }
}

function dashRenderHygieneQuota(quotaData) {
  const hygieneUi = window.ChasteaseDashboardHygieneUI || {};
  if (typeof hygieneUi.renderHygieneQuota === "function") {
    hygieneUi.renderHygieneQuota(quotaData, { formatDate: dashFmtDate });
  }
}

async function dashLoadSummary() {
  const data = await dashGet(`/api/settings/summary?session_id=${DASH_SESSION_ID}`);
  const s = data.session || {};
  dashLockEnd = s.lock_end || dashLockEnd;
  dashUpdateCountdown();
  const sessionUi = window.ChasteaseDashboardSessionUI || {};
  if (typeof sessionUi.renderSummary === "function") {
    sessionUi.renderSummary(data, {
      setText: dashSetText,
      setAvatar: dashSetAvatar,
      setPersonaLabel: dashSetPersonaLabel,
      formatDate: dashFmtDate,
      formatSecs: dashFmtSecs,
    });
  }
  dashHygieneConfiguredDurationSeconds = Math.max(60, Math.round(Number(s.hygiene_opening_max_duration_seconds || 900)));
}

async function dashLoadPersonas() {
  const select = document.getElementById("dash-persona-select");
  if (!select) return;
  try {
    const data = await dashGet("/api/personas");
    const items = Array.isArray(data.items) ? data.items : [];
    const sessionUi = window.ChasteaseDashboardSessionUI || {};
    if (typeof sessionUi.renderPersonaOptions === "function") {
      sessionUi.renderPersonaOptions(items, {
        escapeHtml: dashEsc,
        selectedPersonaId: dashPersonaId,
      });
    }
  } catch (err) {
    select.innerHTML = '<option value="">Personas konnten nicht geladen werden</option>';
  }
}

async function dashSavePersona() {
  const select = document.getElementById("dash-persona-select");
  const btn = document.getElementById("dash-persona-save");
  const note = document.getElementById("dash-persona-note");
  const nextPersonaId = Number(select?.value || 0);
  if (!nextPersonaId) {
    if (note) {
      note.textContent = "Bitte zuerst eine gespeicherte Keyholderin auswaehlen.";
      note.classList.remove("is-hidden");
    }
    return;
  }
  if (btn) btn.disabled = true;
  try {
    const data = await dashPut(`/api/sessions/${DASH_SESSION_ID}/persona`, { persona_id: nextPersonaId });
    dashPersonaId = Number(data.persona_id || nextPersonaId);
    dashPersonaMissing = false;
    dashSetPersonaLabel(data.persona_name || "");
    if (dashShell) {
      dashShell.dataset.personaId = String(dashPersonaId);
      dashShell.dataset.personaMissing = "0";
    }
    if (note) {
      note.textContent = `Keyholderin gewechselt zu ${data.persona_name}.`;
      note.classList.remove("is-hidden");
    }
    await dashLoadSummary();
  } catch (err) {
    if (note) {
      note.textContent = `Persona konnte nicht gesetzt werden (${String(err)})`;
      note.classList.remove("is-hidden");
    }
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function dashLoadSessionState() {
  const data = await dashGet(`/api/sessions/${DASH_SESSION_ID}`);
  if (data.roleplay_state) dashRenderRoleplayState(data.roleplay_state, data.phase_progress || {});
  dashRenderRelationshipMemory(data.relationship_memory || {});
}

async function dashLoadHygieneQuota() {
  try {
    const data = await dashGet(`/api/sessions/${DASH_SESSION_ID}/hygiene/quota`);
    dashRenderHygieneQuota(data);
  } catch (err) {
    dashSetText("dash-hygiene-quota", `Kontingent konnte nicht geladen werden (${String(err)})`);
  }
}

function dashSetHygienePhase(phase) {
  const hygieneUi = window.ChasteaseDashboardHygieneUI || {};
  if (typeof hygieneUi.setHygienePhase === "function") {
    hygieneUi.setHygienePhase(phase, { usesSeal: dashHygieneUsesSeal });
  }
}

async function dashLoadRunReport(runId, bodyEl) {
  const run = await dashGet(`/api/games/runs/${runId}`);
  const runsUi = window.ChasteaseDashboardRunsUI || {};
  if (typeof runsUi.renderRunReport === "function") {
    bodyEl.innerHTML = runsUi.renderRunReport(run, { escapeHtml: dashEsc });
  }
}

async function dashLoadRunHistory() {
  const listEl = document.getElementById("dash-runs-list");
  if (!listEl) return;
  try {
    const data = await dashGet(`/api/games/sessions/${DASH_SESSION_ID}/runs`);
    const items = data.items || [];
    const runsUi = window.ChasteaseDashboardRunsUI || {};
    if (typeof runsUi.renderRunHistory === "function") {
      runsUi.renderRunHistory(items, {
        listEl,
        escapeHtml: dashEsc,
        formatDate: dashFmtDate,
        formatSecs: dashFmtSecs,
        loadRunReport: dashLoadRunReport,
      });
    }
  } catch (err) {
    listEl.innerHTML = `<p class='dash-copy'>Fehler beim Laden: ${dashEsc(String(err))}</p>`;
  }
}

function dashBindEvents() {
  document.getElementById("dash-persona-save")?.addEventListener("click", () => {
    dashSavePersona().catch(() => {});
  });
}

async function dashBoot() {
  if (!DASH_SESSION_ID) return;
  const safetyUi = window.ChasteaseDashboardSafetyUI || {};
  if (typeof safetyUi.bindSafetyAndHygiene === "function") {
    safetyUi.bindSafetyAndHygiene({
      state: {
        get hygieneOpeningId() { return dashHygieneOpeningId; },
        set hygieneOpeningId(value) { dashHygieneOpeningId = value; },
        get hygieneUsesSeal() { return dashHygieneUsesSeal; },
        set hygieneUsesSeal(value) { dashHygieneUsesSeal = Boolean(value); },
        get hygieneConfiguredDurationSeconds() { return dashHygieneConfiguredDurationSeconds; },
      },
      sessionId: DASH_SESSION_ID,
      get: dashGet,
      post: dashPost,
      renderQuota: dashRenderHygieneQuota,
      setPhase: dashSetHygienePhase,
      setText: dashSetText,
      loadSummary: dashLoadSummary,
      loadHygieneQuota: dashLoadHygieneQuota,
      formatDate: dashFmtDate,
    });
  }
  dashUpdateCountdown();
  if (typeof dashRuntime.startPolling === "function") {
    dashRuntime.startPolling(dashUpdateCountdown, 1000);
  } else {
    setInterval(dashUpdateCountdown, 1000);
  }
  await dashLoadPersonas();
  await dashLoadSummary();
  await dashLoadSessionState();
  await dashLoadHygieneQuota();
  await dashLoadRunHistory();
  if (typeof dashRuntime.startPolling === "function") {
    dashRuntime.startPolling(dashLoadSessionState, 8000);
  } else {
    setInterval(() => {
      dashLoadSessionState().catch(() => {});
    }, 8000);
  }
}

dashBindEvents();
document.addEventListener("DOMContentLoaded", () => {
  dashBoot().catch(() => {});
});
