document.addEventListener('DOMContentLoaded', function () {
  const loginBtn = document.getElementById('loginBtn');
  const registerBtn = document.getElementById('registerBtn');
  const chasterLoginBtn = document.getElementById('chasterLoginBtn');
  const userInfo = document.getElementById('userInfo');
  const authCard = document.getElementById('authCard');
  const localAuthWrap = document.getElementById('localAuthWrap');
  const chasterLoginWrap = document.getElementById('chasterLoginWrap');

  const urlParams = new URLSearchParams(window.location.search);
  const mode = (urlParams.get('mode') || 'login').toLowerCase();
  const allowLocalLogin = String(authCard?.dataset?.authAllowLocalLogin || 'true') !== 'false';
  const enableChasterLogin = String(authCard?.dataset?.authEnableChasterLogin || 'true') !== 'false';
  if (localAuthWrap) localAuthWrap.classList.toggle('hidden', !allowLocalLogin);
  if (chasterLoginWrap) chasterLoginWrap.classList.toggle('hidden', !enableChasterLogin);
  setAuthMode(mode);
  handleChasterOAuthCallback(userInfo);

  try {
    if (typeof chastease_common !== 'undefined' && typeof chastease_common.renderNavAuth === 'function') {
      chastease_common.renderNavAuth();
    }
  } catch (e) {}

  if (loginBtn) loginBtn.addEventListener('click', () => handleLoginClick());
  if (registerBtn) registerBtn.addEventListener('click', () => handleRegisterClick());
  if (chasterLoginBtn) chasterLoginBtn.addEventListener('click', () => handleChasterLoginClick());
});

function showFieldError(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.classList.remove('hidden');
}

function clearFieldErrors() {
  document.querySelectorAll('.field-error').forEach(el => {
    el.textContent = '';
    el.classList.add('hidden');
  });
}

function openContractPage() {
  window.location.href = '/contract';
}

function handleLoginClick() {
  const username = document.getElementById('username')?.value || '';
  const password = document.getElementById('password')?.value || '';
  const infoEl = document.getElementById('userInfo');
  clearFieldErrors();
  let hasError = false;
  if (!username) {
    showFieldError('usernameError', 'Username ist erforderlich');
    hasError = true;
  }
  if (!password) {
    showFieldError('passwordError', 'Passwort ist erforderlich');
    hasError = true;
  }
  if (hasError) {
    chastease_common.setStatus(infoEl, 'Bitte alle Pflichtfelder ausfüllen', 'err');
    return;
  }
  chastease_common.setStatus(infoEl, 'Login wird ausgeführt...');
  fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: username, password: password }),
  })
    .then(res => res.json().then(body => ({ status: res.status, body })))
    .then(({ status, body }) => {
      if (status === 200) {
        authSuccess(infoEl, body);
      } else {
        chastease_common.setStatus(infoEl, body.detail || 'Login fehlgeschlagen', 'err');
      }
    })
    .catch(() => chastease_common.setStatus(infoEl, 'Login-Anfrage fehlgeschlagen', 'err'));
}

function handleChasterLoginClick() {
  const infoEl = document.getElementById('userInfo');
  const targetReturn = '/app';
  chastease_common.setStatus(infoEl, 'Weiterleitung zu Chaster OAuth...');
  window.location.href = `/api/v1/auth/chaster/signin?${new URLSearchParams({ return_to: targetReturn }).toString()}`;
}

function handleRegisterClick() {
  const username = document.getElementById('username')?.value || '';
  const email = document.getElementById('email')?.value || `${username}@example.com`;
  const password = document.getElementById('password')?.value || '';
  const passwordRepeat = document.getElementById('passwordRepeat')?.value || '';
  const infoEl = document.getElementById('userInfo');
  clearFieldErrors();
  let hasError = false;
  if (!username) {
    showFieldError('usernameError', 'Username ist erforderlich');
    hasError = true;
  }
  if (!password) {
    showFieldError('passwordError', 'Passwort ist erforderlich');
    hasError = true;
  }
  if (password && password !== passwordRepeat) {
    showFieldError('passwordError', 'Passwörter stimmen nicht überein');
    hasError = true;
  }
  if (hasError) {
    chastease_common.setStatus(infoEl, 'Bitte alle Pflichtfelder korrekt ausfüllen', 'err');
    return;
  }
  chastease_common.setStatus(infoEl, 'Konto wird erstellt...');
  fetch('/api/v1/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: username, email: email, display_name: username, password: password }),
  })
    .then(res => res.json().then(body => ({ status: res.status, body })))
    .then(({ status, body }) => {
      if (status === 200) {
        authSuccess(infoEl, body, true);
      } else {
        chastease_common.setStatus(infoEl, body.detail || 'Registrierung fehlgeschlagen', 'err');
      }
    })
    .catch(() => chastease_common.setStatus(infoEl, 'Registrierungsanfrage fehlgeschlagen', 'err'));
}

