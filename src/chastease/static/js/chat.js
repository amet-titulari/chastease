const statusEl = document.getElementById('chatStatus');
const sessionInfoEl = document.getElementById('chatSessionInfo');
const messagesEl = document.getElementById('messages');
const inputEl = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const attachImageBtn = document.getElementById('attachImageBtn');
const chatAttachmentInput = document.getElementById('chatAttachmentInput');
const attachmentPreviewEl = document.getElementById('attachmentPreview');
const pendingActionsWrapEl = document.getElementById('pendingActionsWrap');
const pendingActionsEl = document.getElementById('pendingActions');

let activeSessionId = null;
let currentLanguage = 'de';
let currentAutonomyMode = 'execute';
let pendingAttachments = [];
const MAX_RENDERED_HISTORY_TURNS = 12;
const AUTO_TIMER_ACTIONS = new Set(['add_time', 'reduce_time', 'pause_timer', 'unpause_timer']);
const HYGIENE_COUNTDOWN_STORAGE_PREFIX = 'chastease_hygiene_countdown:';
let hygieneCountdownInterval = null;
let hygieneSealRequiredOnClose = false;
let sessionSealRequiredOnClose = false;

function hygieneCountdownStorageKey() {
  if (!activeSessionId) return null;
  return `${HYGIENE_COUNTDOWN_STORAGE_PREFIX}${activeSessionId}`;
}

function persistHygieneCountdownState(endAtIso) {
  const key = hygieneCountdownStorageKey();
  if (!key) return;
  try {
    localStorage.setItem(key, JSON.stringify({ end_at: String(endAtIso || '') }));
  } catch (_error) {
    // Ignore storage errors; UI still works for current page lifetime.
  }
}

function readPersistedHygieneCountdownState() {
  const key = hygieneCountdownStorageKey();
  if (!key) return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const endAt = String(parsed?.end_at || '').trim();
    if (!endAt) return null;
    return { end_at: endAt };
  } catch (_error) {
    return null;
  }
}

function clearPersistedHygieneCountdownState() {
  const key = hygieneCountdownStorageKey();
  if (!key) return;
  try {
    localStorage.removeItem(key);
  } catch (_error) {
    // Ignore storage errors.
  }
}

function clearHygieneCountdownCard() {
  if (hygieneCountdownInterval) {
    window.clearInterval(hygieneCountdownInterval);
    hygieneCountdownInterval = null;
  }
  if (!messagesEl) return;
  const row = messagesEl.querySelector('[data-hygiene-countdown-row="true"]');
  if (row) row.remove();
}

