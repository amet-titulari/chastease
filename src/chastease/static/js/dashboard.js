const sessionHelper = typeof chastease_session !== 'undefined' ? chastease_session : null;
const statusEl = document.getElementById('dashboardStatus');
const activeEl = document.getElementById('activeSessionInfo');
const setupEl = document.getElementById('setupSessionInfo');
const setupBtn = document.getElementById('dashboardSetupBtn');
const refreshBtn = document.getElementById('dashboardRefreshBtn');
const killBtn = document.getElementById('dashboardKillBtn');

const timerSummaryEl = document.getElementById('dashboardTimerSummary');
const timerDayAEl = document.getElementById('timerDayA');
const timerDayBEl = document.getElementById('timerDayB');
const timerDayCEl = document.getElementById('timerDayC');
const timerHourAEl = document.getElementById('timerHourA');
const timerHourBEl = document.getElementById('timerHourB');
const timerMinAEl = document.getElementById('timerMinA');
const timerMinBEl = document.getElementById('timerMinB');
const timerSecAEl = document.getElementById('timerSecA');
const timerSecBEl = document.getElementById('timerSecB');

const psychSummaryEl = document.getElementById('dashboardPsychSummary');
const psychMetaEl = document.getElementById('dashboardPsychMeta');
const psychAnalysisEl = document.getElementById('dashboardPsychAnalysis');
const psychTraitsEl = document.getElementById('dashboardPsychTraits');

let currentSession = null;
let timerInterval = null;
let sessionRefreshInterval = null;

const traitLabels = {
  structure_need: 'Strukturbedarf',
  strictness_affinity: 'Strenge',
  accountability_need: 'Kontrollbedürfnis',
  praise_affinity: 'Lobaffinität',
  novelty_affinity: 'Neuigkeitsdrang',
  challenge_affinity: 'Challenge-Affinität',
};

