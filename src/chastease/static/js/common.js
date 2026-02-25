// Common utilities used across pages
function authStorageKey() {
  return "chastease_auth_v1";
}

function logoutUser() {
  try { localStorage.removeItem(authStorageKey()); } catch (e) {}
  window.location.href = "/app?mode=login";
}

function renderNavAuth() {
  try {
    const raw = localStorage.getItem(authStorageKey());
    const node = document.getElementById('navAuth');
    if (!node) return;
    node.innerHTML = '';
    if (!raw) return;
    const parsed = JSON.parse(raw);
    const niceName = parsed.display_name || parsed.username || parsed.user_display_name || parsed.user_id || '';
    if (!niceName) return;
    const btn = document.createElement('button');
    btn.className = 'px-3 py-1 rounded-md bg-gray-800 hover:bg-gray-700';
    btn.textContent = `Logout (${niceName})`;
    btn.addEventListener('click', () => {
      logoutUser();
    });
    node.appendChild(btn);
  } catch (e) {}
}

function setStatus(selector, text, kind = "ok") {
  const node = typeof selector === 'string' ? document.querySelector(selector) : selector;
  if (!node) return;
  node.textContent = text;
  node.className = kind === 'err' ? 'text-red-400' : 'text-green-400';
}

// expose globally
window.chastease_common = { authStorageKey, logoutUser, setStatus, renderNavAuth };

document.addEventListener('DOMContentLoaded', () => {
  try {
    renderNavAuth();
  } catch (e) {}
});
window.chastease_common.renderNavAuth = renderNavAuth;