function formatCountdown(secondsRaw) {
  const total = Math.max(0, Math.floor(Number(secondsRaw) || 0));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function showHygieneCountdownCard(resultBody) {
  if (!messagesEl) return;
  const payload = resultBody?.payload && typeof resultBody.payload === 'object' ? resultBody.payload : {};
  const ttlock = resultBody?.ttlock && typeof resultBody.ttlock === 'object' ? resultBody.ttlock : {};
  hygieneSealRequiredOnClose = Boolean(payload?.seal_required_on_close);
  const endAtText = String(payload.window_end_at || '').trim();
  const openingWindowSeconds = Number(payload.opening_window_seconds || 0);
  const endAtMs = endAtText ? new Date(endAtText).getTime() : (Date.now() + (openingWindowSeconds * 1000));
  if (!Number.isFinite(endAtMs) || endAtMs <= 0) return;

  if (String(ttlock.command || '').toLowerCase() === 'close') {
    clearPersistedHygieneCountdownState();
    clearHygieneCountdownCard();
    return;
  }

  clearHygieneCountdownCard();

  const messageWrapper = document.createElement('div');
  messageWrapper.className = 'flex items-start gap-3';
  messageWrapper.setAttribute('data-hygiene-countdown-row', 'true');

  const avatar = document.createElement('div');
  avatar.className = 'flex-none w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white text-sm font-bold';
  avatar.textContent = 'AI';

  const contentDiv = document.createElement('div');
  contentDiv.className = 'flex-1';

  const bubble = document.createElement('div');
  bubble.className = 'max-w-[90%] rounded-2xl bg-gray-800/80 text-gray-100 px-5 py-3 border border-cyan-600/50 shadow-lg';

  const card = document.createElement('div');
  card.className = 'rounded-lg border border-cyan-600/50 bg-gray-900/50 p-4';
  card.setAttribute('data-hygiene-countdown-card', 'true');

  const title = document.createElement('div');
  title.className = 'text-sm font-semibold text-cyan-300';
  title.textContent = 'Hygieneöffnung aktiv';

  const timer = document.createElement('div');
  timer.className = 'mt-2 text-lg font-mono text-gray-100';

  const hint = document.createElement('div');
  hint.className = 'mt-1 text-xs text-gray-400';
  hint.textContent = 'Maximale Dauer (Countdown)';

  const closeBtn = document.createElement('button');
  closeBtn.className = 'mt-3 px-3 py-1 text-xs rounded bg-blue-600 hover:bg-blue-500';
  closeBtn.textContent = 'Hygieneöffnung beenden';

  const renderTick = () => {
    const remainingSeconds = Math.max(0, Math.floor((endAtMs - Date.now()) / 1000));
    timer.textContent = `⏳ ${formatCountdown(remainingSeconds)}`;
    if (remainingSeconds <= 0) {
      hint.textContent = 'Maximale Dauer erreicht';
      if (hygieneCountdownInterval) {
        window.clearInterval(hygieneCountdownInterval);
        hygieneCountdownInterval = null;
      }
    }
  };

  closeBtn.addEventListener('click', async () => {
    if (!activeSessionId) return setStatus('Session fehlt.', true);
    let sealText = '';
    if (hygieneSealRequiredOnClose) {
      sealText = String(window.prompt('Bitte neuen Plomben-/Siegeltext eingeben:', '') || '').trim();
      if (sealText.length < 3) {
        setStatus('Neuer Siegeltext erforderlich (mindestens 3 Zeichen).', true);
        return;
      }
    }
    try {
      closeBtn.disabled = true;
      closeBtn.classList.add('opacity-70');
      closeBtn.textContent = 'Beende...';
      const body = await apiCall('POST', '/api/v1/chat/actions/execute', {
        session_id: activeSessionId,
        action_type: 'hygiene_close',
        payload: { reason: 'hygiene_window_completed', seal_text: sealText || undefined },
      });
      const successMessage = body?.message || 'Hygieneöffnung beendet.';
      appendMessage('assistant', `✅ ${successMessage}`);
      setStatus(successMessage);
      clearPersistedHygieneCountdownState();
      clearHygieneCountdownCard();
    } catch (error) {
      const errorMessage = String(error?.message || error);
      appendMessage('assistant', `⚠️ Aktion fehlgeschlagen (hygiene close): ${errorMessage}`);
      setStatus(errorMessage, true);
      closeBtn.disabled = false;
      closeBtn.classList.remove('opacity-70');
      closeBtn.textContent = 'Hygieneöffnung beenden';
    }
  });

  card.appendChild(title);
  card.appendChild(timer);
  card.appendChild(hint);
  card.appendChild(closeBtn);
  bubble.appendChild(card);
  contentDiv.appendChild(bubble);
  messageWrapper.appendChild(avatar);
  messageWrapper.appendChild(contentDiv);
  messagesEl.appendChild(messageWrapper);
  scrollToBottom();

  persistHygieneCountdownState(new Date(endAtMs).toISOString());

  renderTick();
  hygieneCountdownInterval = window.setInterval(renderTick, 1000);
}

function restoreHygieneCountdownCardFromStorage() {
  const state = readPersistedHygieneCountdownState();
  if (!state?.end_at) return;
  showHygieneCountdownCard({
    payload: {
      window_end_at: state.end_at,
    },
    ttlock: { command: 'open' },
  });
}

function setStatus(text, isError = false) {
  if (!statusEl || !window.chastease_common) return;
  window.chastease_common.setStatus(statusEl, text, isError ? 'err' : 'ok');
}

function renderMarkdown(text) {
  const renderer = window.chastease_common?.markdownToHtml;
  const value = String(text || '');
  if (typeof renderer === 'function') return renderer(value);
  return value;
}

function toPrettyActionName(actionType) {
  const raw = String(actionType || '').trim();
  if (!raw) return 'action';
  return raw.replaceAll('_', ' ');
}

function appendMessage(role, text, opts = {}) {
  if (!messagesEl) return;
  const shouldScroll = opts.scroll !== false;
  
  const messageWrapper = document.createElement('div');
  messageWrapper.className = 'flex items-start gap-3';
  
  if (role === 'user') {
    // User message: avatar on right
    const contentDiv = document.createElement('div');
    contentDiv.className = 'flex-1 flex justify-end';
    
    const bubble = document.createElement('div');
    bubble.className = 'max-w-[80%] rounded-2xl bg-gradient-to-br from-blue-600 to-blue-700 text-white px-5 py-3 shadow-lg';
    bubble.textContent = String(text || '');
    
    const avatar = document.createElement('div');
    avatar.className = 'flex-none w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white text-sm font-bold';
    avatar.textContent = 'DU';
    
    contentDiv.appendChild(bubble);
    messageWrapper.appendChild(contentDiv);
    messageWrapper.appendChild(avatar);
  } else {
    // Assistant message: avatar on left
    const avatar = document.createElement('div');
    avatar.className = 'flex-none w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white text-sm font-bold';
    avatar.textContent = 'AI';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'flex-1';
    
    const bubble = document.createElement('div');
    bubble.className = 'max-w-[90%] rounded-2xl bg-gray-800/80 text-gray-100 px-5 py-3 border border-gray-700/50 shadow-lg prose prose-invert prose-sm max-w-none';
    bubble.innerHTML = renderMarkdown(text);
    
    contentDiv.appendChild(bubble);
    messageWrapper.appendChild(avatar);
    messageWrapper.appendChild(contentDiv);
  }
  
  messagesEl.appendChild(messageWrapper);
  if (shouldScroll) scrollToBottom();
}

function appendAssistantInfoCard(titleText, bodyText, tone = 'neutral', opts = {}) {
  if (!messagesEl) return;
  const shouldScroll = opts.scroll !== false;

  const messageWrapper = document.createElement('div');
  messageWrapper.className = 'flex items-start gap-3';

  const avatar = document.createElement('div');
  avatar.className = 'flex-none w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white text-sm font-bold';
  avatar.textContent = 'AI';

  const contentDiv = document.createElement('div');
  contentDiv.className = 'flex-1';

  const bubble = document.createElement('div');
  bubble.className = 'max-w-[90%] rounded-2xl bg-gray-800/80 text-gray-100 px-5 py-3 border border-gray-700/50 shadow-lg';

  const toneClasses = {
    success: 'border-emerald-500/40 bg-emerald-950/30 text-emerald-200',
    failed: 'border-rose-500/40 bg-rose-950/30 text-rose-200',
    neutral: 'border-slate-600/60 bg-slate-900/50 text-slate-200',
  };

  const card = document.createElement('div');
  card.className = `rounded-lg border p-4 ${toneClasses[tone] || toneClasses.neutral}`;

  const title = document.createElement('div');
  title.className = 'text-sm font-semibold tracking-wide uppercase';
  title.textContent = String(titleText || 'Info');

  const body = document.createElement('div');
  body.className = 'mt-2 prose prose-invert prose-sm max-w-none text-sm';
  body.innerHTML = renderMarkdown(bodyText || '');

  card.appendChild(title);
  if (String(bodyText || '').trim()) card.appendChild(body);
  bubble.appendChild(card);
  contentDiv.appendChild(bubble);
  messageWrapper.appendChild(avatar);
  messageWrapper.appendChild(contentDiv);
  messagesEl.appendChild(messageWrapper);

  if (shouldScroll) scrollToBottom();
}

function findImageVerificationOutcome(body) {
  const executedActions = Array.isArray(body?.executed_actions) ? body.executed_actions : [];
  const failedActions = Array.isArray(body?.failed_actions) ? body.failed_actions : [];
  if (executedActions.some((item) => String(item?.action_type || '').trim() === 'image_verification')) {
    return 'success';
  }
  if (failedActions.some((item) => String(item?.action_type || '').trim() === 'image_verification')) {
    return 'failed';
  }

  const narration = String(body?.narration || '').toUpperCase();
  if (narration.includes('VERDICT: PASSED') || narration.endsWith('PASSED.')) return 'success';
  if (narration.includes('VERDICT: FAILED') || narration.endsWith('FAILED.')) return 'failed';
  return null;
}

function scrollToBottom(smooth = true) {
  const container = document.getElementById('messagesContainer');
  if (!container) return;
  container.scrollTo({
    top: container.scrollHeight,
    behavior: smooth ? 'smooth' : 'auto'
  });
}

function ensureInputAndLatestVisible() {
  scrollToBottom(false);
  if (inputEl) {
    try {
      inputEl.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    } catch (_error) {}
  }
}

function renderAttachmentPreview() {
  if (!attachmentPreviewEl) return;
  attachmentPreviewEl.innerHTML = '';
  if (!pendingAttachments.length) {
    attachmentPreviewEl.classList.add('hidden');
    return;
  }
  attachmentPreviewEl.classList.remove('hidden');
  pendingAttachments.forEach((item, index) => {
    const chip = document.createElement('div');
    chip.className = 'inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800/90 px-2 py-1 text-xs text-slate-200';

    const thumb = document.createElement('img');
    thumb.src = item.data_url;
    thumb.alt = item.name || 'Bild';
    thumb.className = 'h-8 w-8 rounded object-cover border border-slate-600';

    const label = document.createElement('span');
    label.textContent = item.name || `Bild ${index + 1}`;

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'rounded px-1 text-slate-300 hover:text-white';
    removeBtn.textContent = '✕';
    removeBtn.title = 'Entfernen';
    removeBtn.addEventListener('click', () => {
      pendingAttachments = pendingAttachments.filter((_, i) => i !== index);
      renderAttachmentPreview();
    });

    chip.appendChild(thumb);
    chip.appendChild(label);
    chip.appendChild(removeBtn);
    attachmentPreviewEl.appendChild(chip);
  });
}

async function handleAttachmentFiles(fileList) {
  const files = Array.from(fileList || []).filter((f) => String(f.type || '').startsWith('image/'));
  if (!files.length) return;
  const maxFiles = 4;
  const remainingSlots = Math.max(0, maxFiles - pendingAttachments.length);
  const accepted = files.slice(0, remainingSlots);
  for (const file of accepted) {
    if ((file.size || 0) > 8 * 1024 * 1024) {
      setStatus(`Datei zu groß: ${file.name} (max 8MB).`, true);
      continue;
    }
    const dataUrl = await fileToDataUrl(file);
    pendingAttachments.push({
      name: String(file.name || 'image.jpg'),
      type: String(file.type || 'image/jpeg'),
      mime_type: String(file.type || 'image/jpeg'),
      data_url: dataUrl,
    });
  }
  renderAttachmentPreview();
}

function clearInlineActionCards() {
  if (!messagesEl) return;
  messagesEl.querySelectorAll('[data-inline-action-card="true"]').forEach((node) => node.remove());
}

function appendInlineActionCard(cardNode) {
  if (!messagesEl || !cardNode) return;
  const messageWrapper = document.createElement('div');
  messageWrapper.className = 'flex items-start gap-3';
  messageWrapper.setAttribute('data-inline-action-card', 'true');

  const avatar = document.createElement('div');
  avatar.className = 'flex-none w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white text-sm font-bold';
  avatar.textContent = 'AI';

  const contentDiv = document.createElement('div');
  contentDiv.className = 'flex-1';

  const bubble = document.createElement('div');
  bubble.className = 'max-w-[90%] rounded-2xl bg-gray-800/80 text-gray-100 px-5 py-3 border border-gray-700/50 shadow-lg';
  bubble.appendChild(cardNode);

  contentDiv.appendChild(bubble);
  messageWrapper.appendChild(avatar);
  messageWrapper.appendChild(contentDiv);
  messagesEl.appendChild(messageWrapper);
  scrollToBottom();
}

async function apiCall(method, path, payload) {
  const response = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body?.detail || `HTTP ${response.status}`);
  }
  return body;
}

