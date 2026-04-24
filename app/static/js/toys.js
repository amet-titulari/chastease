"use strict";

const toysShell = document.querySelector(".dashboard-shell");
const TOYS_SESSION_ID = Number(toysShell?.dataset.sessionId || 0);
const toysLovenseEnabled = String(toysShell?.dataset.lovenseEnabled || "") === "1";
const toysLovenseConfigured = String(toysShell?.dataset.lovenseConfigured || "") === "1";
const toysLovensePlatform = String(toysShell?.dataset.lovensePlatform || "").trim();
const toysLovenseAppType = String(toysShell?.dataset.lovenseAppType || "connect").trim() || "connect";
const toysLovenseDebug = String(toysShell?.dataset.lovenseDebug || "") === "1";
const toysLovenseSimulator = String(toysShell?.dataset.lovenseSimulator || "") === "1";
const toysPreferredProvider = String(toysShell?.dataset.toyProvider || "none").trim().toLowerCase();
const toysProfileEnabled = String(toysShell?.dataset.toyEnabled || "") === "1";
const toysPreferredToyName = String(toysShell?.dataset.toyPreferredName || "").trim();
const toysPreferredToyId = String(toysShell?.dataset.toyPreferredId || "").trim();
const toysPreferredPreset = String(toysShell?.dataset.toyPreferredPreset || "").trim();
const toysDefaultIntensity = Number(toysShell?.dataset.toyDefaultIntensity || 8) || 8;
const toysDefaultDuration = Number(toysShell?.dataset.toyDefaultDuration || 20) || 20;
const toysDefaultPause = Number(toysShell?.dataset.toyDefaultPause || 5) || 5;
const toysDefaultLoops = Number(toysShell?.dataset.toyDefaultLoops || 1) || 1;
const TOYS_LOVENSE_AUTO_INIT_KEY = `chastease.lovense.auto_init.${TOYS_SESSION_ID || "default"}`;
const TOYS_LOVENSE_TOY_KEY = `chastease.lovense.toy.${TOYS_SESSION_ID || "default"}`;
let toysLovenseSdk = null;
let toysLovenseBootstrap = null;
let toysLovenseToys = [];
let toysLovensePollHandle = null;
let toysLovenseSequenceTimeout = null;
let toysPresetLibrary = { builtin: [], wearer: [], persona: [], combined: [] };

