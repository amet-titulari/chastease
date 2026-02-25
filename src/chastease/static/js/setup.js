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

const accordionDefs = [
  { key: 'base', btn: 'accBaseBtn', body: 'accBaseBody', chevron: 'accBaseChevron' },
  { key: 'questionnaire', btn: 'accQuestionBtn', body: 'accQuestionBody', chevron: 'accQuestionChevron' },
  { key: 'llm', btn: 'accLlmBtn', body: 'accLlmBody', chevron: 'accLlmChevron' },
  { key: 'ttlock', btn: 'accTtlockBtn', body: 'accTtlockBody', chevron: 'accTtlockChevron' },
  { key: 'chaster', btn: 'accChasterBtn', body: 'accChasterBody', chevron: 'accChasterChevron' },
  { key: 'completion', btn: 'accCompletionBtn', body: 'accCompletionBody', chevron: 'accCompletionChevron' },
  { key: 'artifacts', btn: 'accArtifactsBtn', body: 'accArtifactsBody', chevron: 'accArtifactsChevron' },
];

const languageEl = document.getElementById('setupLanguage');
const autonomyEl = document.getElementById('setupAutonomy');
const hardStopEl = document.getElementById('setupHardStop');
const intTtlockEl = document.getElementById('setupIntTtlock');
const intChasterEl = document.getElementById('setupIntChaster');
const contractStartDateEl = document.getElementById('contractStartDate');
const contractMinDurationDaysEl = document.getElementById('contractMinDurationDays');
const contractMaxEndDateEl = document.getElementById('contractMaxEndDate');
const contractMaxDurationDaysEl = document.getElementById('contractMaxDurationDays');
const openingLimitPeriodEl = document.getElementById('openingLimitPeriod');
const maxOpeningsInPeriodEl = document.getElementById('maxOpeningsInPeriod');
const openingWindowMinutesEl = document.getElementById('openingWindowMinutes');
const consentEl = document.getElementById('consentText');

const ttlockUserEl = document.getElementById('ttlockUser');
const ttlockPasswordEl = document.getElementById('ttlockPassword');
const ttlockGatewayEl = document.getElementById('ttlockGatewayId');
const ttlockLockEl = document.getElementById('ttlockLockId');
const ttlockDiscoverBtn = document.getElementById('ttlockDiscoverBtn');
const ttlockInfoEl = document.getElementById('ttlockDiscoverInfo');

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
let llmLiveTestPassed = false;

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