function getStoredAuth() {
  if (window.chastease_session && typeof window.chastease_session.getStoredAuth === 'function') {
    return window.chastease_session.getStoredAuth();
  }
  try {
    const raw = localStorage.getItem(window.chastease_common.authStorageKey());
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.user_id || !parsed?.auth_token) return null;
    return parsed;
  } catch (_e) {
    return null;
  }
}

async function resolveActiveSession() {
  const auth = getStoredAuth();
  if (!auth) {
    setStatus('Kein Login gefunden. Bitte zuerst einloggen.', true);
    if (sendBtn) sendBtn.disabled = true;
    return null;
  }

  let active = null;
  if (window.chastease_session && typeof window.chastease_session.fetchActiveSession === 'function') {
    active = await window.chastease_session.fetchActiveSession(statusEl);
  } else {
    active = await apiCall(
      'GET',
      `/api/v1/sessions/active?user_id=${encodeURIComponent(auth.user_id)}&auth_token=${encodeURIComponent(auth.auth_token)}`,
    );
  }
  if (!active?.has_active_session) {
    setStatus('Keine aktive Session. Bitte zuerst Setup/Dashboard abschließen.', true);
    if (sessionInfoEl) sessionInfoEl.textContent = 'Session: keine aktive Session';
    if (sendBtn) sendBtn.disabled = true;
    return null;
  }

  const sessionId = active?.chastity_session?.session_id;
  if (!sessionId) {
    setStatus('Aktive Session-ID fehlt.', true);
    if (sendBtn) sendBtn.disabled = true;
    return null;
  }

  activeSessionId = String(sessionId);
  currentLanguage = String(active?.chastity_session?.language || 'de');
  const mode = String(active?.chastity_session?.policy?.autonomy_mode || 'execute').toLowerCase();
  currentAutonomyMode = mode === 'suggest' ? 'suggest' : 'execute';
  const sealMode = String(active?.chastity_session?.policy?.seal?.mode || 'none').toLowerCase();
  sessionSealRequiredOnClose = sealMode === 'plomben' || sealMode === 'versiegelung';
  hygieneSealRequiredOnClose = sessionSealRequiredOnClose;
  if (sessionInfoEl) {
    sessionInfoEl.textContent = `Session: ${activeSessionId} · Modus: ${currentAutonomyMode}`;
  }
  if (sendBtn) sendBtn.disabled = false;
  setStatus('Chat bereit.');
  await loadRecentTurns();
  restoreHygieneCountdownCardFromStorage();
  return active;
}

