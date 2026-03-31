(() => {
  const runtime = window.ChasteaseUiRuntime || {};
  const MODULE_KEY = window.GAME_POSTURE_MODULE_KEY;
  let items = [];
  let availableModules = [];
  const skeletonEditStateById = new Map();

  function setMsg(msg, warn = false) {
    const el = document.getElementById("pm-msg");
    if (!el) return;
    el.textContent = msg || "";
    el.className = warn ? "pm-status warn" : "pm-status";
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

  function moduleCheckboxesHtml(selectedKeys) {
    const selected = new Set(Array.isArray(selectedKeys) ? selectedKeys : []);
    if (!availableModules.length) return '<p class="pm-meta">Module werden geladen...</p>';
    return availableModules
      .map((mod) => {
        const checked = selected.has(mod.key) ? "checked" : "";
        return `<label style="display:flex; gap:0.35rem; align-items:center;"><input class="js-module-check" type="checkbox" value="${esc(mod.key)}" ${checked} />${esc(mod.title)}</label>`;
      })
      .join("");
  }

  const SKELETON_EDGES = [
    ["left_shoulder", "right_shoulder"],
    ["left_shoulder", "left_elbow"],
    ["left_elbow", "left_wrist"],
    ["right_shoulder", "right_elbow"],
    ["right_elbow", "right_wrist"],
    ["left_shoulder", "left_hip"],
    ["right_shoulder", "right_hip"],
    ["left_hip", "right_hip"],
    ["left_hip", "left_knee"],
    ["left_knee", "left_ankle"],
    ["right_hip", "right_knee"],
    ["right_knee", "right_ankle"],
  ];

  function referencePointsFromJson(referenceJson) {
    if (!referenceJson) return null;
    try {
      const parsed = JSON.parse(referenceJson);
      const points = parsed?.points;
      const meta = parsed?.meta;
      if (!points || !meta || !Array.isArray(meta.center)) return null;
      const scale = Number(meta.scale || 0);
      const centerX = Number(meta.center[0]);
      const centerY = Number(meta.center[1]);
      if (!Number.isFinite(scale) || scale <= 0) return null;
      if (!Number.isFinite(centerX) || !Number.isFinite(centerY)) return null;

      const denorm = {};
      Object.entries(points).forEach(([name, value]) => {
        const x = Number(value?.x);
        const y = Number(value?.y);
        if (!Number.isFinite(x) || !Number.isFinite(y)) return;
        denorm[name] = { x: centerX + (x * scale), y: centerY + (y * scale) };
      });
      return denorm;
    } catch {
      return null;
    }
  }

  function referenceModelFromJson(referenceJson) {
    if (!referenceJson) return null;
    try {
      const parsed = JSON.parse(referenceJson);
      const points = parsed?.points;
      const meta = parsed?.meta;
      if (!points || !meta || !Array.isArray(meta.center)) return null;
      const scale = Number(meta.scale || 0);
      const centerX = Number(meta.center[0]);
      const centerY = Number(meta.center[1]);
      if (!Number.isFinite(scale) || scale <= 0) return null;
      if (!Number.isFinite(centerX) || !Number.isFinite(centerY)) return null;

      const absPoints = {};
      const visByName = {};
      Object.entries(points).forEach(([name, value]) => {
        const x = Number(value?.x);
        const y = Number(value?.y);
        if (!Number.isFinite(x) || !Number.isFinite(y)) return;
        absPoints[name] = { x: centerX + (x * scale), y: centerY + (y * scale) };
        visByName[name] = Number.isFinite(Number(value?.visibility)) ? Number(value?.visibility) : 1.0;
      });
      return { meta: { scale, center: [centerX, centerY] }, absPoints, visibility: visByName };
    } catch {
      return null;
    }
  }

  function clamp01(value) {
    return Math.min(1, Math.max(0, Number(value) || 0));
  }

  function editableJsonFromState(state) {
    const points = {};
    const centerX = Number(state?.meta?.center?.[0] || 0);
    const centerY = Number(state?.meta?.center?.[1] || 0);
    const scale = Number(state?.meta?.scale || 0);
    if (!Number.isFinite(scale) || scale <= 0) return null;
    Object.entries(state.absPoints || {}).forEach(([name, p]) => {
      const xAbs = Number(p?.x);
      const yAbs = Number(p?.y);
      if (!Number.isFinite(xAbs) || !Number.isFinite(yAbs)) return;
      points[name] = {
        x: (xAbs - centerX) / scale,
        y: (yAbs - centerY) / scale,
        visibility: Number.isFinite(Number(state.visibility?.[name])) ? Number(state.visibility[name]) : 1.0,
      };
    });
    return JSON.stringify({ points, meta: { scale, center: [centerX, centerY] } });
  }

  function defaultReferenceAbsPoints() {
    return {
      left_shoulder: { x: 0.40, y: 0.30 },
      right_shoulder: { x: 0.60, y: 0.30 },
      left_elbow: { x: 0.37, y: 0.43 },
      right_elbow: { x: 0.63, y: 0.43 },
      left_wrist: { x: 0.36, y: 0.56 },
      right_wrist: { x: 0.64, y: 0.56 },
      left_hip: { x: 0.45, y: 0.55 },
      right_hip: { x: 0.55, y: 0.55 },
      left_knee: { x: 0.44, y: 0.75 },
      right_knee: { x: 0.56, y: 0.75 },
      left_ankle: { x: 0.43, y: 0.92 },
      right_ankle: { x: 0.57, y: 0.92 },
    };
  }

  function rearReferenceAbsPoints() {
    const front = defaultReferenceAbsPoints();
    return {
      left_shoulder: front.right_shoulder,
      right_shoulder: front.left_shoulder,
      left_elbow: front.right_elbow,
      right_elbow: front.left_elbow,
      left_wrist: front.right_wrist,
      right_wrist: front.left_wrist,
      left_hip: front.right_hip,
      right_hip: front.left_hip,
      left_knee: front.right_knee,
      right_knee: front.left_knee,
      left_ankle: front.right_ankle,
      right_ankle: front.left_ankle,
    };
  }

  function defaultReferenceJson(variant = "front") {
    const center = [0.5, 0.5];
    const scale = 0.24;
    const abs = variant === "rear" ? rearReferenceAbsPoints() : defaultReferenceAbsPoints();
    const points = {};
    Object.entries(abs).forEach(([name, p]) => {
      points[name] = { x: (p.x - center[0]) / scale, y: (p.y - center[1]) / scale, visibility: 1.0 };
    });
    return JSON.stringify({ points, meta: { scale, center } });
  }

  function skeletonOverlaySvg(referenceJson) {
    const points = referencePointsFromJson(referenceJson);
    if (!points) return "";
    const lines = SKELETON_EDGES
      .map(([a, b]) => {
        const pa = points[a];
        const pb = points[b];
        if (!pa || !pb) return "";
        return `<line data-edge-a="${a}" data-edge-b="${b}" x1="${clamp01(pa.x)}" y1="${clamp01(pa.y)}" x2="${clamp01(pb.x)}" y2="${clamp01(pb.y)}" />`;
      })
      .join("");
    const circles = Object.entries(points)
      .map(([name, p]) => `<circle data-point-name="${name}" cx="${clamp01(p.x)}" cy="${clamp01(p.y)}" r="0.012" />`)
      .join("");
    if (!lines && !circles) return "";
    return `<svg class="pm-overlay" viewBox="0 0 1 1" preserveAspectRatio="none">${lines}${circles}</svg>`;
  }

  function cardHtml(item) {
    const referenceActive = Boolean(item.reference_pose_available);
    const referenceLabel = referenceActive ? "Aktiv" : "Inaktiv";
    const referenceClass = referenceActive ? "pm-reference-active" : "pm-reference-inactive";
    const toggleText = referenceActive ? "Landmark-Erkennung deaktivieren" : "Landmark-Erkennung aktivieren";
    const toggleEnabled = referenceActive ? "false" : "true";
    const overlay = referenceActive ? skeletonOverlaySvg(item.reference_landmarks_json) : "";
    return `
    <article class="pm-card" data-id="${item.id}" data-image-url="${esc(item.image_url || "")}" data-reference-json="${esc(item.reference_landmarks_json || "")}">
      <div class="pm-view">
        <h3 class="pm-title">${esc(item.title)}</h3>
        ${item.image_url ? `<div class="pm-image-wrap"><img class="pm-image" src="${esc(item.image_url)}" alt="Posture" />${overlay}</div>` : ""}
        <p class="pm-meta">Key: ${esc(item.posture_key)} · Sort: ${item.sort_order} · Target: ${item.target_seconds}s · Aktiv: ${item.is_active ? "Ja" : "Nein"}</p>
        <p class="pm-meta">Referenz-Landmark-Skelett: <strong class="${referenceClass}">${referenceLabel}</strong></p>
        <p class="pm-meta">Instruktion: ${esc(item.instruction || "-")}</p>
        <div class="pm-actions">
          <button type="button" class="ghost js-edit">Bearbeiten</button>
          <button type="button" class="warn js-delete">Loeschen</button>
        </div>
        <details class="pm-advanced">
          <summary>Erweiterte Referenz</summary>
          <p class="pm-help">Nur noetig, wenn die automatische Landmark-Erkennung nicht passt. Reihenfolge: Referenzbild setzen oder Skelett automatisch erzeugen, danach bei Bedarf Punkte manuell verschieben.</p>
          <div class="pm-actions">
            <button type="button" class="ghost js-reference-toggle" data-enabled="${toggleEnabled}">${toggleText}</button>
            <button type="button" class="ghost js-reference-refresh">Landmark-Skelett neu berechnen</button>
            ${!referenceActive ? '<button type="button" class="ghost js-skeleton-seed-front">Front-Standard setzen</button>' : ''}
            ${!referenceActive ? '<button type="button" class="ghost js-skeleton-seed-rear">Rueckansicht-Standard setzen</button>' : ''}
            ${referenceActive ? '<button type="button" class="ghost js-skeleton-edit">Skelettpunkte bearbeiten</button>' : ''}
            ${referenceActive ? '<button type="button" class="ghost pm-skeleton-save js-skeleton-save">Skelett speichern</button>' : ''}
            ${referenceActive ? '<button type="button" class="ghost pm-skeleton-cancel js-skeleton-cancel">Bearbeitung abbrechen</button>' : ''}
          </div>
          <p class="pm-section-label">Eigenes Referenzbild</p>
          <p class="pm-help">Dieses Bild wird nur fuer die Referenz-Landmarks verwendet, nicht als sichtbares Hauptbild der Posture.</p>
          <div class="pm-actions">
            <input class="js-reference-file" type="file" accept="image/jpeg,image/png,image/webp,image/gif,image/heic,image/heif" />
            <button type="button" class="ghost js-reference-upload">Eigenes Referenzbild setzen</button>
          </div>
        </details>
      </div>

      <div class="pm-edit">
        <p class="pm-help">Grunddaten der Posture. Das Hauptbild zuerst hochladen, dann die Karte speichern. Referenzbild und Skelettpunkte bleiben im Bereich "Erweiterte Referenz".</p>
        <div class="pm-form-grid">
          <label class="full">Titel
            <input class="js-title" type="text" maxlength="200" value="${esc(item.title)}" />
          </label>
          <label>Posture-Key
            <input class="js-key" type="text" maxlength="120" value="${esc(item.posture_key || "")}" />
          </label>
          <label>Sortierung
            <input class="js-sort" type="number" min="0" max="10000" value="${item.sort_order}" />
          </label>
          <label>Target (Sek)
            <input class="js-target" type="number" min="1" max="3600" value="${item.target_seconds}" />
          </label>
          <label>Aktiv
            <select class="js-active">
              <option value="true" ${item.is_active ? "selected" : ""}>Ja</option>
              <option value="false" ${item.is_active ? "" : "selected"}>Nein</option>
            </select>
          </label>
          <label class="full">Bild (Pflicht)
            <div class="pm-actions">
              <input class="js-image-file" type="file" accept="image/jpeg,image/png,image/webp,image/gif,image/heic,image/heif" />
              <button type="button" class="ghost js-upload">Bild hochladen</button>
            </div>
          </label>
          <label class="full">Instruktion
            <textarea class="js-instruction" rows="3" maxlength="2000">${esc(item.instruction || "")}</textarea>
          </label>
          <label class="full">Verwendbar in Modulen
            <div class="pm-actions" style="align-items:center;">${moduleCheckboxesHtml(item.allowed_module_keys || [])}</div>
          </label>
        </div>
        <div class="pm-actions">
          <button type="button" class="js-save">Speichern</button>
          <button type="button" class="ghost js-cancel">Abbrechen</button>
        </div>
      </div>
      <p class="pm-status js-status"></p>
    </article>`;
  }

  function newCardHtml() {
    return `
    <article class="pm-card" data-id="new" data-image-url="">
      <h3 class="pm-title">Neue Posture</h3>
      <div class="pm-form-grid">
        <label class="full">Titel
          <input class="js-title" type="text" maxlength="200" placeholder="z.B. Wall" />
        </label>
        <label>Posture-Key
          <input class="js-key" type="text" maxlength="120" placeholder="optional" />
        </label>
        <label>Sortierung
          <input class="js-sort" type="number" min="0" max="10000" value="0" />
        </label>
        <label>Target (Sek)
          <input class="js-target" type="number" min="1" max="3600" value="120" />
        </label>
        <label>Aktiv
          <select class="js-active">
            <option value="true">Ja</option>
            <option value="false">Nein</option>
          </select>
        </label>
        <label class="full">Bild (Pflicht)
          <div class="pm-actions">
            <input class="js-image-file" type="file" accept="image/jpeg,image/png,image/webp,image/gif,image/heic,image/heif" />
            <button type="button" class="ghost js-upload">Bild hochladen</button>
          </div>
        </label>
        <label class="full">Instruktion
          <textarea class="js-instruction" rows="3" maxlength="2000" placeholder="Pose-Beschreibung"></textarea>
        </label>
        <label class="full">Verwendbar in Modulen
          <div class="pm-actions" style="align-items:center;">${moduleCheckboxesHtml([MODULE_KEY])}</div>
        </label>
      </div>
      <div class="pm-actions">
        <button type="button" class="js-save">Anlegen</button>
      </div>
      <p class="pm-status js-status"></p>
    </article>`;
  }

  function payloadFrom(card) {
    return {
      posture_key: card.querySelector(".js-key")?.value.trim() || null,
      title: card.querySelector(".js-title")?.value.trim() || "",
      image_url: (card.dataset.imageUrl || "").trim() || null,
      instruction: card.querySelector(".js-instruction")?.value.trim() || null,
      target_seconds: Number(card.querySelector(".js-target")?.value || 120),
      sort_order: Number(card.querySelector(".js-sort")?.value || 0),
      is_active: (card.querySelector(".js-active")?.value || "true") === "true",
      allowed_module_keys: [...card.querySelectorAll(".js-module-check:checked")].map((el) => el.value),
    };
  }

  function setEditVisible(card, visible) {
    if (!card || card.dataset.id === "new") return;
    if (visible) {
      document.querySelectorAll("#pm-grid .pm-card.is-editing").forEach((node) => {
        if (node !== card) node.classList.remove("is-editing");
      });
    }
    card.classList.toggle("is-editing", visible);
  }

  function setCardStatus(card, msg, warn = false) {
    const el = card.querySelector(".js-status");
    if (!el) return;
    el.textContent = msg || "";
    el.className = warn ? "pm-status js-status warn" : "pm-status js-status ok";
  }

  function renderCards(list) {
    items = Array.isArray(list) ? list : [];
    const root = document.getElementById("pm-grid");
    if (!root) return;
    root.innerHTML = [...items.map((it) => cardHtml(it)), newCardHtml()].join("");
    syncOverlaySizing();
  }

  function syncOverlaySizing() {
    document.querySelectorAll("#pm-grid .pm-card").forEach((card) => {
      const wrap = card.querySelector(".pm-image-wrap");
      const img = card.querySelector(".pm-image");
      const overlay = card.querySelector(".pm-overlay");
      if (!(wrap instanceof HTMLElement) || !(img instanceof HTMLImageElement) || !(overlay instanceof SVGElement)) return;

      const apply = () => {
        const w = Math.max(1, img.clientWidth || 0);
        const h = Math.max(1, img.clientHeight || 0);
        wrap.style.width = `${w}px`;
        wrap.style.height = `${h}px`;
        overlay.style.width = `${w}px`;
        overlay.style.height = `${h}px`;
      };
      if (img.complete) apply();
      else img.addEventListener("load", apply, { once: true });
    });
  }

  async function loadItems() {
    try {
      const data = await api(`/api/inventory/postures/modules/${MODULE_KEY}`);
      renderCards(data.items || []);
    } catch (err) {
      setMsg(`Fehler beim Laden: ${err.message}`, true);
    }
  }

  async function loadModules() {
    const data = await api("/api/games/modules");
    availableModules = Array.isArray(data.items) ? data.items : [];
  }

  async function uploadForCard(card) {
    const input = card.querySelector(".js-image-file");
    const file = input?.files?.[0];
    if (!file) return setCardStatus(card, "Bitte Bild auswaehlen.", true);
    const form = new FormData();
    form.append("file", file, file.name);
    try {
      const result = await api(`/api/inventory/postures/modules/${MODULE_KEY}/upload-image`, { method: "POST", body: form });
      card.dataset.imageUrl = result.content_url;
      setCardStatus(card, "Bild hochgeladen. Jetzt auf Speichern/Anlegen klicken.");
    } catch (err) {
      setCardStatus(card, `Bild-Upload fehlgeschlagen: ${err.message}`, true);
    }
  }

  async function saveCard(card) {
    const payload = payloadFrom(card);
    if (!payload.title) return setCardStatus(card, "Titel fehlt.", true);
    if (!payload.image_url) return setCardStatus(card, "Bitte zuerst Bild hochladen.", true);
    if (!Array.isArray(payload.allowed_module_keys) || payload.allowed_module_keys.length === 0) {
      return setCardStatus(card, "Bitte mindestens ein Modul auswaehlen.", true);
    }
    const id = card.dataset.id;
    const isNew = !id || id === "new";
    try {
      await api(isNew ? `/api/inventory/postures/modules/${MODULE_KEY}` : `/api/inventory/postures/modules/${MODULE_KEY}/${id}`, {
        method: isNew ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setMsg(isNew ? "Posture angelegt." : "Posture gespeichert.");
      await loadItems();
    } catch (err) {
      setCardStatus(card, `Speichern fehlgeschlagen: ${err.message}`, true);
    }
  }

  async function removeCard(card) {
    const id = Number(card.dataset.id || 0);
    if (!id) return;
    if (!confirm("Posture wirklich loeschen?")) return;
    try {
      await api(`/api/inventory/postures/modules/${MODULE_KEY}/${id}`, { method: "DELETE" });
      setMsg("Posture geloescht.");
      await loadItems();
    } catch (err) {
      setCardStatus(card, `Loeschen fehlgeschlagen: ${err.message}`, true);
    }
  }

  async function updateReferencePose(card, enabled, refresh = false) {
    const id = Number(card.dataset.id || 0);
    if (!id) return setCardStatus(card, "Bitte Posture zuerst speichern.", true);
    try {
      await api(`/api/inventory/postures/modules/${MODULE_KEY}/${id}/reference-pose`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled, refresh }),
      });
      setMsg(enabled ? "Referenz-Landmark aktualisiert." : "Referenz-Landmark deaktiviert.");
      await loadItems();
    } catch (err) {
      setCardStatus(card, `Landmark-Aktion fehlgeschlagen: ${err.message}`, true);
    }
  }

  async function uploadReferencePoseForCard(card) {
    const id = Number(card.dataset.id || 0);
    if (!id) return setCardStatus(card, "Bitte Posture zuerst speichern.", true);
    const input = card.querySelector(".js-reference-file");
    const file = input?.files?.[0];
    if (!file) return setCardStatus(card, "Bitte Referenzbild auswaehlen.", true);
    const form = new FormData();
    form.append("file", file, file.name);
    try {
      await api(`/api/inventory/postures/modules/${MODULE_KEY}/${id}/reference-pose/upload-image`, { method: "POST", body: form });
      setMsg("Eigenes Referenzbild uebernommen und Landmark-Skelett aktiviert.");
      await loadItems();
    } catch (err) {
      setCardStatus(card, `Referenzbild fehlgeschlagen: ${err.message}`, true);
    }
  }

  function updateOverlayGeometry(svg, absPoints) {
    if (!(svg instanceof SVGElement)) return;
    const points = absPoints || {};
    svg.querySelectorAll("line[data-edge-a][data-edge-b]").forEach((line) => {
      const a = line.getAttribute("data-edge-a") || "";
      const b = line.getAttribute("data-edge-b") || "";
      const pa = points[a];
      const pb = points[b];
      if (!pa || !pb) {
        line.setAttribute("visibility", "hidden");
        return;
      }
      line.setAttribute("visibility", "visible");
      line.setAttribute("x1", `${clamp01(pa.x)}`);
      line.setAttribute("y1", `${clamp01(pa.y)}`);
      line.setAttribute("x2", `${clamp01(pb.x)}`);
      line.setAttribute("y2", `${clamp01(pb.y)}`);
    });
    svg.querySelectorAll("circle[data-point-name]").forEach((circle) => {
      const name = circle.getAttribute("data-point-name") || "";
      const p = points[name];
      if (!p) {
        circle.setAttribute("visibility", "hidden");
        return;
      }
      circle.setAttribute("visibility", "visible");
      circle.setAttribute("cx", `${clamp01(p.x)}`);
      circle.setAttribute("cy", `${clamp01(p.y)}`);
    });
  }

  function attachSkeletonDrag(card, state) {
    const overlay = card.querySelector(".pm-overlay");
    if (!(overlay instanceof SVGElement)) return;
    overlay.classList.add("is-editable");
    let draggingName = null;
    let activeCircle = null;

    const movePointFromEvent = (event) => {
      if (!draggingName) return;
      const rect = overlay.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      const x = clamp01((event.clientX - rect.left) / rect.width);
      const y = clamp01((event.clientY - rect.top) / rect.height);
      state.absPoints[draggingName] = { x, y };
      updateOverlayGeometry(overlay, state.absPoints);
    };

    const stopDrag = () => {
      if (activeCircle) activeCircle.classList.remove("is-dragging");
      activeCircle = null;
      draggingName = null;
      window.removeEventListener("pointermove", movePointFromEvent);
      window.removeEventListener("pointerup", stopDrag);
    };

    overlay.querySelectorAll("circle[data-point-name]").forEach((circle) => {
      circle.addEventListener("pointerdown", (event) => {
        const pointName = circle.getAttribute("data-point-name") || "";
        if (!pointName) return;
        draggingName = pointName;
        activeCircle = circle;
        circle.classList.add("is-dragging");
        window.addEventListener("pointermove", movePointFromEvent);
        window.addEventListener("pointerup", stopDrag, { once: true });
        event.preventDefault();
        event.stopPropagation();
      });
    });
  }

  function beginSkeletonEdit(card) {
    const id = Number(card.dataset.id || 0);
    if (!id) return;
    const raw = card.dataset.referenceJson || "";
    const model = referenceModelFromJson(raw);
    if (!model || !model.absPoints || !Object.keys(model.absPoints).length) {
      return setCardStatus(card, "Kein editierbares Landmark-Skelett vorhanden. Bitte zuerst Referenzbild setzen.", true);
    }
    const state = { id, meta: model.meta, absPoints: { ...model.absPoints }, visibility: { ...model.visibility }, originalJson: raw };
    skeletonEditStateById.set(id, state);
    card.classList.add("pm-skeleton-editing");
    const overlay = card.querySelector(".pm-overlay");
    if (overlay instanceof SVGElement) updateOverlayGeometry(overlay, state.absPoints);
    attachSkeletonDrag(card, state);
    setCardStatus(card, "Punkte verschieben und danach auf 'Skelett speichern' klicken.", false);
  }

  function cancelSkeletonEdit(card) {
    const id = Number(card.dataset.id || 0);
    const state = skeletonEditStateById.get(id);
    if (state) {
      const overlay = card.querySelector(".pm-overlay");
      if (overlay instanceof SVGElement) {
        overlay.classList.remove("is-editable");
        const original = referencePointsFromJson(state.originalJson) || {};
        updateOverlayGeometry(overlay, original);
      }
    }
    skeletonEditStateById.delete(id);
    card.classList.remove("pm-skeleton-editing");
    setCardStatus(card, "Bearbeitung verworfen.", false);
  }

  async function saveSkeletonEdit(card) {
    const id = Number(card.dataset.id || 0);
    const state = skeletonEditStateById.get(id);
    if (!id || !state) return setCardStatus(card, "Keine aktive Skelett-Bearbeitung gefunden.", true);
    const nextJson = editableJsonFromState(state);
    if (!nextJson) return setCardStatus(card, "Skelettdaten ungueltig und konnten nicht gespeichert werden.", true);
    try {
      await api(`/api/inventory/postures/modules/${MODULE_KEY}/${id}/reference-pose/manual`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reference_landmarks_json: nextJson }),
      });
      setMsg("Landmark-Skelett gespeichert.");
      skeletonEditStateById.delete(id);
      card.classList.remove("pm-skeleton-editing");
      await loadItems();
    } catch (err) {
      setCardStatus(card, `Skelett speichern fehlgeschlagen: ${err.message}`, true);
    }
  }

  async function seedDefaultSkeleton(card, variant = "front") {
    const id = Number(card.dataset.id || 0);
    if (!id) return setCardStatus(card, "Bitte Posture zuerst speichern.", true);
    try {
      await api(`/api/inventory/postures/modules/${MODULE_KEY}/${id}/reference-pose`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: true, refresh: true }),
      });
      setMsg("Skelett automatisch auf dem aktuellen Bild erzeugt.");
      await loadItems();
      return;
    } catch {
      // continue with fallback
    }
    try {
      await api(`/api/inventory/postures/modules/${MODULE_KEY}/${id}/reference-pose/manual`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reference_landmarks_json: defaultReferenceJson(variant) }),
      });
      setMsg(`${variant === "rear" ? "Rueckansicht" : "Front"}-Standard gesetzt (Auto-Fit war fuer dieses Bild nicht moeglich).`);
      await loadItems();
    } catch (err) {
      setCardStatus(card, `Standard-Skelett fehlgeschlagen: ${err.message}`, true);
    }
  }

  function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function exportZip() {
    try {
      const res = await fetch(`/api/inventory/postures/modules/${MODULE_KEY}/export`);
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload.detail || res.statusText || "Export fehlgeschlagen");
      }
      const blob = await res.blob();
      const disposition = res.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="?([^";]+)"?/i);
      triggerDownload(blob, match?.[1] || `postures_${MODULE_KEY}.zip`);
      setMsg("ZIP exportiert.");
    } catch (err) {
      setMsg(`Export fehlgeschlagen: ${err.message}`, true);
    }
  }

  async function importZip() {
    const input = document.getElementById("pm-import-file");
    const file = input?.files?.[0];
    if (!file) return setMsg("Bitte ZIP-Datei auswaehlen.", true);
    if (!confirm("ZIP importieren und alle Postures ersetzen?")) return;
    const form = new FormData();
    form.append("file", file, file.name);
    try {
      const result = await api(`/api/inventory/postures/modules/${MODULE_KEY}/import-zip`, { method: "POST", body: form });
      setMsg(`Import erfolgreich: ${result.imported || 0} Postures.`);
      input.value = "";
      await loadItems();
    } catch (err) {
      setMsg(`Import fehlgeschlagen: ${err.message}`, true);
    }
  }

  document.getElementById("pm-grid")?.addEventListener("click", async (event) => {
    const btn = event.target.closest("button");
    if (!btn) return;
    const card = event.target.closest(".pm-card");
    if (!card) return;

    if (btn.classList.contains("js-edit")) return setEditVisible(card, true);
    if (btn.classList.contains("js-cancel")) return setEditVisible(card, false);
    if (btn.classList.contains("js-upload")) return uploadForCard(card);
    if (btn.classList.contains("js-save")) return saveCard(card);
    if (btn.classList.contains("js-delete")) return removeCard(card);
    if (btn.classList.contains("js-reference-toggle")) {
      const enabled = String(btn.dataset.enabled || "false") === "true";
      return updateReferencePose(card, enabled, false);
    }
    if (btn.classList.contains("js-reference-refresh")) return updateReferencePose(card, true, true);
    if (btn.classList.contains("js-skeleton-seed-front")) return seedDefaultSkeleton(card, "front");
    if (btn.classList.contains("js-skeleton-seed-rear")) return seedDefaultSkeleton(card, "rear");
    if (btn.classList.contains("js-skeleton-edit")) return beginSkeletonEdit(card);
    if (btn.classList.contains("js-skeleton-cancel")) return cancelSkeletonEdit(card);
    if (btn.classList.contains("js-skeleton-save")) return saveSkeletonEdit(card);
    if (btn.classList.contains("js-reference-upload")) return uploadReferencePoseForCard(card);
  });

  document.getElementById("pm-export")?.addEventListener("click", exportZip);
  document.getElementById("pm-import")?.addEventListener("click", importZip);

  loadModules().then(() => loadItems()).catch((err) => setMsg(`Initialisierung fehlgeschlagen: ${err.message}`, true));
  window.addEventListener("resize", syncOverlaySizing);
})();
