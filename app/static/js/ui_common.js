(() => {
  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function setText(target, value, fallback = "—") {
    const el = typeof target === "string" ? document.getElementById(target) : target;
    if (!el) return;
    const nextValue = value === null || value === undefined || value === "" ? fallback : value;
    el.textContent = String(nextValue);
  }

  function setHtml(target, html, fallback = "") {
    const el = typeof target === "string" ? document.getElementById(target) : target;
    if (!el) return;
    el.innerHTML = html || fallback;
  }

  function renderPillList(items, emptyText, options = {}) {
    const list = Array.isArray(items) ? items.filter(Boolean) : [];
    const pillClass = String(options.pillClass || "ui-pill").trim();
    const emptyClass = String(options.emptyClass || "ui-empty").trim();
    const esc = typeof options.escapeHtml === "function" ? options.escapeHtml : escapeHtml;
    if (!list.length) {
      return `<span class="${emptyClass}">${esc(emptyText)}</span>`;
    }
    return list.map((item) => `<span class="${pillClass}">${esc(item)}</span>`).join("");
  }

  function fillPillList(target, items, emptyText, options = {}) {
    setHtml(target, renderPillList(items, emptyText, options));
  }

  window.ChasteaseUiCommon = {
    escapeHtml,
    fillPillList,
    renderPillList,
    setHtml,
    setText,
  };
})();
