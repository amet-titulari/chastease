(() => {
  function formatDateTime(value, locale = "de-DE", fallback = "—") {
    if (!value) return fallback;
    try {
      return new Date(value).toLocaleString(locale);
    } catch (_) {
      return String(value);
    }
  }

  function formatDurationSeconds(secs, fallback = "—") {
    if (secs == null || Number.isNaN(Number(secs))) return fallback;
    const total = Math.max(0, Number(secs));
    const d = Math.floor(total / 86400);
    const h = Math.floor((total % 86400) / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = Math.floor(total % 60);
    return `${d}d ${h}h ${m}m ${s}s`;
  }

  function formatRemaining(isoStr, options = {}) {
    const expiredLabel = options.expiredLabel || "Frei";
    const fallback = options.fallback || "—";
    if (!isoStr) return fallback;
    const diff = new Date(isoStr).getTime() - Date.now();
    if (diff <= 0) return expiredLabel;
    const d = Math.floor(diff / 86400000);
    const h = Math.floor((diff % 86400000) / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    if (d > 0) return `${d}d ${h}h ${m}m`;
    const s = Math.floor((diff % 60000) / 1000);
    if (h > 0) return `${h}h ${m}m ${s}s`;
    return `${m}m ${s}s`;
  }

  async function jsonRequest(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data?.detail || JSON.stringify(data));
    }
    return data;
  }

  function jsonGet(url) {
    return jsonRequest(url);
  }

  function jsonSend(url, method, payload) {
    return jsonRequest(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  function startPolling(task, intervalMs) {
    if (typeof task !== "function") return null;
    return window.setInterval(() => {
      Promise.resolve(task()).catch(() => {});
    }, Math.max(250, Number(intervalMs) || 1000));
  }

  window.ChasteaseUiRuntime = {
    formatDateTime,
    formatDurationSeconds,
    formatRemaining,
    jsonGet,
    jsonRequest,
    jsonSend,
    startPolling,
  };
})();
