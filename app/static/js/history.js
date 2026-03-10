const out = document.getElementById("history-output");

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
