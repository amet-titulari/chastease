document.addEventListener('DOMContentLoaded', function () {
  const loginBtn = document.getElementById('loginBtn');
  const registerBtn = document.getElementById('registerBtn');
  const userInfo = document.getElementById('userInfo');

  const urlParams = new URLSearchParams(window.location.search);
  const mode = (urlParams.get('mode') || 'login').toLowerCase();
  setAuthMode(mode);

  try {
    if (typeof chastease_common !== 'undefined' && typeof chastease_common.renderNavAuth === 'function') {
      chastease_common.renderNavAuth();
    }
  } catch (e) {}

  if (loginBtn) loginBtn.addEventListener('click', () => handleLoginClick());
  if (registerBtn) registerBtn.addEventListener('click', () => handleRegisterClick());
});

function openContractPage() {
  window.location.href = '/contract';
}

function handleLoginClick() {
  const username = document.getElementById('username')?.value || '';
  const password = document.getElementById('password')?.value || '';
  const infoEl = document.getElementById('userInfo');
  if (!username || !password) {
    chastease_common.setStatus(infoEl, 'Username and password required', 'err');
    return;
  }
  chastease_common.setStatus(infoEl, 'Logging in...');
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
        chastease_common.setStatus(infoEl, body.detail || 'Login failed', 'err');
      }
    })
    .catch(() => chastease_common.setStatus(infoEl, 'Login request failed', 'err'));
}

function handleRegisterClick() {
  const username = document.getElementById('username')?.value || '';
  const email = document.getElementById('email')?.value || `${username}@example.com`;
  const password = document.getElementById('password')?.value || '';
  const passwordRepeat = document.getElementById('passwordRepeat')?.value || '';
  const infoEl = document.getElementById('userInfo');
  if (!username || !password) {
    chastease_common.setStatus(infoEl, 'Username and password required for register', 'err');
    return;
  }
  if (password !== passwordRepeat) {
    chastease_common.setStatus(infoEl, 'Passwords do not match', 'err');
    return;
  }
  chastease_common.setStatus(infoEl, 'Registering...');
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
        chastease_common.setStatus(infoEl, body.detail || 'Register failed', 'err');
      }
    })
    .catch(() => chastease_common.setStatus(infoEl, 'Register request failed', 'err'));
}

function authSuccess(infoEl, body, isRegister = false) {
  persistAuth(body);
  const displayName = (body.display_name || body.username || body.user_id || 'User').trim();
  chastease_common.setStatus(infoEl, `${isRegister ? 'Registered' : 'Logged in'} as ${displayName}`);
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

function setAuthMode(mode) {
  const emailWrap = document.getElementById('emailWrap');
  const passwordRepeatInput = document.getElementById('passwordRepeat');
  const loginBtn = document.getElementById('loginBtn');
  const registerBtn = document.getElementById('registerBtn');
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