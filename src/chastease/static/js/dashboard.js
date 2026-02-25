const sessionHelper = typeof chastease_session !== 'undefined' ? chastease_session : null;
const statusEl = document.getElementById('dashboardStatus');
const activeEl = document.getElementById('activeSessionInfo');
const setupEl = document.getElementById('setupSessionInfo');
const setupBtn = document.getElementById('dashboardSetupBtn');
const refreshBtn = document.getElementById('dashboardRefreshBtn');
const killBtn = document.getElementById('dashboardKillBtn');
let currentSession = null;

function describeActiveSession(body) {
  if (!body) return '—';
  if (body.has_active_session) {
    const sess = body.chastity_session || {};
    return sess.session_id || sess.id || 'active (unknown id)';
  }
  return 'Not active';
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
  if (statusEl) {
    const msg = body?.has_active_session ? 'Active session loaded.' : 'No active session. Use setup to continue.';
    chastease_common.setStatus(statusEl, msg, body?.has_active_session ? 'ok' : 'err');
  }
}

function refreshSession() {
  if (!sessionHelper || typeof sessionHelper.fetchActiveSession !== 'function') {
    if (statusEl) chastease_common.setStatus(statusEl, 'Session helper missing.', 'err');
    return;
  }
  sessionHelper.fetchActiveSession(statusEl).then(body => {
    if (!body) return;
    updateView(body);
  });
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
    .then(res => res.json().then(body => ({ status: res.status, body })))
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

if (refreshBtn) {
  refreshBtn.addEventListener('click', refreshSession);
}

if (setupBtn) {
  setupBtn.addEventListener('click', goToSetup);
}

if (killBtn) {
  killBtn.addEventListener('click', killSession);
}

document.addEventListener('DOMContentLoaded', refreshSession);document.addEventListener('DOMContentLoaded', () => {
  if (typeof chastease_common !== 'undefined' && typeof chastease_common.renderNavAuth === 'function') {
    chastease_common.renderNavAuth();
  }

  const statusEl = document.getElementById('dashboardStatus');
  const activeEl = document.getElementById('activeSessionInfo');
  const setupEl = document.getElementById('setupSessionInfo');
  const setupBtn = document.getElementById('dashboardSetupBtn');
  const killBtn = document.getElementById('dashboardKillBtn');
  const refreshBtn = document.getElementById('dashboardRefreshBtn');

  const sessionHelper = typeof chastease_session !== 'undefined' ? chastease_session : null;

  function describeActiveSession(body) {
    if (!body) return '—';
    if (body.has_active_session) {
      const sess = body.chastity_session || {};
      return sess.id ? `Active session ${sess.id}` : 'Active session present';
    }
    return 'Keine aktive Session';
  }

  function describeSetup(body) {
    if (!body) return '—';
    const status = body.setup_status || 'unknown';
    const identifier = body.setup_session_id || '(no id)';
    return `${status} (${identifier})`;
  }

  function refreshSession() {
    if (!sessionHelper || typeof sessionHelper.fetchActiveSession !== 'function') {
      if (statusEl) chastease_common.setStatus(statusEl, 'Session helper missing.', 'err');
      return;
    }
    sessionHelper.fetchActiveSession(statusEl).then(body => {
      if (!body) {
        if (statusEl) chastease_common.setStatus(statusEl, 'Unable to determine session status.', 'err');
        return;
      }
      if (activeEl) activeEl.textContent = describeActiveSession(body);
      if (setupEl) setupEl.textContent = describeSetup(body);
    });
  }

  if (refreshBtn) {
    refreshBtn.addEventListener('click', refreshSession);
  }

  if (setupBtn) {
    setupBtn.addEventListener('click', () => {
      const current = window.chastease_active_session;
      if (current && current.setup_session_id) {
        window.location.href = `/setup?setup_session_id=${encodeURIComponent(current.setup_session_id)}`;
      } else {
        window.location.href = '/setup';
      }
    });
  }

  if (killBtn) {
    killBtn.addEventListener('click', () => {
      const auth = sessionHelper?.getStoredAuth?.();
      if (!auth) {
        if (statusEl) chastease_common.setStatus(statusEl, 'Kein Login gespeichert.', 'err');
        return;
      }
      if (statusEl) chastease_common.setStatus(statusEl, 'Killing session...');
      fetch(`/api/v1/sessions/active?user_id=${encodeURIComponent(auth.user_id)}&auth_token=${encodeURIComponent(auth.auth_token)}`, { method: 'DELETE' })
        .then(res => res.json().then(body => ({ status: res.status, body })))
        .then(({ status, body }) => {
          if (status === 200) {
            if (statusEl) chastease_common.setStatus(statusEl, body.deleted ? 'Session terminated.' : 'No active session to delete.');
            refreshSession();
          } else if (statusEl) {
            chastease_common.setStatus(statusEl, body.detail || 'Kill failed', 'err');
          }
        })
        .catch(() => {
          if (statusEl) chastease_common.setStatus(statusEl, 'Kill request failed', 'err');
        });
    });
  }

  refreshSession();
});