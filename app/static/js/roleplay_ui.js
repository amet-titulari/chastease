(() => {
  const DEFAULT_GROWTH_BASELINE = {
    trust: 55,
    obedience: 50,
    resistance: 20,
    favor: 40,
    strictness: 68,
    frustration: 18,
    attachment: 46,
  };

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function renderRelationshipMeters(options = {}) {
    const esc = typeof options.esc === "function" ? options.esc : (value) => String(value ?? "");
    const meterClass = String(options.meterClass || "roleplay-meter");
    const topClass = String(options.topClass || "roleplay-meter-top");
    const trackClass = String(options.trackClass || "roleplay-meter-track");
    const fillClass = String(options.fillClass || "roleplay-meter-fill");
    const metaClass = String(options.metaClass || "roleplay-meter-meta");
    const deltaClass = String(options.deltaClass || "roleplay-meter-delta");
    const phaseClass = String(options.phaseClass || "roleplay-meter-phase");
    const growthBaseline = { ...DEFAULT_GROWTH_BASELINE, ...(options.growthBaseline || {}) };
    const defs = Array.isArray(options.metricDefs) ? options.metricDefs : [];
    const relationship = options.relationship || {};

    return defs.map(([label, key]) => {
      const safe = clamp(Number(relationship?.[key]) || 0, 0, 100);
      const baseline = Number(growthBaseline[key]);
      const baseSafe = clamp(Number.isFinite(baseline) ? baseline : 0, 0, 100);
      const delta = Number.isFinite(baseline) ? safe - baseline : 0;
      const deltaText = delta > 0 ? `+${delta}` : `${delta}`;
      const deltaTone = delta > 0 ? "is-up" : (delta < 0 ? "is-down" : "is-flat");
      const resistanceTone = key === "resistance" ? " is-resistance" : "";
      const baseWidth = Math.min(safe, baseSafe);
      const growthWidth = Math.max(0, safe - baseSafe);
      return `
        <div class="${meterClass}">
          <div class="${topClass}">
            <span>${esc(label)}</span>
            <strong>${safe}</strong>
          </div>
          <div class="${trackClass}">
            <span class="${fillClass} ${fillClass}--base" style="width:${baseWidth}%"></span>
            ${growthWidth > 0 ? `<span class="${fillClass} ${fillClass}--growth" style="left:${baseWidth}%;width:${growthWidth}%"></span>` : ""}
          </div>
          <div class="${metaClass}">
            <span class="${deltaClass} ${deltaTone}${resistanceTone}">Seit Start: ${deltaText}</span>
            <span class="${phaseClass}">Skala: 0-100</span>
          </div>
        </div>
      `;
    }).join("");
  }

  function renderPhaseMeters(options = {}) {
    const esc = typeof options.esc === "function" ? options.esc : (value) => String(value ?? "");
    const meterClass = String(options.meterClass || "roleplay-meter");
    const topClass = String(options.topClass || "roleplay-meter-top");
    const trackClass = String(options.trackClass || "roleplay-meter-track");
    const fillClass = String(options.fillClass || "roleplay-meter-fill");
    const metaClass = String(options.metaClass || "roleplay-meter-meta");
    const deltaClass = String(options.deltaClass || "roleplay-meter-delta");
    const phaseClass = String(options.phaseClass || "roleplay-meter-phase");
    const phaseProgress = options.phaseProgress || {};
    const phaseIndex = Number(phaseProgress?.phase_index || 0);
    const phaseCount = Number(phaseProgress?.phase_count || 0);
    const scoreCount = Math.max(0, Number(phaseProgress?.score_count) || 0);
    const targetScoreCount = Math.max(0, Number(phaseProgress?.target_score_count) || 0);
    const remainingScoreCount = Math.max(0, Number(phaseProgress?.remaining_score_count) || 0);
    const criteriaPercent = targetScoreCount > 0 ? clamp((scoreCount / targetScoreCount) * 100, 0, 100) : 0;

    if (!(phaseIndex && phaseCount)) {
      return "";
    }

    const metrics = Array.isArray(phaseProgress?.metrics) ? phaseProgress.metrics : [];
    const metricHtml = metrics.map((item) => {
      const total = Math.max(1, Number(item?.progress_total) || 1);
      const value = clamp(Number(item?.progress_value) || 0, 0, total);
      const percent = clamp((value / total) * 100, 0, 100);
      const goalValue = clamp(Number(item?.goal_value) || 0, 0, 100);
      const status = item?.goal_reached ? "Ziel erreicht" : `Noch ${item?.remaining ?? 0} Punkte`;
      return `
        <div class="${meterClass}">
          <div class="${topClass}">
            <span>${esc(item?.label || "Wert")}</span>
            <strong>${value}/${total}</strong>
          </div>
          <div class="${trackClass}">
            <span class="${fillClass} ${fillClass}--growth" style="left:0;width:${percent}%"></span>
          </div>
          <div class="${metaClass}">
            <span class="${deltaClass}">Phase startet bei 0 · Ziel ${goalValue}</span>
            <span class="${phaseClass}">${esc(status)} · Phasenpunkte ${value}</span>
          </div>
        </div>
      `;
    }).join("");

    return `
      <div class="${meterClass}">
        <div class="${topClass}">
          <span>Erfuellte Kriterien dieser Phase</span>
          <strong>${scoreCount}/${targetScoreCount}</strong>
        </div>
        <div class="${trackClass}">
          <span class="${fillClass} ${fillClass}--growth" style="left:0;width:${criteriaPercent}%"></span>
        </div>
        <div class="${metaClass}">
          <span class="${deltaClass}">Alle Phasenpunkte starten bei 0</span>
          <span class="${phaseClass}">${remainingScoreCount} Kriterien bis zum Wechsel</span>
        </div>
      </div>
      ${metricHtml}
    `;
  }

  window.ChasteaseRoleplayUI = {
    renderRelationshipMeters,
    renderPhaseMeters,
  };
})();
