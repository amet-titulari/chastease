document.addEventListener('DOMContentLoaded', function () {
  const consentBtn = document.getElementById('consentBtn');
  const consentInput = document.getElementById('consentInput');
  const status = document.getElementById('status');

  if (consentBtn && consentInput) consentBtn.addEventListener('click', () => {
    const val = consentInput.value.trim();
    if (val === '') return chastease_common.setStatus(status, 'Bitte Text eingeben', 'err');
    chastease_common.setStatus(status, 'Vertrag akzeptiert');
  });
});

// expose simple API
function acceptContractConsent() {
  const input = document.getElementById('consentInput');
  const status = document.getElementById('status');
  const val = input ? input.value.trim() : '';
  if (!val) return chastease_common.setStatus(status, 'Bitte Text eingeben', 'err');
  chastease_common.setStatus(status, 'Vertrag akzeptiert');
}

window.acceptContractConsent = acceptContractConsent;
window.chastease_contract = { acceptContractConsent };
