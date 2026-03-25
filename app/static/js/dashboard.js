"use strict";

const dashShell = document.querySelector(".dashboard-shell");
const DASH_SESSION_ID = Number(dashShell?.dataset.sessionId || 0);
let dashPersonaId = Number(dashShell?.dataset.personaId || 0);
let dashPersonaMissing = String(dashShell?.dataset.personaMissing || "") === "1";
let dashLockEnd = dashShell?.dataset.lockEnd || "";
let dashHygieneOpeningId = null;
let dashHygieneUsesSeal = false;
let dashHygieneConfiguredDurationSeconds = 900;
const dashLovenseEnabled = String(dashShell?.dataset.lovenseEnabled || "") === "1";
const dashLovenseConfigured = String(dashShell?.dataset.lovenseConfigured || "") === "1";
const dashLovensePlatform = String(dashShell?.dataset.lovensePlatform || "").trim();
const dashLovenseAppType = String(dashShell?.dataset.lovenseAppType || "connect").trim() || "connect";
const dashLovenseDebug = String(dashShell?.dataset.lovenseDebug || "") === "1";
let dashLovenseSdk = null;
let dashLovenseBootstrap = null;
let dashLovenseToys = [];
let dashLovensePollHandle = null;
let dashLovenseSequenceTimeout = null;

const DASH_LOVENSE_PRESETS = {
  tease_ramp: {
    label: "Tease Ramp",
    kind: "pattern",
    description: "Sanfter Aufbau ueber mehrere Stufen, dann kurzer Rueckzug.",
    pattern: (intensity) => {
      const level = Math.max(1, Math.min(20, intensity));
      const low = Math.max(1, Math.round(level * 0.35));
      const mid = Math.max(1, Math.round(level * 0.6));
      const high = Math.max(1, Math.round(level * 0.85));
      return `${low};${mid};${high};${level};${high};${mid}`;
    },
    interval: 220,
  },
  strict_pulse: {
    label: "Strict Pulse",
    kind: "pattern",
    description: "Kurze harte Impulse mit klaren Pausen dazwischen.",
    pattern: (intensity) => {
      const level = Math.max(1, Math.min(20, intensity));
      return `0;${level};0;${level};0;${Math.max(1, Math.round(level * 0.75))}`;
    },
    interval: 160,
  },
  wave_ladder: {
    label: "Wave Ladder",
    kind: "pattern",
    description: "Glaettende Wellenbewegung mit progressiver Leiter.",
    pattern: (intensity) => {
      const level = Math.max(1, Math.min(20, intensity));
      const one = Math.max(1, Math.round(level * 0.3));
      const two = Math.max(1, Math.round(level * 0.5));
      const three = Math.max(1, Math.round(level * 0.7));
      return `${one};${two};${three};${level};${three};${two};${one};0`;
    },
    interval: 210,
  },
  deny_spikes: {
    label: "Deny Spikes",
    kind: "pattern",
    description: "Unregelmaessige Spitzen mit abruptem Wegbrechen.",
    pattern: (intensity) => {
      const level = Math.max(1, Math.min(20, intensity));
      const spike = Math.max(1, Math.round(level * 0.9));
      const low = Math.max(1, Math.round(level * 0.25));
      return `${low};${spike};0;${low};${level};0;${spike};0`;
    },
    interval: 150,
  },
};

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

