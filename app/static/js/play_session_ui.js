(() => {
  function renderHygieneQuota(quotaData) {
    const el = document.getElementById("psd-hygiene-quota");
    const nextEl = document.getElementById("psd-hygiene-next-allowed");
    if (!el || !quotaData) return;

    const limits = quotaData.limits || {};
    const used = quotaData.used || {};
    const remaining = quotaData.remaining || {};
    const nextAllowedAt = quotaData.next_allowed_at || {};
    const fmt = (value) => (value === null || value === undefined ? "unbegrenzt" : String(value));

    el.textContent =
      `Kontingent - Tag: ${fmt(used.daily)}/${fmt(limits.daily)} (rest ${fmt(remaining.daily)}), ` +
      `Woche: ${fmt(used.weekly)}/${fmt(limits.weekly)} (rest ${fmt(remaining.weekly)}), ` +
      `Monat: ${fmt(used.monthly)}/${fmt(limits.monthly)} (rest ${fmt(remaining.monthly)})`;

    if (!nextEl) return;

    function fmtNextReset(isoStr, label) {
      if (!isoStr) return null;
      try {
        const diff = new Date(isoStr).getTime() - Date.now();
        if (diff <= 0) return null;
        const d = Math.floor(diff / 86400000);
        const h = Math.floor((diff % 86400000) / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        const countdown = d > 0 ? `${d}T ${h}h ${m}m` : h > 0 ? `${h}h ${m}m` : `${m}m`;
        const dateStr = new Date(isoStr).toLocaleString("de-DE", {
          day: "2-digit",
          month: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        });
        return `${label}: ${dateStr} (in ${countdown})`;
      } catch (_) {
        return null;
      }
    }

    if (nextAllowedAt.overall) {
      const formatted = fmtNextReset(nextAllowedAt.overall, "Nächste Öffnung erlaubt ab");
      if (formatted) {
        nextEl.textContent = formatted;
        nextEl.style.color = "var(--color-warn, #ffb300)";
        return;
      }
    }

    const nextPeriodStart = quotaData.next_period_start || {};
    const resetLines = [];
    if (nextPeriodStart.daily) {
      const line = fmtNextReset(nextPeriodStart.daily, "Tageslimit setzt zurück");
      if (line) resetLines.push(line);
    }
    if (nextPeriodStart.weekly) {
      const line = fmtNextReset(nextPeriodStart.weekly, "Wochenlimit setzt zurück");
      if (line) resetLines.push(line);
    }
    if (nextPeriodStart.monthly) {
      const line = fmtNextReset(nextPeriodStart.monthly, "Monatslimit setzt zurück");
      if (line) resetLines.push(line);
    }
    nextEl.textContent = resetLines.join(" · ");
    nextEl.style.color = "";
  }

  function setHygienePhase(phase, usesSeal) {
    const openArea = document.getElementById("psd-hygiene-open-area");
    const relockArea = document.getElementById("psd-hygiene-relock-area");
    if (phase === "relock") {
      openArea?.classList.add("is-hidden");
      relockArea?.classList.remove("is-hidden");
    } else {
      openArea?.classList.remove("is-hidden");
      relockArea?.classList.add("is-hidden");
    }
    const sealRow = document.getElementById("psd-hygiene-seal-row");
    if (sealRow) sealRow.style.display = phase === "relock" && usesSeal ? "" : "none";
  }

  function setVerifySeal(sealNumber) {
    const row = document.getElementById("play-verify-seal-row");
    const code = document.getElementById("play-verify-seal");
    if (sealNumber) {
      if (code) code.textContent = sealNumber;
      if (row) row.style.display = "";
      return;
    }
    if (row) row.style.display = "none";
  }

  function renderVerifications(items) {
    const el = document.getElementById("play-verify-history");
    if (!el) return;
    if (!Array.isArray(items) || !items.length) {
      el.innerHTML = "<p class='verify-empty'>Noch keine Verifikationen.</p>";
      return;
    }
    const latest = items.slice(-1);
    el.innerHTML = latest
      .map((item) => {
        const pill = item.status === "confirmed"
          ? "<span class='verify-pill confirmed'>&#10003; Best&auml;tigt</span>"
          : item.status === "suspicious"
            ? "<span class='verify-pill suspicious'>&#9888; Verdacht</span>"
            : "<span class='verify-pill pending'>&#8987; Ausstehend</span>";
        const analysis = item.analysis ? `<p class='verify-analysis'>${String(item.analysis).replace(/</g, "&lt;")}</p>` : "";
        const seal = item.requested_seal_number ? `<span class='verify-seal-tag'>#${item.requested_seal_number}</span>` : "";
        return `<div class="verify-card">${pill}${seal}${analysis}</div>`;
      })
      .join("");
  }

  function bindSessionControls(options = {}) {
    const sessionId = Number(options.sessionId || 0);
    if (!sessionId) return;
    const state = options.state || {};
    const get = typeof options.get === "function" ? options.get : async () => ({});
    const post = typeof options.post === "function" ? options.post : async () => ({});
    const write = typeof options.write === "function" ? options.write : () => {};
    const loadHygieneQuota = typeof options.loadHygieneQuota === "function" ? options.loadHygieneQuota : async () => {};
    const loadVerifications = typeof options.loadVerifications === "function" ? options.loadVerifications : async () => {};
    const listTasks = typeof options.listTasks === "function" ? options.listTasks : async () => {};
    const onSafety = typeof options.onSafety === "function" ? options.onSafety : async () => {};
    const onSafeword = typeof options.onSafeword === "function" ? options.onSafeword : async () => {};
    const closeSafetyDropdown = typeof options.closeSafetyDropdown === "function" ? options.closeSafetyDropdown : () => {};
    const updateSafetyToggleStyle = typeof options.updateSafetyToggleStyle === "function" ? options.updateSafetyToggleStyle : () => {};

    document.getElementById("play-safety-green")?.addEventListener("click", () => {
      closeSafetyDropdown();
      updateSafetyToggleStyle("green");
      onSafety("green").catch(() => {});
    });
    document.getElementById("play-safety-yellow")?.addEventListener("click", () => {
      closeSafetyDropdown();
      updateSafetyToggleStyle("yellow");
      onSafety("yellow").catch(() => {});
    });
    document.getElementById("play-safety-red")?.addEventListener("click", () => {
      closeSafetyDropdown();
      updateSafetyToggleStyle("red");
      onSafety("red").catch(() => {});
    });
    document.getElementById("play-safety-safeword")?.addEventListener("click", () => {
      closeSafetyDropdown();
      updateSafetyToggleStyle("safeword");
      onSafeword().catch(() => {});
    });

    document.getElementById("psd-hygiene-open")?.addEventListener("click", async () => {
      const btn = document.getElementById("psd-hygiene-open");
      const statusEl = document.getElementById("psd-hygiene-status");
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
        if (statusEl) {
          statusEl.textContent = `⏱️ Rück bis: ${new Date(data.due_back_at).toLocaleTimeString("de-DE")}`;
          statusEl.style.color = "var(--color-warn,#ffb300)";
        }
        renderHygieneQuota(data.quota);
        setHygienePhase("relock", state.hygieneUsesSeal);
      } catch (err) {
        if (statusEl) {
          statusEl.textContent = `Fehler: ${String(err)}`;
          statusEl.style.color = "var(--color-error,#f44)";
        }
      } finally {
        if (btn) btn.disabled = false;
      }
    });

    document.getElementById("psd-hygiene-relock")?.addEventListener("click", async () => {
      const statusEl = document.getElementById("psd-hygiene-status");
      const btn = document.getElementById("psd-hygiene-relock");
      if (!state.hygieneOpeningId) return;
      let newSeal = null;
      if (state.hygieneUsesSeal) {
        newSeal = document.getElementById("psd-hygiene-new-seal")?.value?.trim();
        if (!newSeal) {
          if (statusEl) {
            statusEl.textContent = "Neue Plombennummer ist erforderlich.";
            statusEl.style.color = "var(--color-error,#f44)";
          }
          return;
        }
      }
      if (btn) btn.disabled = true;
      try {
        const data = await post(`/api/sessions/${sessionId}/hygiene/openings/${state.hygieneOpeningId}/relock`, {
          new_seal_number: newSeal,
        });
        state.hygieneOpeningId = null;
        state.hygieneUsesSeal = false;
        setHygienePhase("open", false);
        const sealInput = document.getElementById("psd-hygiene-new-seal");
        if (sealInput) sealInput.value = "";
        if (statusEl) {
          statusEl.textContent = "Wiederverschlossen ✓";
          statusEl.style.color = "var(--color-success,#81c784)";
        }
        if (data.new_seal_number) {
          state.verifySealNumber = data.new_seal_number;
          setVerifySeal(data.new_seal_number);
        }
        await loadHygieneQuota();
        write("Hygiene Wiederverschluss", data);
      } catch (err) {
        if (statusEl) {
          statusEl.textContent = `Fehler: ${String(err)}`;
          statusEl.style.color = "var(--color-error,#f44)";
        }
      } finally {
        if (btn) btn.disabled = false;
      }
    });

    document.getElementById("play-verify-file")?.addEventListener("change", (event) => {
      const file = event.target?.files?.[0];
      const label = event.target?.closest(".verify-file-label")?.querySelector("span");
      if (label) label.textContent = file ? file.name : "Foto wählen";
    });

    document.getElementById("play-request-verify")?.addEventListener("click", async () => {
      const btn = document.getElementById("play-request-verify");
      if (btn) btn.disabled = true;
      try {
        let sealNumber = null;
        try {
          const sealData = await get(`/api/sessions/${sessionId}/seal-history`);
          const active = (sealData.entries || []).find((item) => item.status === "active");
          if (active) sealNumber = active.seal_number;
        } catch (_) {}

        const data = await post(`/api/sessions/${sessionId}/verifications/request`, {
          requested_seal_number: sealNumber,
        });
        state.pendingVerifyId = data.verification_id;
        state.verifySealNumber = sealNumber;
        setVerifySeal(sealNumber);
        document.getElementById("play-verify-upload-area")?.classList.remove("is-hidden");
        write("Verifikation angefordert", data);
      } catch (err) {
        write("Fehler Verifikation", { error: String(err) });
      } finally {
        if (btn) btn.disabled = false;
      }
    });

    document.getElementById("play-verify-submit")?.addEventListener("click", async () => {
      if (!state.pendingVerifyId) return;
      const fileInput = document.getElementById("play-verify-file");
      const file = fileInput?.files?.[0];
      if (!file) {
        write("Hinweis", { error: "Kein Bild ausgewählt." });
        return;
      }

      const submitBtn = document.getElementById("play-verify-submit");
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Wird geprüft…";
      }

      try {
        const form = new FormData();
        form.append("file", file);
        if (state.verifySealNumber) form.append("observed_seal_number", state.verifySealNumber);

        const response = await fetch(`/api/sessions/${sessionId}/verifications/${state.pendingVerifyId}/upload`, {
          method: "POST",
          body: form,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(JSON.stringify(data));

        state.pendingVerifyId = null;
        state.verifySealNumber = null;
        document.getElementById("play-verify-upload-area")?.classList.add("is-hidden");
        if (fileInput) fileInput.value = "";
        const criteriaHint = document.getElementById("play-verify-criteria-hint");
        if (criteriaHint) {
          criteriaHint.textContent = "";
          criteriaHint.style.display = "none";
        }
        await loadVerifications();
        await listTasks();
        write("Verifikation", data);
      } catch (err) {
        write("Fehler Upload", { error: String(err) });
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = "Hochladen & Prüfen";
        }
      }
    });
  }

  window.ChasteasePlaySessionUI = {
    bindSessionControls,
    renderHygieneQuota,
    renderVerifications,
    setHygienePhase,
    setVerifySeal,
  };
})();
