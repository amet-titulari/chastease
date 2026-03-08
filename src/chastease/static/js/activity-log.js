const sessionHelper = typeof chastease_session !== 'undefined' ? chastease_session : null;
const statusEl = document.getElementById('activityLogStatus');
const summaryEl = document.getElementById('activityLogSummary');
const sessionIdEl = document.getElementById('activityLogSessionId');
const entriesBodyEl = document.getElementById('activityLogEntriesBody');
const reloadBtn = document.getElementById('activityLogReloadBtn');

let isFetchingActivity = false;

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

function clearEntries(message = 'Keine Activity-Eintraege vorhanden.') {
  if (!entriesBodyEl) return;
  const cell = `<td colspan="8" class="px-3 py-4 text-center text-text-tertiary border border-white/10">${escapeHtml(message)}</td>`;
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
  if (!raw || raw === '-') return null;
  return raw;
}

function statusBadge(status) {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'success') {
    return '<span class="px-2 py-1 rounded text-xs bg-emerald-900 text-emerald-300">success</span>';
  }
  if (normalized === 'failed') {
    return '<span class="px-2 py-1 rounded text-xs bg-red-900 text-red-300">failed</span>';
  }
  return '<span class="px-2 py-1 rounded text-xs bg-amber-900 text-amber-300">pending</span>';
}

async function resolvePendingAction(sessionId, actionId, resolutionStatus) {
  const label = resolutionStatus === 'success' ? 'erfolgreich' : 'fehlgeschlagen';
  updateStatus(`Pending Action wird als ${label} markiert...`);
  const response = await fetch('/api/v1/chat/actions/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      action_id: actionId,
      resolution_status: resolutionStatus,
      expected_status: 'pending',
    }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body?.detail || 'Pending Action konnte nicht aufgeloest werden.');
  }
  return body;
}

function renderActivities(activities) {
  if (!entriesBodyEl) return;
  if (!activities.length) {
    clearEntries('Keine Activities fuer diese Sitzung.');
    return;
  }

  const rows = activities
    .map((item) => {
      const statusHtml = statusBadge(item.status);
      const actionType = escapeHtml(item.action_type || '-');
      const source = escapeHtml(item.source || '-');
      const turnNo = item.turn_no == null ? '-' : escapeHtml(item.turn_no);
      const detail = escapeHtml(item.detail || '-');
      const payload = item.payload && typeof item.payload === 'object' ? item.payload : {};
      const payloadText = escapeHtml(JSON.stringify(payload, null, 2));
      const created = escapeHtml(new Date(item.created_at || '').toLocaleString('de-DE') || '-');
      const canResolve = String(item.status || '').toLowerCase() === 'pending' && item.action_id;
      const actionControls = canResolve
        ? `
          <div class="flex flex-wrap gap-2">
            <button class="btn-success text-xs js-resolve-action" data-action-id="${escapeHtml(item.action_id)}" data-resolution="success">success</button>
            <button class="btn-danger text-xs js-resolve-action" data-action-id="${escapeHtml(item.action_id)}" data-resolution="failed">failed</button>
          </div>
        `
        : '<span class="text-xs text-text-tertiary">-</span>';
      return `
        <tr class="border-t border-white/10">
          <td class="px-3 py-2 align-top border border-white/10">${statusHtml}</td>
          <td class="px-3 py-2 align-top border border-white/10 max-w-[180px] break-words">${actionType}</td>
          <td class="px-3 py-2 align-top border border-white/10">${source}</td>
          <td class="px-3 py-2 align-top border border-white/10">${turnNo}</td>
          <td class="px-3 py-2 align-top border border-white/10">${detail}</td>
          <td class="px-3 py-2 align-top border border-white/10 w-48"><pre class="text-xs whitespace-pre-wrap break-words mb-0">${payloadText}</pre></td>
          <td class="px-3 py-2 align-top border border-white/10 min-w-[160px]">${actionControls}</td>
          <td class="px-3 py-2 align-top border border-white/10 min-w-[140px]">${created}</td>
        </tr>`;
    })
    .join('');

  entriesBodyEl.innerHTML = rows;
  entriesBodyEl.querySelectorAll('.js-resolve-action').forEach((button) => {
    button.addEventListener('click', async () => {
      const sessionId = getQuerySessionId() || fallbackSessionId();
      const actionId = button.getAttribute('data-action-id') || '';
      const resolution = button.getAttribute('data-resolution') || '';
      if (!sessionId || !actionId || !resolution) return;
      try {
        button.disabled = true;
        await resolvePendingAction(sessionId, actionId, resolution);
        updateStatus(`Pending Action als ${resolution} markiert.`, 'ok');
        loadActivityLog();
      } catch (error) {
        button.disabled = false;
        updateStatus(error?.message || 'Pending Action konnte nicht aufgeloest werden.', 'err');
      }
    });
  });
}

async function loadActivityLog(event) {
  event?.preventDefault?.();
  if (isFetchingActivity) return;
  if (!sessionHelper) {
    clearEntries('Session helper fehlt.');
    updateStatus('Session helper nicht verfuegbar.', 'err');
    return;
  }

  isFetchingActivity = true;
  if (reloadBtn) reloadBtn.disabled = true;
  updateSummary('Activity-Eintraege werden geladen...');
  updateStatus('Activity-Log wird geladen...');

  try {
    const auth = typeof sessionHelper.getStoredAuth === 'function' ? sessionHelper.getStoredAuth() : null;
    if (!auth) {
      throw new Error('Keine Login-Daten gefunden.');
    }

    let sessionId = getQuerySessionId() || fallbackSessionId();
    if (!sessionId && typeof sessionHelper.fetchActiveSession === 'function') {
      updateStatus('Aktive Sitzung wird ermittelt...');
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

    const url = `/api/v1/admin/activity/session/${encodeURIComponent(sessionId)}?auth_token=${encodeURIComponent(auth.auth_token)}`;
    const response = await fetch(url);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = body?.detail || 'Activity-Log konnte nicht geladen werden.';
      throw new Error(message);
    }

    const activities = Array.isArray(body.activities) ? body.activities : [];
    renderActivities(activities);
    const summaryText = activities.length ? `${activities.length} Activities geladen.` : 'Keine Activities gefunden.';
    updateSummary(summaryText);
    updateStatus(activities.length ? 'Activity-Log geladen.' : 'Keine Activities vorhanden.', 'ok');
  } catch (error) {
    const message = error?.message || 'Activity-Log konnte nicht geladen werden.';
    clearEntries(message);
    updateSummary('Activity-Log konnte nicht geladen werden.');
    updateStatus(message, 'err');
  } finally {
    isFetchingActivity = false;
    if (reloadBtn) reloadBtn.disabled = false;
  }
}

if (reloadBtn) {
  reloadBtn.addEventListener('click', (event) => {
    event.preventDefault();
    loadActivityLog();
  });
}

document.addEventListener('DOMContentLoaded', () => {
  loadActivityLog();
});
