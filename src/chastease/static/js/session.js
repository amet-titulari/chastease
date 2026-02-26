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

const ACTIVE_SESSION_CACHE_TTL_MS = 15000;
let activeSessionCache = {
  body: null,
  fetchedAt: 0,
};
let activeSessionInFlight = null;

function getCachedActiveSession() {
  if (!activeSessionCache.body) return null;
  const ageMs = Date.now() - activeSessionCache.fetchedAt;
  if (ageMs > ACTIVE_SESSION_CACHE_TTL_MS) return null;
  return activeSessionCache.body;
}

function invalidateActiveSessionCache() {
  activeSessionCache = { body: null, fetchedAt: 0 };
}

function fetchActiveSession(statusEl, options = {}) {
  return new Promise(resolve => {
    if (typeof chastease_common === 'undefined') {
      resolve(null);
      return;
    }
    const node = getStatusNode(statusEl);
    const forceRefresh = options && options.forceRefresh === true;

    if (!forceRefresh) {
      const cached = getCachedActiveSession();
      if (cached) {
        window.chastease_active_session = cached;
        if (node) chastease_common.setStatus(node, 'Session status loaded.');
        resolve(cached);
        return;
      }
      if (activeSessionInFlight) {
        activeSessionInFlight.then(resolve);
        return;
      }
    }

    const auth = getStoredAuth();
    if (!auth) {
      if (node) chastease_common.setStatus(node, 'No stored login found.', 'err');
      resolve(null);
      return;
    }
    if (node) chastease_common.setStatus(node, 'Checking session status...');
    const url = `/api/v1/sessions/active?user_id=${encodeURIComponent(auth.user_id)}&auth_token=${encodeURIComponent(auth.auth_token)}`;

    activeSessionInFlight = fetch(url)
      .then(res => res.json().then(body => ({ status: res.status, body })))
      .then(({ status, body }) => {
        if (status === 200) {
          activeSessionCache = {
            body,
            fetchedAt: Date.now(),
          };
          window.chastease_active_session = body;
          if (node) chastease_common.setStatus(node, 'Session status loaded.');
          return body;
        }
        invalidateActiveSessionCache();
        if (node) chastease_common.setStatus(node, body.detail || 'Session lookup failed', 'err');
        return null;
      })
      .catch(() => {
        invalidateActiveSessionCache();
        if (node) chastease_common.setStatus(node, 'Session lookup failed', 'err');
        return null;
      })
      .finally(() => {
        activeSessionInFlight = null;
      });

    activeSessionInFlight.then(resolve);
  });
}

window.chastease_session = {
  getStoredAuth,
  fetchActiveSession,
  invalidateActiveSessionCache,
};