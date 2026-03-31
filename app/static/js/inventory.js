(() => {
  const uiCommon = window.ChasteaseUiCommon || {};
  const runtime = window.ChasteaseUiRuntime || {};

  const statusEl = document.getElementById("im-status");
  const formPanelEl = document.getElementById("im-form-panel");
  const createToggleRowEl = document.getElementById("im-create-toggle-row");
  const formEl = document.getElementById("im-form");
  const editIdEl = document.getElementById("im-edit-id");
  const nameEl = document.getElementById("im-name");
  const keyEl = document.getElementById("im-key");
  const categoryEl = document.getElementById("im-category");
  const tagsEl = document.getElementById("im-tags");
  const descriptionEl = document.getElementById("im-description");
  const activeEl = document.getElementById("im-is-active");
  const formTitleEl = document.getElementById("im-form-title");
  const saveBtnEl = document.getElementById("im-save-btn");
  const cancelBtnEl = document.getElementById("im-cancel-btn");
  const newBtnEl = document.getElementById("im-new-btn");
  const importInputEl = document.getElementById("im-import-input");
  const importZoneEl = document.getElementById("im-import-zone");
  const exportAllBtnEl = document.getElementById("im-export-all-btn");

  function escapeHtml(value) {
    if (typeof uiCommon.escapeHtml === "function") return uiCommon.escapeHtml(value);
    return String(value ?? "");
  }

  function status(message, isError = false) {
    if (!statusEl) return;
    statusEl.innerHTML = `<p class="status ${isError ? "error" : "success"}">${escapeHtml(message)}</p>`;
    window.setTimeout(() => {
      if (statusEl) statusEl.innerHTML = "";
    }, 4000);
  }

  async function fetchJson(url, options = {}) {
    if (typeof runtime.jsonRequest === "function") {
      return runtime.jsonRequest(url, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
    }
    const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
    const data = await response.json();
    if (!response.ok) throw new Error(data?.detail || response.statusText);
    return data;
  }

  function showForm() {
    if (formPanelEl) formPanelEl.style.display = "";
    if (createToggleRowEl) createToggleRowEl.style.display = "none";
  }

  function hideForm() {
    if (formPanelEl) formPanelEl.style.display = "none";
    if (createToggleRowEl) createToggleRowEl.style.display = "flex";
  }

  function autoKey() {
    if (!editIdEl || !keyEl || !nameEl || editIdEl.value) return;
    keyEl.value = nameEl.value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  }

  function reloadList() {
    if (window.htmx) {
      window.htmx.ajax("GET", "/inventory/partials/list", { target: "#im-list", swap: "outerHTML" });
      return;
    }
    const list = document.getElementById("im-list");
    if (list) list.innerHTML = '<div class="empty-hint">Liste konnte nicht aktualisiert werden.</div>';
  }

  function resetInlineEditors() {
    document.querySelectorAll(".inventory-inline-editor").forEach((node) => node.remove());
  }

  function resetForm() {
    if (editIdEl) editIdEl.value = "";
    formEl?.reset();
    if (activeEl) activeEl.checked = true;
    if (formTitleEl) formTitleEl.textContent = "Neues Item erstellen";
    if (saveBtnEl) saveBtnEl.textContent = "Item speichern";
    if (cancelBtnEl) cancelBtnEl.style.display = "none";
    hideForm();
  }

  function collectInlinePayload(form) {
    return {
      key: form.querySelector('[data-im-field="key"]').value.trim(),
      name: form.querySelector('[data-im-field="name"]').value.trim(),
      category: form.querySelector('[data-im-field="category"]').value.trim() || null,
      description: form.querySelector('[data-im-field="description"]').value.trim() || null,
      tags: form.querySelector('[data-im-field="tags"]').value.split(",").map((value) => value.trim()).filter(Boolean),
      is_active: form.querySelector('[data-im-field="is_active"]').checked,
    };
  }

  async function startEdit(itemId) {
    try {
      const item = await fetchJson(`/api/inventory/items/${itemId}`);
      hideForm();
      resetInlineEditors();
      const card = document.querySelector(`.inventory-card[data-id="${itemId}"]`);
      if (!card) throw new Error("Item-Karte nicht gefunden");
      const host = document.createElement("div");
      host.className = "inventory-inline-editor";
      host.innerHTML = `
        <form class="stack" data-im-inline-form="${item.id}">
          <div class="inventory-inline-grid">
            <label>Name *
              <input data-im-field="name" type="text" maxlength="160" required value="${escapeHtml(item.name || "")}" />
            </label>
            <label>Key
              <input data-im-field="key" type="text" maxlength="120" required value="${escapeHtml(item.key || "")}" />
            </label>
            <label>Kategorie
              <input data-im-field="category" type="text" maxlength="80" value="${escapeHtml(item.category || "")}" />
            </label>
            <label>Tags
              <input data-im-field="tags" type="text" value="${escapeHtml((item.tags || []).join(", "))}" />
            </label>
            <label>Beschreibung
              <textarea data-im-field="description" rows="3" maxlength="4000">${escapeHtml(item.description || "")}</textarea>
            </label>
          </div>
          <label style="display:flex;gap:0.45rem;align-items:center;">
            <input data-im-field="is_active" type="checkbox" ${item.is_active ? "checked" : ""} />
            Item ist aktiv
          </label>
          <div class="inventory-inline-actions">
            <button type="submit" data-im-inline-save="${item.id}">Speichern</button>
            <button type="button" class="ghost" data-im-inline-cancel="${item.id}">Abbrechen</button>
            <span class="inventory-inline-note">Direkt in der Kachel bearbeiten.</span>
          </div>
        </form>
      `;
      card.appendChild(host);
      host.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (err) {
      status(`Fehler beim Laden: ${String(err)}`, true);
    }
  }

  async function deleteItem(id, name) {
    if (!window.confirm(`Item "${name}" wirklich loeschen?`)) return;
    try {
      await fetchJson(`/api/inventory/items/${id}`, { method: "DELETE" });
      status(`Item "${name}" geloescht.`);
      reloadList();
    } catch (err) {
      status(`Fehler beim Loeschen: ${err.message}`, true);
    }
  }

  function exportOne(id, name) {
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || `item-${id}`;
    const anchor = document.createElement("a");
    anchor.href = `/api/inventory/items/${id}/export`;
    anchor.download = `item-${slug}.json`;
    anchor.click();
  }

  async function importFile(file) {
    let raw;
    try {
      raw = JSON.parse(await file.text());
    } catch (_) {
      status(`${file.name}: Ungueltiges JSON.`, true);
      return 0;
    }
    const cards = raw.kind === "item_collection" && Array.isArray(raw.items) ? raw.items : [raw];
    let imported = 0;
    for (const card of cards) {
      try {
        await fetchJson("/api/inventory/items/import", { method: "POST", body: JSON.stringify({ card }) });
        imported += 1;
      } catch (err) {
        const name = card && card.name ? String(card.name) : "?";
        status(`Fehler beim Importieren von "${name}": ${err.message}`, true);
      }
    }
    return imported;
  }

  async function handleImportFiles(files) {
    let total = 0;
    for (const file of files) {
      total += await importFile(file);
    }
    if (total > 0) {
      status(`${total} Item(s) importiert.`);
      reloadList();
    }
  }

  async function submitCreate(event) {
    event.preventDefault();
    const payload = {
      key: keyEl?.value.trim(),
      name: nameEl?.value.trim(),
      category: categoryEl?.value.trim() || null,
      description: descriptionEl?.value.trim() || null,
      tags: tagsEl?.value.split(",").map((value) => value.trim()).filter(Boolean) || [],
      is_active: activeEl?.checked ?? true,
    };

    if (saveBtnEl) saveBtnEl.disabled = true;
    try {
      await fetchJson("/api/inventory/items", { method: "POST", body: JSON.stringify(payload) });
      status(`Item "${payload.name}" erstellt.`);
      resetForm();
      reloadList();
    } catch (err) {
      status(`Fehler: ${err.message}`, true);
    } finally {
      if (saveBtnEl) saveBtnEl.disabled = false;
    }
  }

  function bindToolbar() {
    exportAllBtnEl?.addEventListener("click", () => {
      const anchor = document.createElement("a");
      anchor.href = "/api/inventory/items/export";
      anchor.download = "items-export.json";
      anchor.click();
    });

    importInputEl?.addEventListener("change", async () => {
      await handleImportFiles(importInputEl.files || []);
      importInputEl.value = "";
    });

    importZoneEl?.addEventListener("dragover", (event) => {
      event.preventDefault();
      importZoneEl.classList.add("drag-over");
    });
    importZoneEl?.addEventListener("dragleave", () => importZoneEl.classList.remove("drag-over"));
    importZoneEl?.addEventListener("drop", async (event) => {
      event.preventDefault();
      importZoneEl.classList.remove("drag-over");
      const files = [...(event.dataTransfer?.files || [])].filter((file) => file.name.endsWith(".json"));
      await handleImportFiles(files);
    });
  }

  function bindForm() {
    nameEl?.addEventListener("input", autoKey);
    formEl?.addEventListener("submit", submitCreate);
    cancelBtnEl?.addEventListener("click", resetForm);
    newBtnEl?.addEventListener("click", () => {
      resetForm();
      showForm();
      formPanelEl?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function bindDelegatedActions() {
    document.addEventListener("click", (event) => {
      const trigger = event.target.closest("[data-im-action]");
      if (trigger) {
        const action = String(trigger.getAttribute("data-im-action") || "").trim();
        const itemId = Number.parseInt(trigger.getAttribute("data-item-id") || "", 10);
        const itemName = trigger.getAttribute("data-item-name") || "";
        if (!Number.isFinite(itemId) || itemId <= 0) return;
        if (action === "edit") {
          startEdit(itemId);
          return;
        }
        if (action === "export") {
          if (trigger.tagName !== "A") exportOne(itemId, itemName);
          return;
        }
        if (action === "delete") {
          deleteItem(itemId, itemName);
        }
        return;
      }

      const cancelTrigger = event.target.closest("[data-im-inline-cancel]");
      if (cancelTrigger) {
        cancelTrigger.closest(".inventory-inline-editor")?.remove();
      }
    });

    document.addEventListener("submit", async (event) => {
      const form = event.target.closest("[data-im-inline-form]");
      if (!form) return;
      event.preventDefault();
      const itemId = Number.parseInt(form.getAttribute("data-im-inline-form") || "", 10);
      if (!Number.isFinite(itemId) || itemId <= 0) return;
      const payload = collectInlinePayload(form);
      const saveBtn = form.querySelector("[data-im-inline-save]");
      if (saveBtn) saveBtn.disabled = true;
      try {
        await fetchJson(`/api/inventory/items/${itemId}`, { method: "PUT", body: JSON.stringify(payload) });
        status(`Item "${payload.name}" aktualisiert.`);
        reloadList();
      } catch (err) {
        status(`Fehler: ${err.message}`, true);
        if (saveBtn) saveBtn.disabled = false;
      }
    });
  }

  function boot() {
    bindToolbar();
    bindForm();
    bindDelegatedActions();
  }

  window.imStartEdit = startEdit;
  window.imExportOne = exportOne;
  window.imAutoKey = autoKey;

  boot();
})();
