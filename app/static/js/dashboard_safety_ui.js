(() => {
  function bindSafetyAndHygiene(options = {}) {
    const state = options.state || {};
    const get = typeof options.get === "function" ? options.get : async () => ({});
    const post = typeof options.post === "function" ? options.post : async () => ({});
    const renderQuota = typeof options.renderQuota === "function" ? options.renderQuota : () => {};
    const setPhase = typeof options.setPhase === "function" ? options.setPhase : () => {};
    const setText = typeof options.setText === "function" ? options.setText : () => {};
    const loadSummary = typeof options.loadSummary === "function" ? options.loadSummary : async () => {};
    const loadHygieneQuota = typeof options.loadHygieneQuota === "function" ? options.loadHygieneQuota : async () => {};
    const formatDate = typeof options.formatDate === "function" ? options.formatDate : (value) => String(value ?? "");
    const sessionId = Number(options.sessionId || 0);
    if (!sessionId) return;

    async function handleSafety(action) {
      const endpoint = action === "safeword"
        ? `/api/sessions/${sessionId}/safety/safeword`
        : `/api/sessions/${sessionId}/safety/traffic-light`;
      const payload = action === "safeword" ? {} : { color: action };
      await post(endpoint, payload);
      await loadSummary();
    }

    document.getElementById("dash-hygiene-open")?.addEventListener("click", async () => {
      const btn = document.getElementById("dash-hygiene-open");
      const statusEl = document.getElementById("dash-hygiene-status");
      if (btn) btn.disabled = true;
      try {
        let oldSealNumber = null;
        try {
          const sealData = await get(`/api/sessions/${sessionId}/seal-history`);
          const active = (sealData.entries || []).find((item) => item.status === "active");
          if (active) oldSealNumber = active.seal_number;
        } catch (_) {}
        state.hygieneUsesSeal = Boolean(oldSealNumber);
        const data = await post(`/api/sessions/${sessionId}/hygiene/openings`, {
          duration_seconds: Math.max(60, Math.round(Number(state.hygieneConfiguredDurationSeconds) || 900)),
          old_seal_number: oldSealNumber,
        });
        state.hygieneOpeningId = data.opening_id;
        if (statusEl) statusEl.textContent = `Rueck bis: ${formatDate(data.due_back_at)}`;
        renderQuota(data.quota);
        setPhase("relock");
        await loadSummary();
      } catch (err) {
        if (statusEl) statusEl.textContent = `Fehler: ${String(err)}`;
      } finally {
        if (btn) btn.disabled = false;
      }
    });

    document.getElementById("dash-hygiene-relock")?.addEventListener("click", async () => {
      const btn = document.getElementById("dash-hygiene-relock");
      const statusEl = document.getElementById("dash-hygiene-status");
      if (!state.hygieneOpeningId) return;
      let newSeal = null;
      if (state.hygieneUsesSeal) {
        newSeal = document.getElementById("dash-hygiene-new-seal")?.value?.trim();
        if (!newSeal) {
          if (statusEl) statusEl.textContent = "Neue Plombennummer ist erforderlich.";
          return;
        }
      }
      if (btn) btn.disabled = true;
      try {
        await post(`/api/sessions/${sessionId}/hygiene/openings/${state.hygieneOpeningId}/relock`, {
          new_seal_number: newSeal,
        });
        state.hygieneOpeningId = null;
        state.hygieneUsesSeal = false;
        setPhase("open");
        setText("dash-hygiene-status", "Wiederverschlossen");
        const sealInput = document.getElementById("dash-hygiene-new-seal");
        if (sealInput) sealInput.value = "";
        await loadSummary();
        await loadHygieneQuota();
      } catch (err) {
        if (statusEl) statusEl.textContent = `Fehler: ${String(err)}`;
      } finally {
        if (btn) btn.disabled = false;
      }
    });

    document.getElementById("dash-resume-session")?.addEventListener("click", async () => {
      const btn = document.getElementById("dash-resume-session");
      if (btn) btn.disabled = true;
      try {
        await post(`/api/sessions/${sessionId}/safety/resume`, {});
        await loadSummary();
        if (btn) btn.remove();
      } catch (_) {
        if (btn) btn.disabled = false;
      }
    });

    document.getElementById("dash-safety-green")?.addEventListener("click", () => { handleSafety("green").catch(() => {}); });
    document.getElementById("dash-safety-yellow")?.addEventListener("click", () => { handleSafety("yellow").catch(() => {}); });
    document.getElementById("dash-safety-red")?.addEventListener("click", () => { handleSafety("red").catch(() => {}); });
    document.getElementById("dash-safety-safeword")?.addEventListener("click", () => { handleSafety("safeword").catch(() => {}); });
  }

  window.ChasteaseDashboardSafetyUI = {
    bindSafetyAndHygiene,
  };
})();
