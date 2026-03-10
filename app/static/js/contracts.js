const output = document.getElementById("contract-output");

function sessionId() {
  const value = Number(document.getElementById("contract-session-id").value);
  if (!value) {
    throw new Error("Session-ID fehlt");
  }
  return value;
}

function show(title, payload) {
  output.textContent = `${title}\n${typeof payload === "string" ? payload : JSON.stringify(payload, null, 2)}`;
}

document.getElementById("contract-load-btn").addEventListener("click", async () => {
  try {
    const id = sessionId();
    const res = await fetch(`/api/sessions/${id}/contract`);
    const data = await res.json();
    if (!res.ok) throw new Error(JSON.stringify(data));
    show("Contract", data);
  } catch (err) {
    show("Fehler", String(err));
  }
});

async function exportContract(format) {
  try {
    const id = sessionId();
    const res = await fetch(`/api/sessions/${id}/contract/export?format=${format}`);
    if (!res.ok) {
      const data = await res.json();
      throw new Error(JSON.stringify(data));
    }
    if (format === "json") {
      show("Export JSON", await res.json());
      return;
    }
    show("Export Text", await res.text());
  } catch (err) {
    show("Fehler Export", String(err));
  }
}

document.getElementById("contract-export-text-btn").addEventListener("click", () => exportContract("text"));
document.getElementById("contract-export-json-btn").addEventListener("click", () => exportContract("json"));
