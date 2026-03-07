const extensionBindStatusEl = document.getElementById('extensionBindStatus');
const extensionBindResultEl = document.getElementById('extensionBindResult');

function setExtensionStatus(text, isErr = false) {
  if (!extensionBindStatusEl) return;
  if (typeof chastease_common !== 'undefined') {
    chastease_common.setStatus(extensionBindStatusEl, text, isErr ? 'err' : 'ok');
  } else {
    extensionBindStatusEl.textContent = text;
  }
}

function readMainTokenFromLocation() {
  const hash = String(window.location.hash || '').trim();
  if (hash.startsWith('#mainToken=')) return decodeURIComponent(hash.slice('#mainToken='.length));
  if (hash.startsWith('#')) {
    const raw = hash.slice(1);
    try {
      const parsed = JSON.parse(decodeURIComponent(raw));
      const token = String(parsed?.mainToken || '').trim();
      if (token) return token;
    } catch (_error) {
      // Ignore and continue with query-string fallbacks.
    }
  }
  const query = new URLSearchParams(window.location.search);
  return String(query.get('mainToken') || query.get('main_token') || '').trim();
}

async function bindExtensionMainToken() {
  const mainToken = readMainTokenFromLocation();
  if (!mainToken) {
    setExtensionStatus('Kein Chaster mainToken gefunden.', true);
    if (extensionBindResultEl) {
      extensionBindResultEl.textContent = 'Erwartet wird ein Aufruf der Chaster Extension Main Page mit mainToken.';
    }
    return;
  }

  const auth = (typeof chastease_session !== 'undefined' && chastease_session.getStoredAuth)
    ? chastease_session.getStoredAuth()
    : null;
  const payload = { main_token: mainToken };
  if (auth?.user_id && auth?.auth_token) {
    payload.user_id = auth.user_id;
    payload.auth_token = auth.auth_token;
  }

  try {
    setExtensionStatus('Binde Chaster Extension Session…');
    const response = await fetch('/api/v1/setup/chaster/extension/main-page/bind', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body?.detail || `HTTP ${response.status}`);
    }
    setExtensionStatus('Chaster Extension Session verbunden.');
    if (extensionBindResultEl) {
      extensionBindResultEl.textContent = JSON.stringify(body, null, 2);
    }
  } catch (error) {
    setExtensionStatus(String(error?.message || error), true);
    if (extensionBindResultEl) {
      extensionBindResultEl.textContent = String(error?.message || error);
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  void bindExtensionMainToken();
});
