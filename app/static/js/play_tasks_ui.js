(() => {
  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatDeadline(deadlineAt) {
    if (!deadlineAt) return "";
    try {
      const deadline = new Date(deadlineAt);
      const now = new Date();
      const diffMs = deadline - now;
      if (diffMs < 0) return `<span class="ac-deadline ac-deadline--overdue">&#9201; &uuml;berf&auml;llig</span>`;
      const diffMin = Math.floor(diffMs / 60000);
      if (diffMin < 60) return `<span class="ac-deadline ac-deadline--soon">&#9201; noch ${diffMin}&nbsp;Min</span>`;
      const sameDay = deadline.toDateString() === now.toDateString();
      const time = deadline.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
      if (sameDay) return `<span class="ac-deadline">&#9201; heute ${time}</span>`;
      const date = deadline.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
      return `<span class="ac-deadline">&#9201; ${date}&nbsp;${time}</span>`;
    } catch (_) {
      return "";
    }
  }

  function buildSingleActionCard(item) {
    const title = escapeHtml(item?.title || "");
    const criteria = escapeHtml(item?.verification_criteria || "");
    const isVerify = !!item?.requires_verification;
    const criteriaHtml =
      isVerify && item?.verification_criteria
        ? `<p class="ac-hint">&#128203; ${escapeHtml(item.verification_criteria)}</p>`
        : "";
    const actions = isVerify
      ? `<button class="ac-btn ac-btn--photo" data-action="verify">&#128247; Fotoverifikation</button>
         <button class="ac-btn ac-btn--fail" data-action="fail">&#10007; Fail</button>`
      : `<button class="ac-btn ac-btn--done" data-action="complete">&#10003; Best&auml;tigung</button>
         <button class="ac-btn ac-btn--fail" data-action="fail">&#10007; Fail</button>`;
    const uploadArea = isVerify
      ? `<div class="ac-upload is-hidden">
          <p class="ac-seal-row" style="display:none">Plombe: <code class="ac-seal-code"></code></p>
          <label class="ac-file-label">
            <input type="file" accept="image/*" capture="environment" class="ac-file-input" />
            <span>Foto w&auml;hlen</span>
          </label>
          <button class="ac-submit-btn" type="button">Hochladen &amp; Pr&uuml;fen</button>
        </div>`
      : "";
    return `
      <div class="action-card ${isVerify ? "action-card--verify" : "action-card--task"}"
           data-task-id="${Number(item?.id || 0)}"
           data-requires-verification="${isVerify ? "1" : ""}"
           data-verification-criteria="${criteria}">
        <div class="ac-header">
          <div class="ac-header-row">
            <span class="ac-label">${isVerify ? "&#128247; Verifikation" : "&#128203; Task"}</span>
            <span class="ac-num">#${Number(item?.id || 0)}</span>
            ${formatDeadline(item?.deadline_at)}
          </div>
          <div class="ac-title">${title}</div>
        </div>
        ${criteriaHtml}
        <div class="ac-actions">${actions}</div>
        ${uploadArea}
      </div>`;
  }

  async function submitVerificationCard(card, options = {}) {
    const taskId = Number(card?.dataset?.taskId || 0);
    const verifyId = card?.dataset?.verifyId;
    const sealNumber = card?.dataset?.verifySeal || null;
    if (!verifyId) return;
    const write = typeof options.write === "function" ? options.write : () => {};
    const setPendingItems = typeof options.setPendingItems === "function" ? options.setPendingItems : () => {};
    const getPendingItems = typeof options.getPendingItems === "function" ? options.getPendingItems : () => [];
    const loadChat = typeof options.loadChat === "function" ? options.loadChat : async () => {};
    const listTasks = typeof options.listTasks === "function" ? options.listTasks : async () => {};
    const sessionId = Number(options.sessionId || 0);
    if (!sessionId) return;

    const fileInput = card.querySelector(".ac-file-input");
    const file = fileInput?.files?.[0];
    if (!file) {
      write("Hinweis", { error: "Kein Bild ausgewaehlt." });
      return;
    }

    const submitBtn = card.querySelector(".ac-submit-btn");
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Wird geprueft...";
    }
    try {
      const form = new FormData();
      form.append("file", file);
      if (sealNumber) form.append("observed_seal_number", sealNumber);
      const res = await fetch(`/api/sessions/${sessionId}/verifications/${verifyId}/upload`, {
        method: "POST",
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(data));
      const pill =
        data.status === "confirmed"
          ? "<span class='verify-pill confirmed'>&#10003; Best&auml;tigt</span>"
          : data.status === "suspicious"
          ? "<span class='verify-pill suspicious'>&#9888; Verdacht</span>"
          : "<span class='verify-pill pending'>&#8987; Ausstehend</span>";
      const uploadArea = card.querySelector(".ac-upload");
      if (uploadArea) {
        uploadArea.innerHTML = `<div class="ac-result">${pill}${
          data.analysis ? `<p class="ac-hint">${escapeHtml(data.analysis)}</p>` : ""
        }</div>`;
      }
      if (taskId && data.status === "confirmed") {
        setPendingItems(getPendingItems().filter((item) => item.id !== taskId));
      }
      await loadChat();
      await listTasks();
      write("Verifikation", data);
    } catch (err) {
      write("Fehler Upload", { error: String(err) });
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Hochladen & Pruefen";
      }
    }
  }

  function attachActionCardHandlers(container, options = {}) {
    if (!container) return;
    const post = typeof options.post === "function" ? options.post : async () => ({});
    const get = typeof options.get === "function" ? options.get : async () => ({});
    const write = typeof options.write === "function" ? options.write : () => {};
    const loadChat = typeof options.loadChat === "function" ? options.loadChat : async () => {};
    const listTasks = typeof options.listTasks === "function" ? options.listTasks : async () => {};
    const setPendingItems = typeof options.setPendingItems === "function" ? options.setPendingItems : () => {};
    const getPendingItems = typeof options.getPendingItems === "function" ? options.getPendingItems : () => [];
    const sessionId = Number(options.sessionId || 0);
    const chatTimeline = options.chatTimeline || null;
    if (!sessionId) return;

    container.querySelectorAll(".action-card button[data-action]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const card = btn.closest(".action-card");
        const taskId = card ? Number(card.dataset.taskId) : 0;
        if (!taskId) return;
        const action = btn.dataset.action;

        if (action === "verify") {
          btn.disabled = true;
          try {
            const criteria = card.dataset.verificationCriteria || null;
            let sealNumber = null;
            try {
              const sealData = await get(`/api/sessions/${sessionId}/seal-history`);
              const active = (sealData.entries || []).find((entry) => entry.status === "active");
              if (active) sealNumber = active.seal_number;
            } catch (_) {}
            const data = await post(`/api/sessions/${sessionId}/verifications/request`, {
              requested_seal_number: sealNumber,
              linked_task_id: taskId,
              verification_criteria: criteria,
            });
            card.dataset.verifyId = data.verification_id;
            card.dataset.verifySeal = sealNumber || "";
            const uploadArea = card.querySelector(".ac-upload");
            if (uploadArea) uploadArea.classList.remove("is-hidden");
            const sealRow = card.querySelector(".ac-seal-row");
            const sealCode = card.querySelector(".ac-seal-code");
            if (sealNumber && sealRow && sealCode) {
              sealCode.textContent = sealNumber;
              sealRow.style.display = "";
            }
            btn.style.display = "none";
            card.querySelector(".ac-submit-btn")?.addEventListener("click", () => submitVerificationCard(card, options));
            card.querySelector(".ac-file-input")?.addEventListener("change", (event) => {
              const file = event.target?.files?.[0];
              const span = event.target?.closest(".ac-file-label")?.querySelector("span");
              if (span) span.textContent = file ? file.name : "Foto waehlen";
            });
            chatTimeline?.scrollTo({ top: chatTimeline.scrollHeight, behavior: "smooth" });
            write("Verifikation angefordert", data);
          } catch (err) {
            write("Fehler Verifikation", { error: String(err) });
            btn.disabled = false;
          }
          return;
        }

        const status = action === "complete" ? "completed" : "failed";
        try {
          await post(`/api/sessions/${sessionId}/tasks/${taskId}/status`, { status });
          setPendingItems(getPendingItems().filter((item) => item.id !== taskId));
          await loadChat();
          await listTasks();
        } catch (err) {
          write("Fehler Task-Update", { error: String(err) });
        }
      });
    });
  }

  function installInlineTaskCards(options = {}) {
    const chatTimeline = options.chatTimeline || null;
    if (!chatTimeline) return;
    chatTimeline.querySelectorAll(".play-action-cards").forEach((wrapper) => wrapper.remove());
    const pendingItems = Array.isArray(options.pendingItems) ? options.pendingItems : [];
    if (!pendingItems.length) return;

    const pendingById = {};
    pendingItems.forEach((item) => {
      pendingById[item.id] = item;
    });
    const renderedIds = new Set();

    chatTimeline.querySelectorAll("[data-msg-type='task_assigned']").forEach((bubble) => {
      const rawIds = (bubble.dataset.taskIds || "").split(",").map(Number).filter(Boolean);
      const cards = rawIds
        .filter((id) => pendingById[id] && !renderedIds.has(id))
        .map((id) => {
          renderedIds.add(id);
          return buildSingleActionCard(pendingById[id]);
        });
      if (!cards.length) return;
      const wrapper = document.createElement("div");
      wrapper.className = "play-action-cards";
      wrapper.innerHTML = cards.join("");
      bubble.after(wrapper);
      attachActionCardHandlers(wrapper, options);
    });

    const unrendered = pendingItems.filter((item) => !renderedIds.has(item.id));
    if (!unrendered.length) return;
    const fallback = document.createElement("div");
    fallback.className = "play-action-cards";
    fallback.innerHTML = unrendered.map(buildSingleActionCard).join("");
    chatTimeline.appendChild(fallback);
    attachActionCardHandlers(fallback, options);
  }

  function renderTasks(options = {}) {
    const pending = Array.isArray(options.items) ? options.items.filter((item) => item.status === "pending") : [];
    const setPendingItems = typeof options.setPendingItems === "function" ? options.setPendingItems : () => {};
    const taskDropBoard = options.taskDropBoard || null;
    const tasksToggleBtn = options.tasksToggleBtn || null;
    const tasksBadge = options.tasksBadge || null;

    setPendingItems(pending);
    installInlineTaskCards({ ...options, pendingItems: pending });

    if (taskDropBoard) {
      if (pending.length) {
        taskDropBoard.innerHTML = pending.map(buildSingleActionCard).join("");
        attachActionCardHandlers(taskDropBoard, { ...options, pendingItems: pending });
      } else {
        taskDropBoard.innerHTML = "<p>Keine offenen Tasks.</p>";
      }
    }

    if (tasksToggleBtn) {
      tasksToggleBtn.classList.toggle("has-pending", pending.length > 0);
    }
    if (tasksBadge) {
      if (pending.length > 0) {
        tasksBadge.textContent = pending.length;
        tasksBadge.classList.remove("is-hidden");
      } else {
        tasksBadge.classList.add("is-hidden");
      }
    }
  }

  window.ChasteasePlayTasksUI = {
    installInlineTaskCards,
    renderTasks,
  };
})();
