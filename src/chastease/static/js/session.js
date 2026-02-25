function getStoredAuth() {
  try {
    const raw = localStorage.getItem(chastease_common.authStorageKey());
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.user_id || !parsed.auth_token) return null;
    return parsed;
  } catch (e) {
    return null;
  }
}

function getStatusNode(preferred) {
  if (preferred) return preferred;
  return document.getElementById('status') || document.getElementById('userInfo');
}

function fetchActiveSession(statusEl) {
  return new Promise(resolve => {
    if (typeof chastease_common === 'undefined') {
      resolve(null);
      return;
    }
    const node = getStatusNode(statusEl);
    const auth = getStoredAuth();
    if (!auth) {
      if (node) chastease_common.setStatus(node, 'No stored login found.', 'err');
      resolve(null);
      return;
    }
    if (node) chastease_common.setStatus(node, 'Checking session status...');
    const url = `/api/v1/sessions/active?user_id=${encodeURIComponent(auth.user_id)}&auth_token=${encodeURIComponent(auth.auth_token)}`;
    fetch(url)
      .then(res => res.json().then(body => ({ status: res.status, body })))
      .then(({ status, body }) => {
        if (status === 200) {
          window.chastease_active_session = body;
          if (node) chastease_common.setStatus(node, 'Session status loaded.');
          resolve(body);
          return;
        }
        if (node) chastease_common.setStatus(node, body.detail || 'Session lookup failed', 'err');
        resolve(null);
      })
      .catch(() => {
        if (node) chastease_common.setStatus(node, 'Session lookup failed', 'err');
        resolve(null);
      });
  });
}

window.chastease_session = {
  getStoredAuth,
  fetchActiveSession,
};