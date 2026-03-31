(() => {
  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function renderMessageHtml(value) {
    const escaped = escapeHtml(value);
    return escaped
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*\n]+)\*/g, "<em>$1</em>")
      .replace(/\n/g, "<br>");
  }

  function formatPromptMeta(item) {
    if (!item || item.role !== "assistant" || !item.prompt_version) return "";
    return `Prompt ${item.prompt_version}`;
  }

  function formatSpeakerName(item, options = {}) {
    if (item && item.speaker_name) return String(item.speaker_name);
    const role = String(item?.role || "system").toLowerCase();
    if (role === "assistant") return String(options.personaName || "Keyholderin");
    if (role === "user") return String(options.playerName || "Du");
    return "System";
  }

  function renderOperationalState(items, options = {}) {
    const warnings = Array.isArray(items)
      ? items.filter((item) => String(item?.message_type || "") === "system_warning" && String(item?.content || "").trim())
      : [];
    const latestWarning = warnings.length ? warnings[warnings.length - 1] : null;
    const warningText = latestWarning ? String(latestWarning.content || "").trim() : "";
    const opsBannerEl = options.opsBannerEl || null;
    const statusPillEl = options.statusPillEl || null;
    if (opsBannerEl) {
      if (warningText) {
        opsBannerEl.textContent = warningText;
        opsBannerEl.classList.remove("is-hidden");
      } else {
        opsBannerEl.textContent = "";
        opsBannerEl.classList.add("is-hidden");
      }
    }
    if (statusPillEl) {
      statusPillEl.classList.toggle("is-degraded", Boolean(warningText));
    }
  }

  function renderChat(items, options = {}) {
    const chatTimeline = options.chatTimeline || null;
    if (!chatTimeline) return;
    const list = Array.isArray(items) ? items : [];
    renderOperationalState(list, options);
    if (!list.length) {
      chatTimeline.innerHTML = "<p>Noch keine Nachrichten.</p>";
      if (typeof options.installInlineTaskCards === "function") {
        options.installInlineTaskCards();
      }
      return;
    }

    const personaAvatarUrl = String(options.personaAvatarUrl || "").trim();
    chatTimeline.innerHTML = list
      .slice(-80)
      .map((item) => {
        const role = item.role || "system";
        const cssRole = role === "user" ? "from-user" : "from-ai";
        const content = renderMessageHtml(item.content || "");
        const ts = typeof options.formatMessageTime === "function" ? options.formatMessageTime(item.created_at) : "";
        const promptMeta = formatPromptMeta(item);
        const speakerName = formatSpeakerName(item, options);
        let taskAttr = "";
        if (item.message_type === "task_assigned") {
          const ids = (item.content || "").match(/\d+/g) || [];
          taskAttr = ` data-msg-type="task_assigned" data-task-ids="${ids.join(",")}"`;
        }
        const avatarHtml = (cssRole === "from-ai" && personaAvatarUrl)
          ? `<img class="bubble-avatar" src="${personaAvatarUrl}" alt="" aria-hidden="true" />`
          : "";
        const bodyRow = avatarHtml
          ? `<div class="bubble-row">${avatarHtml}<div class="bubble-body">${content}</div></div>`
          : `<div class="bubble-body">${content}</div>`;
        return `
          <div class="chat-bubble ${cssRole}"${taskAttr}>
            ${bodyRow}
            <div class="bubble-meta">${speakerName}${ts ? " · " + ts : ""}${promptMeta ? " · " + promptMeta : ""}</div>
          </div>`;
      })
      .join("");

    if (typeof options.installInlineTaskCards === "function") {
      options.installInlineTaskCards();
    }
    chatTimeline.scrollTop = chatTimeline.scrollHeight;
  }

  function appendVoiceTranscript(chatTimeline, transcript, playerName = "Du") {
    if (!chatTimeline) return;
    chatTimeline.innerHTML += `\n<div class="chat-bubble from-user"><div class="bubble-body">${escapeHtml(transcript)}</div><div class="bubble-meta">${escapeHtml(playerName)} · Voice</div></div>`;
    chatTimeline.scrollTop = chatTimeline.scrollHeight;
  }

  window.ChasteasePlayChatUI = {
    appendVoiceTranscript,
    escapeHtml,
    renderChat,
  };
})();
