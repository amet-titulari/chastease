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

  const lines = source.split('\n');
  const out = [];
  let inCodeBlock = false;
  let listOpen = false;

  function closeListIfOpen() {
    if (listOpen) {
      out.push('</ul>');
      listOpen = false;
    }
  }

  function formatInline(text) {
    let html = escapeHtml(text);
    html = html.replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 rounded bg-gray-800 text-gray-200">$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" class="text-blue-400 underline" target="_blank" rel="noopener noreferrer">$1</a>');
    return html;
  }

  for (const rawLine of lines) {
    const line = String(rawLine || '');
    const trimmed = line.trim();

    if (trimmed.startsWith('```')) {
      closeListIfOpen();
      if (!inCodeBlock) {
        out.push('<pre class="rounded bg-gray-950 border border-gray-700 p-3 overflow-x-auto"><code>');
        inCodeBlock = true;
      } else {
        out.push('</code></pre>');
        inCodeBlock = false;
      }
      continue;
    }

    if (inCodeBlock) {
      out.push(`${escapeHtml(line)}\n`);
      continue;
    }

    if (!trimmed) {
      closeListIfOpen();
      out.push('<div class="h-2"></div>');
      continue;
    }

    const heading = trimmed.match(/^(#{1,3})\s+(.*)$/);
    if (heading) {
      closeListIfOpen();
      const level = heading[1].length;
      const text = formatInline(heading[2]);
      if (level === 1) out.push(`<h1 class="text-xl font-bold mb-2">${text}</h1>`);
      else if (level === 2) out.push(`<h2 class="text-lg font-semibold mb-2">${text}</h2>`);
      else out.push(`<h3 class="text-base font-semibold mb-1">${text}</h3>`);
      continue;
    }

    const listItem = trimmed.match(/^[-*]\s+(.*)$/);
    if (listItem) {
      if (!listOpen) {
        out.push('<ul class="list-disc pl-5 space-y-1">');
        listOpen = true;
      }
      out.push(`<li>${formatInline(listItem[1])}</li>`);
      continue;
    }

    closeListIfOpen();
    out.push(`<p class="leading-relaxed">${formatInline(trimmed)}</p>`);
  }

  closeListIfOpen();
  if (inCodeBlock) out.push('</code></pre>');
  return out.join('');
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
window.chastease_common = { authStorageKey, logoutUser, setStatus, renderNavAuth, markdownToHtml, updatePrimaryNav };

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
