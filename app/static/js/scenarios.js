(() => {
  const uiCommon = window.ChasteaseUiCommon || {};
  const runtime = window.ChasteaseUiRuntime || {};

  let smInventoryCatalog = [];
  let smInventoryAssigned = [];
  let smPhaseCount = 0;
  let smLoreCount = 0;
  let smLoadedPresets = [];

  function escHtml(value) {
    if (typeof uiCommon.escapeHtml === "function") return uiCommon.escapeHtml(value);
    return String(value ?? "");
  }

  function smStatus(msg, isError = false) {
    const el = document.getElementById("sm-status");
    el.innerHTML = `<p class="status ${isError ? "error" : "success"}">${escHtml(msg)}</p>`;
    setTimeout(() => { el.innerHTML = ""; }, 4000);
  }

  async function smFetch(url, options = {}) {
    if (typeof runtime.jsonRequest === "function") {
      return runtime.jsonRequest(url, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
    }
    const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || res.statusText);
    return data;
  }

  function smShowForm() {
    document.getElementById("sm-form-panel").style.display = "";
    document.getElementById("sm-create-toggle-row").style.display = "none";
  }

  function smHideForm() {
    document.getElementById("sm-form-panel").style.display = "none";
    document.getElementById("sm-create-toggle-row").style.display = "flex";
  }

  function smRenderInventoryEditor() {
    const host = document.getElementById("sm-inventory-editor");
    if (!host) return;
    if (!smInventoryCatalog.length) {
      host.innerHTML = '<div class="empty-hint">Keine Items vorhanden. Lege zuerst Items unter Inventar an.</div>';
      return;
    }
    const assignedMap = new Map(smInventoryAssigned.map((x) => [x.item.id, x]));
    host.innerHTML = smInventoryCatalog.map((item) => {
      const assigned = assignedMap.get(item.id);
      return `
        <div class="inventory-row" data-item-id="${item.id}">
          <label class="inv-enabled-wrap" title="Im Scenario aktivieren">
            <input type="checkbox" class="inv-enabled" ${assigned ? "checked" : ""} />
          </label>
          <div class="inv-name">
            <span class="inv-title">${escHtml(item.name)}</span>
            ${item.category ? `<span class="inv-category">${escHtml(item.category)}</span>` : ""}
          </div>
          <input class="inv-qty" type="number" min="1" value="${assigned ? assigned.default_quantity : 1}" />
          <label class="inv-required-wrap">
            <input class="inv-required" type="checkbox" ${assigned?.is_required ? "checked" : ""} />
            <span>Pflicht</span>
          </label>
        </div>`;
    }).join("");
  }

  async function smLoadInventoryCatalog() {
    try {
      const data = await smFetch("/api/inventory/items?include_inactive=false");
      smInventoryCatalog = data.items || [];
      smRenderInventoryEditor();
    } catch (err) {
      const host = document.getElementById("sm-inventory-editor");
      if (host) host.innerHTML = `<div class="empty-hint">Fehler beim Laden der Items: ${escHtml(err.message)}</div>`;
    }
  }

  function smCollectInventoryEntries() {
    return Array.from(document.querySelectorAll("#sm-inventory-editor .inventory-row"))
      .map((row) => {
        const itemId = Number(row.dataset.itemId || 0);
        const enabled = row.querySelector(".inv-enabled")?.checked;
        const qty = Number(row.querySelector(".inv-qty")?.value || 1);
        const required = row.querySelector(".inv-required")?.checked;
        return {
          enabled,
          payload: {
            item_id: itemId,
            is_required: !!required,
            default_quantity: Math.max(1, Math.trunc(qty) || 1),
          },
        };
      })
      .filter((item) => item.enabled)
      .map((item) => item.payload);
  }

  async function smLoadScenarioInventory(scenarioId) {
    smInventoryAssigned = [];
    if (!scenarioId) {
      smRenderInventoryEditor();
      return;
    }
    try {
      const data = await smFetch(`/api/inventory/scenarios/${scenarioId}/items`);
      smInventoryAssigned = data.items || [];
    } catch (_) {
      smInventoryAssigned = [];
    }
    smRenderInventoryEditor();
  }

  function smAutoKey() {
    const id = document.getElementById("sm-edit-id").value;
    if (id) return;
    const title = document.getElementById("sm-title").value;
    document.getElementById("sm-key").value = title.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  }

  function smAddPhase(data = {}) {
    smPhaseCount += 1;
    const idx = smPhaseCount;
    const container = document.getElementById("sm-phases-editor");
    const block = document.createElement("div");
    block.className = "phase-block";
    block.dataset.phaseIdx = idx;
    block.innerHTML = `
      <div class="phase-block-header">
        <span class="phase-block-title">Phase ${idx}</span>
        <button type="button" class="phase-block-remove" data-sm-phase-remove="${idx}" title="Phase entfernen">✕</button>
      </div>
      <label>Titel
        <input class="phase-title" type="text" maxlength="120" value="${escHtml(data.title || "")}" placeholder="z.B. Initiierung" />
      </label>
      <label>Ziel
        <input class="phase-objective" type="text" maxlength="300" value="${escHtml(data.objective || "")}" placeholder="Was soll die Phase erreichen?" />
      </label>
      <label>Führungshinweis <span style="font-weight:400;font-size:0.75rem;color:#7d8da1;">(KI-Anweisung)</span>
        <textarea class="phase-guidance" rows="3" maxlength="2000" placeholder="Wie soll die KI in dieser Phase vorgehen?">${escHtml(data.guidance || "")}</textarea>
      </label>
      <div class="phase-meta-grid">
        <label>Gewichtung
          <input class="phase-weight" type="number" min="0.1" step="0.05" value="${Number.isFinite(Number(data.phase_weight)) ? escHtml(String(data.phase_weight)) : ""}" placeholder="z.B. 1.25" />
        </label>
        <label>Mindestdauer (Stunden)
          <input class="phase-min-hours" type="number" min="1" step="1" value="${Number.isFinite(Number(data.min_phase_duration_hours)) ? escHtml(String(data.min_phase_duration_hours)) : ""}" placeholder="z.B. 72" />
        </label>
      </div>
      <div class="phase-score-section">
        <span class="phase-score-title">Phasen-Zielwerte</span>
        <div class="phase-score-grid">
          <label>Trust
            <input class="phase-score-trust" type="number" min="0" step="1" value="${Number.isFinite(Number(data.score_targets?.trust)) ? escHtml(String(data.score_targets.trust)) : ""}" placeholder="0" />
          </label>
          <label>Obedience
            <input class="phase-score-obedience" type="number" min="0" step="1" value="${Number.isFinite(Number(data.score_targets?.obedience)) ? escHtml(String(data.score_targets.obedience)) : ""}" placeholder="0" />
          </label>
          <label>Resistance
            <input class="phase-score-resistance" type="number" min="0" step="1" value="${Number.isFinite(Number(data.score_targets?.resistance)) ? escHtml(String(data.score_targets.resistance)) : ""}" placeholder="0" />
          </label>
          <label>Favor
            <input class="phase-score-favor" type="number" min="0" step="1" value="${Number.isFinite(Number(data.score_targets?.favor)) ? escHtml(String(data.score_targets.favor)) : ""}" placeholder="0" />
          </label>
          <label>Strictness
            <input class="phase-score-strictness" type="number" min="0" step="1" value="${Number.isFinite(Number(data.score_targets?.strictness)) ? escHtml(String(data.score_targets.strictness)) : ""}" placeholder="0" />
          </label>
          <label>Frustration
            <input class="phase-score-frustration" type="number" min="0" step="1" value="${Number.isFinite(Number(data.score_targets?.frustration)) ? escHtml(String(data.score_targets.frustration)) : ""}" placeholder="0" />
          </label>
          <label>Attachment
            <input class="phase-score-attachment" type="number" min="0" step="1" value="${Number.isFinite(Number(data.score_targets?.attachment)) ? escHtml(String(data.score_targets.attachment)) : ""}" placeholder="0" />
          </label>
        </div>
      </div>`;
    container.appendChild(block);
  }

  function smRemovePhase(idx) {
    const block = document.querySelector(`.phase-block[data-phase-idx="${idx}"]`);
    if (block) block.remove();
  }

  function smCollectPhases() {
    return Array.from(document.querySelectorAll(".phase-block")).map((block, index) => {
      const scoreTargets = {};
      for (const key of ["trust", "obedience", "resistance", "favor", "strictness", "frustration", "attachment"]) {
        const raw = block.querySelector(`.phase-score-${key}`)?.value?.trim();
        if (raw !== "") scoreTargets[key] = Math.max(0, Math.trunc(Number(raw) || 0));
      }
      const phaseWeightRaw = block.querySelector(".phase-weight")?.value?.trim() || "";
      const minHoursRaw = block.querySelector(".phase-min-hours")?.value?.trim() || "";
      const payload = {
        phase_id: `phase_${index + 1}`,
        title: block.querySelector(".phase-title").value.trim(),
        objective: block.querySelector(".phase-objective").value.trim(),
        guidance: block.querySelector(".phase-guidance").value.trim(),
      };
      if (phaseWeightRaw !== "") payload.phase_weight = Math.max(0.1, Number(phaseWeightRaw) || 1);
      if (minHoursRaw !== "") payload.min_phase_duration_hours = Math.max(1, Math.trunc(Number(minHoursRaw) || 1));
      if (Object.keys(scoreTargets).length) payload.score_targets = scoreTargets;
      return payload;
    }).filter((phase) => phase.title || phase.objective);
  }

  function smSetPhases(phases) {
    document.getElementById("sm-phases-editor").innerHTML = "";
    smPhaseCount = 0;
    (phases || []).forEach((phase) => smAddPhase(phase));
  }

  function smAddLore(data = {}) {
    smLoreCount += 1;
    const idx = smLoreCount;
    const container = document.getElementById("sm-lore-editor");
    const block = document.createElement("div");
    block.className = "lore-block";
    block.dataset.loreIdx = idx;
    block.innerHTML = `
      <div class="lore-block-header">
        <span class="lore-block-title">Lore-Eintrag ${idx}</span>
        <button type="button" class="lore-block-remove" data-sm-lore-remove="${idx}" title="Eintrag entfernen">✕</button>
      </div>
      <label>Key <span style="font-weight:400;font-size:0.75rem;color:#7d8da1;">(interner Bezeichner)</span>
        <input class="lore-key" type="text" maxlength="80" value="${escHtml(data.key || "")}" placeholder="z.B. denial-rules" />
      </label>
      <label>Trigger-Wörter <span style="font-weight:400;font-size:0.75rem;color:#7d8da1;">(kommagetrennt)</span>
        <input class="lore-triggers" type="text" value="${escHtml((data.triggers || []).join(", "))}" placeholder="z.B. orgasm, edge, denial" />
      </label>
      <label>Inhalt <span style="font-weight:400;font-size:0.75rem;color:#7d8da1;">(wird der KI als Kontext gegeben)</span>
        <textarea class="lore-content" rows="4" maxlength="3000" placeholder="Was soll die KI über dieses Thema wissen?">${escHtml(data.content || "")}</textarea>
      </label>`;
    container.appendChild(block);
  }

  function smRemoveLore(idx) {
    const block = document.querySelector(`.lore-block[data-lore-idx="${idx}"]`);
    if (block) block.remove();
  }

  function smCollectLore() {
    return Array.from(document.querySelectorAll(".lore-block")).map((block, index) => ({
      key: block.querySelector(".lore-key").value.trim() || `lore_${index + 1}`,
      content: block.querySelector(".lore-content").value.trim(),
      triggers: block.querySelector(".lore-triggers").value.split(",").map((trigger) => trigger.trim()).filter(Boolean),
      priority: 100 - index * 10,
    })).filter((entry) => entry.content);
  }

  function smSetLore(entries) {
    document.getElementById("sm-lore-editor").innerHTML = "";
    smLoreCount = 0;
    (entries || []).forEach((entry) => smAddLore(entry));
  }

  function smReloadList() {
    if (window.htmx) {
      window.htmx.ajax("GET", "/scenarios/partials/list", { target: "#sm-list", swap: "outerHTML" });
      return;
    }
    smStatus("Scenario-Liste konnte nicht aktualisiert werden.", true);
  }

  async function smLoadPresets() {
    try {
      const data = await smFetch("/api/scenarios/presets");
      const grid = document.getElementById("sm-preset-grid");
      const presets = data.items || [];
      smLoadedPresets = presets;
      if (!presets.length) {
        grid.innerHTML = '<div class="empty-hint">Keine Presets.</div>';
        return;
      }
      grid.innerHTML = presets.map((preset, index) =>
        `<button type="button" class="preset-btn" data-sm-preset-index="${index}">
          <span class="preset-btn-name">${escHtml(preset.title)}</span>
          <span class="preset-btn-meta">${(preset.tags || []).slice(0, 3).join(", ")}</span>
        </button>`
      ).join("");
    } catch (_) {
      document.getElementById("sm-preset-grid").innerHTML = '<div class="empty-hint">Fehler beim Laden.</div>';
    }
  }

  function smLoadPreset(preset) {
    smReset();
    smShowForm();
    document.getElementById("sm-title").value = preset.title || "";
    document.getElementById("sm-key").value = preset.key || "";
    document.getElementById("sm-summary").value = preset.summary || "";
    document.getElementById("sm-tags").value = (preset.tags || []).join(", ");
    document.getElementById("sm-behavior-profile").value = preset.behavior_profile ? JSON.stringify(preset.behavior_profile, null, 2) : "";
    smSetPhases(preset.phases || []);
    smSetLore(preset.lorebook || []);
  }

  async function smStartEdit(id) {
    try {
      const s = await smFetch(`/api/scenarios/${id}`);
      smReset();
      smShowForm();
      document.getElementById("sm-edit-id").value = s.id;
      document.getElementById("sm-form-title").textContent = `Scenario bearbeiten: ${s.title}`;
      document.getElementById("sm-title").value = s.title;
      document.getElementById("sm-key").value = s.key;
      document.getElementById("sm-summary").value = s.summary || "";
      document.getElementById("sm-tags").value = (s.tags || []).join(", ");
      document.getElementById("sm-behavior-profile").value = s.behavior_profile ? JSON.stringify(s.behavior_profile, null, 2) : "";
      smSetPhases(s.phases || []);
      smSetLore(s.lorebook || []);
      try {
        await smLoadScenarioInventory(id);
      } catch (_) {
        smStatus("Scenario geöffnet, aber die Item-Zuordnung konnte nicht geladen werden.", true);
      }
      document.getElementById("sm-cancel-btn").style.display = "";
      document.getElementById("sm-form-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      smStatus("Fehler beim Laden: " + err.message, true);
    }
  }

  function smReset() {
    document.getElementById("sm-edit-id").value = "";
    document.getElementById("sm-form-title").textContent = "Neues Scenario erstellen";
    document.getElementById("sm-form").reset();
    smSetPhases([]);
    smSetLore([]);
    smInventoryAssigned = [];
    smRenderInventoryEditor();
    document.getElementById("sm-cancel-btn").style.display = "none";
    smHideForm();
  }

  async function smDelete(id) {
    if (!confirm("Scenario wirklich löschen?")) return;
    try {
      await smFetch(`/api/scenarios/${id}`, { method: "DELETE" });
      smStatus("Scenario gelöscht.");
      smReloadList();
    } catch (err) {
      smStatus("Fehler: " + err.message, true);
    }
  }

  function smExport(id) {
    window.open(`/api/scenarios/${id}/export`, "_blank");
  }

  function bindForm() {
    document.getElementById("sm-title")?.addEventListener("input", smAutoKey);
    document.getElementById("sm-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const id = document.getElementById("sm-edit-id").value;
      const payload = {
        title: document.getElementById("sm-title").value.trim(),
        key: document.getElementById("sm-key").value.trim(),
        summary: document.getElementById("sm-summary").value.trim() || null,
        tags: document.getElementById("sm-tags").value.split(",").map((t) => t.trim()).filter(Boolean),
        phases: smCollectPhases(),
        lorebook: smCollectLore(),
      };
      const behaviorRaw = document.getElementById("sm-behavior-profile").value.trim();
      if (behaviorRaw) {
        try {
          payload.behavior_profile = JSON.parse(behaviorRaw);
        } catch (err) {
          smStatus("Behavior Profile JSON ist ungültig: " + err.message, true);
          return;
        }
      } else {
        payload.behavior_profile = {};
      }
      const saveBtn = document.getElementById("sm-save-btn");
      saveBtn.disabled = true;
      try {
        if (id) {
          const updated = await smFetch(`/api/scenarios/${id}`, { method: "PUT", body: JSON.stringify(payload) });
          await smFetch(`/api/inventory/scenarios/${updated.id}/items`, {
            method: "PUT",
            body: JSON.stringify({ entries: smCollectInventoryEntries() }),
          });
          smStatus("Scenario aktualisiert.");
        } else {
          const created = await smFetch("/api/scenarios", { method: "POST", body: JSON.stringify(payload) });
          await smFetch(`/api/inventory/scenarios/${created.id}/items`, {
            method: "PUT",
            body: JSON.stringify({ entries: smCollectInventoryEntries() }),
          });
          smStatus("Scenario erstellt.");
        }
        smReset();
        smReloadList();
      } catch (err) {
        smStatus("Fehler: " + err.message, true);
      } finally {
        saveBtn.disabled = false;
      }
    });

    document.getElementById("sm-cancel-btn").addEventListener("click", smReset);
    document.getElementById("sm-new-btn").addEventListener("click", () => {
      smReset();
      smShowForm();
      document.getElementById("sm-form-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    document.getElementById("sm-add-phase-btn").addEventListener("click", () => smAddPhase());
    document.getElementById("sm-add-lore-btn").addEventListener("click", () => smAddLore());
  }

  function bindDelegatedActions() {
    document.addEventListener("click", (event) => {
      const presetTrigger = event.target.closest("[data-sm-preset-index]");
      if (presetTrigger) {
        const presetIndex = Number.parseInt(presetTrigger.getAttribute("data-sm-preset-index") || "", 10);
        const preset = smLoadedPresets[presetIndex];
        if (preset) smLoadPreset(preset);
        return;
      }

      const phaseRemoveTrigger = event.target.closest("[data-sm-phase-remove]");
      if (phaseRemoveTrigger) {
        const idx = Number.parseInt(phaseRemoveTrigger.getAttribute("data-sm-phase-remove") || "", 10);
        if (Number.isFinite(idx)) smRemovePhase(idx);
        return;
      }

      const loreRemoveTrigger = event.target.closest("[data-sm-lore-remove]");
      if (loreRemoveTrigger) {
        const idx = Number.parseInt(loreRemoveTrigger.getAttribute("data-sm-lore-remove") || "", 10);
        if (Number.isFinite(idx)) smRemoveLore(idx);
        return;
      }

      const trigger = event.target.closest("[data-sm-action]");
      if (!trigger) return;
      const action = String(trigger.getAttribute("data-sm-action") || "").trim();
      const scenarioId = Number.parseInt(trigger.getAttribute("data-scenario-id") || "", 10);
      if (!Number.isFinite(scenarioId) || scenarioId <= 0) return;

      if (action === "edit") {
        smStartEdit(scenarioId);
        return;
      }
      if (action === "export") {
        smExport(scenarioId);
        return;
      }
      if (action === "delete") {
        smDelete(scenarioId);
      }
    });
  }

  function bindImport() {
    const input = document.getElementById("sm-import-input");
    const importZone = document.getElementById("sm-import-zone");

    input.addEventListener("change", async (e) => {
      const files = Array.from(e.target.files);
      for (const file of files) {
        try {
          const text = await file.text();
          const json = JSON.parse(text);
          await smFetch("/api/scenarios/import", { method: "POST", body: JSON.stringify(json) });
          smStatus(`"${file.name}" importiert.`);
        } catch (err) {
          smStatus(`Fehler bei "${file.name}": ${err.message}`, true);
        }
      }
      smReloadList();
      e.target.value = "";
    });

    importZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      importZone.classList.add("drag-over");
    });
    importZone.addEventListener("dragleave", () => importZone.classList.remove("drag-over"));
    importZone.addEventListener("drop", async (e) => {
      e.preventDefault();
      importZone.classList.remove("drag-over");
      for (const file of Array.from(e.dataTransfer.files)) {
        try {
          const text = await file.text();
          const json = JSON.parse(text);
          await smFetch("/api/scenarios/import", { method: "POST", body: JSON.stringify(json) });
          smStatus(`"${file.name}" importiert.`);
        } catch (err) {
          smStatus(`Fehler bei "${file.name}": ${err.message}`, true);
        }
      }
      smReloadList();
    });
  }

  function boot() {
    bindForm();
    bindDelegatedActions();
    bindImport();
    smLoadPresets();
    smLoadInventoryCatalog();
  }

  window.smAutoKey = smAutoKey;
  window.smDelete = smDelete;
  window.smExport = smExport;
  window.smStartEdit = smStartEdit;

  boot();
})();
