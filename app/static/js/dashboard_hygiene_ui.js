(() => {
  function renderHygieneQuota(quotaData, options = {}) {
    const quotaEl = document.getElementById("dash-hygiene-quota");
    const nextEl = document.getElementById("dash-hygiene-next-allowed");
    const formatDate = typeof options.formatDate === "function" ? options.formatDate : (value) => String(value ?? "");
    if (!quotaEl || !quotaData) return;
    const limits = quotaData.limits || {};
    const used = quotaData.used || {};
    const remaining = quotaData.remaining || {};
    const nextAllowedAt = quotaData.next_allowed_at || {};
    const formatValue = (value) => (value == null ? "unbegrenzt" : String(value));
    quotaEl.textContent =
      `Kontingent - Tag: ${formatValue(used.daily)}/${formatValue(limits.daily)} (rest ${formatValue(remaining.daily)}), ` +
      `Woche: ${formatValue(used.weekly)}/${formatValue(limits.weekly)} (rest ${formatValue(remaining.weekly)}), ` +
      `Monat: ${formatValue(used.monthly)}/${formatValue(limits.monthly)} (rest ${formatValue(remaining.monthly)})`;

    if (!nextEl) return;
    if (nextAllowedAt.overall) {
      nextEl.textContent = `Naechste Oeffnung erlaubt ab: ${formatDate(nextAllowedAt.overall)}`;
      return;
    }
    nextEl.textContent = "";
  }

  function setHygienePhase(phase, options = {}) {
    document.getElementById("dash-hygiene-open-area")?.classList.toggle("is-hidden", phase === "relock");
    document.getElementById("dash-hygiene-relock-area")?.classList.toggle("is-hidden", phase !== "relock");
    document.getElementById("dash-hygiene-seal-row")?.classList.toggle("is-hidden", !(phase === "relock" && options.usesSeal));
  }

  window.ChasteaseDashboardHygieneUI = {
    renderHygieneQuota,
    setHygienePhase,
  };
})();
