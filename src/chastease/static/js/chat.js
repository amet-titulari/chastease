document.addEventListener('DOMContentLoaded', function () {
  const sendBtn = document.getElementById('sendBtn');
  const input = document.getElementById('messageInput');
  const messages = document.getElementById('messages');

  if (sendBtn && input && messages) sendBtn.addEventListener('click', () => {
    const text = input.value.trim();
    if (!text) return;
    const p = document.createElement('div');
    p.className = 'mb-2 p-2 rounded bg-gray-800';
    p.textContent = text;
    messages.appendChild(p);
    input.value = '';
    messages.scrollTop = messages.scrollHeight;
  });
});

// Chat-level functions used by templates
function sendMessage() {
  const input = document.getElementById('messageInput');
  const messages = document.getElementById('messages');
  if (!input || !messages) return;
  const text = input.value.trim();
  if (!text) return;
  const p = document.createElement('div');
  p.className = 'mb-2 p-2 rounded bg-gray-800';
  p.textContent = text;
  messages.appendChild(p);
  input.value = '';
  messages.scrollTop = messages.scrollHeight;
}

function loadAuthFromStorage() {
  try {
    const raw = localStorage.getItem(chastease_common.authStorageKey());
    if (!raw) return chastease_common.setStatus(document.getElementById('status'), 'Kein gespeicherter Login gefunden.', 'err');
    const parsed = JSON.parse(raw);
    document.getElementById('userId').value = parsed.user_id || '';
    document.getElementById('authToken').value = parsed.auth_token || '';
    chastease_common.setStatus(document.getElementById('status'), 'Auth geladen.');
  } catch (e) {
    chastease_common.setStatus(document.getElementById('status'), 'Auth konnte nicht geladen werden.', 'err');
  }
}

// expose globally
window.chastease_chat = { sendMessage, loadAuthFromStorage };
window.sendMessage = sendMessage;
window.loadAuthFromStorage = loadAuthFromStorage;
