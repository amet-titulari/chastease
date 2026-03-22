"use strict";

const dashShell = document.querySelector(".dashboard-shell");
const DASH_SESSION_ID = Number(dashShell?.dataset.sessionId || 0);
let dashLockEnd = dashShell?.dataset.lockEnd || "";
let dashHygieneOpeningId = null;
let dashHygieneUsesSeal = false;
let dashHygieneConfiguredDurationSeconds = 900;

function dashEsc(value) {
  return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function dashGet(url) {
  const resp = await fetch(url);
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}

async function dashPost(url, payload) {
  const resp = await fetch(url, {
    method: "POST",
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

function dashFmtDate(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("de-DE");
  } catch (_) {
    return String(value);
  }
}

function dashFmtSecs(secs) {
  if (secs == null || Number.isNaN(Number(secs))) return "—";
  const total = Math.max(0, Number(secs));
  const d = Math.floor(total / 86400);
  const h = Math.floor((total % 86400) / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = Math.floor(total % 60);
  return `${d}d ${h}h ${m}m ${s}s`;
}

function dashFmtRemaining(isoStr) {
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

function dashPillList(id, items, emptyText) {
  const el = document.getElementById(id);
  if (!el) return;
  const list = Array.isArray(items) ? items.filter(Boolean) : [];
  if (!list.length) {
    el.innerHTML = `<span class="dash-empty">${dashEsc(emptyText)}</span>`;
    return;
  }
  el.innerHTML = list.map((item) => `<span class="dash-pill">${dashEsc(item)}</span>`).join("");
}

function dashRenderRoleplayState(roleplayState) {
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

  dashSetText("dash-scene-pressure", scene.pressure || "—");
  dashSetText("dash-scene-title", sceneHeading);
  dashSetText("dash-scene-objective", scene.objective || "—");
  dashSetText("dash-scene-next-beat", scene.next_beat || "—");
  dashSetText("dash-scene-consequence", scene.last_consequence || "keine");
  dashSetText("dash-control-level", relationship.control_level || "structured");

  const meterEl = document.getElementById("dash-relationship-meters");
  if (meterEl) {
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
      const safe = Math.max(0, Math.min(100, Number(value) || 0));
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
        <div class="dash-meter">
          <div class="dash-meter-top">
            <span>${dashEsc(label)}</span>
            <strong>${safe}</strong>
          </div>
          <div class="dash-meter-track">
            <span class="dash-meter-fill dash-meter-fill--base" style="width:${baseWidth}%"></span>
            ${growthWidth > 0 ? `<span class="dash-meter-fill dash-meter-fill--growth" style="left:${baseWidth}%;width:${growthWidth}%"></span>` : ""}
            ${targetMarker != null ? `<span class="dash-meter-target" style="left:${targetMarker}%"></span>` : ""}
          </div>
          <div class="dash-meter-meta">
            <span class="dash-meter-delta ${deltaClass}${resistanceClass}">Seit Start: ${deltaText}</span>
            <span class="dash-meter-phase">${dashEsc(phase.label)}</span>
          </div>
        </div>
      `;
    };
    const metricDefs = [
      ["Trust", "trust"],
      ["Obedience", "obedience"],
      ["Resistance", "resistance"],
      ["Favor", "favor"],
      ["Strictness", "strictness"],
      ["Frustration", "frustration"],
      ["Attachment", "attachment"],
    ];
    meterEl.innerHTML = [
      ...metricDefs.map(([label, key]) => metric(label, relationship[key], key)),
    ].join("");
  }

  dashPillList("dash-active-rules", protocol.active_rules, "Keine aktiven Regeln");
  dashPillList("dash-open-orders", protocol.open_orders, "Keine offenen Anweisungen");
}

function dashRenderRelationshipMemory(memory) {
  const safeMemory = memory || {};
  const sessionsConsidered = Number(safeMemory.sessions_considered || 0);
  const highlights = Array.isArray(safeMemory.highlights) ? safeMemory.highlights.filter(Boolean) : [];

  dashSetText("dash-memory-count", sessionsConsidered);
  dashSetText("dash-memory-control", safeMemory.dominant_control_level || "noch offen");
  dashSetText(
    "dash-memory-summary",
    sessionsConsidered > 0
      ? safeMemory.summary || "Langzeitdynamik verfuegbar."
      : "Noch keine abgeschlossenen Vergleichssessions."
  );
  dashSetText(
    "dash-memory-highlights",
    highlights.length ? highlights.join(" • ") : (sessionsConsidered > 0 ? "Noch keine markante Tendenz." : "—")
  );
}

function dashRenderHygieneQuota(quotaData) {
  const el = document.getElementById("dash-hygiene-quota");
  const nextEl = document.getElementById("dash-hygiene-next-allowed");
  if (!el || !quotaData) return;
  const limits = quotaData.limits || {};
  const used = quotaData.used || {};
  const remaining = quotaData.remaining || {};
  const nextAllowedAt = quotaData.next_allowed_at || {};
  const fmt = (v) => (v == null ? "unbegrenzt" : String(v));
  el.textContent =
    `Kontingent - Tag: ${fmt(used.daily)}/${fmt(limits.daily)} (rest ${fmt(remaining.daily)}), ` +
    `Woche: ${fmt(used.weekly)}/${fmt(limits.weekly)} (rest ${fmt(remaining.weekly)}), ` +
    `Monat: ${fmt(used.monthly)}/${fmt(limits.monthly)} (rest ${fmt(remaining.monthly)})`;

  if (!nextEl) return;
  if (nextAllowedAt.overall) {
    nextEl.textContent = `Naechste Oeffnung erlaubt ab: ${dashFmtDate(nextAllowedAt.overall)}`;
    return;
  }
  nextEl.textContent = "";
}

async function dashLoadSummary() {
  const data = await dashGet(`/api/settings/summary?session_id=${DASH_SESSION_ID}`);
  const s = data.session || {};
  dashLockEnd = s.lock_end || dashLockEnd;
  dashUpdateCountdown();
  dashSetAvatar("dash-keyholder-avatar", s.persona_avatar_url || null);
  dashSetAvatar("dash-player-avatar", s.player_avatar_url || null);
  dashSetText("dash-wearer", s.player_nickname);
  dashSetText("dash-keyholder", s.persona_name);
  dashSetText("dash-session-id", s.session_id ? `#${s.session_id}` : "—");
  dashSetText("dash-status-pill", s.status || "—");
  dashSetText("dash-status-text", s.status || "—");
  dashSetText("dash-lock-start", dashFmtDate(s.lock_start));
  dashSetText("dash-lock-end", dashFmtDate(s.lock_end));
  dashSetText("dash-timer-frozen", s.timer_frozen ? "eingefroren" : "laufend");
  dashSetText("dash-min-duration", dashFmtSecs(s.min_duration_seconds));
  dashSetText("dash-max-duration", s.max_duration_seconds ? dashFmtSecs(s.max_duration_seconds) : "—");
  dashSetText("dash-active-seal", s.active_seal_number || "—");
  dashSetText(
    "dash-last-opening",
    s.last_opening_status
      ? `${s.last_opening_status}${s.last_opening_due_back_at ? ` (Rueckgabe: ${dashFmtDate(s.last_opening_due_back_at)})` : ""}`
      : "—"
  );
  dashSetText("dash-total-played", dashFmtSecs(s.total_played_seconds));
  dashSetText("dash-exp", data.experience_level);
  dashSetText("dash-style", data.style);
  dashSetText("dash-goal", data.goal);
  dashSetText("dash-boundary", data.boundary);
  dashSetText(
    "dash-task-stats",
    `Gesamt: ${s.task_total ?? 0} | pending: ${s.task_pending ?? 0} | completed: ${s.task_completed ?? 0} | overdue: ${s.task_overdue ?? 0} | failed: ${s.task_failed ?? 0}`
  );
  dashSetText("dash-task-penalty", dashFmtSecs(s.task_penalty_total_seconds));
  dashSetText("dash-hygiene-penalty", `${dashFmtSecs(s.hygiene_penalty_total_seconds)} (Overrun: ${dashFmtSecs(s.hygiene_overrun_total_seconds)})`);
  dashSetText("dash-llm-provider", data.llm?.provider || "—");
  dashSetText("dash-llm-chat", data.llm?.chat_model || "—");
  dashSetText("dash-llm-key", data.llm?.api_key_stored ? "hinterlegt" : "nicht gesetzt");

  const rulesEl = document.getElementById("dash-hygiene-rules");
  if (rulesEl) {
    const maxMinutes = Math.max(1, Math.floor(Number(s.hygiene_opening_max_duration_seconds || 900) / 60));
    rulesEl.textContent =
      `Regeln: Maximaldauer ${maxMinutes} Minuten. Bei Ueberziehung gilt Penalty = max(Overrun, ${dashFmtSecs(s.hygiene_overdue_penalty_min_seconds)}).`;
  }
  dashHygieneConfiguredDurationSeconds = Math.max(60, Math.round(Number(s.hygiene_opening_max_duration_seconds || 900)));
}

async function dashLoadSessionState() {
  const data = await dashGet(`/api/sessions/${DASH_SESSION_ID}`);
  if (data.roleplay_state) dashRenderRoleplayState(data.roleplay_state);
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
  document.getElementById("dash-hygiene-open-area")?.classList.toggle("is-hidden", phase === "relock");
  document.getElementById("dash-hygiene-relock-area")?.classList.toggle("is-hidden", phase !== "relock");
  document.getElementById("dash-hygiene-seal-row")?.classList.toggle("is-hidden", !(phase === "relock" && dashHygieneUsesSeal));
}

async function dashHandleSafety(action) {
  const endpoint = action === "safeword"
    ? `/api/sessions/${DASH_SESSION_ID}/safety/safeword`
    : `/api/sessions/${DASH_SESSION_ID}/safety/traffic-light`;
  const payload = action === "safeword" ? {} : { color: action };
  await dashPost(endpoint, payload);
  await dashLoadSummary();
}

function dashModuleName(key) {
  return {
    posture_training: "Posture Training",
    dont_move: "Don't Move",
    tiptoeing: "Tiptoeing",
  }[key] || key;
}

function dashDiffLabel(key) {
  return { easy: "Leicht", medium: "Mittel", hard: "Schwer" }[key] || key;
}

function dashRunBadge(run) {
  if (run.status !== "completed") return ["active", run.status];
  if (run.failed_steps === 0 && run.unplayed_steps === 0) return ["ok", "Bestanden"];
  if (run.unplayed_steps > 0 && run.failed_steps === 0) return ["warn", "Unvollstaendig"];
  return ["fail", "Fehler"];
}

async function dashLoadRunReport(runId, bodyEl) {
  const run = await dashGet(`/api/games/runs/${runId}`);
  const summary = run.summary || {};
  const checks = Array.isArray(summary.checks) ? summary.checks : [];
  const steps = Array.isArray(run.steps) ? run.steps : [];
  const total = Number(summary.total_steps || 0);
  const scheduled = Number(summary.scheduled_steps || total);
  const unplayed = Number(summary.unplayed_steps || Math.max(0, scheduled - total));
  const passed = Number(summary.passed_steps || 0);
  const failed = Number(summary.failed_steps || 0);
  const misses = Number(summary.miss_count || run.miss_count || 0);
  const penaltyApplied = Boolean(summary.session_penalty_applied);
  const endReason = summary.end_reason === "time_elapsed" ? "Zeit abgelaufen" : "Alle Schritte abgeschlossen";
  const checksWithImages = checks.filter((entry) => entry && entry.capture_url);
  const checksWithoutImages = checks.filter((entry) => entry && !entry.capture_url);

  let html = `<div class="dash-run-stats">
    <span>Beendigung: <strong>${dashEsc(endReason)}</strong></span>
    <span>Gespielt: <strong>${passed}/${total}</strong></span>
    <span>Fehler: <strong>${failed}</strong></span>
    <span>Verfehlungen: <strong>${misses}</strong></span>
    <span>Checks: <strong>${checks.length}</strong></span>
    ${unplayed > 0 ? `<span>Nicht gespielt: <strong>${unplayed}/${scheduled}</strong></span>` : ""}
    ${penaltyApplied ? `<span>Session-Penalty ausgeloest</span>` : ""}
  </div>`;

  if (summary.ai_assessment) {
    html += `<div class="dash-run-ai">${dashEsc(summary.ai_assessment)}</div>`;
  }
  if (failed > 0 && misses === 0 && checks.length === 0) {
    html += `<div class="dash-run-note">Run fehlgeschlagen, aber ohne serverseitigen Check-Eintrag. Das spricht fuer ein Upload- oder Persistenzproblem im Live-Run.</div>`;
  }
  if (steps.length) {
    html += `<div class="dash-run-steps">`;
    steps.forEach((step, index) => {
      html += `<article class="dash-run-step">
        <div><strong>${index + 1}. ${dashEsc(step.posture_name || "Pose")}</strong></div>
        <div>Status: ${dashEsc(step.status || "unknown")} · Verifikationen: ${Number(step.verification_count || 0)}</div>
        <div>${dashEsc(step.last_analysis || "Keine serverseitige Analyse gespeichert.")}</div>
      </article>`;
    });
    html += `</div>`;
  }
  if (checksWithImages.length || checksWithoutImages.length) {
    html += `<div class="dash-run-checks">`;
    checksWithImages.forEach((entry, index) => {
      html += `<article class="dash-run-check">
        <img src="${dashEsc(entry.capture_url || "")}" alt="Kontrollbild ${index + 1}" onclick="window.open('${dashEsc(entry.capture_url || "")}','_blank')" />
        <div><strong>${dashEsc(entry.posture_name || "Pose")}</strong></div>
        <div>${dashEsc(entry.analysis || "—")}</div>
      </article>`;
    });
    checksWithoutImages.forEach((entry) => {
      html += `<article class="dash-run-check">
        <div><strong>${dashEsc(entry.posture_name || "Pose")}</strong></div>
        <div>${dashEsc(entry.analysis || "—")}</div>
      </article>`;
    });
    html += `</div>`;
  } else {
    html += `<p class="dash-copy">Keine gespeicherten Kontrollbilder.</p>`;
  }
  bodyEl.innerHTML = html;
}

async function dashLoadRunHistory() {
  const listEl = document.getElementById("dash-runs-list");
  if (!listEl) return;
  try {
    const data = await dashGet(`/api/games/sessions/${DASH_SESSION_ID}/runs`);
    const items = data.items || [];
    if (!items.length) {
      listEl.innerHTML = "<p class='dash-copy'>Noch keine Spiele in dieser Session.</p>";
      return;
    }
    listEl.innerHTML = `<div class="dash-run-list"></div>`;
    const runList = listEl.querySelector(".dash-run-list");
    items.forEach((run) => {
      const [badgeClass, badgeLabel] = dashRunBadge(run);
      const card = document.createElement("article");
      card.className = "dash-run-card";
      card.innerHTML = `
        <button class="dash-run-head" type="button">
          <div class="dash-run-title">
            <strong>${dashEsc(dashModuleName(run.module_key))}</strong>
            <span class="dash-run-meta">${dashEsc(dashDiffLabel(run.difficulty_key))} · ${dashEsc(dashFmtDate(run.effective_started_at || run.started_at))} · ${dashEsc(dashFmtSecs(run.elapsed_duration_seconds || 0))}</span>
          </div>
          <span class="dash-run-badge ${badgeClass}">${dashEsc(badgeLabel)}</span>
        </button>
        <div class="dash-run-body"><p class="dash-copy">Wird geladen …</p></div>
      `;
      const head = card.querySelector(".dash-run-head");
      const body = card.querySelector(".dash-run-body");
      head?.addEventListener("click", async () => {
        const isOpen = card.hasAttribute("open");
        if (isOpen) {
          card.removeAttribute("open");
          return;
        }
        card.setAttribute("open", "");
        if (body?.dataset.loaded !== "1") {
          await dashLoadRunReport(run.id, body);
          body.dataset.loaded = "1";
        }
      });
      runList?.appendChild(card);
    });
  } catch (err) {
    listEl.innerHTML = `<p class='dash-copy'>Fehler beim Laden: ${dashEsc(String(err))}</p>`;
  }
}

document.getElementById("dash-hygiene-open")?.addEventListener("click", async () => {
  const btn = document.getElementById("dash-hygiene-open");
  const statusEl = document.getElementById("dash-hygiene-status");
  if (btn) btn.disabled = true;
  try {
    let oldSealNumber = null;
    try {
      const sealData = await dashGet(`/api/sessions/${DASH_SESSION_ID}/seal-history`);
      const active = (sealData.entries || []).find((item) => item.status === "active");
      if (active) oldSealNumber = active.seal_number;
    } catch (_) {}
    dashHygieneUsesSeal = Boolean(oldSealNumber);
    const data = await dashPost(`/api/sessions/${DASH_SESSION_ID}/hygiene/openings`, {
      duration_seconds: Math.max(60, Math.round(Number(dashHygieneConfiguredDurationSeconds) || 900)),
      old_seal_number: oldSealNumber,
    });
    dashHygieneOpeningId = data.opening_id;
    if (statusEl) statusEl.textContent = `Rueck bis: ${dashFmtDate(data.due_back_at)}`;
    dashRenderHygieneQuota(data.quota);
    dashSetHygienePhase("relock");
    await dashLoadSummary();
  } catch (err) {
    if (statusEl) statusEl.textContent = `Fehler: ${String(err)}`;
  } finally {
    if (btn) btn.disabled = false;
  }
});

document.getElementById("dash-hygiene-relock")?.addEventListener("click", async () => {
  const btn = document.getElementById("dash-hygiene-relock");
  const statusEl = document.getElementById("dash-hygiene-status");
  if (!dashHygieneOpeningId) return;
  let newSeal = null;
  if (dashHygieneUsesSeal) {
    newSeal = document.getElementById("dash-hygiene-new-seal")?.value?.trim();
    if (!newSeal) {
      if (statusEl) statusEl.textContent = "Neue Plombennummer ist erforderlich.";
      return;
    }
  }
  if (btn) btn.disabled = true;
  try {
    await dashPost(`/api/sessions/${DASH_SESSION_ID}/hygiene/openings/${dashHygieneOpeningId}/relock`, {
      new_seal_number: newSeal,
    });
    dashHygieneOpeningId = null;
    dashHygieneUsesSeal = false;
    dashSetHygienePhase("open");
    dashSetText("dash-hygiene-status", "Wiederverschlossen");
    const sealInput = document.getElementById("dash-hygiene-new-seal");
    if (sealInput) sealInput.value = "";
    await dashLoadSummary();
    await dashLoadHygieneQuota();
  } catch (err) {
    if (statusEl) statusEl.textContent = `Fehler: ${String(err)}`;
  } finally {
    if (btn) btn.disabled = false;
  }
});

document.getElementById("dash-resume-session")?.addEventListener("click", async () => {
  const btn = document.getElementById("dash-resume-session");
  if (btn) btn.disabled = true;
  try {
    await dashPost(`/api/sessions/${DASH_SESSION_ID}/safety/resume`, {});
    await dashLoadSummary();
    if (btn) btn.remove();
  } catch (err) {
    if (btn) btn.disabled = false;
  }
});

document.getElementById("dash-safety-green")?.addEventListener("click", () => dashHandleSafety("green"));
document.getElementById("dash-safety-yellow")?.addEventListener("click", () => dashHandleSafety("yellow"));
document.getElementById("dash-safety-red")?.addEventListener("click", () => dashHandleSafety("red"));
document.getElementById("dash-safety-safeword")?.addEventListener("click", () => dashHandleSafety("safeword"));

document.addEventListener("DOMContentLoaded", async () => {
  if (!DASH_SESSION_ID) return;
  dashUpdateCountdown();
  setInterval(dashUpdateCountdown, 1000);
  await dashLoadSummary();
  await dashLoadSessionState();
  await dashLoadHygieneQuota();
  await dashLoadRunHistory();
  setInterval(() => {
    dashLoadSessionState().catch(() => {});
  }, 8000);
});
