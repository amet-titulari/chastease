// Common utilities used across pages
function authStorageKey() {
  return "chastease_auth_v1";
}

function logoutUser() {
  try { localStorage.removeItem(authStorageKey()); } catch (e) {}
  window.location.href = "/app?mode=login";
}

function setStatus(selector, text, kind = "ok") {
  const node = typeof selector === 'string' ? document.querySelector(selector) : selector;
  if (!node) return;
  node.textContent = text;
  node.className = kind === 'err' ? 'text-red-400' : 'text-green-400';
}

// expose globally
window.chastease_common = { authStorageKey, logoutUser, setStatus };
