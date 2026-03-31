(() => {
  function renderSummary(data, options = {}) {
    const session = data.session || {};
    const setText = typeof options.setText === "function" ? options.setText : () => {};
    const setAvatar = typeof options.setAvatar === "function" ? options.setAvatar : () => {};
    const setPersonaLabel = typeof options.setPersonaLabel === "function" ? options.setPersonaLabel : () => {};
    const formatDate = typeof options.formatDate === "function" ? options.formatDate : (value) => String(value ?? "");
    const formatSecs = typeof options.formatSecs === "function" ? options.formatSecs : (value) => String(value ?? "");

    setAvatar("dash-keyholder-avatar", session.persona_avatar_url || null);
    setAvatar("dash-player-avatar", session.player_avatar_url || null);
    setText("dash-wearer", session.player_nickname);
    setPersonaLabel(session.persona_name);
    setText("dash-session-id", session.session_id ? `#${session.session_id}` : "—");
    setText("dash-status-pill", session.status || "—");
    setText("dash-status-text", session.status || "—");
    setText("dash-lock-start", formatDate(session.lock_start));
    setText("dash-lock-end", formatDate(session.lock_end));
    setText("dash-timer-frozen", session.timer_frozen ? "eingefroren" : "laufend");
    setText("dash-min-duration", formatSecs(session.min_duration_seconds));
    setText("dash-max-duration", session.max_duration_seconds ? formatSecs(session.max_duration_seconds) : "—");
    setText("dash-active-seal", session.active_seal_number || "—");
    setText(
      "dash-last-opening",
      session.last_opening_status
        ? `${session.last_opening_status}${session.last_opening_due_back_at ? ` (Rueckgabe: ${formatDate(session.last_opening_due_back_at)})` : ""}`
        : "—"
    );
    setText("dash-total-played", formatSecs(session.total_played_seconds));
    setText("dash-exp", data.experience_level);
    setText("dash-style", data.style);
    setText("dash-goal", data.goal);
    setText("dash-boundary", data.boundary);
    setText(
      "dash-task-stats",
      `Gesamt: ${session.task_total ?? 0} | pending: ${session.task_pending ?? 0} | completed: ${session.task_completed ?? 0} | overdue: ${session.task_overdue ?? 0} | failed: ${session.task_failed ?? 0}`
    );
    setText("dash-task-penalty", formatSecs(session.task_penalty_total_seconds));
    setText("dash-hygiene-penalty", `${formatSecs(session.hygiene_penalty_total_seconds)} (Overrun: ${formatSecs(session.hygiene_overrun_total_seconds)})`);
    setText("dash-llm-provider", data.llm?.provider || "—");
    setText("dash-llm-chat", data.llm?.chat_model || "—");
    setText("dash-llm-key", data.llm?.api_key_stored ? "hinterlegt" : "nicht gesetzt");

    const rulesEl = document.getElementById("dash-hygiene-rules");
    if (rulesEl) {
      const maxMinutes = Math.max(1, Math.floor(Number(session.hygiene_opening_max_duration_seconds || 900) / 60));
      rulesEl.textContent =
        `Regeln: Maximaldauer ${maxMinutes} Minuten. Bei Ueberziehung gilt Penalty = max(Overrun, ${formatSecs(session.hygiene_overdue_penalty_min_seconds)}).`;
    }
  }

  function renderPersonaOptions(items, options = {}) {
    const select = document.getElementById("dash-persona-select");
    if (!select) return;
    const escapeHtml = typeof options.escapeHtml === "function" ? options.escapeHtml : (value) => String(value ?? "");
    const selectedPersonaId = Number(options.selectedPersonaId || 0);
    const safeItems = Array.isArray(items) ? items : [];
    const rendered = ['<option value="">Keyholderin waehlen</option>'];
    safeItems.forEach((item) => {
      const id = Number(item?.id || 0);
      const name = String(item?.name || "").trim();
      if (!id || !name) return;
      rendered.push(`<option value="${id}">${escapeHtml(name)}</option>`);
    });
    select.innerHTML = rendered.join("");
    if (selectedPersonaId && safeItems.some((item) => Number(item?.id || 0) === selectedPersonaId)) {
      select.value = String(selectedPersonaId);
    } else {
      select.value = "";
    }
  }

  window.ChasteaseDashboardSessionUI = {
    renderPersonaOptions,
    renderSummary,
  };
})();
