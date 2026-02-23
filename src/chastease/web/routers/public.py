from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["web-public"])


@router.get("/", response_class=HTMLResponse)
def landing_page() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Chastease</title>
  <style>
    :root {
      --bg: #f4f6fb;
      --ink: #0f172a;
      --muted: #5b6478;
      --card: #ffffff;
      --line: #d8deec;
      --brand: #1565c0;
      --brand-2: #0ea5a0;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(1200px 500px at 85% -20%, #cfe0ff 0%, transparent 60%),
        radial-gradient(900px 500px at -10% 120%, #c8f2e8 0%, transparent 55%),
        var(--bg);
      font-family: "Avenir Next", "Segoe UI", Arial, sans-serif;
    }
    .wrap { max-width: 1060px; margin: 0 auto; padding: 28px 20px 60px; }
    .hero {
      background: linear-gradient(145deg, #ffffff, #eef3ff);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 34px;
      box-shadow: 0 16px 40px rgba(20, 40, 80, 0.08);
    }
    h1 { margin: 0 0 10px; font-size: clamp(2rem, 4.5vw, 3rem); line-height: 1.05; }
    p { margin: 0; color: var(--muted); line-height: 1.5; }
    .actions { margin-top: 22px; display: flex; gap: 10px; flex-wrap: wrap; }
    .btn {
      display: inline-block;
      border-radius: 12px;
      padding: 11px 16px;
      text-decoration: none;
      font-weight: 700;
      border: 1px solid transparent;
    }
    .btn-primary { background: var(--brand); color: #fff; }
    .btn-secondary { background: #fff; border-color: var(--line); color: var(--ink); }
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>Chastease</h1>
      <p>Evolutionäres Prototyping für ein KI-gestütztes Session-Rollenspiel mit User-Setup, Psychogramm und persistentem Turn-Flow.</p>
      <div class="actions">
        <a class="btn btn-primary" href="/app?mode=login">Login</a>
        <a class="btn btn-secondary" href="/app?mode=register">Register</a>
        <a class="btn btn-secondary" href="/chat">AI Chat</a>
      </div>
    </section>
  </div>
</body>
</html>
"""

@router.get("/contract", response_class=HTMLResponse)
def contract_shell() -> str:
    return """
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Keuschheitsvertrag</title>
  <style>
    :root {
      --bg: #080f1e;
      --ink: #e9efff;
      --muted: #9bb0d9;
      --line: #213255;
      --panel: #101b33;
      --brand: #2d8cff;
      --ok: #35c68b;
      --danger: #d65a5a;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", Arial, sans-serif;
      color: var(--ink);
      background:
        radial-gradient(900px 360px at 85% -10%, #1c2f58 0%, transparent 60%),
        radial-gradient(800px 360px at -20% 120%, #143a44 0%, transparent 58%),
        var(--bg);
    }
    .wrap { max-width: 980px; margin: 0 auto; padding: 22px; }
    .topbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .btn {
      border-radius: 10px;
      border: 1px solid #2b3f66;
      background: #111e3b;
      color: var(--ink);
      padding: 9px 12px;
      text-decoration: none;
      font-weight: 700;
    }
    .btn.primary { background: var(--brand); border-color: transparent; }
    .card { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 16px; }
    .small { color: var(--muted); font-size: 12px; }
    .status { margin-top: 10px; min-height: 18px; }
    .ok { color: var(--ok); }
    .err { color: var(--danger); }
    .contract {
      line-height: 1.45;
      min-height: 300px;
      border: 1px solid #2a3f67;
      border-radius: 10px;
      padding: 12px;
      background: #0f1830;
      overflow-wrap: anywhere;
    }
    .contract.progress-text {
      white-space: pre-line;
    }
    .contract h1, .contract h2, .contract h3, .contract h4, .contract h5, .contract h6 {
      margin: 0 0 10px;
      line-height: 1.2;
    }
    .contract p { margin: 0 0 10px; color: var(--ink); }
    .contract ul, .contract ol { margin: 0 0 12px 20px; padding: 0; }
    .contract li { margin: 2px 0; }
    .contract pre {
      margin: 0 0 12px;
      padding: 10px;
      border-radius: 8px;
      border: 1px solid #2a3f67;
      background: #0a1328;
      overflow: auto;
    }
    .contract code {
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      background: #0a1328;
      border: 1px solid #2a3f67;
      border-radius: 5px;
      padding: 1px 4px;
    }
    .contract pre code {
      background: transparent;
      border: 0;
      border-radius: 0;
      padding: 0;
    }
    .contract a { color: #7fb5ff; }
    .consent-box {
      margin-top: 14px;
      border: 1px solid #2a3f67;
      border-radius: 10px;
      padding: 12px;
      background: #0f1830;
    }
    .hidden { display: none !important; }
    .consent-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 8px;
    }
    .consent-row input {
      flex: 1 1 320px;
      min-width: 220px;
      border-radius: 8px;
      border: 1px solid #2b3f66;
      background: #111e3b;
      color: var(--ink);
      padding: 8px 10px;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div>
        <h1 style="margin:0 0 6px;">Keuschheitsvertrag</h1>
        <div class="small">Der Keuschheitsvertrag wird aus den Session-Daten erstellt.</div>
      </div>
      <div class="actions">
        <a class="btn" href="/">Landing</a>
        <a class="btn" href="/app">Dashboard</a>
        <a class="btn primary" href="/contract">Vertrag</a>
        <a class="btn" href="/chat">AI Chat</a>
      </div>
    </div>

    <section class="card">
      <div id="contractBox" class="contract">Der Keuschheitsvertrag wird generiert. Geduld ....</div>
      <div id="status" class="status small"></div>
      <div id="consentBox" class="consent-box hidden">
        <div class="small"><strong>Digital Consent</strong></div>
        <div id="consentRequired" class="small" style="margin-top:6px;">Kontrolltext: "Ich akzeptiere diesen Vertrag"</div>
        <div id="consentRow" class="consent-row">
          <input id="consentInput" placeholder="Ich akzeptiere diesen Vertrag" />
          <button id="consentBtn" class="btn primary" onclick="acceptContractConsent()">Vertrag akzeptieren</button>
        </div>
        <div id="consentInfo" class="status small"></div>
      </div>
    </section>
  </div>

  <script>
    function setStatus(text, kind = "ok") {
      const node = document.getElementById("status");
      node.textContent = text;
      node.className = `status small ${kind === "err" ? "err" : "ok"}`;
    }

    function authStorageKey() {
      return "chastease_auth_v1";
    }

    let contractUserId = null;
    let contractUserDisplayName = null;
    let contractAuthToken = null;
    let contractSetupSessionId = null;
    let contractConsentRequiredText = "Ich akzeptiere diesen Vertrag";
    let contractIsReadyForConsent = false;

    function escapeHtml(value) {
      return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function safeHref(value) {
      const url = String(value || "").trim();
      if (/^https?:\\/\\//i.test(url) || /^mailto:/i.test(url)) return url;
      return "#";
    }

    function renderInlineMarkdown(text) {
      let out = escapeHtml(text);
      out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
      out = out.replace(/\\*\\*([^*]+)\\*\\*/g, "<strong>$1</strong>");
      out = out.replace(/\\*([^*]+)\\*/g, "<em>$1</em>");
      out = out.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, (_m, label, href) => {
        const target = escapeHtml(safeHref(href));
        return `<a href="${target}" target="_blank" rel="noopener noreferrer">${label}</a>`;
      });
      return out;
    }

    function renderMarkdownSafe(markdown) {
      const raw = String(markdown || "").replace(/\\r\\n/g, "\\n");
      const codeBlocks = [];
      const withTokens = raw.replace(/```([\\s\\S]*?)```/g, (_m, code) => {
        const idx = codeBlocks.length;
        codeBlocks.push(`<pre><code>${escapeHtml(String(code).trim())}</code></pre>`);
        return `@@CODEBLOCK_${idx}@@`;
      });

      const lines = withTokens.split("\\n");
      const html = [];
      let paragraph = [];
      let inUl = false;
      let inOl = false;

      function flushParagraph() {
        if (!paragraph.length) return;
        html.push(`<p>${paragraph.join("<br/>")}</p>`);
        paragraph = [];
      }

      function closeLists() {
        if (inUl) {
          html.push("</ul>");
          inUl = false;
        }
        if (inOl) {
          html.push("</ol>");
          inOl = false;
        }
      }

      for (const line of lines) {
        const trimmed = line.trim();
        const codeTokenMatch = trimmed.match(/^@@CODEBLOCK_(\\d+)@@$/);
        if (codeTokenMatch) {
          flushParagraph();
          closeLists();
          html.push(trimmed);
          continue;
        }
        if (!trimmed) {
          flushParagraph();
          closeLists();
          continue;
        }
        const heading = trimmed.match(/^(#{1,6})\\s+(.+)$/);
        if (heading) {
          flushParagraph();
          closeLists();
          const level = heading[1].length;
          html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
          continue;
        }
        const ul = trimmed.match(/^[-*]\\s+(.+)$/);
        if (ul) {
          flushParagraph();
          if (inOl) {
            html.push("</ol>");
            inOl = false;
          }
          if (!inUl) {
            html.push("<ul>");
            inUl = true;
          }
          html.push(`<li>${renderInlineMarkdown(ul[1])}</li>`);
          continue;
        }
        const ol = trimmed.match(/^\\d+\\.\\s+(.+)$/);
        if (ol) {
          flushParagraph();
          if (inUl) {
            html.push("</ul>");
            inUl = false;
          }
          if (!inOl) {
            html.push("<ol>");
            inOl = true;
          }
          html.push(`<li>${renderInlineMarkdown(ol[1])}</li>`);
          continue;
        }
        paragraph.push(renderInlineMarkdown(trimmed));
      }

      flushParagraph();
      closeLists();

      const rendered = html.join("\\n").replace(/@@CODEBLOCK_(\\d+)@@/g, (_m, idx) => {
        return codeBlocks[Number(idx)] || "";
      });
      return rendered || `<p>${escapeHtml(raw)}</p>`;
    }

    function looksLikeGeneratedContract(text) {
      const raw = String(text || "").trim();
      if (raw.length < 350) return false;
      return (/(Artikel\\s+1|Article\\s+1)/i.test(raw) && /(Signatur|Signature)/i.test(raw));
    }

    function renderConsent(consent) {
      const box = document.getElementById("consentBox");
      const requiredNode = document.getElementById("consentRequired");
      const row = document.getElementById("consentRow");
      const input = document.getElementById("consentInput");
      const button = document.getElementById("consentBtn");
      const info = document.getElementById("consentInfo");
      if (!contractIsReadyForConsent) {
        box.classList.add("hidden");
        requiredNode.classList.remove("hidden");
        row.classList.remove("hidden");
        input.disabled = false;
        button.disabled = false;
        info.textContent = "";
        info.className = "status small";
        return;
      }
      box.classList.remove("hidden");
      const required = String(consent?.required_text || "Ich akzeptiere diesen Vertrag");
      contractConsentRequiredText = required;
      const accepted = Boolean(consent?.accepted);
      const acceptedAt = String(consent?.accepted_at || "");
      const consentText = String(consent?.consent_text || "");

      requiredNode.textContent = `Kontrolltext: "${required}"`;
      input.placeholder = required;

      if (accepted) {
        requiredNode.classList.add("hidden");
        row.classList.add("hidden");
        input.value = consentText || required;
        input.disabled = true;
        button.disabled = true;
        const signer = contractUserDisplayName || contractUserId || "user";
        info.textContent = `Ich, ${signer}, habe den Vertrag am ${acceptedAt || "-"} akzeptiert und halte mich daran.`;
        info.className = "status small ok";
      } else {
        requiredNode.classList.remove("hidden");
        row.classList.remove("hidden");
        if (!input.value) input.value = "";
        input.disabled = false;
        button.disabled = false;
        info.textContent = "Noch nicht akzeptiert.";
        info.className = "status small";
      }
    }

    async function safeJson(res) {
      try { return await res.json(); }
      catch {
        const text = await res.text();
        return { error: "non-json", body: text, status: res.status };
      }
    }

    async function run() {
      let auth = null;
      let bootstrap = null;
      try {
        auth = JSON.parse(localStorage.getItem(authStorageKey()) || "{}");
      } catch {}
      try {
        bootstrap = JSON.parse(sessionStorage.getItem("chastease_post_setup_bootstrap") || "{}");
      } catch {}

      let userId = String(auth?.user_id || "").trim();
      const authToken = auth?.auth_token;
      contractUserDisplayName = String(auth?.display_name || auth?.username || "").trim() || null;

      if (authToken) {
        const meRes = await fetch(`/api/v1/auth/me?auth_token=${encodeURIComponent(authToken)}`);
        const meData = await safeJson(meRes);
        if (meRes.ok) {
          const meUserId = String(meData?.user_id || "").trim();
          const meDisplayName = String(meData?.display_name || "").trim();
          if (meUserId) userId = meUserId;
          if (meDisplayName) contractUserDisplayName = meDisplayName;
          try {
            localStorage.setItem(
              authStorageKey(),
              JSON.stringify({
                ...(auth || {}),
                user_id: userId,
                auth_token: authToken,
                display_name: contractUserDisplayName || null,
              })
            );
          } catch {}
        }
      }

      let setupSessionId = bootstrap?.setup_session_id || new URLSearchParams(window.location.search).get("setup_session_id");
      if (!setupSessionId && userId && authToken) {
        const activeRes = await fetch(
          `/api/v1/sessions/active?user_id=${encodeURIComponent(userId)}&auth_token=${encodeURIComponent(authToken)}`
        );
        const activeData = await safeJson(activeRes);
        if (activeRes.ok && activeData?.has_active_session && activeData?.setup_session_id) {
          setupSessionId = String(activeData.setup_session_id);
        }
      }
      contractUserId = userId;
      contractAuthToken = authToken;
      contractSetupSessionId = setupSessionId;
      if (!userId || !authToken || !setupSessionId) {
        setStatus("Setup-Kontext fehlt. Bitte Setup erneut abschließen.", "err");
        return;
      }

      function saveBootstrap(nextBootstrap) {
        try {
          sessionStorage.setItem("chastease_post_setup_bootstrap", JSON.stringify(nextBootstrap || {}));
        } catch {}
      }

      function showProgress(lines) {
        const box = document.getElementById("contractBox");
        box.classList.add("progress-text");
        box.textContent = lines.join("\\n");
      }

      async function generateContract() {
        const res = await fetch(`/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}/contract`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: userId, auth_token: authToken }),
        });
        const data = await safeJson(res);
        if (!res.ok) {
          setStatus(data?.detail || "Keuschheitsvertrag konnte nicht generiert werden.", "err");
          return false;
        }
        const contractText = String(data?.contract_text || "");
        contractIsReadyForConsent = looksLikeGeneratedContract(contractText);
        const box = document.getElementById("contractBox");
        box.classList.remove("progress-text");
        box.innerHTML = renderMarkdownSafe(contractText || "Keuschheitsvertrag erstellt.");
        renderConsent(data?.consent || null);
        setStatus(contractIsReadyForConsent ? "Keuschheitsvertrag erstellt." : "Vertrag noch nicht im finalen Format.");
        return true;
      }

      if (Boolean(bootstrap?.pending_artifacts)) {
        showProgress(["Psychogramm wird analysiert. Geduld...."]);
        setStatus("Psychogramm wird analysiert...");
        const analysisRes = await fetch(`/api/v1/setup/sessions/${encodeURIComponent(setupSessionId)}/analysis`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: userId, auth_token: authToken }),
        });
        const analysisData = await safeJson(analysisRes);
        if (!analysisRes.ok) {
          setStatus(analysisData?.detail || "Psychogramm-Analyse fehlgeschlagen.", "err");
          return;
        }

        showProgress([
          "Psychogramm wird analysiert. Geduld....",
          "Psychogramm erfolgreich erstellt.",
          "Der Keuschheitsvertrag wird generiert. Geduld ....",
        ]);
        setStatus("Keuschheitsvertrag wird generiert...");
        const ok = await generateContract();
        if (!ok) return;

        saveBootstrap({ ...(bootstrap || {}), setup_session_id: setupSessionId, pending_artifacts: false });
        return;
      }

      await generateContract();
    }

    async function acceptContractConsent() {
      const consentText = String(document.getElementById("consentInput").value || "").trim();
      if (!consentText) {
        return setStatus("Bitte den Kontrolltext eingeben.", "err");
      }
      if (!contractUserId || !contractAuthToken || !contractSetupSessionId) {
        return setStatus("Setup-Kontext fehlt. Bitte Seite neu laden.", "err");
      }
      setStatus("Consent wird gespeichert...");
      const res = await fetch(`/api/v1/setup/sessions/${encodeURIComponent(contractSetupSessionId)}/contract/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: contractUserId,
          auth_token: contractAuthToken,
          consent_text: consentText,
        }),
      });
      const data = await safeJson(res);
      if (!res.ok) {
        setStatus(data?.detail || "Consent konnte nicht gespeichert werden.", "err");
        return;
      }
      if (data?.contract_text) {
        const contractText = String(data.contract_text || "");
        contractIsReadyForConsent = looksLikeGeneratedContract(contractText);
        const box = document.getElementById("contractBox");
        box.classList.remove("progress-text");
        box.innerHTML = renderMarkdownSafe(contractText);
      }
      renderConsent(data?.consent || { required_text: contractConsentRequiredText, accepted: true, consent_text: consentText });
      setStatus("Digital Consent gespeichert.");
    }

    run();
  </script>
</body>
</html>
"""
