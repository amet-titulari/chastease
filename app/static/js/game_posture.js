const bootstrap = window.GAME_POSTURE_BOOTSTRAP || {};
const sessionId = Number(bootstrap.sessionId || 0);
const moduleKey = String(bootstrap.moduleKey || "");
const isDontMoveModule = moduleKey === "dont_move";
const isTiptoeingModule = moduleKey === "tiptoeing";
const TIPTOEING_MASK_FALLBACK_URL = "/static/masks/tiptoeing-mask.png";
let tiptoeingMaskUrl = TIPTOEING_MASK_FALLBACK_URL;
const singlePoseModuleKeys = new Set(["dont_move", "tiptoeing"]);
const isSinglePoseModule = singlePoseModuleKeys.has(moduleKey);
const initialDifficulty = bootstrap.initialDifficulty ?? null;
let runId = bootstrap.latestRunId ?? null;
let activeRun = null;
let cameraStream = null;
let totalTimerHandle = null;
let phaseTimerHandle = null;
let runPollHandle = null;
let dontMoveMonitorHandle = null;
let postureScoreMonitorHandle = null;
let movementPose = null;
let movementFileset = null;
let movementPoseReady = false;
let movementPoseBusy = false;
let movementLatestPoseLandmarks = null;
let movementLatestWorldLandmarks = null;
let movementLastWorldLandmarks = null;
let movementTargetWorldLandmarks = null;
let movementStrikeCount = 0;
let movementCooldownUntil = 0;
let movementRedFlashUntil = 0;
let movementEventInFlight = false;
let movementMonitorActive = false;
let movementLastMarker = null;
let movementPendingViolation = null;
let movementLocalPreviewUrl = null;
let movementPendingLocalCaptureUrls = [];
let movementPoseMissingFrames = 0;
let movementOverlayMode = "idle";
let tiptoeingMaskImage = null;
let tiptoeingMaskReady = false;
let tiptoeingOutsideGreenFrames = 0;
let tiptoeingFlatFootFrames = 0;
let strictStartStableFrames = 0;
let strictStartDebugText = "";
let postureOverlayStatus = "idle";
let postureInconclusiveCount = 0;
let currentReferenceLandmarksJson = null;
let sequenceToken = 0;
let skeletonMonitorHandle = null;
let sequenceStepId = null;
let availableCameraDevices = [];
let selectedCameraDeviceId = "";
let verifyInFlight = false;
let runRefreshInFlight = false;
let audioCtx = null;
let beepVolume = 0.35;
let moduleSettings = {
  easy_target_multiplier: 0.85,
  hard_target_multiplier: 1.25,
  target_randomization_percent: 10,
  movement_easy_pose_deviation: null,
  movement_easy_stillness: null,
  movement_medium_pose_deviation: null,
  movement_medium_stillness: null,
  movement_hard_pose_deviation: null,
  movement_hard_stillness: null,
  pose_similarity_min_score_easy: null,
  pose_similarity_min_score_medium: null,
  pose_similarity_min_score_hard: null,
};

const statusEl = document.getElementById("gm-status");
const setupSectionEl = document.getElementById("gm-setup-section");
const playStageEl = document.getElementById("gm-play-stage");
const phaseLabelEl = document.getElementById("gm-phase-label");
const phaseCountdownEl = document.getElementById("gm-phase-countdown");
const postureNameEl = document.getElementById("gm-posture-name");
const postureInstructionEl = document.getElementById("gm-posture-instruction");
const postureImageEl = document.getElementById("gm-posture-image");
const runStatusEl = document.getElementById("gm-run-status");
const totalTimerEl = document.getElementById("gm-total-timer");
const missCountEl = document.getElementById("gm-miss-count");
const retryTimeEl = document.getElementById("gm-retry-time");
const analysisEl = document.getElementById("gm-analysis");
const uploadDebugEl = document.getElementById("gm-upload-debug");
const verifyThumbEl = document.getElementById("gm-verify-thumb");
const captureGalleryEl = document.getElementById("gm-capture-gallery");
const finalReportEl = document.getElementById("gm-final-report");
const setupVideoEl = document.getElementById("gm-setup-video");
const playVideoEl = document.getElementById("gm-video");
const feedWrapEl = document.getElementById("gm-feed-wrap");
const motionOverlayEl = document.getElementById("gm-motion-overlay");
const beepVolumeEl = document.getElementById("gm-beep-volume");
const testBeepEl = document.getElementById("gm-test-beep");
const dontMoveOptionsEl = document.getElementById("gm-dont-move-options");
const dontMovePostureEl = document.getElementById("gm-dont-move-posture");
const missLabelEl = document.getElementById("gm-miss-label");
const transitionWrapEl = document.getElementById("gm-transition-wrap");
const transitionLabelTextEl = document.getElementById("gm-transition-label-text");
const maxMissesWrapEl = document.getElementById("gm-max-misses-wrap");
const sessionPenaltyLabelTextEl = document.getElementById("gm-session-penalty-label-text");
const cameraGuidanceEl = document.getElementById("gm-camera-guidance");
const maskPreviewEl = document.getElementById("gm-mask-preview");
const cameraDeviceEl = document.getElementById("gm-camera-device");
const cameraQualityEl = document.getElementById("gm-camera-quality");
const cameraDeviceLabelEl = document.getElementById("gm-camera-device-label");
const cameraMetaBoxEl = document.getElementById("gm-camera-meta-box");
const cameraStartBtnEl = document.getElementById("gm-cam-start");

finalReportEl?.addEventListener("click", (event) => {
  const target = event.target.closest("[data-gm-report-image]");
  if (!target) return;
  const imageUrl = String(target.getAttribute("data-gm-report-image") || "").trim();
  if (!imageUrl) return;
  window.open(imageUrl, "_blank");
});

const cameraDeviceStorageKey = "game_posture_camera_device_id";

const movementWatchIndices = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32];
const movementPoseCompareIndices = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32];
const dontMoveCoreReferenceParts = [
  "left_shoulder",
  "right_shoulder",
  "left_hip",
  "right_hip",
];
const dontMoveCoreAngleTriplets = [
  ["left_shoulder", "left_hip", "right_hip"],
  ["right_shoulder", "right_hip", "left_hip"],
];
const dontMoveArmReferenceParts = [
  "left_shoulder",
  "right_shoulder",
  "left_elbow",
  "right_elbow",
  "left_wrist",
  "right_wrist",
];
const dontMoveLegReferenceParts = [
  "left_hip",
  "right_hip",
  "left_knee",
  "right_knee",
  "left_ankle",
  "right_ankle",
];
const dontMoveZonePartMap = {
  core: dontMoveCoreReferenceParts,
  arms: dontMoveArmReferenceParts,
  legs: dontMoveLegReferenceParts,
};
const dontMoveArmAngleTriplets = [
  ["left_shoulder", "left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow", "right_wrist"],
  ["left_elbow", "left_shoulder", "left_hip"],
  ["right_elbow", "right_shoulder", "right_hip"],
];
const dontMoveLegAngleTriplets = [
  ["left_hip", "left_knee", "left_ankle"],
  ["right_hip", "right_knee", "right_ankle"],
  ["left_shoulder", "left_hip", "left_knee"],
  ["right_shoulder", "right_hip", "right_knee"],
];
const dontMoveReferenceEdges = [
  ["left_shoulder", "right_shoulder"],
  ["left_shoulder", "left_elbow"],
  ["left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow"],
  ["right_elbow", "right_wrist"],
  ["left_shoulder", "left_hip"],
  ["right_shoulder", "right_hip"],
  ["left_hip", "right_hip"],
  ["left_hip", "left_knee"],
  ["left_knee", "left_ankle"],
  ["right_hip", "right_knee"],
  ["right_knee", "right_ankle"],
];
const dontMoveZoneWeights = {
  core: 0.42,
  arms: 0.38,
  legs: 0.20,
};
const postureReferencePointToIndex = {
  left_shoulder: 11,
  right_shoulder: 12,
  left_elbow: 13,
  right_elbow: 14,
  left_wrist: 15,
  right_wrist: 16,
  left_hip: 23,
  right_hip: 24,
  left_knee: 25,
  right_knee: 26,
  left_ankle: 27,
  right_ankle: 28,
};
const referenceAngleTriplets = [
  ["left_shoulder", "left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow", "right_wrist"],
  ["left_hip", "left_knee", "left_ankle"],
  ["right_hip", "right_knee", "right_ankle"],
  ["left_shoulder", "left_hip", "left_knee"],
  ["right_shoulder", "right_hip", "right_knee"],
];
const postureSkeletonConnections = [
  [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
  [15, 17], [15, 19], [17, 19], [16, 18], [16, 20], [18, 20],
  [11, 23], [12, 24], [23, 24],
  [23, 25], [24, 26], [25, 27], [26, 28],
  [27, 29], [28, 30], [29, 31], [30, 32], [27, 31], [28, 32],
];
const movementDefaults = {
  dont_move: {
    easy: { poseDeviation: 0.28, stillness: 0.0450 },
    medium: { poseDeviation: 0.25, stillness: 0.0380 },
    hard: { poseDeviation: 0.22, stillness: 0.0320 },
  },
  tiptoeing: {
    easy: { poseDeviation: 0.14, stillness: 0.22 },
    medium: { poseDeviation: 0.18, stillness: 0.26 },
    hard: { poseDeviation: 0.22, stillness: 0.30 },
  },
};

const TASKS_VISION_SCRIPT_URLS = [
  "/static/vendor/mediapipe/tasks-vision/0.10.14/vision_bundle.mjs",
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs",
  "https://unpkg.com/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs",
];

const TASKS_VISION_WASM_ROOTS = [
  "/static/vendor/mediapipe/tasks-vision/0.10.14/wasm",
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm",
  "https://unpkg.com/@mediapipe/tasks-vision@0.10.14/wasm",
];

let visionModule = null;

async function ensureVisionLoaded() {
  if (visionModule) return;

  let lastError = null;
  for (const url of TASKS_VISION_SCRIPT_URLS) {
    try {
      const mod = await import(url);
      if (mod && mod.FilesetResolver && mod.PoseLandmarker) {
        visionModule = mod;
        return;
      }
    } catch (err) {
      lastError = err;
    }
  }

  throw new Error(
    `MediaPipe Tasks Vision konnte nicht geladen werden (${lastError ? lastError.message : "CDN blockiert"})`
  );
}

function setStatus(msg, warn = false) {
  statusEl.textContent = msg || "";
  statusEl.className = warn ? "game-meta warn" : "game-meta";
}

function setUploadDebug(msg, warn = false) {
  if (!uploadDebugEl) return;
  uploadDebugEl.textContent = msg || "";
  uploadDebugEl.className = warn ? "game-meta warn" : "game-meta";
}

function revokeMovementLocalPreview() {
  if (!movementLocalPreviewUrl) return;
  try {
    URL.revokeObjectURL(movementLocalPreviewUrl);
  } catch {
    // Ignore object URL cleanup failures.
  }
  movementLocalPreviewUrl = null;
}

function clearPendingLocalCaptureGallery() {
  if (!captureGalleryEl) return;
  captureGalleryEl.querySelectorAll('[data-local-pending="true"]').forEach((node) => {
    const url = node.getAttribute("data-object-url");
    if (url) {
      try {
        URL.revokeObjectURL(url);
      } catch {
        // Ignore object URL cleanup failures.
      }
    }
    node.remove();
  });
  movementPendingLocalCaptureUrls = [];
}

function appendPendingLocalCaptureThumbnail(objectUrl) {
  if (!captureGalleryEl || !objectUrl) return;
  const alreadyPresent = Array.from(captureGalleryEl.querySelectorAll("[data-object-url]"))
    .some((node) => node.getAttribute("data-object-url") === objectUrl);
  if (alreadyPresent) return;
  const img = document.createElement("img");
  img.src = objectUrl;
  img.alt = "Lokales Kontrollbild";
  img.className = "capture-thumb fail";
  img.setAttribute("data-local-pending", "true");
  img.setAttribute("data-object-url", objectUrl);
  captureGalleryEl.prepend(img);
  movementPendingLocalCaptureUrls.unshift(objectUrl);
  while (captureGalleryEl.children.length > 60) {
    const last = captureGalleryEl.lastElementChild;
    if (!last) break;
    const url = last.getAttribute("data-object-url");
    if (url) {
      try {
        URL.revokeObjectURL(url);
      } catch {
        // Ignore object URL cleanup failures.
      }
    }
    captureGalleryEl.removeChild(last);
  }
}

function loadStoredCameraDeviceId() {
  try {
    return String(window.localStorage.getItem(cameraDeviceStorageKey) || "").trim();
  } catch {
    return "";
  }
}

function storeCameraDeviceId(deviceId) {
  try {
    if (deviceId) {
      window.localStorage.setItem(cameraDeviceStorageKey, deviceId);
    } else {
      window.localStorage.removeItem(cameraDeviceStorageKey);
    }
  } catch {
    // Ignore storage failures.
  }
}

function currentVideoTrack() {
  return cameraStream?.getVideoTracks?.()[0] || null;
}

function cameraLabelText(value) {
  return String(value || "").trim().toLowerCase();
}

function isUltrawideCameraLabel(value) {
  const text = cameraLabelText(value);
  return text.includes("ultra") || text.includes("weitwinkel") || text.includes("wide") || text.includes("0.5");
}

function isFrontCameraLabel(value) {
  const text = cameraLabelText(value);
  return text.includes("front") || text.includes("vorder") || text.includes("selfie") || text.includes("face");
}

function cameraDeviceRank(device) {
  const label = cameraLabelText(device?.label);
  let score = 0;

  if (label.includes("r\u00fcck") || label.includes("back") || label.includes("rear") || label.includes("environment")) score += 50;
  if (label.includes("wide") || label.includes("weitwinkel")) score += 8;
  if (label.includes("standard") || label.includes("normal")) score += 12;
  if (label.includes("tele")) score -= 8;
  if (isFrontCameraLabel(label)) score -= 12;
  if (isUltrawideCameraLabel(label)) score -= 30;

  return score;
}

function preferredCameraDeviceId() {
  if (!availableCameraDevices.length) return "";
  const ranked = [...availableCameraDevices].sort((left, right) => cameraDeviceRank(right) - cameraDeviceRank(left));
  return String(ranked[0]?.deviceId || "").trim();
}

function effectiveCameraDeviceId() {
  return String(selectedCameraDeviceId || preferredCameraDeviceId() || "").trim();
}

function activeCameraLabel(track = null) {
  const deviceId = String(track?.getSettings?.().deviceId || selectedCameraDeviceId || "").trim();
  const match = availableCameraDevices.find((item) => String(item.deviceId || "") === deviceId);
  return match?.label || track?.label || "Kamera";
}

function updateCameraMeta(track = null) {
  const liveTrack = track || currentVideoTrack();
  if (!cameraMetaBoxEl || !cameraQualityEl || !cameraDeviceLabelEl) return;

  if (!liveTrack) {
    cameraMetaBoxEl.classList.add("hidden");
    cameraMetaBoxEl.classList.remove("warn");
    cameraQualityEl.textContent = "";
    cameraDeviceLabelEl.textContent = "";
    return;
  }

  const settings = typeof liveTrack.getSettings === "function" ? liveTrack.getSettings() : {};
  const width = Number(settings.width || playVideoEl.videoWidth || setupVideoEl.videoWidth || 0);
  const height = Number(settings.height || playVideoEl.videoHeight || setupVideoEl.videoHeight || 0);
  const frameRate = Number(settings.frameRate || 0);
  const pixels = width * height;
  const isLowQuality = pixels > 0 && pixels < (1280 * 720);
  const label = activeCameraLabel(liveTrack);
  const isUltrawide = isUltrawideCameraLabel(label);
  const isFront = isFrontCameraLabel(label);
  const fpsText = Number.isFinite(frameRate) && frameRate > 0 ? ` · ${frameRate.toFixed(frameRate >= 10 ? 0 : 1)} fps` : "";

  cameraMetaBoxEl.classList.remove("hidden");
  cameraMetaBoxEl.classList.toggle("warn", isLowQuality || isUltrawide);
  cameraQualityEl.textContent = width > 0 && height > 0
    ? `Aktive Stream-Qualitaet: ${width} x ${height}${fpsText}`
    : "Aktive Stream-Qualitaet: unbekannt";
  cameraDeviceLabelEl.textContent = `Aktive Kamera: ${label}`;

  if (isLowQuality) {
    setStatus(`Die aktive Kamera liefert nur ${width} x ${height}. Bitte andere Kamera waehlen oder Kamera neu verbinden.`, true);
    return;
  }

  if (isUltrawide) {
    const hint = isFront
      ? "Ultra-Weitwinkel-Frontkamera erkannt. Diese Linse verzerrt Koerperproportionen und verschlechtert die Pose-Erkennung."
      : "Ultra-Weitwinkelkamera erkannt. Diese Linse kann die Pose-Erkennung durch starke Verzeichnung verschlechtern.";
    setStatus(hint, true);
  }
}

function updateCameraSelectorOptions() {
  if (!cameraDeviceEl) return;

  const previous = String(selectedCameraDeviceId || cameraDeviceEl.value || "").trim();
  cameraDeviceEl.innerHTML = "";

  if (availableCameraDevices.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Standardkamera";
    cameraDeviceEl.appendChild(option);
    cameraDeviceEl.disabled = true;
    return;
  }

  const autoOption = document.createElement("option");
  autoOption.value = "";
  autoOption.textContent = "Automatische Kamerawahl (empfohlen)";
  cameraDeviceEl.appendChild(autoOption);

  availableCameraDevices.forEach((device, index) => {
    const option = document.createElement("option");
    option.value = String(device.deviceId || "");
    option.textContent = String(device.label || `Kamera ${index + 1}`);
    cameraDeviceEl.appendChild(option);
  });

  cameraDeviceEl.disabled = false;
  const valid = previous && availableCameraDevices.some((device) => String(device.deviceId || "") === previous);
  cameraDeviceEl.value = valid ? previous : "";
  selectedCameraDeviceId = String(cameraDeviceEl.value || "").trim();
}

async function refreshCameraDevices() {
  if (!navigator.mediaDevices?.enumerateDevices) return;
  const devices = await navigator.mediaDevices.enumerateDevices();
  availableCameraDevices = devices.filter((item) => item.kind === "videoinput");
  if (!selectedCameraDeviceId) {
    selectedCameraDeviceId = loadStoredCameraDeviceId();
  }
  updateCameraSelectorOptions();
}

function fmtSecs(total) {
  const s = Math.max(0, Number(total || 0));
  const m = Math.floor(s / 60).toString().padStart(2, "0");
  const sec = Math.floor(s % 60).toString().padStart(2, "0");
  return `${m}:${sec}`;
}

async function api(url, options = {}) {
  const res = await fetch(url, options);
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || res.statusText);
  return payload;
}

