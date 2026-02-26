const sessionHelper = typeof chastease_session !== 'undefined' ? chastease_session : null;
const statusEl = document.getElementById('turnLogStatus');
const summaryEl = document.getElementById('turnLogSummary');
const sessionIdEl = document.getElementById('turnLogSessionId');
const entriesBodyEl = document.getElementById('turnLogEntriesBody');
const reloadBtn = document.getElementById('turnLogReloadBtn');

let fetchingTurns = false;

function escapeHtml(value) {
  if (typeof chastease_common?.escapeHtml === 'function') {
    return chastease_common.escapeHtml(value);
  }
  return String(value || '');
}

function updateStatus(text, kind = 'ok') {
  if (!statusEl || typeof chastease_common?.setStatus !== 'function') return;
  chastease_common.setStatus(statusEl, text, kind);
}

function updateSummary(text) {
  if (summaryEl) summaryEl.textContent = text;
}

function clearEntries(message = 'Keine Turn-Einträge vorhanden.') {
  if (!entriesBodyEl) return;
  const cell = `<td colspan="5" class="px-3 py-4 text-center text-gray-500 border border-gray-700">${escapeHtml(message)}</td>`;
  entriesBodyEl.innerHTML = `<tr>${cell}</tr>`;
}

function getQuerySessionId() {
  try {
    return new URLSearchParams(window.location.search).get('session_id') || null;
  } catch (error) {
    return null;
  }
}

function fallbackSessionId() {
  if (!sessionIdEl) return null;
  const fallback = sessionIdEl.dataset?.initialSessionId;
  if (fallback) return fallback;
  const raw = sessionIdEl.textContent?.trim();
  if (!raw || raw === '—') return null;
  return raw;
}

function renderTurnRows(turns) {
  if (!entriesBodyEl) return;
  if (!turns.length) {
    clearEntries('Keine Turns für diese Sitzung.');
    return;
  }

  const rows = turns
    .map((turn) => {
      const playerAction = escapeHtml(turn.player_action || '-');
      const aiNarration = escapeHtml(turn.ai_narration || '-');
      const language = escapeHtml(turn.language || '-');
      const created = escapeHtml(new Date(turn.created_at || '').toLocaleString('de-DE') || '-');
      const turnNo = escapeHtml(turn.turn_no ?? '-');
      return `
        <tr class="border-t border-gray-700">
          <td class="px-3 py-2 align-top border border-gray-700 text-sm font-semibold">${turnNo}</td>
          <td class="px-3 py-2 align-top border border-gray-700"><pre class="text-xs whitespace-pre-wrap break-words mb-0">${playerAction}</pre></td>
          <td class="px-3 py-2 align-top border border-gray-700"><pre class="text-xs whitespace-pre-wrap break-words mb-0">${aiNarration}</pre></td>
          <td class="px-3 py-2 align-top border border-gray-700">${language}</td>
          <td class="px-3 py-2 align-top border border-gray-700">${created}</td>
        </tr>`;
    })
    .join('');

  entriesBodyEl.innerHTML = rows;
}

async function loadTurnLog(event) {
  event?.preventDefault?.();
  if (fetchingTurns) return;
  fetchingTurns = true;
  if (reloadBtn) reloadBtn.disabled = true;
  updateSummary('Turns werden geladen...');
  updateStatus('Turns laden...', 'ok');

  try {
    let sessionId = getQuerySessionId() || fallbackSessionId();
    if (!sessionId && sessionHelper && typeof sessionHelper.fetchActiveSession === 'function') {
      updateStatus('Aktive Sitzung wird ermittelt...', 'ok');
      const body = await sessionHelper.fetchActiveSession(statusEl, { forceRefresh: true });
      sessionId = body?.chastity_session?.session_id || body?.chastity_session?.id;
    }

    if (!sessionId) {
      throw new Error('Session-ID konnte nicht ermittelt werden.');
    }

    if (sessionIdEl) {
      sessionIdEl.textContent = sessionId;
      if (sessionIdEl.dataset) {
        sessionIdEl.dataset.initialSessionId = sessionId;
      }
    }

    const response = await fetch(`/api/v1/sessions/${encodeURIComponent(sessionId)}/turns`);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = body?.detail || 'Turns konnten nicht geladen werden.';
      throw new Error(message);
    }

    const turns = Array.isArray(body.turns) ? body.turns : [];
    const sortedTurns = [...turns].sort((a, b) => Number(b?.turn_no || 0) - Number(a?.turn_no || 0));
    renderTurnRows(sortedTurns);
    const summaryText = sortedTurns.length ? `${sortedTurns.length} Turns geladen.` : 'Keine Turns gefunden.';
    updateSummary(summaryText);
    updateStatus(sortedTurns.length ? 'Turns geladen.' : 'Keine Turns vorhanden.', 'ok');
  } catch (error) {
    const message = error?.message || 'Turns konnten nicht geladen werden.';
    clearEntries(message);
    updateSummary(message);
    updateStatus(message, 'err');
  } finally {
    fetchingTurns = false;
    if (reloadBtn) reloadBtn.disabled = false;
  }
}

if (reloadBtn) {
  reloadBtn.addEventListener('click', (event) => {
    event.preventDefault();
    loadTurnLog();
  });
}

document.addEventListener('DOMContentLoaded', () => {
  loadTurnLog();
});
