(() => {
  function moduleName(key) {
    return {
      posture_training: "Posture Training",
      dont_move: "Don't Move",
      tiptoeing: "Tiptoeing",
    }[key] || key;
  }

  function difficultyLabel(key) {
    return { easy: "Leicht", medium: "Mittel", hard: "Schwer" }[key] || key;
  }

  function runBadge(run) {
    if (run.status !== "completed") return ["active", run.status];
    if (run.end_reason === "time_elapsed") return ["warn", "Zeit abgelaufen"];
    if (run.failed_steps === 0 && run.unplayed_steps === 0) return ["ok", "Bestanden"];
    if (run.unplayed_steps > 0 && run.failed_steps === 0) return ["warn", "Unvollstaendig"];
    return ["fail", "Fehler"];
  }

  function renderRunReport(run, options = {}) {
    const summary = run.summary || {};
    const checks = Array.isArray(summary.checks) ? summary.checks : [];
    const steps = Array.isArray(run.steps) ? run.steps : [];
    const total = Number(summary.total_steps || 0);
    const scheduled = Number(summary.scheduled_steps || total);
    const unplayed = Number(summary.unplayed_steps || Math.max(0, scheduled - total));
    const passed = Number(summary.passed_steps || 0);
    const failed = Number(summary.failed_steps || 0);
    const misses = Number(summary.miss_count || run.miss_count || 0);
    const penaltyApplied = Boolean(summary.session_penalty_applied);
    const endReason = summary.end_reason === "time_elapsed" ? "Zeit abgelaufen" : "Alle Schritte abgeschlossen";
    const checksWithImages = checks.filter((entry) => entry && entry.capture_url);
    const checksWithoutImages = checks.filter((entry) => entry && !entry.capture_url);
    const escapeHtml = typeof options.escapeHtml === "function" ? options.escapeHtml : (value) => String(value ?? "");

    let html = `<div class="dash-run-stats">
      <span>Beendigung: <strong>${escapeHtml(endReason)}</strong></span>
      <span>Gespielt: <strong>${passed}/${total}</strong></span>
      <span>Fehler: <strong>${failed}</strong></span>
      <span>Verfehlungen: <strong>${misses}</strong></span>
      <span>Checks: <strong>${checks.length}</strong></span>
      ${unplayed > 0 ? `<span>Nicht gespielt: <strong>${unplayed}/${scheduled}</strong></span>` : ""}
      ${penaltyApplied ? `<span>Session-Penalty ausgeloest</span>` : ""}
    </div>`;

    if (summary.ai_assessment) {
      html += `<div class="dash-run-ai">${escapeHtml(summary.ai_assessment)}</div>`;
    }
    if (failed > 0 && misses === 0 && checks.length === 0) {
      html += `<div class="dash-run-note">Run fehlgeschlagen, aber ohne serverseitigen Check-Eintrag. Das spricht fuer ein Upload- oder Persistenzproblem im Live-Run.</div>`;
    }
    if (steps.length) {
      html += `<div class="dash-run-steps">`;
      steps.forEach((step, index) => {
        html += `<article class="dash-run-step">
          <div><strong>${index + 1}. ${escapeHtml(step.posture_name || "Pose")}</strong></div>
          <div>Status: ${escapeHtml(step.status || "unknown")} · Verifikationen: ${Number(step.verification_count || 0)}</div>
          <div>${escapeHtml(step.last_analysis || "Keine serverseitige Analyse gespeichert.")}</div>
        </article>`;
      });
      html += `</div>`;
    }
    if (checksWithImages.length || checksWithoutImages.length) {
      html += `<div class="dash-run-checks">`;
      checksWithImages.forEach((entry, index) => {
        const url = escapeHtml(entry.capture_url || "");
        html += `<article class="dash-run-check">
          <img src="${url}" alt="Kontrollbild ${index + 1}" data-dash-run-image="${url}" />
          <div><strong>${escapeHtml(entry.posture_name || "Pose")}</strong></div>
          <div>${escapeHtml(entry.analysis || "—")}</div>
        </article>`;
      });
      checksWithoutImages.forEach((entry) => {
        html += `<article class="dash-run-check">
          <div><strong>${escapeHtml(entry.posture_name || "Pose")}</strong></div>
          <div>${escapeHtml(entry.analysis || "—")}</div>
        </article>`;
      });
      html += `</div>`;
    } else {
      html += `<p class="dash-copy">Keine gespeicherten Kontrollbilder.</p>`;
    }

    return html;
  }

  function renderRunHistory(items, options = {}) {
    const listEl = options.listEl || document.getElementById("dash-runs-list");
    if (!listEl) return;
    const safeItems = Array.isArray(items) ? items : [];
    const escapeHtml = typeof options.escapeHtml === "function" ? options.escapeHtml : (value) => String(value ?? "");
    const formatDate = typeof options.formatDate === "function" ? options.formatDate : (value) => String(value ?? "");
    const formatSecs = typeof options.formatSecs === "function" ? options.formatSecs : (value) => String(value ?? "");

    if (!safeItems.length) {
      listEl.innerHTML = "<p class='dash-copy'>Noch keine Spiele in dieser Session.</p>";
      return;
    }

    listEl.innerHTML = `<div class="dash-run-list"></div>`;
    const runList = listEl.querySelector(".dash-run-list");
    safeItems.forEach((run) => {
      const [badgeClass, badgeLabel] = runBadge(run);
      const card = document.createElement("article");
      card.className = "dash-run-card";
      card.innerHTML = `
        <button class="dash-run-head" type="button">
          <div class="dash-run-title">
            <strong>${escapeHtml(moduleName(run.module_key))}</strong>
            <span class="dash-run-meta">${escapeHtml(difficultyLabel(run.difficulty_key))} · ${escapeHtml(formatDate(run.effective_started_at || run.started_at))} · ${escapeHtml(formatSecs(run.elapsed_duration_seconds || 0))}</span>
          </div>
          <span class="dash-run-badge ${badgeClass}">${escapeHtml(badgeLabel)}</span>
        </button>
        <div class="dash-run-body"><p class="dash-copy">Wird geladen …</p></div>
      `;
      const head = card.querySelector(".dash-run-head");
      const body = card.querySelector(".dash-run-body");
      head?.addEventListener("click", async () => {
        const isOpen = card.hasAttribute("open");
        if (isOpen) {
          card.removeAttribute("open");
          return;
        }
        card.setAttribute("open", "");
        if (body?.dataset.loaded !== "1" && typeof options.loadRunReport === "function") {
          await options.loadRunReport(run.id, body);
          body.dataset.loaded = "1";
        }
      });
      runList?.appendChild(card);
    });
  }

  document.addEventListener("click", (event) => {
    const image = event.target.closest("[data-dash-run-image]");
    if (!(image instanceof HTMLElement)) return;
    const url = String(image.getAttribute("data-dash-run-image") || "").trim();
    if (url) window.open(url, "_blank");
  });

  window.ChasteaseDashboardRunsUI = {
    renderRunHistory,
    renderRunReport,
  };
})();
