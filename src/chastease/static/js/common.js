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
    syncProtectedNavVisibility();
    const raw = localStorage.getItem(authStorageKey());
    const node = document.getElementById('navAuth');
    if (!node) return;
    node.innerHTML = '';
    if (!raw) return;
    const parsed = JSON.parse(raw);
    const niceName = parsed.display_name || parsed.username || parsed.user_display_name || parsed.user_id || '';
    if (!niceName) return;
    const btn = document.createElement('button');
    btn.className = 'nav-link text-sm';
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
  node.className = kind === 'err' ? 'status-err text-sm' : 'status-ok text-sm';
}

function showToast(message, type = 'success', durationMs = 3000) {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = type === 'error' ? 'toast-error' : 'toast-success';
  toast.textContent = message;
  toast.setAttribute('role', 'status');
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, durationMs);
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function markdownToHtml(markdown) {
  const source = String(markdown || '').replace(/\r\n/g, '\n');
  if (!source.trim()) return '';

  // Use marked.js if available (loaded from vendor)
  if (typeof marked !== 'undefined' && marked.parse) {
    try {
      marked.setOptions({
        breaks: true,
        gfm: true,
        headerIds: false,
        mangle: false,
      });
      // Sanitize: escape any potentially dangerous HTML in the source first
      const raw = marked.parse(source);
      // Wrap in prose styling
      return raw;
    } catch (e) {
      // Fall through to basic fallback
    }
  }

  // Fallback: basic inline formatting if marked.js not loaded
  let html = escapeHtml(source);
  html = html.replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded bg-surface-alt text-text">$1</code>');
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  html = html.replace(/\n/g, '<br>');
  return html;
}

function getStoredAuth() {
  try {
    const raw = localStorage.getItem(authStorageKey());
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.user_id || !parsed.auth_token) return null;
    return parsed;
  } catch (e) {
    return null;
  }
}

async function updatePrimaryNav() {
  const link = document.getElementById('navPrimary');
  if (!link) return;

  const auth = getStoredAuth();
  if (!auth) {
    syncProtectedNavVisibility(false);
    link.textContent = 'App';
    link.setAttribute('href', '/app');
    return;
  }
  syncProtectedNavVisibility(true);

  try {
    const url = `/api/v1/sessions/active?user_id=${encodeURIComponent(auth.user_id)}&auth_token=${encodeURIComponent(auth.auth_token)}`;
    const response = await fetch(url);
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      link.textContent = 'App';
      link.setAttribute('href', '/app');
      return;
    }

    if (body?.has_active_session || body?.setup_status === 'configured') {
      link.textContent = 'Dashboard';
      link.setAttribute('href', '/dashboard');
      return;
    }

    const setupId = body?.setup_session_id;
    link.textContent = 'Setup';
    link.setAttribute('href', setupId ? `/setup?setup_session_id=${encodeURIComponent(setupId)}` : '/setup');
  } catch (e) {
    link.textContent = 'App';
    link.setAttribute('href', '/app');
  }
}

function syncProtectedNavVisibility(forceAuth) {
  const hasAuth = typeof forceAuth === 'boolean' ? forceAuth : Boolean(getStoredAuth());
  const protectedIds = ['navPrimary', 'navChat', 'navContract'];
  protectedIds.forEach((id) => {
    const node = document.getElementById(id);
    if (!node) return;
    node.classList.toggle('hidden', !hasAuth);
  });
}

// expose globally
window.chastease_common = { authStorageKey, logoutUser, setStatus, renderNavAuth, markdownToHtml, updatePrimaryNav, showToast, escapeHtml };

document.addEventListener('DOMContentLoaded', () => {
  try {
    syncProtectedNavVisibility();
  } catch (e) {}
  try {
    renderNavAuth();
  } catch (e) {}
  try {
    updatePrimaryNav();
  } catch (e) {}
});
window.chastease_common.renderNavAuth = renderNavAuth;
window.chastease_common.updatePrimaryNav = updatePrimaryNav;
