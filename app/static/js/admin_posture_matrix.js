(() => {
  const runtime = window.ChasteaseUiRuntime || {};

  let modules = [];
  let items = [];

  const statusEl = document.getElementById("mx-status");
  const headEl = document.getElementById("mx-head-row");
  const bodyEl = document.getElementById("mx-body");
  const searchEl = document.getElementById("mx-search");
  const moduleFilterEl = document.getElementById("mx-module-filter");
  const activeOnlyEl = document.getElementById("mx-active-only");
  const previewModalEl = document.getElementById("mx-preview-modal");
  const previewModalImageEl = document.getElementById("mx-preview-modal-image");
  const previewModalTitleEl = document.getElementById("mx-preview-modal-title");
  const previewModalKeyEl = document.getElementById("mx-preview-modal-key");
  const previewModalCloseEl = document.getElementById("mx-preview-modal-close");
  let modalSequence = [];
  let modalIndex = -1;

  function setStatus(msg, warn = false) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.className = warn ? "mx-status warn" : "mx-status";
  }

  function esc(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  async function api(url, options = {}) {
    if (typeof runtime.jsonRequest === "function") {
      return runtime.jsonRequest(url, options);
    }
    const res = await fetch(url, options);
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(payload.detail || res.statusText || "Fehler");
    return payload;
  }

  function getFilteredItems() {
    const q = (searchEl?.value || "").trim().toLowerCase();
    const moduleKey = moduleFilterEl?.value || "all";
    const activeMode = activeOnlyEl?.value || "all";

    return items.filter((item) => {
      const title = String(item.title || "").toLowerCase();
      const key = String(item.posture_key || "").toLowerCase();
      if (q && !title.includes(q) && !key.includes(q)) return false;
      if (activeMode === "active" && !item.is_active) return false;
      if (activeMode === "inactive" && item.is_active) return false;
      if (moduleKey !== "all") {
        const allowed = Array.isArray(item.allowed_module_keys) ? item.allowed_module_keys : [];
        if (!allowed.includes(moduleKey)) return false;
      }
      return true;
    });
  }

  function renderTable() {
    const headerCells = ["<tr><th>Titel</th><th>Vorschau</th><th>Aktiv</th>"];
    for (const mod of modules) headerCells.push(`<th>${esc(mod.title || mod.key)}</th>`);
    headerCells.push("</tr>");
    if (headEl) headEl.innerHTML = headerCells.join("");

    const visibleItems = getFilteredItems();
    if (bodyEl) {
      bodyEl.innerHTML = visibleItems.map((item) => {
        const allowed = new Set(Array.isArray(item.allowed_module_keys) ? item.allowed_module_keys : []);
        const checks = modules.map((mod) => {
          const checked = allowed.has(mod.key) ? "checked" : "";
          return `<td><input class="mx-check" type="checkbox" data-posture-id="${item.id}" data-module-key="${esc(mod.key)}" ${checked} /></td>`;
        }).join("");

        const previewCell = item.image_url
          ? `
        <td class="mx-preview-cell">
          <button type="button" class="mx-preview-trigger" data-posture-id="${item.id}" data-posture-image="${esc(item.image_url)}" data-posture-title="${esc(item.title)}" data-posture-key="${esc(item.posture_key)}">
            <img class="mx-preview-thumb" src="${esc(item.image_url)}" alt="Preview ${esc(item.title)}" loading="lazy" />
          </button>
          <span class="mx-preview-popover">
            <img src="${esc(item.image_url)}" alt="Posture ${esc(item.title)}" loading="lazy" />
            <span class="mx-preview-key">${esc(item.posture_key)}</span>
            <button type="button" class="mx-preview-open-modal" data-posture-id="${item.id}" data-posture-image="${esc(item.image_url)}" data-posture-title="${esc(item.title)}" data-posture-key="${esc(item.posture_key)}">Grossansicht</button>
          </span>
        </td>`
          : `<td class="mx-preview-cell"><span class="mx-preview-empty">Kein Bild</span></td>`;

        return `<tr data-posture-id="${item.id}"><td><span class="mx-title">${esc(item.title)}</span></td>${previewCell}<td><span class="${item.is_active ? "mx-active" : "mx-inactive"}">${item.is_active ? "Ja" : "Nein"}</span></td>${checks}</tr>`;
      }).join("");
    }

    setStatus(`Ansicht: ${visibleItems.length}/${items.length} Postures sichtbar.`);
  }

  function populateModuleFilter() {
    if (!moduleFilterEl) return;
    moduleFilterEl.innerHTML = '<option value="all">Alle Module</option>' + modules
      .map((mod) => `<option value="${esc(mod.key)}">${esc(mod.title || mod.key)}</option>`)
      .join("");
  }

  async function loadMatrix() {
    setStatus("Matrix wird geladen...");
    const data = await api("/api/inventory/postures/matrix");
    modules = Array.isArray(data.modules) ? data.modules : [];
    items = Array.isArray(data.items) ? data.items : [];
    populateModuleFilter();
    renderTable();
    setStatus(`Matrix geladen: ${items.length} Postures, ${modules.length} Module.`);
  }

  function collectPayload() {
    return items.map((item) => ({
      posture_id: Number(item.id),
      allowed_module_keys: Array.isArray(item.allowed_module_keys) ? item.allowed_module_keys : [],
    }));
  }

  function syncItemFromCheckbox(checkbox) {
    const postureId = Number(checkbox.dataset.postureId || 0);
    const moduleKey = String(checkbox.dataset.moduleKey || "");
    if (!postureId || !moduleKey) return;
    const item = items.find((x) => Number(x.id) === postureId);
    if (!item) return;
    const allowed = new Set(Array.isArray(item.allowed_module_keys) ? item.allowed_module_keys : []);
    if (checkbox.checked) allowed.add(moduleKey);
    else allowed.delete(moduleKey);
    item.allowed_module_keys = [...allowed];
  }

  function applyBulkForVisible(checked) {
    const moduleKey = moduleFilterEl?.value || "all";
    if (moduleKey === "all") {
      setStatus("Bitte zuerst im Modul-Fokus ein konkretes Modul waehlen.", true);
      return;
    }
    const visibleIds = new Set(getFilteredItems().map((item) => Number(item.id)));
    for (const item of items) {
      if (!visibleIds.has(Number(item.id))) continue;
      const allowed = new Set(Array.isArray(item.allowed_module_keys) ? item.allowed_module_keys : []);
      if (checked) allowed.add(moduleKey);
      else allowed.delete(moduleKey);
      item.allowed_module_keys = [...allowed];
    }
    renderTable();
  }

  function isTouchLikeInput() {
    return window.matchMedia("(hover: none), (pointer: coarse)").matches;
  }

  function closeAllInlinePreviews() {
    if (!bodyEl) return;
    for (const cell of bodyEl.querySelectorAll(".mx-preview-cell.is-open")) cell.classList.remove("is-open");
  }

  function visiblePreviewSequence() {
    return getFilteredItems()
      .filter((item) => Boolean(item.image_url))
      .map((item) => ({
        postureId: Number(item.id),
        imageUrl: String(item.image_url || ""),
        title: String(item.title || "Posture"),
        key: String(item.posture_key || ""),
      }));
  }

  function renderPreviewModalEntry(entry) {
    if (!previewModalImageEl || !previewModalTitleEl || !previewModalKeyEl) return;
    previewModalImageEl.src = entry.imageUrl;
    previewModalImageEl.alt = `Posture ${entry.title}`;
    previewModalTitleEl.textContent = entry.title;
    previewModalKeyEl.textContent = entry.key ? `Key: ${entry.key}` : "";
  }

  function openPreviewModalForPosture(postureId, fallbackImage, fallbackTitle, fallbackKey) {
    modalSequence = visiblePreviewSequence();
    modalIndex = modalSequence.findIndex((item) => item.postureId === postureId);
    if (modalIndex < 0) {
      modalSequence = [{ postureId, imageUrl: String(fallbackImage || ""), title: String(fallbackTitle || "Posture"), key: String(fallbackKey || "") }];
      modalIndex = 0;
    }
    renderPreviewModalEntry(modalSequence[modalIndex]);
    previewModalEl?.classList.add("is-open");
    previewModalEl?.setAttribute("aria-hidden", "false");
  }

  function stepPreviewModal(delta) {
    if (!previewModalEl?.classList.contains("is-open")) return;
    if (!Array.isArray(modalSequence) || modalSequence.length <= 1) return;
    modalIndex = (modalIndex + delta + modalSequence.length) % modalSequence.length;
    renderPreviewModalEntry(modalSequence[modalIndex]);
  }

  function closePreviewModal() {
    previewModalEl?.classList.remove("is-open");
    previewModalEl?.setAttribute("aria-hidden", "true");
    if (previewModalImageEl) previewModalImageEl.src = "";
    modalSequence = [];
    modalIndex = -1;
  }

  async function saveMatrix() {
    const payload = { items: collectPayload() };
    try {
      const result = await api("/api/inventory/postures/matrix", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setStatus(`Gespeichert: ${result.updated || 0} aktualisiert, ${result.skipped || 0} uebersprungen.`);
    } catch (err) {
      setStatus(`Speichern fehlgeschlagen: ${err.message}`, true);
    }
  }

  document.getElementById("mx-save")?.addEventListener("click", saveMatrix);
  document.getElementById("mx-reload")?.addEventListener("click", () => {
    loadMatrix().catch((err) => setStatus(`Laden fehlgeschlagen: ${err.message}`, true));
  });
  document.getElementById("mx-bulk-enable")?.addEventListener("click", () => applyBulkForVisible(true));
  document.getElementById("mx-bulk-disable")?.addEventListener("click", () => applyBulkForVisible(false));
  searchEl?.addEventListener("input", renderTable);
  moduleFilterEl?.addEventListener("change", renderTable);
  activeOnlyEl?.addEventListener("change", renderTable);
  bodyEl?.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement) || !target.classList.contains("mx-check")) return;
    syncItemFromCheckbox(target);
  });
  bodyEl?.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const modalButton = target.closest(".mx-preview-open-modal");
    if (modalButton instanceof HTMLButtonElement) {
      openPreviewModalForPosture(
        Number(modalButton.dataset.postureId || 0),
        String(modalButton.dataset.postureImage || ""),
        String(modalButton.dataset.postureTitle || "Posture"),
        String(modalButton.dataset.postureKey || ""),
      );
      return;
    }

    const previewTrigger = target.closest(".mx-preview-trigger");
    if (!(previewTrigger instanceof HTMLButtonElement)) return;
    if (isTouchLikeInput()) {
      const cell = previewTrigger.closest(".mx-preview-cell");
      if (!(cell instanceof HTMLElement)) return;
      const nextOpen = !cell.classList.contains("is-open");
      closeAllInlinePreviews();
      if (nextOpen) cell.classList.add("is-open");
      event.preventDefault();
    }
  });
  previewModalCloseEl?.addEventListener("click", closePreviewModal);
  previewModalEl?.addEventListener("click", (event) => {
    if (event.target === previewModalEl) closePreviewModal();
  });
  document.addEventListener("click", (event) => {
    if (!isTouchLikeInput()) return;
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.closest(".mx-preview-cell")) return;
    closeAllInlinePreviews();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closePreviewModal();
      closeAllInlinePreviews();
      return;
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      stepPreviewModal(1);
      return;
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      stepPreviewModal(-1);
    }
  });

  loadMatrix().catch((err) => setStatus(`Laden fehlgeschlagen: ${err.message}`, true));
})();
