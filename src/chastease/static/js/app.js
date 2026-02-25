document.addEventListener('DOMContentLoaded', function () {
  const loginBtn = document.getElementById('loginBtn');
  const registerBtn = document.getElementById('registerBtn');
  const userInfo = document.getElementById('userInfo');

  // set mode from URL param `mode=register` or `mode=login` (default: login)
  const urlParams = new URLSearchParams(window.location.search);
  const mode = (urlParams.get('mode') || 'login').toLowerCase();
  setAuthMode(mode);

  if (loginBtn) loginBtn.addEventListener('click', () => {
    handleLoginClick();
  });
  if (registerBtn) registerBtn.addEventListener('click', () => {
    handleRegisterClick();
  });
});

// App-level interactions
function toggleDashboard() {
  const el = document.getElementById('dashboard');
  if (!el) return;
  el.classList.toggle('hidden');
}

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
        try { localStorage.setItem(chastease_common.authStorageKey(), JSON.stringify({ user_id: body.user_id, auth_token: body.auth_token })); } catch (e) {}
        chastease_common.setStatus(infoEl, `Logged in as ${body.user_id}`);
      } else {
        chastease_common.setStatus(infoEl, body.detail || 'Login failed', 'err');
      }
    })
    .catch(err => chastease_common.setStatus(infoEl, 'Login request failed', 'err'));
}

function handleRegisterClick() {
  const username = document.getElementById('reg_username')?.value || '';
  const email = document.getElementById('email')?.value || `${username}@example.com`;
  const password = document.getElementById('reg_password')?.value || '';
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
        try { localStorage.setItem(chastease_common.authStorageKey(), JSON.stringify({ user_id: body.user_id, auth_token: body.auth_token })); } catch (e) {}
        chastease_common.setStatus(infoEl, `Registered as ${body.user_id}`);
      } else {
        chastease_common.setStatus(infoEl, body.detail || 'Register failed', 'err');
      }
    })
    .catch(err => chastease_common.setStatus(infoEl, 'Register request failed', 'err'));
}

function setAuthMode(mode) {
  const loginSection = document.getElementById('loginSection');
  const registerSection = document.getElementById('registerSection');
  const switchToLogin = document.getElementById('switchToLogin');
  const switchToRegister = document.getElementById('switchToRegister');
  if (mode === 'register') {
    if (loginSection) loginSection.classList.add('hidden');
    if (registerSection) registerSection.classList.remove('hidden');
  } else {
    if (loginSection) loginSection.classList.remove('hidden');
    if (registerSection) registerSection.classList.add('hidden');
  }
}

function startSetup() {
  chastease_common.setStatus(document.getElementById('setupSessionInfo'), 'Setup started (client-side stub)');
}

function discoverTtlockDevices() {
  chastease_common.setStatus(document.getElementById('setupSessionInfo'), 'Discovering TTLock devices (stub)');
}

// expose globally for onclick handlers in templates
window.chastease_app = {
  toggleDashboard,
  openContractPage,
  handleLoginClick,
  handleRegisterClick,
  startSetup,
  discoverTtlockDevices,
};

// attach convenience functions to global scope (backwards compatible)
window.toggleDashboard = toggleDashboard;
window.openContractPage = openContractPage;
window.handleLoginClick = handleLoginClick;
window.handleRegisterClick = handleRegisterClick;
window.startSetup = startSetup;
window.discoverTtlockDevices = discoverTtlockDevices;