async function loadRecentTurns() {
  if (!activeSessionId || !messagesEl) return;
  try {
    const body = await apiCall('GET', `/api/v1/sessions/${encodeURIComponent(activeSessionId)}/turns`);
    const turns = Array.isArray(body?.turns) ? body.turns : [];
    const recentTurns = turns.slice(-MAX_RENDERED_HISTORY_TURNS);
    messagesEl.innerHTML = '';
    recentTurns.forEach((turn) => {
      const playerAction = String(turn?.player_action || '').trim();
      const narration = String(turn?.ai_narration || '').trim();
      if (playerAction) appendMessage('user', playerAction, { scroll: false });
      if (narration) appendMessage('assistant', narration, { scroll: false });
    });
    if (!recentTurns.length) {
      appendMessage('assistant', 'Noch keine Nachrichten in dieser Session.', { scroll: false });
    }
    ensureInputAndLatestVisible();
  } catch (_error) {
    // Keep chat usable even if history endpoint fails.
  }
}

function renderPendingActions(pendingActions) {
  clearInlineActionCards();
  const actions = Array.isArray(pendingActions) ? pendingActions : [];
  if (!actions.length) return;

  if (pendingActionsWrapEl) pendingActionsWrapEl.classList.add('hidden');
  if (pendingActionsEl) pendingActionsEl.innerHTML = '';

  actions.forEach((action) => {
    const actionType = String(action?.action_type || '').trim();
    const payload = action?.payload && typeof action.payload === 'object' ? action.payload : {};
    const isHygieneAction = actionType === 'hygiene_open' || actionType === 'hygiene_close';
    const isAbortDecision = actionType === 'abort_decision';

    const card = document.createElement('div');
    card.className = 'rounded border border-gray-700 bg-gray-800 p-3';

    const header = document.createElement('div');
    header.className = 'flex items-center justify-between';

    const title = document.createElement('div');
    title.className = 'text-sm font-semibold text-gray-200';
    title.textContent = toPrettyActionName(actionType);

    const btn = document.createElement('button');
    btn.className = 'px-2 py-1 text-xs rounded bg-blue-600 hover:bg-blue-500';
    if (actionType === 'hygiene_open') btn.textContent = 'Hygieneöffnung starten';
    else if (actionType === 'hygiene_close') btn.textContent = 'Hygieneöffnung beenden';
    else btn.textContent = 'Ausführen';

    const payloadNode = document.createElement('pre');
    payloadNode.className = 'mt-2 text-xs text-gray-300 bg-gray-900 border border-gray-700 rounded p-2 overflow-x-auto';
    payloadNode.textContent = JSON.stringify(payload, null, 2);

    const hygieneHint = document.createElement('div');
    hygieneHint.className = 'mt-2 text-xs text-gray-300';
    if (actionType === 'hygiene_open') {
      const durationSeconds = Number(payload.duration_seconds || payload.opening_window_seconds || 0);
      const durationMinutes = durationSeconds > 0 ? Math.max(1, Math.floor(durationSeconds / 60)) : null;
      hygieneHint.textContent = durationMinutes
        ? `Hygienezeit freigeben (${durationMinutes} Min.).`
        : 'Hygienezeit freigeben.';
    } else if (actionType === 'hygiene_close') {
      hygieneHint.textContent = 'Hygieneöffnung wieder schließen.';
    }

    const sealInputWrap = document.createElement('div');
    sealInputWrap.className = 'mt-2 hidden';
    const sealInputLabel = document.createElement('label');
    sealInputLabel.className = 'text-xs text-gray-300 block';
    sealInputLabel.textContent = 'Neuer Plomben-/Siegeltext (Pflicht bei Plomben/Versiegelung)';
    const sealInput = document.createElement('input');
    sealInput.type = 'text';
    sealInput.className = 'mt-1 w-full rounded-md bg-gray-900 p-2 border border-gray-700 text-sm';
    sealInput.placeholder = 'z.B. PLOMBE-2026-02-27-A';
    sealInputWrap.appendChild(sealInputLabel);
    sealInputWrap.appendChild(sealInput);
    const sealRequiredOnClose = Boolean(payload?.seal_required_on_close ?? hygieneSealRequiredOnClose ?? sessionSealRequiredOnClose);
    if (actionType === 'hygiene_close' && sealRequiredOnClose) {
      sealInputWrap.classList.remove('hidden');
    }

    header.appendChild(title);
    if (isAbortDecision) {
      const helper = document.createElement('div');
      helper.className = 'mt-2 text-xs text-gray-300';
      helper.textContent = 'Ich habe ein mögliches Notfallsignal erkannt. Bitte kurz einordnen: ABBRECHEN oder NICHT ABBRECHEN (mit Begründung).';

      const reasonLabel = document.createElement('label');
      reasonLabel.className = 'mt-2 text-xs text-gray-300 block';
      reasonLabel.textContent = 'Kurze Einordnung (Pflichtfeld)';
      const reasonInput = document.createElement('textarea');
      reasonInput.className = 'mt-1 w-full rounded-md bg-gray-900 p-2 border border-gray-700 text-sm min-h-20';
      reasonInput.placeholder = 'Was ist der Kontext in 1–2 Sätzen?';

      const continueChecksWrap = document.createElement('div');
      continueChecksWrap.className = 'mt-2 space-y-1 text-xs text-gray-300';
      const checksTitle = document.createElement('div');
      checksTitle.className = 'text-xs text-gray-400';
      checksTitle.textContent = 'Für "Kein Abbruch" bitte bestätigen:';
      const check1 = document.createElement('label');
      const check1Input = document.createElement('input');
      check1Input.type = 'checkbox';
      check1Input.className = 'mr-2';
      check1.appendChild(check1Input);
      check1.append('Es geht nicht um mich persönlich');
      const check2 = document.createElement('label');
      const check2Input = document.createElement('input');
      check2Input.type = 'checkbox';
      check2Input.className = 'mr-2';
      check2.appendChild(check2Input);
      check2.append('Es besteht aktuell keine akute Gefahr');
      const check3 = document.createElement('label');
      const check3Input = document.createElement('input');
      check3Input.type = 'checkbox';
      check3Input.className = 'mr-2';
      check3.appendChild(check3Input);
      check3.append('Ich möchte nur sachliche Unterstützung');
      continueChecksWrap.appendChild(checksTitle);
      continueChecksWrap.appendChild(check1);
      continueChecksWrap.appendChild(check2);
      continueChecksWrap.appendChild(check3);

      const actionRow = document.createElement('div');
      actionRow.className = 'mt-3 flex flex-wrap gap-2';
      const abortBtn = document.createElement('button');
      abortBtn.className = 'px-3 py-1.5 text-xs rounded bg-red-600 hover:bg-red-500';
      abortBtn.textContent = 'Notfallabbruch';
      const continueBtn = document.createElement('button');
      continueBtn.className = 'px-3 py-1.5 text-xs rounded bg-green-600 hover:bg-green-500';
      continueBtn.textContent = 'Kein Abbruch';
      actionRow.appendChild(abortBtn);
      actionRow.appendChild(continueBtn);

      const executeDecision = async (decision) => {
        const reason = String(reasonInput.value || '').trim();
        if (reason.length < 3) {
          setStatus('Bitte kurz den Kontext eintragen.', true);
          return;
        }
        if (decision === 'continue') {
          if (!(check1Input.checked && check2Input.checked && check3Input.checked)) {
            setStatus('Für "NICHT ABBRECHEN" bitte alle drei Sicherheitsangaben bestätigen.', true);
            return;
          }
        }

        abortBtn.disabled = true;
        continueBtn.disabled = true;
        try {
          if (decision === 'abort') {
            appendMessage('user', `Begründung: ${reason}`);
            const reasonTurn = await apiCall('POST', '/api/v1/chat/turn', {
              session_id: activeSessionId,
              message: `Begründung: ${reason}`,
              language: currentLanguage,
              attachments: [],
            });
            appendMessage('assistant', reasonTurn?.narration || '(keine Antwort)');
            renderPendingActions(reasonTurn?.pending_actions || []);

            appendMessage('user', 'Ich bestaetige den Abbruch.');
            const confirmTurn = await apiCall('POST', '/api/v1/chat/turn', {
              session_id: activeSessionId,
              message: 'Ich bestaetige den Abbruch.',
              language: currentLanguage,
              attachments: [],
            });
            appendMessage('assistant', confirmTurn?.narration || '(keine Antwort)');
            const pendingAfterAutoExec = await autoExecuteTimerPendingActions(confirmTurn?.pending_actions || []);
            renderPendingActions(pendingAfterAutoExec);
            setStatus('Danke für die Einordnung. Notfallablauf wird jetzt ausgeführt.');
          } else {
            const message = `Nicht abbrechen. Es betrifft nicht mich. Keine akute Gefahr. Nur sachliche Beratung/Begleitung. Grund: ${reason}`;
            appendMessage('user', message);
            const turn = await apiCall('POST', '/api/v1/chat/turn', {
              session_id: activeSessionId,
              message,
              language: currentLanguage,
              attachments: [],
            });
            appendMessage('assistant', turn?.narration || '(keine Antwort)');
            const pendingAfterAutoExec = await autoExecuteTimerPendingActions(turn?.pending_actions || []);
            renderPendingActions(pendingAfterAutoExec);
            setStatus('Danke für die Einordnung. Kein Abbruch – die Session bleibt aktiv.');
          }
        } catch (error) {
          setStatus(String(error?.message || error), true);
          abortBtn.disabled = false;
          continueBtn.disabled = false;
        }
      };

      abortBtn.addEventListener('click', () => executeDecision('abort'));
      continueBtn.addEventListener('click', () => executeDecision('continue'));

      card.appendChild(helper);
      card.appendChild(reasonLabel);
      card.appendChild(reasonInput);
      card.appendChild(actionRow);
      card.appendChild(continueChecksWrap);
      appendInlineActionCard(card);
      return;
    }

    if (actionType !== 'image_verification') {
      btn.addEventListener('click', async () => {
        if (!activeSessionId) return setStatus('Session fehlt.', true);
        const inlineRow = card.closest('[data-inline-action-card="true"]');
        try {
          btn.disabled = true;
          btn.classList.add('opacity-70');
          const originalLabel = btn.textContent;
          btn.textContent = 'Wird ausgeführt...';
          setStatus(`Führe Action aus: ${actionType}...`);
          const effectivePayload = { ...payload };
          if (actionType === 'hygiene_close') {
            const maybeSealText = String(sealInput.value || '').trim();
            if (sealRequiredOnClose && maybeSealText) effectivePayload.seal_text = maybeSealText;
          }
          const body = await apiCall('POST', '/api/v1/chat/actions/execute', {
            session_id: activeSessionId,
            action_type: actionType,
            payload: effectivePayload,
          });
          const successMessage = body?.message || `Action ausgeführt: ${actionType}`;
          setStatus(successMessage);
          appendMessage('assistant', `✅ ${successMessage}`);
          if (actionType === 'hygiene_open') {
            showHygieneCountdownCard(body);
          }
          if (actionType === 'hygiene_close') {
            clearPersistedHygieneCountdownState();
            clearHygieneCountdownCard();
          }
          if (inlineRow) inlineRow.remove();
          else {
            btn.textContent = 'Ausgeführt';
          }
        } catch (error) {
          const errorMessage = String(error?.message || error);
          setStatus(errorMessage, true);
          appendMessage('assistant', `⚠️ Aktion fehlgeschlagen (${toPrettyActionName(actionType)}): ${errorMessage}`);
          btn.disabled = false;
          btn.classList.remove('opacity-70');
          if (actionType === 'hygiene_open') btn.textContent = 'Hygieneöffnung starten';
          else if (actionType === 'hygiene_close') btn.textContent = 'Hygieneöffnung beenden';
          else btn.textContent = 'Ausführen';
        }
      });
      header.appendChild(btn);
    }
    card.appendChild(header);
    if (isHygieneAction) {
      card.appendChild(hygieneHint);
      if (actionType === 'hygiene_close') card.appendChild(sealInputWrap);
    } else if (actionType === 'image_verification') {
      // Image verification card renders a custom UI; do not show raw JSON payload.
    } else {
      card.appendChild(payloadNode);
    }

    if (actionType === 'image_verification') {
      const requestText = String(payload?.request || 'Bitte ein Verifikationsbild aufnehmen/hochladen.');
      const instructionText = String(payload?.verification_instruction || 'Prüfe, ob die angeforderte Bedingung im Bild sichtbar erfüllt ist.');

      card.className = 'rounded border border-gray-700 bg-gray-800 p-3';
      title.className = 'text-sm font-semibold text-gray-200';

      const hint = document.createElement('div');
      hint.className = 'mt-2 rounded border border-gray-700 bg-gray-900 p-2 text-sm text-gray-200';
      hint.textContent = `Anforderung: ${requestText}`;

      const instruction = document.createElement('div');
      instruction.className = 'mt-2 rounded border border-gray-700 bg-gray-900 p-2 text-sm text-gray-300';
      instruction.textContent = `Verifikation: ${instructionText}`;

      const controls = document.createElement('div');
      controls.className = 'mt-2 flex flex-wrap items-center gap-2';

      const captureBtn = document.createElement('button');
      captureBtn.className = 'px-3 py-1.5 text-sm rounded bg-blue-600 hover:bg-blue-500';
      captureBtn.textContent = 'Bild aufnehmen';

      const fileInput = document.createElement('input');
      fileInput.type = 'file';
      fileInput.accept = 'image/*';
      fileInput.capture = 'environment';
      fileInput.className = 'hidden';

      const previewWrap = document.createElement('div');
      previewWrap.className = 'mt-2 hidden rounded border border-gray-700 bg-gray-900 p-2';

      const previewImage = document.createElement('img');
      previewImage.className = 'max-h-44 rounded border border-gray-700';
      previewImage.alt = 'Vorschau Bildverifikation';

      const reviewControls = document.createElement('div');
      reviewControls.className = 'mt-2 hidden flex flex-wrap items-center gap-2';

      const selectedInfo = document.createElement('div');
      selectedInfo.className = 'mt-1 text-xs text-gray-400';
      selectedInfo.textContent = 'Noch kein Bild gewählt.';

      const reviewState = document.createElement('div');
      reviewState.className = 'mt-2 text-xs text-blue-300 hidden';
      reviewState.textContent = 'Bildprüfung gestartet...';

      const reviewBtn = document.createElement('button');
      reviewBtn.className = 'px-2 py-1 text-xs rounded bg-blue-600 hover:bg-blue-500';
      reviewBtn.textContent = 'Bild prüfen';
      reviewBtn.disabled = true;

      let selectedImage = null;

      const setSelectedImage = (dataUrl, pictureName, pictureType, sourceText) => {
        selectedImage = {
          dataUrl,
          pictureName: pictureName || 'image.jpg',
          pictureType: pictureType || 'image/jpeg',
        };
        previewImage.src = dataUrl;
        previewWrap.classList.remove('hidden');
        reviewControls.classList.remove('hidden');
        reviewBtn.disabled = false;
        selectedInfo.textContent = sourceText;
        reviewState.classList.add('hidden');
        reviewState.textContent = 'Bildprüfung gestartet...';
      };

      captureBtn.addEventListener('click', () => {
        fileInput.click();
      });

      fileInput.addEventListener('change', async () => {
        const file = fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
        if (!file) return;
        try {
          const dataUrl = await fileToDataUrl(file);
          setSelectedImage(dataUrl, file.name || 'image.jpg', file.type || 'image/jpeg', `Bild gewählt: ${file.name || 'image.jpg'}`);
        } catch (error) {
          setStatus(String(error?.message || error), true);
        }
      });

      controls.appendChild(captureBtn);
      controls.appendChild(fileInput);

      reviewControls.appendChild(reviewBtn);
      previewWrap.appendChild(previewImage);

      card.appendChild(hint);
      card.appendChild(instruction);
      card.appendChild(controls);
      card.appendChild(previewWrap);
      card.appendChild(reviewControls);
      card.appendChild(selectedInfo);
      card.appendChild(reviewState);

      reviewBtn.addEventListener('click', async () => {
        if (!activeSessionId) return setStatus('Session fehlt.', true);
        if (!selectedImage?.dataUrl) return setStatus('Bitte ein Bild aufnehmen oder auswählen.', true);

        try {
          setStatus('Bildprüfung gestartet...');
          reviewBtn.disabled = true;
          reviewBtn.textContent = 'Prüfung läuft...';
          controls.classList.add('hidden');
          previewWrap.classList.add('hidden');
          reviewControls.classList.add('hidden');
          selectedInfo.classList.add('hidden');
          reviewState.classList.remove('hidden');
          const body = await apiCall('POST', '/api/v1/chat/vision-review', {
            session_id: activeSessionId,
            message: requestText,
            language: currentLanguage,
            picture_name: selectedImage.pictureName,
            picture_content_type: selectedImage.pictureType,
            picture_data_url: selectedImage.dataUrl,
            verification_instruction: instructionText,
            verification_action_payload: payload,
            source: selectedImage.pictureName === 'camera.jpg' ? 'camera_capture' : 'upload',
          });
          const verificationOutcome = findImageVerificationOutcome(body);
          if (verificationOutcome === 'success') {
            appendAssistantInfoCard('Bildprüfung bestanden', body?.narration || 'Die Bildprüfung war erfolgreich.', 'success');
          } else if (verificationOutcome === 'failed') {
            appendAssistantInfoCard('Bildprüfung nicht bestanden', body?.narration || 'Die Bildprüfung ist fehlgeschlagen.', 'failed');
          } else {
            appendAssistantInfoCard('Bildprüfung abgeschlossen', body?.narration || 'Bildprüfung abgeschlossen.', 'neutral');
          }
          const pendingAfterAutoExec = await autoExecuteTimerPendingActions(body?.pending_actions || []);
          renderPendingActions(pendingAfterAutoExec);
          if (verificationOutcome === 'success') setStatus('Bildprüfung bestanden.');
          else if (verificationOutcome === 'failed') setStatus('Bildprüfung nicht bestanden.', true);
          else setStatus('Bildprüfung abgeschlossen.');
        } catch (error) {
          reviewState.textContent = 'Bildprüfung fehlgeschlagen. Bitte erneut versuchen.';
          controls.classList.remove('hidden');
          previewWrap.classList.remove('hidden');
          reviewControls.classList.remove('hidden');
          selectedInfo.classList.remove('hidden');
          setStatus(String(error?.message || error), true);
        } finally {
          reviewBtn.disabled = false;
          reviewBtn.textContent = 'Bild prüfen';
        }
      });
    }

    appendInlineActionCard(card);
  });
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('Datei konnte nicht gelesen werden.'));
    reader.readAsDataURL(file);
  });
}

