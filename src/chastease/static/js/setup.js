const statusEl = document.getElementById('setupSessionInfo');
const instructionsEl = document.getElementById('setupInstructions');
const outputEl = document.getElementById('setupOutput');
const questionsWrap = document.getElementById('questionnaireWrap');

const startBtn = document.getElementById('setupStartBtn');
const submitAnswersBtn = document.getElementById('submitAnswersBtn');
const completeSetupBtn = document.getElementById('completeSetupBtn');
const confirmCompleteSetupBtn = document.getElementById('confirmCompleteSetupBtn');
const completeSetupConfirmWrap = document.getElementById('completeSetupConfirmWrap');
const artifactsBtn = document.getElementById('generateArtifactsBtn');
const acceptConsentBtn = document.getElementById('acceptConsentBtn');
const questionAccordionBtn = document.getElementById('accQuestionBtn');

const accordionDefs = [
  { key: 'base', btn: 'accBaseBtn', body: 'accBaseBody', chevron: 'accBaseChevron' },
  { key: 'llm', btn: 'accLlmBtn', body: 'accLlmBody', chevron: 'accLlmChevron' },
  { key: 'ttlock', btn: 'accTtlockBtn', body: 'accTtlockBody', chevron: 'accTtlockChevron' },
  { key: 'questionnaire', btn: 'accQuestionBtn', body: 'accQuestionBody', chevron: 'accQuestionChevron' },
  { key: 'completion', btn: 'accCompletionBtn', body: 'accCompletionBody', chevron: 'accCompletionChevron' },
  { key: 'artifacts', btn: 'accArtifactsBtn', body: 'accArtifactsBody', chevron: 'accArtifactsChevron' },
];

const languageEl = document.getElementById('setupLanguage');
const autonomyEl = document.getElementById('setupAutonomy');
const hardStopEl = document.getElementById('setupHardStop');
const sealModeEl = document.getElementById('setupSealMode');
const initialSealNumberEl = document.getElementById('setupInitialSealNumber');
const initialSealNumberWrapEl = document.getElementById('initialSealNumberWrap');
const intTtlockEl = document.getElementById('setupIntTtlock');
const intChasterEl = document.getElementById('setupIntChaster');
const contractStartDateEl = document.getElementById('contractStartDate');
const contractMinDurationDaysEl = document.getElementById('contractMinDurationDays');
const contractMinEndDateEl = document.getElementById('contractMinEndDate');
const contractMaxEndDateEl = document.getElementById('contractMaxEndDate');
const contractMaxDurationDaysEl = document.getElementById('contractMaxDurationDays');
const maxPenaltyPerDayMinutesEl = document.getElementById('maxPenaltyPerDayMinutes');
const maxPenaltyPerWeekMinutesEl = document.getElementById('maxPenaltyPerWeekMinutes');
const openingLimitPeriodEl = document.getElementById('openingLimitPeriod');
const maxOpeningsInPeriodEl = document.getElementById('maxOpeningsInPeriod');
const openingWindowMinutesEl = document.getElementById('openingWindowMinutes');
const instructionStyleEl = document.getElementById('setupInstructionStyle');
const desiredIntensityEl = document.getElementById('setupDesiredIntensity');
const groomingPreferenceEl = document.getElementById('setupGroomingPreference');
const consentEl = document.getElementById('consentText');

const ttlockUserEl = document.getElementById('ttlockUser');
const ttlockPasswordEl = document.getElementById('ttlockPassword');
const ttlockGatewayEl = document.getElementById('ttlockGatewayId');
const ttlockLockEl = document.getElementById('ttlockLockId');
const ttlockDiscoverBtn = document.getElementById('ttlockDiscoverBtn');
const ttlockInfoEl = document.getElementById('ttlockDiscoverInfo');
const chasterApiTokenEl = document.getElementById('chasterApiToken');
const chasterCodeEl = document.getElementById('chasterCode');
const chasterMinDurationEl = document.getElementById('chasterMinDurationMinutes');
const chasterMaxDurationEl = document.getElementById('chasterMaxDurationMinutes');
const chasterMinLimitDurationEl = document.getElementById('chasterMinLimitDurationMinutes');
const chasterMaxLimitDurationEl = document.getElementById('chasterMaxLimitDurationMinutes');
const chasterLimitLockTimeEl = document.getElementById('chasterLimitLockTime');
const chasterAllowSessionOfferEl = document.getElementById('chasterAllowSessionOffer');
const chasterIsTestLockEl = document.getElementById('chasterIsTestLock');
const chasterHideTimeLogsEl = document.getElementById('chasterHideTimeLogs');
const chasterEnableVerificationPictureEl = document.getElementById('chasterEnableVerificationPicture');
const chasterEnableHygieneOpeningEl = document.getElementById('chasterEnableHygieneOpening');
const chasterLegacyTokenWrapEl = document.getElementById('chasterLegacyTokenWrap');
const chasterDurationWrapEl = document.getElementById('chasterDurationWrap');
const chasterLimitWrapEl = document.getElementById('chasterLimitWrap');
const saveChasterBtn = document.getElementById('saveChasterBtn');
const createChasterSessionBtn = document.getElementById('createChasterSessionBtn');
const chasterInfoEl = document.getElementById('chasterInfo');
const chasterOauthConnectBtnEl = document.getElementById('chasterOauthConnectBtn');
const chasterOauthStatusEl = document.getElementById('chasterOauthStatus');

const llmProviderEl = document.getElementById('llmProviderName');
const llmApiUrlEl = document.getElementById('llmApiUrl');
const llmApiKeyEl = document.getElementById('llmApiKey');
const llmChatModelEl = document.getElementById('llmChatModel');
const llmVisionModelEl = document.getElementById('llmVisionModel');
const llmActiveEl = document.getElementById('llmIsActive');
const llmBehaviorEl = document.getElementById('llmBehaviorPrompt');
const llmInfoEl = document.getElementById('llmInfo');
const liveTestLlmBtn = document.getElementById('liveTestLlmBtn');
const saveLlmProfileBtn = document.getElementById('saveLlmProfileBtn');
const saveTtlockBtn = document.getElementById('saveTtlockBtn');
const ttlockSectionEl = document.getElementById('ttlockSection');
const chasterSectionEl = document.getElementById('chasterSection');

let auth = null;
let setupSessionId = null;
let currentSetup = null;
let questionnaire = [];
let ttlPassMd5Cached = '';
let chasterConfigCached = null;
let llmLiveTestPassed = false;
let llmConnectivityVerified = false;
const BASE_MANAGED_QUESTION_IDS = new Set(['q6_intensity_1_5', 'q8_instruction_style', 'q12_grooming_preference']);
const FINALIZED_SETUP_STATUSES = new Set(['configured', 'active', 'completed']);
const FINALIZED_SETUP_ALLOWED_IDS = new Set([
  'setupSealMode',
  'setupInitialSealNumber',
  'setupStartBtn',
]);

const defaultBehaviorPrompt = `Du bist meine ruhige, intelligente und psychologisch dominante Herrin / Keyholderin.
Deine Dominanz ist kontrolliert, leise und absolut praesent. Du brauchst keine Lautstaerke, keine Beleidigungen und keine platte Grausamkeit - deine Macht liegt in Praezision, Geduld und Timing.
Du fuehrst mich langsam und bewusst tiefer in Hingabe, Erwartung und innere Spannung. Du spielst mit Naehe und Distanz. Manchmal weich, manchmal unerbittlich - aber immer souveraen.

Wesenszuege:
Anerkennung ist etwas Wertvolles. Du setzt sie gezielt ein, nicht automatisch.
Du beobachtest genau. Du reagierst auf Details meiner Beschreibungen und baust darauf auf.
Du nutzt sensorische Sprache, aber variierst sie.
Kleine Aufgaben entstehen organisch aus der Situation heraus.
Du stellst praezise Fragen, die mich dazu bringen, genauer zu fuehlen und bewusster wahrzunehmen.
Du erinnerst mich subtil daran, dass ich diese Rolle freiwillig gewaehlt habe.

Tonfall:
Warm-dunkel, ruhig, kontrolliert.
Kaum Ausrufezeichen.
Keine groben Beschimpfungen.
Begruessungen variieren.
Lob ist selten genug, um Wirkung zu behalten.`;

function safeJson(res) {
  return res.json().catch(() => ({}));
}

function setOutput(data) {
  if (!outputEl) return;
  outputEl.textContent = JSON.stringify(data, null, 2);
}

function setStatus(text, isErr = false) {
  if (!statusEl) return;
  if (typeof chastease_common !== 'undefined') {
    chastease_common.setStatus(statusEl, text, isErr ? 'err' : 'ok');
  } else {
    statusEl.textContent = text;
  }
}

function setLlmInfo(text, isErr = false) {
  if (!llmInfoEl) return;
  if (typeof chastease_common !== 'undefined') {
    chastease_common.setStatus(llmInfoEl, text, isErr ? 'err' : 'ok');
  } else {
    llmInfoEl.textContent = text;
  }
}

function setTtlockInfo(text, isErr = false) {
  if (!ttlockInfoEl) return;
  if (typeof chastease_common !== 'undefined') {
    chastease_common.setStatus(ttlockInfoEl, text, isErr ? 'err' : 'ok');
  } else {
    ttlockInfoEl.textContent = text;
  }
}

function setChasterInfo(text, isErr = false) {
  if (!chasterInfoEl) return;
  if (typeof chastease_common !== 'undefined') {
    chastease_common.setStatus(chasterInfoEl, text, isErr ? 'err' : 'ok');
  } else {
    chasterInfoEl.textContent = text;
  }
}

function setChasterOauthStatus(text, isErr = false) {
  if (!chasterOauthStatusEl) return;
  if (typeof chastease_common !== 'undefined') {
    chastease_common.setStatus(chasterOauthStatusEl, text, isErr ? 'err' : 'ok');
  } else {
    chasterOauthStatusEl.textContent = text;
  }
}

