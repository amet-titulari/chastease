(() => {
  const runtime = window.ChasteaseUiRuntime || {};

  async function jsonRequest(url, options = {}) {
    if (typeof runtime.jsonRequest === "function") {
      return runtime.jsonRequest(url, options);
    }
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data?.detail || data?.error || response.statusText || "Fehler");
    return data;
  }

  function setResult(el, text, ok) {
    if (!el) return;
    el.textContent = text;
    el.style.color = ok ? "var(--color-success, #4caf50)" : "var(--color-error, #f44)";
  }

  async function testLlmConnection() {
    const btn = document.getElementById("llm-test-btn");
    const result = document.getElementById("llm-test-result");
    if (!btn || !result) return;
    btn.disabled = true;
    result.textContent = "Teste...";
    try {
      const data = await jsonRequest("/profile/llm/test", { method: "POST" });
      setResult(result, data.ok ? `✓ Verbindung OK (HTTP ${data.status})` : `✗ Fehler: ${data.error}`, !!data.ok);
    } catch (error) {
      setResult(result, `✗ ${error}`, false);
    } finally {
      btn.disabled = false;
    }
  }

  function applyXaiPreset() {
    const sttUrl = document.getElementById("audio-transcription-api-url");
    const sttModel = document.querySelector("input[name='transcription_model']");
    const wsUrl = document.getElementById("audio-voice-ws-url");
    const voice = document.getElementById("audio-voice-default");
    if (sttUrl) sttUrl.value = "https://api.x.ai/v1/audio/transcriptions";
    if (sttModel) sttModel.value = "whisper-1";
    if (wsUrl) wsUrl.value = "wss://api.x.ai/v1/realtime";
    if (voice) voice.value = "Eve";
  }

  function applyOpenAiPreset() {
    const sttUrl = document.getElementById("audio-transcription-api-url");
    const sttModel = document.querySelector("input[name='transcription_model']");
    if (sttUrl) sttUrl.value = "https://api.openai.com/v1/audio/transcriptions";
    if (sttModel) sttModel.value = "whisper-1";
  }

  async function testAudioConnection() {
    const btn = document.getElementById("audio-test-btn");
    const result = document.getElementById("audio-test-result");
    if (!btn || !result) return;
    btn.disabled = true;
    result.textContent = "Teste Voice Gateway...";
    try {
      const data = await jsonRequest("/profile/audio/test", { method: "POST" });
      setResult(result, data.ok ? `✓ ${data.message || "Voice Gateway erreichbar."}` : `✗ ${data.error || "Unbekannter Fehler"}`, !!data.ok);
    } catch (error) {
      setResult(result, `✗ ${error}`, false);
    } finally {
      btn.disabled = false;
    }
  }

  document.getElementById("llm-test-btn")?.addEventListener("click", testLlmConnection);
  document.getElementById("audio-apply-xai")?.addEventListener("click", applyXaiPreset);
  document.getElementById("audio-apply-openai")?.addEventListener("click", applyOpenAiPreset);
  document.getElementById("audio-test-btn")?.addEventListener("click", testAudioConnection);
})();