function getAudioContext() {
  if (!audioCtx) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    audioCtx = new Ctx();
  }
  return audioCtx;
}

function beep() {
  const ctx = getAudioContext();
  if (!ctx) return;
  if (ctx.state === "suspended") {
    ctx.resume().catch(() => {});
  }
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.value = 920;
  gain.gain.value = Math.max(0, Math.min(0.25, beepVolume * 0.25));
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.1);
}

function beepDouble() {
  beep();
  window.setTimeout(() => beep(), 180);
}

function applyBeepVolume(percentValue, persist = true) {
  const safePercent = Math.max(0, Math.min(100, Number(percentValue || 0)));
  beepVolume = safePercent / 100;
  beepVolumeEl.value = String(safePercent);
  if (persist) {
    window.localStorage.setItem("game_beep_volume_percent", String(safePercent));
  }
}

function initializeBeepVolume() {
  const stored = window.localStorage.getItem("game_beep_volume_percent");
  const initialPercent = stored !== null ? Number(stored) : Number(beepVolumeEl.value || 35);
  applyBeepVolume(initialPercent, false);
}

function syncMotionOverlaySize() {
  if (!motionOverlayEl || !feedWrapEl) return;
  const rect = feedWrapEl.getBoundingClientRect();
  motionOverlayEl.width = Math.max(1, Math.floor(rect.width));
  motionOverlayEl.height = Math.max(1, Math.floor(rect.height));
}

async function ensureTiptoeingMaskLoaded() {
  if (!isTiptoeingModule) return;
  if (tiptoeingMaskReady && tiptoeingMaskImage) return;

  const img = new Image();
  img.decoding = "async";
  img.src = tiptoeingMaskUrl;

  await new Promise((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error("Tiptoeing-Maske konnte nicht geladen werden"));
  });

  tiptoeingMaskImage = img;
  tiptoeingMaskReady = true;
}

function isMaskBlack(r, g, b, a, profile) {
  const blackLimit = Math.round(Math.max(0, Math.min(255, Number(profile?.blackThreshold || 0.18) * 255)));
  return a > 32 && r <= blackLimit && g <= blackLimit && b <= blackLimit;
}

function isMaskGreen(r, g, b, a, profile) {
  const greenMin = Math.round(Math.max(0, Math.min(255, Number(profile?.greenMinThreshold || 0.26) * 255)));
  const dominance = Math.round(Math.max(0, Math.min(255, Number(profile?.dominanceThreshold || 0.10) * 255)));
  return a > 32 && g >= greenMin && g >= (r + dominance) && g >= (b + dominance);
}

function readTiptoeingMaskZone(nx, ny, profile) {
  if (!tiptoeingMaskReady || !tiptoeingMaskImage) return "none";

  const xNorm = Math.max(0, Math.min(1, Number(nx || 0)));
  const yNorm = Math.max(0, Math.min(1, Number(ny || 0)));
  const sampleCanvas = document.createElement("canvas");
  sampleCanvas.width = Math.max(1, motionOverlayEl?.width || 1);
  sampleCanvas.height = Math.max(1, motionOverlayEl?.height || 1);
  const sampleCtx = sampleCanvas.getContext("2d", { willReadFrequently: true });
  if (!sampleCtx) return "none";

  sampleCtx.drawImage(tiptoeingMaskImage, 0, 0, sampleCanvas.width, sampleCanvas.height);
  const px = Math.max(0, Math.min(sampleCanvas.width - 1, Math.round(xNorm * (sampleCanvas.width - 1))));
  const py = Math.max(0, Math.min(sampleCanvas.height - 1, Math.round(yNorm * (sampleCanvas.height - 1))));
  const data = sampleCtx.getImageData(px, py, 1, 1).data;
  const r = Number(data[0] || 0);
  const g = Number(data[1] || 0);
  const b = Number(data[2] || 0);
  const a = Number(data[3] || 0);

  if (isMaskBlack(r, g, b, a, profile)) return "black";
  if (isMaskGreen(r, g, b, a, profile)) return "green";
  return "neutral";
}

