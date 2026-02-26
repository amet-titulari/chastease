const statusEl = document.getElementById('chatStatus');
const sessionInfoEl = document.getElementById('chatSessionInfo');
const messagesEl = document.getElementById('messages');
const inputEl = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const pendingActionsWrapEl = document.getElementById('pendingActionsWrap');
const pendingActionsEl = document.getElementById('pendingActions');

let activeSessionId = null;
let currentLanguage = 'de';
let currentAutonomyMode = 'execute';
const MAX_RENDERED_HISTORY_TURNS = 12;
const AUTO_TIMER_ACTIONS = new Set(['add_time', 'reduce_time', 'pause_timer', 'unpause_timer']);
const HYGIENE_COUNTDOWN_STORAGE_PREFIX = 'chastease_hygiene_countdown:';
let hygieneCountdownInterval = null;

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

  const row = document.createElement('div');
  row.className = 'flex justify-start';
  row.setAttribute('data-hygiene-countdown-row', 'true');

  const bubble = document.createElement('div');
  bubble.className = 'max-w-[95%] w-full rounded-lg bg-gray-900 text-gray-100 px-3 py-2 border border-cyan-700';

  const card = document.createElement('div');
  card.className = 'rounded border border-cyan-700 bg-gray-800 p-3';
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
    try {
      closeBtn.disabled = true;
      closeBtn.classList.add('opacity-70');
      closeBtn.textContent = 'Beende...';
      const body = await apiCall('POST', '/api/v1/chat/actions/execute', {
        session_id: activeSessionId,
        action_type: 'hygiene_close',
        payload: { reason: 'hygiene_window_completed' },
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
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;

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

function appendMessage(role, text) {
  if (!messagesEl) return;
  const row = document.createElement('div');
  row.className = role === 'user' ? 'flex justify-end' : 'flex justify-start';

  const bubble = document.createElement('div');
  bubble.className = role === 'user'
    ? 'max-w-[85%] rounded-lg bg-blue-700 text-white px-3 py-2'
    : 'max-w-[85%] rounded-lg bg-gray-800 text-gray-100 px-3 py-2 border border-gray-700';

  if (role === 'assistant') bubble.innerHTML = renderMarkdown(text);
  else bubble.textContent = String(text || '');

  row.appendChild(bubble);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function clearInlineActionCards() {
  if (!messagesEl) return;
  messagesEl.querySelectorAll('[data-inline-action-card="true"]').forEach((node) => node.remove());
}

function appendInlineActionCard(cardNode) {
  if (!messagesEl || !cardNode) return;
  const row = document.createElement('div');
  row.className = 'flex justify-start';
  row.setAttribute('data-inline-action-card', 'true');

  const bubble = document.createElement('div');
  bubble.className = 'max-w-[95%] w-full rounded-lg bg-gray-900 text-gray-100 px-3 py-2 border border-gray-700';
  bubble.appendChild(cardNode);

  row.appendChild(bubble);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
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
      if (playerAction) appendMessage('user', playerAction);
      if (narration) appendMessage('assistant', narration);
    });
    if (!recentTurns.length) {
      appendMessage('assistant', 'Noch keine Nachrichten in dieser Session.');
    }
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

    header.appendChild(title);
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
          const body = await apiCall('POST', '/api/v1/chat/actions/execute', {
            session_id: activeSessionId,
            action_type: actionType,
            payload,
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
          appendMessage('assistant', body?.narration || 'Bildprüfung abgeschlossen.');
          const pendingAfterAutoExec = await autoExecuteTimerPendingActions(body?.pending_actions || []);
          renderPendingActions(pendingAfterAutoExec);
          setStatus('Bildprüfung abgeschlossen.');
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
  if (!message) return;

  appendMessage('user', message);
  inputEl.value = '';
  if (sendBtn) sendBtn.disabled = true;

  try {
    setStatus('Sende an LLM...');
    const body = await apiCall('POST', '/api/v1/chat/turn', {
      session_id: activeSessionId,
      message,
      language: currentLanguage,
      attachments: [],
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
    if (sendBtn) sendBtn.disabled = false;
    if (inputEl) inputEl.focus();
  }
}

function wireEvents() {
  if (sendBtn) sendBtn.addEventListener('click', sendMessage);
  if (inputEl) {
    inputEl.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    });
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  wireEvents();
  if (typeof window.chastease_common !== 'undefined' && typeof window.chastease_common.renderNavAuth === 'function') {
    window.chastease_common.renderNavAuth();
  }
  if (sendBtn) sendBtn.disabled = true;
  await resolveActiveSession();
});

window.chastease_chat = { sendMessage, resolveActiveSession };
window.sendMessage = sendMessage;
