document.addEventListener('DOMContentLoaded', function () {
  const consentBtn = document.getElementById('consentBtn');
  const consentInput = document.getElementById('consentInput');
  const status = document.getElementById('status');
  const contractBox = document.getElementById('contractBox');
  const consentBox = document.getElementById('consentBox');
  const consentRequired = document.getElementById('consentRequired');
  let setupSessionId = null;

  async function apiCall(method, path, payload) {
    const res = await fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: payload ? JSON.stringify(payload) : undefined,
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body?.detail || `HTTP ${res.status}`);
    return body;
  }

  async function loadContract() {
    chastease_common.setStatus(status, 'Lade Session...');

    let active = null;
    if (window.chastease_session && typeof window.chastease_session.fetchActiveSession === 'function') {
      active = await window.chastease_session.fetchActiveSession(status);
    } else {
      const auth = getStoredAuth();
      if (!auth) {
        chastease_common.setStatus(status, 'Login fehlt', 'err');
        return;
      }
      active = await apiCall(
        'GET',
        `/api/v1/sessions/active?user_id=${encodeURIComponent(auth.user_id)}&auth_token=${encodeURIComponent(auth.auth_token)}`,
      );
    }

    if (!active) return;

    setupSessionId = active.setup_session_id || null;
    let generated = ((active.chastity_session || {}).policy || {}).generated_contract || null;
    if ((!generated || !generated.text) && setupSessionId) {
      const setupData = await apiCall('GET', `/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}`);
      generated = ((setupData.policy_preview || {}).generated_contract) || null;
    }

    if (!generated || !generated.text) {
      contractBox.textContent = 'Kein Vertragsentwurf vorhanden. Bitte Setup abschliessen.';
      chastease_common.setStatus(status, 'Kein Vertrag vorhanden', 'err');
      return;
    }

    contractBox.textContent = String(generated.text);

    const consent = generated.consent || {};
    const required = String(consent.required_text || 'Ich akzeptiere diesen Vertrag');
    if (consent.accepted) {
      chastease_common.setStatus(status, `Vertrag digital akzeptiert: ${consent.accepted_at || ''}`);
      if (consentBox) consentBox.classList.add('hidden');
      return;
    }

    if (consentBox) consentBox.classList.remove('hidden');
    if (consentRequired) consentRequired.textContent = required;
    if (consentInput) consentInput.value = required;
  }

  function getStoredAuth() {
    if (window.chastease_session && typeof window.chastease_session.getStoredAuth === 'function') {
      return window.chastease_session.getStoredAuth();
    }
    try {
      const raw = localStorage.getItem(chastease_common.authStorageKey());
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || !parsed.user_id || !parsed.auth_token) return null;
      return parsed;
    } catch (_e) {
      return null;
    }
  }

  async function submitConsent() {
    const val = String(consentInput?.value || '').trim();
    if (!val) return chastease_common.setStatus(status, 'Bitte Text eingeben', 'err');
    if (!setupSessionId) return chastease_common.setStatus(status, 'Setup-Session fehlt', 'err');

    try {
      chastease_common.setStatus(status, 'Sende Consent...');
      const auth = getStoredAuth();
      if (!auth) throw new Error('Login fehlt');
      const payload = {
        user_id: auth.user_id,
        auth_token: auth.auth_token,
        consent_text: val,
      };
      const body = await apiCall('POST', `/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}/contract/accept`, payload);
      contractBox.textContent = String(body.contract_text || contractBox.textContent);
      chastease_common.setStatus(status, `Consent akzeptiert: ${body?.consent?.accepted_at || ''}`);
      if (consentBox) consentBox.classList.add('hidden');
    } catch (err) {
      chastease_common.setStatus(status, String(err?.message || err), 'err');
    }
  }

  if (consentBtn) {
    consentBtn.addEventListener('click', submitConsent);
  }

  loadContract().catch((e) => chastease_common.setStatus(status, String(e?.message || e), 'err'));
});

// expose simple API
function acceptContractConsent() {
  const input = document.getElementById('consentInput');
  const status = document.getElementById('status');
  const val = input ? String(input.value || '').trim() : '';
  if (!val) return chastease_common.setStatus(status, 'Bitte Text eingeben', 'err');
  chastease_common.setStatus(status, 'Vertrag akzeptiert');
}

window.acceptContractConsent = acceptContractConsent;
window.chastease_contract = { acceptContractConsent };