function authSuccess(infoEl, body, isRegister = false) {
  persistAuth(body);
  const displayName = (body.display_name || body.username || body.user_id || 'User').trim();
  chastease_common.setStatus(infoEl, `${isRegister ? 'Registriert' : 'Angemeldet'} als ${displayName}`);
  try {
    if (typeof chastease_common !== 'undefined' && typeof chastease_common.renderNavAuth === 'function') {
      chastease_common.renderNavAuth();
    }
  } catch (e) {}
  redirectAfterAuth(infoEl);
}

function persistAuth(body) {
  if (!body || !body.user_id || !body.auth_token) return;
  const payload = {
    user_id: body.user_id,
    auth_token: body.auth_token,
    display_name: (body.display_name || body.username || body.user_id || '').trim(),
    username: body.username,
  };
  try {
    localStorage.setItem(chastease_common.authStorageKey(), JSON.stringify(payload));
  } catch (e) {}
}

function redirectAfterAuth(statusEl) {
  const sessionHelper = typeof chastease_session !== 'undefined' ? chastease_session : null;
  const fetcher = sessionHelper?.fetchActiveSession;
  if (!fetcher) {
    window.location.href = '/setup';
    return;
  }
  fetcher(statusEl)
    .then(body => {
      if (!body) {
        window.location.href = '/setup';
        return;
      }
      const active = body.has_active_session;
      const configured = body.setup_status === 'configured';
      if (active || configured) {
        window.location.href = '/dashboard';
        return;
      }
      const setupId = body.setup_session_id;
      const target = setupId ? `/setup?setup_session_id=${encodeURIComponent(setupId)}` : '/setup';
      window.location.href = target;
    })
    .catch(() => {
      window.location.href = '/setup';
    });
}

function handleChasterOAuthCallback(infoEl) {
  const params = new URLSearchParams(window.location.search);
  const oauthResult = params.get('chaster_oauth');
  if (!oauthResult) return;
  if (oauthResult === 'error') {
    chastease_common.setStatus(infoEl, `Chaster OAuth Fehler: ${params.get('message') || 'unknown'}`, 'err');
    return;
  }
  if (oauthResult !== 'ok') return;
  const user_id = String(params.get('user_id') || '').trim();
  const auth_token = String(params.get('auth_token') || '').trim();
  const display_name = String(params.get('display_name') || '').trim();
  const setup_session_id = String(params.get('setup_session_id') || '').trim();
  if (!user_id || !auth_token) return;
  persistAuth({
    user_id,
    auth_token,
    display_name: display_name || user_id,
    username: display_name || user_id,
    setup_session_id: setup_session_id || null,
  });
  const cleanUrl = new URL(window.location.href);
  cleanUrl.searchParams.delete('chaster_oauth');
  cleanUrl.searchParams.delete('user_id');
  cleanUrl.searchParams.delete('auth_token');
  cleanUrl.searchParams.delete('display_name');
  cleanUrl.searchParams.delete('setup_session_id');
  window.history.replaceState({}, '', cleanUrl.toString());
  chastease_common.setStatus(infoEl, `Angemeldet als ${display_name || user_id}`);
  redirectAfterAuth(infoEl);
}

function setAuthMode(mode) {
  const emailWrap = document.getElementById('emailWrap');
  const passwordRepeatInput = document.getElementById('passwordRepeat');
  const loginBtn = document.getElementById('loginBtn');
  const registerBtn = document.getElementById('registerBtn');
  const authCard = document.getElementById('authCard');
  const allowLocalLogin = String(authCard?.dataset?.authAllowLocalLogin || 'true') !== 'false';
  if (!allowLocalLogin) {
    if (emailWrap) emailWrap.classList.add('hidden');
    if (passwordRepeatInput && passwordRepeatInput.parentElement) passwordRepeatInput.parentElement.classList.add('hidden');
    if (registerBtn) registerBtn.classList.add('hidden');
    if (loginBtn) loginBtn.classList.remove('hidden');
    return;
  }
  if (mode === 'register') {
    if (emailWrap) emailWrap.classList.remove('hidden');
    if (passwordRepeatInput && passwordRepeatInput.parentElement) passwordRepeatInput.parentElement.classList.remove('hidden');
    if (loginBtn) loginBtn.classList.add('hidden');
    if (registerBtn) registerBtn.classList.remove('hidden');
  } else {
    if (emailWrap) emailWrap.classList.add('hidden');
    if (passwordRepeatInput && passwordRepeatInput.parentElement) passwordRepeatInput.parentElement.classList.add('hidden');
    if (loginBtn) loginBtn.classList.remove('hidden');
    if (registerBtn) registerBtn.classList.add('hidden');
  }
}

function startSetup() {
  chastease_common.setStatus(document.getElementById('setupSessionInfo'), 'Setup started (client-side stub)');
}

function discoverTtlockDevices() {
  chastease_common.setStatus(document.getElementById('setupSessionInfo'), 'Discovering TTLock devices (stub)');
}

window.chastease_app = {
  openContractPage,
  handleLoginClick,
  handleRegisterClick,
  startSetup,
  discoverTtlockDevices,
};

window.openContractPage = openContractPage;
window.handleLoginClick = handleLoginClick;
window.handleRegisterClick = handleRegisterClick;
window.startSetup = startSetup;
window.discoverTtlockDevices = discoverTtlockDevices;
