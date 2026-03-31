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

  function renderRoleplayState(options = {}) {
    const roleplayState = options.roleplayState || {};
    const relationshipMemory = options.relationshipMemory || {};
    const phaseProgress = options.phaseProgress || {};
    const roleplayToggle = options.roleplayToggle || null;
    const relationship = roleplayState.relationship || {};
    const protocol = roleplayState.protocol || {};
    const scene = roleplayState.scene || {};
    const sceneTitleRaw = String(scene.title || "").trim();
    const sceneHeading = sceneTitleRaw || "Einstimmung";
    const roleplayUi = window.ChasteaseRoleplayUI || {};
    const chatUi = window.ChasteasePlayChatUI || {};
    const uiCommon = window.ChasteaseUiCommon || {};
    const escapeHtml = typeof chatUi.escapeHtml === "function"
      ? chatUi.escapeHtml
      : (typeof uiCommon.escapeHtml === "function" ? uiCommon.escapeHtml : (value) => String(value ?? ""));
    const setText = typeof uiCommon.setText === "function" ? uiCommon.setText : () => {};
    const setHtml = typeof uiCommon.setHtml === "function" ? uiCommon.setHtml : () => {};
    const renderPillList = typeof uiCommon.renderPillList === "function" ? uiCommon.renderPillList : () => "";

    if (roleplayToggle) {
      roleplayToggle.textContent = sceneHeading;
      roleplayToggle.title = sceneHeading;
      roleplayToggle.setAttribute("aria-label", sceneHeading);
    }

    const phaseIndex = Number(phaseProgress.phase_index || 0);
    const phaseCount = Number(phaseProgress.phase_count || 0);
    const phaseMeters = typeof roleplayUi.renderPhaseMeters === "function"
      ? roleplayUi.renderPhaseMeters({
          phaseProgress,
          esc: escapeHtml,
          meterClass: "roleplay-meter",
          topClass: "roleplay-meter-top",
          trackClass: "roleplay-meter-track",
          fillClass: "roleplay-meter-fill",
          metaClass: "roleplay-meter-meta",
          deltaClass: "roleplay-meter-delta",
          phaseClass: "roleplay-meter-phase",
        })
      : "";

    setText("play-scene-pressure", scene.pressure || "—");
    setText("play-scene-title", sceneHeading);
    setText("play-scene-objective", scene.objective || "—");
    setText("play-scene-next-beat", scene.next_beat || "—");
    setText("play-scene-consequence", scene.last_consequence || "keine");
    setText("play-control-level", relationship.control_level || "structured");
    setText("play-phase-chip", phaseIndex && phaseCount ? `Phase ${phaseIndex}/${phaseCount}` : "—");
    setText("play-phase-title", phaseProgress.active_phase_title || "Keine Phase aktiv");
    setText(
      "play-phase-summary",
      phaseIndex && phaseCount
        ? "Jedes Kriterium startet pro Phase neu bei 0 und muss in dieser Phase erarbeitet werden."
        : "Kein Szenario aktiv."
    );
    setHtml("play-phase-progress-meters", phaseMeters, "Keine Phasendaten");

    setHtml(
      "play-relationship-meters",
      typeof roleplayUi.renderRelationshipMeters === "function"
        ? roleplayUi.renderRelationshipMeters({
            relationship,
            esc: escapeHtml,
            meterClass: "roleplay-meter",
            topClass: "roleplay-meter-top",
            trackClass: "roleplay-meter-track",
            fillClass: "roleplay-meter-fill",
            metaClass: "roleplay-meter-meta",
            deltaClass: "roleplay-meter-delta",
            phaseClass: "roleplay-meter-phase",
            metricDefs: METRIC_DEFS,
          })
        : ""
    );

    setHtml(
      "play-active-rules",
      renderPillList(protocol.active_rules, "Keine aktiven Regeln", {
        escapeHtml,
        pillClass: "roleplay-pill ui-pill",
        emptyClass: "roleplay-empty ui-empty",
      })
    );
    setHtml(
      "play-open-orders",
      renderPillList(protocol.open_orders, "Keine offenen Anweisungen", {
        escapeHtml,
        pillClass: "roleplay-pill ui-pill",
        emptyClass: "roleplay-empty ui-empty",
      })
    );

    const sessionsConsidered = Number(relationshipMemory.sessions_considered || 0);
    setText("play-memory-count", sessionsConsidered);
    setText("play-memory-control", relationshipMemory.dominant_control_level || "noch offen");
    setText(
      "play-memory-summary",
      sessionsConsidered > 0
        ? relationshipMemory.summary || "Langzeitdynamik verfuegbar."
        : "Noch keine abgeschlossenen Vergleichssessions."
    );
    setHtml(
      "play-memory-highlights",
      renderPillList(
        relationshipMemory.highlights,
        sessionsConsidered > 0 ? "Noch keine markante Tendenz" : "Keine Langzeitdaten",
        {
          escapeHtml,
          pillClass: "roleplay-pill ui-pill",
          emptyClass: "roleplay-empty ui-empty",
        }
      )
    );
  }

  window.ChasteasePlayRoleplayStateUI = {
    renderRoleplayState,
  };
})();
