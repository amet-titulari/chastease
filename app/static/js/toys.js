"use strict";

const toysShell = document.querySelector(".dashboard-shell");
const TOYS_SESSION_ID = Number(toysShell?.dataset.sessionId || 0);
const toysLovenseEnabled = String(toysShell?.dataset.lovenseEnabled || "") === "1";
const toysLovenseConfigured = String(toysShell?.dataset.lovenseConfigured || "") === "1";
const toysLovensePlatform = String(toysShell?.dataset.lovensePlatform || "").trim();
const toysLovenseAppType = String(toysShell?.dataset.lovenseAppType || "connect").trim() || "connect";
const toysLovenseDebug = String(toysShell?.dataset.lovenseDebug || "") === "1";
let toysLovenseSdk = null;
let toysLovenseBootstrap = null;
let toysLovenseToys = [];
let toysLovensePollHandle = null;
let toysLovenseSequenceTimeout = null;

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

function toysEsc(value) {
  return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
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

function toysSetLovenseStatus(message, pill = null) {
  const el = document.getElementById("dash-lovense-status");
  if (el) el.textContent = message || "—";
  const chip = document.getElementById("dash-lovense-app-pill");
  if (chip && pill) chip.textContent = pill;
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
  return TOYS_LOVENSE_PRESETS[presetId] || null;
}

function toysUpdateLovensePresetCopy() {
  const el = document.getElementById("dash-lovense-preset-copy");
  if (!el) return;
  const preset = toysSelectedLovensePreset();
  el.textContent = preset
    ? `${preset.label}: ${preset.description}`
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
  const chosen = toysSelectedLovenseToyId() || String(toysLovenseToys[0].id || toysLovenseToys[0].toyId || toysLovenseToys[0].toy_id || "");
  if (chosen) select.value = chosen;
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
    toysSetLovenseStatus("Lovense ist noch nicht vollstaendig konfiguriert. Es fehlen Plattformname oder Developer-Token.", "Konfig");
    return;
  }
  if (typeof window.LovenseBasicSdk !== "function") {
    toysSetLovenseStatus("Lovense SDK konnte im Browser nicht geladen werden.", "Fehler");
    return;
  }
  const bootstrap = toysLovenseBootstrap || await toysLoadLovenseBootstrap();
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
  if (!toysLovenseSdk) {
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
    toysClearLovenseSequence();
    if (typeof toysLovenseSdk.stopToyAction === "function") {
      await toysLovenseSdk.stopToyAction(commandPayload);
    } else if (typeof toysLovenseSdk.sendToyCommand === "function") {
      await toysLovenseSdk.sendToyCommand({ ...commandPayload, vibrate: 0, time: 0 });
    }
    toysSetLovenseStatus("Toy gestoppt.", "Stop");
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
  toysRenderLovenseToys(toysLovenseToys);
});
document.getElementById("dash-lovense-preset")?.addEventListener("change", toysUpdateLovensePresetCopy);
document.getElementById("dash-lovense-run-preset")?.addEventListener("click", () => {
  toysRunLovensePreset().catch((err) => toysSetLovenseStatus(`Preset fehlgeschlagen (${String(err)})`, "Fehler"));
});

document.addEventListener("DOMContentLoaded", async () => {
  if (!TOYS_SESSION_ID) return;
  toysUpdateLovenseIntensityLabel();
  toysUpdateLovensePresetCopy();
  toysSetLovenseStatus(
    !toysLovenseEnabled
      ? "Lovense ist serverseitig deaktiviert."
      : (!toysLovenseConfigured ? "Lovense ist noch nicht vollstaendig konfiguriert." : "Lovense bereit. Initialisiere die Verbindung, um deinen Edge 2 zu koppeln."),
    !toysLovenseEnabled ? "aus" : (!toysLovenseConfigured ? "Konfig" : "bereit")
  );
});