function invalidateLlmLiveTest(silent = false) {
  llmLiveTestPassed = false;
  setSaveLlmEnabled(false);
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

function syncMinDurationGuard() {
  if (!contractMinDurationDaysEl || !contractMaxDurationDaysEl) return;
  const minDuration = Math.max(0, Number(contractMinDurationDaysEl.value || 0));
  const maxDuration = Math.max(0, Number(contractMaxDurationDaysEl.value || 0));
  if (maxDuration > 0 && minDuration > maxDuration) {
    contractMinDurationDaysEl.value = String(maxDuration);
    return;
  }
  contractMinDurationDaysEl.value = String(minDuration);
}

function syncDurationFromMaxEndDate() {
  if (!contractStartDateEl || !contractMaxEndDateEl || !contractMaxDurationDaysEl) return;
  const diffDays = daysBetween(contractStartDateEl.value, contractMaxEndDateEl.value);
  contractMaxDurationDaysEl.value = diffDays === null ? '0' : String(diffDays);
  syncMinDurationGuard();
}

function syncMaxEndDateFromDuration() {
  if (!contractStartDateEl || !contractMaxEndDateEl || !contractMaxDurationDaysEl) return;
  const duration = Math.max(0, Number(contractMaxDurationDaysEl.value || 0));
  if (duration === 0) {
    contractMaxEndDateEl.value = '';
    syncMinDurationGuard();
    return;
  }
  const targetDate = dateByDuration(contractStartDateEl.value, duration);
  if (targetDate) contractMaxEndDateEl.value = targetDate;
  syncMinDurationGuard();
}

function setContractDefaults() {
  const now = new Date();
  if (contractStartDateEl && !contractStartDateEl.value) {
    contractStartDateEl.value = formatDateInputValue(now);
  }
  if (contractMinDurationDaysEl && !String(contractMinDurationDaysEl.value || '').trim()) {
    contractMinDurationDaysEl.value = '90';
  }
  if (contractMaxDurationDaysEl && !String(contractMaxDurationDaysEl.value || '').trim()) {
    contractMaxDurationDaysEl.value = '365';
  }
  if (contractMaxEndDateEl && !contractMaxEndDateEl.value && contractStartDateEl?.value) {
    const maxEnd = dateByDuration(contractStartDateEl.value, Number(contractMaxDurationDaysEl?.value || 365));
    if (maxEnd) contractMaxEndDateEl.value = maxEnd;
  }
  syncMinDurationGuard();
}

function getContractPayloadValues() {
  const contract_start_date = contractStartDateEl?.value || null;
  const minDuration = Math.max(0, Number(contractMinDurationDaysEl?.value || 0));
  const maxDuration = Math.max(0, Number(contractMaxDurationDaysEl?.value || 0));
  const contract_min_end_date = dateByDuration(contract_start_date, minDuration);
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

function openAccordion(targetKey) {
  accordionDefs.forEach((definition) => {
    const body = document.getElementById(definition.body);
    const chevron = document.getElementById(definition.chevron);
    const isActive = definition.key === targetKey;
    if (body) body.classList.toggle('hidden', !isActive);
    if (chevron) chevron.textContent = isActive ? '−' : '+';
  });
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
  openAccordion('base');
}

function openNextAfterBaseSave() {
  openAccordion('questionnaire');
}

function openNextAfterPsychogramSave() {
  openAccordion('llm');
}

function openNextAfterLlmSave() {
  if (intTtlockEl?.value === 'true') {
    openAccordion('ttlock');
    return;
  }
  if (intChasterEl?.value === 'true') {
    openAccordion('chaster');
    return;
  }
  openAccordion('completion');
}

function openNextAfterTtlockSave() {
  if (intChasterEl?.value === 'true') {
    openAccordion('chaster');
    return;
  }
  openAccordion('completion');
}

function getIntegrations(ttlockCfgPresent) {
  const integrations = [];
  if (intTtlockEl?.value === 'true' && ttlockCfgPresent) integrations.push('ttlock');
  if (intChasterEl?.value === 'true') integrations.push('chaster');
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
  questionnaire = Array.isArray(questions) ? questions : [];
  if (!questionsWrap) return;
  if (!questionnaire.length) {
    questionsWrap.innerHTML = '<p class="text-sm text-gray-400">Noch keine Fragen geladen. Bitte zuerst "Start setup" ausführen.</p>';
    return;
  }
  questionsWrap.innerHTML = '';

  questionnaire.forEach((question) => {
    const questionId = question.question_id || question.id;
    if (!questionId) return;

    const container = document.createElement('div');
    container.className = 'bg-gray-900 border border-gray-700 rounded p-3';

    const label = document.createElement('label');
    label.className = 'text-sm text-gray-300 block';
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
      valueInfo.className = 'text-xs text-gray-400 mt-1';
      valueInfo.textContent = `Wert: ${input.value}`;
      input.addEventListener('input', () => {
        valueInfo.textContent = `Wert: ${input.value}`;
      });
      container.appendChild(input);
      container.appendChild(valueInfo);
    } else if (question.type === 'choice') {
      input = document.createElement('select');
      input.className = 'mt-2 w-full rounded-md bg-gray-800 p-2 border border-gray-700';
      (question.options || []).forEach((option) => {
        const opt = document.createElement('option');
        opt.value = option.value;
        opt.textContent = option.label || option.value;
        if (question.default_value && question.default_value === option.value) opt.selected = true;
        input.appendChild(opt);
      });
    } else {
      input = document.createElement('textarea');
      input.className = 'mt-2 w-full rounded-md bg-gray-800 p-2 border border-gray-700 min-h-20';
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
    const message = body?.detail || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return body;
}

function applySetupToForm(data) {
  if (!data) return;
  currentSetup = data;
  if (data.language && languageEl) languageEl.value = data.language;
  if (autonomyEl && data.autonomy_mode) autonomyEl.value = data.autonomy_mode;
  if (hardStopEl) hardStopEl.value = parseBool(data.hard_stop_enabled, true) ? 'true' : 'false';
  if (openingLimitPeriodEl && data.opening_limit_period) openingLimitPeriodEl.value = data.opening_limit_period;
  if (maxOpeningsInPeriodEl && Number.isFinite(Number(data.max_openings_in_period))) {
    maxOpeningsInPeriodEl.value = String(data.max_openings_in_period);
  }
  if (openingWindowMinutesEl && Number.isFinite(Number(data.opening_window_minutes))) {
    openingWindowMinutesEl.value = String(data.opening_window_minutes);
  }
  if (contractStartDateEl) contractStartDateEl.value = data.contract_start_date || contractStartDateEl.value || '';
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
  updateIntegrationSections();
  updateTtlockSaveVisibility();
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
  const integrations = getIntegrations(Boolean(ttCfg));
  const integration_config = {};
  if (ttCfg) integration_config.ttlock = ttCfg;

  const payload = {
    user_id: auth.user_id,
    auth_token: auth.auth_token,
    language: languageEl?.value || 'de',
    autonomy_mode: autonomyEl?.value || 'suggest',
    hard_stop_enabled: hardStopEl?.value === 'true',
    integrations,
    integration_config,
    ...getContractPayloadValues(),
    ai_controls_end_date: true,
    opening_limit_period: openingLimitPeriodEl?.value || 'week',
    max_openings_in_period: Number(maxOpeningsInPeriodEl?.value || 2),
    opening_window_minutes: Number(openingWindowMinutesEl?.value || 15),
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

async function saveTtlockConfig() {
  if (!auth) {
    setStatus('Login fehlt.', true);
    return;
  }

  const ttCfg = ttlockConfigFromForm();
  const integrations = getIntegrations(Boolean(ttCfg));
  const integration_config = {};
  if (ttCfg) integration_config.ttlock = ttCfg;

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
    setLlmInfo(`LLM-Profil geladen (API-Key gespeichert: ${p.has_api_key ? 'ja' : 'nein'}).`);
    setOutput(body);
  } catch (error) {
    setLlmInfo(String(error?.message || error), true);
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

startBtn?.addEventListener('click', startSetup);
submitAnswersBtn?.addEventListener('click', submitAnswers);
completeSetupBtn?.addEventListener('click', showCompleteSetupConfirmation);
confirmCompleteSetupBtn?.addEventListener('click', completeSetup);
artifactsBtn?.addEventListener('click', generateArtifacts);
acceptConsentBtn?.addEventListener('click', acceptConsent);
ttlockDiscoverBtn?.addEventListener('click', discoverTtlockDevices);
ttlockLockEl?.addEventListener('change', updateTtlockSaveVisibility);
contractStartDateEl?.addEventListener('change', syncMaxEndDateFromDuration);
contractMaxEndDateEl?.addEventListener('change', syncDurationFromMaxEndDate);
contractMaxDurationDaysEl?.addEventListener('input', syncMaxEndDateFromDuration);
contractMinDurationDaysEl?.addEventListener('input', syncMinDurationGuard);
saveTtlockBtn?.addEventListener('click', saveTtlockConfig);

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