function toDateOrNull(value) {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

function updateTimerDigits(days, hours, minutes, seconds) {
  const dayString = String(Math.max(0, days)).padStart(3, '0').slice(-3);
  const hourString = String(Math.max(0, hours)).padStart(2, '0');
  const minuteString = String(Math.max(0, minutes)).padStart(2, '0');
  const secondString = String(Math.max(0, seconds)).padStart(2, '0');

  if (timerDayAEl) timerDayAEl.textContent = dayString[0];
  if (timerDayBEl) timerDayBEl.textContent = dayString[1];
  if (timerDayCEl) timerDayCEl.textContent = dayString[2];
  if (timerHourAEl) timerHourAEl.textContent = hourString[0];
  if (timerHourBEl) timerHourBEl.textContent = hourString[1];
  if (timerMinAEl) timerMinAEl.textContent = minuteString[0];
  if (timerMinBEl) timerMinBEl.textContent = minuteString[1];
  if (timerSecAEl) timerSecAEl.textContent = secondString[0];
  if (timerSecBEl) timerSecBEl.textContent = secondString[1];
}

function resetTimerDisplay(summary = 'Kein Enddatum verfügbar.') {
  updateTimerDigits(0, 0, 0, 0);
  if (timerSummaryEl) timerSummaryEl.textContent = summary;
}

function clearTimerInterval() {
  if (!timerInterval) return;
  window.clearInterval(timerInterval);
  timerInterval = null;
}

function getTargetDate(body) {
  const runtimeTimer = body?.chastity_session?.policy?.runtime_timer || {};
  const runtimeTarget = toDateOrNull(runtimeTimer.effective_end_at);
  if (runtimeTarget) return runtimeTarget;
  const contract = body?.chastity_session?.policy?.contract || {};
  return (
    toDateOrNull(contract.proposed_end_date) ||
    toDateOrNull(contract.end_date) ||
    toDateOrNull(contract.max_end_date)
  );
}

function splitSeconds(totalSecondsRaw) {
  const totalSeconds = Math.max(0, Math.floor(Number(totalSecondsRaw) || 0));
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return { days, hours, minutes, seconds };
}

function renderTimer(body) {
  clearTimerInterval();
  if (!body?.has_active_session) {
    resetTimerDisplay('Keine aktive Session.');
    return;
  }

  const runtimeTimer = body?.chastity_session?.policy?.runtime_timer || {};
  const timerState = String(runtimeTimer.state || '').toLowerCase();
  if (timerState === 'paused') {
    const remaining = Number(runtimeTimer.remaining_seconds);
    const { days, hours, minutes, seconds } = splitSeconds(remaining);
    updateTimerDigits(days, hours, minutes, seconds);

    const pausedAt = toDateOrNull(runtimeTimer.paused_at);
    if (timerSummaryEl) {
      if (pausedAt) {
        const datePart = pausedAt.toLocaleDateString('de-DE');
        const timePart = pausedAt.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        timerSummaryEl.textContent = `❄️ Timer angehalten seit ${datePart} ${timePart}`;
      } else {
        timerSummaryEl.textContent = '❄️ Timer angehalten';
      }
    }
    return;
  }

  const targetDate = getTargetDate(body);
  if (!targetDate) {
    resetTimerDisplay('Enddatum: KI entscheidet.');
    return;
  }

  const tick = () => {
    const now = new Date();
    const diffMs = targetDate.getTime() - now.getTime();
    if (diffMs <= 0) {
      updateTimerDigits(0, 0, 0, 0);
      if (timerSummaryEl) timerSummaryEl.textContent = 'Zielzeit erreicht.';
      clearTimerInterval();
      return;
    }

    const totalSeconds = Math.floor(diffMs / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    updateTimerDigits(days, hours, minutes, seconds);
    if (timerSummaryEl) {
      const datePart = targetDate.toLocaleDateString('de-DE');
      const timePart = targetDate.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
      const prefix = runtimeTimer?.effective_end_at ? '⏱️ Runtime bis' : 'Bis';
      timerSummaryEl.textContent = `${prefix} ${datePart} ${timePart}`;
    }
  };

  tick();
  timerInterval = window.setInterval(tick, 1000);
}

function renderPsychogram(body) {
  const psychogram = body?.chastity_session?.psychogram;
  if (!psychogram) {
    if (psychSummaryEl) psychSummaryEl.textContent = 'Noch kein Psychogramm verfügbar.';
    if (psychMetaEl) psychMetaEl.textContent = '';
    if (psychAnalysisEl) psychAnalysisEl.textContent = '';
    if (psychTraitsEl) psychTraitsEl.innerHTML = '';
    return;
  }

  if (psychSummaryEl) psychSummaryEl.textContent = psychogram.summary || 'Psychogramm geladen.';

  const confidence = Number(psychogram.confidence);
  const confidenceText = Number.isFinite(confidence) ? `${Math.round(confidence * 100)}%` : '-';
  const updatedAt = psychogram.updated_at || psychogram.created_at || '-';
  if (psychMetaEl) psychMetaEl.textContent = `Confidence: ${confidenceText} · Aktualisiert: ${updatedAt}`;

  if (psychAnalysisEl) {
    const analysis = String(psychogram.analysis || '');
    const renderer = window.chastease_common?.markdownToHtml;
    if (typeof renderer === 'function') {
      psychAnalysisEl.innerHTML = renderer(analysis);
    } else {
      psychAnalysisEl.textContent = analysis;
    }
  }

  const traits = psychogram.traits || {};
  const entries = Object.entries(traits)
    .filter(([, value]) => Number.isFinite(Number(value)))
    .sort((a, b) => Number(b[1]) - Number(a[1]));

  if (!psychTraitsEl) return;
  psychTraitsEl.innerHTML = '';
  if (!entries.length) {
    psychTraitsEl.innerHTML = '<p class="text-sm text-gray-400">Keine Trait-Werte verfügbar.</p>';
    return;
  }

  entries.forEach(([key, value]) => {
    const normalized = Math.max(0, Math.min(100, Number(value)));
    const label = traitLabels[key] || key;
    const row = document.createElement('div');
    row.className = 'rounded border border-gray-700 p-2 bg-gray-900';
    row.innerHTML = `
      <div class="flex items-center justify-between text-sm text-gray-300 mb-1">
        <span>${label}</span>
        <span>${normalized}</span>
      </div>
      <div class="h-2 rounded bg-gray-700 overflow-hidden">
        <div class="h-full bg-blue-500" style="width: ${normalized}%;"></div>
      </div>
    `;
    psychTraitsEl.appendChild(row);
  });
}

function describeActiveSession(body) {
  if (!body) return '—';
  if (body.has_active_session) {
    const sess = body.chastity_session || {};
    return sess.session_id || sess.id || 'active (unknown id)';
  }
  return 'Keine aktive Session';
}

function describeSetup(body) {
  if (!body) return '—';
  const status = body.setup_status || 'unknown';
  const id = body.setup_session_id || 'n/a';
  return `${status} (${id})`;
}

function updateView(body) {
  currentSession = body;
  if (activeEl) activeEl.textContent = describeActiveSession(body);
  if (setupEl) setupEl.textContent = describeSetup(body);
  renderTimer(body);
  renderPsychogram(body);

  if (statusEl) {
    const msg = body?.has_active_session ? 'Session status loaded.' : 'Keine aktive Session. Setup fortsetzen.';
    chastease_common.setStatus(statusEl, msg, body?.has_active_session ? 'ok' : 'err');
  }
}

function refreshSession() {
  if (!sessionHelper || typeof sessionHelper.fetchActiveSession !== 'function') {
    if (statusEl) chastease_common.setStatus(statusEl, 'Session helper missing.', 'err');
    return;
  }
  sessionHelper.fetchActiveSession(statusEl).then((body) => {
    if (!body) return;
    updateView(body);
  });
}

function startSessionAutoRefresh() {
  if (sessionRefreshInterval) return;
  sessionRefreshInterval = window.setInterval(() => {
    refreshSession();
  }, 5000);
}

function goToSetup() {
  const setupId = currentSession?.setup_session_id;
  const target = setupId ? `/setup?setup_session_id=${encodeURIComponent(setupId)}` : '/setup';
  window.location.href = target;
}

function killSession() {
  if (!currentSession) return;
  const auth = sessionHelper?.getStoredAuth();
  if (!auth) {
    if (statusEl) chastease_common.setStatus(statusEl, 'No auth info.', 'err');
    return;
  }
  if (statusEl) chastease_common.setStatus(statusEl, 'Deleting session...');
  fetch(`/api/v1/sessions/active?user_id=${encodeURIComponent(auth.user_id)}&auth_token=${encodeURIComponent(auth.auth_token)}`, {
    method: 'DELETE',
  })
    .then((res) => res.json().then((body) => ({ status: res.status, body })))
    .then(({ status, body }) => {
      if (status === 200) {
        if (statusEl) chastease_common.setStatus(statusEl, 'Session deleted.');
        refreshSession();
      } else if (statusEl) {
        chastease_common.setStatus(statusEl, body.detail || 'Failed to delete', 'err');
      }
    })
    .catch(() => statusEl && chastease_common.setStatus(statusEl, 'Delete request failed', 'err'));
}

if (refreshBtn) refreshBtn.addEventListener('click', refreshSession);
if (setupBtn) setupBtn.addEventListener('click', goToSetup);
if (killBtn) killBtn.addEventListener('click', killSession);

document.addEventListener('DOMContentLoaded', () => {
  if (typeof chastease_common !== 'undefined' && typeof chastease_common.renderNavAuth === 'function') {
    chastease_common.renderNavAuth();
  }
  refreshSession();
  startSessionAutoRefresh();
});
