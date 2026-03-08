document.addEventListener('DOMContentLoaded', function () {
  const consentBtn = document.getElementById('consentBtn');
  const consentInput = document.getElementById('consentInput');
  const status = document.getElementById('status');
  const contractBox = document.getElementById('contractBox');
  const consentBox = document.getElementById('consentBox');
  const consentRequired = document.getElementById('consentRequired');
  const contractChangesBox = document.getElementById('contractChangesBox');
  const contractChangesList = document.getElementById('contractChangesList');
  const contractDiffPreview = document.getElementById('contractDiffPreview');
  const contractDiffDetails = document.getElementById('contractDiffDetails');
  let setupSessionId = null;

  function renderContractTechnicalInfo(generated) {
    if (!contractChangesBox || !contractChangesList || !contractDiffPreview || !contractDiffDetails) return;
    const technical = (generated && typeof generated === 'object' && generated.technical_info && typeof generated.technical_info === 'object')
      ? generated.technical_info
      : null;
    const edits = Array.isArray(technical?.ai_edits) ? technical.ai_edits : [];
    const diffText = String(technical?.diff_preview || '').trim();

    if (!edits.length && !diffText) {
      contractChangesBox.classList.add('hidden');
      contractChangesList.innerHTML = '';
      contractDiffPreview.textContent = '';
      return;
    }

    contractChangesList.innerHTML = '';
    edits.forEach((edit) => {
      const li = document.createElement('li');
      const target = String(edit?.target || '-');
      const op = String(edit?.op || '-');
      const before = String(edit?.before_preview || '').trim();
      const after = String(edit?.after_preview || '').trim();
      li.textContent = `${target} (${op})${before || after ? `: "${before || '...'}" -> "${after || '...'}"` : ''}`;
      contractChangesList.appendChild(li);
    });

    contractDiffPreview.textContent = diffText || 'Kein Diff verfuegbar.';
    contractDiffDetails.open = Boolean(diffText);
    contractChangesBox.classList.remove('hidden');
  }

  function renderMarkdown(node, value) {
    if (!node) return;
    const text = String(value || '');
    const renderer = window.chastease_common?.markdownToHtml;
    if (typeof renderer === 'function') {
      node.innerHTML = renderer(text);
      dedupeAdjacentContractHeadings(node);
      return;
    }
    node.textContent = text;
  }

  function dedupeAdjacentContractHeadings(node) {
    if (!node) return;
    const headings = Array.from(node.querySelectorAll('h1, h2, h3, h4'));
    let previousHeading = null;
    headings.forEach((heading) => {
      if (
        previousHeading
        && previousHeading.tagName === heading.tagName
        && String(previousHeading.textContent || '').trim() === String(heading.textContent || '').trim()
      ) {
        let onlyWhitespaceBetween = true;
        let cursor = previousHeading.nextSibling;
        while (cursor && cursor !== heading) {
          if (
            (cursor.nodeType === Node.TEXT_NODE && String(cursor.textContent || '').trim())
            || (cursor.nodeType === Node.ELEMENT_NODE && String(cursor.textContent || '').trim())
          ) {
            onlyWhitespaceBetween = false;
            break;
          }
          cursor = cursor.nextSibling;
        }
        if (onlyWhitespaceBetween) {
          heading.remove();
          return;
        }
      }
      previousHeading = heading;
    });
  }

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

    renderMarkdown(contractBox, generated.text);
    renderContractTechnicalInfo(generated);

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
      if (body.contract_text) renderMarkdown(contractBox, body.contract_text);
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
