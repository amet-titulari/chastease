(() => {
  const STRICTNESS_LABELS = ["", "Sehr sanft", "Sanft", "Ausgewogen", "Streng", "Sehr streng"];
  const uiCommon = window.ChasteaseUiCommon || {};
  const runtime = window.ChasteaseUiRuntime || {};

  let pmAvatarMediaId = null;
  let pmCurrentPersonaId = null;
  let pmCurrentTemplates = [];
  let pmTplImportReplaceMode = false;
  let pmLoadedPresets = [];

  function escHtml(value) {
    if (typeof uiCommon.escapeHtml === "function") return uiCommon.escapeHtml(value);
    return String(value ?? "");
  }

  function pmShowForm() {
    document.getElementById("pm-form-panel").style.display = "";
    document.getElementById("pm-create-toggle-row").style.display = "none";
  }

  function pmHideForm() {
    document.getElementById("pm-form-panel").style.display = "none";
    document.getElementById("pm-create-toggle-row").style.display = "flex";
  }

  function pmUpdateAvatarUi(url) {
    const img = document.getElementById("pm-avatar-preview");
    const empty = document.getElementById("pm-avatar-empty");
    const clearBtn = document.getElementById("pm-avatar-clear");
    if (url) {
      img.src = url;
      img.style.display = "";
      empty.style.display = "none";
      clearBtn.style.display = "inline-flex";
    } else {
      img.removeAttribute("src");
      img.style.display = "none";
      empty.style.display = "";
      clearBtn.style.display = "none";
    }
  }

  async function pmUploadAvatar() {
    const fileInput = document.getElementById("pm-avatar-file");
    const file = fileInput?.files?.[0];
    if (!file) {
      pmStatus("Bitte zuerst ein Bild auswählen.", true);
      return;
    }
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("visibility", "private");

    const btn = document.getElementById("pm-avatar-upload");
    btn.disabled = true;
    const oldText = btn.textContent;
    btn.textContent = "Upload…";
    try {
      const data = await runtime.jsonRequest("/api/media/avatar", { method: "POST", body: form });
      pmAvatarMediaId = data.id;
      document.getElementById("pm-avatar-media-id").value = String(data.id);
      pmUpdateAvatarUi(data.content_url);
      pmStatus("Avatar hochgeladen.");
    } catch (e) {
      pmStatus("Avatar-Upload fehlgeschlagen: " + e.message, true);
    } finally {
      btn.disabled = false;
      btn.textContent = oldText;
    }
  }

  function pmStatus(msg, isError = false) {
    const el = document.getElementById("pm-status");
    el.innerHTML = `<p class="status ${isError ? "error" : "success"}">${escHtml(msg)}</p>`;
    setTimeout(() => { el.innerHTML = ""; }, 4000);
  }

  async function pmFetch(url, options = {}) {
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

  function pmBoolBadge(label, val) {
    return `<span class="tpl-chip">${escHtml(label)}: ${val ? "Ja" : "Nein"}</span>`;
  }

  function pmTplTags(tags) {
    if (!Array.isArray(tags) || !tags.length) return "";
    return tags.slice(0, 6).map((tag) => `<span class="tpl-chip">${escHtml(tag)}</span>`).join("");
  }

  function pmRenderTemplates(items) {
    pmCurrentTemplates = Array.isArray(items) ? items : [];
    const container = document.getElementById("pm-tpl-list");
    if (!pmCurrentPersonaId) {
      container.innerHTML = `<div class="empty-hint" style="padding:0.6rem 0;">Bitte zuerst eine Persona bearbeiten.</div>`;
      return;
    }
    if (!pmCurrentTemplates.length) {
      container.innerHTML = `<div class="empty-hint" style="padding:0.6rem 0;">Keine Vorlagen vorhanden.</div>`;
      return;
    }
    container.innerHTML = pmCurrentTemplates.map((tpl) => {
      const meta = [
        tpl.category ? `Kategorie: ${tpl.category}` : null,
        tpl.deadline_minutes ? `Deadline: ${tpl.deadline_minutes} min` : "Deadline: keine",
        tpl.is_active ? "Aktiv" : "Inaktiv",
      ].filter(Boolean).join(" · ");
      return `
        <div class="tpl-item">
          <div class="tpl-item-main">
            <p class="tpl-item-title">${escHtml(tpl.title)}</p>
            <p class="tpl-item-meta">${escHtml(meta)}</p>
            ${tpl.description ? `<p class="tpl-item-meta">${escHtml(tpl.description)}</p>` : ""}
            <div class="tpl-item-meta">
              ${pmBoolBadge("Fotoverifikation", !!tpl.requires_verification)}
              ${tpl.verification_criteria ? `<span class="tpl-chip">Kriterium: ${escHtml(tpl.verification_criteria)}</span>` : ""}
              ${pmTplTags(tpl.tags)}
            </div>
          </div>
          <div class="tpl-item-actions">
            <button type="button" class="ghost" data-pm-template-action="edit" data-template-id="${tpl.id}">Bearbeiten</button>
            <button type="button" class="warn" data-pm-template-action="delete" data-template-id="${tpl.id}">L&ouml;schen</button>
          </div>
        </div>
      `;
    }).join("");
  }

  async function pmTplLoad() {
    if (!pmCurrentPersonaId) {
      pmRenderTemplates([]);
      return;
    }
    try {
      const data = await pmFetch(`/api/personas/${pmCurrentPersonaId}/task-templates`);
      pmRenderTemplates(data.items || []);
    } catch (e) {
      document.getElementById("pm-tpl-list").innerHTML = `<div class="empty-hint" style="padding:0.6rem 0;">Fehler: ${escHtml(e.message)}</div>`;
    }
  }

  function pmTplResetForm() {
    document.getElementById("pm-tpl-id").value = "";
    document.getElementById("pm-tpl-title").value = "";
    document.getElementById("pm-tpl-description").value = "";
    document.getElementById("pm-tpl-deadline").value = "";
    document.getElementById("pm-tpl-category").value = "";
    document.getElementById("pm-tpl-tags").value = "";
    document.getElementById("pm-tpl-verification").value = "false";
    document.getElementById("pm-tpl-active").value = "true";
    document.getElementById("pm-tpl-criteria").value = "";
    document.getElementById("pm-tpl-save-btn").textContent = "Vorlage speichern";
  }

  function pmTplStartEdit(templateId) {
    const tpl = pmCurrentTemplates.find((item) => item.id === templateId);
    if (!tpl) return;
    document.getElementById("pm-tpl-id").value = String(tpl.id);
    document.getElementById("pm-tpl-title").value = tpl.title || "";
    document.getElementById("pm-tpl-description").value = tpl.description || "";
    document.getElementById("pm-tpl-deadline").value = tpl.deadline_minutes || "";
    document.getElementById("pm-tpl-category").value = tpl.category || "";
    document.getElementById("pm-tpl-tags").value = Array.isArray(tpl.tags) ? tpl.tags.join(", ") : "";
    document.getElementById("pm-tpl-verification").value = tpl.requires_verification ? "true" : "false";
    document.getElementById("pm-tpl-active").value = tpl.is_active ? "true" : "false";
    document.getElementById("pm-tpl-criteria").value = tpl.verification_criteria || "";
    document.getElementById("pm-tpl-save-btn").textContent = "Vorlage aktualisieren";
  }

  async function pmTplDelete(templateId, title) {
    if (!pmCurrentPersonaId) return;
    if (!confirm(`Vorlage "${title}" wirklich löschen?`)) return;
    try {
      await pmFetch(`/api/personas/${pmCurrentPersonaId}/task-templates/${templateId}`, { method: "DELETE" });
      pmStatus(`Vorlage "${title}" gelöscht.`);
      pmTplResetForm();
      await pmTplLoad();
    } catch (e) {
      pmStatus("Fehler beim Löschen der Vorlage: " + e.message, true);
    }
  }

  function pmReloadList() {
    if (window.htmx) {
      window.htmx.ajax("GET", "/personas/partials/list", { target: "#pm-list", swap: "outerHTML" });
      return;
    }
    const container = document.getElementById("pm-list");
    if (container) {
      container.innerHTML = `<div class="empty-hint">Liste konnte nicht aktualisiert werden.</div>`;
    }
  }

  async function pmLoadPresets() {
    try {
      const data = await pmFetch("/api/personas/presets");
      const grid = document.getElementById("pm-preset-grid");
      pmLoadedPresets = data.items || [];
      if (!data.items.length) { grid.innerHTML = ""; return; }
      grid.innerHTML = data.items.map((preset, index) => `
        <button type="button" class="preset-btn" data-pm-preset-index="${index}">
          <span class="preset-btn-name">${escHtml(preset.name)}</span>
          <span class="preset-btn-style">${escHtml([preset.speech_style_tone, preset.speech_style_dominance].filter(Boolean).join(", ") || "")}</span>
        </button>
      `).join("");
    } catch (_) {
      document.getElementById("pm-preset-grid").innerHTML = `<span style="font-size:0.8rem;color:#8899aa;">Presets nicht verfügbar.</span>`;
    }
  }

  function pmLoadPreset(preset) {
    pmResetForm();
    pmShowForm();
    document.getElementById("pm-name").value = preset.name || "";
    document.getElementById("pm-tone").value = preset.speech_style_tone || "";
    const dominance = preset.speech_style_dominance || "";
    document.getElementById("pm-dominance").value = dominance;
    pmAutoStrictness(dominance);
    document.getElementById("pm-formatting-style").value = preset.formatting_style || "";
    document.getElementById("pm-verbosity-style").value = preset.verbosity_style || "";
    document.getElementById("pm-praise-style").value = preset.praise_style || "";
    document.getElementById("pm-repetition-guard").value = preset.repetition_guard || "";
    document.getElementById("pm-context-exposition-style").value = preset.context_exposition_style || "";
    document.getElementById("pm-description").value = preset.description || "";
    document.getElementById("pm-system-prompt").value = preset.system_prompt || "";
    document.getElementById("pm-behavior-profile").value = preset.behavior_profile ? JSON.stringify(preset.behavior_profile, null, 2) : "";
    document.getElementById("pm-form-title").textContent = `Aus System-Keyholder-Profil: ${preset.name}`;
    document.getElementById("pm-cancel-btn").style.display = "inline-flex";
    document.getElementById("pm-preset-section").removeAttribute("open");
  }

  async function pmStartEdit(id) {
    try {
      const p = await pmFetch(`/api/personas/${id}`);
      pmShowForm();
      document.getElementById("pm-edit-id").value = p.id;
      document.getElementById("pm-name").value = p.name || "";
      document.getElementById("pm-tone").value = p.speech_style_tone || "";
      const dominance = p.speech_style_dominance || "";
      document.getElementById("pm-dominance").value = dominance;
      pmAutoStrictness(dominance);
      document.getElementById("pm-formatting-style").value = p.formatting_style || "";
      document.getElementById("pm-verbosity-style").value = p.verbosity_style || "";
      document.getElementById("pm-praise-style").value = p.praise_style || "";
      document.getElementById("pm-repetition-guard").value = p.repetition_guard || "";
      document.getElementById("pm-context-exposition-style").value = p.context_exposition_style || "";
      document.getElementById("pm-description").value = p.description || "";
      document.getElementById("pm-system-prompt").value = p.system_prompt || "";
      document.getElementById("pm-behavior-profile").value = p.behavior_profile ? JSON.stringify(p.behavior_profile, null, 2) : "";
      pmAvatarMediaId = p.avatar_media_id || null;
      document.getElementById("pm-avatar-media-id").value = pmAvatarMediaId ? String(pmAvatarMediaId) : "";
      pmUpdateAvatarUi(p.avatar_url || null);
      document.getElementById("pm-form-title").textContent = `Keyholder-Profil bearbeiten: ${p.name}`;
      document.getElementById("pm-save-btn").textContent = "Änderungen speichern";
      document.getElementById("pm-cancel-btn").style.display = "inline-flex";
      pmCurrentPersonaId = p.id;
      document.getElementById("pm-task-lib-panel").style.display = "";
      pmTplResetForm();
      try {
        await pmTplLoad();
      } catch (_) {
        pmStatus("Persona geöffnet, aber Aufgaben-Bibliothek konnte nicht geladen werden.", true);
      }
      document.getElementById("pm-form-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      pmStatus("Fehler: " + e.message, true);
    }
  }

  async function pmStartEditSystem(systemKey) {
    try {
      const p = await pmFetch(`/api/personas/system/${systemKey}`);
      pmShowForm();
      document.getElementById("pm-edit-id").value = "";
      document.getElementById("pm-name").value = p.name || "";
      document.getElementById("pm-tone").value = p.speech_style_tone || "";
      document.getElementById("pm-dominance").value = p.speech_style_dominance || "";
      document.getElementById("pm-formatting-style").value = p.formatting_style || "";
      document.getElementById("pm-verbosity-style").value = p.verbosity_style || "";
      document.getElementById("pm-praise-style").value = p.praise_style || "";
      document.getElementById("pm-repetition-guard").value = p.repetition_guard || "";
      document.getElementById("pm-context-exposition-style").value = p.context_exposition_style || "";
      document.getElementById("pm-description").value = p.description || "";
      document.getElementById("pm-system-prompt").value = p.system_prompt || "";
      document.getElementById("pm-behavior-profile").value = p.behavior_profile ? JSON.stringify(p.behavior_profile, null, 2) : "";
      document.getElementById("pm-strictness").value = String(p.strictness_level || 3);
      pmAvatarMediaId = null;
      document.getElementById("pm-avatar-media-id").value = "";
      pmUpdateAvatarUi(null);
      document.getElementById("pm-form-title").textContent = `System-Keyholder-Profil: ${p.name}`;
      document.getElementById("pm-save-btn").textContent = "Als neues Profil speichern";
      document.getElementById("pm-cancel-btn").style.display = "inline-flex";
      pmCurrentPersonaId = null;
      document.getElementById("pm-task-lib-panel").style.display = "none";
      pmRenderTemplates([]);
      document.getElementById("pm-form-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      pmStatus("Fehler: " + e.message, true);
    }
  }

  async function pmDelete(id, name) {
    if (!confirm(`Keyholder-Profil "${name}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`)) return;
    try {
      await pmFetch(`/api/personas/${id}`, { method: "DELETE" });
      pmStatus(`Keyholder-Profil "${name}" gelöscht.`);
      pmReloadList();
    } catch (e) {
      pmStatus("Fehler beim Löschen: " + e.message, true);
    }
  }

  function pmResetForm() {
    document.getElementById("pm-edit-id").value = "";
    document.getElementById("pm-form").reset();
    document.getElementById("pm-tone").value = "";
    document.getElementById("pm-dominance").value = "";
    document.getElementById("pm-formatting-style").value = "";
    document.getElementById("pm-verbosity-style").value = "";
    document.getElementById("pm-praise-style").value = "";
    document.getElementById("pm-repetition-guard").value = "";
    document.getElementById("pm-context-exposition-style").value = "";
    document.getElementById("pm-behavior-profile").value = "";
    document.getElementById("pm-strictness").value = "3";
    document.getElementById("pm-avatar-file").value = "";
    document.getElementById("pm-avatar-media-id").value = "";
    pmAvatarMediaId = null;
    pmUpdateAvatarUi(null);
    document.getElementById("pm-form-title").textContent = "Neues Keyholder-Profil erstellen";
    document.getElementById("pm-save-btn").textContent = "Keyholder-Profil speichern";
    document.getElementById("pm-cancel-btn").style.display = "none";
    pmCurrentPersonaId = null;
    pmCurrentTemplates = [];
    document.getElementById("pm-task-lib-panel").style.display = "none";
    pmTplResetForm();
    pmRenderTemplates([]);
    pmHideForm();
  }

  const DOMINANCE_STRICTNESS = {
    soft: 1,
    supportive: 2,
    "gentle-dominant": 3,
    balanced: 3,
    firm: 4,
    dominant: 4,
    strict: 5,
    "hard-dominant": 5,
  };

  function pmAutoStrictness(dominance) {
    const value = DOMINANCE_STRICTNESS[dominance];
    if (value !== undefined) {
      document.getElementById("pm-strictness").value = value;
    }
  }

  function pmExportOne(id, name) {
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || `persona-${id}`;
    const anchor = document.createElement("a");
    anchor.href = `/api/personas/${id}/export`;
    anchor.download = `persona-${slug}.json`;
    anchor.click();
  }

  async function pmImportFile(file) {
    let raw;
    try {
      raw = JSON.parse(await file.text());
    } catch (_) {
      pmStatus(`${file.name}: Ungültiges JSON.`, true);
      return 0;
    }
    const cards = raw.kind === "persona_collection" && Array.isArray(raw.personas) ? raw.personas : [raw];
    let imported = 0;
    for (const card of cards) {
      try {
        await pmFetch("/api/personas/import", { method: "POST", body: JSON.stringify({ card }) });
        imported += 1;
      } catch (e) {
        pmStatus(`Fehler beim Importieren von "${card.name || "?"}": ${e.message}`, true);
      }
    }
    return imported;
  }

  async function pmHandleImportFiles(files) {
    let total = 0;
    for (const file of files) {
      total += await pmImportFile(file);
    }
    if (total > 0) {
      pmStatus(`${total} Persona(s) importiert.`);
      pmReloadList();
    }
  }

  function bindPersonaForm() {
    document.getElementById("pm-dominance")?.addEventListener("change", (event) => {
      pmAutoStrictness(event.target?.value || "");
    });

    document.getElementById("pm-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const editId = document.getElementById("pm-edit-id").value;
      const payload = {
        name: document.getElementById("pm-name").value.trim(),
        speech_style_tone: document.getElementById("pm-tone").value.trim() || null,
        speech_style_dominance: document.getElementById("pm-dominance").value || null,
        formatting_style: document.getElementById("pm-formatting-style").value || null,
        verbosity_style: document.getElementById("pm-verbosity-style").value || null,
        praise_style: document.getElementById("pm-praise-style").value || null,
        repetition_guard: document.getElementById("pm-repetition-guard").value || null,
        context_exposition_style: document.getElementById("pm-context-exposition-style").value || null,
        description: document.getElementById("pm-description").value.trim() || null,
        system_prompt: document.getElementById("pm-system-prompt").value.trim() || null,
        strictness_level: parseInt(document.getElementById("pm-strictness").value, 10),
        avatar_media_id: pmAvatarMediaId,
      };
      const behaviorRaw = document.getElementById("pm-behavior-profile").value.trim();
      if (behaviorRaw) {
        try {
          payload.behavior_profile = JSON.parse(behaviorRaw);
        } catch (err) {
          pmStatus("Behavior Profile JSON ist ungültig: " + err.message, true);
          return;
        }
      } else {
        payload.behavior_profile = {};
      }

      const btn = document.getElementById("pm-save-btn");
      btn.disabled = true;
      try {
        if (editId) {
          await pmFetch(`/api/personas/${editId}`, { method: "PUT", body: JSON.stringify(payload) });
          pmStatus(`Keyholder-Profil "${payload.name}" aktualisiert.`);
        } else {
          await pmFetch("/api/personas", { method: "POST", body: JSON.stringify(payload) });
          pmStatus(`Keyholder-Profil "${payload.name}" erstellt.`);
        }
        pmResetForm();
        pmReloadList();
      } catch (e) {
        pmStatus("Fehler: " + e.message, true);
      } finally {
        btn.disabled = false;
      }
    });

    document.getElementById("pm-cancel-btn").addEventListener("click", pmResetForm);
    document.getElementById("pm-new-btn").addEventListener("click", () => {
      pmResetForm();
      pmShowForm();
      document.getElementById("pm-form-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function bindImportExport() {
    document.getElementById("pm-export-all-btn").addEventListener("click", () => {
      const a = document.createElement("a");
      a.href = "/api/personas/export";
      a.download = "personas-export.json";
      a.click();
    });

    const pmImportInput = document.getElementById("pm-import-input");
    const pmImportZone = document.getElementById("pm-import-zone");

    pmImportInput.addEventListener("change", async () => {
      await pmHandleImportFiles(pmImportInput.files || []);
      pmImportInput.value = "";
    });

    pmImportZone.addEventListener("dragover", (e) => { e.preventDefault(); pmImportZone.classList.add("drag-over"); });
    pmImportZone.addEventListener("dragleave", () => pmImportZone.classList.remove("drag-over"));
    pmImportZone.addEventListener("drop", async (e) => {
      e.preventDefault();
      pmImportZone.classList.remove("drag-over");
      const files = [...(e.dataTransfer?.files || [])].filter((f) => f.name.endsWith(".json"));
      await pmHandleImportFiles(files);
    });
  }

  function bindDelegatedActions() {
    document.addEventListener("click", (event) => {
      const presetTrigger = event.target.closest("[data-pm-preset-index]");
      if (presetTrigger) {
        const presetIndex = Number.parseInt(presetTrigger.getAttribute("data-pm-preset-index") || "", 10);
        const preset = pmLoadedPresets[presetIndex];
        if (preset) pmLoadPreset(preset);
        return;
      }

      const templateTrigger = event.target.closest("[data-pm-template-action]");
      if (templateTrigger) {
        const action = String(templateTrigger.getAttribute("data-pm-template-action") || "").trim();
        const templateId = Number.parseInt(templateTrigger.getAttribute("data-template-id") || "", 10);
        if (!Number.isFinite(templateId) || templateId <= 0) return;
        const template = pmCurrentTemplates.find((item) => item.id === templateId);
        if (action === "edit") {
          pmTplStartEdit(templateId);
          return;
        }
        if (action === "delete" && template) {
          pmTplDelete(templateId, template.title || "Vorlage");
          return;
        }
      }

      const trigger = event.target.closest("[data-pm-action]");
      if (!trigger) return;
      const action = String(trigger.getAttribute("data-pm-action") || "").trim();
      const personaId = Number.parseInt(trigger.getAttribute("data-persona-id") || "", 10);
      const personaName = trigger.getAttribute("data-persona-name") || "";
      const systemKey = trigger.getAttribute("data-system-key") || "";

      if (action === "edit-system") {
        if (systemKey) pmStartEditSystem(systemKey);
        return;
      }

      if (!Number.isFinite(personaId) || personaId <= 0) return;
      if (action === "edit") {
        pmStartEdit(personaId);
        return;
      }
      if (action === "export") {
        if (trigger.tagName !== "A") pmExportOne(personaId, personaName);
        return;
      }
      if (action === "delete") {
        pmDelete(personaId, personaName);
      }
    });
  }

  function bindAvatarControls() {
    document.getElementById("pm-avatar-upload")?.addEventListener("click", pmUploadAvatar);
    document.getElementById("pm-avatar-clear")?.addEventListener("click", () => {
      pmAvatarMediaId = null;
      document.getElementById("pm-avatar-media-id").value = "";
      document.getElementById("pm-avatar-file").value = "";
      pmUpdateAvatarUi(null);
    });
  }

  function bindTemplateLibrary() {
    document.getElementById("pm-tpl-reset-btn")?.addEventListener("click", pmTplResetForm);

    document.getElementById("pm-tpl-export-btn")?.addEventListener("click", () => {
      if (!pmCurrentPersonaId) {
        pmStatus("Bitte zuerst eine Persona bearbeiten.", true);
        return;
      }
      const a = document.createElement("a");
      a.href = `/api/personas/${pmCurrentPersonaId}/task-templates/export`;
      a.download = `persona-${pmCurrentPersonaId}-task-library.json`;
      a.click();
    });

    document.getElementById("pm-tpl-import-append-btn")?.addEventListener("click", () => {
      if (!pmCurrentPersonaId) {
        pmStatus("Bitte zuerst eine Persona bearbeiten.", true);
        return;
      }
      pmTplImportReplaceMode = false;
      document.getElementById("pm-tpl-import-file")?.click();
    });

    document.getElementById("pm-tpl-import-replace-btn")?.addEventListener("click", () => {
      if (!pmCurrentPersonaId) {
        pmStatus("Bitte zuerst eine Persona bearbeiten.", true);
        return;
      }
      pmTplImportReplaceMode = true;
      document.getElementById("pm-tpl-import-file")?.click();
    });

    document.getElementById("pm-tpl-import-file")?.addEventListener("change", async (e) => {
      if (!pmCurrentPersonaId) {
        pmStatus("Bitte zuerst eine Persona bearbeiten.", true);
        return;
      }
      const input = e.target;
      const file = input?.files?.[0];
      input.value = "";
      if (!file) return;

      let library;
      try {
        library = JSON.parse(await file.text());
      } catch (_) {
        pmStatus("Ungültige JSON-Datei für Task-Bibliothek.", true);
        return;
      }

      if (pmTplImportReplaceMode) {
        const proceed = confirm("Bestehende Vorlagen dieser Persona ersetzen?");
        if (!proceed) return;
      }

      try {
        const result = await pmFetch(`/api/personas/${pmCurrentPersonaId}/task-templates/import`, {
          method: "POST",
          body: JSON.stringify({
            library,
            replace_existing: pmTplImportReplaceMode,
          }),
        });
        pmStatus(`Import abgeschlossen: ${result.imported} Vorlage(n).`);
        pmTplResetForm();
        await pmTplLoad();
      } catch (err) {
        pmStatus("Fehler beim Import der Bibliothek: " + err.message, true);
      }
    });

    document.getElementById("pm-tpl-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!pmCurrentPersonaId) {
        pmStatus("Bitte zuerst eine Persona bearbeiten.", true);
        return;
      }

      const tplId = document.getElementById("pm-tpl-id").value;
      const title = document.getElementById("pm-tpl-title").value.trim();
      if (!title) {
        pmStatus("Titel der Vorlage ist erforderlich.", true);
        return;
      }

      const deadlineRaw = document.getElementById("pm-tpl-deadline").value.trim();
      const deadline = deadlineRaw ? parseInt(deadlineRaw, 10) : null;
      const tags = document.getElementById("pm-tpl-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean).slice(0, 20);

      const payload = {
        title,
        description: document.getElementById("pm-tpl-description").value.trim() || null,
        deadline_minutes: Number.isInteger(deadline) && deadline > 0 ? deadline : null,
        requires_verification: document.getElementById("pm-tpl-verification").value === "true",
        verification_criteria: document.getElementById("pm-tpl-criteria").value.trim() || null,
        category: document.getElementById("pm-tpl-category").value.trim() || null,
        tags,
        is_active: document.getElementById("pm-tpl-active").value === "true",
      };

      try {
        if (tplId) {
          await pmFetch(`/api/personas/${pmCurrentPersonaId}/task-templates/${tplId}`, {
            method: "PUT",
            body: JSON.stringify({ ...payload, clear_deadline: payload.deadline_minutes === null }),
          });
          pmStatus("Vorlage aktualisiert.");
        } else {
          await pmFetch(`/api/personas/${pmCurrentPersonaId}/task-templates`, {
            method: "POST",
            body: JSON.stringify(payload),
          });
          pmStatus("Vorlage erstellt.");
        }
        pmTplResetForm();
        await pmTplLoad();
      } catch (err) {
        pmStatus("Fehler beim Speichern der Vorlage: " + err.message, true);
      }
    });
  }

  function boot() {
    bindPersonaForm();
    bindImportExport();
    bindDelegatedActions();
    bindAvatarControls();
    bindTemplateLibrary();
    pmLoadPresets();
  }

  window.pmAutoStrictness = pmAutoStrictness;
  window.pmDelete = pmDelete;
  window.pmExportOne = pmExportOne;
  window.pmStartEdit = pmStartEdit;
  window.pmStartEditSystem = pmStartEditSystem;

  boot();
})();