const TOYS_LOVENSE_PRESETS = {
  tease_ramp: {
    label: "Tease Ramp",
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
    description: "Kurze harte Impulse mit klaren Pausen dazwischen.",
    pattern: (intensity) => {
      const level = Math.max(1, Math.min(20, intensity));
      return `0;${level};0;${level};0;${Math.max(1, Math.round(level * 0.75))}`;
    },
    interval: 160,
  },
  wave_ladder: {
    label: "Wave Ladder",
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

function toysCombinedPresetMap() {
  const map = { ...TOYS_LOVENSE_PRESETS };
  const items = Array.isArray(toysPresetLibrary?.combined) ? toysPresetLibrary.combined : [];
  items.forEach((item) => {
    if (!item || !item.key) return;
    if (item.command === "pattern") {
      if (String(item.pattern || "").startsWith("builtin:")) {
        const builtinKey = String(item.pattern || "").split(":").slice(1).join(":");
        const builtin = TOYS_LOVENSE_PRESETS[builtinKey];
        if (builtin) map[item.key] = { ...builtin, label: item.name || builtinKey };
        return;
      }
      map[item.key] = {
        label: item.name || item.key,
        description: `${item.owner_type === "persona" ? "Keyholder" : "Wearer"}-Preset`,
        interval: Number(item.interval || 180) || 180,
        pattern: () => String(item.pattern || ""),
      };
      return;
    }
    if (item.command === "preset" && item.preset && TOYS_LOVENSE_PRESETS[item.preset]) {
      map[item.key] = { ...TOYS_LOVENSE_PRESETS[item.preset], label: item.name || item.key };
    }
  });
  return map;
}

function toysEsc(value) {
  return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function toysSetPolicyStatus(message, isError = false) {
  const el = document.getElementById("toy-policy-status");
  if (!el) return;
  el.textContent = message || "—";
  el.classList.toggle("dash-copy-warn", Boolean(isError));
}

function toysSetNullableNumberInput(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  el.value = value == null ? "" : String(value);
}

function toysReadNullableNumberInput(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  const text = String(el.value || "").trim();
  return text ? Number(text) : null;
}

function toysReadCheckbox(id, fallback = true) {
  const el = document.getElementById(id);
  return el ? Boolean(el.checked) : fallback;
}

function toysRememberLovenseAutoInit() {
  try {
    window.sessionStorage.setItem(TOYS_LOVENSE_AUTO_INIT_KEY, "1");
  } catch (_) {}
}

function toysShouldAutoInitLovense() {
  try {
    return window.sessionStorage.getItem(TOYS_LOVENSE_AUTO_INIT_KEY) === "1";
  } catch (_) {
    return false;
  }
}

function toysRememberSelectedToyId(toyId) {
  if (!toyId) return;
  try {
    window.sessionStorage.setItem(TOYS_LOVENSE_TOY_KEY, String(toyId));
  } catch (_) {}
}

function toysRestoreSelectedToyId() {
  try {
    return String(window.sessionStorage.getItem(TOYS_LOVENSE_TOY_KEY) || "").trim();
  } catch (_) {
    return "";
  }
}

async function toysGet(url) {
  const resp = await fetch(url);
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}

async function toysPost(url, payload) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}

async function toysDelete(url) {
  const resp = await fetch(url, { method: "DELETE" });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}

async function toysLogEvent(payload) {
  if (!TOYS_SESSION_ID) return;
  try {
    await toysPost(`/api/lovense/sessions/${TOYS_SESSION_ID}/events`, payload);
  } catch (_) {}
}

function toysSetLovenseStatus(message, pill = null) {
  const el = document.getElementById("dash-lovense-status");
  if (el) el.textContent = message || "—";
  const chip = document.getElementById("dash-lovense-app-pill");
  if (chip && pill) chip.textContent = pill;
}

function toysApplyProfileDefaults() {
  const intensity = document.getElementById("dash-lovense-intensity");
  const duration = document.getElementById("dash-lovense-duration");
  const pause = document.getElementById("dash-lovense-pause");
  const loops = document.getElementById("dash-lovense-loops");
  const preset = document.getElementById("dash-lovense-preset");
  if (intensity) intensity.value = String(Math.max(1, Math.min(20, toysDefaultIntensity)));
  if (duration) duration.value = String(Math.max(1, Math.min(300, toysDefaultDuration)));
  if (pause) pause.value = String(Math.max(0, Math.min(300, toysDefaultPause)));
  if (loops) loops.value = String(Math.max(1, Math.min(20, toysDefaultLoops)));
  if (preset && toysPreferredPreset && toysCombinedPresetMap()[toysPreferredPreset]) {
    preset.value = toysPreferredPreset;
  }
}

function toysUpdateLovenseIntensityLabel() {
  const input = document.getElementById("dash-lovense-intensity");
  const el = document.getElementById("dash-lovense-intensity-value");
  if (!input || !el) return;
  const intensity = Math.max(1, Math.min(20, Number(input.value || 8)));
  el.textContent = `${intensity}/20`;
}

function toysSelectedLovensePreset() {
  const presetId = String(document.getElementById("dash-lovense-preset")?.value || "").trim();
  return toysCombinedPresetMap()[presetId] || null;
}

function toysUpdateLovensePresetCopy() {
  const el = document.getElementById("dash-lovense-preset-copy");
  if (!el) return;
  const preset = toysSelectedLovensePreset();
  el.textContent = preset
    ? `${preset.label}: ${preset.description || "Gespeicherte Routine fuer kurze Toy-Sequenzen."}`
    : "Kurze Bibliothek fuer erste Routinen. Ein visueller Pattern-Designer kann spaeter darauf aufbauen.";
}

function toysSetLovenseQrVisible(visible) {
  const wrap = document.getElementById("dash-lovense-qr-wrap");
  if (!wrap) return;
  wrap.classList.toggle("is-hidden", !visible);
}

function toysLovenseCommandSettings() {
  const intensity = Math.max(1, Math.min(20, Number(document.getElementById("dash-lovense-intensity")?.value || 8)));
  const duration = Math.max(1, Math.min(300, Number(document.getElementById("dash-lovense-duration")?.value || 20)));
  const pause = Math.max(0, Math.min(300, Number(document.getElementById("dash-lovense-pause")?.value || 5)));
  const loops = Math.max(1, Math.min(20, Number(document.getElementById("dash-lovense-loops")?.value || 1)));
  return { intensity, duration, pause, loops };
}

function toysClearLovenseSequence() {
  if (toysLovenseSequenceTimeout) {
    window.clearTimeout(toysLovenseSequenceTimeout);
    toysLovenseSequenceTimeout = null;
  }
}

function toysSelectedLovenseToyId() {
  return String(document.getElementById("dash-lovense-toy-select")?.value || "").trim();
}

function toysRenderLovenseToys(toys) {
  toysLovenseToys = Array.isArray(toys) ? toys.filter(Boolean) : [];
  const select = document.getElementById("dash-lovense-toy-select");
  const meta = document.getElementById("dash-lovense-toy-meta");
  if (!select) return;
  if (!toysLovenseToys.length) {
    select.innerHTML = '<option value="">Noch kein Toy verbunden</option>';
    if (meta) meta.textContent = "Kein Lovense-Toy aktiv. Verbinde den Edge 2 ueber die Lovense Connect App.";
    toysSetLovenseQrVisible(true);
    return;
  }
  const options = toysLovenseToys.map((toy, idx) => {
    const id = String(toy.id || toy.toyId || toy.toy_id || idx);
    const name = String(toy.name || toy.nickName || toy.nickname || toy.type || "Toy");
    const state = String(toy.status || toy.connectStatus || toy.connection || "verbunden");
    return `<option value="${toysEsc(id)}">${toysEsc(name)} (${toysEsc(state)})</option>`;
  });
  select.innerHTML = options.join("");
  const rememberedToyId = toysRestoreSelectedToyId();
  const preferredMatch = toysLovenseToys.find((toy) => {
    const id = String(toy.id || toy.toyId || toy.toy_id || "").trim();
    const name = String(toy.name || toy.nickName || toy.nickname || toy.type || "").trim().toLowerCase();
    return (toysPreferredToyId && id === toysPreferredToyId) || (toysPreferredToyName && name === toysPreferredToyName.toLowerCase());
  });
  const preferredId = preferredMatch ? String(preferredMatch.id || preferredMatch.toyId || preferredMatch.toy_id || "") : "";
  const chosen = toysSelectedLovenseToyId() || rememberedToyId || preferredId || String(toysLovenseToys[0].id || toysLovenseToys[0].toyId || toysLovenseToys[0].toy_id || "");
  if (chosen) select.value = chosen;
  toysRememberSelectedToyId(select.value);
  const active = toysLovenseToys.find((toy) => String(toy.id || toy.toyId || toy.toy_id || "") === select.value) || toysLovenseToys[0];
  if (meta && active) {
    const label = String(active.name || active.nickName || active.nickname || active.type || "Toy");
    const battery = active.battery != null ? ` · Akku ${active.battery}%` : "";
    const version = active.version ? ` · ${active.version}` : "";
    meta.textContent = `${label}${battery}${version}`;
  }
  toysSetLovenseQrVisible(false);
}

async function toysLoadLovenseBootstrap() {
  const data = await toysPost(`/api/lovense/sessions/${TOYS_SESSION_ID}/bootstrap`, {});
  toysLovenseBootstrap = data;
  return data;
}

function toysResolveLovenseQr(payload) {
  if (!payload || typeof payload !== "object") return "";
  return String(payload.qrcodeUrl || payload.qrCodeUrl || payload.url || payload.qrcode || "").trim();
}

async function toysRefreshLovenseQr() {
  if (toysLovenseSimulator) return;
  if (!toysLovenseSdk || typeof toysLovenseSdk.getQrcode !== "function") return;
  try {
    const qr = await toysLovenseSdk.getQrcode();
    const qrUrl = toysResolveLovenseQr(qr);
    const img = document.getElementById("dash-lovense-qr");
    if (img && qrUrl) {
      img.src = qrUrl;
      img.classList.remove("is-hidden");
      toysSetLovenseQrVisible(true);
    }
  } catch (err) {
    toysSetLovenseStatus(`Lovense QR fehlgeschlagen (${String(err)})`, "Fehler");
  }
}

function toysLovensePatternStrength(intensity, mode) {
  const level = Math.max(1, Math.min(20, Number(intensity) || 8));
  if (mode === "pulse") {
    return `0;${level};0;${Math.max(1, Math.round(level * 0.85))};0;${level}`;
  }
  return `0;${Math.max(1, Math.round(level * 0.45))};${Math.max(1, Math.round(level * 0.7))};${level};${Math.max(1, Math.round(level * 0.7))};${Math.max(1, Math.round(level * 0.45))}`;
}

async function toysExecuteLovenseSegment(kind, payload) {
  if (toysLovenseSimulator) {
    await new Promise((resolve) => window.setTimeout(resolve, 120));
    return;
  }
  if (!toysLovenseSdk) {
    throw new Error("Lovense ist noch nicht initialisiert.");
  }
  if (kind === "vibrate") {
    if (typeof toysLovenseSdk.sendToyCommand !== "function") {
      throw new Error("sendToyCommand wird vom geladenen SDK nicht angeboten.");
    }
    await toysLovenseSdk.sendToyCommand(payload);
    return;
  }
  if (kind === "pattern") {
    if (typeof toysLovenseSdk.sendPatternCommand !== "function") {
      throw new Error("sendPatternCommand wird vom geladenen SDK nicht angeboten.");
    }
    await toysLovenseSdk.sendPatternCommand(payload);
    return;
  }
  throw new Error(`Lovense-Segmenttyp wird nicht unterstuetzt: ${kind}`);
}

async function toysStopActiveLovenseAction() {
  const toyId = toysSelectedLovenseToyId();
  if ((!toysLovenseSdk && !toysLovenseSimulator) || !toyId) return false;
  toysClearLovenseSequence();
  if (toysLovenseSimulator) {
    toysSetLovenseStatus("Toy gestoppt.", "Stop");
    await toysLogEvent({ source: "manual", phase: "executed", command: "stop", title: "Stop", toy_id: toyId });
    return true;
  }
  if (typeof toysLovenseSdk.stopToyAction === "function") {
    await toysLovenseSdk.stopToyAction({ toyId });
  } else if (typeof toysLovenseSdk.sendToyCommand === "function") {
    await toysLovenseSdk.sendToyCommand({ toyId, vibrate: 0, time: 0 });
  } else {
    return false;
  }
  toysSetLovenseStatus("Toy gestoppt.", "Stop");
  return true;
}

async function toysRunLovenseProgram(program) {
  const toyId = toysSelectedLovenseToyId();
  if (!toyId) {
    toysSetLovenseStatus("Bitte zuerst ein verbundenes Toy waehlen.", "Toy");
    return;
  }
  toysClearLovenseSequence();
  const { intensity, duration, pause, loops } = toysLovenseCommandSettings();
  const runOnce = async (step) => {
    const payload = program.buildPayload({ toyId, intensity, duration });
    await toysExecuteLovenseSegment(program.kind, payload);
    await toysLogEvent({
      source: "manual",
      phase: "executed",
      command: program.kind,
      title: program.label,
      intensity,
      duration_seconds: duration,
      pause_seconds: pause,
      loops,
      toy_id: toyId,
    });
    const detail = loops > 1 ? ` Loop ${step}/${loops}` : "";
    toysSetLovenseStatus(`${program.label}${detail} aktiv. ${duration}s on, ${pause}s pause.`, "aktiv");
    if (step >= loops) return;
    toysLovenseSequenceTimeout = window.setTimeout(() => {
      runOnce(step + 1).catch((err) => {
        toysSetLovenseStatus(`${program.label} fehlgeschlagen (${String(err)})`, "Fehler");
      });
    }, Math.max(0, (duration + pause) * 1000));
  };
  await runOnce(1);
}

async function toysSyncLovenseToys() {
  if (toysLovenseSimulator) {
    toysRenderLovenseToys([{ id: "sim-edge-2", name: "Simulator Edge 2", battery: 100, status: "simulated", version: "sim" }]);
    toysSetLovenseStatus("Simulator aktiv. Virtuelles Toy verbunden.", "sim");
    return;
  }
  if (!toysLovenseSdk) return;
  try {
    let toys = [];
    if (typeof toysLovenseSdk.getToys === "function") {
      toys = await toysLovenseSdk.getToys();
    } else if (typeof toysLovenseSdk.getOnlineToys === "function") {
      toys = await toysLovenseSdk.getOnlineToys();
    }
    toysRenderLovenseToys(Array.isArray(toys) ? toys : Object.values(toys || {}));
    toysSetLovenseStatus(
      toysLovenseToys.length ? `${toysLovenseToys.length} Lovense-Toy(s) verbunden.` : "SDK aktiv. Warte auf verbundenes Toy…",
      toysLovenseToys.length ? "verbunden" : "bereit"
    );
  } catch (err) {
    toysSetLovenseStatus(`Toy-Status konnte nicht geladen werden (${String(err)})`, "Fehler");
  }
}

async function toysInitLovense() {
  if (!TOYS_SESSION_ID) return;
  if (!toysLovenseEnabled) {
    toysSetLovenseStatus("Lovense ist serverseitig deaktiviert.", "aus");
    return;
  }
  if (!toysLovenseConfigured) {
    if (toysLovenseSimulator) {
      toysRememberLovenseAutoInit();
      await toysSyncLovenseToys();
      return;
    }
    toysSetLovenseStatus("Lovense ist noch nicht vollstaendig konfiguriert. Es fehlen Plattformname oder Developer-Token.", "Konfig");
    return;
  }
  if (typeof window.LovenseBasicSdk !== "function") {
    toysSetLovenseStatus("Lovense SDK konnte im Browser nicht geladen werden.", "Fehler");
    return;
  }
  const bootstrap = toysLovenseBootstrap || await toysLoadLovenseBootstrap();
  toysRememberLovenseAutoInit();
  toysSetLovenseStatus(`Lovense wird fuer ${bootstrap.uname || bootstrap.uid} initialisiert…`, "Start");
  toysLovenseSdk = new window.LovenseBasicSdk({
    platform: bootstrap.platform || toysLovensePlatform,
    authToken: bootstrap.auth_token,
    uid: bootstrap.uid,
    appType: bootstrap.app_type || toysLovenseAppType,
    debug: toysLovenseDebug,
  });

  if (typeof toysLovenseSdk.on === "function") {
    toysLovenseSdk.on("ready", async () => {
      toysSetLovenseStatus("Lovense SDK bereit. Verbinde jetzt deinen Edge 2 ueber die App oder den QR-Code.", "bereit");
      await toysRefreshLovenseQr();
      await toysSyncLovenseToys();
    });
    toysLovenseSdk.on("sdkError", (data) => {
      const message = data && data.message ? data.message : "Lovense SDK Fehler";
      toysSetLovenseStatus(message, "Fehler");
    });
  } else {
    await toysRefreshLovenseQr();
    await toysSyncLovenseToys();
  }

  if (toysLovensePollHandle) window.clearInterval(toysLovensePollHandle);
  toysLovensePollHandle = window.setInterval(() => {
    toysSyncLovenseToys().catch(() => {});
  }, 6000);
}

async function toysSendLovenseCommand(action) {
  if (!toysLovenseSdk && !toysLovenseSimulator) {
    toysSetLovenseStatus("Lovense ist noch nicht initialisiert.", "Start");
    return;
  }
  const toyId = toysSelectedLovenseToyId();
  if (!toyId) {
    toysSetLovenseStatus("Bitte zuerst ein verbundenes Toy waehlen.", "Toy");
    return;
  }
  const { intensity, duration } = toysLovenseCommandSettings();
  const commandPayload = { toyId };
  if (action === "stop") {
    await toysStopActiveLovenseAction();
    return;
  }
  if (action === "vibrate") {
    await toysRunLovenseProgram({
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
    await toysRunLovenseProgram({
      label: action === "pulse" ? "Pulse" : "Wave",
      kind: "pattern",
      buildPayload: ({ toyId: activeToyId, intensity: activeIntensity, duration: activeDuration }) => ({
        toyId: activeToyId,
        strength: toysLovensePatternStrength(activeIntensity, action),
        time: activeDuration,
        interval: 180,
        vibrate: true,
      }),
    });
    return;
  }
  throw new Error(`Lovense-Aktion wird vom geladenen SDK nicht unterstuetzt: ${action}`);
}

async function toysRunLovensePreset() {
  const preset = toysSelectedLovensePreset();
  if (!preset) {
    toysSetLovenseStatus("Bitte zuerst ein Preset waehlen.", "Preset");
    return;
  }
  await toysRunLovenseProgram({
    label: preset.label,
    kind: "pattern",
    buildPayload: ({ toyId, intensity, duration }) => ({
      toyId,
      strength: preset.pattern(intensity),
      time: duration,
      interval: preset.interval || 180,
      vibrate: true,
    }),
  });
  await toysLogEvent({
    source: "manual",
    phase: "executed",
    command: "preset",
    title: preset.label,
    preset: String(document.getElementById("dash-lovense-preset")?.value || ""),
  });
}

async function toysLoadPresetLibrary() {
  const data = await toysGet(`/api/lovense/sessions/${TOYS_SESSION_ID}/preset-library`);
  toysPresetLibrary = data.library || { builtin: [], wearer: [], persona: [], combined: [] };
  const select = document.getElementById("dash-lovense-preset");
  if (select) {
    const items = Array.isArray(toysPresetLibrary.combined) ? toysPresetLibrary.combined : [];
    select.innerHTML = items
      .map((item) => `<option value="${toysEsc(item.key)}">${toysEsc(item.name || item.key)}${item.owner_type === "persona" ? " · Persona" : item.owner_type === "wearer" ? " · Wearer" : ""}</option>`)
      .join("");
  }
  toysRenderSavedPresetLists();
}

function toysRenderSavedPresetLists() {
  const wearerEl = document.getElementById("toy-wearer-presets");
  const personaEl = document.getElementById("toy-persona-presets");
  const render = (items, scope) => {
    if (!Array.isArray(items) || !items.length) return "<p class=\"dash-copy\">Noch keine Presets gespeichert.</p>";
    return items.map((item) => `
      <div class="task-card">
        <div class="task-card-title">${toysEsc(item.name)} <span class="task-num">${toysEsc(item.command)}</span></div>
        <div class="dash-actions">
          <button type="button" class="dash-link-secondary" data-preset-run="${toysEsc(item.key)}">Starten</button>
          <button type="button" class="dash-link-secondary" data-preset-load="${toysEsc(item.key)}" data-preset-scope="${toysEsc(scope)}">Laden</button>
          <button type="button" class="dash-safety-btn dash-safety-btn--red" data-preset-delete="${toysEsc(item.key)}" data-preset-scope="${toysEsc(scope)}">Loeschen</button>
        </div>
      </div>`).join("");
  };
  if (wearerEl) wearerEl.innerHTML = render(toysPresetLibrary.wearer, "wearer");
  if (personaEl) personaEl.innerHTML = render(toysPresetLibrary.persona, "persona");
}

function toysReadPresetEditorPayload() {
  return {
    key: String(document.getElementById("toy-preset-key")?.value || "").trim() || undefined,
    name: String(document.getElementById("toy-preset-name")?.value || "").trim(),
    command: String(document.getElementById("toy-preset-command")?.value || "pattern").trim(),
    preset: String(document.getElementById("toy-preset-base")?.value || "").trim() || undefined,
    pattern: String(document.getElementById("toy-preset-pattern")?.value || "").trim() || undefined,
    intensity: toysReadNullableNumberInput("toy-preset-intensity"),
    duration_seconds: toysReadNullableNumberInput("toy-preset-duration"),
    pause_seconds: toysReadNullableNumberInput("toy-preset-pause"),
    loops: toysReadNullableNumberInput("toy-preset-loops"),
    interval: toysReadNullableNumberInput("toy-preset-interval"),
  };
}

function toysLoadPresetIntoEditor(scope, key) {
  const source = scope === "persona" ? toysPresetLibrary.persona : toysPresetLibrary.wearer;
  const item = (Array.isArray(source) ? source : []).find((entry) => entry.key === key);
  if (!item) return;
  const set = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.value = value == null ? "" : String(value);
  };
  set("toy-preset-scope", scope);
  set("toy-preset-key", item.key);
  set("toy-preset-name", item.name);
  set("toy-preset-command", item.command);
  set("toy-preset-base", item.preset || "");
  set("toy-preset-pattern", item.pattern || "");
  set("toy-preset-intensity", item.intensity || "");
  set("toy-preset-duration", item.duration_seconds || "");
  set("toy-preset-pause", item.pause_seconds || "");
  set("toy-preset-loops", item.loops || "");
  set("toy-preset-interval", item.interval || "");
}

function toysFillPresetEditorFromCurrent() {
  const set = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.value = value == null ? "" : String(value);
  };
  set("toy-preset-intensity", document.getElementById("dash-lovense-intensity")?.value || "");
  set("toy-preset-duration", document.getElementById("dash-lovense-duration")?.value || "");
  set("toy-preset-pause", document.getElementById("dash-lovense-pause")?.value || "");
  set("toy-preset-loops", document.getElementById("dash-lovense-loops")?.value || "");
  set("toy-preset-base", document.getElementById("dash-lovense-preset")?.value || "");
}

async function toysSaveNamedPreset() {
  const scope = String(document.getElementById("toy-preset-scope")?.value || "wearer").trim();
  const payload = toysReadPresetEditorPayload();
  if (!payload.name) {
    toysSetPolicyStatus("Preset-Name fehlt.", true);
    return;
  }
  const url = scope === "persona"
    ? `/api/lovense/sessions/${TOYS_SESSION_ID}/persona-presets`
    : `/api/lovense/sessions/${TOYS_SESSION_ID}/presets`;
  await toysPost(url, payload);
  await toysLoadPresetLibrary();
  toysSetPolicyStatus(`Preset '${payload.name}' gespeichert.`);
}

async function toysDeleteNamedPreset(scope, key) {
  const url = scope === "persona"
    ? `/api/lovense/sessions/${TOYS_SESSION_ID}/persona-presets/${encodeURIComponent(key)}`
    : `/api/lovense/sessions/${TOYS_SESSION_ID}/presets/${encodeURIComponent(key)}`;
  await toysDelete(url);
  await toysLoadPresetLibrary();
  toysSetPolicyStatus(`Preset '${key}' geloescht.`);
}

function toysApplyLovensePolicy(policy) {
  const value = policy && typeof policy === "object" ? policy : {};
  const allowed = value.allowed_commands && typeof value.allowed_commands === "object" ? value.allowed_commands : {};
  toysSetNullableNumberInput("toy-policy-min-intensity", value.min_intensity);
  toysSetNullableNumberInput("toy-policy-max-intensity", value.max_intensity);
  toysSetNullableNumberInput("toy-policy-min-step-duration", value.min_step_duration_seconds);
  toysSetNullableNumberInput("toy-policy-max-step-duration", value.max_step_duration_seconds);
  toysSetNullableNumberInput("toy-policy-min-pause", value.min_pause_seconds);
  toysSetNullableNumberInput("toy-policy-max-pause", value.max_pause_seconds);
  toysSetNullableNumberInput("toy-policy-max-plan-duration", value.max_plan_duration_seconds);
  toysSetNullableNumberInput("toy-policy-max-plan-steps", value.max_plan_steps);
  const presetAllowed = value.allow_presets !== false && allowed.preset !== false;
  const vibrateEl = document.getElementById("toy-policy-allow-vibrate");
  const pulseEl = document.getElementById("toy-policy-allow-pulse");
  const waveEl = document.getElementById("toy-policy-allow-wave");
  const presetEl = document.getElementById("toy-policy-allow-preset");
  const appendEl = document.getElementById("toy-policy-allow-append");
  if (vibrateEl) vibrateEl.checked = allowed.vibrate !== false;
  if (pulseEl) pulseEl.checked = allowed.pulse !== false;
  if (waveEl) waveEl.checked = allowed.wave !== false;
  if (presetEl) presetEl.checked = presetAllowed;
  if (appendEl) appendEl.checked = value.allow_append_mode !== false;
}

function toysCollectLovensePolicyPayload() {
  const allowPresets = toysReadCheckbox("toy-policy-allow-preset", true);
  return {
    min_intensity: toysReadNullableNumberInput("toy-policy-min-intensity"),
    max_intensity: toysReadNullableNumberInput("toy-policy-max-intensity"),
    min_step_duration_seconds: toysReadNullableNumberInput("toy-policy-min-step-duration"),
    max_step_duration_seconds: toysReadNullableNumberInput("toy-policy-max-step-duration"),
    min_pause_seconds: toysReadNullableNumberInput("toy-policy-min-pause"),
    max_pause_seconds: toysReadNullableNumberInput("toy-policy-max-pause"),
    max_plan_duration_seconds: toysReadNullableNumberInput("toy-policy-max-plan-duration"),
    max_plan_steps: toysReadNullableNumberInput("toy-policy-max-plan-steps"),
    allow_presets: allowPresets,
    allow_append_mode: toysReadCheckbox("toy-policy-allow-append", true),
    allowed_commands: {
      vibrate: toysReadCheckbox("toy-policy-allow-vibrate", true),
      pulse: toysReadCheckbox("toy-policy-allow-pulse", true),
      wave: toysReadCheckbox("toy-policy-allow-wave", true),
      preset: allowPresets,
    },
  };
}

async function toysLoadLovensePolicy() {
  try {
    const data = await toysGet(`/api/lovense/sessions/${TOYS_SESSION_ID}/policy`);
    toysApplyLovensePolicy(data.policy || {});
    toysSetPolicyStatus("KI-Policy bereit. Leere Felder bleiben offen.");
  } catch (err) {
    toysSetPolicyStatus(`KI-Policy konnte nicht geladen werden (${String(err)})`, true);
  }
}

async function toysSaveLovensePolicy() {
  const button = document.getElementById("toy-policy-save");
  if (button) button.disabled = true;
  toysSetPolicyStatus("KI-Policy wird gespeichert…");
  try {
    const data = await toysPost(`/api/lovense/sessions/${TOYS_SESSION_ID}/policy`, toysCollectLovensePolicyPayload());
    toysApplyLovensePolicy(data.policy || {});
    toysSetPolicyStatus("KI-Policy gespeichert.");
  } catch (err) {
    toysSetPolicyStatus(`Speichern fehlgeschlagen (${String(err)})`, true);
  } finally {
    if (button) button.disabled = false;
  }
}

document.getElementById("dash-lovense-init")?.addEventListener("click", () => {
  toysInitLovense().catch((err) => toysSetLovenseStatus(`Lovense Start fehlgeschlagen (${String(err)})`, "Fehler"));
});
document.getElementById("dash-lovense-refresh")?.addEventListener("click", () => {
  toysRefreshLovenseQr().catch((err) => toysSetLovenseStatus(`QR konnte nicht erneuert werden (${String(err)})`, "Fehler"));
});
document.getElementById("dash-lovense-open-app")?.addEventListener("click", () => {
  if (toysLovenseSdk && typeof toysLovenseSdk.connectLovenseAPP === "function") {
    Promise.resolve(toysLovenseSdk.connectLovenseAPP()).catch((err) => {
      toysSetLovenseStatus(`Connect App konnte nicht geoeffnet werden (${String(err)})`, "Fehler");
    });
    return;
  }
  toysSetLovenseStatus("Die Connect-App-Funktion ist in diesem Browser nicht verfuegbar.", "Hinweis");
});
document.getElementById("dash-lovense-vibrate")?.addEventListener("click", () => {
  toysSendLovenseCommand("vibrate").catch((err) => toysSetLovenseStatus(`Vibration fehlgeschlagen (${String(err)})`, "Fehler"));
});
document.getElementById("dash-lovense-pulse")?.addEventListener("click", () => {
  toysSendLovenseCommand("pulse").catch((err) => toysSetLovenseStatus(`Pulse fehlgeschlagen (${String(err)})`, "Fehler"));
});
document.getElementById("dash-lovense-wave")?.addEventListener("click", () => {
  toysSendLovenseCommand("wave").catch((err) => toysSetLovenseStatus(`Wave fehlgeschlagen (${String(err)})`, "Fehler"));
});
document.getElementById("dash-lovense-stop")?.addEventListener("click", () => {
  toysSendLovenseCommand("stop").catch((err) => toysSetLovenseStatus(`Stop fehlgeschlagen (${String(err)})`, "Fehler"));
});
document.getElementById("dash-lovense-intensity")?.addEventListener("input", toysUpdateLovenseIntensityLabel);
document.getElementById("dash-lovense-toy-select")?.addEventListener("change", () => {
  toysRememberSelectedToyId(toysSelectedLovenseToyId());
  toysRenderLovenseToys(toysLovenseToys);
});
document.getElementById("dash-lovense-preset")?.addEventListener("change", toysUpdateLovensePresetCopy);
document.getElementById("dash-lovense-run-preset")?.addEventListener("click", () => {
  toysRunLovensePreset().catch((err) => toysSetLovenseStatus(`Preset fehlgeschlagen (${String(err)})`, "Fehler"));
});
document.getElementById("toy-policy-save")?.addEventListener("click", () => {
  toysSaveLovensePolicy().catch((err) => toysSetPolicyStatus(`Speichern fehlgeschlagen (${String(err)})`, true));
});
document.getElementById("toy-preset-fill-current")?.addEventListener("click", toysFillPresetEditorFromCurrent);
document.getElementById("toy-preset-save")?.addEventListener("click", () => {
  toysSaveNamedPreset().catch((err) => toysSetPolicyStatus(`Preset speichern fehlgeschlagen (${String(err)})`, true));
});
document.getElementById("toy-preset-lists")?.addEventListener("click", (event) => {
  const target = event.target;
  const runKey = target?.getAttribute?.("data-preset-run");
  const loadKey = target?.getAttribute?.("data-preset-load");
  const deleteKey = target?.getAttribute?.("data-preset-delete");
  const scope = target?.getAttribute?.("data-preset-scope") || "wearer";
  if (runKey) {
    const select = document.getElementById("dash-lovense-preset");
    if (select) select.value = runKey;
    toysUpdateLovensePresetCopy();
    toysRunLovensePreset().catch((err) => toysSetLovenseStatus(`Preset fehlgeschlagen (${String(err)})`, "Fehler"));
    return;
  }
  if (loadKey) {
    toysLoadPresetIntoEditor(scope, loadKey);
    return;
  }
  if (deleteKey) {
    toysDeleteNamedPreset(scope, deleteKey).catch((err) => toysSetPolicyStatus(`Preset loeschen fehlgeschlagen (${String(err)})`, true));
  }
});

document.addEventListener("DOMContentLoaded", async () => {
  if (!TOYS_SESSION_ID) return;
  await toysLoadPresetLibrary();
  toysApplyProfileDefaults();
  toysUpdateLovenseIntensityLabel();
  toysUpdateLovensePresetCopy();
  await toysLoadLovensePolicy();
  toysSetLovenseStatus(
    !toysLovenseEnabled
      ? "Lovense ist serverseitig deaktiviert."
      : (!toysLovenseConfigured && !toysLovenseSimulator ? "Lovense ist noch nicht vollstaendig konfiguriert." : "Lovense bereit. Initialisiere die Verbindung, um dein bevorzugtes Toy zu koppeln."),
    !toysLovenseEnabled ? "aus" : (!toysLovenseConfigured ? "Konfig" : "bereit")
  );
  if (toysPreferredProvider && toysPreferredProvider !== "none" && !toysProfileEnabled) {
    toysSetLovenseStatus(`Profil bevorzugt ${toysPreferredProvider}, Toy-Steuerung ist aber im Wearer-Profil deaktiviert.`, "Profil");
  }
  if (toysLovenseEnabled && (toysLovenseConfigured || toysLovenseSimulator) && toysShouldAutoInitLovense()) {
    toysInitLovense().catch(() => {});
  }
  toysOtcInit();
  toysLovenseGameInit();
});

// ─── OTC / Coyote 3 ──────────────────────────────────────────────────────────

function toysOtcSetStatus(message, pill) {
  const text = document.getElementById("otc-status-text");
  const chip = document.getElementById("otc-status-pill");
  if (text) text.textContent = message || "—";
  if (chip && pill != null) chip.textContent = pill;
}

function toysOtcApply(settings) {
  const s = settings || {};
  const enabledEl = document.getElementById("otc-enabled");
  const urlEl = document.getElementById("otc-url");
  const accessKeyEl = document.getElementById("otc-access-key");
  const channelEl = document.getElementById("otc-channel");
  if (enabledEl) enabledEl.value = s.enabled ? "true" : "false";
  if (urlEl) urlEl.value = String(s.otc_url || "");
  if (accessKeyEl) accessKeyEl.value = String(s.howl_access_key || "");
  if (channelEl) channelEl.value = String(s.channel || "A");
  const set = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.value = value != null ? String(value) : "";
  };
  set("otc-intensity-continuous", s.intensity_continuous ?? 30);
  set("otc-ticks-continuous", s.ticks_continuous ?? 50);
  set("otc-pattern-continuous", s.pattern_continuous ?? "RELENTLESS");
  set("otc-intensity-fail", s.intensity_fail);
  set("otc-ticks-fail", s.ticks_fail);
  set("otc-pattern-fail", s.pattern_fail ?? "RELENTLESS");
  set("otc-intensity-penalty", s.intensity_penalty);
  set("otc-ticks-penalty", s.ticks_penalty);
  set("otc-pattern-penalty", s.pattern_penalty ?? "RELENTLESS");
  set("otc-intensity-pass", s.intensity_pass);
  set("otc-ticks-pass", s.ticks_pass);
  set("otc-pattern-pass", s.pattern_pass ?? "RELENTLESS");
}

async function toysOtcLoad() {
  try {
    const data = await toysGet("/api/howl/settings");
    toysOtcApply(data);
    const status = await toysGet("/api/howl/status");
    const connected = Boolean(status.connected);
    const enabled = Boolean(data.enabled);
    toysOtcSetStatus(
      !enabled ? "Howl deaktiviert." : (connected ? "Howl erreichbar." : "Howl aktiviert, Verbindung fehlgeschlagen."),
      !enabled ? "aus" : (connected ? "bereit" : "offline")
    );
  } catch (err) {
    toysOtcSetStatus(`Laden fehlgeschlagen (${String(err)})`, "Fehler");
  }
}

function toysOtcCollect() {
  const read = (id) => {
    const el = document.getElementById(id);
    return el ? String(el.value || "").trim() : "";
  };
  const readInt = (id) => {
    const v = read(id);
    return v !== "" ? Number(v) : 0;
  };
  return {
    enabled: read("otc-enabled") === "true",
    otc_url: read("otc-url") || null,
    howl_access_key: read("otc-access-key") || null,
    channel: read("otc-channel") || "A",
    intensity_continuous: readInt("otc-intensity-continuous"),
    intensity_fail: readInt("otc-intensity-fail"),
    intensity_penalty: readInt("otc-intensity-penalty"),
    intensity_pass: readInt("otc-intensity-pass"),
    ticks_continuous: readInt("otc-ticks-continuous"),
    ticks_fail: readInt("otc-ticks-fail"),
    ticks_penalty: readInt("otc-ticks-penalty"),
    ticks_pass: readInt("otc-ticks-pass"),
    pattern_continuous: read("otc-pattern-continuous") || "RELENTLESS",
    pattern_fail: read("otc-pattern-fail") || "RELENTLESS",
    pattern_penalty: read("otc-pattern-penalty") || "RELENTLESS",
    pattern_pass: read("otc-pattern-pass") || "RELENTLESS",
  };
}

async function toysOtcSave() {
  const btn = document.getElementById("otc-save");
  if (btn) btn.disabled = true;
  toysOtcSetStatus("Wird gespeichert…");
  try {
    const resp = await fetch("/api/howl/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toysOtcCollect()),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || JSON.stringify(data));
    toysOtcApply(data);
    toysOtcSetStatus("Einstellungen gespeichert.", data.enabled ? "aktiv" : "aus");
  } catch (err) {
    toysOtcSetStatus(`Speichern fehlgeschlagen (${String(err)})`, "Fehler");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function toysOtcTest() {
  toysOtcSetStatus("Howl-Testimpuls wird gesendet\u2026");
  try {
    const channel = String(document.getElementById("otc-channel")?.value || "A");
    const intensity = Number(document.getElementById("otc-intensity-continuous")?.value || 30);
    const ticks = Number(document.getElementById("otc-ticks-continuous")?.value || 15);
    const pattern = String(document.getElementById("otc-pattern-continuous")?.value || "RELENTLESS");
    await toysPost("/api/howl/test", { channel, intensity, ticks, pattern });
    toysOtcSetStatus(`Testimpuls gesendet (Kanal\u00a0${channel}, Intensit\u00e4t\u00a0${intensity}, ${ticks}\u00a0Ticks).`, "OK");
  } catch (err) {
    toysOtcSetStatus(`Testimpuls fehlgeschlagen (${String(err)})`, "Fehler");
  }
}

function toysOtcInitFromDataset() {
  const s = toysShell?.dataset || {};
  toysOtcApply({
    enabled: s.otcEnabled === "1",
    otc_url: s.otcUrl || "",
    howl_access_key: s.otcAccessKey || "",
    channel: s.otcChannel || "A",
    intensity_continuous: Number(s.otcIntensityContinuous || 30),
    intensity_fail: Number(s.otcIntensityFail || 40),
    intensity_penalty: Number(s.otcIntensityPenalty || 70),
    intensity_pass: Number(s.otcIntensityPass || 20),
    ticks_continuous: Number(s.otcTicksContinuous || 50),
    ticks_fail: Number(s.otcTicksFail || 20),
    ticks_penalty: Number(s.otcTicksPenalty || 40),
    ticks_pass: Number(s.otcTicksPass || 10),
    pattern_continuous: s.otcPatternContinuous || "RELENTLESS",
    pattern_fail: s.otcPatternFail || "RELENTLESS",
    pattern_penalty: s.otcPatternPenalty || "RELENTLESS",
    pattern_pass: s.otcPatternPass || "RELENTLESS",
  });
}

function toysOtcInit() {
  toysOtcInitFromDataset();
  document.getElementById("otc-save")?.addEventListener("click", () => {
    toysOtcSave().catch((err) => toysOtcSetStatus(`Fehler: ${String(err)}`, "Fehler"));
  });
  document.getElementById("otc-test")?.addEventListener("click", () => {
    toysOtcTest().catch((err) => toysOtcSetStatus(`Fehler: ${String(err)}`, "Fehler"));
  });
  // Refresh live status from server (non-blocking)
  toysOtcLoad().catch(() => {});
}

// ─── Lovense Spiel-Feedback ───────────────────────────────────────────────────

function toysLovenseGameSetStatus(msg) {
  const el = document.getElementById("lovense-game-status");
  if (el) el.textContent = msg || "\u00a0";
}

function toysLovenseGameApply(s) {
  s = s || {};
  const enabled = document.getElementById("lovense-game-enabled");
  if (enabled) enabled.checked = Boolean(s.enabled);
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v != null ? String(v) : ""; };
  set("lovense-game-intensity-continuous", s.intensity_continuous ?? 6);
  set("lovense-game-duration-continuous",  s.duration_continuous  ?? 0);
  set("lovense-game-intensity-fail",       s.intensity_fail       ?? 18);
  set("lovense-game-duration-fail",        s.duration_fail        ?? 3);
  set("lovense-game-intensity-penalty",    s.intensity_penalty    ?? 20);
  set("lovense-game-duration-penalty",     s.duration_penalty     ?? 5);
  set("lovense-game-intensity-pass",       s.intensity_pass       ?? 8);
  set("lovense-game-duration-pass",        s.duration_pass        ?? 2);
}

function toysLovenseGameCollect() {
  const num = (id, lo, hi) => {
    const v = parseInt(document.getElementById(id)?.value || "0", 10);
    return Math.max(lo, Math.min(hi, isNaN(v) ? lo : v));
  };
  return {
    enabled:              Boolean(document.getElementById("lovense-game-enabled")?.checked),
    intensity_continuous: num("lovense-game-intensity-continuous", 0, 20),
    duration_continuous:  num("lovense-game-duration-continuous",  0, 300),
    intensity_fail:       num("lovense-game-intensity-fail",       0, 20),
    duration_fail:        num("lovense-game-duration-fail",        0, 300),
    intensity_penalty:    num("lovense-game-intensity-penalty",    0, 20),
    duration_penalty:     num("lovense-game-duration-penalty",     0, 300),
    intensity_pass:       num("lovense-game-intensity-pass",       0, 20),
    duration_pass:        num("lovense-game-duration-pass",        0, 300),
  };
}

async function toysLovenseGameLoad() {
  const data = await toysGet("/api/lovense-game/settings");
  toysLovenseGameApply(data);
}

async function toysLovenseGameSave() {
  toysLovenseGameSetStatus("Wird gespeichert\u2026");
  const body = toysLovenseGameCollect();
  const resp = await fetch("/api/lovense-game/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  toysLovenseGameSetStatus("Gespeichert.");
}

async function toysLovenseGameTest() {
  toysLovenseGameSetStatus("Sende Test-Impuls\u2026");
  const intensity = parseInt(document.getElementById("lovense-game-intensity-fail")?.value || "12", 10) || 12;
  const resp = await fetch("/api/lovense-game/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ intensity: Math.max(1, Math.min(20, intensity)), duration: 2 }),
  });
  const data = await resp.json().catch(() => ({}));
  if (data.ok) {
    toysLovenseGameSetStatus(`Test gesendet an ${data.uid || "Toy"} \u2013 Aktion: ${data.action || ""}.`);
  } else {
    toysLovenseGameSetStatus(`Fehler: ${data.error || "Unbekannt"}`);
  }
}

function toysLovenseGameInitFromDataset() {
  const s = toysShell?.dataset || {};
  toysLovenseGameApply({
    enabled:              s.lovenseGameEnabled === "1",
    intensity_continuous: Number(s.lovenseGameIntensityContinuous ?? 6),
    duration_continuous:  Number(s.lovenseGameDurationContinuous  ?? 0),
    intensity_fail:       Number(s.lovenseGameIntensityFail       ?? 18),
    duration_fail:        Number(s.lovenseGameDurationFail        ?? 3),
    intensity_penalty:    Number(s.lovenseGameIntensityPenalty    ?? 20),
    duration_penalty:     Number(s.lovenseGameDurationPenalty     ?? 5),
    intensity_pass:       Number(s.lovenseGameIntensityPass       ?? 8),
    duration_pass:        Number(s.lovenseGameDurationPass        ?? 2),
  });
}

function toysLovenseGameInit() {
  toysLovenseGameInitFromDataset();
  document.getElementById("lovense-game-save")?.addEventListener("click", () => {
    toysLovenseGameSave().catch((err) => toysLovenseGameSetStatus(`Fehler: ${String(err)}`));
  });
  document.getElementById("lovense-game-test")?.addEventListener("click", () => {
    toysLovenseGameTest().catch((err) => toysLovenseGameSetStatus(`Fehler: ${String(err)}`));
  });
  toysLovenseGameLoad().catch(() => {});
}