async function dashPut(url, payload) {
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

function dashSetLovenseStatus(message, pill = null) {
  const el = document.getElementById("dash-lovense-status");
  if (el) el.textContent = message || "—";
  const chip = document.getElementById("dash-lovense-app-pill");
  if (chip && pill) chip.textContent = pill;
}

function dashUpdateLovenseIntensityLabel() {
  const input = document.getElementById("dash-lovense-intensity");
  const el = document.getElementById("dash-lovense-intensity-value");
  if (!input || !el) return;
  const intensity = Math.max(1, Math.min(20, Number(input.value || 8)));
  el.textContent = `${intensity}/20`;
}

function dashSelectedLovensePreset() {
  const presetId = String(document.getElementById("dash-lovense-preset")?.value || "").trim();
  return DASH_LOVENSE_PRESETS[presetId] || null;
}

function dashUpdateLovensePresetCopy() {
  const el = document.getElementById("dash-lovense-preset-copy");
  if (!el) return;
  const preset = dashSelectedLovensePreset();
  el.textContent = preset
    ? `${preset.label}: ${preset.description}`
    : "Kurze Bibliothek fuer erste Routinen. Ein visueller Pattern-Designer kann spaeter darauf aufbauen.";
}

function dashSetLovenseQrVisible(visible) {
  const wrap = document.getElementById("dash-lovense-qr-wrap");
  if (!wrap) return;
  wrap.classList.toggle("is-hidden", !visible);
}

function dashLovenseCommandSettings() {
  const intensity = Math.max(1, Math.min(20, Number(document.getElementById("dash-lovense-intensity")?.value || 8)));
  const duration = Math.max(1, Math.min(300, Number(document.getElementById("dash-lovense-duration")?.value || 20)));
  const pause = Math.max(0, Math.min(300, Number(document.getElementById("dash-lovense-pause")?.value || 5)));
  const loops = Math.max(1, Math.min(20, Number(document.getElementById("dash-lovense-loops")?.value || 1)));
  return { intensity, duration, pause, loops };
}

function dashClearLovenseSequence() {
  if (dashLovenseSequenceTimeout) {
    window.clearTimeout(dashLovenseSequenceTimeout);
    dashLovenseSequenceTimeout = null;
  }
}

function dashSelectedLovenseToyId() {
  return String(document.getElementById("dash-lovense-toy-select")?.value || "").trim();
}

function dashRenderLovenseToys(toys) {
  dashLovenseToys = Array.isArray(toys) ? toys.filter(Boolean) : [];
  const select = document.getElementById("dash-lovense-toy-select");
  const meta = document.getElementById("dash-lovense-toy-meta");
  if (!select) return;
  if (!dashLovenseToys.length) {
    select.innerHTML = '<option value="">Noch kein Toy verbunden</option>';
    if (meta) meta.textContent = "Kein Lovense-Toy aktiv. Verbinde den Edge 2 ueber die Lovense Connect App.";
    dashSetLovenseQrVisible(true);
    return;
  }
  const options = dashLovenseToys.map((toy, idx) => {
    const id = String(toy.id || toy.toyId || toy.toy_id || idx);
    const name = String(toy.name || toy.nickName || toy.nickname || toy.type || "Toy");
    const state = String(toy.status || toy.connectStatus || toy.connection || "verbunden");
    return `<option value="${dashEsc(id)}">${dashEsc(name)} (${dashEsc(state)})</option>`;
  });
  select.innerHTML = options.join("");
  const chosen = dashSelectedLovenseToyId() || String(dashLovenseToys[0].id || dashLovenseToys[0].toyId || dashLovenseToys[0].toy_id || "");
  if (chosen) select.value = chosen;
  const active = dashLovenseToys.find((toy) => String(toy.id || toy.toyId || toy.toy_id || "") === select.value) || dashLovenseToys[0];
  if (meta && active) {
    const label = String(active.name || active.nickName || active.nickname || active.type || "Toy");
    const battery = active.battery != null ? ` · Akku ${active.battery}%` : "";
    const version = active.version ? ` · ${active.version}` : "";
    meta.textContent = `${label}${battery}${version}`;
  }
  dashSetLovenseQrVisible(false);
}

async function dashLoadLovenseBootstrap() {
  const data = await dashPost(`/api/lovense/sessions/${DASH_SESSION_ID}/bootstrap`, {});
  dashLovenseBootstrap = data;
  return data;
}

function dashResolveLovenseQr(payload) {
  if (!payload || typeof payload !== "object") return "";
  return String(payload.qrcodeUrl || payload.qrCodeUrl || payload.url || payload.qrcode || "").trim();
}

async function dashRefreshLovenseQr() {
  if (!dashLovenseSdk || typeof dashLovenseSdk.getQrcode !== "function") return;
  try {
    const qr = await dashLovenseSdk.getQrcode();
    const qrUrl = dashResolveLovenseQr(qr);
    const img = document.getElementById("dash-lovense-qr");
    if (img && qrUrl) {
      img.src = qrUrl;
      img.classList.remove("is-hidden");
      dashSetLovenseQrVisible(true);
    }
  } catch (err) {
    dashSetLovenseStatus(`Lovense QR fehlgeschlagen (${String(err)})`, "Fehler");
  }
}

function dashLovensePatternStrength(intensity, mode) {
  const level = Math.max(1, Math.min(20, Number(intensity) || 8));
  if (mode === "pulse") {
    return `0;${level};0;${Math.max(1, Math.round(level * 0.85))};0;${level}`;
  }
  return `0;${Math.max(1, Math.round(level * 0.45))};${Math.max(1, Math.round(level * 0.7))};${level};${Math.max(1, Math.round(level * 0.7))};${Math.max(1, Math.round(level * 0.45))}`;
}

async function dashExecuteLovenseSegment(kind, payload) {
  if (!dashLovenseSdk) {
    throw new Error("Lovense ist noch nicht initialisiert.");
  }
  if (kind === "vibrate") {
    if (typeof dashLovenseSdk.sendToyCommand !== "function") {
      throw new Error("sendToyCommand wird vom geladenen SDK nicht angeboten.");
    }
    await dashLovenseSdk.sendToyCommand(payload);
    return;
  }
  if (kind === "pattern") {
    if (typeof dashLovenseSdk.sendPatternCommand !== "function") {
      throw new Error("sendPatternCommand wird vom geladenen SDK nicht angeboten.");
    }
    await dashLovenseSdk.sendPatternCommand(payload);
    return;
  }
  throw new Error(`Lovense-Segmenttyp wird nicht unterstuetzt: ${kind}`);
}

async function dashRunLovenseProgram(program) {
  const toyId = dashSelectedLovenseToyId();
  if (!toyId) {
    dashSetLovenseStatus("Bitte zuerst ein verbundenes Toy waehlen.", "Toy");
    return;
  }
  dashClearLovenseSequence();
  const { intensity, duration, pause, loops } = dashLovenseCommandSettings();
  const runOnce = async (step) => {
    const payload = program.buildPayload({ toyId, intensity, duration });
    await dashExecuteLovenseSegment(program.kind, payload);
    const detail = loops > 1 ? ` Loop ${step}/${loops}` : "";
    dashSetLovenseStatus(`${program.label}${detail} aktiv. ${duration}s on, ${pause}s pause.`, "aktiv");
    if (step >= loops) return;
    dashLovenseSequenceTimeout = window.setTimeout(() => {
      runOnce(step + 1).catch((err) => {
        dashSetLovenseStatus(`${program.label} fehlgeschlagen (${String(err)})`, "Fehler");
      });
    }, Math.max(0, (duration + pause) * 1000));
  };
  await runOnce(1);
}

async function dashSyncLovenseToys() {
  if (!dashLovenseSdk) return;
  try {
    let toys = [];
    if (typeof dashLovenseSdk.getToys === "function") {
      toys = await dashLovenseSdk.getToys();
    } else if (typeof dashLovenseSdk.getOnlineToys === "function") {
      toys = await dashLovenseSdk.getOnlineToys();
    }
    dashRenderLovenseToys(Array.isArray(toys) ? toys : Object.values(toys || {}));
    dashSetLovenseStatus(
      dashLovenseToys.length ? `${dashLovenseToys.length} Lovense-Toy(s) verbunden.` : "SDK aktiv. Warte auf verbundenes Toy…",
      dashLovenseToys.length ? "verbunden" : "bereit"
    );
  } catch (err) {
    dashSetLovenseStatus(`Toy-Status konnte nicht geladen werden (${String(err)})`, "Fehler");
  }
}

async function dashInitLovense() {
  if (!DASH_SESSION_ID) return;
  if (!dashLovenseEnabled) {
    dashSetLovenseStatus("Lovense ist serverseitig deaktiviert.", "aus");
    return;
  }
  if (!dashLovenseConfigured) {
    dashSetLovenseStatus("Lovense ist noch nicht vollstaendig konfiguriert. Es fehlen Plattformname oder Developer-Token.", "Konfig");
    return;
  }
  if (typeof window.LovenseBasicSdk !== "function") {
    dashSetLovenseStatus("Lovense SDK konnte im Browser nicht geladen werden.", "Fehler");
    return;
  }
  const bootstrap = dashLovenseBootstrap || await dashLoadLovenseBootstrap();
  dashSetLovenseStatus(`Lovense wird fuer ${bootstrap.uname || bootstrap.uid} initialisiert…`, "Start");
  dashLovenseSdk = new window.LovenseBasicSdk({
    platform: bootstrap.platform || dashLovensePlatform,
    authToken: bootstrap.auth_token,
    uid: bootstrap.uid,
    appType: bootstrap.app_type || dashLovenseAppType,
    debug: dashLovenseDebug,
  });

  if (typeof dashLovenseSdk.on === "function") {
    dashLovenseSdk.on("ready", async () => {
      dashSetLovenseStatus("Lovense SDK bereit. Verbinde jetzt deinen Edge 2 ueber die App oder den QR-Code.", "bereit");
      await dashRefreshLovenseQr();
      await dashSyncLovenseToys();
    });
    dashLovenseSdk.on("sdkError", (data) => {
      const message = data && data.message ? data.message : "Lovense SDK Fehler";
      dashSetLovenseStatus(message, "Fehler");
    });
  } else {
    await dashRefreshLovenseQr();
    await dashSyncLovenseToys();
  }

  if (dashLovensePollHandle) window.clearInterval(dashLovensePollHandle);
  dashLovensePollHandle = window.setInterval(() => {
    dashSyncLovenseToys().catch(() => {});
  }, 6000);
}

async function dashSendLovenseCommand(action) {
  if (!dashLovenseSdk) {
    dashSetLovenseStatus("Lovense ist noch nicht initialisiert.", "Start");
    return;
  }
  const toyId = dashSelectedLovenseToyId();
  if (!toyId) {
    dashSetLovenseStatus("Bitte zuerst ein verbundenes Toy waehlen.", "Toy");
    return;
  }
  const { intensity, duration } = dashLovenseCommandSettings();
  const commandPayload = { toyId };
  if (action === "stop") {
    dashClearLovenseSequence();
    if (typeof dashLovenseSdk.stopToyAction === "function") {
      await dashLovenseSdk.stopToyAction(commandPayload);
    } else if (typeof dashLovenseSdk.sendToyCommand === "function") {
      await dashLovenseSdk.sendToyCommand({ ...commandPayload, vibrate: 0, time: 0 });
    }
    dashSetLovenseStatus("Toy gestoppt.", "Stop");
    return;
  }
  if (action === "vibrate") {
    await dashRunLovenseProgram({
      label: `Vibrate ${intensity}/20`,
      kind: "vibrate",
      buildPayload: ({ toyId: activeToyId, intensity: activeIntensity, duration: activeDuration }) => ({
        toyId: activeToyId,
        vibrate: activeIntensity,
        time: activeDuration,
      }),
    });
    return;
  }
  if (action === "pulse" || action === "wave") {
    await dashRunLovenseProgram({
      label: action === "pulse" ? "Pulse" : "Wave",
      kind: "pattern",
      buildPayload: ({ toyId: activeToyId, intensity: activeIntensity, duration: activeDuration }) => ({
        toyId: activeToyId,
        strength: dashLovensePatternStrength(activeIntensity, action),
        time: activeDuration,
        interval: 180,
        vibrate: true,
      }),
    });
    return;
  }
  throw new Error(`Lovense-Aktion wird vom geladenen SDK nicht unterstuetzt: ${action}`);
}

async function dashRunLovensePreset() {
  const preset = dashSelectedLovensePreset();
  if (!preset) {
    dashSetLovenseStatus("Bitte zuerst ein Preset waehlen.", "Preset");
    return;
  }
  await dashRunLovenseProgram({
    label: preset.label,
    kind: preset.kind,
    buildPayload: ({ toyId, intensity, duration }) => ({
      toyId,
      strength: preset.pattern(intensity),
      time: duration,
      interval: preset.interval || 180,
      vibrate: true,
    }),
  });
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
  dashSetPersonaLabel(s.persona_name);
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

async function dashLoadPersonas() {
  const select = document.getElementById("dash-persona-select");
  if (!select) return;
  try {
    const data = await dashGet("/api/personas");
    const items = Array.isArray(data.items) ? data.items : [];
    const options = ['<option value="">Keyholderin waehlen</option>'];
    items.forEach((item) => {
      const id = Number(item?.id || 0);
      const name = String(item?.name || "").trim();
      if (!id || !name) return;
      options.push(`<option value="${id}">${dashEsc(name)}</option>`);
    });
    select.innerHTML = options.join("");
    if (dashPersonaId && items.some((item) => Number(item?.id || 0) === dashPersonaId)) {
      select.value = String(dashPersonaId);
    } else {
      select.value = "";
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
document.getElementById("dash-persona-save")?.addEventListener("click", () => {
  dashSavePersona().catch(() => {});
});
document.getElementById("dash-lovense-init")?.addEventListener("click", () => {
  dashInitLovense().catch((err) => dashSetLovenseStatus(`Lovense Start fehlgeschlagen (${String(err)})`, "Fehler"));
});
document.getElementById("dash-lovense-refresh")?.addEventListener("click", () => {
  dashRefreshLovenseQr().catch((err) => dashSetLovenseStatus(`QR konnte nicht erneuert werden (${String(err)})`, "Fehler"));
});
document.getElementById("dash-lovense-open-app")?.addEventListener("click", () => {
  if (dashLovenseSdk && typeof dashLovenseSdk.connectLovenseAPP === "function") {
    Promise.resolve(dashLovenseSdk.connectLovenseAPP()).catch((err) => {
      dashSetLovenseStatus(`Connect App konnte nicht geoeffnet werden (${String(err)})`, "Fehler");
    });
    return;
  }
  dashSetLovenseStatus("Die Connect-App-Funktion ist in diesem Browser nicht verfuegbar.", "Hinweis");
});
document.getElementById("dash-lovense-vibrate")?.addEventListener("click", () => {
  dashSendLovenseCommand("vibrate").catch((err) => dashSetLovenseStatus(`Vibration fehlgeschlagen (${String(err)})`, "Fehler"));
});
document.getElementById("dash-lovense-pulse")?.addEventListener("click", () => {
  dashSendLovenseCommand("pulse").catch((err) => dashSetLovenseStatus(`Pulse fehlgeschlagen (${String(err)})`, "Fehler"));
});
document.getElementById("dash-lovense-wave")?.addEventListener("click", () => {
  dashSendLovenseCommand("wave").catch((err) => dashSetLovenseStatus(`Wave fehlgeschlagen (${String(err)})`, "Fehler"));
});
document.getElementById("dash-lovense-stop")?.addEventListener("click", () => {
  dashSendLovenseCommand("stop").catch((err) => dashSetLovenseStatus(`Stop fehlgeschlagen (${String(err)})`, "Fehler"));
});
document.getElementById("dash-lovense-intensity")?.addEventListener("input", dashUpdateLovenseIntensityLabel);
document.getElementById("dash-lovense-toy-select")?.addEventListener("change", () => {
  dashRenderLovenseToys(dashLovenseToys);
});
document.getElementById("dash-lovense-preset")?.addEventListener("change", dashUpdateLovensePresetCopy);
document.getElementById("dash-lovense-run-preset")?.addEventListener("click", () => {
  dashRunLovensePreset().catch((err) => dashSetLovenseStatus(`Preset fehlgeschlagen (${String(err)})`, "Fehler"));
});

document.addEventListener("DOMContentLoaded", async () => {
  if (!DASH_SESSION_ID) return;
  dashUpdateLovenseIntensityLabel();
  dashUpdateLovensePresetCopy();
  dashUpdateCountdown();
  setInterval(dashUpdateCountdown, 1000);
  await dashLoadPersonas();
  await dashLoadSummary();
  await dashLoadSessionState();
  await dashLoadHygieneQuota();
  await dashLoadRunHistory();
  dashSetLovenseStatus(
    !dashLovenseEnabled
      ? "Lovense ist serverseitig deaktiviert."
      : (!dashLovenseConfigured ? "Lovense ist noch nicht vollstaendig konfiguriert." : "Lovense bereit. Initialisiere die Verbindung, um deinen Edge 2 zu koppeln."),
    !dashLovenseEnabled ? "aus" : (!dashLovenseConfigured ? "Konfig" : "bereit")
  );
  setInterval(() => {
    dashLoadSessionState().catch(() => {});
  }, 8000);
});