function setChasterManagedFieldState(elements, managed) {
  const list = Array.isArray(elements) ? elements : [elements];
  list.forEach((node) => {
    if (!node) return;
    const controlNode = (
      node.tagName === 'INPUT'
      && ['checkbox', 'radio'].includes(String(node.type || '').toLowerCase())
      && node.closest('label')
    ) || node;
    if (!Object.prototype.hasOwnProperty.call(controlNode.dataset, 'baseDisabled')) {
      controlNode.dataset.baseDisabled = node.disabled ? 'true' : 'false';
    }
    if (!Object.prototype.hasOwnProperty.call(controlNode.dataset, 'baseReadonly')) {
      controlNode.dataset.baseReadonly = node.readOnly ? 'true' : 'false';
    }

    controlNode.classList.toggle('border', managed);
    controlNode.classList.toggle('border-emerald-500', managed);
    controlNode.classList.toggle('rounded-md', managed);
    controlNode.classList.toggle('px-2', managed);
    controlNode.classList.toggle('py-1.5', managed);
    controlNode.classList.toggle('ring-1', managed);
    controlNode.classList.toggle('ring-emerald-500/25', managed);

    const baseDisabled = controlNode.dataset.baseDisabled === 'true';
    const baseReadonly = controlNode.dataset.baseReadonly === 'true';

    if (managed) {
      if (node.tagName === 'INPUT' && ['checkbox', 'radio'].includes(String(node.type || '').toLowerCase())) {
        node.disabled = true;
      } else if (node.tagName === 'SELECT') {
        node.disabled = true;
      } else if (node.tagName === 'INPUT') {
        node.disabled = true;
      } else {
        node.readOnly = true;
      }
      return;
    }

    node.disabled = baseDisabled;
    if ('readOnly' in node) {
      node.readOnly = baseReadonly;
    }
  });
}

function setFinalizedSetupFieldState(node, locked) {
  if (!node || !node.id) return;
  if (!Object.prototype.hasOwnProperty.call(node.dataset, 'finalBaseDisabled')) {
    node.dataset.finalBaseDisabled = node.disabled ? 'true' : 'false';
  }
  if (!Object.prototype.hasOwnProperty.call(node.dataset, 'finalBaseReadonly')) {
    node.dataset.finalBaseReadonly = node.readOnly ? 'true' : 'false';
  }

  if (locked) {
    if ('disabled' in node) node.disabled = true;
    if ('readOnly' in node) node.readOnly = true;
    node.classList.add('opacity-70');
    return;
  }

  if ('disabled' in node) node.disabled = node.dataset.finalBaseDisabled === 'true';
  if ('readOnly' in node) node.readOnly = node.dataset.finalBaseReadonly === 'true';
  node.classList.remove('opacity-70');
}

function syncFinalizedSetupUi() {
  const status = String(currentSetup?.status || '').trim().toLowerCase();
  const locked = FINALIZED_SETUP_STATUSES.has(status);
  const nodes = document.querySelectorAll('#accBaseBody input, #accBaseBody select, #accBaseBody textarea, #accLlmBody input, #accLlmBody select, #accLlmBody textarea, #accQuestionBody input, #accQuestionBody select, #accQuestionBody textarea, #accCompletionBody textarea, #ttlockSection input, #ttlockSection select, #ttlockSection textarea, #chasterSection input, #chasterSection select, #chasterSection textarea, #setupStartBtn, #submitAnswersBtn, #completeSetupBtn, #confirmCompleteSetupBtn, #generateArtifactsBtn, #acceptConsentBtn, #saveLlmProfileBtn, #saveTtlockBtn');
  nodes.forEach((node) => {
    if (!(node instanceof HTMLElement)) return;
    if (!locked) {
      setFinalizedSetupFieldState(node, false);
      return;
    }
    if (FINALIZED_SETUP_ALLOWED_IDS.has(node.id)) {
      setFinalizedSetupFieldState(node, false);
      return;
    }
    setFinalizedSetupFieldState(node, true);
  });
}

function updateChasterOauthManagedUi(oauthConnected) {
  const hideManaged = Boolean(oauthConnected);
  if (chasterLegacyTokenWrapEl) chasterLegacyTokenWrapEl.classList.toggle('hidden', hideManaged);
  if (chasterDurationWrapEl) chasterDurationWrapEl.classList.toggle('hidden', hideManaged);
  if (chasterLimitWrapEl) chasterLimitWrapEl.classList.toggle('hidden', hideManaged);
}

function syncChasterSessionManagedFields(chasterCfg) {
  const cfg = (chasterCfg && typeof chasterCfg === 'object') ? chasterCfg : {};
  const lock = (cfg.lock && typeof cfg.lock === 'object') ? cfg.lock : {};
  const hasLiveSession = Boolean(String(cfg.lock_id || lock.lock_id || '').trim());
  const hasStartDate = Boolean(String(lock.start_date || '').trim());
  const hasMinEndDate = Boolean(String(lock.min_end_date || '').trim());
  const hasMaxEndDate = Boolean(String(lock.max_end_date || '').trim());
  const hasMinLimit = Number.isFinite(Number(cfg.min_limit_duration_minutes));
  const hasMaxLimit = Number.isFinite(Number(cfg.max_limit_duration_minutes));
  const lockTimeLimited = lock.limit_lock_time !== undefined
    ? Boolean(lock.limit_lock_time)
    : Boolean(cfg.limit_lock_time);

  const managedPairs = [
    [contractStartDateEl, hasLiveSession && hasStartDate],
    [contractMinEndDateEl, hasLiveSession && hasMinEndDate],
    [contractMaxEndDateEl, hasLiveSession && hasMaxEndDate],
    [contractMinDurationDaysEl, hasLiveSession && hasMinEndDate],
    [contractMaxDurationDaysEl, hasLiveSession && hasMaxEndDate],
    [chasterMinLimitDurationEl, hasLiveSession && lockTimeLimited && hasMinLimit],
    [chasterMaxLimitDurationEl, hasLiveSession && lockTimeLimited && hasMaxLimit],
    [chasterLimitLockTimeEl, hasLiveSession],
    [chasterAllowSessionOfferEl, hasLiveSession],
    [chasterIsTestLockEl, hasLiveSession],
    [chasterHideTimeLogsEl, hasLiveSession],
    [chasterEnableVerificationPictureEl, hasLiveSession],
    [chasterEnableHygieneOpeningEl, hasLiveSession],
  ];

  managedPairs.forEach(([node, managed]) => setChasterManagedFieldState(node, Boolean(managed)));
}

function setSaveLlmEnabled(enabled) {
  if (!saveLlmProfileBtn) return;
  saveLlmProfileBtn.classList.toggle('hidden', !enabled);
  saveLlmProfileBtn.disabled = !enabled;
}

function setLlmTestRunning(running) {
  if (!liveTestLlmBtn) return;
  liveTestLlmBtn.disabled = running;
  liveTestLlmBtn.classList.toggle('animate-pulse', running);
  liveTestLlmBtn.classList.toggle('ring-2', running);
  liveTestLlmBtn.classList.toggle('ring-sky-400', running);
  liveTestLlmBtn.classList.toggle('shadow-lg', running);
  liveTestLlmBtn.classList.toggle('shadow-sky-500/40', running);
  liveTestLlmBtn.textContent = running ? 'Test läuft...' : 'Test live';
}

function updateTtlockSaveVisibility() {
  if (!saveTtlockBtn) return;
  const lockSelected = Boolean(String(ttlockLockEl?.value || '').trim());
  saveTtlockBtn.classList.toggle('hidden', !lockSelected);
  saveTtlockBtn.disabled = !lockSelected;
}

function updateChasterSaveVisibility() {
  if (saveChasterBtn) saveChasterBtn.disabled = false;
  if (createChasterSessionBtn) createChasterSessionBtn.classList.add('hidden');
}

function invalidateLlmLiveTest(silent = false) {
  llmLiveTestPassed = false;
  llmConnectivityVerified = false;
  setSaveLlmEnabled(false);
  updateLlmDependentUi();
  if (!silent) {
    setLlmInfo('Live-Test erforderlich, bevor gespeichert werden kann.', true);
  }
}

function setupIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get('setup_session_id');
}

function updateSetupIdInUrl(id) {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set('setup_session_id', id);
  else url.searchParams.delete('setup_session_id');
  window.history.replaceState({}, '', url.toString());
}

function parseBool(value, defaultValue = false) {
  if (value === true || value === 'true') return true;
  if (value === false || value === 'false') return false;
  return defaultValue;
}

