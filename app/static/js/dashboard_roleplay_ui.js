(() => {
  const METRIC_DEFS = [
    ["Trust", "trust"],
    ["Obedience", "obedience"],
    ["Resistance", "resistance"],
    ["Favor", "favor"],
    ["Strictness", "strictness"],
    ["Frustration", "frustration"],
    ["Attachment", "attachment"],
  ];

  function renderRoleplayState(roleplayState, phaseProgress = {}, options = {}) {
    const safeState = roleplayState || {};
    const relationship = safeState.relationship || {};
    const protocol = safeState.protocol || {};
    const scene = safeState.scene || {};
    const sceneTitleRaw = String(scene.title || "").trim();
    const sceneHeading = sceneTitleRaw || "Einstimmung";
    const uiCommon = window.ChasteaseUiCommon || {};
    const setText = typeof options.setText === "function" ? options.setText : (typeof uiCommon.setText === "function" ? uiCommon.setText : () => {});
    const fillPillList = typeof uiCommon.fillPillList === "function" ? uiCommon.fillPillList : () => {};
    const escapeHtml = typeof options.escapeHtml === "function"
      ? options.escapeHtml
      : (typeof uiCommon.escapeHtml === "function" ? uiCommon.escapeHtml : (value) => String(value ?? ""));
    const roleplayUi = window.ChasteaseRoleplayUI || {};

    setText("dash-scene-pressure", scene.pressure || "—");
    setText("dash-scene-title", sceneHeading);
    setText("dash-scene-objective", scene.objective || "—");
    setText("dash-scene-next-beat", scene.next_beat || "—");
    setText("dash-scene-consequence", scene.last_consequence || "keine");
    setText("dash-control-level", relationship.control_level || "structured");

    const phaseMeterEl = document.getElementById("dash-phase-progress-meters");
    if (phaseMeterEl) {
      const phaseIndex = Number(phaseProgress?.phase_index || 0);
      const phaseCount = Number(phaseProgress?.phase_count || 0);
      setText("dash-phase-chip", phaseIndex && phaseCount ? `Phase ${phaseIndex}/${phaseCount}` : "—");
      setText("dash-phase-title", phaseProgress?.active_phase_title || "Keine Phase aktiv");
      setText(
        "dash-phase-summary",
        phaseIndex && phaseCount
          ? "Jedes Kriterium startet pro Phase neu bei 0 und muss in dieser Phase erarbeitet werden."
          : "Kein Szenario aktiv."
      );
      phaseMeterEl.innerHTML = phaseIndex && phaseCount && typeof roleplayUi.renderPhaseMeters === "function"
        ? roleplayUi.renderPhaseMeters({
            phaseProgress,
            esc: escapeHtml,
            meterClass: "dash-meter",
            topClass: "dash-meter-top",
            trackClass: "dash-meter-track",
            fillClass: "dash-meter-fill",
            metaClass: "dash-meter-meta",
            deltaClass: "dash-meter-delta",
            phaseClass: "dash-meter-phase",
          })
        : "Keine Phasendaten";
    }

    const meterEl = document.getElementById("dash-relationship-meters");
    if (meterEl) {
      meterEl.innerHTML = typeof roleplayUi.renderRelationshipMeters === "function"
        ? roleplayUi.renderRelationshipMeters({
            relationship,
            esc: escapeHtml,
            meterClass: "dash-meter",
            topClass: "dash-meter-top",
            trackClass: "dash-meter-track",
            fillClass: "dash-meter-fill",
            metaClass: "dash-meter-meta",
            deltaClass: "dash-meter-delta",
            phaseClass: "dash-meter-phase",
            metricDefs: METRIC_DEFS,
          })
        : "";
    }

    fillPillList("dash-active-rules", protocol.active_rules, "Keine aktiven Regeln", {
      escapeHtml,
      pillClass: "dash-pill ui-pill",
      emptyClass: "dash-empty ui-empty",
    });
    fillPillList("dash-open-orders", protocol.open_orders, "Keine offenen Anweisungen", {
      escapeHtml,
      pillClass: "dash-pill ui-pill",
      emptyClass: "dash-empty ui-empty",
    });
  }

  function renderRelationshipMemory(memory, options = {}) {
    const safeMemory = memory || {};
    const sessionsConsidered = Number(safeMemory.sessions_considered || 0);
    const highlights = Array.isArray(safeMemory.highlights) ? safeMemory.highlights.filter(Boolean) : [];
    const setText = typeof options.setText === "function" ? options.setText : () => {};

    setText("dash-memory-count", sessionsConsidered);
    setText("dash-memory-control", safeMemory.dominant_control_level || "noch offen");
    setText(
      "dash-memory-summary",
      sessionsConsidered > 0
        ? safeMemory.summary || "Langzeitdynamik verfuegbar."
        : "Noch keine abgeschlossenen Vergleichssessions."
    );
    setText(
      "dash-memory-highlights",
      highlights.length ? highlights.join(" • ") : (sessionsConsidered > 0 ? "Noch keine markante Tendenz." : "—")
    );
  }

  window.ChasteaseDashboardRoleplayUI = {
    renderRelationshipMemory,
    renderRoleplayState,
  };
})();