function drawMotionOverlay(marker = null, forceAlert = false) {
  if (!motionOverlayEl || !isSinglePoseModule) return;
  const ctx = motionOverlayEl.getContext("2d");
  if (!ctx) return;
  const w = motionOverlayEl.width;
  const h = motionOverlayEl.height;
  if (!w || !h || w < 20 || h < 20) {
    syncMotionOverlaySize();
    return;
  }

  ctx.clearRect(0, 0, w, h);
  const isAlert = forceAlert || Date.now() < movementRedFlashUntil;
  if (!movementMonitorActive && !isAlert) {
    return;
  }

  if (isTiptoeingModule && tiptoeingMaskReady && tiptoeingMaskImage) {
    ctx.save();
    ctx.globalAlpha = isAlert ? 0.4 : 0.32;
    ctx.drawImage(tiptoeingMaskImage, 0, 0, w, h);
    ctx.restore();
  }

  const stroke = isAlert
    ? "rgba(255, 72, 72, 0.96)"
    : movementOverlayMode === "positioning"
      ? "rgba(88, 178, 255, 0.96)"
      : "rgba(56, 221, 112, 0.96)";
  const fill = isAlert
    ? "rgba(255, 72, 72, 0.07)"
    : movementOverlayMode === "positioning"
      ? "rgba(88, 178, 255, 0.08)"
      : "rgba(56, 221, 112, 0.05)";
  const zoneFeedback = currentDontMoveZoneFeedback();
  const startFeedback = currentDontMoveStartOverlayFeedback();

  let effectiveStroke = stroke;
  let effectiveFill = fill;
  if (isDontMoveModule && startFeedback && !isAlert) {
    if (startFeedback.tone === "blocked") {
      effectiveStroke = "rgba(255, 124, 124, 0.96)";
      effectiveFill = "rgba(255, 92, 92, 0.07)";
    } else if (startFeedback.tone === "stabilizing") {
      effectiveStroke = "rgba(255, 194, 82, 0.96)";
      effectiveFill = "rgba(255, 194, 82, 0.08)";
    } else if (startFeedback.tone === "countdown" || startFeedback.tone === "ready") {
      effectiveStroke = "rgba(56, 221, 112, 0.96)";
      effectiveFill = "rgba(56, 221, 112, 0.06)";
    }
  }

  if (!isDontMoveModule) {
    ctx.fillStyle = effectiveFill;
    ctx.fillRect(0, 0, w, h);
  }
  if (currentReferenceLandmarksJson) {
    drawReferenceSkeletonOnCanvas(ctx, w, h, currentReferenceLandmarksJson, zoneFeedback);
  }
  if (isDontMoveModule && Array.isArray(movementLatestPoseLandmarks) && movementLatestPoseLandmarks.length > 0) {
    drawDontMoveLiveSkeleton(ctx, w, h, movementLatestPoseLandmarks, zoneFeedback);
  }

  ctx.lineWidth = Math.max(4, Math.floor(Math.min(w, h) * 0.012));
  ctx.strokeStyle = effectiveStroke;
  ctx.strokeRect(ctx.lineWidth / 2, ctx.lineWidth / 2, w - ctx.lineWidth, h - ctx.lineWidth);

  if (!isDontMoveModule && marker && Number.isFinite(marker.x) && Number.isFinite(marker.y)) {
    const mx = Math.max(0, Math.min(w, marker.x * w));
    const my = Math.max(0, Math.min(h, marker.y * h));
    const r = Math.max(10, Math.floor(Math.min(w, h) * 0.03));
    ctx.beginPath();
    ctx.arc(mx, my, r, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(255, 64, 64, 0.98)";
    ctx.lineWidth = Math.max(3, Math.floor(Math.min(w, h) * 0.006));
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(mx - r - 8, my);
    ctx.lineTo(mx + r + 8, my);
    ctx.moveTo(mx, my - r - 8);
    ctx.lineTo(mx, my + r + 8);
    ctx.stroke();
  }

  if (!isDontMoveModule && movementOverlayMode === "positioning" && strictStartDebugText) {
    const lines = String(strictStartDebugText).split("\n").slice(0, 2);
    const fontSize = Math.max(14, Math.floor(Math.min(w, h) * 0.028));
    const lineHeight = fontSize + 7;
    const boxWidth = Math.min(260, Math.max(180, Math.floor(w * 0.32)));
    const boxHeight = (lines.length * lineHeight) + 16;
    const boxX = 12;
    const boxY = Math.max(12, h - boxHeight - 16);
    ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
    ctx.fillRect(boxX, boxY, boxWidth, boxHeight);
    ctx.fillStyle = "rgba(230, 244, 255, 0.96)";
    ctx.font = `700 ${fontSize}px sans-serif`;
    ctx.textBaseline = "top";
    lines.forEach((line, idx) => {
      ctx.fillText(line, boxX + 10, boxY + 8 + (idx * lineHeight), boxWidth - 20);
    });
  }
}

function referencePointsFromJson(referenceJson) {
  if (!referenceJson) return null;
  try {
    const parsed = JSON.parse(referenceJson);
    const points = parsed?.points;
    if (!points || typeof points !== "object") return null;

    const normalized = {};
    Object.entries(points).forEach(([name, value]) => {
      const x = Number(value?.x);
      const y = Number(value?.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return;
      normalized[name] = {
        x,
        y,
        visibility: Number.isFinite(Number(value?.visibility)) ? Number(value.visibility) : 1.0,
      };
    });
    return normalized;
  } catch {
    return null;
  }
}

function livePoseFrameFromLandmarks(landmarks) {
  if (!Array.isArray(landmarks) || landmarks.length === 0) return null;
  const leftHip = landmarks[23];
  const rightHip = landmarks[24];
  const leftShoulder = landmarks[11];
  const rightShoulder = landmarks[12];
  if (!leftHip || !rightHip || !leftShoulder || !rightShoulder) return null;

  // Full-body required: hip and shoulder visibility needed for stable anchor.
  const required = [leftHip, rightHip, leftShoulder, rightShoulder];
  if (required.some((item) => Number(item.visibility ?? 1) < 0.35)) return null;

  const centerX = (Number(leftHip.x || 0) + Number(rightHip.x || 0)) / 2;
  const centerY = (Number(leftHip.y || 0) + Number(rightHip.y || 0)) / 2;
  const shoulderCenterX = (Number(leftShoulder.x || 0) + Number(rightShoulder.x || 0)) / 2;
  const shoulderCenterY = (Number(leftShoulder.y || 0) + Number(rightShoulder.y || 0)) / 2;
  const shoulderDist = Math.hypot(
    Number(leftShoulder.x || 0) - Number(rightShoulder.x || 0),
    Number(leftShoulder.y || 0) - Number(rightShoulder.y || 0)
  );
  const torsoDist = Math.hypot(shoulderCenterX - centerX, shoulderCenterY - centerY);
  const scale = shoulderDist > 0.02 ? shoulderDist : torsoDist;
  if (!Number.isFinite(scale) || scale <= 0.02) return null;

  return { centerX, centerY, scale };
}

function dontMoveZoneForReferencePart(name) {
  if (dontMoveZonePartMap.arms.includes(name)) return "arms";
  if (dontMoveZonePartMap.legs.includes(name)) return "legs";
  if (dontMoveZonePartMap.core.includes(name)) return "core";
  return "core";
}

function dontMoveZoneOverlayColor(zoneName, isBad = false) {
  return isBad ? "rgba(255, 88, 88, 0.98)" : "rgba(56, 221, 112, 0.96)";
}

function currentDontMoveZoneFeedback() {
  if (!isDontMoveModule || !currentReferenceLandmarksJson || !Array.isArray(movementLatestPoseLandmarks)) {
    return null;
  }
  const score = scoreLivePoseAgainstReference(currentReferenceLandmarksJson, movementLatestPoseLandmarks);
  const threshold = movementOverlayMode === "active" ? strictHoldPoseThreshold() : strictStartReadyThreshold();
  const visibilityMetrics = dontMoveVisibilityMetrics(currentReferenceLandmarksJson, movementLatestPoseLandmarks);
  const readiness = evaluateDontMoveReadiness(score, visibilityMetrics, threshold);
  if (!score || !score.zones || !readiness) return null;
  return {
    threshold,
    zones: {
      core: {
        score: Number(score.zones.core ?? 0),
        bad: !readiness.coreOk,
      },
      arms: {
        score: Number(score.zones.arms ?? 0),
        bad: !readiness.armsOk,
      },
      legs: {
        score: Number(score.zones.legs ?? 0),
        bad: !readiness.legsOk,
      },
    },
  };
}

function currentDontMoveStartOverlayFeedback() {
  if (!isDontMoveModule || movementOverlayMode !== "positioning" || !Array.isArray(movementLatestPoseLandmarks)) {
    return null;
  }
  const verdict = strictStartVerdict(movementLatestPoseLandmarks);
  const stableTarget = strictStartStableFrameTarget();
  const stableFrames = Math.max(0, Number(strictStartStableFrames || 0));
  if (!verdict?.ready) {
    const lines = String(verdict?.debug || "").split("\n").map((line) => String(line || "").trim()).filter(Boolean);
    const compactDetail = String(lines[2] || lines[1] || verdict?.analysis || "Pose weiter ausrichten.")
      .replace(/^Sichtbar:\s*/i, "")
      .replace(/^Pose\s+\d+(?:\.\d+)?\/100,\s*Start ab\s+\d+(?:\.\d+)?\s*/i, "")
      .trim();
    return {
      tone: "blocked",
      message: compactDetail || "Pose weiter ausrichten",
    };
  }
  if (stableFrames < stableTarget) {
    return {
      tone: "stabilizing",
      message: `Stabilisiere ${stableFrames}/${stableTarget}`,
    };
  }
  const debugText = String(strictStartDebugText || "");
  const countdownMatch = debugText.match(/Countdown:\s*(\d+)/i);
  if (countdownMatch) {
    return {
      tone: "countdown",
      message: `Countdown ${countdownMatch[1]}`,
    };
  }
  return {
    tone: "ready",
    message: "Startbereit",
  };
}

function drawReferenceSkeletonOnCanvas(ctx, width, height, referenceJson, zoneFeedback = null) {
  const points = referencePointsFromJson(referenceJson);
  if (!points) return;

  const liveFrame = livePoseFrameFromLandmarks(movementLatestPoseLandmarks);
  // When live pose is not yet detected (e.g. user is still stepping into frame)
  // draw the reference skeleton as a static guide centred in the canvas so the
  // user knows where to stand. Use a typical torso height as the scale.
  const frame = liveFrame || (() => {
    // Estimate a sensible scale from the reference itself (hip-to-shoulder distance).
    const ls = points.left_shoulder;
    const rs = points.right_shoulder;
    const lh = points.left_hip;
    const rh = points.right_hip;
    if (!ls || !rs || !lh || !rh) return null;
    const shoulderDist = Math.hypot(ls.x - rs.x, ls.y - rs.y);
    const scale = shoulderDist > 0.02 ? shoulderDist : 0.18;
    // Centre slightly above mid-frame so a standing person is well-placed.
    return { centerX: 0.5, centerY: 0.58, scale };
  })();
  if (!frame) return;

  ctx.save();
  ctx.setLineDash([8, 7]);
  ctx.lineCap = "round";

  // White backing keeps the black target visible on dark and bright backgrounds.
  ctx.strokeStyle = "rgba(255, 255, 255, 0.7)";
  ctx.lineWidth = Math.max(3, Math.floor(Math.min(width, height) * 0.008));

  for (const [fromName, toName] of dontMoveReferenceEdges) {
    const fromRef = points[fromName];
    const toRef = points[toName];
    const from = fromRef ? {
      x: frame.centerX + (Number(fromRef.x || 0) * frame.scale),
      y: frame.centerY + (Number(fromRef.y || 0) * frame.scale),
      visibility: fromRef.visibility,
    } : null;
    const to = toRef ? {
      x: frame.centerX + (Number(toRef.x || 0) * frame.scale),
      y: frame.centerY + (Number(toRef.y || 0) * frame.scale),
      visibility: toRef.visibility,
    } : null;
    if (!from || !to) continue;
    if (Number(from.visibility ?? 1) < 0.35 || Number(to.visibility ?? 1) < 0.35) continue;
    const zoneName = dontMoveZoneForReferencePart(fromName);
    const zoneBad = Boolean(zoneFeedback?.zones?.[zoneName]?.bad);
    ctx.beginPath();
    ctx.moveTo(Number(from.x || 0) * width, Number(from.y || 0) * height);
    ctx.lineTo(Number(to.x || 0) * width, Number(to.y || 0) * height);
    if (zoneBad) {
      ctx.strokeStyle = "rgba(255, 255, 255, 0.92)";
      ctx.lineWidth = Math.max(5, Math.floor(Math.min(width, height) * 0.011));
    } else {
      ctx.strokeStyle = "rgba(255, 255, 255, 0.72)";
      ctx.lineWidth = Math.max(4, Math.floor(Math.min(width, height) * 0.009));
    }
    ctx.stroke();
  }

  for (const [fromName, toName] of dontMoveReferenceEdges) {
    const fromRef = points[fromName];
    const toRef = points[toName];
    const from = fromRef ? {
      x: frame.centerX + (Number(fromRef.x || 0) * frame.scale),
      y: frame.centerY + (Number(fromRef.y || 0) * frame.scale),
      visibility: fromRef.visibility,
    } : null;
    const to = toRef ? {
      x: frame.centerX + (Number(toRef.x || 0) * frame.scale),
      y: frame.centerY + (Number(toRef.y || 0) * frame.scale),
      visibility: toRef.visibility,
    } : null;
    if (!from || !to) continue;
    if (Number(from.visibility ?? 1) < 0.35 || Number(to.visibility ?? 1) < 0.35) continue;
    const zoneName = dontMoveZoneForReferencePart(fromName);
    const zoneBad = Boolean(zoneFeedback?.zones?.[zoneName]?.bad);
    ctx.beginPath();
    ctx.moveTo(Number(from.x || 0) * width, Number(from.y || 0) * height);
    ctx.lineTo(Number(to.x || 0) * width, Number(to.y || 0) * height);
    ctx.strokeStyle = dontMoveZoneOverlayColor(zoneName, zoneBad);
    ctx.lineWidth = zoneBad
      ? Math.max(3, Math.floor(Math.min(width, height) * 0.007))
      : Math.max(2, Math.floor(Math.min(width, height) * 0.0055));
    ctx.stroke();
  }

  ctx.setLineDash([]);
  Object.entries(points).forEach(([name, pointRef]) => {
    const point = pointRef ? {
      x: frame.centerX + (Number(pointRef.x || 0) * frame.scale),
      y: frame.centerY + (Number(pointRef.y || 0) * frame.scale),
      visibility: pointRef.visibility,
    } : null;
    if (!point || Number(point.visibility ?? 1) < 0.35) return;
    const px = Number(point.x || 0) * width;
    const py = Number(point.y || 0) * height;
    const zoneName = dontMoveZoneForReferencePart(name);
    const zoneBad = Boolean(zoneFeedback?.zones?.[zoneName]?.bad);
    const radius = zoneBad
      ? Math.max(5, Math.floor(Math.min(width, height) * 0.012))
      : Math.max(4, Math.floor(Math.min(width, height) * 0.01));
    ctx.beginPath();
    ctx.arc(px, py, radius + 2, 0, Math.PI * 2);
    ctx.fillStyle = zoneBad ? "rgba(255, 255, 255, 0.92)" : "rgba(255, 255, 255, 0.75)";
    ctx.fill();
    ctx.beginPath();
    ctx.arc(px, py, radius, 0, Math.PI * 2);
    ctx.fillStyle = zoneBad ? dontMoveZoneOverlayColor(zoneName, true) : "rgba(12, 12, 12, 0.88)";
    ctx.fill();
  });
  ctx.restore();
}

function postureOverlayPalette(status, hasPose) {
  if (status === "suspicious") {
    return {
      stroke: "rgba(255, 72, 72, 0.96)",
      line: "rgba(255, 120, 120, 0.9)",
      joint: "rgba(255, 196, 196, 0.96)",
      fill: "rgba(255, 72, 72, 0.08)",
    };
  }
  if (!hasPose || status === "inconclusive" || status === "idle") {
    return {
      stroke: "rgba(255, 194, 82, 0.96)",
      line: "rgba(255, 210, 120, 0.92)",
      joint: "rgba(255, 237, 196, 0.98)",
      fill: "rgba(255, 194, 82, 0.08)",
    };
  }
  return {
    stroke: "rgba(56, 221, 112, 0.96)",
    line: "rgba(56, 221, 112, 0.88)",
    joint: "rgba(176, 244, 204, 0.96)",
    fill: "rgba(56, 221, 112, 0.07)",
  };
}

function drawDontMoveLiveSkeleton(ctx, width, height, landmarks, zoneFeedback = null) {
  const visibleLandmarks = Array.isArray(landmarks)
    ? landmarks.filter((item) => item && Number(item.visibility ?? 1) >= 0.45)
    : [];
  if (visibleLandmarks.length < 6) return;

  ctx.save();
  ctx.lineCap = "round";
  for (const [fromIdx, toIdx] of postureSkeletonConnections) {
    const from = landmarks[fromIdx];
    const to = landmarks[toIdx];
    if (!from || !to) continue;
    if (Number(from.visibility ?? 1) < 0.45 || Number(to.visibility ?? 1) < 0.45) continue;
    const fromName = Object.keys(postureReferencePointToIndex).find((key) => postureReferencePointToIndex[key] === fromIdx) || "";
    const zoneName = dontMoveZoneForReferencePart(fromName);
    const zoneBad = Boolean(zoneFeedback?.zones?.[zoneName]?.bad);
    ctx.beginPath();
    ctx.moveTo(Number(from.x || 0) * width, Number(from.y || 0) * height);
    ctx.lineTo(Number(to.x || 0) * width, Number(to.y || 0) * height);
    ctx.strokeStyle = zoneBad ? "rgba(255, 120, 120, 0.98)" : "rgba(120, 235, 180, 0.94)";
    ctx.lineWidth = zoneBad
      ? Math.max(5, Math.floor(Math.min(width, height) * 0.0105))
      : Math.max(4, Math.floor(Math.min(width, height) * 0.008));
    ctx.stroke();
  }

  Object.entries(postureReferencePointToIndex).forEach(([name, idx]) => {
    const item = landmarks[idx];
    if (!item || Number(item.visibility ?? 1) < 0.45) return;
    const zoneName = dontMoveZoneForReferencePart(name);
    const zoneBad = Boolean(zoneFeedback?.zones?.[zoneName]?.bad);
    const px = Number(item.x || 0) * width;
    const py = Number(item.y || 0) * height;
    const radius = zoneBad
      ? Math.max(7, Math.floor(Math.min(width, height) * 0.014))
      : Math.max(5, Math.floor(Math.min(width, height) * 0.011));
    ctx.beginPath();
    ctx.arc(px, py, radius + 2, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(0, 0, 0, 0.58)";
    ctx.fill();
    ctx.beginPath();
    ctx.arc(px, py, radius, 0, Math.PI * 2);
    ctx.fillStyle = zoneBad ? dontMoveZoneOverlayColor(zoneName, true) : "rgba(190, 255, 230, 0.96)";
    ctx.fill();
  });
  ctx.restore();
}

function drawSkeletonOnCanvas(landmarks = null) {
  if (!motionOverlayEl || moduleKey !== "posture_training") return;
  const ctx = motionOverlayEl.getContext("2d");
  if (!ctx) return;

  const w = motionOverlayEl.width;
  const h = motionOverlayEl.height;
  if (!w || !h || w < 20 || h < 20) {
    syncMotionOverlaySize();
    return;
  }

  ctx.clearRect(0, 0, w, h);
  const visibleLandmarks = Array.isArray(landmarks)
    ? landmarks.filter((item) => item && Number(item.visibility ?? 1) >= 0.45)
    : [];
  const hasPose = visibleLandmarks.length >= 6;
  const palette = postureOverlayPalette(postureOverlayStatus, hasPose);

  ctx.save();
  ctx.fillStyle = palette.fill;
  ctx.fillRect(0, 0, w, h);
  ctx.lineWidth = Math.max(4, Math.floor(Math.min(w, h) * 0.012));
  ctx.strokeStyle = palette.stroke;
  ctx.strokeRect(ctx.lineWidth / 2, ctx.lineWidth / 2, w - ctx.lineWidth, h - ctx.lineWidth);
  drawReferenceSkeletonOnCanvas(ctx, w, h, currentReferenceLandmarksJson);

  if (!hasPose) {
    ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
    ctx.fillRect(12, 12, Math.min(w - 24, 190), 34);
    ctx.fillStyle = "rgba(255, 236, 236, 0.98)";
    ctx.font = `600 ${Math.max(13, Math.floor(Math.min(w, h) * 0.033))}px sans-serif`;
    ctx.textBaseline = "middle";
    ctx.fillText("Keine Pose erkannt", 24, 29);
    ctx.restore();
    return;
  }

  ctx.strokeStyle = palette.line;
  ctx.lineWidth = Math.max(2, Math.floor(Math.min(w, h) * 0.007));
  for (const [fromIdx, toIdx] of postureSkeletonConnections) {
    const from = landmarks[fromIdx];
    const to = landmarks[toIdx];
    if (!from || !to) continue;
    if (Number(from.visibility ?? 1) < 0.45 || Number(to.visibility ?? 1) < 0.45) continue;
    ctx.beginPath();
    ctx.moveTo(Number(from.x || 0) * w, Number(from.y || 0) * h);
    ctx.lineTo(Number(to.x || 0) * w, Number(to.y || 0) * h);
    ctx.stroke();
  }

  const radius = Math.max(3, Math.floor(Math.min(w, h) * 0.012));
  ctx.fillStyle = palette.joint;
  for (const item of visibleLandmarks) {
    ctx.beginPath();
    ctx.arc(Number(item.x || 0) * w, Number(item.y || 0) * h, radius, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function activeDifficultyKey() {
  return String((activeRun && activeRun.difficulty) || document.getElementById("gm-difficulty").value || "medium");
}

function strictStartReadyThreshold() {
  if (isTiptoeingModule) return 1;
  const diff = activeDifficultyKey();
  const raw = Number(moduleSettings?.[`pose_similarity_min_score_${diff}`]);
  const fallback = isDontMoveModule
    ? (diff === "easy" ? 58 : (diff === "hard" ? 72 : 64))
    : (diff === "easy" ? 45 : (diff === "hard" ? 65 : 55));
  if (isDontMoveModule) {
    return Math.max(fallback, Number.isFinite(raw) && raw > 0 ? raw : 0);
  }
  return Number.isFinite(raw) && raw > 0 ? raw : fallback;
}

function strictHoldPoseThreshold() {
  const startThreshold = strictStartReadyThreshold();
  if (!isDontMoveModule) return startThreshold;
  return Math.max(48, startThreshold - 6);
}

function strictStartStableFrameTarget() {
  if (isDontMoveModule) return 4;
  if (isTiptoeingModule) return 5;
  return 6;
}

function movementViolationStrikeTarget() {
  const diff = activeDifficultyKey();
  if (isDontMoveModule) {
    if (diff === "easy") return 12;
    if (diff === "hard") return 8;
    return 10;
  }
  return 4;
}

function movementPoseMissingFrameTarget() {
  const diff = activeDifficultyKey();
  if (!isDontMoveModule) return 7;
  if (diff === "easy") return 12;
  if (diff === "hard") return 8;
  return 10;
}

function movementProfile() {
  const diff = activeDifficultyKey();
  const moduleProfile = movementDefaults[moduleKey] || movementDefaults.dont_move;
  const fallback = moduleProfile[diff] || moduleProfile.medium;

  const poseKey = `movement_${diff}_pose_deviation`;
  const stillnessKey = `movement_${diff}_stillness`;
  const poseVal = Number(moduleSettings?.[poseKey]);
  const stillnessVal = Number(moduleSettings?.[stillnessKey]);

  if (Number.isFinite(poseVal) && poseVal > 0 && Number.isFinite(stillnessVal) && stillnessVal > 0) {
    return {
      poseDeviation: poseVal,
      stillness: stillnessVal,
    };
  }
  return fallback;
}

function tiptoeingMaskProfile() {
  const diff = activeDifficultyKey();
  const fallback = movementDefaults.tiptoeing[diff] || movementDefaults.tiptoeing.medium;

  const blackRaw = Number(moduleSettings?.[`movement_${diff}_pose_deviation`]);
  const greenMinRaw = Number(moduleSettings?.[`movement_${diff}_stillness`]);
  const dominancePctRaw = Number(moduleSettings?.[`pose_similarity_min_score_${diff}`]);

  const blackThreshold = Number.isFinite(blackRaw) && blackRaw > 0 ? blackRaw : fallback.poseDeviation;
  const greenMinThreshold = Number.isFinite(greenMinRaw) && greenMinRaw > 0 ? greenMinRaw : fallback.stillness;
  const dominanceDefaultPct = diff === "easy" ? 8 : (diff === "hard" ? 12 : 10);
  const dominanceThreshold = (
    Number.isFinite(dominancePctRaw) && dominancePctRaw > 0
      ? (dominancePctRaw / 100)
      : (dominanceDefaultPct / 100)
  );

  return {
    blackThreshold: Math.max(0.01, Math.min(0.95, blackThreshold)),
    greenMinThreshold: Math.max(0.01, Math.min(0.95, greenMinThreshold)),
    dominanceThreshold: Math.max(0.01, Math.min(0.95, dominanceThreshold)),
  };
}

function jointAngleDeg(a, b, c) {
  const baX = Number(a?.x || 0) - Number(b?.x || 0);
  const baY = Number(a?.y || 0) - Number(b?.y || 0);
  const bcX = Number(c?.x || 0) - Number(b?.x || 0);
  const bcY = Number(c?.y || 0) - Number(b?.y || 0);
  const magBA = Math.hypot(baX, baY);
  const magBC = Math.hypot(bcX, bcY);
  if (magBA <= 1e-9 || magBC <= 1e-9) return 180;
  const cosv = Math.max(-1, Math.min(1, ((baX * bcX) + (baY * bcY)) / (magBA * magBC)));
  return Math.acos(cosv) * (180 / Math.PI);
}

function normalizePoseLandmarksForReference(landmarks) {
  if (!Array.isArray(landmarks) || landmarks.length === 0) return null;
  const points = {};
  Object.entries(postureReferencePointToIndex).forEach(([name, idx]) => {
    const item = landmarks[idx];
    if (!item) return;
    points[name] = {
      x: Number(item.x || 0),
      y: Number(item.y || 0),
      visibility: Number(item.visibility ?? 0),
    };
  });

  const leftHip = points.left_hip;
  const rightHip = points.right_hip;
  const leftShoulder = points.left_shoulder;
  const rightShoulder = points.right_shoulder;
  if (!leftHip || !rightHip || !leftShoulder || !rightShoulder) return null;

  // Anchor: hip midpoint — consistent full-body anchor (requires full-body frame).
  const centerX = (leftHip.x + rightHip.x) / 2;
  const centerY = (leftHip.y + rightHip.y) / 2;
  const shoulderCenterX = (leftShoulder.x + rightShoulder.x) / 2;
  const shoulderCenterY = (leftShoulder.y + rightShoulder.y) / 2;
  const shoulderDist = Math.hypot(leftShoulder.x - rightShoulder.x, leftShoulder.y - rightShoulder.y);
  const torsoDist = Math.hypot(shoulderCenterX - centerX, shoulderCenterY - centerY);
  const scale = shoulderDist > 0.02 ? shoulderDist : torsoDist;
  if (!Number.isFinite(scale) || scale <= 0.02) return null;

  const normalized = {};
  let visibleCount = 0;
  Object.entries(points).forEach(([name, point]) => {
    normalized[name] = {
      x: (point.x - centerX) / scale,
      y: (point.y - centerY) / scale,
      visibility: Number(point.visibility ?? 0),
    };
    if (Number(point.visibility ?? 0) >= 0.45) visibleCount += 1;
  });

  return { points: normalized, visibleCount };
}

function scoreReferenceZone(reference, currentPoints, partNames, angleTriplets = []) {
  if (!reference || !currentPoints || !Array.isArray(partNames) || partNames.length === 0) {
    return null;
  }

  let posWeightSum = 0;
  let posErrorSum = 0;
  let visibleCount = 0;
  let visibilitySum = 0;

  partNames.forEach((name) => {
    const rp = reference[name];
    const cp = currentPoints[name];
    if (!rp || !cp) return;
    const weight = Math.min(Number(rp.visibility ?? 0), Number(cp.visibility ?? 0));
    if (weight < 0.2) return;
    const dist = Math.hypot(Number(rp.x || 0) - Number(cp.x || 0), Number(rp.y || 0) - Number(cp.y || 0));
    posErrorSum += weight * dist;
    posWeightSum += weight;
    visibleCount += 1;
    visibilitySum += weight;
  });

  let angWeightSum = 0;
  let angErrorSum = 0;
  angleTriplets.forEach(([aName, bName, cName]) => {
    const ra = reference[aName];
    const rb = reference[bName];
    const rc = reference[cName];
    const ca = currentPoints[aName];
    const cb = currentPoints[bName];
    const cc = currentPoints[cName];
    if (!ra || !rb || !rc || !ca || !cb || !cc) return;
    const weight = Math.min(
      Number(ra.visibility ?? 0),
      Number(rb.visibility ?? 0),
      Number(rc.visibility ?? 0),
      Number(ca.visibility ?? 0),
      Number(cb.visibility ?? 0),
      Number(cc.visibility ?? 0)
    );
    if (weight < 0.2) return;
    const refAngle = jointAngleDeg(ra, rb, rc);
    const curAngle = jointAngleDeg(ca, cb, cc);
    angErrorSum += weight * Math.abs(refAngle - curAngle);
    angWeightSum += weight;
  });

  if (posWeightSum <= 1e-9 && angWeightSum <= 1e-9) {
    return null;
  }

  const ePos = posWeightSum > 1e-9 ? (posErrorSum / posWeightSum) : 0;
  const eAng = angWeightSum > 1e-9 ? (angErrorSum / angWeightSum / 180) : 0;
  const meanVisibility = visibleCount > 0 ? (visibilitySum / visibleCount) : 0;
  const eVis = Math.max(0, 0.62 - meanVisibility);
  const combinedError = Math.max(0, Math.min(1, (0.68 * ePos) + (0.24 * eAng) + (0.08 * eVis)));

  return {
    score: 100 * (1 - combinedError),
    visibleCount,
    meanVisibility,
  };
}

function scoreLivePoseAgainstReference(referenceJson, landmarks) {
  const reference = referencePointsFromJson(referenceJson);
  const current = normalizePoseLandmarksForReference(landmarks);
  if (!reference || !current) return null;
  const coreZone = scoreReferenceZone(reference, current.points, dontMoveZonePartMap.core, dontMoveCoreAngleTriplets);
  const armZone = scoreReferenceZone(reference, current.points, dontMoveZonePartMap.arms, dontMoveArmAngleTriplets);
  const legZone = scoreReferenceZone(reference, current.points, dontMoveZonePartMap.legs, dontMoveLegAngleTriplets);
  const zones = { core: coreZone, arms: armZone, legs: legZone };

  let weightedScoreSum = 0;
  let weightedZoneSum = 0;
  Object.entries(dontMoveZoneWeights).forEach(([zoneName, zoneWeight]) => {
    const zone = zones[zoneName];
    if (!zone) return;
    weightedScoreSum += zone.score * zoneWeight;
    weightedZoneSum += zoneWeight;
  });
  if (weightedZoneSum <= 1e-9) return null;

  const overallScore = weightedScoreSum / weightedZoneSum;
  const zoneScores = Object.fromEntries(
    Object.entries(zones).map(([zoneName, zone]) => [zoneName, zone ? zone.score : null])
  );
  const visibleCount = Object.values(zones).reduce((sum, zone) => sum + Number(zone?.visibleCount || 0), 0);
  const visibleZoneCount = Object.values(zones).filter(Boolean).length;
  const meanVisibility = visibleZoneCount > 0
    ? (Object.values(zones).reduce((sum, zone) => sum + Number(zone?.meanVisibility || 0), 0) / visibleZoneCount)
    : 0;

  return {
    score: overallScore,
    visibleCount,
    meanVisibility,
    zones: zoneScores,
  };
}

function requiredReferencePoseParts(referenceJson) {
  const reference = referencePointsFromJson(referenceJson);
  if (!reference) return [];
  return Object.entries(reference)
    .filter(([, point]) => Number(point?.visibility ?? 0) >= 0.35)
    .map(([name]) => name);
}

function visibleReferencePoseParts(landmarks, names) {
  const normalized = normalizePoseLandmarksForReference(landmarks);
  if (!normalized) return [];
  return names.filter((name) => Number(normalized.points?.[name]?.visibility ?? 0) >= 0.45);
}

function dontMoveVisibilityMetrics(referenceJson, landmarks) {
  const requiredParts = requiredReferencePoseParts(referenceJson);
  const visibleParts = visibleReferencePoseParts(landmarks, requiredParts);
  const totalRatio = requiredParts.length > 0 ? (visibleParts.length / requiredParts.length) : 0;
  const requiredCoreParts = requiredParts.filter((name) => dontMoveCoreReferenceParts.includes(name));
  const visibleCoreParts = visibleParts.filter((name) => dontMoveCoreReferenceParts.includes(name));
  const requiredArmParts = requiredParts.filter((name) => dontMoveArmReferenceParts.includes(name));
  const visibleArmParts = visibleParts.filter((name) => dontMoveArmReferenceParts.includes(name));
  const coreRatio = requiredCoreParts.length > 0 ? (visibleCoreParts.length / requiredCoreParts.length) : totalRatio;
  const armRatio = requiredArmParts.length > 0 ? (visibleArmParts.length / requiredArmParts.length) : totalRatio;
  return {
    requiredParts,
    visibleParts,
    totalRatio,
    requiredCoreParts,
    visibleCoreParts,
    coreRatio,
    requiredArmParts,
    visibleArmParts,
    armRatio,
    requiredLegParts: requiredParts.filter((name) => dontMoveLegReferenceParts.includes(name)),
    visibleLegParts: visibleParts.filter((name) => dontMoveLegReferenceParts.includes(name)),
    legRatio: requiredParts.filter((name) => dontMoveLegReferenceParts.includes(name)).length > 0
      ? (visibleParts.filter((name) => dontMoveLegReferenceParts.includes(name)).length / requiredParts.filter((name) => dontMoveLegReferenceParts.includes(name)).length)
      : totalRatio,
  };
}

function evaluateDontMoveReadiness(score, visibilityMetrics, threshold) {
  if (!score || !visibilityMetrics) return null;
  const visibleCoreCount = visibilityMetrics.visibleCoreParts.length;
  const visibleArmCount = visibilityMetrics.visibleArmParts.length;
  const visibleLegCount = visibilityMetrics.visibleLegParts.length;
  const coreZoneScore = Number(score.zones?.core ?? 0);
  const armZoneScore = Number(score.zones?.arms ?? 0);
  const legZoneScore = Number(score.zones?.legs ?? 0);
  const coverageOk = Math.max(
    visibilityMetrics.totalRatio,
    visibilityMetrics.coreRatio,
    visibilityMetrics.armRatio,
    visibilityMetrics.legRatio
  ) >= 0.56;
  const coreOk = visibleCoreCount >= 4 && coreZoneScore >= (threshold - 6);
  const armsOk = visibleArmCount >= 4 && armZoneScore >= (threshold - 2);
  const legsOk = visibleLegCount >= 2 && legZoneScore >= (threshold - 10);
  const visibilityOk = score.visibleCount >= 7 && score.meanVisibility >= 0.40 && coverageOk;
  const ready = score.score >= threshold && visibilityOk && coreOk && armsOk && legsOk;
  let blocker = "";
  if (!coverageOk) blocker = `Abdeckung zu klein (${Math.round(100 * Math.max(visibilityMetrics.totalRatio, visibilityMetrics.coreRatio, visibilityMetrics.armRatio, visibilityMetrics.legRatio))}%)`;
  else if (visibleCoreCount < 4) blocker = `Kern nicht voll sichtbar (${visibleCoreCount}/${visibilityMetrics.requiredCoreParts.length})`;
  else if (visibleArmCount < 4) blocker = `Arme nicht voll sichtbar (${visibleArmCount}/${visibilityMetrics.requiredArmParts.length})`;
  else if (visibleLegCount < 2) blocker = `Beine nicht genug sichtbar (${visibleLegCount}/${visibilityMetrics.requiredLegParts.length})`;
  else if (coreZoneScore < (threshold - 6)) blocker = `Kern noch nicht korrekt (${coreZoneScore.toFixed(0)})`;
  else if (armZoneScore < (threshold - 2)) blocker = `Arme noch nicht korrekt (${armZoneScore.toFixed(0)})`;
  else if (legZoneScore < (threshold - 10)) blocker = `Beine noch nicht korrekt (${legZoneScore.toFixed(0)})`;
  else if (score.score < threshold) blocker = `Pose ${score.score.toFixed(1)}/100, Start ab ${threshold.toFixed(1)}`;
  return {
    ready,
    coverageOk,
    coreOk,
    armsOk,
    legsOk,
    visibilityOk,
    blocker,
    visibleCoreCount,
    visibleArmCount,
    visibleLegCount,
    coreZoneScore,
    armZoneScore,
    legZoneScore,
  };
}

function copyLandmarks(landmarks) {
  if (!Array.isArray(landmarks)) return null;
  return landmarks.map((item) => ({
    x: Number(item?.x || 0),
    y: Number(item?.y || 0),
    z: Number(item?.z || 0),
    visibility: Number(item?.visibility ?? 1),
  }));
}

function fallbackMarkerFromPoseLandmarks(poseLandmarks) {
  if (!Array.isArray(poseLandmarks) || poseLandmarks.length === 0) return null;
  const indices = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32];
  let sx = 0;
  let sy = 0;
  let count = 0;
  for (const idx of indices) {
    const item = poseLandmarks[idx];
    if (!item) continue;
    const v = Number(item.visibility ?? 1);
    if (v < 0.35) continue;
    sx += Number(item.x || 0);
    sy += Number(item.y || 0);
    count += 1;
  }
  if (count <= 0) return null;
  return { x: sx / count, y: sy / count };
}

function bodyRegionLabelForIndex(idx) {
  if (idx === 0) return "Kopf";
  if (idx === 11 || idx === 12) return "Schulter";
  if (idx === 13 || idx === 14) return "Oberarm";
  if (idx === 15 || idx === 16) return "Hand";
  if (idx === 23 || idx === 24) return "Huefte";
  if (idx === 25 || idx === 26) return "Oberschenkel";
  if (idx === 27 || idx === 28) return "Knie";
  if (idx === 29 || idx === 30) return "Sprunggelenk";
  if (idx === 31 || idx === 32) return "Fuss";
  return "Koerper";
}

function uploadCaptureDimensions() {
  const sourceW = Math.max(1, Number(playVideoEl?.videoWidth || 0), 640);
  const sourceH = Math.max(1, Number(playVideoEl?.videoHeight || 0), 360);
  const maxEdge = 1280;
  const scale = Math.min(1, maxEdge / Math.max(sourceW, sourceH));
  return {
    width: Math.max(640, Math.round(sourceW * scale)),
    height: Math.max(360, Math.round(sourceH * scale)),
  };
}

function tiptoeingFootState(poseLandmarks, side) {
  const heelIndex = side === "left" ? 29 : 30;
  const toeIndex = side === "left" ? 31 : 32;
  const ankleIndex = side === "left" ? 27 : 28;
  const heel = poseLandmarks?.[heelIndex];
  const toe = poseLandmarks?.[toeIndex];
  const ankle = poseLandmarks?.[ankleIndex];
  const heelVis = Number(heel?.visibility ?? 0);
  const toeVis = Number(toe?.visibility ?? 0);
  const ankleVis = Number(ankle?.visibility ?? 0);
  const visible = heelVis >= 0.45 && toeVis >= 0.45;
  if (!visible) {
    return {
      side,
      visible: false,
      lifted: false,
      liftAmount: 0,
      marker: null,
    };
  }

  const heelY = Number(heel?.y || 0);
  const toeY = Number(toe?.y || 0);
  const ankleY = Number(ankle?.y || heelY);
  const heelLift = toeY - heelY;
  const ankleToToe = toeY - ankleY;
  const minLift = Math.max(0.018, ankleVis >= 0.45 ? ankleToToe * 0.22 : 0.018);
  const lifted = heelLift >= minLift;

  return {
    side,
    visible: true,
    lifted,
    liftAmount: heelLift,
    marker: {
      x: Number(heel?.x || toe?.x || 0),
      y: Number(heel?.y || toe?.y || 0),
    },
    markerLabel: `${side === "left" ? "Linke" : "Rechte"} Ferse`,
    markerStrength: Math.max(0, minLift - heelLift),
  };
}

function strictStartVerdict(poseLandmarks) {
  if (isTiptoeingModule) {
    const tipVerdict = evaluateTiptoeingMask(poseLandmarks);
    const leftFoot = tiptoeingFootState(poseLandmarks, "left");
    const rightFoot = tiptoeingFootState(poseLandmarks, "right");
    const visibleFeet = [leftFoot, rightFoot].filter((item) => item.visible);
    const liftedFeet = visibleFeet.filter((item) => item.lifted);
    if (!tipVerdict || visibleFeet.length === 0) {
      return {
        ready: false,
        marker: null,
        markerLabel: "Fuesse nicht sichtbar",
        analysis: "Fuesse und Knoechel muessen vor dem Start sichtbar sein.",
        debug: "Start blockiert\nFuesse/Knoechel nicht stabil sichtbar",
      };
    }
    if (tipVerdict.violation || String(tipVerdict.reason || "").includes("ausserhalb")) {
      return {
        ready: false,
        marker: tipVerdict.marker || null,
        markerLabel: tipVerdict.markerLabel || "Fussposition korrigieren",
        analysis: "Fussbereiche muessen komplett in Gruen bleiben, Schwarz ist verboten.",
        debug: `Start blockiert\n${tipVerdict.markerLabel || "Fussposition korrigieren"}`,
      };
    }
    if (liftedFeet.length === 0) {
      return {
        ready: false,
        marker: leftFoot.marker || rightFoot.marker || null,
        markerLabel: "Fersen anheben",
        analysis: "Vor dem Start muessen die Fersen sichtbar auf den Zehenspitzen oben sein.",
        debug: "Start blockiert\nFersen muessen angehoben sein",
      };
    }
    return {
      ready: true,
      marker: null,
      markerLabel: "Tiptoeing bereit",
      analysis: "Pose erkannt. Halte Gruen und Zehenspitzen stabil.",
      debug: `Start bereit\nStabile Frames: ${strictStartStableFrames + 1}/${strictStartStableFrameTarget()}`,
    };
  }

  const score = scoreLivePoseAgainstReference(currentReferenceLandmarksJson, poseLandmarks);
  if (score) {
    const threshold = strictStartReadyThreshold();
    const visibilityMetrics = dontMoveVisibilityMetrics(currentReferenceLandmarksJson, poseLandmarks);
    const requiredParts = visibilityMetrics.requiredParts;
    const visibleParts = visibilityMetrics.visibleParts;
    const readiness = isDontMoveModule ? evaluateDontMoveReadiness(score, visibilityMetrics, threshold) : null;
    const coreZoneScore = Number(score.zones?.core ?? 0);
    const armZoneScore = Number(score.zones?.arms ?? 0);
    const legZoneScore = Number(score.zones?.legs ?? 0);
    const visibleCoreCount = visibilityMetrics.visibleCoreParts.length;
    const visibleArmCount = visibilityMetrics.visibleArmParts.length;
    const visibleLegCount = visibilityMetrics.visibleLegParts.length;
    const ready = isDontMoveModule ? Boolean(readiness?.ready) : (
      score.score >= threshold
      && score.visibleCount >= 10
      && score.meanVisibility >= 0.52
      && visibilityMetrics.totalRatio >= 0.78
    );
    return {
      ready,
      marker: movementLastMarker || fallbackMarkerFromPoseLandmarks(poseLandmarks),
      markerLabel: ready ? "Pose bereit" : "Pose ausrichten",
      analysis: ready
        ? `Sollpose erkannt (${score.score.toFixed(1)}/100).`
        : `Noch ausrichten: Pose ${score.score.toFixed(1)}/100, Start ab ${threshold.toFixed(1)}.`,
      debug: ready
        ? `Start bereit\nPose ${score.score.toFixed(1)}/100\nStabile Frames: ${strictStartStableFrames + 1}/${strictStartStableFrameTarget()}`
        : `Start blockiert\nPose ${score.score.toFixed(1)}/100, Start ab ${threshold.toFixed(1)}\n${isDontMoveModule ? `${readiness?.blocker || "Pose weiter ausrichten."} · Kern: ${coreZoneScore.toFixed(0)} (${visibleCoreCount}/${visibilityMetrics.requiredCoreParts.length}) · Arme: ${armZoneScore.toFixed(0)} (${visibleArmCount}/${visibilityMetrics.requiredArmParts.length}) · Beine: ${legZoneScore.toFixed(0)} (${visibleLegCount}/${visibilityMetrics.requiredLegParts.length})` : `Sichtbar: ${visibleParts.length}/${requiredParts.length}`}`,
    };
  }

  if (currentReferenceLandmarksJson) {
    return {
      ready: false,
      marker: fallbackMarkerFromPoseLandmarks(poseLandmarks),
      markerLabel: "Pose ausrichten",
      analysis: "Sollpose noch nicht sicher erkannt. Richte dich weiter am Referenzskelett aus.",
      debug: "Start blockiert\nReferenzpose noch nicht sicher erkannt",
    };
  }

  const visibleCount = Array.isArray(poseLandmarks)
    ? poseLandmarks.filter((item) => item && Number(item.visibility ?? 0) >= 0.45).length
    : 0;
  return {
    ready: false,
    marker: fallbackMarkerFromPoseLandmarks(poseLandmarks),
    markerLabel: visibleCount >= 10 ? "Referenzpose fehlt" : "Koerper ausrichten",
    analysis: "Fuer Don't move wird eine gespeicherte Referenzpose benoetigt. Bitte die Posture mit Referenzpose hinterlegen.",
    debug: `Start blockiert\nKeine Referenzpose fuer dieses Posture\nSichtbare Punkte: ${visibleCount}`,
  };
}

function evaluateTiptoeingMask(poseLandmarks) {
  if (!Array.isArray(poseLandmarks) || poseLandmarks.length === 0) return null;
  if (!tiptoeingMaskReady) return null;

  const profile = tiptoeingMaskProfile();
  const tracked = [29, 30, 31, 32];
  let blackHit = null;
  let outsideGreen = null;

  for (const idx of tracked) {
    const item = poseLandmarks[idx];
    if (!item) continue;
    const v = Number(item.visibility ?? 1);
    if (!Number.isFinite(v) || v < 0.45) continue;

    const nx = Number(item.x || 0);
    const ny = Number(item.y || 0);
    const zone = readTiptoeingMaskZone(nx, ny, profile);
    if (zone === "black") {
      blackHit = {
        marker: { x: nx, y: ny },
        markerIndex: idx,
        markerLabel: `Verbotene Zone (${bodyRegionLabelForIndex(idx)})`,
        markerStrength: 1.0,
        reason: "Verbotene Zone beruehrt",
      };
      break;
    }
    if (!outsideGreen && zone !== "green") {
      outsideGreen = {
        marker: { x: nx, y: ny },
        markerIndex: idx,
        markerLabel: `Gruene Zone verlassen (${bodyRegionLabelForIndex(idx)})`,
        markerStrength: 0.65,
        reason: "Leg/Fuss ausserhalb der gruenen Zone",
      };
    }
  }

  if (blackHit) {
    tiptoeingOutsideGreenFrames = 0;
    tiptoeingFlatFootFrames = 0;
    return {
      violation: true,
      immediate: true,
      ...blackHit,
    };
  }

  if (outsideGreen) {
    tiptoeingOutsideGreenFrames += 1;
    tiptoeingFlatFootFrames = 0;
    const violation = tiptoeingOutsideGreenFrames >= 3;
    return {
      violation,
      immediate: false,
      ...outsideGreen,
    };
  }

  tiptoeingOutsideGreenFrames = 0;
  const footStates = [
    tiptoeingFootState(poseLandmarks, "left"),
    tiptoeingFootState(poseLandmarks, "right"),
  ];
  const visibleFeet = footStates.filter((item) => item.visible);
  const liftedFeet = visibleFeet.filter((item) => item.lifted);
  if (visibleFeet.length > 0 && liftedFeet.length === 0) {
    tiptoeingFlatFootFrames += 1;
    const primary = [...visibleFeet].sort((left, right) => left.liftAmount - right.liftAmount)[0];
    return {
      violation: tiptoeingFlatFootFrames >= 4,
      immediate: false,
      marker: primary?.marker || null,
      markerIndex: primary?.side === "left" ? 29 : 30,
      markerLabel: `${primary?.markerLabel || "Ferse"} zu tief`,
      markerStrength: Math.max(0.3, Number(primary?.markerStrength || 0.3)),
      reason: "Nicht auf den Zehenspitzen",
    };
  }

  tiptoeingFlatFootFrames = 0;
  return {
    violation: false,
    immediate: false,
    marker: null,
    markerIndex: null,
    markerLabel: "Gruene Zone gehalten, Fersen oben",
    markerStrength: 0,
    reason: "Fuesse in der erlaubten Zone und auf den Zehenspitzen",
  };
}

function evaluatePoseMovement(worldLandmarks, poseLandmarks) {
  if (!Array.isArray(worldLandmarks) || worldLandmarks.length === 0) {
    if (isDontMoveModule) {
      movementPoseMissingFrames += 1;
      const fallbackMarker = fallbackMarkerFromPoseLandmarks(poseLandmarks) || movementLastMarker || null;
      return {
        violation: movementPoseMissingFrames >= movementPoseMissingFrameTarget(),
        marker: fallbackMarker,
        markerIndex: null,
        markerLabel: "Koerper nicht stabil erfasst",
        markerStrength: movementPoseMissingFrames,
        movementScore: movementPoseMissingFrames,
        poseScore: 999,
        poseOk: false,
        stillOk: false,
        reason: "Pose verloren oder Koerper ausserhalb des Bildausschnitts",
      };
    }
    return null;
  }
  movementPoseMissingFrames = 0;
  if (!movementTargetWorldLandmarks) {
    movementTargetWorldLandmarks = copyLandmarks(worldLandmarks);
  }
  if (!movementLastWorldLandmarks) {
    movementLastWorldLandmarks = copyLandmarks(worldLandmarks);
    return null;
  }

  const profile = movementProfile();
  let maxMovement = 0;
  let poseDeviation = 0;
  let poseVisiblePoints = 0;
  let marker = null;
  let markerIndex = null;

  for (const idx of movementWatchIndices) {
    const cur = worldLandmarks[idx];
    const prev = movementLastWorldLandmarks[idx];
    if (!cur || !prev) continue;
    if (Number(cur.visibility || 0) < 0.45 || Number(prev.visibility || 0) < 0.45) continue;

    const dx = Number(cur.x || 0) - Number(prev.x || 0);
    const dy = Number(cur.y || 0) - Number(prev.y || 0);
    const dz = Number(cur.z || 0) - Number(prev.z || 0);
    const weight = 1.0;
    const delta = Math.hypot(dx, dy, dz) * weight;
    if (delta > maxMovement) {
      maxMovement = delta;
      markerIndex = idx;
      const markerSource = Array.isArray(poseLandmarks) ? poseLandmarks[idx] : null;
      if (markerSource) {
        marker = { x: Number(markerSource.x || 0), y: Number(markerSource.y || 0) };
      }
    }
  }

  if (!marker) {
    marker = movementLastMarker || fallbackMarkerFromPoseLandmarks(poseLandmarks);
  }

  for (const idx of movementPoseCompareIndices) {
    const cur = worldLandmarks[idx];
    const target = movementTargetWorldLandmarks[idx];
    if (!cur || !target) continue;
    if (Number(cur.visibility || 0) < 0.55 || Number(target.visibility || 0) < 0.55) continue;
    const dx = Number(cur.x || 0) - Number(target.x || 0);
    const dy = Number(cur.y || 0) - Number(target.y || 0);
    const dz = Number(cur.z || 0) - Number(target.z || 0);
    poseDeviation += Math.hypot(dx, dy, dz);
    poseVisiblePoints += 1;
  }

  const avgPoseDeviation = poseVisiblePoints > 0 ? (poseDeviation / poseVisiblePoints) : 0;
  let poseOk = poseVisiblePoints < (isDontMoveModule ? 4 : 1)
    ? true
    : avgPoseDeviation < Number(profile.poseDeviation);
  const stillOk = maxMovement < Number(profile.stillness);

  if (isDontMoveModule && currentReferenceLandmarksJson) {
    const score = scoreLivePoseAgainstReference(currentReferenceLandmarksJson, poseLandmarks);
    const threshold = strictHoldPoseThreshold();
    const visibilityMetrics = dontMoveVisibilityMetrics(currentReferenceLandmarksJson, poseLandmarks);
    const visibilityRatio = Math.max(
      visibilityMetrics.totalRatio,
      visibilityMetrics.coreRatio,
      visibilityMetrics.armRatio,
      visibilityMetrics.legRatio
    );
    const coreZoneScore = Number(score?.zones?.core ?? 0);
    const armZoneScore = Number(score?.zones?.arms ?? 0);
    const legZoneScore = Number(score?.zones?.legs ?? 0);
    if (
      !score
      || score.score < threshold
      || score.visibleCount < 7
      || score.meanVisibility < 0.38
      || visibilityRatio < 0.5
      || visibilityMetrics.visibleCoreParts.length < 4
      || visibilityMetrics.visibleArmParts.length < 4
      || visibilityMetrics.visibleLegParts.length < 2
      || coreZoneScore < (threshold - 4)
      || armZoneScore < (threshold - 2)
      || legZoneScore < (threshold - 12)
    ) {
      poseOk = false;
      if (!marker) {
        marker = fallbackMarkerFromPoseLandmarks(poseLandmarks);
      }
      markerIndex = null;
    }
  }

  if (!poseOk || !stillOk) {
    movementStrikeCount += 1;
  } else {
    movementStrikeCount = Math.max(0, movementStrikeCount - 1);
  }

  movementLastWorldLandmarks = copyLandmarks(worldLandmarks);
  const now = Date.now();
  const violation = movementStrikeCount >= movementViolationStrikeTarget() && now >= movementCooldownUntil;
  if (violation) {
    movementStrikeCount = 0;
    movementCooldownUntil = now + (isDontMoveModule ? 4200 : 2200);
  }
  return {
    violation,
    marker,
    markerIndex,
    markerLabel: bodyRegionLabelForIndex(markerIndex ?? -1),
    markerStrength: maxMovement,
    movementScore: maxMovement,
    poseScore: avgPoseDeviation,
    poseOk,
    stillOk,
  };
}

async function initMovementPose() {
  if (!isSinglePoseModule && moduleKey !== "posture_training") return;
  if (movementPoseReady) return;
  await ensureVisionLoaded();

  const { FilesetResolver, PoseLandmarker } = visionModule;

  if (!movementFileset) {
    let lastError = null;
    for (const wasmRoot of TASKS_VISION_WASM_ROOTS) {
      try {
        movementFileset = await FilesetResolver.forVisionTasks(wasmRoot);
        break;
      } catch (err) {
        lastError = err;
      }
    }
    if (!movementFileset) {
      throw new Error(
        `MediaPipe WASM konnte nicht geladen werden (${lastError ? lastError.message : "unbekannt"})`
      );
    }
  }

  movementPose = await PoseLandmarker.createFromOptions(movementFileset, {
    baseOptions: {
      modelAssetPath:
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
    },
    runningMode: "VIDEO",
    numPoses: 1,
    minPoseDetectionConfidence: 0.6,
    minPosePresenceConfidence: 0.6,
    minTrackingConfidence: 0.6,
  });
  movementPoseReady = true;
}

function describeMovementReason(verdict) {
  if (isTiptoeingModule) {
    const markerLabel = String(verdict?.markerLabel || "Bein/Fuss");
    if (String(verdict?.reason || "").includes("Verbotene Zone")) {
      return `Tiptoeing-Maskenverstoss: Verbotene Zone beruehrt (${markerLabel}).`;
    }
    if (String(verdict?.reason || "").includes("Zehenspitzen")) {
      return `Tiptoeing-Verstoss: Ferse abgesenkt, nicht mehr auf den Zehenspitzen (${markerLabel}).`;
    }
    return `Tiptoeing-Maskenverstoss: Gruene Zone verlassen (${markerLabel}).`;
  }
  if (String(verdict?.reason || "").trim()) {
    const region = String(verdict?.markerLabel || "Koerper");
    return `${String(verdict.reason).trim()} (${region})`;
  }
  if (isDontMoveModule && verdict?.poseOk === false && currentReferenceLandmarksJson) {
    const posePart = `pose=${Number(verdict?.poseScore || 0).toFixed(4)}/${Number(movementProfile().poseDeviation).toFixed(4)}`;
    return `Sollpose nicht korrekt gehalten (${posePart})`;
  }
  const profile = movementProfile();
  const movePart = `movement=${Number(verdict?.movementScore || 0).toFixed(4)}/${Number(profile.stillness).toFixed(4)}`;
  const posePart = `pose=${Number(verdict?.poseScore || 0).toFixed(4)}/${Number(profile.poseDeviation).toFixed(4)}`;
  const region = String(verdict?.markerLabel || "Koerper");
  return `Lokale Bewegung erkannt (${region}; ${movePart}, ${posePart})`;
}

async function captureViolationFrameBlob(marker = null, markerMeta = null) {
  if (!cameraStream) return null;
  const canvas = document.createElement("canvas");
  const dims = uploadCaptureDimensions();
  const w = dims.width;
  const h = dims.height;
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  ctx.drawImage(playVideoEl, 0, 0, w, h);

  if (isTiptoeingModule && tiptoeingMaskReady && tiptoeingMaskImage) {
    ctx.save();
    ctx.globalAlpha = 0.34;
    ctx.drawImage(tiptoeingMaskImage, 0, 0, w, h);
    ctx.restore();
  }

  const border = Math.max(8, Math.floor(Math.min(w, h) * 0.018));
  ctx.strokeStyle = "rgba(255, 48, 48, 0.98)";
  ctx.lineWidth = border;
  ctx.strokeRect(border / 2, border / 2, w - border, h - border);

  if (marker && Number.isFinite(marker.x) && Number.isFinite(marker.y)) {
    const mx = Math.max(0, Math.min(w, marker.x * w));
    const my = Math.max(0, Math.min(h, marker.y * h));
    const strength = Math.max(0, Number(markerMeta?.strength || 0));
    const strengthNorm = Math.min(2.5, strength / Math.max(0.0001, Number(movementProfile().stillness || 0.004)));
    const radius = Math.max(14, Math.floor(Math.min(w, h) * (0.03 + (0.008 * strengthNorm))));

    ctx.fillStyle = "rgba(255, 24, 24, 0.22)";
    ctx.beginPath();
    ctx.arc(mx, my, radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.beginPath();
    ctx.arc(mx, my, radius, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(255, 36, 36, 1)";
    ctx.lineWidth = Math.max(5, Math.floor(Math.min(w, h) * 0.01));
    ctx.stroke();

    const cross = Math.max(20, Math.floor(radius * 1.45));
    ctx.beginPath();
    ctx.moveTo(mx - cross, my);
    ctx.lineTo(mx + cross, my);
    ctx.moveTo(mx, my - cross);
    ctx.lineTo(mx, my + cross);
    ctx.stroke();

    const label = String(markerMeta?.label || "Bewegung");
    const fontSize = Math.max(24, Math.floor(Math.min(w, h) * 0.044));
    ctx.font = `bold ${fontSize}px sans-serif`;
    ctx.textBaseline = "middle";
    const textWidth = ctx.measureText(label).width;
    const padX = Math.max(12, Math.floor(fontSize * 0.45));
    const padY = Math.max(8, Math.floor(fontSize * 0.28));
    const tx = Math.max(8, Math.min(w - textWidth - (padX * 2) - 8, mx + radius + 10));
    const ty = Math.max(fontSize, Math.min(h - fontSize, my - radius - 18));
    ctx.fillStyle = "rgba(0, 0, 0, 0.62)";
    ctx.fillRect(tx, ty - Math.round(fontSize * 0.52) - padY, textWidth + (padX * 2), fontSize + (padY * 2));
    ctx.fillStyle = "rgba(255, 90, 90, 0.98)";
    ctx.fillText(label, tx + padX, ty);
  }

  const annotated = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
  if (annotated) return annotated;
  return captureFrameBlob();
}

async function submitMovementViolation(token, marker, verdict) {
  if (token !== sequenceToken) return;
  if (!activeRun || !activeRun.current_step) return;
  if (movementEventInFlight) {
    movementPendingViolation = {
      token,
      marker,
      verdict,
      attempts: Number(verdict?.attempts || 0),
    };
    return;
  }
  movementEventInFlight = true;
  movementPendingViolation = null;

  try {
    const effectiveMarker = (marker && Number.isFinite(marker.x) && Number.isFinite(marker.y))
      ? marker
      : bestEffortMovementMarker();

    const markerLabel = String(verdict?.markerLabel || "Bewegung");
    const markerStrength = Number(verdict?.markerStrength || verdict?.movementScore || 0);

    // Use a direct camera capture for uploads. The server already annotates the
    // stored image with marker metadata, so relying on a client-side canvas here
    // only adds a browser-specific failure point.
    let blob = await captureFrameBlob();
    if (!blob) {
      blob = await captureViolationFrameBlob(effectiveMarker, {
        label: markerLabel,
        strength: markerStrength,
      });
    }
    if (!blob) throw new Error("Kontrollbild fuer Bewegung konnte nicht erzeugt werden");

    revokeMovementLocalPreview();
    movementLocalPreviewUrl = URL.createObjectURL(blob);
    verifyThumbEl.src = movementLocalPreviewUrl;
    verifyThumbEl.style.display = "";
    verifyThumbEl.classList.remove("ok");
    verifyThumbEl.classList.add("fail");
    appendPendingLocalCaptureThumbnail(movementLocalPreviewUrl);
    setStatus("Verstoss erkannt. Kontrollbild wird gespeichert …", true);
    setUploadDebug(`Upload startet: run=${runId}, step=${activeRun.current_step.id}, size=${blob.size || 0} bytes`, true);

    const form = new FormData();
    form.append("file", blob, "movement_violation.jpg");
    if (effectiveMarker && Number.isFinite(effectiveMarker.x) && Number.isFinite(effectiveMarker.y)) {
      form.append("marker_x", String(effectiveMarker.x));
      form.append("marker_y", String(effectiveMarker.y));
    }
    form.append("marker_label", markerLabel);
    form.append("marker_strength", String(markerStrength));
    form.append("reason", describeMovementReason(verdict));

    const result = await api(`/api/games/runs/${runId}/steps/${activeRun.current_step.id}/movement-event`, {
      method: "POST",
      body: form,
    });

    analysisEl.textContent = `Bewegung erkannt: ${result.step.analysis || "Verstoss registriert."}`;
    setStatus("Verstoss protokolliert und Kontrollbild gespeichert.", true);
    setUploadDebug(`Upload erfolgreich: miss_count=${result.run?.miss_count ?? "?"}, image=${result.step?.capture_url || "-"}`, false);
    revokeMovementLocalPreview();
    clearPendingLocalCaptureGallery();
    renderRun(result.run);
    // Ensure violation thumbnail is always visible after gallery rebuild
    updateVerificationPreview(result.step, true);
    if (captureGalleryEl && captureGalleryEl.children.length === 0 && result.step?.capture_url) {
      appendCaptureThumbnail(result.step);
    }
  } catch (err) {
    setStatus(`Lokale Bewegungserfassung fehlgeschlagen: ${err.message}`, true);
    setUploadDebug(`Upload fehlgeschlagen: ${err.message}`, true);
    const attempts = Number(verdict?.attempts || 0);
    if (attempts < 2 && token === sequenceToken && activeRun && activeRun.current_step) {
      movementPendingViolation = {
        token,
        marker,
        verdict: {
        ...verdict,
        attempts: attempts + 1,
        },
      };
    }
  } finally {
    movementEventInFlight = false;
    if (
      movementPendingViolation
      && movementPendingViolation.token === sequenceToken
      && activeRun
      && activeRun.current_step
    ) {
      const pending = movementPendingViolation;
      movementPendingViolation = null;
      window.setTimeout(() => {
        submitMovementViolation(pending.token, pending.marker, pending.verdict).catch(() => {});
      }, 0);
    }
  }
}

async function waitForMovementViolationsToSettle(token, timeoutMs = 2600) {
  const startedAt = Date.now();
  while (token === sequenceToken) {
    const hasQueuedViolation = Boolean(movementPendingViolation);
    if (!movementEventInFlight && !hasQueuedViolation) {
      return true;
    }
    if ((Date.now() - startedAt) >= timeoutMs) {
      return false;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 80));
  }
  return false;
}

async function finalizeStrictCompletionAfterSettledViolations(token) {
  if (token !== sequenceToken) return;

  const flushed = await waitForMovementViolationsToSettle(token, 5000);
  if (token !== sequenceToken) return;

  if (!flushed && (movementEventInFlight || movementPendingViolation)) {
    setStatus("Verstoss-Upload braucht laenger. Abschluss wartet auf Speicherung.", true);
    window.setTimeout(() => {
      finalizeStrictCompletionAfterSettledViolations(token).catch(() => {});
    }, 300);
    return;
  }

  stopMovementMonitor();
  completeStrictStepWithoutCapture(token).catch(() => {});
}

function bestEffortMovementMarker() {
  if (movementLastMarker && Number.isFinite(movementLastMarker.x) && Number.isFinite(movementLastMarker.y)) {
    return movementLastMarker;
  }

  if (Array.isArray(movementLatestPoseLandmarks) && movementLatestPoseLandmarks.length > 0) {
    const fallback = fallbackMarkerFromPoseLandmarks(movementLatestPoseLandmarks);
    if (fallback && Number.isFinite(fallback.x) && Number.isFinite(fallback.y)) {
      return fallback;
    }
  }

  return null;
}

async function startMovementMonitor(token) {
  if (!isSinglePoseModule) return;
  if (dontMoveMonitorHandle) {
    clearInterval(dontMoveMonitorHandle);
    dontMoveMonitorHandle = null;
  }

  try {
    await initMovementPose();
    if (isTiptoeingModule) {
      await ensureTiptoeingMaskLoaded();
    }
  } catch (err) {
    setStatus(`${err.message} - Echtzeit-Bewegungserkennung nicht verfuegbar.`, true);
    analysisEl.textContent = "Echtzeit-Bewegungserkennung konnte nicht gestartet werden.";
    return;
  }

  movementLastWorldLandmarks = null;
  movementLatestPoseLandmarks = null;
  movementLatestWorldLandmarks = null;
  movementTargetWorldLandmarks = null;
  movementStrikeCount = 0;
  movementCooldownUntil = 0;
  movementRedFlashUntil = 0;
  movementLastMarker = null;
  movementPendingViolation = null;
  movementPoseMissingFrames = 0;
  movementOverlayMode = "active";
  strictStartStableFrames = 0;
  strictStartDebugText = "";
  tiptoeingOutsideGreenFrames = 0;
  tiptoeingFlatFootFrames = 0;
  movementMonitorActive = true;
  syncMotionOverlaySize();
  drawMotionOverlay();

  dontMoveMonitorHandle = setInterval(async () => {
    if (token !== sequenceToken) {
      clearInterval(dontMoveMonitorHandle);
      dontMoveMonitorHandle = null;
      return;
    }
    if (!movementPose || movementPoseBusy || !cameraStream) return;

    movementPoseBusy = true;
    try {
      const result = movementPose.detectForVideo(playVideoEl, performance.now());
      movementLatestPoseLandmarks = copyLandmarks(result?.landmarks?.[0] || []);
      movementLatestWorldLandmarks = copyLandmarks(result?.worldLandmarks?.[0] || []);

      const verdict = isTiptoeingModule
        ? evaluateTiptoeingMask(movementLatestPoseLandmarks)
        : evaluatePoseMovement(movementLatestWorldLandmarks, movementLatestPoseLandmarks);
      if (!verdict) {
        drawMotionOverlay();
        return;
      }

      if (verdict.marker && Number.isFinite(verdict.marker.x) && Number.isFinite(verdict.marker.y)) {
        movementLastMarker = verdict.marker;
      }

      if (verdict.violation) {
        movementRedFlashUntil = Date.now() + 900;
        drawMotionOverlay(verdict.marker, true);
        submitMovementViolation(token, verdict.marker, verdict).catch(() => {});
      } else {
        drawMotionOverlay();
      }
    } finally {
      movementPoseBusy = false;
    }
  }, 120);
}

async function startSkeletonMonitor(token) {
  if (moduleKey !== "posture_training") return;
  if (skeletonMonitorHandle) {
    clearInterval(skeletonMonitorHandle);
    skeletonMonitorHandle = null;
  }

  try {
    await initMovementPose();
  } catch (err) {
    setStatus(`${err.message} - Skelett-Overlay nicht verfuegbar.`, true);
    return;
  }

  postureOverlayStatus = "idle";
  syncMotionOverlaySize();
  drawSkeletonOnCanvas(movementLatestPoseLandmarks);

  skeletonMonitorHandle = setInterval(() => {
    if (token !== sequenceToken) {
      clearInterval(skeletonMonitorHandle);
      skeletonMonitorHandle = null;
      return;
    }
    if (!movementPose || movementPoseBusy || !cameraStream) {
      drawSkeletonOnCanvas(movementLatestPoseLandmarks);
      return;
    }

    movementPoseBusy = true;
    try {
      const result = movementPose.detectForVideo(playVideoEl, performance.now());
      movementLatestPoseLandmarks = copyLandmarks(result?.landmarks?.[0] || []);
      drawSkeletonOnCanvas(movementLatestPoseLandmarks);
    } finally {
      movementPoseBusy = false;
    }
  }, 120);
}

function stopMovementMonitor() {
  if (dontMoveMonitorHandle) {
    clearInterval(dontMoveMonitorHandle);
    dontMoveMonitorHandle = null;
  }
  movementLastWorldLandmarks = null;
  movementLatestPoseLandmarks = null;
  movementLatestWorldLandmarks = null;
  movementTargetWorldLandmarks = null;
  movementStrikeCount = 0;
  movementCooldownUntil = 0;
  movementRedFlashUntil = 0;
  movementLastMarker = null;
  movementPoseMissingFrames = 0;
  revokeMovementLocalPreview();
  clearPendingLocalCaptureGallery();
  movementOverlayMode = "idle";
  strictStartStableFrames = 0;
  strictStartDebugText = "";
  tiptoeingOutsideGreenFrames = 0;
  tiptoeingFlatFootFrames = 0;
  movementMonitorActive = false;
  postureInconclusiveCount = 0;
  if (motionOverlayEl) {
    const ctx = motionOverlayEl.getContext("2d");
    if (ctx) {
      ctx.clearRect(0, 0, motionOverlayEl.width, motionOverlayEl.height);
    }
  }
}

async function startStrictStartAlignment(token, readyCountdownSeconds, onReady) {
  if (!isSinglePoseModule) {
    onReady();
    return;
  }
  if (dontMoveMonitorHandle) {
    clearInterval(dontMoveMonitorHandle);
    dontMoveMonitorHandle = null;
  }

  try {
    await initMovementPose();
    if (isTiptoeingModule) {
      await ensureTiptoeingMaskLoaded();
    }
  } catch (err) {
    setStatus(`${err.message} - Startausrichtung nicht verfuegbar.`, true);
    analysisEl.textContent = "Startausrichtung konnte nicht aktiviert werden.";
    return;
  }

  movementLatestPoseLandmarks = null;
  movementLatestWorldLandmarks = null;
  movementLastMarker = null;
  movementOverlayMode = "positioning";
  movementMonitorActive = true;
  strictStartStableFrames = 0;
  strictStartDebugText = "Start blockiert\nWarte auf stabile Sollpose";
  let countdownLeft = Math.max(0, Number(readyCountdownSeconds || 0));
  let countdownStarted = countdownLeft <= 0;
  let lastCountdownTick = Date.now();
  updatePhase(countdownStarted ? "START" : "POSITIONIEREN", countdownStarted ? "0" : "--");
  analysisEl.textContent = "Nimm die Sollpose ein. Der Start erfolgt erst bei stabil erkannter Haltung.";
  syncMotionOverlaySize();
  drawMotionOverlay();

  dontMoveMonitorHandle = setInterval(() => {
    if (token !== sequenceToken) {
      clearInterval(dontMoveMonitorHandle);
      dontMoveMonitorHandle = null;
      movementMonitorActive = false;
      movementOverlayMode = "idle";
      return;
    }
    if (!movementPose || movementPoseBusy || !cameraStream) return;

    movementPoseBusy = true;
    try {
      const result = movementPose.detectForVideo(playVideoEl, performance.now());
      movementLatestPoseLandmarks = copyLandmarks(result?.landmarks?.[0] || []);
      movementLatestWorldLandmarks = copyLandmarks(result?.worldLandmarks?.[0] || []);
      const verdict = strictStartVerdict(movementLatestPoseLandmarks);

      if (verdict?.marker && Number.isFinite(verdict.marker.x) && Number.isFinite(verdict.marker.y)) {
        movementLastMarker = verdict.marker;
      }

      if (!verdict?.ready) {
        strictStartStableFrames = 0;
        countdownStarted = false;
        countdownLeft = Math.max(0, Number(readyCountdownSeconds || 0));
        movementOverlayMode = "positioning";
        strictStartDebugText = String(verdict?.debug || "Start blockiert\nPose ausrichten");
        updatePhase("POSITIONIEREN", "--");
        analysisEl.textContent = verdict?.analysis || "Richte die Pose fuer den Start aus.";
        drawMotionOverlay(verdict?.marker || null);
        return;
      }

      strictStartStableFrames += 1;
      const stableFrameTarget = strictStartStableFrameTarget();
      // Keep "positioning" (blue) during stabilisation — only startMovementMonitor sets "active" (green)
      strictStartDebugText = String(verdict?.debug || `Start bereit\nStabile Frames: ${strictStartStableFrames}/${stableFrameTarget}`);
      drawMotionOverlay(verdict.marker || null);

      if (strictStartStableFrames < stableFrameTarget) {
        updatePhase("POSITIONIEREN", "--");
        analysisEl.textContent = `${verdict.analysis || "Pose erkannt."} Stabilisiere die Haltung kurz.`;
        return;
      }

      if (!countdownStarted) {
        countdownStarted = true;
        lastCountdownTick = Date.now();
        strictStartDebugText = `Start bereit\nCountdown: ${countdownLeft}`;
        updatePhase("START", countdownLeft > 0 ? String(countdownLeft) : "0");
        analysisEl.textContent = "Pose erkannt. Start laeuft.";
        return;
      }

      if (countdownLeft > 0 && (Date.now() - lastCountdownTick) >= 1000) {
        countdownLeft = Math.max(0, countdownLeft - 1);
        lastCountdownTick = Date.now();
        strictStartDebugText = `Start bereit\nCountdown: ${countdownLeft}`;
        updatePhase("START", String(countdownLeft));
        if (countdownLeft > 0 && countdownLeft <= 5) {
          beep();
        }
      }

      if (countdownLeft <= 0) {
        clearInterval(dontMoveMonitorHandle);
        dontMoveMonitorHandle = null;
        movementMonitorActive = false;
        movementOverlayMode = "idle";
        strictStartStableFrames = 0;
        strictStartDebugText = "";
        onReady();
      }
    } finally {
      movementPoseBusy = false;
    }
  }, 120);
}

function stopSkeletonMonitor() {
  if (skeletonMonitorHandle) {
    clearInterval(skeletonMonitorHandle);
    skeletonMonitorHandle = null;
  }
  postureOverlayStatus = "idle";
  postureInconclusiveCount = 0;
  if (moduleKey === "posture_training") {
    movementLatestPoseLandmarks = null;
    if (motionOverlayEl) {
      const ctx = motionOverlayEl.getContext("2d");
      if (ctx) {
        ctx.clearRect(0, 0, motionOverlayEl.width, motionOverlayEl.height);
      }
    }
  }
}

function stopPostureScoreMonitor() {
  if (postureScoreMonitorHandle) {
    clearInterval(postureScoreMonitorHandle);
    postureScoreMonitorHandle = null;
  }
}

async function startPostureScoreMonitor(token) {
  if (moduleKey !== "posture_training") return;
  stopPostureScoreMonitor();

  const runMonitorCheck = async () => {
    if (token !== sequenceToken) return;
    if (!cameraStream || !activeRun || activeRun.status !== "active" || !activeRun.current_step) return;
    await verifyCurrentStepWithMode(token, { monitorOnly: true });
  };

  window.setTimeout(() => {
    runMonitorCheck().catch(() => {});
  }, 900);

  postureScoreMonitorHandle = setInterval(() => {
    runMonitorCheck().catch(() => {});
  }, 5000);
}

function updatePhase(label, value) {
  phaseLabelEl.textContent = label;
  phaseCountdownEl.textContent = value;
}

function updateVerificationPreview(stepResult, sampleOnly) {
  if (!stepResult) return;

  const imageUrl = stepResult.capture_url || "";
  if (imageUrl) {
    verifyThumbEl.src = imageUrl;
    verifyThumbEl.style.display = "";
  }

  const status = String(stepResult.verification_status || "").toLowerCase();
  verifyThumbEl.classList.remove("ok", "fail");

  if (status === "confirmed") {
    verifyThumbEl.classList.add("ok");
    return;
  }

  if (status === "suspicious") {
    verifyThumbEl.classList.add("fail");
    return;
  }
}

function poseSimilaritySummary(stepResult) {
  if (!stepResult || !stepResult.pose_similarity) return "";
  const status = String(stepResult.pose_similarity_status || "").trim();
  const score = Number(stepResult.pose_similarity.score);
  const threshold = Number(stepResult.pose_similarity.threshold);
  if (!Number.isFinite(score) || !Number.isFinite(threshold)) {
    return status ? ` Pose-Check: ${status}.` : "";
  }
  const statusLabel = status || (score >= threshold ? "confirmed" : "suspicious");
  return ` Pose-Check: ${statusLabel} (${score.toFixed(1)}/100, min ${threshold.toFixed(1)}).`;
}

function escHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderFinalReport(summary) {
  const checks = Array.isArray(summary?.checks) ? summary.checks : [];
  const aiAssessment = escHtml(summary?.ai_assessment || "");

  // Summary header with stats
  const total = Number(summary?.total_steps || 0);
  const scheduled = Number(summary?.scheduled_steps || total);
  const unplayed = Number(summary?.unplayed_steps || Math.max(0, scheduled - total));
  const passed = Number(summary?.passed_steps || 0);
  const failed = Number(summary?.failed_steps || 0);
  const misses = Number(summary?.miss_count || 0);
  const retryExt = Number(summary?.retry_extension_seconds || 0);
  const penaltyApplied = Boolean(summary?.session_penalty_applied);

  let headerHtml = `<div class="final-report-header">
    <h4>Spiel-Bericht</h4>
    <div class="final-report-stats">
      <span>Gespielt: <strong class="${passed === total && failed === 0 ? 'stat-ok' : 'stat-fail'}">${passed}/${total}</strong></span>
      <span>Fehler: <strong class="${failed > 0 ? 'stat-fail' : 'stat-ok'}">${failed}</strong></span>
      <span>Verfehlungen: <strong class="${misses > 0 ? 'stat-fail' : 'stat-ok'}">${misses}</strong></span>`;
  if (unplayed > 0) headerHtml += `<span>Nicht gespielt: <strong>${unplayed}/${scheduled}</strong></span>`;
  if (retryExt > 0) headerHtml += `<span>Strafzeit: <strong class="stat-fail">+${retryExt}s</strong></span>`;
  if (penaltyApplied) headerHtml += `<span><strong class="stat-fail">Session-Penalty aktiv</strong></span>`;
  headerHtml += `</div>`;

  if (aiAssessment) {
    headerHtml += `<div class="final-ai-assessment">${aiAssessment}</div>`;
  }
  headerHtml += `<a href="/games" class="final-report-link">&#8592; Zur Spieluebersicht</a></div>`;

  if (checks.length === 0) {
    finalReportEl.innerHTML = headerHtml;
    return;
  }

  const realChecks = checks.filter(c => c.capture_url);
  const checksWithoutImage = checks.filter(c => !c.capture_url);
  const checksHtml = realChecks
    .map((entry, idx) => {
      const status = String(entry.verification_status || "").toLowerCase();
      const statusLabel = status === "confirmed" ? "Bestanden" : "Nicht bestanden";
      const statusClass = status === "confirmed" ? "ok" : "fail";
      const modeLabel = entry.monitor_only ? "Monitoring" : entry.sample_only ? "Stichprobe" : "Endpruefung";
      const imgClass = status === "confirmed" ? "ok" : "fail";
      const imgUrl = escHtml(entry.capture_url || "");
      const analysis = escHtml(entry.analysis || "-");
      const posture = escHtml(entry.posture_name || "-");
      const poseScore = entry.pose_score != null ? ` (Pose: ${Number(entry.pose_score).toFixed(1)}/100)` : "";
      return `
        <article class="final-check">
          <img class="${imgClass}" src="${imgUrl}" alt="Kontrollbild ${idx + 1}"
               data-gm-report-image="${imgUrl}" title="Bild vergroessern" />
          <div class="meta">
            <div><strong>${idx + 1}. ${modeLabel}</strong> · Pose: ${posture}${escHtml(poseScore)}</div>
            <div><strong class="${statusClass}">${statusLabel}</strong></div>
            <div>Begruendung: ${analysis}</div>
          </div>
        </article>
      `;
    })
    .join("");

  const checksLabel = realChecks.length > 0
    ? `<p class="final-checks-label">${realChecks.length} Kontrollbild${realChecks.length === 1 ? "" : "er"}</p>`
    : "";

  const noImageHtml = checksWithoutImage.length > 0
    ? `<p class="final-checks-label">${checksWithoutImage.length} Check${checksWithoutImage.length === 1 ? "" : "s"} ohne Bild</p>
       <div class="final-checks-plain">${checksWithoutImage.map((entry, idx) => {
          const status = String(entry.verification_status || "").toLowerCase();
          const statusLabel = status === "confirmed" ? "Bestanden" : "Nicht bestanden";
          const statusClass = status === "confirmed" ? "ok" : "fail";
          const modeLabel = entry.monitor_only ? "Monitoring" : entry.sample_only ? "Stichprobe" : "Endpruefung";
          const posture = escHtml(entry.posture_name || "-");
          const analysis = escHtml(entry.analysis || "-");
          const poseScore = entry.pose_score != null ? ` · Pose ${Number(entry.pose_score).toFixed(1)}/100` : "";
          return `<article class="final-check plain">
            <div class="meta">
              <div><strong>${idx + 1}. ${modeLabel}</strong> · Pose: ${posture}${escHtml(poseScore)}</div>
              <div><strong class="${statusClass}">${statusLabel}</strong></div>
              <div>Begruendung: ${analysis}</div>
            </div>
          </article>`;
        }).join("")}</div>`
    : "";

  finalReportEl.innerHTML = headerHtml + checksLabel + checksHtml + noImageHtml;
}

function appendCaptureThumbnail(stepResult) {
  if (!stepResult) return;
  const imageUrl = stepResult.capture_url || "";
  if (!imageUrl) return;

  const status = String(stepResult.verification_status || "").toLowerCase();
  const img = document.createElement("img");
  img.src = imageUrl;
  img.alt = "Pruefungsbild";
  img.className = "capture-thumb";
  if (status === "confirmed") {
    img.classList.add("ok");
  } else if (status === "suspicious") {
    img.classList.add("fail");
  }
  captureGalleryEl.prepend(img);

  // Keep the gallery compact and responsive.
  while (captureGalleryEl.children.length > 60) {
    captureGalleryEl.removeChild(captureGalleryEl.lastElementChild);
  }
}

function syncLiveCaptureUiFromSummary(summary) {
  const checks = Array.isArray(summary?.checks) ? summary.checks : [];
  const withImages = checks.filter((entry) => entry && entry.capture_url);

  captureGalleryEl.innerHTML = "";
  verifyThumbEl.style.display = "none";
  verifyThumbEl.removeAttribute("src");
  verifyThumbEl.classList.remove("ok", "fail");

  if (withImages.length === 0) return;

  const latest = withImages[withImages.length - 1];
  updateVerificationPreview(latest, Boolean(latest.sample_only));

  [...withImages].reverse().slice(0, 60).forEach((entry) => {
    appendCaptureThumbnail(entry);
  });

  movementPendingLocalCaptureUrls.forEach((url) => appendPendingLocalCaptureThumbnail(url));
}

function startTotalTimer(seconds, isActive) {
  if (totalTimerHandle) clearInterval(totalTimerHandle);
  let remaining = Math.max(0, Number(seconds || 0));
  totalTimerEl.textContent = fmtSecs(remaining);
  if (!isActive) return;

  totalTimerHandle = setInterval(() => {
    remaining = Math.max(0, remaining - 1);
    totalTimerEl.textContent = fmtSecs(remaining);
    if (remaining <= 0) {
      clearInterval(totalTimerHandle);
      totalTimerHandle = null;
      loadRun().catch(() => {});
    }
  }, 1000);
}

function renderRun(run) {
  activeRun = run;
  const summary = run.summary || {};
  runStatusEl.textContent = run.status;
  missCountEl.textContent = String(run.miss_count || 0);
  retryTimeEl.textContent = isSinglePoseModule ? "0s" : `${run.retry_extension_seconds || 0}s`;
  const totalTimerActive = run.status === "active" && (!isSinglePoseModule || Boolean(run.hold_started));
  startTotalTimer(run.remaining_seconds, totalTimerActive);
  syncLiveCaptureUiFromSummary(summary);

  const step = run.current_step;
  if (step) {
    postureNameEl.textContent = step.posture_name;
    postureInstructionEl.textContent = step.instruction || "";
    currentReferenceLandmarksJson = step.reference_landmarks_json || null;
    if (step.posture_image_url) {
      postureImageEl.src = step.posture_image_url;
      postureImageEl.style.display = "";
    } else {
      postureImageEl.style.display = "none";
    }
  } else {
    postureNameEl.textContent = run.status === "completed" ? "Spiel abgeschlossen" : "Keine offene Posture";
    postureInstructionEl.textContent = "";
    currentReferenceLandmarksJson = null;
    postureImageEl.style.display = "none";
    updatePhase(run.status === "completed" ? "FERTIG" : "BEREIT", "--");
  }

  setupSectionEl.classList.toggle("hidden", run.status === "active");
  playStageEl.classList.toggle("hidden", run.status !== "active");

  if (run.status === "active" && isSinglePoseModule) {
    requestAnimationFrame(() => {
      syncMotionOverlaySize();
      if (movementMonitorActive) {
        drawMotionOverlay(movementLastMarker);
      }
    });
  }

  if (run.status === "active" && moduleKey === "posture_training") {
    requestAnimationFrame(() => {
      syncMotionOverlaySize();
      drawSkeletonOnCanvas(movementLatestPoseLandmarks);
    });
  }

  if (run.status === "active" && run.current_step) {
    startRunPolling();
    if (sequenceStepId !== run.current_step.id) {
      startStepSequence(run.current_step, run.transition_seconds || 0, run.remaining_seconds || 0);
    }
  } else {
    stopRunPolling();
    stopStepSequence();
  }

  if (run.status === "completed") {
    const reason = summary.end_reason === "time_elapsed" ? "Zeit abgelaufen" : "Alle Schritte verarbeitet";
    const total = Number(summary.total_steps || 0);
    const passed = Number(summary.passed_steps || 0);
    const failed = Number(summary.failed_steps || 0);
    const timeoutFailed = Number(summary.timeout_failed_steps || 0);
    const misses = Number(summary.miss_count || run.miss_count || 0);
    analysisEl.textContent = `Spiel beendet (${reason}). Schritte: ${passed}/${total} bestanden, ${failed} fehlgeschlagen (${timeoutFailed} wegen Zeitablauf). Misses: ${misses}.`;
    renderFinalReport(summary);
    setStatus("Spiel abgeschlossen. Bericht gespeichert.", false);
    updatePhase("FERTIG", "--");
    stopCamera();
  } else {
    finalReportEl.innerHTML = "";
  }

  if (run.status !== "active" && !movementEventInFlight && !movementPendingViolation) {
    setUploadDebug("", false);
  }

  if (run.status === "active" && !cameraStream) {
    startCamera().catch((err) => {
      setStatus(`Kamera konnte nicht gestartet werden: ${err.message}`, true);
    });
  }
}

function stopStepSequence() {
  sequenceToken += 1;
  sequenceStepId = null;
  stopPostureScoreMonitor();
  stopSkeletonMonitor();
  stopMovementMonitor();
  if (phaseTimerHandle) {
    clearInterval(phaseTimerHandle);
    phaseTimerHandle = null;
  }
}

function countdownPhase({
  token,
  label,
  startSeconds,
  onTick,
  onFinished,
}) {
  if (phaseTimerHandle) clearInterval(phaseTimerHandle);
  let seconds = Math.max(0, Number(startSeconds || 0));
  updatePhase(label, String(seconds));

  if (seconds <= 0) {
    onFinished();
    return;
  }

  phaseTimerHandle = setInterval(() => {
    if (token !== sequenceToken) {
      clearInterval(phaseTimerHandle);
      phaseTimerHandle = null;
      return;
    }

    seconds = Math.max(0, seconds - 1);
    if (onTick) {
      onTick(seconds);
    }
    if (seconds > 0 && seconds <= 5) {
      beep();
    }
    updatePhase(label, String(seconds));

    if (seconds <= 0) {
      clearInterval(phaseTimerHandle);
      phaseTimerHandle = null;
      onFinished();
    }
  }, 1000);
}

function startStepSequence(step, transitionSeconds, runRemainingSeconds) {
  sequenceToken += 1;
  const token = sequenceToken;
  sequenceStepId = step.id;
  const budget = Math.max(0, Number(runRemainingSeconds || 0));
  // For single-pose modules the pose detection itself is the "get ready" gate.
  // No countdown before the hold phase is needed, and holdSeconds must not be
  // capped by the current budget because the server clock doesn't start until
  // hold-started is signalled (the server will cap via remaining_seconds).
  const readyCountdownSeconds = isSinglePoseModule
    ? Math.max(0, Number(transitionSeconds || 0))
    : 0;
  const transition = isSinglePoseModule ? 0 : Math.max(0, Math.min(Number(transitionSeconds || 0), budget));
  const holdBudget = Math.max(0, budget - transition);
  const holdSeconds = isSinglePoseModule
    ? Math.max(0, Number(step.raw_target_seconds || step.target_seconds || 0))
    : Math.max(0, Math.min(Number(step.target_seconds || 0), holdBudget));
  const sampleWindowStart = 2;
  const sampleWindowEnd = Math.max(sampleWindowStart, holdSeconds - 6);
  const sampleSecond = (!isSinglePoseModule && moduleKey !== "posture_training" && holdSeconds >= 8)
    ? (sampleWindowStart + Math.floor(Math.random() * (sampleWindowEnd - sampleWindowStart + 1)))
    : null;
  let sampleTriggered = false;

  const beginHold = async () => {
    if (holdSeconds <= 0) {
      loadRun().catch(() => {});
      return;
    }

    // Signal the server that positioning is done — the game clock starts now.
    // For single-pose modules this prevents positioning time from eating the timer.
    let effectiveHoldSeconds = holdSeconds;
    if (isSinglePoseModule) {
      try {
        const holdData = await api(`/api/games/runs/${runId}/hold-started`, { method: "POST" });
        const serverRemaining = Number(holdData.remaining_seconds || 0);
        if (serverRemaining > 0) {
          effectiveHoldSeconds = Math.min(holdSeconds, serverRemaining);
        }
      } catch (err) {
        // Non-fatal: if the run already ended, the movement monitor and
        // complete-step flow will handle the error gracefully.
      }
      if (token !== sequenceToken) return;
    }

    if (isSinglePoseModule) {
      // Strict modules use frame-based movement detection on the live stream.
      startMovementMonitor(token).catch(() => {});
    } else if (moduleKey === "posture_training") {
      startSkeletonMonitor(token).catch(() => {});
      startPostureScoreMonitor(token).catch(() => {});
    }

    countdownPhase({
      token,
      label: "POSE HALTEN",
      startSeconds: effectiveHoldSeconds,
      onTick: (secondsRemaining) => {
        if (
          sampleSecond !== null
          && !sampleTriggered
          && secondsRemaining === sampleSecond
        ) {
          sampleTriggered = true;
          verifyCurrentStepWithMode(token, { sampleOnly: true }).catch(() => {});
        }
      },
      onFinished: async () => {
        stopPostureScoreMonitor();
        stopSkeletonMonitor();
        if (isSinglePoseModule) {
          finalizeStrictCompletionAfterSettledViolations(token).catch(() => {});
        } else {
          stopMovementMonitor();
          verifyCurrentStepWithMode(token, { sampleOnly: false });
        }
      },
    });
  };

  if (isSinglePoseModule) {
    startStrictStartAlignment(token, readyCountdownSeconds, beginHold);
    return;
  }

  countdownPhase({
    token,
    label: "POSE EINNEHMEN",
    startSeconds: transition,
    onFinished: beginHold,
  });
}

async function loadModule() {
  const data = await api(`/api/games/modules/${moduleKey}`);
  const diffSel = document.getElementById("gm-difficulty");
  diffSel.innerHTML = data.difficulties
    .map((d) => `<option value="${d.key}">${d.label}</option>`)
    .join("");
  if ([...diffSel.options].some((opt) => opt.value === initialDifficulty)) {
    diffSel.value = initialDifficulty;
  }

  if (isSinglePoseModule) {
    if (transitionWrapEl) transitionWrapEl.classList.add("hidden");
    if (maxMissesWrapEl) maxMissesWrapEl.classList.add("hidden");
    if (sessionPenaltyLabelTextEl) {
      sessionPenaltyLabelTextEl.textContent = "Penalty pro Verfehlung (Tage/Std/Min)";
    }
    if (missLabelEl) {
      missLabelEl.textContent = "Verstoesse";
    }
    document.getElementById("gm-max-misses").value = "1";
  } else if (transitionLabelTextEl) {
    transitionLabelTextEl.textContent = "Wechseldauer (Sek)";
    if (transitionWrapEl) transitionWrapEl.classList.remove("hidden");
  }

  if (isTiptoeingModule) {
    if (dontMoveOptionsEl) dontMoveOptionsEl.classList.add("hidden");
    if (cameraGuidanceEl) {
      cameraGuidanceEl.textContent = "Ausschnitt: Fuesse bis untere Knie sichtbar. Ziel: nur die Fussbereiche in Gruen, Schwarz nie beruehren, Fersen angehoben auf den Zehenspitzen halten.";
    }
    if (maskPreviewEl) {
      maskPreviewEl.src = tiptoeingMaskUrl;
      maskPreviewEl.style.display = "";
    }

    const postureData = await api(`/api/inventory/postures/modules/${moduleKey}/available`);
    const usable = postureData.items || [];
    if (usable.length === 0) {
      throw new Error("Keine freigegebenen Postures fuer Tiptoeing vorhanden");
    }
  }

  if (isDontMoveModule) {
    dontMoveOptionsEl.classList.remove("hidden");
    if (maxMissesWrapEl) {
      maxMissesWrapEl.classList.remove("hidden");
    }
    if (cameraGuidanceEl) {
      cameraGuidanceEl.textContent = "Achte auf einen stabilen Ganzkoerper-Ausschnitt ohne Verdeckung der relevanten Haltung.";
    }
    if (maskPreviewEl) {
      maskPreviewEl.style.display = "none";
      maskPreviewEl.removeAttribute("src");
    }

    const postureData = await api(`/api/inventory/postures/modules/${moduleKey}/available`);
    const usable = postureData.items || [];
    dontMovePostureEl.innerHTML = "";
    for (const item of usable) {
      const option = document.createElement("option");
      option.value = String(item.posture_key || "");
      option.textContent = String(item.title || item.posture_key || "Pose");
      dontMovePostureEl.appendChild(option);
    }
    if (usable.length === 0) {
      throw new Error("Keine freigegebenen Postures fuer dieses Modul vorhanden");
    }
  }

  if (!isSinglePoseModule && cameraGuidanceEl) {
    cameraGuidanceEl.textContent = "Achte auf einen stabilen Ausschnitt mit klar erkennbarer Koerperhaltung.";
  }
  if (!isTiptoeingModule && maskPreviewEl) {
    maskPreviewEl.style.display = "none";
    maskPreviewEl.removeAttribute("src");
  }
}

async function loadModuleSettings() {
  const data = await api(`/api/games/modules/${moduleKey}/settings`);
  moduleSettings = {
    easy_target_multiplier: Number(data.easy_target_multiplier || 0.85),
    hard_target_multiplier: Number(data.hard_target_multiplier || 1.25),
    target_randomization_percent: Number(data.target_randomization_percent || 10),
    movement_easy_pose_deviation: Number(data.movement_easy_pose_deviation || 0),
    movement_easy_stillness: Number(data.movement_easy_stillness || 0),
    movement_medium_pose_deviation: Number(data.movement_medium_pose_deviation || 0),
    movement_medium_stillness: Number(data.movement_medium_stillness || 0),
    movement_hard_pose_deviation: Number(data.movement_hard_pose_deviation || 0),
    movement_hard_stillness: Number(data.movement_hard_stillness || 0),
    pose_similarity_min_score_easy: Number(data.pose_similarity_min_score_easy || 0),
    pose_similarity_min_score_medium: Number(data.pose_similarity_min_score_medium || 0),
    pose_similarity_min_score_hard: Number(data.pose_similarity_min_score_hard || 0),
    mask_image_url: data.mask_image_url || null,
  };
  if (isTiptoeingModule && moduleSettings.mask_image_url) {
    tiptoeingMaskUrl = moduleSettings.mask_image_url;
  }
}

async function loadRun() {
  if (!runId || runRefreshInFlight) return;
  runRefreshInFlight = true;
  try {
    const run = await api(`/api/games/runs/${runId}`);
    renderRun(run);
  } finally {
    runRefreshInFlight = false;
  }
}

function stopRunPolling() {
  if (!runPollHandle) return;
  clearInterval(runPollHandle);
  runPollHandle = null;
}

function startRunPolling() {
  if (!runId || runPollHandle) return;
  runPollHandle = setInterval(() => {
    if (!activeRun || activeRun.status !== "active") {
      stopRunPolling();
      return;
    }
    loadRun().catch(() => {});
  }, 2000);
}

function preferredCameraConstraints() {
  return {
    audio: false,
    video: {
      width: { ideal: 1920 },
      height: { ideal: 1080 },
      frameRate: { ideal: 30, max: 30 },
      facingMode: "user",
    },
  };
}

function cameraConstraintCandidates(deviceId = "") {
  const trimmedDeviceId = String(deviceId || "").trim();
  const videoBase = trimmedDeviceId
    ? { deviceId: { exact: trimmedDeviceId } }
    : { facingMode: "user" };

  return [
    {
      audio: false,
      video: {
        ...videoBase,
        width: { min: 1280, ideal: 1920 },
        height: { min: 720, ideal: 1080 },
        frameRate: { ideal: 30, max: 30 },
      },
    },
    {
      audio: false,
      video: {
        ...videoBase,
        width: { ideal: 1920 },
        height: { ideal: 1080 },
        frameRate: { ideal: 30, max: 30 },
      },
    },
    {
      audio: false,
      video: {
        ...videoBase,
        width: { ideal: 1280 },
        height: { ideal: 720 },
        frameRate: { ideal: 30, max: 30 },
      },
    },
    trimmedDeviceId
      ? { audio: false, video: { deviceId: { exact: trimmedDeviceId } } }
      : preferredCameraConstraints(),
    { audio: false, video: true },
  ];
}

async function maximizeVideoTrackQuality(track) {
  if (!track || typeof track.getCapabilities !== "function" || typeof track.applyConstraints !== "function") {
    return;
  }

  const caps = track.getCapabilities();
  const advanced = {};

  if (caps.width && Number.isFinite(Number(caps.width.max))) {
    advanced.width = Number(caps.width.max);
  }
  if (caps.height && Number.isFinite(Number(caps.height.max))) {
    advanced.height = Number(caps.height.max);
  }
  if (caps.frameRate && Number.isFinite(Number(caps.frameRate.max))) {
    advanced.frameRate = Math.min(30, Number(caps.frameRate.max));
  }

  if (Object.keys(advanced).length === 0) return;

  try {
    await track.applyConstraints({ advanced: [advanced] });
  } catch {
    // Keep the original stream if the browser rejects advanced constraints.
  }
}

async function openBestCameraStream(deviceId = "") {
  let lastError = null;
  for (const constraints of cameraConstraintCandidates(deviceId)) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      return stream;
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError || new Error("Keine Kamera verfuegbar");
}

async function startCamera(forceRestart = false) {
  if (cameraStream && !forceRestart) {
    updateCameraMeta();
    return;
  }
  if (cameraStream && forceRestart) {
    stopCamera();
  }

  await refreshCameraDevices();
  cameraStartBtnEl.disabled = true;
  cameraStartBtnEl.textContent = forceRestart ? "Kamera verbindet neu ..." : "Kamera verbindet ...";

  try {
    cameraStream = await openBestCameraStream(effectiveCameraDeviceId());
  } finally {
    cameraStartBtnEl.disabled = false;
    cameraStartBtnEl.textContent = cameraStream ? "Kamera neu verbinden" : "Kamera aktivieren";
  }

  const track = cameraStream.getVideoTracks()[0];
  if (track) {
    try {
      track.contentHint = "detail";
    } catch {
      // Ignore browsers that expose contentHint as read-only or unsupported.
    }
    await maximizeVideoTrackQuality(track);
    const settings = typeof track.getSettings === "function" ? track.getSettings() : {};
    const activeDeviceId = String(settings.deviceId || "").trim();
    if (activeDeviceId) {
      selectedCameraDeviceId = activeDeviceId;
      storeCameraDeviceId(activeDeviceId);
    } else {
      storeCameraDeviceId(selectedCameraDeviceId);
    }
  }

  setupVideoEl.srcObject = cameraStream;
  playVideoEl.srcObject = cameraStream;
  await refreshCameraDevices();
  updateCameraMeta(track);
  window.setTimeout(() => {
    syncMotionOverlaySize();
    updateCameraMeta(track);
    if (isSinglePoseModule && movementMonitorActive) {
      drawMotionOverlay(movementLastMarker);
    } else if (moduleKey === "posture_training") {
      drawSkeletonOnCanvas(movementLatestPoseLandmarks);
    }
  }, 120);
}

function stopCamera() {
  if (!cameraStream) return;
  for (const track of cameraStream.getTracks()) track.stop();
  cameraStream = null;
  setupVideoEl.srcObject = null;
  playVideoEl.srcObject = null;
  stopPostureScoreMonitor();
  stopSkeletonMonitor();
  stopMovementMonitor();
  updateCameraMeta(null);
}

async function captureFrameBlob() {
  if (!cameraStream) return null;
  const dims = uploadCaptureDimensions();
  const canvas = document.createElement("canvas");
  canvas.width = dims.width;
  canvas.height = dims.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(playVideoEl, 0, 0, canvas.width, canvas.height);
  const photoBlob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.88));
  return photoBlob || null;
}

async function verifyCurrentStep(token) {
  return verifyCurrentStepWithMode(token, { sampleOnly: false });
}

async function completeStrictStepWithoutCapture(token) {
  if (token !== sequenceToken) return;
  if (!activeRun || activeRun.status !== "active" || !activeRun.current_step) return;

  if (!movementPoseReady) {
    analysisEl.textContent = "Echtzeit-Bewegungserkennung nicht verfuegbar - automatischer Abschluss gestoppt.";
    setStatus("Echtzeit-Bewegungserkennung fehlt. Bitte Spiel neu starten.", true);
    return;
  }

  try {
    updatePhase("ABSCHLUSS", "...");
    const result = await api(`/api/games/runs/${runId}/steps/${activeRun.current_step.id}/complete`, {
      method: "POST",
    });
    analysisEl.textContent = result.step.analysis || "Haltephase ohne Bewegungsverstoss abgeschlossen.";
    renderRun(result.run);
    if (result.run.status === "completed") {
      setStatus("Spiel abgeschlossen.", false);
      updatePhase("FERTIG", "--");
    }
  } catch (err) {
    const msg = String(err && err.message ? err.message : err || "");
    if (msg.includes("not active") || msg.includes("not pending")) {
      loadRun().catch(() => {});
      return;
    }
    analysisEl.textContent = `Abschluss fehlgeschlagen: ${err.message}`;
    setStatus(`Abschluss fehlgeschlagen: ${err.message}`, true);
    setTimeout(() => {
      if (token === sequenceToken && activeRun && activeRun.status === "active") {
        completeStrictStepWithoutCapture(token).catch(() => {});
      }
    }, 2000);
  }
}

async function verifyCurrentStepWithMode(token, options = {}) {
  const sampleOnly = Boolean(options.sampleOnly);
  const monitorOnly = Boolean(options.monitorOnly);
  if (token !== sequenceToken) return;
  if (!activeRun || activeRun.status !== "active" || !activeRun.current_step) return;
  if (verifyInFlight) {
    if (!sampleOnly && !monitorOnly) {
      setTimeout(() => {
        if (token === sequenceToken) {
          verifyCurrentStepWithMode(token, { sampleOnly: false, monitorOnly: false }).catch(() => {});
        }
      }, 350);
    }
    return;
  }
  if (!cameraStream) {
    setStatus("Kamera ist nicht aktiv. Bitte Seite neu laden und Kamera freigeben.", true);
    return;
  }

  verifyInFlight = true;
  if (!sampleOnly && !monitorOnly) {
    updatePhase("PRUEFUNG", "...");
  }

  try {
    const blob = await captureFrameBlob();
    if (!blob) throw new Error("Kein Kamerabild verfuegbar");

    revokeMovementLocalPreview();
    movementLocalPreviewUrl = URL.createObjectURL(blob);
    verifyThumbEl.src = movementLocalPreviewUrl;
    verifyThumbEl.style.display = "";
    verifyThumbEl.classList.remove("ok", "fail");
    verifyThumbEl.classList.add(sampleOnly ? "fail" : "ok");
    appendPendingLocalCaptureThumbnail(movementLocalPreviewUrl);
    setUploadDebug(
      `Upload startet: run=${runId}, step=${activeRun.current_step.id}, mode=${monitorOnly ? "monitor" : sampleOnly ? "sample" : "final"}, size=${blob.size || 0} bytes`,
      monitorOnly || sampleOnly
    );

    const form = new FormData();
    form.append("file", blob, "autocap.jpg");
    form.append("observed_posture", activeRun.current_step.posture_name || "");
    form.append("sample_only", sampleOnly ? "true" : "false");
    form.append("monitor_only", monitorOnly ? "true" : "false");
    if (isSinglePoseModule) {
      const marker = bestEffortMovementMarker();
      if (marker && Number.isFinite(marker.x) && Number.isFinite(marker.y)) {
        form.append("marker_x", String(marker.x));
        form.append("marker_y", String(marker.y));
      }
    }

    const result = await api(`/api/games/runs/${runId}/steps/${activeRun.current_step.id}/verify`, {
      method: "POST",
      body: form,
    });

    setUploadDebug(
      `Upload erfolgreich: status=${result.step?.verification_status || "?"}, image=${result.step?.capture_url || "-"}`,
      false
    );
    revokeMovementLocalPreview();
    if (result.step && result.step.capture_url) {
      clearPendingLocalCaptureGallery();
    }

    const livePoseStatus = String(
      result?.step?.pose_similarity_status || result?.step?.verification_status || ""
    ).toLowerCase();
    const verificationStatus = String(result?.step?.verification_status || "").toLowerCase();
    if (moduleKey === "posture_training") {
      if (verificationStatus === "inconclusive" || livePoseStatus === "skipped") {
        postureOverlayStatus = "inconclusive";
      } else {
        postureOverlayStatus = livePoseStatus === "confirmed" ? "confirmed" : "suspicious";
      }
      drawSkeletonOnCanvas(movementLatestPoseLandmarks);
    }

    if (!monitorOnly || (result.step && result.step.capture_url)) {
      updateVerificationPreview(result.step, sampleOnly);
    }
    if (result.step && result.step.capture_url) {
      appendCaptureThumbnail(result.step);
    }

    if (monitorOnly) {
      if (verificationStatus === "inconclusive") {
        postureInconclusiveCount += 1;
        const softPrefix = postureInconclusiveCount >= 2 ? "Pose weiter unklar" : "Pose noch nicht erkannt";
        analysisEl.textContent = `${softPrefix}: ${result.step.analysis || "Bitte Kamera, Abstand oder Ausrichtung korrigieren."}`;
      } else if (result.step && result.step.capture_url && result.step.pose_similarity) {
        postureInconclusiveCount = 0;
        const score = Number(result.step.pose_similarity.score || 0);
        const threshold = Number(result.step.pose_similarity.threshold || 0);
        analysisEl.textContent = `Pose-Score unterschritten: ${score.toFixed(1)}/100 (min ${threshold.toFixed(1)}). Kontrollbild gespeichert.`;
      } else if (result.step && result.step.pose_similarity) {
        postureInconclusiveCount = 0;
        const score = Number(result.step.pose_similarity.score || 0);
        const threshold = Number(result.step.pose_similarity.threshold || 0);
        analysisEl.textContent = `Live-Pose bestaetigt: ${score.toFixed(1)}/100 (min ${threshold.toFixed(1)}).`;
      } else {
        postureInconclusiveCount = 0;
      }
    } else if (sampleOnly) {
      if (result.step && result.step.finalized) {
        analysisEl.textContent = `Stichprobe fehlgeschlagen: ${result.step.analysis || "Pose nicht bestaetigt."}${poseSimilaritySummary(result.step)}`;
      } else {
        analysisEl.textContent = `Stichprobe bestaetigt.${poseSimilaritySummary(result.step)}`;
      }
    } else {
      analysisEl.textContent = `${result.step.analysis || "Pruefung abgeschlossen."}${poseSimilaritySummary(result.step)}`;
    }
    renderRun(result.run);
    if (result.run.status === "completed") {
      setStatus("Spiel abgeschlossen.", false);
      updatePhase("FERTIG", "--");
    }
  } catch (err) {
    setUploadDebug(`Upload fehlgeschlagen: ${err.message}`, true);
    if (!monitorOnly) {
      analysisEl.textContent = `Pruefung fehlgeschlagen: ${err.message}`;
      setStatus(`Verifikation fehlgeschlagen: ${err.message}`, true);
      setTimeout(() => {
        if (token === sequenceToken && activeRun && activeRun.status === "active") {
          verifyCurrentStepWithMode(token, { sampleOnly, monitorOnly }).catch(() => {});
        }
      }, 2500);
    }
  } finally {
    verifyInFlight = false;
  }
}

async function startRun() {
  if (!cameraStream) {
    setStatus("Bitte zuerst die Kamera aktivieren.", true);
    return;
  }

  const duration = Number(document.getElementById("gm-duration").value || 20);
  const transitionSecondsInput = Number(document.getElementById("gm-transition-seconds").value || 8);
  const difficulty = document.getElementById("gm-difficulty").value || "medium";
  const maxMissesInput = Number(document.getElementById("gm-max-misses").value || 3);
  const penaltyDays = Number(document.getElementById("gm-session-penalty-days").value || 0);
  const penaltyHours = Number(document.getElementById("gm-session-penalty-hours").value || 0);
  const penaltyMinutes = Number(document.getElementById("gm-session-penalty-minutes").value || 0);
  const sessionPenalty = Math.max(0, (penaltyDays * 86400) + (penaltyHours * 3600) + (penaltyMinutes * 60));

  let dontMovePostureKey = null;
  let effectiveTransitionSeconds = transitionSecondsInput;
  let effectiveMaxMisses = maxMissesInput;
  let effectiveDuration = duration;
  if (isDontMoveModule) {
    dontMovePostureKey = String(dontMovePostureEl.value || "").trim();
    effectiveTransitionSeconds = 0;
    effectiveMaxMisses = 1;
    if (!dontMovePostureKey) {
      setStatus("Bitte eine Pose fuer dieses Modul auswaehlen.", true);
      return;
    }
    effectiveDuration = Math.max(1, duration);
  }
  if (isTiptoeingModule) {
    effectiveTransitionSeconds = 0;
    effectiveMaxMisses = 1;
    effectiveDuration = Math.max(1, duration);
  }

  if (isSinglePoseModule) {
    try {
      await initMovementPose();
    } catch (err) {
      setStatus(`Start blockiert: ${err.message}`, true);
      analysisEl.textContent = "Echtzeit-Bewegungserkennung konnte nicht initialisiert werden.";
      return;
    }
  }

  try {
    const run = await api(`/api/games/sessions/${sessionId}/runs/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        module_key: moduleKey,
        difficulty,
        duration_minutes: effectiveDuration,
        transition_seconds: effectiveTransitionSeconds,
        initiated_by: "player",
        max_misses_before_penalty: effectiveMaxMisses,
        session_penalty_seconds: sessionPenalty,
        easy_target_multiplier: moduleSettings.easy_target_multiplier,
        hard_target_multiplier: moduleSettings.hard_target_multiplier,
        target_randomization_percent: moduleSettings.target_randomization_percent,
        selected_posture_key: dontMovePostureKey,
      }),
    });
    runId = run.id;
    analysisEl.textContent = "";
    verifyThumbEl.style.display = "none";
    verifyThumbEl.removeAttribute("src");
    verifyThumbEl.classList.remove("ok", "fail");
    captureGalleryEl.innerHTML = "";
    finalReportEl.innerHTML = "";
    setStatus("Spiel gestartet.", false);
    renderRun(run);
  } catch (err) {
    setStatus(`Start fehlgeschlagen: ${err.message}`, true);
  }
}

cameraStartBtnEl.addEventListener("click", async () => {
  try {
    await startCamera(Boolean(cameraStream));
    const track = currentVideoTrack();
    updateCameraMeta(track);
    setStatus(`Kamera aktiv: ${activeCameraLabel(track)}.`, false);
    const ctx = getAudioContext();
    if (ctx && ctx.state === "suspended") {
      await ctx.resume();
    }
  } catch (err) {
    setStatus(`Kamera konnte nicht gestartet werden: ${err.message}`, true);
  }
});

cameraDeviceEl.addEventListener("change", async () => {
  selectedCameraDeviceId = String(cameraDeviceEl.value || "").trim();
  storeCameraDeviceId(selectedCameraDeviceId);
  if (!cameraStream) {
    updateCameraMeta(null);
    setStatus(selectedCameraDeviceId ? "Kamera-Auswahl gespeichert." : "Automatische Kamerawahl aktiv.", false);
    return;
  }

  try {
    await startCamera(true);
    const track = currentVideoTrack();
    updateCameraMeta(track);
    setStatus(`Kamera gewechselt: ${activeCameraLabel(track)}.`, false);
  } catch (err) {
    setStatus(`Kamerawechsel fehlgeschlagen: ${err.message}`, true);
  }
});

document.getElementById("gm-start-btn").addEventListener("click", startRun);
beepVolumeEl.addEventListener("input", () => applyBeepVolume(beepVolumeEl.value));
testBeepEl.addEventListener("click", async () => {
  try {
    const ctx = getAudioContext();
    if (ctx && ctx.state === "suspended") {
      await ctx.resume();
    }
    beep();
    setStatus("Test-Beep abgespielt.", false);
  } catch (err) {
    setStatus(`Test-Beep fehlgeschlagen: ${err.message}`, true);
  }
});

playVideoEl.addEventListener("loadedmetadata", () => {
  syncMotionOverlaySize();
  updateCameraMeta(currentVideoTrack());
  if (isSinglePoseModule && movementMonitorActive) {
    drawMotionOverlay(movementLastMarker);
  } else if (moduleKey === "posture_training") {
    drawSkeletonOnCanvas(movementLatestPoseLandmarks);
  }
});

window.addEventListener("resize", () => {
  syncMotionOverlaySize();
  if (isSinglePoseModule && movementMonitorActive) {
    drawMotionOverlay(movementLastMarker);
  } else if (moduleKey === "posture_training") {
    drawSkeletonOnCanvas(movementLatestPoseLandmarks);
  }
});

window.addEventListener("beforeunload", () => {
  stopCamera();
  stopRunPolling();
  stopStepSequence();
  if (totalTimerHandle) clearInterval(totalTimerHandle);
});

Promise.all([loadModule(), loadModuleSettings()])
  .then(async () => {
    initializeBeepVolume();
    await refreshCameraDevices();
    if (runId) {
      await loadRun();
    } else {
      updatePhase("BEREIT", "--");
    }
  })
  .catch((err) => setStatus(`Initialisierung fehlgeschlagen: ${err.message}`, true));
