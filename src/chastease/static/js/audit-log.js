const sessionHelper = typeof chastease_session !== 'undefined' ? chastease_session : null;
const statusEl = document.getElementById('auditStatus');
const summaryEl = document.getElementById('auditSummary');
const sessionIdEl = document.getElementById('auditSessionId');
const entriesBodyEl = document.getElementById('auditEntriesBody');
const reloadBtn = document.getElementById('auditReloadBtn');

let isFetchingAudit = false;

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

function clearEntries(message = 'Keine Einträge vorhanden.') {
  if (!entriesBodyEl) return;
  const cell = `<td colspan="4" class="px-3 py-4 text-center text-text-tertiary border border-white/10">${escapeHtml(message)}</td>`;
  entriesBodyEl.innerHTML = `<tr>${cell}</tr>`;
}

function getQuerySessionId() {
  try {
    return new URLSearchParams(window.location.search).get('session_id') || null;
  } catch (error) {
    return null;
  }
}

function initialSessionIdFromDom() {
  if (!sessionIdEl) return null;
  const fallback = sessionIdEl.dataset?.initialSessionId;
  if (fallback) return fallback;
  const raw = sessionIdEl.textContent?.trim();
  if (!raw || raw === '—') return null;
  return raw;
}

function renderEntries(entries) {
  if (!entriesBodyEl) return;
  if (!entries.length) {
    clearEntries('Keine Audit-Einträge gefunden.');
    return;
  }

  const rows = entries
    .map((entry) => {
      const metadata = entry.metadata && Object.keys(entry.metadata).length ? entry.metadata : {};
      const metadataText = JSON.stringify(metadata, null, 2) || '{}';
      const metadataHtml = escapeHtml(metadataText);
      const eventType = escapeHtml(entry.event_type || '-');
      const detail = escapeHtml(entry.detail || '-');
      const timestamp = escapeHtml(new Date(entry.created_at || '').toLocaleString('de-DE') || '-');
      return `        
        <tr class="border-t border-white/10">
          <td class="px-3 py-2 align-top border border-white/10 max-w-[160px] break-words">${eventType}</td>
          <td class="px-3 py-2 align-top border border-white/10">${detail}</td>
          <td class="px-3 py-2 align-top border border-white/10 w-44">
            <pre class="text-xs leading-snug text-text whitespace-pre-wrap break-words mb-0">${metadataHtml}</pre>
          </td>
          <td class="px-3 py-2 align-top border border-white/10 min-w-[140px]">${timestamp}</td>
        </tr>`;
    })
    .join('');

  entriesBodyEl.innerHTML = rows;
}

async function loadAuditEntries(event) {
  event?.preventDefault?.();
  if (isFetchingAudit) return;
  if (!sessionHelper) {
    clearEntries('Session helper fehlt.');
    updateStatus('Session helper nicht verfügbar.', 'err');
    return;
  }

  isFetchingAudit = true;
  if (reloadBtn) reloadBtn.disabled = true;
  updateSummary('Audit-Einträge werden geladen...');
  updateStatus('Audit-Log wird geladen...');

  try {
    const auth = typeof sessionHelper.getStoredAuth === 'function' ? sessionHelper.getStoredAuth() : null;
    if (!auth) {
      throw new Error('Keine Login-Daten gefunden.');
    }

    let sessionId = getQuerySessionId() || initialSessionIdFromDom();
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

    const url = `/api/v1/admin/audit/session/${encodeURIComponent(sessionId)}?auth_token=${encodeURIComponent(auth.auth_token)}`;
    const response = await fetch(url);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const message = body?.detail || 'Audit-Log konnte nicht geladen werden.';
      throw new Error(message);
    }

    const entries = Array.isArray(body.entries) ? body.entries : [];
    renderEntries(entries);
    const summaryText = entries.length ? `${entries.length} Einträge geladen.` : 'Keine Audit-Einträge gefunden.';
    updateSummary(summaryText);
    updateStatus(entries.length ? 'Audit-Log geladen.' : 'Keine Einträge vorhanden.', 'ok');
  } catch (error) {
    const message = error?.message || 'Audit-Log konnte nicht geladen werden.';
    clearEntries(message);
    updateSummary('Audit-Log konnte nicht geladen werden.');
    updateStatus(message, 'err');
  } finally {
    isFetchingAudit = false;
    if (reloadBtn) reloadBtn.disabled = false;
  }
}

if (reloadBtn) {
  reloadBtn.addEventListener('click', (event) => {
    event.preventDefault();
    loadAuditEntries();
  });
}

document.addEventListener('DOMContentLoaded', () => {
  loadAuditEntries();
});
