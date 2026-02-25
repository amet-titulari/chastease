document.addEventListener('DOMContentLoaded', function () {
  const loginBtn = document.getElementById('loginBtn');
  const registerBtn = document.getElementById('registerBtn');
  const userInfo = document.getElementById('userInfo');

  if (loginBtn) loginBtn.addEventListener('click', () => {
    chastease_common.setStatus(userInfo, 'Login clicked');
  });
  if (registerBtn) registerBtn.addEventListener('click', () => {
    chastease_common.setStatus(userInfo, 'Register clicked');
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
  chastease_common.setStatus(document.getElementById('userInfo'), `Logged in as ${username}`);
  try { localStorage.setItem(chastease_common.authStorageKey(), JSON.stringify({ user_id: username, auth_token: 'devtoken' })); } catch (e) {}
}

function handleRegisterClick() {
  chastease_common.setStatus(document.getElementById('userInfo'), 'Register flow not implemented (demo)');
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
