(() => {
  function formatPlanCommand(command) {
    const value = String(command || "").trim().toLowerCase();
    if (!value) return "wartet";
    const labels = {
      vibrate: "Vibrate",
      pulse: "Pulse",
      wave: "Wave",
      stop: "Stop",
      preset: "Preset",
      pause: "Pause",
    };
    return labels[value] || value;
  }

  function describeStep(step) {
    if (!step || typeof step !== "object") return "nichts geplant";
    const command = String(step.command || "").trim().toLowerCase();
    if (!command) return "nichts geplant";
    const label = formatPlanCommand(command);
    if (command === "preset") {
      const preset = String(step.preset || "").trim();
      const duration = Math.max(0, Number(step.duration_seconds) || 0);
      return preset ? `${label} ${preset}${duration > 0 ? ` · ${duration}s` : ""}` : label;
    }
    const intensity = Math.max(0, Number(step.intensity) || 0);
    const duration = Math.max(0, Number(step.duration_seconds) || 0);
    if (command === "pause" || command === "stop") {
      return duration > 0 ? `${label} · ${duration}s` : label;
    }
    const detail = [];
    if (intensity > 0) detail.push(`${intensity}/20`);
    if (duration > 0) detail.push(`${duration}s`);
    return detail.length ? `${label} ${detail.join(" · ")}` : label;
  }

  function renderConsole(options = {}) {
    const state = options.state || {};
    const refs = options.refs || {};
    const hasToy = Boolean(options.hasToy);
    const queue = Array.isArray(options.queue) ? options.queue : [];
    const planTitle = String(options.planTitle || "").trim();
    const planTotal = Math.max(0, Number(options.planTotal) || 0);
    const planCurrentIndex = Math.max(0, Number(options.planCurrentIndex) || 0);
    const nextStep = queue.length ? describeStep(queue[0]?.step) : "nichts geplant";
    const consoleEl = refs.consoleEl || null;
    if (!consoleEl) return;

    consoleEl.classList.remove("is-idle", "is-connected", "is-running", "is-queued", "is-done", "is-error");
    const showExpanded = hasToy || ["running", "queued", "done", "error"].includes(state.planState);
    const stateClass = ["running", "queued", "done", "error"].includes(state.planState)
      ? `is-${state.planState}`
      : hasToy
      ? "is-connected"
      : "is-idle";
    consoleEl.classList.add(stateClass);
    consoleEl.classList.toggle("is-collapsed", !showExpanded);
    if (state.statusTone === "error") consoleEl.classList.add("is-error");

    if (refs.toyEl) refs.toyEl.textContent = state.toyLabel || "Kein Toy verbunden";
    if (refs.compactStatusEl) {
      refs.compactStatusEl.textContent = hasToy ? (state.toyLabel || "Kein Toy verbunden") : (state.statusText || "Lovense: Status unbekannt.");
    }
    if (refs.planModeEl) {
      refs.planModeEl.textContent =
        state.planState === "running"
          ? "KI-Steuerung aktiv"
          : state.planState === "queued"
          ? "KI-Plan geladen"
          : state.planState === "done"
          ? "KI-Plan abgeschlossen"
          : state.planState === "error"
          ? "KI-Plan Fehler"
          : hasToy
          ? "Autopilot bereit"
          : "KI-Steuerung inaktiv";
    }
    if (refs.planCommandEl) {
      refs.planCommandEl.textContent = state.currentLabel || "wartet";
    }
    if (refs.planTitleEl) {
      if (state.planState === "running" || state.planState === "queued" || state.planState === "done" || state.planState === "error") {
        refs.planTitleEl.textContent = planTitle || "Session-Plan";
      } else if (hasToy) {
        refs.planTitleEl.textContent = "Bereit fuer KI-Steuerung";
      } else {
        refs.planTitleEl.textContent = "Keine aktive KI-Session";
      }
    }
    if (refs.planStepEl) {
      refs.planStepEl.textContent = planTotal > 0 ? `Schritt ${planCurrentIndex}/${planTotal}` : "Schritt 0/0";
    }
    if (refs.nextStepEl) {
      refs.nextStepEl.textContent = `Als Naechstes: ${nextStep}`;
    }
  }

  function setStatus(options = {}) {
    const state = options.state || {};
    state.statusText = String(options.text || "").trim() || "Lovense: Status unbekannt.";
    const lowered = state.statusText.toLowerCase();
    state.statusTone =
      lowered.includes("fehler") || lowered.includes("fehlgeschlagen")
        ? "error"
        : lowered.includes("verbunden") || lowered.includes("bereit")
        ? "ok"
        : "neutral";
    const refs = options.refs || {};
    if (refs.statusEl) refs.statusEl.textContent = state.statusText;
    if (refs.compactStatusEl) {
      refs.compactStatusEl.textContent = options.hasToy ? (state.toyLabel || "Kein Toy verbunden") : state.statusText;
    }
    renderConsole(options);
  }

  function renderPlanStatus(options = {}) {
    const state = options.state || {};
    state.planState = String(options.planState || "").trim().toLowerCase() || "idle";
    if (state.planState === "done") state.currentLabel = "fertig";
    else if (state.planState === "idle") state.currentLabel = "";
    else if (!state.currentLabel) state.currentLabel = formatPlanCommand(options.command);
    renderConsole(options);
  }

  function resetPlanStatus(options = {}) {
    const state = options.state || {};
    state.currentLabel = "";
    renderPlanStatus({
      ...options,
      planState: "idle",
      planTitle: "Keine aktive KI-Session",
      planTotal: 0,
      planCurrentIndex: 0,
      command: "",
    });
  }

  function setPlanQueued(options = {}) {
    const state = options.state || {};
    state.currentLabel = "wartet";
    renderPlanStatus({
      ...options,
      planState: "queued",
      command: "",
    });
  }

  function setPlanProgress(options = {}) {
    const state = options.state || {};
    state.currentLabel = formatPlanCommand(options.command);
    renderPlanStatus({
      ...options,
      planState: "running",
    });
  }

  window.ChasteasePlayLovenseUI = {
    describeStep,
    renderConsole,
    renderPlanStatus,
    resetPlanStatus,
    setPlanProgress,
    setPlanQueued,
    setStatus,
  };
})();