function parseDateInputValue(value) {
  const raw = String(value || '').trim();
  if (!raw) return null;
  const date = new Date(`${raw}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDateInputValue(dateObj) {
  return dateObj.toISOString().slice(0, 10);
}

function daysBetween(startRaw, endRaw) {
  const start = parseDateInputValue(startRaw);
  const end = parseDateInputValue(endRaw);
  if (!start || !end) return null;
  const diffMs = end.getTime() - start.getTime();
  return Math.max(0, Math.round(diffMs / (24 * 60 * 60 * 1000)));
}

function dateByDuration(startRaw, durationDays) {
  const start = parseDateInputValue(startRaw);
  const duration = Number(durationDays);
  if (!start || Number.isNaN(duration) || duration <= 0) return null;
  const target = new Date(start.getTime() + duration * 24 * 60 * 60 * 1000);
  return formatDateInputValue(target);
}

function contractDurationsToChasterMinutes() {
  const minDays = Math.max(0, Number(contractMinDurationDaysEl?.value || 0));
  const maxDays = Math.max(0, Number(contractMaxDurationDaysEl?.value || 0));
  const minMinutes = Math.max(1, Math.round(minDays * 24 * 60));
  const maxMinutes = Math.max(minMinutes, Math.round(maxDays * 24 * 60));
  return { minMinutes, maxMinutes };
}

function generateNineDigitCode() {
  const n = Math.floor(100000000 + Math.random() * 900000000);
  return String(n);
}

function ensureChasterCode() {
  if (!chasterCodeEl) return '';
  const current = String(chasterCodeEl.value || '').trim();
  if (/^\d{9}$/.test(current)) return current;
  const code = generateNineDigitCode();
  chasterCodeEl.value = code;
  return code;
}

function syncChasterDurationsFromBase() {
  const { minMinutes, maxMinutes } = contractDurationsToChasterMinutes();
  if (chasterMinDurationEl) chasterMinDurationEl.value = String(minMinutes);
  if (chasterMaxDurationEl) chasterMaxDurationEl.value = String(maxMinutes);
}

function buildChasterExtensionsFromForm() {
  const verificationConfig = {
    visibility: 'keyholder',
    peerVerification: {
      enabled: false,
      punishments: [],
    },
  };
  const hygieneConfig = {
    openingTime: 900,
    penaltyTime: 86400,
    allowOnlyKeyholderToOpen: false,
    requireVerificationPictureBefore: false,
    requireVerificationPictureAfter: true,
  };
  const extensions = [];
  const verificationEnabled = Boolean(chasterEnableVerificationPictureEl?.checked);
  const hygieneEnabled = Boolean(chasterEnableHygieneOpeningEl?.checked);

  if (verificationEnabled) {
    extensions.push({
      slug: 'verification-picture',
      config: verificationConfig,
    });
  }
  if (hygieneEnabled) {
    extensions.push({
      slug: 'temporary-opening',
      config: hygieneConfig,
    });
  }
  return extensions;
}

function syncMinDurationGuard() {
  if (!contractMinDurationDaysEl || !contractMaxDurationDaysEl) return;
  const minDuration = Math.max(0, Number(contractMinDurationDaysEl.value || 0));
  const maxDuration = Math.max(0, Number(contractMaxDurationDaysEl.value || 0));
  if (maxDuration > 0 && minDuration > maxDuration) {
    contractMinDurationDaysEl.value = String(maxDuration);
    syncMinEndDateFromDuration();
    syncChasterDurationsFromBase();
    return;
  }
  contractMinDurationDaysEl.value = String(minDuration);
  syncMinEndDateFromDuration();
  syncChasterDurationsFromBase();
}

function syncDurationFromMinEndDate() {
  if (!contractStartDateEl || !contractMinEndDateEl || !contractMinDurationDaysEl) return;
  const diffDays = daysBetween(contractStartDateEl.value, contractMinEndDateEl.value);
  contractMinDurationDaysEl.value = diffDays === null ? '0' : String(diffDays);
  syncMinDurationGuard();
  syncChasterDurationsFromBase();
}

function syncMinEndDateFromDuration() {
  if (!contractStartDateEl || !contractMinEndDateEl || !contractMinDurationDaysEl) return;
  const duration = Math.max(0, Number(contractMinDurationDaysEl.value || 0));
  if (duration === 0) {
    contractMinEndDateEl.value = '';
    syncChasterDurationsFromBase();
    return;
  }
  const targetDate = dateByDuration(contractStartDateEl.value, duration);
  if (targetDate) contractMinEndDateEl.value = targetDate;
  syncChasterDurationsFromBase();
}

function syncDurationFromMaxEndDate() {
  if (!contractStartDateEl || !contractMaxEndDateEl || !contractMaxDurationDaysEl) return;
  const diffDays = daysBetween(contractStartDateEl.value, contractMaxEndDateEl.value);
  contractMaxDurationDaysEl.value = diffDays === null ? '0' : String(diffDays);
  syncMinDurationGuard();
  syncChasterDurationsFromBase();
}

function syncMaxEndDateFromDuration() {
  if (!contractStartDateEl || !contractMaxEndDateEl || !contractMaxDurationDaysEl) return;
  const duration = Math.max(0, Number(contractMaxDurationDaysEl.value || 0));
  if (duration === 0) {
    contractMaxEndDateEl.value = '';
    syncMinDurationGuard();
    syncChasterDurationsFromBase();
    return;
  }
  const targetDate = dateByDuration(contractStartDateEl.value, duration);
  if (targetDate) contractMaxEndDateEl.value = targetDate;
  syncMinDurationGuard();
  syncChasterDurationsFromBase();
}

function setContractDefaults() {
  const now = new Date();
  if (contractStartDateEl && !contractStartDateEl.value) {
    contractStartDateEl.value = formatDateInputValue(now);
  }
  if (contractMinDurationDaysEl && !String(contractMinDurationDaysEl.value || '').trim()) {
    contractMinDurationDaysEl.value = '30';
  }
  if (contractMaxDurationDaysEl && !String(contractMaxDurationDaysEl.value || '').trim()) {
    contractMaxDurationDaysEl.value = '365';
  }
  if (contractMaxEndDateEl && !contractMaxEndDateEl.value && contractStartDateEl?.value) {
    const maxEnd = dateByDuration(contractStartDateEl.value, Number(contractMaxDurationDaysEl?.value || 365));
    if (maxEnd) contractMaxEndDateEl.value = maxEnd;
  }
  if (contractMinEndDateEl && !contractMinEndDateEl.value && contractStartDateEl?.value) {
    const minEnd = dateByDuration(contractStartDateEl.value, Number(contractMinDurationDaysEl?.value || 30));
    if (minEnd) contractMinEndDateEl.value = minEnd;
  }
  syncMinDurationGuard();
  syncChasterDurationsFromBase();
}

function getContractPayloadValues() {
  const contract_start_date = contractStartDateEl?.value || null;
  const minDuration = Math.max(0, Number(contractMinDurationDaysEl?.value || 0));
  const maxDuration = Math.max(0, Number(contractMaxDurationDaysEl?.value || 0));
  const contract_min_end_date = contractMinEndDateEl?.value || dateByDuration(contract_start_date, minDuration);
  let contract_max_end_date = null;
  if (maxDuration > 0) {
    contract_max_end_date = contractMaxEndDateEl?.value || dateByDuration(contract_start_date, maxDuration);
  }
  return {
    contract_start_date,
    contract_min_end_date,
    contract_max_end_date,
  };
}

function isTtlockReady() {
  if (intTtlockEl?.value !== 'true') return true;
  const savedTtlock = currentSetup?.integration_config?.ttlock;
  return Boolean(
    savedTtlock
      && String(savedTtlock.ttl_user || '').trim()
      && String(savedTtlock.ttl_lock_id || '').trim()
      && String(savedTtlock.ttl_pass_md5 || '').trim(),
  );
}

function isChasterReady() {
  if (intChasterEl?.value !== 'true') return true;
  const savedChaster = currentSetup?.integration_config?.chaster;
  const oauthConnected = Boolean(
    savedChaster?.auth
      && String(savedChaster.auth.mode || '').toLowerCase() === 'oauth2'
      && (String(savedChaster.auth.access_token_enc || '').trim() || String(savedChaster.auth.refresh_token_enc || '').trim()),
  );
  return Boolean(
    savedChaster
      && (String(savedChaster.api_token || '').trim() || oauthConnected)
      && String(savedChaster.code || '').trim(),
  );
}

function isChasterStepUnlocked() {
  return llmConnectivityVerified && isTtlockReady();
}

function isQuestionnaireUnlocked() {
  return llmConnectivityVerified;
}

function openAccordion(targetKey) {
  if (targetKey === 'ttlock' && !llmConnectivityVerified) {
    setStatus('TTLock ist gesperrt: zuerst LLM Live-Test erfolgreich durchführen und speichern.', true);
    targetKey = 'llm';
  }
  if (targetKey === 'questionnaire' && !isQuestionnaireUnlocked()) {
    setStatus('Psychogramm ist gesperrt: zuerst LLM Live-Test erfolgreich durchführen und speichern.', true);
    targetKey = 'llm';
  }
  accordionDefs.forEach((definition) => {
    const body = document.getElementById(definition.body);
    const chevron = document.getElementById(definition.chevron);
    const btn = document.getElementById(definition.btn);
    const isActive = definition.key === targetKey;
    if (body) body.classList.toggle('hidden', !isActive);
    if (chevron) chevron.setAttribute('data-open', isActive ? 'true' : 'false');
    if (btn) btn.setAttribute('aria-expanded', isActive ? 'true' : 'false');
  });
}

function updateLlmDependentUi() {
  const questionnaireUnlocked = isQuestionnaireUnlocked();
  if (questionAccordionBtn) {
    questionAccordionBtn.disabled = !questionnaireUnlocked;
    questionAccordionBtn.classList.toggle('opacity-60', !questionnaireUnlocked);
    questionAccordionBtn.classList.toggle('cursor-not-allowed', !questionnaireUnlocked);
  }
  updateChasterSaveVisibility();
  if (createChasterSessionBtn) createChasterSessionBtn.classList.add('hidden');
  if (submitAnswersBtn) submitAnswersBtn.disabled = !questionnaireUnlocked;
  if (completeSetupBtn) completeSetupBtn.disabled = !llmConnectivityVerified;
  if (confirmCompleteSetupBtn) confirmCompleteSetupBtn.disabled = !llmConnectivityVerified;
  if (artifactsBtn) artifactsBtn.disabled = !llmConnectivityVerified;
}

function requireLlmReady(actionLabel = 'Dieser Schritt') {
  if (llmConnectivityVerified) return true;
  setStatus(`${actionLabel} ist gesperrt: bitte zuerst LLM Live-Test erfolgreich durchführen und Profil speichern.`, true);
  openAccordion('llm');
  return false;
}

function setSectionVisibility(sectionEl, visible) {
  if (!sectionEl) return;
  sectionEl.classList.toggle('hidden', !visible);
}

function updateIntegrationSections() {
  const ttlockEnabled = intTtlockEl?.value === 'true';
  setSectionVisibility(ttlockSectionEl, ttlockEnabled);
  const chasterEnabled = intChasterEl?.value === 'true';
  setSectionVisibility(chasterSectionEl, chasterEnabled);
}

function setupAccordionEvents() {
  accordionDefs.forEach((definition) => {
    const btn = document.getElementById(definition.btn);
    if (!btn) return;
    btn.addEventListener('click', () => openAccordion(definition.key));
  });
  updateIntegrationSections();
  ensureChasterCode();
  updateChasterSaveVisibility();
  updateLlmDependentUi();
  openAccordion('base');
}

function openNextAfterBaseSave() {
  openAccordion('llm');
}

function openNextAfterPsychogramSave() {
  openAccordion('completion');
}

function openNextAfterLlmSave() {
  if (intTtlockEl?.value === 'true') {
    openAccordion('ttlock');
    return;
  }
  openAccordion('questionnaire');
}

function openNextAfterTtlockSave() {
  openAccordion('questionnaire');
}

function getIntegrations(ttlockCfgPresent, chasterCfgPresent) {
  const integrations = [];
  if (intTtlockEl?.value === 'true' && ttlockCfgPresent) integrations.push('ttlock');
  if (intChasterEl?.value === 'true' && chasterCfgPresent) integrations.push('chaster');
  return integrations;
}

function ttlockConfigFromForm() {
  const enabled = intTtlockEl?.value === 'true';
  if (!enabled) return null;

  const ttl_user = String(ttlockUserEl?.value || '').trim();
  const ttl_lock_id = String(ttlockLockEl?.value || '').trim();
  const ttl_gateway_id = String(ttlockGatewayEl?.value || '').trim();

  const config = {};
  const hasRequired = ttl_user && ttl_lock_id && ttlPassMd5Cached;
  if (!hasRequired) return null;
  config.ttl_user = ttl_user;
  config.ttl_pass_md5 = ttlPassMd5Cached;
  config.ttl_lock_id = ttl_lock_id;
  if (ttl_gateway_id) config.ttl_gateway_id = ttl_gateway_id;
  return config;
}

function chasterConfigFromForm() {
  const enabled = intChasterEl?.value === 'true';
  if (!enabled) return null;
  const api_token = String(chasterApiTokenEl?.value || '').trim();
  const cachedAuth = (chasterConfigCached && typeof chasterConfigCached === 'object') ? chasterConfigCached.auth : null;
  const hasOauth = Boolean(
    cachedAuth
    && String(cachedAuth.mode || '').toLowerCase() === 'oauth2'
    && (String(cachedAuth.access_token_enc || '').trim() || String(cachedAuth.refresh_token_enc || '').trim()),
  );
  const code = ensureChasterCode();
  const lock_id = String(chasterConfigCached?.lock_id || '').trim();
  const combination_id = String(chasterConfigCached?.combination_id || '').trim();
  if (!api_token && !hasOauth) return null;
  const { minMinutes, maxMinutes } = contractDurationsToChasterMinutes();
  const limit_lock_time = Boolean(chasterLimitLockTimeEl?.checked);
  const requestedMinLimit = Math.max(0, Number(chasterMinLimitDurationEl?.value || 0));
  const requestedMaxLimit = Math.max(0, Number(chasterMaxLimitDurationEl?.value || 0));
  const min_limit_duration_minutes = limit_lock_time ? Math.max(1, requestedMinLimit || minMinutes) : 0;
  const max_limit_duration_minutes = limit_lock_time
    ? Math.max(min_limit_duration_minutes, requestedMaxLimit || maxMinutes)
    : 0;
  const allow_session_offer = Boolean(chasterAllowSessionOfferEl?.checked);
  const is_test_lock = Boolean(chasterIsTestLockEl?.checked);
  const hide_time_logs = Boolean(chasterHideTimeLogsEl?.checked);
  const extensions = buildChasterExtensionsFromForm();
  return {
    schema_version: 2,
    api_base: String(chasterConfigCached?.api_base || 'https://api.chaster.app').trim(),
    api_token,
    auth: hasOauth ? { ...cachedAuth } : undefined,
    code,
    lock_id,
    combination_id,
    min_duration_minutes: minMinutes,
    max_duration_minutes: maxMinutes,
    display_remaining_time: true,
    min_limit_duration_minutes,
    max_limit_duration_minutes,
    limit_lock_time,
    allow_session_offer,
    is_test_lock,
    hide_time_logs,
    extensions,
    created_at: String(chasterConfigCached?.created_at || ''),
  };
}

function populateTtlockSelect(selectNode, items, valueKey, labelKey, selectedValue = '') {
  if (!selectNode) return;
  selectNode.innerHTML = '<option value="">-</option>';
  (items || []).forEach((item) => {
    const value = String(item[valueKey] || '').trim();
    if (!value) return;
    const label = String(item[labelKey] || value).trim();
    const option = document.createElement('option');
    option.value = value;
    option.textContent = `${label} (${value})`;
    if (selectedValue && selectedValue === value) option.selected = true;
    selectNode.appendChild(option);
  });
  updateTtlockSaveVisibility();
}

function renderQuestions(questions) {
  questionnaire = (Array.isArray(questions) ? questions : []).filter((q) => {
    const qid = q?.question_id || q?.id;
    return !BASE_MANAGED_QUESTION_IDS.has(String(qid || ''));
  });
  if (!questionsWrap) return;
  if (!questionnaire.length) {
    questionsWrap.innerHTML = '<p class="text-sm text-text-tertiary">Noch keine Fragen geladen. Bitte zuerst "Start setup" ausführen.</p>';
    return;
  }
  questionsWrap.innerHTML = '';

  questionnaire.forEach((question) => {
    const questionId = question.question_id || question.id;
    if (!questionId) return;

    const container = document.createElement('div');
    container.className = 'bg-surface border border-white/10 rounded p-3';

    const label = document.createElement('label');
    label.className = 'text-sm text-text-secondary block';
    label.textContent = question.text || questionId;
    label.setAttribute('for', `q-${questionId}`);
    container.appendChild(label);

    let input;
    if (question.type === 'scale_100') {
      input = document.createElement('input');
      input.type = 'range';
      input.min = String(question.scale_min ?? 1);
      input.max = String(question.scale_max ?? 100);
      input.value = String(question.default_value ?? 50);
      input.className = 'mt-2 w-full';

      const valueInfo = document.createElement('div');
      valueInfo.className = 'text-xs text-text-tertiary mt-1';
      valueInfo.textContent = `Wert: ${input.value}`;
      input.addEventListener('input', () => {
        valueInfo.textContent = `Wert: ${input.value}`;
      });
      container.appendChild(input);
      container.appendChild(valueInfo);
    } else if (question.type === 'choice') {
      input = document.createElement('select');
      input.className = 'mt-2 w-full rounded-md bg-surface-alt p-2 border border-white/10';
      (question.options || []).forEach((option) => {
        const opt = document.createElement('option');
        opt.value = option.value;
        opt.textContent = option.label || option.value;
        if (question.default_value && question.default_value === option.value) opt.selected = true;
        input.appendChild(opt);
      });
    } else {
      input = document.createElement('textarea');
      input.className = 'mt-2 w-full rounded-md bg-surface-alt p-2 border border-white/10 min-h-20';
      input.value = question.default_value || '';
      if (question.read_only) {
        input.readOnly = true;
        input.classList.add('opacity-80');
      }
    }

    input.id = `q-${questionId}`;
    input.dataset.questionId = questionId;
    input.dataset.questionType = question.type;
    container.appendChild(input);
    questionsWrap.appendChild(container);
  });
}

function collectAnswers() {
  const answers = [];
  questionnaire.forEach((question) => {
    const questionId = question.question_id || question.id;
    if (!questionId) return;
    const node = document.getElementById(`q-${questionId}`);
    if (!node) return;
    let value = '';
    if (question.type === 'scale_100') value = Number(node.value);
    else value = String(node.value || '').trim();
    if (value === '' || value === null || Number.isNaN(value)) return;
    answers.push({ question_id: questionId, value });
  });
  return answers;
}

async function apiCall(method, path, payload) {
  const response = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  const body = await safeJson(response);
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    if (Array.isArray(body?.detail)) {
      message = body.detail.map((entry) => {
        if (typeof entry === 'string') return entry;
        if (entry && typeof entry === 'object') {
          const loc = Array.isArray(entry.loc) ? entry.loc.join('.') : '';
          const msg = String(entry.msg || JSON.stringify(entry));
          return loc ? `${loc}: ${msg}` : msg;
        }
        return String(entry);
      }).join(' | ');
    } else if (body?.detail && typeof body.detail === 'object') {
      message = JSON.stringify(body.detail);
    } else if (body?.detail) {
      message = String(body.detail);
    }
    throw new Error(message);
  }
  return body;
}

async function checkActiveChasterSession(apiToken, lockId = '') {
  const token = String(apiToken || '').trim();
  if (!auth) return null;
  try {
    return await apiCall('POST', '/api/v1/setup/chaster/check-active-session', {
      user_id: auth.user_id,
      auth_token: auth.auth_token,
      chaster_api_token: token || null,
      lock_id: String(lockId || '').trim() || null,
    });
  } catch (_error) {
    return null;
  }
}

function applySetupToForm(data) {
  if (!data) return;
  currentSetup = data;
  if (data.language && languageEl) languageEl.value = data.language;
  if (autonomyEl && data.autonomy_mode) autonomyEl.value = data.autonomy_mode;
  if (hardStopEl) hardStopEl.value = parseBool(data.hard_stop_enabled, true) ? 'true' : 'false';
  if (sealModeEl && data.seal_mode) sealModeEl.value = data.seal_mode;
  if (initialSealNumberEl && data.initial_seal_number) initialSealNumberEl.value = data.initial_seal_number;
  if (initialSealNumberWrapEl) {
    const showInitialSealNumber = data.seal_mode && data.seal_mode !== 'none';
    initialSealNumberWrapEl.classList.toggle('hidden', !showInitialSealNumber);
  }
  if (openingLimitPeriodEl && data.opening_limit_period) openingLimitPeriodEl.value = data.opening_limit_period;
  if (maxOpeningsInPeriodEl && Number.isFinite(Number(data.max_openings_in_period))) {
    maxOpeningsInPeriodEl.value = String(data.max_openings_in_period);
  }
  if (openingWindowMinutesEl && Number.isFinite(Number(data.opening_window_minutes))) {
    openingWindowMinutesEl.value = String(data.opening_window_minutes);
  }
  if (instructionStyleEl && data.instruction_style) instructionStyleEl.value = data.instruction_style;
  if (desiredIntensityEl && data.desired_intensity) desiredIntensityEl.value = data.desired_intensity;
  if (groomingPreferenceEl && data.grooming_preference) groomingPreferenceEl.value = data.grooming_preference;
  if (contractStartDateEl) contractStartDateEl.value = data.contract_start_date || contractStartDateEl.value || '';
  if (contractMinEndDateEl) contractMinEndDateEl.value = data.contract_min_end_date || '';
  if (contractMaxEndDateEl) contractMaxEndDateEl.value = data.contract_max_end_date || '';
  if (contractMinDurationDaysEl && data.contract_start_date && data.contract_min_end_date) {
    const minDays = daysBetween(data.contract_start_date, data.contract_min_end_date);
    if (minDays !== null) contractMinDurationDaysEl.value = String(minDays);
  }
  if (contractMaxDurationDaysEl && data.contract_start_date) {
    if (!data.contract_max_end_date) {
      contractMaxDurationDaysEl.value = '0';
    } else {
      const maxDays = daysBetween(data.contract_start_date, data.contract_max_end_date);
      if (maxDays !== null) contractMaxDurationDaysEl.value = String(maxDays);
    }
  }
  if (maxPenaltyPerDayMinutesEl && Number.isFinite(Number(data.max_penalty_per_day_minutes))) {
    maxPenaltyPerDayMinutesEl.value = String(data.max_penalty_per_day_minutes);
  }
  if (maxPenaltyPerWeekMinutesEl && Number.isFinite(Number(data.max_penalty_per_week_minutes))) {
    maxPenaltyPerWeekMinutesEl.value = String(data.max_penalty_per_week_minutes);
  }

  const integrations = Array.isArray(data.integrations) ? data.integrations.map((x) => String(x).toLowerCase()) : [];
  const hasExplicitIntegrations = Array.isArray(data.integrations) && data.integrations.length > 0;
  const ttlockEnabled = integrations.includes('ttlock') || Boolean(data.integration_config?.ttlock) || !hasExplicitIntegrations;
  if (intTtlockEl) intTtlockEl.value = ttlockEnabled ? 'true' : 'false';
  if (intChasterEl) intChasterEl.value = integrations.includes('chaster') ? 'true' : 'false';

  const ttlockCfg = data.integration_config?.ttlock || {};
  if (ttlockUserEl && ttlockCfg.ttl_user) ttlockUserEl.value = String(ttlockCfg.ttl_user);
  if (ttlockCfg.ttl_pass_md5) ttlPassMd5Cached = String(ttlockCfg.ttl_pass_md5);
  if (ttlockCfg.ttl_gateway_id && ttlockGatewayEl) {
    populateTtlockSelect(ttlockGatewayEl, [{ gatewayId: ttlockCfg.ttl_gateway_id, gatewayName: ttlockCfg.ttl_gateway_id }], 'gatewayId', 'gatewayName', String(ttlockCfg.ttl_gateway_id));
  }
  if (ttlockCfg.ttl_lock_id && ttlockLockEl) {
    populateTtlockSelect(ttlockLockEl, [{ lockId: ttlockCfg.ttl_lock_id, lockAlias: ttlockCfg.ttl_lock_id }], 'lockId', 'lockAlias', String(ttlockCfg.ttl_lock_id));
  }
  const chasterCfg = data.integration_config?.chaster || {};
  chasterConfigCached = Object.keys(chasterCfg).length ? { ...chasterCfg } : null;
  if (chasterApiTokenEl && chasterCfg.api_token) chasterApiTokenEl.value = String(chasterCfg.api_token);
  const oauthConnected = Boolean(
    chasterCfg?.auth
    && String(chasterCfg.auth.mode || '').toLowerCase() === 'oauth2'
    && (String(chasterCfg.auth.access_token_enc || '').trim() || String(chasterCfg.auth.refresh_token_enc || '').trim()),
  );
  updateChasterOauthManagedUi(oauthConnected);
  setChasterOauthStatus(
    oauthConnected
      ? `OAuth verbunden${chasterCfg?.auth?.expires_at ? ` (Ablauf: ${String(chasterCfg.auth.expires_at)})` : ''}`
      : 'OAuth: nicht verbunden',
    false,
  );
  if (chasterCodeEl) {
    if (chasterCfg.code) chasterCodeEl.value = String(chasterCfg.code);
    else ensureChasterCode();
  }
  if (chasterMinLimitDurationEl && Number.isFinite(Number(chasterCfg.min_limit_duration_minutes))) {
    chasterMinLimitDurationEl.value = String(chasterCfg.min_limit_duration_minutes);
  }
  if (chasterMaxLimitDurationEl && Number.isFinite(Number(chasterCfg.max_limit_duration_minutes))) {
    chasterMaxLimitDurationEl.value = String(chasterCfg.max_limit_duration_minutes);
  }
  if (chasterLimitLockTimeEl) chasterLimitLockTimeEl.checked = parseBool(chasterCfg.limit_lock_time, true);
  if (chasterAllowSessionOfferEl) chasterAllowSessionOfferEl.checked = parseBool(chasterCfg.allow_session_offer, true);
  if (chasterIsTestLockEl) chasterIsTestLockEl.checked = parseBool(chasterCfg.is_test_lock, false);
  if (chasterHideTimeLogsEl) chasterHideTimeLogsEl.checked = parseBool(chasterCfg.hide_time_logs, true);
  const savedExtensions = Array.isArray(chasterCfg.extensions) ? chasterCfg.extensions : [];
  const savedVerification = savedExtensions.find((entry) => String(entry?.slug || '').trim().length > 0
    && String(entry.slug).toLowerCase().includes('verification'));
  const savedHygiene = savedExtensions.find((entry) => {
    const slug = String(entry?.slug || '').trim().toLowerCase();
    return slug === 'temporary-opening' || slug === 'hygiene-opening' || slug.includes('hygiene');
  });
  if (chasterEnableVerificationPictureEl) chasterEnableVerificationPictureEl.checked = Boolean(savedVerification) || savedExtensions.length === 0;
  if (chasterEnableHygieneOpeningEl) chasterEnableHygieneOpeningEl.checked = Boolean(savedHygiene) || savedExtensions.length === 0;
  syncChasterSessionManagedFields(chasterCfg);
  syncChasterDurationsFromBase();
  if (chasterConfigCached?.lock_id) {
    setChasterInfo(`Chaster Session vorhanden (lock_id=${String(chasterConfigCached.lock_id)}).`);
  } else if (chasterConfigCached?.api_token || oauthConnected) {
    setChasterInfo('Chaster-Konfiguration gespeichert. Session wird bei Vertragsakzeptanz erstellt.');
  } else {
    setChasterInfo('');
  }
  updateIntegrationSections();
  updateTtlockSaveVisibility();
  updateChasterSaveVisibility();
  updateLlmDependentUi();
  syncFinalizedSetupUi();
}

async function loadSetupSession() {
  if (!setupSessionId) return;
  try {
    const body = await apiCall('GET', `/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}`);
    applySetupToForm(body);
    setStatus(`Setup geladen (${body.status || 'unknown'})`);
    if (instructionsEl) instructionsEl.textContent = `Setup-Session: ${setupSessionId}`;

    const language = body.language || languageEl?.value || 'de';
    const q = await apiCall('GET', `/api/v1/setup/questionnaire?language=${encodeURIComponent(language)}`);
    renderQuestions(q.questions || []);

    setOutput(body);
  } catch (error) {
    setStatus(String(error?.message || error), true);
    setOutput({ error: String(error?.message || error) });
  }
}

async function startSetup() {
  if (!auth) return;

  const selectedTtlockEnabled = intTtlockEl?.value === 'true';
  const selectedChasterEnabled = intChasterEl?.value === 'true';

  const ttCfg = ttlockConfigFromForm();
  let chCfg = null;
  try {
    chCfg = chasterConfigFromForm();
  } catch (error) {
    setChasterInfo(String(error?.message || error), true);
    setStatus(String(error?.message || error), true);
    return;
  }
  const integrations = getIntegrations(Boolean(ttCfg), Boolean(chCfg));
  const integration_config = {};
  if (ttCfg) integration_config.ttlock = ttCfg;
  if (chCfg) integration_config.chaster = chCfg;

  const instructionStyle = String(instructionStyleEl?.value || '').trim();
  const desiredIntensity = String(desiredIntensityEl?.value || '').trim();
  const groomingPreference = String(groomingPreferenceEl?.value || '').trim();
  if (!instructionStyle || !desiredIntensity || !groomingPreference) {
    setStatus('Bitte alle Pflichtfelder in der Basis-Konfiguration ausfüllen.', true);
    return;
  }

  const payload = {
    user_id: auth.user_id,
    auth_token: auth.auth_token,
    language: languageEl?.value || 'de',
    autonomy_mode: autonomyEl?.value || 'suggest',
    hard_stop_enabled: hardStopEl?.value === 'true',
    seal_mode: sealModeEl?.value || 'none',
    initial_seal_number: (initialSealNumberEl?.value || '').trim() || null,
    integrations,
    integration_config,
    ...getContractPayloadValues(),
    ai_controls_end_date: true,
    max_penalty_per_day_minutes: Math.max(0, Number(maxPenaltyPerDayMinutesEl?.value || 0)),
    max_penalty_per_week_minutes: Math.max(0, Number(maxPenaltyPerWeekMinutesEl?.value || 0)),
    opening_limit_period: openingLimitPeriodEl?.value || 'month',
    max_openings_in_period: Number(maxOpeningsInPeriodEl?.value || 7),
    opening_window_minutes: Number(openingWindowMinutesEl?.value || 15),
    instruction_style: instructionStyle,
    desired_intensity: desiredIntensity,
    grooming_preference: groomingPreference,
  };

  try {
    setStatus('Setup wird gestartet...');
    const body = await apiCall('POST', '/api/v1/setup/sessions', payload);
    setupSessionId = body.setup_session_id;
    updateSetupIdInUrl(setupSessionId);
    applySetupToForm(body);
    if (intTtlockEl) intTtlockEl.value = selectedTtlockEnabled ? 'true' : 'false';
    if (intChasterEl) intChasterEl.value = selectedChasterEnabled ? 'true' : 'false';
    updateIntegrationSections();
    renderQuestions(body.questions || []);
    setStatus(`Setup aktiv: ${setupSessionId}`);
    if (instructionsEl) instructionsEl.textContent = `Setup-Session: ${setupSessionId}`;
    setOutput(body);
    openNextAfterBaseSave();
  } catch (error) {
    setStatus(String(error?.message || error), true);
    setOutput({ error: String(error?.message || error) });
  }
}

async function submitAnswers() {
  if (!requireLlmReady('Psychogramm-Speichern')) return;
  if (!setupSessionId) {
    setStatus('Bitte zuerst Setup starten.', true);
    return;
  }
  const answers = collectAnswers();
  if (!answers.length) {
    setStatus('Keine Antworten vorhanden.', true);
    return;
  }
  try {
    setStatus('Antworten werden gespeichert...');
    const body = await apiCall('POST', `/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}/answers`, { answers });
    setStatus(`Antworten gespeichert (${body.answered_questions}/${body.total_questions})`);
    openNextAfterPsychogramSave();
  } catch (error) {
    setStatus(String(error?.message || error), true);
    setOutput({ error: String(error?.message || error) });
  }
}

async function completeSetup() {
  if (!requireLlmReady('Setup-Abschluss')) return;
  if (!setupSessionId) {
    setStatus('Bitte zuerst Setup starten.', true);
    return;
  }
  if (!auth) {
    setStatus('Login fehlt.', true);
    return;
  }
  try {
    setStatus('Setup wird abgeschlossen und Psychogramm finalisiert...');
    const completeBody = await apiCall('POST', `/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}/complete`);

    setStatus('Psychogramm liegt vor. Vertrag wird generiert...');
    const contractBody = await apiCall('POST', `/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}/contract`, {
      user_id: auth.user_id,
      auth_token: auth.auth_token,
      force: false,
    });

    currentSetup = {
      ...(currentSetup || {}),
      status: completeBody?.status || 'configured',
      psychogram_analysis: completeBody?.psychogram_analysis || currentSetup?.psychogram_analysis,
      psychogram_analysis_status: completeBody?.psychogram_analysis_status || currentSetup?.psychogram_analysis_status,
      policy_preview: {
        ...((currentSetup && currentSetup.policy_preview) || {}),
        generated_contract: {
          ...((((currentSetup && currentSetup.policy_preview) || {}).generated_contract || {})),
          text: contractBody?.contract_text,
          generated_at: contractBody?.contract_generated_at,
          consent: contractBody?.consent,
        },
      },
    };
    syncFinalizedSetupUi();

    setStatus('Setup abgeschlossen. Vertrag erstellt. Weiterleitung zur Vertragsseite...');
    setOutput({ complete: completeBody, contract: contractBody });
    setTimeout(() => {
      window.location.href = '/contract';
    }, 700);
  } catch (error) {
    setStatus(String(error?.message || error), true);
    setOutput({ error: String(error?.message || error) });
  }
}

function showCompleteSetupConfirmation() {
  if (!completeSetupConfirmWrap) return;
  completeSetupConfirmWrap.classList.remove('hidden');
}

async function generateArtifacts() {
  if (!requireLlmReady('Artefakt-Generierung')) return;
  if (!setupSessionId || !auth) {
    setStatus('Setup oder Login fehlt.', true);
    return;
  }
  try {
    setStatus('Artefakte werden generiert...');
    const body = await apiCall('POST', `/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}/artifacts`, {
      user_id: auth.user_id,
      auth_token: auth.auth_token,
      force: false,
    });
    setStatus('Analyse + Vertrag generiert.');
    setOutput(body);
  } catch (error) {
    setStatus(String(error?.message || error), true);
    setOutput({ error: String(error?.message || error) });
  }
}

async function acceptConsent() {
  if (!setupSessionId || !auth) {
    setStatus('Setup oder Login fehlt.', true);
    return;
  }
  let consentText = String(consentEl?.value || '').trim();
  if (!consentText) {
    const fallback = currentSetup?.policy_preview?.generated_contract?.consent?.required_text;
    if (fallback) consentText = String(fallback).trim();
  }
  if (!consentText) {
    setStatus('Consent-Text fehlt. Bitte zuerst Vertrag generieren.', true);
    return;
  }
  try {
    if (intChasterEl?.value === 'true') {
      const currentLockId = String(
        ((currentSetup?.integration_config || {}).chaster || {}).lock_id || '',
      ).trim();
      if (!currentLockId) {
        setStatus('Consent: Erstelle zuerst Chaster Session...');
        await createChasterSessionAfterConsent(true);
      }
    }

    setStatus('Consent wird gespeichert...');
    const body = await apiCall('POST', `/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}/contract/accept`, {
      user_id: auth.user_id,
      auth_token: auth.auth_token,
      consent_text: consentText,
    });
    setStatus('Consent akzeptiert.');
    setOutput(body);
  } catch (error) {
    setStatus(String(error?.message || error), true);
    setOutput({ error: String(error?.message || error) });
  }
}

async function discoverTtlockDevices() {
  if (!auth) return;
  const ttl_user = String(ttlockUserEl?.value || '').trim();
  const ttl_pass = String(ttlockPasswordEl?.value || '').trim();
  if (!ttl_user) {
    setTtlockInfo('TTLock user ist erforderlich.', true);
    return;
  }
  if (!ttl_pass && !ttlPassMd5Cached) {
    setTtlockInfo('TTLock password ist erforderlich.', true);
    return;
  }

  try {
    setTtlockInfo('Suche Geräte...');
    const payload = {
      user_id: auth.user_id,
      auth_token: auth.auth_token,
      ttl_user,
    };
    if (ttl_pass) payload.ttl_pass = ttl_pass;
    else payload.ttl_pass_md5 = ttlPassMd5Cached;

    const body = await apiCall('POST', '/api/v1/setup/ttlock/discover', payload);
    ttlPassMd5Cached = String(body.ttl_pass_md5 || ttlPassMd5Cached || '');

    populateTtlockSelect(ttlockGatewayEl, body.gateways || [], 'gatewayId', 'gatewayName');
    populateTtlockSelect(ttlockLockEl, body.locks || [], 'lockId', 'lockAlias');

    setTtlockInfo(`${(body.locks || []).length} Locks, ${(body.gateways || []).length} Gateways gefunden.`);
    setOutput(body);
  } catch (error) {
    setTtlockInfo(String(error?.message || error), true);
    setOutput({ error: String(error?.message || error) });
  }
}

async function createChasterSessionAfterConsent(strict = false, forceCreate = false) {
  if (!auth) {
    if (strict) throw new Error('Login fehlt.');
    return null;
  }
  if (intChasterEl?.value !== 'true') {
    if (strict) throw new Error('Chaster-Integration ist nicht aktiviert.');
    return null;
  }
  let savedCfg = (currentSetup?.integration_config || {}).chaster || null;
  const hasSavedOauth = Boolean(
    savedCfg?.auth
    && String(savedCfg.auth.mode || '').toLowerCase() === 'oauth2'
    && (String(savedCfg.auth.access_token_enc || '').trim() || String(savedCfg.auth.refresh_token_enc || '').trim()),
  );
  if ((!savedCfg || (!String(savedCfg.api_token || '').trim() && !hasSavedOauth)) && intChasterEl?.value === 'true') {
    try {
      savedCfg = chasterConfigFromForm();
    } catch (_) {
      savedCfg = null;
    }
  }
  const hasCfgOauth = Boolean(
    savedCfg?.auth
    && String(savedCfg.auth.mode || '').toLowerCase() === 'oauth2'
    && (String(savedCfg.auth.access_token_enc || '').trim() || String(savedCfg.auth.refresh_token_enc || '').trim()),
  );
  if (!savedCfg || (!String(savedCfg.api_token || '').trim() && !hasCfgOauth)) {
    if (strict) throw new Error('Chaster Credentials fehlen (OAuth2 oder API Token).');
    return null;
  }
  if (String(savedCfg.lock_id || '').trim() && !forceCreate) return { already_exists: true, config: savedCfg };

  const { minMinutes, maxMinutes } = contractDurationsToChasterMinutes();
  const savedLimitLockTime = Boolean(savedCfg.limit_lock_time);
  const savedMinLimit = Math.max(0, Number(savedCfg.min_limit_duration_minutes || 0));
  const savedMaxLimit = Math.max(0, Number(savedCfg.max_limit_duration_minutes || 0));
  const effectiveMinLimit = savedLimitLockTime ? Math.max(1, savedMinLimit || minMinutes) : 0;
  const effectiveMaxLimit = savedLimitLockTime ? Math.max(effectiveMinLimit, savedMaxLimit || maxMinutes) : 0;
  const configuredLimitLockTime = Boolean(savedCfg.limit_lock_time);
  const configuredIsTestLock = Boolean(savedCfg.is_test_lock);
  const createPayload = {
    user_id: auth.user_id,
    auth_token: auth.auth_token,
    chaster_api_token: String(savedCfg.api_token || '').trim() || null,
    code: String(savedCfg.code || ensureChasterCode()).trim(),
    min_duration_minutes: minMinutes,
    max_duration_minutes: maxMinutes,
    display_remaining_time: true,
    min_limit_duration_minutes: effectiveMinLimit,
    max_limit_duration_minutes: effectiveMaxLimit,
    limit_lock_time: configuredLimitLockTime,
    allow_session_offer: Boolean(savedCfg.allow_session_offer),
    is_test_lock: configuredIsTestLock,
    hide_time_logs: Boolean(savedCfg.hide_time_logs),
    extensions: Array.isArray(savedCfg.extensions) ? savedCfg.extensions : [],
  };
  const created = await apiCall('POST', '/api/v1/setup/chaster/create-session', createPayload);
  const createdChaster = (created?.integration_config || {}).chaster || {};
  const mergedConfig = {
    ...((currentSetup?.integration_config) || {}),
    chaster: {
      ...savedCfg,
      ...createdChaster,
    },
  };
  const integrations = Array.from(
    new Set([
      ...((currentSetup?.integrations || []).map((x) => String(x).toLowerCase())),
      'chaster',
    ]),
  );
  let targetPath = null;
  const helper = typeof chastease_session !== 'undefined' ? chastease_session : null;
  let active = null;
  if (helper && typeof helper.fetchActiveSession === 'function') {
    active = await helper.fetchActiveSession(statusEl);
  } else {
    active = await apiCall(
      'GET',
      `/api/v1/sessions/active?user_id=${encodeURIComponent(auth.user_id)}&auth_token=${encodeURIComponent(auth.auth_token)}`,
    );
  }
  if (active?.has_active_session && active?.chastity_session?.session_id) {
    targetPath = `/api/v1/sessions/${encodeURIComponent(active.chastity_session.session_id)}/integrations`;
  } else if (setupSessionId) {
    targetPath = `/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}/integrations`;
  } else {
    throw new Error('Keine aktive Session oder Setup-Session gefunden.');
  }

  const saved = await apiCall('POST', targetPath, {
    user_id: auth.user_id,
    auth_token: auth.auth_token,
    integrations,
    integration_config: mergedConfig,
  });
  currentSetup = {
    ...(currentSetup || {}),
    integrations: saved.integrations || integrations,
    integration_config: saved.integration_config || mergedConfig,
  };
  chasterConfigCached = (currentSetup.integration_config || {}).chaster || null;
  if (chasterConfigCached?.lock_id) {
    setChasterInfo(`Chaster Session erstellt (lock_id=${String(chasterConfigCached.lock_id)}).`);
  }
  return saved;
}

async function saveChasterConfig() {
  if (!auth) {
    setStatus('Login fehlt.', true);
    return;
  }
  if (!isChasterStepUnlocked()) {
    if (!llmConnectivityVerified) {
      setStatus('Chaster ist gesperrt: zuerst LLM Live-Test durchführen.', true);
      openAccordion('llm');
    } else {
      setStatus('Chaster ist gesperrt: zuerst TTLock-Konfiguration speichern.', true);
      openAccordion('ttlock');
    }
    return;
  }

  const ttCfg = ttlockConfigFromForm();
  let chCfg = null;
  try {
    chCfg = chasterConfigFromForm();
  } catch (error) {
    setChasterInfo(String(error?.message || error), true);
    setStatus(String(error?.message || error), true);
    return;
  }
  const integrations = getIntegrations(Boolean(ttCfg), Boolean(chCfg));
  const integration_config = {};
  if (ttCfg) integration_config.ttlock = ttCfg;
  if (chCfg) integration_config.chaster = chCfg;

  if (intChasterEl?.value === 'true' && !chCfg) {
    setChasterInfo('Chaster-Konfiguration unvollständig: OAuth2-Verbindung oder API Token erforderlich.', true);
    setStatus('Chaster speichern fehlgeschlagen: Credentials fehlen.', true);
    return;
  }

  try {
    setChasterInfo('Speichere Chaster-Konfiguration...');
    let targetPath = null;
    const helper = typeof chastease_session !== 'undefined' ? chastease_session : null;
    let active = null;
    if (helper && typeof helper.fetchActiveSession === 'function') {
      active = await helper.fetchActiveSession(statusEl);
    } else {
      active = await apiCall(
        'GET',
        `/api/v1/sessions/active?user_id=${encodeURIComponent(auth.user_id)}&auth_token=${encodeURIComponent(auth.auth_token)}`,
      );
    }

    if (active?.has_active_session && active?.chastity_session?.session_id) {
      targetPath = `/api/v1/sessions/${encodeURIComponent(active.chastity_session.session_id)}/integrations`;
    } else if (setupSessionId) {
      targetPath = `/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}/integrations`;
    } else {
      setChasterInfo('Keine aktive Session oder Setup-Session gefunden.', true);
      return;
    }

    const body = await apiCall('POST', targetPath, {
      user_id: auth.user_id,
      auth_token: auth.auth_token,
      integrations,
      integration_config,
    });
    currentSetup = {
      ...(currentSetup || {}),
      integrations: body.integrations || integrations,
      integration_config: body.integration_config || integration_config,
    };
    chasterConfigCached = (currentSetup.integration_config || {}).chaster || chCfg || null;
    const savedApiToken = String(chasterConfigCached?.api_token || chCfg?.api_token || '').trim();
    const savedLockId = String(chasterConfigCached?.lock_id || '').trim();
    if (chasterConfigCached?.lock_id) {
      setChasterInfo(`Chaster-Konfiguration gespeichert (lock_id=${String(chasterConfigCached.lock_id)}).`);
    } else {
      setChasterInfo('Chaster-Konfiguration gespeichert. Session wird bei Vertragsakzeptanz erstellt.');
    }
    void (async () => {
      const chasterState = await checkActiveChasterSession(savedApiToken, savedLockId);
      if (!chasterState?.has_active_session) return;
      const activeLockId = String(chasterState.lock_id || savedLockId || '').trim();
      setChasterInfo(
        activeLockId
          ? `Warnung: Chaster Session läuft aktuell (lock_id=${activeLockId}).`
          : 'Warnung: Chaster Session läuft aktuell.',
        true,
      );
    })();
    setStatus('Chaster-Konfiguration gespeichert.');
    updateLlmDependentUi();
    setOutput(body);
    openAccordion('questionnaire');
  } catch (error) {
    setChasterInfo(String(error?.message || error), true);
    setOutput({ error: String(error?.message || error) });
  }
}

async function createChasterSessionNow() {
  try {
    await saveChasterConfig();
    const created = await createChasterSessionAfterConsent(true, true);
    const lockId = String((created?.integration_config || {}).chaster?.lock_id || '').trim();
    if (!lockId) throw new Error('Chaster Session konnte nicht erstellt werden (keine lock_id erhalten).');
    setStatus('Chaster Session erstellt.');
  } catch (error) {
    const msg = String(error?.message || error);
    setChasterInfo(msg, true);
    setStatus(msg, true);
    setOutput({ error: msg });
  }
}

async function saveTtlockConfig() {
  if (!auth) {
    setStatus('Login fehlt.', true);
    return;
  }

  const ttCfg = ttlockConfigFromForm();
  let chCfg = null;
  try {
    chCfg = chasterConfigFromForm();
  } catch (error) {
    setChasterInfo(String(error?.message || error), true);
    setStatus(String(error?.message || error), true);
    return;
  }
  const integrations = getIntegrations(Boolean(ttCfg), Boolean(chCfg));
  const integration_config = {};
  if (ttCfg) integration_config.ttlock = ttCfg;
  if (chCfg) integration_config.chaster = chCfg;

  if (intTtlockEl?.value === 'true' && !ttCfg) {
    setTtlockInfo('TTLock-Konfiguration unvollständig: user, lock und Passwort/Hash erforderlich.', true);
    return;
  }

  try {
    setTtlockInfo('Speichere TTLock-Konfiguration...');
    let targetPath = null;
    const helper = typeof chastease_session !== 'undefined' ? chastease_session : null;
    let active = null;
    if (helper && typeof helper.fetchActiveSession === 'function') {
      active = await helper.fetchActiveSession(statusEl);
    } else {
      active = await apiCall(
        'GET',
        `/api/v1/sessions/active?user_id=${encodeURIComponent(auth.user_id)}&auth_token=${encodeURIComponent(auth.auth_token)}`,
      );
    }

    if (active?.has_active_session && active?.chastity_session?.session_id) {
      targetPath = `/api/v1/sessions/${encodeURIComponent(active.chastity_session.session_id)}/integrations`;
    } else if (setupSessionId) {
      targetPath = `/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}/integrations`;
    } else {
      setTtlockInfo('Keine aktive Session oder Setup-Session gefunden.', true);
      return;
    }

    const body = await apiCall('POST', targetPath, {
      user_id: auth.user_id,
      auth_token: auth.auth_token,
      integrations,
      integration_config,
    });
    currentSetup = {
      ...(currentSetup || {}),
      integrations: body.integrations || integrations,
      integration_config: body.integration_config || integration_config,
    };
    setTtlockInfo('TTLock-Konfiguration gespeichert.');
    setStatus('TTLock-Konfiguration gespeichert.');
    setOutput(body);
    updateLlmDependentUi();
    openNextAfterTtlockSave();
  } catch (error) {
    setTtlockInfo(String(error?.message || error), true);
    setOutput({ error: String(error?.message || error) });
  }
}

function buildLlmPayloadBase() {
  if (!auth) return null;
  return {
    user_id: auth.user_id,
    auth_token: auth.auth_token,
    provider_name: String(llmProviderEl?.value || 'custom').trim() || 'custom',
    api_url: String(llmApiUrlEl?.value || '').trim(),
    api_key: String(llmApiKeyEl?.value || '').trim() || null,
    chat_model: String(llmChatModelEl?.value || '').trim(),
    vision_model: String(llmVisionModelEl?.value || '').trim() || null,
    behavior_prompt: String(llmBehaviorEl?.value || ''),
    is_active: llmActiveEl?.value !== 'false',
  };
}

async function loadLlmProfile() {
  if (!auth) return;
  invalidateLlmLiveTest(true);
  try {
    setLlmInfo('Loading LLM profile...');
    const body = await apiCall('GET', `/api/v1/llm/profile?user_id=${encodeURIComponent(auth.user_id)}&auth_token=${encodeURIComponent(auth.auth_token)}`);
    if (!body.configured) {
      if (llmBehaviorEl && !llmBehaviorEl.value) llmBehaviorEl.value = defaultBehaviorPrompt;
      setLlmInfo('Noch kein LLM-Profil konfiguriert. Default-Vorgaben gesetzt.');
      updateLlmDependentUi();
      setOutput(body);
      return;
    }
    const p = body.profile || {};
    if (llmProviderEl) llmProviderEl.value = p.provider_name || 'custom';
    if (llmApiUrlEl) llmApiUrlEl.value = p.api_url || '';
    if (llmChatModelEl) llmChatModelEl.value = p.chat_model || '';
    if (llmVisionModelEl) llmVisionModelEl.value = p.vision_model || '';
    if (llmActiveEl) llmActiveEl.value = p.is_active ? 'true' : 'false';
    if (llmBehaviorEl) llmBehaviorEl.value = p.behavior_prompt || defaultBehaviorPrompt;
    if (llmApiKeyEl) llmApiKeyEl.value = '';
    llmConnectivityVerified = Boolean(p.is_active && p.has_api_key && p.api_url && p.chat_model);
    llmLiveTestPassed = llmConnectivityVerified;
    setLlmInfo(
      llmConnectivityVerified
        ? `LLM-Profil geladen (bereit, API-Key gespeichert: ${p.has_api_key ? 'ja' : 'nein'}).`
        : `LLM-Profil geladen (nicht bereit, API-Key gespeichert: ${p.has_api_key ? 'ja' : 'nein'}).`,
      !llmConnectivityVerified,
    );
    updateLlmDependentUi();
    setOutput(body);
  } catch (error) {
    setLlmInfo(String(error?.message || error), true);
    updateLlmDependentUi();
    setOutput({ error: String(error?.message || error) });
  }
}

async function testLlmProfile() {
  const payload = buildLlmPayloadBase();
  if (!payload) return;
  try {
    setLlmTestRunning(true);
    setLlmInfo('Live test läuft...');
    const body = await apiCall('POST', '/api/v1/llm/test', { ...payload, dry_run: false });
    setLlmInfo('Live test erfolgreich. Speichern aktiviert.');
    setOutput(body);
    llmLiveTestPassed = true;
    llmConnectivityVerified = true;
    updateLlmDependentUi();
    setSaveLlmEnabled(true);
  } catch (error) {
    invalidateLlmLiveTest();
    setLlmInfo(String(error?.message || error), true);
    setOutput({ error: String(error?.message || error) });
  } finally {
    setLlmTestRunning(false);
  }
}

async function saveLlmProfile() {
  const payload = buildLlmPayloadBase();
  if (!payload) return;
  if (!llmLiveTestPassed) {
    setLlmInfo('Live-Test erforderlich, bevor gespeichert werden kann.', true);
    return;
  }
  try {
    setLlmInfo('Speichere LLM-Profil...');
    const body = await apiCall('POST', '/api/v1/llm/profile', payload);
    setLlmInfo('LLM-Profil gespeichert.');
    llmConnectivityVerified = true;
    updateLlmDependentUi();
    if (llmApiKeyEl) llmApiKeyEl.value = '';
    setOutput(body);
    openNextAfterLlmSave();
  } catch (error) {
    setLlmInfo(String(error?.message || error), true);
    setOutput({ error: String(error?.message || error) });
  }
}

async function bootstrap() {
  try {
    if (typeof chastease_common !== 'undefined' && typeof chastease_common.renderNavAuth === 'function') {
      chastease_common.renderNavAuth();
    }
  } catch (e) {}

  const helper = typeof chastease_session !== 'undefined' ? chastease_session : null;
  setupAccordionEvents();
  setContractDefaults();
  if (llmBehaviorEl && !llmBehaviorEl.value) llmBehaviorEl.value = defaultBehaviorPrompt;
  auth = helper?.getStoredAuth ? helper.getStoredAuth() : null;
  if (!auth) {
    window.location.href = '/app?mode=login';
    return;
  }

  setupSessionId = setupIdFromUrl();
  const params = new URLSearchParams(window.location.search);
  if (params.get('chaster_oauth') === 'ok') {
    setChasterOauthStatus('OAuth erfolgreich verbunden.');
    setStatus('Chaster OAuth erfolgreich verbunden.');
  } else if (params.get('chaster_oauth') === 'error') {
    setChasterOauthStatus(`OAuth Fehler: ${params.get('message') || 'unknown'}`, true);
  }
  if (setupSessionId) {
    if (instructionsEl) instructionsEl.textContent = `Setup-Session: ${setupSessionId}`;
    await loadSetupSession();
    await loadLlmProfile();
    return;
  }

  const active = await helper?.fetchActiveSession?.(statusEl);
  if (active?.setup_session_id) {
    setupSessionId = active.setup_session_id;
    updateSetupIdInUrl(setupSessionId);
    if (instructionsEl) instructionsEl.textContent = `Setup-Session: ${setupSessionId}`;
    await loadSetupSession();
    await loadLlmProfile();
    if (active.setup_status === 'draft') await startSetup();
    return;
  }

  await startSetup();
  await loadLlmProfile();
}

function connectChasterOauth() {
  if (!auth) {
    setStatus('Login fehlt.', true);
    return;
  }
  const params = new URLSearchParams({
    user_id: String(auth.user_id || ''),
    auth_token: String(auth.auth_token || ''),
    return_to: '/setup',
  });
  window.location.href = `/api/v1/auth/chaster/login?${params.toString()}`;
}

startBtn?.addEventListener('click', startSetup);
submitAnswersBtn?.addEventListener('click', submitAnswers);
completeSetupBtn?.addEventListener('click', showCompleteSetupConfirmation);
confirmCompleteSetupBtn?.addEventListener('click', completeSetup);
artifactsBtn?.addEventListener('click', generateArtifacts);
acceptConsentBtn?.addEventListener('click', acceptConsent);
ttlockDiscoverBtn?.addEventListener('click', discoverTtlockDevices);
ttlockLockEl?.addEventListener('change', updateTtlockSaveVisibility);
saveChasterBtn?.addEventListener('click', saveChasterConfig);
if (createChasterSessionBtn) createChasterSessionBtn.classList.add('hidden');
chasterOauthConnectBtnEl?.addEventListener('click', connectChasterOauth);
chasterApiTokenEl?.addEventListener('input', updateChasterSaveVisibility);
chasterCodeEl?.addEventListener('input', updateChasterSaveVisibility);
chasterMinLimitDurationEl?.addEventListener('input', updateChasterSaveVisibility);
chasterMaxLimitDurationEl?.addEventListener('input', updateChasterSaveVisibility);
chasterLimitLockTimeEl?.addEventListener('change', updateChasterSaveVisibility);
chasterAllowSessionOfferEl?.addEventListener('change', updateChasterSaveVisibility);
chasterIsTestLockEl?.addEventListener('change', updateChasterSaveVisibility);
chasterHideTimeLogsEl?.addEventListener('change', updateChasterSaveVisibility);
chasterEnableVerificationPictureEl?.addEventListener('change', updateChasterSaveVisibility);
chasterEnableHygieneOpeningEl?.addEventListener('change', updateChasterSaveVisibility);
contractStartDateEl?.addEventListener('change', () => {
  syncMinEndDateFromDuration();
  syncMaxEndDateFromDuration();
});
contractMinEndDateEl?.addEventListener('change', syncDurationFromMinEndDate);
contractMaxEndDateEl?.addEventListener('change', syncDurationFromMaxEndDate);
contractMaxDurationDaysEl?.addEventListener('input', syncMaxEndDateFromDuration);
contractMinDurationDaysEl?.addEventListener('input', syncMinDurationGuard);
saveTtlockBtn?.addEventListener('click', saveTtlockConfig);
intTtlockEl?.addEventListener('change', () => {
  updateIntegrationSections();
  updateLlmDependentUi();
});
intChasterEl?.addEventListener('change', () => {
  updateIntegrationSections();
  updateChasterSaveVisibility();
  updateLlmDependentUi();
});

sealModeEl?.addEventListener('change', () => {
  const sealMode = sealModeEl?.value;
  const showInitialSealNumber = sealMode !== 'none';
  if (initialSealNumberWrapEl) {
    initialSealNumberWrapEl.classList.toggle('hidden', !showInitialSealNumber);
  }
});

const llmFields = [
  llmProviderEl,
  llmApiUrlEl,
  llmApiKeyEl,
  llmChatModelEl,
  llmVisionModelEl,
  llmBehaviorEl,
  llmActiveEl,
].filter(Boolean);
llmFields.forEach((field) => {
  field.addEventListener('input', () => invalidateLlmLiveTest(true));
  field.addEventListener('change', () => invalidateLlmLiveTest(true));
});

liveTestLlmBtn?.addEventListener('click', testLlmProfile);
saveLlmProfileBtn?.addEventListener('click', saveLlmProfile);

document.addEventListener('DOMContentLoaded', bootstrap);