async function autoExecuteTimerPendingActions(pendingActions) {
  const actions = Array.isArray(pendingActions) ? pendingActions : [];
  if (!actions.length || !activeSessionId) return actions;
  if (currentAutonomyMode !== 'execute') return actions;

  const remaining = [];
  for (const action of actions) {
    const actionType = String(action?.action_type || '').trim();
    const payload = action?.payload && typeof action.payload === 'object' ? action.payload : {};
    if (!AUTO_TIMER_ACTIONS.has(actionType)) {
      remaining.push(action);
      continue;
    }

    try {
      const result = await apiCall('POST', '/api/v1/chat/actions/execute', {
        session_id: activeSessionId,
        action_type: actionType,
        payload,
      });
      const info = result?.message || `Action ausgeführt: ${actionType}`;
      appendMessage('assistant', `✅ ${info}`);
    } catch (error) {
      appendMessage('assistant', `⚠️ Aktion konnte nicht automatisch ausgeführt werden (${actionType}): ${String(error?.message || error)}`);
      remaining.push(action);
    }
  }
  return remaining;
}

async function sendMessage() {
  if (!inputEl || !activeSessionId) {
    setStatus('Session nicht bereit.', true);
    return;
  }
  const message = String(inputEl.value || '').trim();
  const attachments = Array.isArray(pendingAttachments) ? [...pendingAttachments] : [];
  if (!message && !attachments.length) return;
  const messageForApi = message || (currentLanguage === 'en' ? '[Image upload]' : '[Bildupload]');

  if (message) appendMessage('user', message);
  if (attachments.length) appendMessage('user', `📷 ${attachments.length} Bild(er) angehängt.`);
  inputEl.value = '';
  pendingAttachments = [];
  renderAttachmentPreview();
  autoResizeTextarea();
  if (sendBtn) sendBtn.disabled = true;

  try {
    setStatus('Sende an LLM...');
      showTypingIndicator();
    const body = await apiCall('POST', '/api/v1/chat/turn', {
      session_id: activeSessionId,
      message: messageForApi,
      language: currentLanguage,
      attachments,
    });
    appendMessage('assistant', body?.narration || '(keine Antwort)');

    const failedActions = Array.isArray(body?.failed_actions) ? body.failed_actions : [];
    failedActions.forEach((entry) => {
      const name = toPrettyActionName(entry?.action_type || 'action');
      const detail = String(entry?.detail || 'Unbekannter Fehler');
      appendMessage('assistant', `⚠️ Action nicht ausgelöst (${name}): ${detail}`);
    });

    const pendingAfterAutoExec = await autoExecuteTimerPendingActions(body?.pending_actions || []);
    renderPendingActions(pendingAfterAutoExec);
    setStatus('Antwort erhalten.');
  } catch (error) {
    appendMessage('assistant', `Fehler: ${String(error?.message || error)}`);
    setStatus(String(error?.message || error), true);
  } finally {
    hideTypingIndicator();
    if (sendBtn) sendBtn.disabled = false;
    if (inputEl) inputEl.focus();
    ensureInputAndLatestVisible();
  }
}

