let xpSessionId = null;
let xpWsToken = null;
let xpStep = 1;
let xpPersonaPresets = [];
let xpScenarioPresets = [];

const statusEl = document.getElementById("onboarding-status");
const outputEl = document.getElementById("xp-output");
const contractEl = document.getElementById("xp-contract-preview");
const sessionIdEl = document.getElementById("xp-session-id");
const sessionStatusEl = document.getElementById("xp-session-status");

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
    const initial = xpPersonaPresets.find((item) => item.key === "amet_titulari") || xpPersonaPresets[0];
    select.value = initial.key;
    document.getElementById("xp-persona-name").value = initial.name;
  } catch (err) {
    select.innerHTML = '<option value="">Preset-Fehler</option>';
    xpWrite("Fehler Persona Presets", { error: String(err) });
  }
}

async function xpLoadScenarioPresets() {
  const select = document.getElementById("xp-scenario-preset");
  if (!select) return;
  select.innerHTML = "";
  try {
    const data = await xpGet("/api/personas/scenario-presets");
    xpScenarioPresets = data.items || [];
    if (!xpScenarioPresets.length) {
      select.innerHTML = '<option value="">Keine Scenarios</option>';
      return;
    }
    xpScenarioPresets.forEach((preset) => {
      const opt = document.createElement("option");
      opt.value = preset.key;
      opt.textContent = preset.title;
      select.appendChild(opt);
    });
    const initialScenario = xpScenarioPresets.find((item) => item.key === "amet_titulari_devotion_protocol") || xpScenarioPresets[0];
    if (initialScenario) select.value = initialScenario.key;
  } catch (err) {
    select.innerHTML = '<option value="">Scenario-Fehler</option>';
    xpWrite("Fehler Scenario Presets", { error: String(err) });
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
    const scenarioPreset = document.getElementById("xp-scenario-preset")?.value || null;
    const noLimit = document.getElementById("xp-max-no-limit")?.checked;
    const minSecs = xpDateToSeconds(document.getElementById("xp-min-date")?.value) || xpDaysToSeconds(document.getElementById("xp-min-days")?.value || "7");
    const maxSecs = noLimit ? 0 : (xpDateToSeconds(document.getElementById("xp-max-date")?.value) || xpDaysToSeconds(document.getElementById("xp-max-days")?.value || "30"));
    const payload = {
      persona_name: document.getElementById("xp-persona-name").value,
      player_nickname: document.getElementById("xp-player-nickname").value,
      min_duration_seconds: Math.max(60, minSecs),
      max_duration_seconds: noLimit ? null : Math.max(60, maxSecs),
      hygiene_limit_daily: xpParseOptionalInt(document.getElementById("xp-hygiene-day").value),
      hygiene_limit_weekly: xpParseOptionalInt(document.getElementById("xp-hygiene-week").value),
      hygiene_limit_monthly: xpParseOptionalInt(document.getElementById("xp-hygiene-month").value),
      experience_level: document.getElementById("xp-experience-level").value || "beginner",
      scenario_preset: scenarioPreset,
    };
    const created = await xpPost("/api/sessions", payload);
    xpSessionId = created.session_id;
    xpWsToken = created.ws_auth_token;
    sessionIdEl.textContent = String(xpSessionId);
    sessionStatusEl.textContent = created.status;
    contractEl.textContent = created.contract_preview || "(keine Vorschau)";

    const profilePayload = {
      experience_level: document.getElementById("xp-experience-level").value,
      preferences: {
        scenario_preset: document.getElementById("xp-scenario-preset")?.value || null,
      },
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
    await xpPost(`/api/sessions/${xpSessionId}/sign-contract`, {});
    window.location.href = `/play/${xpSessionId}`;
  } catch (err) {
    xpWrite("Fehler Signatur", { error: String(err) });
  }
});



xpLoadPersonaPresets();
xpLoadScenarioPresets();
xpInitDurationDefaults();
xpWireDuration("xp-min-date", "xp-min-days", "xp-min-summary");
xpWireDuration("xp-max-date", "xp-max-days", "xp-max-summary");
xpWireNoLimit();
xpSwitchStep(1);

// Pre-fill hard limits from setup boundary
(function xpPrefillHardLimits() {
  const input = document.getElementById("xp-hard-limits");
  if (!input) return;
  const raw = (input.dataset.setupBoundary || "").trim();
  if (!raw) return;
  const keywords = raw
    .split(/[\n,]+/)
    .map((s) => s.replace(/^[-*•]\s*/, "").trim())
    .map((s) => s.replace(/^(keine|kein|no)\s+/i, "").trim())
    .filter((s) => s.length > 2 && s.length < 60);
  if (keywords.length > 0) input.value = keywords.join(", ");
})();
