(() => {
  function isVoiceRunning(state) {
    return Boolean(
      state.socket && (state.socket.readyState === WebSocket.OPEN || state.socket.readyState === WebSocket.CONNECTING)
    );
  }

  function setVoiceStatus(text, voiceStatusEl) {
    if (voiceStatusEl) voiceStatusEl.textContent = text;
  }

  function syncVoiceToggleUi(state, voiceToggleBtn) {
    if (!voiceToggleBtn) return;
    const running = isVoiceRunning(state);
    voiceToggleBtn.setAttribute("aria-pressed", running ? "true" : "false");
    voiceToggleBtn.textContent = "🔊";
    voiceToggleBtn.title = running ? "Talk stoppen" : "Talk starten";
    voiceToggleBtn.setAttribute("aria-label", running ? "Talk stoppen" : "Talk starten");
    voiceToggleBtn.disabled = !state.available;
  }

  async function initVoiceAvailability(options = {}) {
    const state = options.state || {};
    state.available = false;
    setVoiceStatus("Voice: pruefe Verfuegbarkeit...", options.voiceStatusEl);
    try {
      const data = await options.get(`/api/voice/realtime/${options.sessionId}/status`);
      const enabled = Boolean(data && data.enabled);
      const hasApiKey = Boolean(data && data.has_api_key);
      const mode = (data && data.mode) || "realtime-manual";
      const hasAgentId = Boolean(data && data.has_agent_id);
      state.mode = mode;
      state.available = enabled && hasApiKey && (mode !== "voice-agent" || hasAgentId);
      if (!enabled) {
        setVoiceStatus("Voice: deaktiviert (Server)", options.voiceStatusEl);
      } else if (!hasApiKey) {
        setVoiceStatus("Voice: kein API-Key konfiguriert", options.voiceStatusEl);
      } else if (mode === "voice-agent" && !hasAgentId) {
        setVoiceStatus("Voice: Agent-ID fehlt", options.voiceStatusEl);
      } else {
        setVoiceStatus(mode === "voice-agent" ? "Voice: bereit (Agent)" : "Voice: bereit", options.voiceStatusEl);
      }
    } catch (err) {
      state.available = false;
      setVoiceStatus(`Voice: Statusfehler (${String(err)})`, options.voiceStatusEl);
    }
    syncVoiceToggleUi(state, options.voiceToggleBtn);
  }

  function pcm16ToBase64(float32Array) {
    const int16 = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i += 1) {
      const sample = Math.max(-1, Math.min(1, float32Array[i]));
      int16[i] = sample < 0 ? sample * 32768 : sample * 32767;
    }
    const bytes = new Uint8Array(int16.buffer);
    let binary = "";
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
  }

  function base64ToFloat32Pcm16(base64) {
    const binary = atob(base64);
    const length = binary.length;
    const bytes = new Uint8Array(length);
    for (let i = 0; i < length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    const int16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i += 1) {
      float32[i] = int16[i] / 32768;
    }
    return float32;
  }

  function queueVoiceAudioPcm(state, base64Pcm, sampleRate = 24000) {
    if (!state.audioCtx) return;
    const pcm = base64ToFloat32Pcm16(base64Pcm);
    const buffer = state.audioCtx.createBuffer(1, pcm.length, sampleRate);
    buffer.copyToChannel(pcm, 0);
    const source = state.audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(state.audioCtx.destination);
    const now = state.audioCtx.currentTime;
    if (state.playCursor < now) state.playCursor = now;
    source.start(state.playCursor);
    state.playCursor += buffer.duration;
  }

  async function stopVoiceMode(options = {}) {
    const state = options.state || {};
    const preserveStatus = Boolean(options.preserveStatus);
    if (state.processor) {
      try { state.processor.disconnect(); } catch (_) {}
      state.processor.onaudioprocess = null;
      state.processor = null;
    }
    if (state.micStream) {
      state.micStream.getTracks().forEach((track) => {
        try { track.stop(); } catch (_) {}
      });
      state.micStream = null;
    }
    if (state.socket) {
      try { state.socket.close(); } catch (_) {}
      state.socket = null;
    }
    if (state.audioCtx) {
      try { await state.audioCtx.close(); } catch (_) {}
      state.audioCtx = null;
    }
    state.sessionReady = false;
    if (!preserveStatus) setVoiceStatus("Voice: aus", options.voiceStatusEl);
    syncVoiceToggleUi(state, options.voiceToggleBtn);
  }

  async function startVoiceMode(options = {}) {
    const state = options.state || {};
    if (!options.sessionId) return;
    if (!state.available) {
      setVoiceStatus("Voice: nicht verfuegbar", options.voiceStatusEl);
      syncVoiceToggleUi(state, options.voiceToggleBtn);
      return;
    }
    if (state.socket && (state.socket.readyState === WebSocket.OPEN || state.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    setVoiceStatus("Voice: initialisiere...", options.voiceStatusEl);
    if (options.voiceToggleBtn) options.voiceToggleBtn.disabled = true;

    try {
      const hasGetUserMedia = Boolean(
        typeof navigator !== "undefined" &&
        navigator.mediaDevices &&
        typeof navigator.mediaDevices.getUserMedia === "function"
      );
      if (!hasGetUserMedia) {
        const secureHint = (typeof window !== "undefined" && !window.isSecureContext)
          ? " (nur in HTTPS oder localhost verfuegbar)"
          : "";
        throw new Error(`Mikrofon-API nicht verfuegbar${secureHint}`);
      }

      const bootstrapResp = await fetch(`/api/voice/realtime/${options.sessionId}/client-secret`, { method: "POST" });
      const bootstrap = await bootstrapResp.json();
      if (!bootstrapResp.ok) {
        throw new Error(bootstrap.detail || bootstrap.error || bootstrapResp.statusText);
      }

      const secret =
        bootstrap?.client_secret?.value ||
        bootstrap?.client_secret?.secret ||
        bootstrap?.client_secret?.token ||
        bootstrap?.client_secret?.client_secret?.value ||
        bootstrap?.client_secret?.client_secret?.secret ||
        bootstrap?.client_secret?.client_secret?.token;
      if (!secret) {
        throw new Error("Kein Ephemeral-Token erhalten");
      }

      const wsUrl = bootstrap.ws_url || "wss://api.x.ai/v1/realtime";
      state.socket = new WebSocket(wsUrl, [`xai-client-secret.${secret}`]);
      state.sessionReady = false;

      state.audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
      await state.audioCtx.resume();
      state.playCursor = state.audioCtx.currentTime;

      state.micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const source = state.audioCtx.createMediaStreamSource(state.micStream);
      state.processor = state.audioCtx.createScriptProcessor(4096, 1, 1);
      source.connect(state.processor);
      state.processor.connect(state.audioCtx.destination);

      state.processor.onaudioprocess = (event) => {
        if (!state.sessionReady || !state.socket || state.socket.readyState !== WebSocket.OPEN) return;
        const channel = event.inputBuffer.getChannelData(0);
        const chunk = new Float32Array(channel.length);
        chunk.set(channel);
        const base64 = pcm16ToBase64(chunk);
        state.socket.send(JSON.stringify({ type: "input_audio_buffer.append", audio: base64 }));
      };

      state.socket.onopen = () => {
        setVoiceStatus("Voice: verbunden", options.voiceStatusEl);
        if (bootstrap.session_update) {
          state.socket?.send(JSON.stringify(bootstrap.session_update));
        } else {
          state.sessionReady = true;
          setVoiceStatus("Voice: bereit (Agent)", options.voiceStatusEl);
        }
        syncVoiceToggleUi(state, options.voiceToggleBtn);
      };

      state.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "session.updated") {
            state.sessionReady = true;
            setVoiceStatus("Voice: bereit", options.voiceStatusEl);
            syncVoiceToggleUi(state, options.voiceToggleBtn);
            return;
          }
          if (data.type === "conversation.item.input_audio_transcription.completed" && data.transcript) {
            if (typeof options.appendVoiceTranscript === "function") {
              options.appendVoiceTranscript(data.transcript);
            }
            return;
          }
          if (data.type === "response.output_audio.delta" && data.delta) {
            queueVoiceAudioPcm(state, data.delta, 24000);
            return;
          }
          if (data.type === "response.output_audio_transcript.delta" && data.delta) {
            options.write("Voice Transcript", { delta: data.delta });
          }
        } catch (_) {}
      };

      state.socket.onerror = () => {
        setVoiceStatus("Voice: Fehler", options.voiceStatusEl);
      };

      state.socket.onclose = () => {
        setVoiceStatus("Voice: getrennt", options.voiceStatusEl);
        state.sessionReady = false;
        state.socket = null;
        syncVoiceToggleUi(state, options.voiceToggleBtn);
      };
    } catch (err) {
      const errMsg = String(err);
      setVoiceStatus(`Voice: Fehler (${errMsg})`, options.voiceStatusEl);
      options.write("Voice Start Fehler", { error: errMsg });
      await stopVoiceMode({ ...options, preserveStatus: true });
    } finally {
      syncVoiceToggleUi(state, options.voiceToggleBtn);
    }
  }

  async function toggleVoiceMode(options = {}) {
    const state = options.state || {};
    if (isVoiceRunning(state)) {
      await stopVoiceMode(options);
      return;
    }
    await startVoiceMode(options);
  }

  window.ChasteasePlayVoiceUI = {
    initVoiceAvailability,
    toggleVoiceMode,
  };
})();
