const out = document.getElementById("history-output");
const messageList = document.getElementById("history-message-list");

function params() {
  const sessionId = Number(document.getElementById("history-session-id").value);
  const source = document.getElementById("history-source").value.trim();
  const eventType = document.getElementById("history-event-type").value.trim();
  const limit = Number(document.getElementById("history-limit").value || 200);

  if (!sessionId) {
    throw new Error("Session-ID fehlt");
  }

  const query = new URLSearchParams({ limit: String(limit) });
  if (source) query.set("source", source);
  if (eventType) query.set("event_type", eventType);

  return { sessionId, query };
}

function write(title, data) {
  if (typeof data === "string") {
    try {
      const parsed = JSON.parse(data);
      if (parsed && parsed.error && parsed.error.message) {
        data = `${parsed.error.message} (${parsed.error.code || "error"})`;
      }
    } catch {
      // Keep plain string.
    }
  }
  out.textContent = `${title}\n${typeof data === "string" ? data : JSON.stringify(data, null, 2)}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderMessageList(items) {
  if (!messageList) return;
  if (!Array.isArray(items) || !items.length) {
    messageList.innerHTML = '<p class="history-muted">Keine Nachrichten gefunden.</p>';
    return;
  }

  messageList.innerHTML = items.map((item) => {
    const promptTemplates = Array.isArray(item.prompt_templates) ? item.prompt_templates : [];
    const templateChips = promptTemplates
      .map((template) => `<span class="history-chip history-chip--prompt">${escapeHtml(template)}</span>`)
      .join("");
    return `
      <article class="history-message-card">
        <div class="history-message-head">
          <div class="history-message-title">#${escapeHtml(item.id)} ${escapeHtml(item.role || "unknown")}</div>
          <div class="history-message-time">${escapeHtml(item.created_at || "")}</div>
        </div>
        <div class="history-meta-row">
          ${item.message_type ? `<span class="history-chip">${escapeHtml(item.message_type)}</span>` : ""}
          ${item.prompt_version ? `<span class="history-chip history-chip--prompt">Prompt ${escapeHtml(item.prompt_version)}</span>` : ""}
        </div>
        ${templateChips ? `<div class="history-meta-row">${templateChips}</div>` : ""}
        <div class="history-message-content">${escapeHtml(item.content || "")}</div>
      </article>`;
  }).join("");
}

function formatMessageMeta(item) {
  const bits = [];
  if (item.message_type) bits.push(`type=${item.message_type}`);
  if (item.prompt_version) bits.push(`prompt=${item.prompt_version}`);
  if (Array.isArray(item.prompt_templates) && item.prompt_templates.length) {
    bits.push(`templates=${item.prompt_templates.join(", ")}`);
  }
  return bits.join(" | ");
}

function formatMessages(items) {
  if (!Array.isArray(items) || !items.length) return "Keine Nachrichten gefunden.";
  return items.map((item) => {
    const meta = formatMessageMeta(item);
    return [
      `#${item.id} ${item.role}${item.created_at ? ` @ ${item.created_at}` : ""}`,
      meta,
      String(item.content || ""),
    ].filter(Boolean).join("\n");
  }).join("\n\n---\n\n");
}

document.getElementById("history-load-btn").addEventListener("click", async () => {
  try {
    const { sessionId, query } = params();
    const res = await fetch(`/api/sessions/${sessionId}/events?${query.toString()}`);
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    write("Events", data);
  } catch (err) {
    write("Fehler", String(err));
  }
});

document.getElementById("history-load-messages-btn").addEventListener("click", async () => {
  try {
    const { sessionId } = params();
    const res = await fetch(`/api/sessions/${sessionId}/messages`);
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    renderMessageList(data.items || []);
    write("Nachrichten", formatMessages(data.items || []));
  } catch (err) {
    renderMessageList([]);
    write("Fehler Nachrichten", String(err));
  }
});

async function exportHistory(format) {
  try {
    const { sessionId, query } = params();
    query.set("format", format);
    const res = await fetch(`/api/sessions/${sessionId}/events/export?${query.toString()}`);
    if (!res.ok) {
      const maybeJson = await res.json();
      throw new Error(JSON.stringify(maybeJson));
    }
    if (format === "json") {
      const data = await res.json();
      write("Export JSON", data);
      return;
    }
    const text = await res.text();
    write("Export Text", text);
  } catch (err) {
    write("Fehler Export", String(err));
  }
}

document.getElementById("history-export-text-btn").addEventListener("click", () => exportHistory("text"));
document.getElementById("history-export-json-btn").addEventListener("click", () => exportHistory("json"));
