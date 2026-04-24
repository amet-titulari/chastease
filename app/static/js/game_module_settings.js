(() => {
  const runtime = window.ChasteaseUiRuntime || {};
  const MODULES = Array.isArray(window.GAME_MODULES) ? window.GAME_MODULES : [];

  function slugKey(value) {
    return String(value || "").replace(/[^a-zA-Z0-9_\-]+/g, "_");
  }

  function setGlobalMsg(msg, warn = false) {
    const el = document.getElementById("gms-global-msg");
    if (!el) return;
    el.textContent = msg || "";
    el.className = warn ? "gms-status warn" : "gms-status ok";
  }

  function setModuleMsg(moduleKey, msg, warn = false) {
    const el = document.getElementById(`gms-module-msg-${slugKey(moduleKey)}`);
    if (!el) return;
    el.textContent = msg || "";
    el.className = warn ? "gms-status warn" : "gms-status ok";
  }

  async function api(url, options = {}) {
    if (typeof runtime.jsonRequest === "function") {
      return runtime.jsonRequest(url, options);
    }
    const res = await fetch(url, options);
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(payload.detail || res.statusText || "Fehler");
    return payload;
  }

  function numberInputValue(id, fallback = 0) {
    const raw = String(document.getElementById(id)?.value ?? fallback).trim();
    const normalized = raw.replace(",", ".");
    const val = Number(normalized);
    return Number.isFinite(val) ? val : fallback;
  }

  function decimalToPercent(value, fallback = 0) {
    const base = Number(value);
    const safe = Number.isFinite(base) ? base : fallback;
    return safe * 100;
  }

  function percentToDecimal(value, fallback = 0) {
    const base = Number(value);
    const safe = Number.isFinite(base) ? base : fallback;
    return safe / 100;
  }

  function formatPercent(value, digits = 2) {
    const num = Number(value);
    if (!Number.isFinite(num)) return "0";
    return num.toFixed(digits).replace(/\.0+$/, "").replace(/(\.\d*[1-9])0+$/, "$1");
  }

  const MOVEMENT_PRESETS = {
    dont_move: {
      tolerant: {
        easy: { pose: 0.82, still: 0.26 },
        medium: { pose: 0.68, still: 0.16 },
        hard: { pose: 0.52, still: 0.095 },
      },
      balanced: {
        easy: { pose: 0.28, still: 0.0450 },
        medium: { pose: 0.25, still: 0.0380 },
        hard: { pose: 0.22, still: 0.0320 },
      },
      strict: {
        easy: { pose: 0.36, still: 0.0360 },
        medium: { pose: 0.32, still: 0.0300 },
        hard: { pose: 0.28, still: 0.0250 },
      },
    },
    tiptoeing: {
      tolerant: {
        easy: { pose: 0.12, still: 0.18 },
        medium: { pose: 0.15, still: 0.22 },
        hard: { pose: 0.18, still: 0.25 },
      },
      balanced: {
        easy: { pose: 0.14, still: 0.22 },
        medium: { pose: 0.18, still: 0.26 },
        hard: { pose: 0.22, still: 0.30 },
      },
      strict: {
        easy: { pose: 0.18, still: 0.28 },
        medium: { pose: 0.22, still: 0.32 },
        hard: { pose: 0.26, still: 0.36 },
      },
    },
  };

  function movementPresetFor(moduleKeyValue, level) {
    const mod = MOVEMENT_PRESETS[moduleKeyValue] || MOVEMENT_PRESETS.dont_move;
    return mod[level] || mod.balanced;
  }

  function moduleFieldId(moduleKey, field) {
    return `gms-${slugKey(moduleKey)}-${field}`;
  }

  function globalPayloadFromInputs() {
    return {
      easy_target_multiplier: numberInputValue("gms-global-easy-mult", 0.75),
      hard_target_multiplier: numberInputValue("gms-global-hard-mult", 1.5),
      target_randomization_percent: Math.round(numberInputValue("gms-global-random", 10)),
      start_countdown_seconds: Math.round(numberInputValue("gms-global-start-countdown", 5)),
      game_feedback_mode: String(document.getElementById("gms-global-feedback-mode")?.value || "both"),
    };
  }

  function applyGlobalSettings(data) {
    document.getElementById("gms-global-easy-mult").value = String(Number(data.easy_target_multiplier ?? 0.75));
    document.getElementById("gms-global-hard-mult").value = String(Number(data.hard_target_multiplier ?? 1.5));
    document.getElementById("gms-global-random").value = String(Number(data.target_randomization_percent ?? 10));
    document.getElementById("gms-global-start-countdown").value = String(Number(data.start_countdown_seconds ?? 5));
    const modeEl = document.getElementById("gms-global-feedback-mode");
    if (modeEl) {
      const mode = String(data.game_feedback_mode || "both");
      modeEl.value = mode === "stim_only" || mode === "ai_summary_only" ? mode : "both";
    }
  }

  async function loadGlobalSettings() {
    const data = await api("/api/games/settings/global");
    applyGlobalSettings(data || {});
  }

  async function saveGlobalSettings() {
    const payload = globalPayloadFromInputs();
    const saved = await api("/api/games/settings/global", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    applyGlobalSettings(saved || payload);
    setGlobalMsg("Globale Konfiguration gespeichert.", false);
  }

  function applyMovementFields(moduleKey, data) {
    const easyPoseEl = document.getElementById(moduleFieldId(moduleKey, "easy-pose"));
    const easyStillEl = document.getElementById(moduleFieldId(moduleKey, "easy-still"));
    const mediumPoseEl = document.getElementById(moduleFieldId(moduleKey, "medium-pose"));
    const mediumStillEl = document.getElementById(moduleFieldId(moduleKey, "medium-still"));
    const hardPoseEl = document.getElementById(moduleFieldId(moduleKey, "hard-pose"));
    const hardStillEl = document.getElementById(moduleFieldId(moduleKey, "hard-still"));
    if (!(easyPoseEl instanceof HTMLInputElement)) return;
    if (!(easyStillEl instanceof HTMLInputElement)) return;
    if (!(mediumPoseEl instanceof HTMLInputElement)) return;
    if (!(mediumStillEl instanceof HTMLInputElement)) return;
    if (!(hardPoseEl instanceof HTMLInputElement)) return;
    if (!(hardStillEl instanceof HTMLInputElement)) return;

    easyPoseEl.value = formatPercent(decimalToPercent(data.movement_easy_pose_deviation ?? 0.28));
    easyStillEl.value = formatPercent(decimalToPercent(data.movement_easy_stillness ?? 0.045));
    mediumPoseEl.value = formatPercent(decimalToPercent(data.movement_medium_pose_deviation ?? 0.25));
    mediumStillEl.value = formatPercent(decimalToPercent(data.movement_medium_stillness ?? 0.038));
    hardPoseEl.value = formatPercent(decimalToPercent(data.movement_hard_pose_deviation ?? 0.22));
    hardStillEl.value = formatPercent(decimalToPercent(data.movement_hard_stillness ?? 0.032));
  }

  function defaultPoseSimilarityThreshold(moduleKey, difficultyKey) {
    const byModule = {
      posture_training: { easy: 62, medium: 74, hard: 84 },
      dont_move: { easy: 58, medium: 64, hard: 72 },
      tiptoeing: { easy: 8, medium: 10, hard: 12 },
    };
    const defaults = byModule[moduleKey] || { easy: 0, medium: 0, hard: 0 };
    return Number(defaults[difficultyKey] ?? 0);
  }

  function applyPoseSimilarityFields(moduleKey, data) {
    const easyDefault = defaultPoseSimilarityThreshold(moduleKey, "easy");
    const mediumDefault = defaultPoseSimilarityThreshold(moduleKey, "medium");
    const hardDefault = defaultPoseSimilarityThreshold(moduleKey, "hard");

    const easyRaw = Number(data.pose_similarity_min_score_easy);
    const mediumRaw = Number(data.pose_similarity_min_score_medium);
    const hardRaw = Number(data.pose_similarity_min_score_hard);

    const easyValue = Number.isFinite(easyRaw) && easyRaw > 0 ? easyRaw : easyDefault;
    const mediumValue = Number.isFinite(mediumRaw) && mediumRaw > 0 ? mediumRaw : mediumDefault;
    const hardValue = Number.isFinite(hardRaw) && hardRaw > 0 ? hardRaw : hardDefault;

    document.getElementById(moduleFieldId(moduleKey, "pose-score-easy")).value = String(Number(easyValue));
    document.getElementById(moduleFieldId(moduleKey, "pose-score-medium")).value = String(Number(mediumValue));
    document.getElementById(moduleFieldId(moduleKey, "pose-score-hard")).value = String(Number(hardValue));
  }

  async function loadModuleSettings(moduleKey) {
    const data = await api(`/api/games/modules/${moduleKey}/settings`);
    applyMovementFields(moduleKey, data || {});
    applyPoseSimilarityFields(moduleKey, data || {});
    const slug = slugKey(moduleKey);
    const maskPreview = document.getElementById(`gms-mask-preview-${slug}`);
    if (maskPreview instanceof HTMLImageElement) {
      const maskUrl = data?.mask_image_url || "/static/masks/tiptoeing-mask.png";
      maskPreview.src = maskUrl;
    }
  }

  function movementPayloadFromInputs(moduleKey) {
    return {
      movement_easy_pose_deviation: percentToDecimal(numberInputValue(moduleFieldId(moduleKey, "easy-pose"), 28.0), 0.28),
      movement_easy_stillness: percentToDecimal(numberInputValue(moduleFieldId(moduleKey, "easy-still"), 4.5), 0.045),
      movement_medium_pose_deviation: percentToDecimal(numberInputValue(moduleFieldId(moduleKey, "medium-pose"), 25.0), 0.25),
      movement_medium_stillness: percentToDecimal(numberInputValue(moduleFieldId(moduleKey, "medium-still"), 3.8), 0.038),
      movement_hard_pose_deviation: percentToDecimal(numberInputValue(moduleFieldId(moduleKey, "hard-pose"), 22.0), 0.22),
      movement_hard_stillness: percentToDecimal(numberInputValue(moduleFieldId(moduleKey, "hard-still"), 3.2), 0.032),
    };
  }

  function poseSimilarityPayloadFromInputs(moduleKey) {
    return {
      pose_similarity_min_score_easy: numberInputValue(moduleFieldId(moduleKey, "pose-score-easy"), defaultPoseSimilarityThreshold(moduleKey, "easy")),
      pose_similarity_min_score_medium: numberInputValue(moduleFieldId(moduleKey, "pose-score-medium"), defaultPoseSimilarityThreshold(moduleKey, "medium")),
      pose_similarity_min_score_hard: numberInputValue(moduleFieldId(moduleKey, "pose-score-hard"), defaultPoseSimilarityThreshold(moduleKey, "hard")),
    };
  }

  async function saveModuleSettings(moduleKey) {
    const payload = {
      ...globalPayloadFromInputs(),
      ...movementPayloadFromInputs(moduleKey),
      ...poseSimilarityPayloadFromInputs(moduleKey),
    };
    await api(`/api/games/modules/${moduleKey}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setModuleMsg(moduleKey, "Modul-Konfiguration gespeichert.", false);
  }

  function applyMovementPreset(moduleKey, level) {
    const easyPoseEl = document.getElementById(moduleFieldId(moduleKey, "easy-pose"));
    const easyStillEl = document.getElementById(moduleFieldId(moduleKey, "easy-still"));
    const mediumPoseEl = document.getElementById(moduleFieldId(moduleKey, "medium-pose"));
    const mediumStillEl = document.getElementById(moduleFieldId(moduleKey, "medium-still"));
    const hardPoseEl = document.getElementById(moduleFieldId(moduleKey, "hard-pose"));
    const hardStillEl = document.getElementById(moduleFieldId(moduleKey, "hard-still"));
    if (!(easyPoseEl instanceof HTMLInputElement)) return;
    if (!(easyStillEl instanceof HTMLInputElement)) return;
    if (!(mediumPoseEl instanceof HTMLInputElement)) return;
    if (!(mediumStillEl instanceof HTMLInputElement)) return;
    if (!(hardPoseEl instanceof HTMLInputElement)) return;
    if (!(hardStillEl instanceof HTMLInputElement)) return;

    const preset = movementPresetFor(moduleKey, level);
    easyPoseEl.value = formatPercent(decimalToPercent(preset.easy.pose));
    easyStillEl.value = formatPercent(decimalToPercent(preset.easy.still));
    mediumPoseEl.value = formatPercent(decimalToPercent(preset.medium.pose));
    mediumStillEl.value = formatPercent(decimalToPercent(preset.medium.still));
    hardPoseEl.value = formatPercent(decimalToPercent(preset.hard.pose));
    hardStillEl.value = formatPercent(decimalToPercent(preset.hard.still));
    setModuleMsg(moduleKey, `Preset ${level} angewendet. Bitte speichern.`, false);
  }

  function moduleCardHtml(module) {
    const key = String(module.key || "");
    const slug = slugKey(key);
    const title = String(module.title || key);
    const summary = String(module.summary || "");
    const isPostureTraining = key === "posture_training";
    const poseScoreEasyDefault = defaultPoseSimilarityThreshold(key, "easy");
    const poseScoreMediumDefault = defaultPoseSimilarityThreshold(key, "medium");
    const poseScoreHardDefault = defaultPoseSimilarityThreshold(key, "hard");
    const movementRows = isPostureTraining
      ? ""
      : `
            <p class="gms-metric-label gms-metric-pose">${key === "tiptoeing" ? "Schwarz-Schwelle % (hoeher = strenger)" : "Pose-Abweichung % (kleiner = strenger)"}<span class="gms-help" title="${key === "tiptoeing" ? "Pixel mit niedrigeren RGB-Werten gelten als verboten (schwarz). Hoeherer Wert macht die Schwarz-Erkennung strenger." : "Maximal erlaubte Abweichung zur Zielpose. Niedriger Wert bedeutet strengere Erkennung."}">?</span></p>
          <input id="gms-${slug}-easy-pose" type="number" min="1" max="100" step="0.1" value="${key === "tiptoeing" ? "14" : "40"}" />
          <input id="gms-${slug}-medium-pose" type="number" min="1" max="100" step="0.1" value="${key === "tiptoeing" ? "18" : "35"}" />
          <input id="gms-${slug}-hard-pose" type="number" min="1" max="100" step="0.1" value="${key === "tiptoeing" ? "22" : "22.5"}" />

            <p class="gms-metric-label gms-metric-still">${key === "tiptoeing" ? "Gruen-Minimum % (hoeher = strenger)" : "Stillness % (kleiner = strenger)"}<span class="gms-help" title="${key === "tiptoeing" ? "Minimaler Gruenkanal fuer erlaubte Zone. Hoeherer Wert erfordert ein klareres Gruen." : "Maximal erlaubte Bewegung waehrend des Haltens. Niedriger Wert bedeutet strengere Erkennung."}">?</span></p>
          <input id="gms-${slug}-easy-still" type="number" min="0.05" max="100" step="0.01" value="${key === "tiptoeing" ? "22" : "4.0"}" />
          <input id="gms-${slug}-medium-still" type="number" min="0.05" max="100" step="0.01" value="${key === "tiptoeing" ? "26" : "3.0"}" />
          <input id="gms-${slug}-hard-still" type="number" min="0.05" max="100" step="0.01" value="${key === "tiptoeing" ? "30" : "2.0"}" />
      `;
    const helpBlock = isPostureTraining
      ? `
      <div class="gms-metric-help-list" aria-live="polite">
        <p class="gms-metric-help-line"><strong>Pose-Score Minimum:</strong> Mindestwert der Pose-Aehnlichkeit. Hoeher = strenger. Startempfehlung in diesem Modul: 62 / 74 / 84.</p>
      </div>
      `
      : `
      <div class="gms-metric-help-list" aria-live="polite">
        <p class="gms-metric-help-line"><strong>${key === "tiptoeing" ? "Gruen-Ueberhang %" : "Pose-Score Minimum"}:</strong> ${key === "tiptoeing" ? "Wie deutlich Gruen gegen Rot/Blau dominieren muss. Hoeher = strenger." : "Mindestwert der Pose-Aehnlichkeit. Hoeher = strenger."}</p>
        <p class="gms-metric-help-line"><strong>${key === "tiptoeing" ? "Schwarz-Schwelle %" : "Pose-Abweichung %"}:</strong> ${key === "tiptoeing" ? "Ab wann ein Pixel als verbotene schwarze Zone gilt. Hoeher = strenger." : "Maximal erlaubte Abweichung zur Zielpose. Kleiner = strenger."}</p>
        <p class="gms-metric-help-line"><strong>${key === "tiptoeing" ? "Gruen-Minimum %" : "Stillness %"}:</strong> ${key === "tiptoeing" ? "Minimaler Gruenwert fuer die erlaubte Zone. Hoeher = strenger." : "Maximal erlaubte Bewegung waehrend des Haltens. Kleiner = strenger."}</p>
      </div>
      `;
    return `
    <article class="gms-module-card" data-module-key="${key}">
      <h3>${title}</h3>
      <p class="gms-module-summary">${summary}</p>
      <div class="gms-matrix-wrap">
        <div class="gms-matrix">
          <div class="gms-matrix-head">Metrik</div>
          <div class="gms-matrix-head">Easy</div>
          <div class="gms-matrix-head">Medium</div>
          <div class="gms-matrix-head">Hard</div>

          <p class="gms-metric-label gms-metric-score">${key === "tiptoeing" ? "Gruen-Ueberhang % (hoeher = strenger)" : "Pose-Score Minimum (%)"}<span class="gms-help" title="${key === "tiptoeing" ? "Minimaler Abstand Gruen zu Rot/Blau. Hoeherer Wert bedeutet strengere Farberkennung." : "Mindestwert fuer die Pose-Aehnlichkeit. Hoeherer Wert bedeutet strengere Erkennung."}">?</span></p>
          <input id="gms-${slug}-pose-score-easy" type="number" min="0" max="100" step="0.1" value="${poseScoreEasyDefault}" />
          <input id="gms-${slug}-pose-score-medium" type="number" min="0" max="100" step="0.1" value="${poseScoreMediumDefault}" />
          <input id="gms-${slug}-pose-score-hard" type="number" min="0" max="100" step="0.1" value="${poseScoreHardDefault}" />
          ${movementRows}
        </div>
      </div>
      ${helpBlock}
      ${key === "tiptoeing" ? `
      <div class="gms-mask-section">
        <h4>Masken-Bild</h4>
        <p class="gms-note">Gruene Bereiche = erlaubte Fusszone, schwarze Bereiche = verboten. Fuer Tiptoeing zaehlen nur Fusskontakte; zusaetzlich muessen die Fersen sichtbar angehoben bleiben.</p>
        <div class="gms-mask-row">
          <img id="gms-mask-preview-${slug}" class="gms-mask-thumb" alt="Aktuelle Maske" />
          <div class="gms-mask-upload">
            <input type="file" id="gms-mask-file-${slug}" accept="image/png,image/jpeg,image/webp" />
            <button type="button" class="ghost gms-upload-mask-btn" data-module-key="${key}">Maske hochladen</button>
          </div>
        </div>
        <p id="gms-mask-msg-${slug}" class="gms-status"></p>
      </div>
      ` : ""}
      <div class="gms-actions">
        <button type="button" class="gms-save-module" data-module-key="${key}">Modul speichern</button>
      </div>
      <p id="gms-module-msg-${slug}" class="gms-status"></p>
    </article>
  `;
  }

  function renderModuleCards() {
    const root = document.getElementById("gms-module-cards");
    if (!root) return;
    root.innerHTML = MODULES.map((module) => moduleCardHtml(module)).join("");
  }

  async function uploadMaskImage(moduleKey) {
    const slug = slugKey(moduleKey);
    const fileInput = document.getElementById(`gms-mask-file-${slug}`);
    const msgEl = document.getElementById(`gms-mask-msg-${slug}`);
    if (!(fileInput instanceof HTMLInputElement) || !fileInput.files?.length) {
      if (msgEl) {
        msgEl.textContent = "Bitte zuerst eine Bilddatei auswaehlen.";
        msgEl.classList.add("warn");
      }
      return;
    }
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    if (msgEl) {
      msgEl.textContent = "Wird hochgeladen...";
      msgEl.classList.remove("warn");
    }
    const result = await api(`/api/games/modules/${moduleKey}/mask`, {
      method: "POST",
      body: formData,
    });
    const preview = document.getElementById(`gms-mask-preview-${slug}`);
    if (preview instanceof HTMLImageElement && result.mask_image_url) {
      preview.src = result.mask_image_url;
    }
    if (msgEl) {
      msgEl.textContent = "Maske erfolgreich hochgeladen.";
      msgEl.classList.remove("warn");
    }
    fileInput.value = "";
  }

  function bindEvents() {
    document.getElementById("gms-save-global")?.addEventListener("click", () => {
      saveGlobalSettings().catch((err) => setGlobalMsg(`Speichern fehlgeschlagen: ${err.message}`, true));
    });

    document.getElementById("gms-module-cards")?.addEventListener("click", (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;

      const presetBtn = target.closest(".gms-preset-btn");
      if (presetBtn instanceof HTMLButtonElement) {
        const level = String(presetBtn.dataset.preset || "balanced");
        const moduleKey = String(presetBtn.dataset.moduleKey || "");
        if (moduleKey) applyMovementPreset(moduleKey, level);
        return;
      }

      const saveBtn = target.closest(".gms-save-module");
      if (saveBtn instanceof HTMLButtonElement) {
        const moduleKey = String(saveBtn.dataset.moduleKey || "");
        if (!moduleKey) return;
        saveModuleSettings(moduleKey).catch((err) => setModuleMsg(moduleKey, `Speichern fehlgeschlagen: ${err.message}`, true));
        return;
      }

      const maskBtn = target.closest(".gms-upload-mask-btn");
      if (maskBtn instanceof HTMLButtonElement) {
        const moduleKey = String(maskBtn.dataset.moduleKey || "");
        if (!moduleKey) return;
        uploadMaskImage(moduleKey).catch((err) => {
          const slug = slugKey(moduleKey);
          const msgEl = document.getElementById(`gms-mask-msg-${slug}`);
          if (msgEl) {
            msgEl.textContent = `Upload fehlgeschlagen: ${err.message}`;
            msgEl.classList.add("warn");
          }
        });
      }
    });
  }

  async function init() {
    renderModuleCards();
    bindEvents();
    await loadGlobalSettings();
    await Promise.all(MODULES.map((module) => loadModuleSettings(String(module.key || ""))));
  }

  init().catch((err) => setGlobalMsg(`Initialisierung fehlgeschlagen: ${err.message}`, true));
})();