function wireEvents() {
    // Auto-resize textarea
    if (inputEl) {
      inputEl.addEventListener('input', autoResizeTextarea);
      autoResizeTextarea();
    }

    // Scroll-to-bottom button
    const scrollBtn = document.getElementById('scrollToBottomBtn');
    const messagesContainer = document.getElementById('messagesContainer');
    if (scrollBtn && messagesContainer) {
      messagesContainer.addEventListener('scroll', () => {
        const isNearBottom = messagesContainer.scrollHeight - messagesContainer.scrollTop - messagesContainer.clientHeight < 150;
        scrollBtn.classList.toggle('hidden', isNearBottom);
      });
      scrollBtn.addEventListener('click', () => scrollToBottom());
    }

  if (attachImageBtn && chatAttachmentInput) {
    attachImageBtn.addEventListener('click', () => {
      try {
        if (typeof chatAttachmentInput.showPicker === 'function') {
          chatAttachmentInput.showPicker();
        } else {
          chatAttachmentInput.click();
        }
      } catch (_error) {
        chatAttachmentInput.click();
      }
    });
    chatAttachmentInput.addEventListener('change', async () => {
      try {
        await handleAttachmentFiles(chatAttachmentInput.files);
      } catch (error) {
        setStatus(String(error?.message || error), true);
      } finally {
        chatAttachmentInput.value = '';
      }
    });
  }

  if (sendBtn) sendBtn.addEventListener('click', sendMessage);
  if (inputEl) {
    inputEl.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    });
    inputEl.addEventListener('focus', () => ensureInputAndLatestVisible());
    inputEl.addEventListener('paste', async (event) => {
      const items = Array.from(event.clipboardData?.items || []);
      const imageFiles = items
        .filter((item) => item.kind === 'file' && String(item.type || '').startsWith('image/'))
        .map((item) => item.getAsFile())
        .filter(Boolean);
      if (!imageFiles.length) return;
      event.preventDefault();
      try {
        await handleAttachmentFiles(imageFiles);
        setStatus(`${imageFiles.length} Bild(er) aus Zwischenablage angehängt.`);
      } catch (error) {
        setStatus(String(error?.message || error), true);
      }
    });
  }

  window.addEventListener('resize', () => ensureInputAndLatestVisible());
  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', ensureInputAndLatestVisible);
    window.visualViewport.addEventListener('scroll', ensureInputAndLatestVisible);
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  wireEvents();
  if (typeof window.chastease_common !== 'undefined' && typeof window.chastease_common.renderNavAuth === 'function') {
    window.chastease_common.renderNavAuth();
  }
  if (sendBtn) sendBtn.disabled = true;
  await resolveActiveSession();
  ensureInputAndLatestVisible();
});

  function showTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
      indicator.classList.remove('hidden');
      scrollToBottom();
    }
  }

  function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) indicator.classList.add('hidden');
  }

  function autoResizeTextarea() {
    if (!inputEl) return;
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + 'px';
  }
hideTypingIndicator();

window.chastease_chat = { sendMessage, resolveActiveSession };
window.sendMessage = sendMessage;
