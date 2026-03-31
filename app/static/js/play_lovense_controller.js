(() => {
  function createController(ctx) {
    const getSdk = () => ctx.getSdk?.() || null;
    const setSdk = (value) => ctx.setSdk?.(value);
    const getBootstrap = () => ctx.getBootstrap?.() || null;
    const setBootstrap = (value) => ctx.setBootstrap?.(value);
    const getToys = () => ctx.getToys?.() || [];
    const setToys = (value) => ctx.setToys?.(value);
    const getPresetLibrary = () => ctx.getPresetLibrary?.() || { builtin: [], wearer: [], persona: [], combined: [] };
    const setPresetLibrary = (value) => ctx.setPresetLibrary?.(value);
    const getPlanQueue = () => ctx.getPlanQueue?.() || [];
    const setPlanQueue = (value) => ctx.setPlanQueue?.(value);
    const getPlanRunId = () => Number(ctx.getPlanRunId?.() || 0);
    const setPlanRunId = (value) => ctx.setPlanRunId?.(value);
    const getPlanRunning = () => Boolean(ctx.getPlanRunning?.());
    const setPlanRunning = (value) => ctx.setPlanRunning?.(value);
    const getPlanTitle = () => String(ctx.getPlanTitle?.() || "");
    const setPlanTitle = (value) => ctx.setPlanTitle?.(value);
    const getPlanTotal = () => Number(ctx.getPlanTotal?.() || 0);
    const setPlanTotal = (value) => ctx.setPlanTotal?.(value);
    const getPlanCurrentIndex = () => Number(ctx.getPlanCurrentIndex?.() || 0);
    const getPlanCurrentCommand = () => String(ctx.getPlanCurrentCommand?.() || "");
    const getUiState = () => ctx.getUiState?.() || {};

    function combinedPresetMap() {
      const map = { ...(ctx.builtinPresets || {}) };
      const items = Array.isArray(getPresetLibrary()?.combined) ? getPresetLibrary().combined : [];
      items.forEach((item) => {
        if (!item || !item.key) return;
        if (item.command === "pattern") {
          if (String(item.pattern || "").startsWith("builtin:")) {
            const builtinKey = String(item.pattern || "").split(":").slice(1).join(":");
            const builtin = (ctx.builtinPresets || {})[builtinKey];
            if (builtin) map[item.key] = builtin;
            return;
          }
          map[item.key] = {
            interval: Number(item.interval || 180) || 180,
            pattern: () => String(item.pattern || ""),
          };
          return;
        }
        if (item.command === "preset" && item.preset && (ctx.builtinPresets || {})[item.preset]) {
          map[item.key] = ctx.builtinPresets[item.preset];
        }
      });
      return map;
    }

    function resolveQr(payload) {
      if (!payload || typeof payload !== "object") return "";
      return String(payload.qrcodeUrl || payload.qrCodeUrl || payload.url || payload.qrcode || "").trim();
    }

    function clearSequence() {
      const handle = ctx.getSequenceTimeout?.();
      if (handle) {
        window.clearTimeout(handle);
        ctx.setSequenceTimeout?.(null);
      }
    }

    function selectToyId() {
      const remembered = typeof ctx.restoreSelectedToyId === "function" ? ctx.restoreSelectedToyId() : "";
      const toys = getToys();
      if (remembered) {
        const matched = toys.find((toy) => String(toy.id || toy.toyId || toy.toy_id || "") === remembered);
        if (matched) return remembered;
      }
      const preferred = toys.find((toy) => {
        const label = String(toy.name || toy.nickName || toy.nickname || toy.type || "").toLowerCase();
        return label.includes("edge");
      });
      const active = preferred || toys[0];
      const toyId = String(active?.id || active?.toyId || active?.toy_id || "").trim();
      ctx.rememberSelectedToyId?.(toyId);
      return toyId;
    }

    async function loadBootstrap() {
      const data = await ctx.post(`/api/lovense/sessions/${ctx.sessionId}/bootstrap`, {});
      setBootstrap(data);
      return data;
    }

    async function loadPresetLibrary() {
      const data = await ctx.get(`/api/lovense/sessions/${ctx.sessionId}/preset-library`);
      setPresetLibrary(data.library || { builtin: [], wearer: [], persona: [], combined: [] });
    }

    async function refreshQr() {
      if (ctx.simulator) return;
      const sdk = getSdk();
      if (!sdk || typeof sdk.getQrcode !== "function") return;
      try {
        const qr = await sdk.getQrcode();
        if (resolveQr(qr)) {
          ctx.setStatus("Lovense: QR bereit. Scanne den Code in der Connect App.");
        }
      } catch (err) {
        ctx.setStatus(`Lovense: QR Fehler (${String(err)})`);
      }
    }

    async function syncToys() {
      const uiState = getUiState();
      if (ctx.simulator) {
        setToys([{ id: "sim-edge-2", name: "Simulator Edge 2", battery: 100, status: "simulated" }]);
        uiState.toyLabel = "Simulator Edge 2 · Akku 100%";
        ctx.setStatus("Lovense: Simulator aktiv. Virtuelles Toy bereit.");
        return;
      }
      const sdk = getSdk();
      if (!sdk) return;
      try {
        let toys = [];
        if (typeof sdk.getToys === "function") {
          toys = await sdk.getToys();
        } else if (typeof sdk.getOnlineToys === "function") {
          toys = await sdk.getOnlineToys();
        }
        const nextToys = Array.isArray(toys) ? toys.filter(Boolean) : Object.values(toys || {});
        setToys(nextToys);
        if (!nextToys.length) {
          uiState.toyLabel = "Kein Toy verbunden";
          ctx.setStatus("Lovense: SDK bereit. Verbinde jetzt den Edge 2 ueber die Connect App.");
          return;
        }
        const activeToyId = selectToyId();
        const activeToy = nextToys.find((toy) => String(toy.id || toy.toyId || toy.toy_id || "") === activeToyId) || nextToys[0];
        const label = String(activeToy?.name || activeToy?.nickName || activeToy?.nickname || activeToy?.type || "Toy");
        const battery = activeToy?.battery != null ? ` · Akku ${activeToy.battery}%` : "";
        uiState.toyLabel = `${label}${battery}`;
        ctx.setStatus(`Lovense: ${label} verbunden${battery}. KI-Steuerung bereit.`);
      } catch (err) {
        uiState.toyLabel = "Toy-Status unbekannt";
        ctx.setStatus(`Lovense: Toy-Status Fehler (${String(err)})`);
      }
    }

    async function init() {
      if (!ctx.sessionId) return false;
      if (getSdk()) return true;
      if (!ctx.enabled) {
        ctx.setStatus("Lovense: serverseitig deaktiviert.");
        return false;
      }
      if (!ctx.configured) {
        if (ctx.simulator) {
          ctx.rememberAutoInit?.();
          await syncToys();
          return true;
        }
        ctx.setStatus("Lovense: Konfiguration unvollstaendig.");
        return false;
      }
      if (typeof window.LovenseBasicSdk !== "function") {
        ctx.setStatus("Lovense: SDK im Browser nicht geladen.");
        return false;
      }

      const bootstrap = getBootstrap() || await loadBootstrap();
      ctx.rememberAutoInit?.();
      ctx.setStatus(`Lovense: Initialisierung fuer ${bootstrap.uname || bootstrap.uid}...`);
      const sdk = new window.LovenseBasicSdk({
        platform: bootstrap.platform || ctx.platform,
        authToken: bootstrap.auth_token,
        uid: bootstrap.uid,
        appType: bootstrap.app_type || ctx.appType,
        debug: ctx.debug,
      });
      setSdk(sdk);

      if (typeof sdk.on === "function") {
        sdk.on("ready", async () => {
          ctx.setStatus("Lovense: SDK bereit. Verbinde jetzt den Edge 2 ueber die App.");
          await refreshQr();
          await syncToys();
        });
        sdk.on("sdkError", (data) => {
          const message = data && data.message ? data.message : "Lovense SDK Fehler";
          ctx.setStatus(`Lovense: ${message}`);
        });
      } else {
        await refreshQr();
        await syncToys();
      }

      if (ctx.getPollHandle?.()) window.clearInterval(ctx.getPollHandle());
      ctx.setPollHandle?.(window.setInterval(() => {
        syncToys().catch(() => {});
      }, 6000));
      return true;
    }

    function patternStrength(intensity, mode) {
      const level = Math.max(1, Math.min(20, Number(intensity) || 8));
      if (mode === "pulse") {
        return `0;${level};0;${Math.max(1, Math.round(level * 0.85))};0;${level}`;
      }
      return `0;${Math.max(1, Math.round(level * 0.45))};${Math.max(1, Math.round(level * 0.7))};${level};${Math.max(1, Math.round(level * 0.7))};${Math.max(1, Math.round(level * 0.45))}`;
    }

    async function executeSegment(kind, payload) {
      if (ctx.simulator) {
        await new Promise((resolve) => window.setTimeout(resolve, 120));
        return;
      }
      const sdk = getSdk();
      if (!sdk) throw new Error("Lovense ist noch nicht initialisiert.");
      if (kind === "vibrate") {
        if (typeof sdk.sendToyCommand !== "function") {
          throw new Error("sendToyCommand wird vom geladenen SDK nicht angeboten.");
        }
        await sdk.sendToyCommand(payload);
        return;
      }
      if (kind === "pattern") {
        if (typeof sdk.sendPatternCommand !== "function") {
          throw new Error("sendPatternCommand wird vom geladenen SDK nicht angeboten.");
        }
        await sdk.sendPatternCommand(payload);
        return;
      }
      throw new Error(`Lovense-Segmenttyp wird nicht unterstuetzt: ${kind}`);
    }

    async function stopAction() {
      if (!(await init())) return false;
      const toyId = selectToyId();
      if (!toyId) {
        ctx.setStatus("Lovense: Kein verbundenes Toy fuer Stop gefunden.");
        return false;
      }
      clearSequence();
      const sdk = getSdk();
      if (typeof sdk?.stopToyAction === "function") {
        await sdk.stopToyAction({ toyId });
      } else if (typeof sdk?.sendToyCommand === "function") {
        await sdk.sendToyCommand({ toyId, vibrate: 0, time: 0 });
      }
      getUiState().currentLabel = "Stop";
      ctx.setStatus("Lovense: Toy gestoppt.");
      try {
        await ctx.post(`/api/lovense/sessions/${ctx.sessionId}/events`, { source: "play", phase: "executed", command: "stop", title: "Stop", toy_id: toyId });
      } catch (_) {}
      return true;
    }

    function cancelPlan(clearQueue = true) {
      setPlanRunId(getPlanRunId() + 1);
      setPlanRunning(false);
      setPlanTitle("");
      if (clearQueue) setPlanQueue([]);
      ctx.resetPlanStatus();
    }

    function normalizePlanStep(step) {
      if (!step || typeof step !== "object") return null;
      const command = String(step.command || "").trim().toLowerCase();
      if (!["vibrate", "pulse", "wave", "stop", "preset", "pause"].includes(command)) return null;
      const normalized = { command };
      if (step.intensity != null && step.intensity !== "") {
        normalized.intensity = Math.max(1, Math.min(20, Number(step.intensity) || 1));
      }
      if (step.duration_seconds != null && step.duration_seconds !== "") {
        normalized.duration_seconds = Math.max(1, Math.min(180, Number(step.duration_seconds) || 1));
      }
      if (step.preset != null && step.preset !== "") {
        normalized.preset = String(step.preset).trim();
      }
      return normalized;
    }

    function waitCancelable(ms, runId) {
      return new Promise((resolve) => {
        window.setTimeout(() => resolve(runId === getPlanRunId()), Math.max(0, ms));
      });
    }

    async function runProgram(program, settings = {}) {
      if (!(await init())) return false;
      const toyId = selectToyId();
      if (!toyId) {
        ctx.setStatus("Lovense: Kein verbundenes Toy gefunden.");
        return false;
      }
      clearSequence();
      const intensity = Math.max(1, Math.min(20, Number(settings.intensity) || 8));
      const duration = Math.max(1, Math.min(120, Number(settings.duration_seconds) || 15));
      const pause = Math.max(0, Math.min(60, Number(settings.pause_seconds) || 0));
      const loops = Math.max(1, Math.min(10, Number(settings.loops) || 1));
      getUiState().currentLabel = `${program.label}${loops > 1 ? ` · ${loops}x` : ""}`;
      ctx.renderConsole();
      const runOnce = async (step) => {
        const payload = program.buildPayload({ toyId, intensity, duration });
        await executeSegment(program.kind, payload);
        try {
          await ctx.post(`/api/lovense/sessions/${ctx.sessionId}/events`, {
            source: "play",
            phase: "executed",
            command: program.kind,
            title: program.label,
            intensity,
            duration_seconds: duration,
            pause_seconds: pause,
            loops,
            toy_id: toyId,
          });
        } catch (_) {}
        const loopText = loops > 1 ? ` Loop ${step}/${loops}` : "";
        ctx.setStatus(`Lovense: ${program.label}${loopText} aktiv.`);
        if (step >= loops) return;
        ctx.setSequenceTimeout?.(window.setTimeout(() => {
          runOnce(step + 1).catch((err) => {
            ctx.setStatus(`Lovense: ${program.label} fehlgeschlagen (${String(err)})`);
          });
        }, Math.max(0, (duration + pause) * 1000)));
      };
      await runOnce(1);
      return true;
    }

    async function runAction(action) {
      const command = String(action?.command || "").trim().toLowerCase();
      if (!command) return;
      if (command === "stop") {
        getUiState().currentLabel = "Stop";
        await stopAction();
        return;
      }
      if (command === "vibrate") {
        await runProgram({
          label: `Vibrate ${Math.max(1, Math.min(20, Number(action.intensity) || 8))}/20`,
          kind: "vibrate",
          buildPayload: ({ toyId, intensity, duration }) => ({ toyId, vibrate: intensity, time: duration }),
        }, action);
        return;
      }
      if (command === "pulse" || command === "wave") {
        await runProgram({
          label: command === "pulse" ? "Pulse" : "Wave",
          kind: "pattern",
          buildPayload: ({ toyId, intensity, duration }) => ({
            toyId,
            strength: patternStrength(intensity, command),
            time: duration,
            interval: 180,
            vibrate: true,
          }),
        }, action);
        return;
      }
      if (command === "preset") {
        const presetId = String(action.preset || "").trim();
        const preset = combinedPresetMap()[presetId];
        if (!preset) throw new Error(`Unbekanntes Preset: ${presetId}`);
        await runProgram({
          label: `Preset ${presetId}`,
          kind: "pattern",
          buildPayload: ({ toyId, intensity, duration }) => ({
            toyId,
            strength: preset.pattern(intensity),
            time: duration,
            interval: preset.interval || 180,
            vibrate: true,
          }),
        }, action);
      }
    }

    async function executePlanStep(step, runId, index, total, title) {
      if (runId !== getPlanRunId()) return false;
      ctx.setPlanProgress(step.command, index, total, title);
      const labelPrefix = title ? `${title} ` : "";
      if (step.command === "pause") {
        await stopAction();
        getUiState().currentLabel = ctx.describeStep(step);
        ctx.renderConsole();
        ctx.setStatus(`Lovense: ${labelPrefix}Pause ${index}/${total} fuer ${step.duration_seconds}s.`);
        return await waitCancelable((Number(step.duration_seconds) || 1) * 1000, runId);
      }
      if (step.command === "stop") {
        getUiState().currentLabel = "Stop";
        await stopAction();
        ctx.setStatus(`Lovense: ${labelPrefix}Stop ${index}/${total}.`);
        return await waitCancelable(250, runId);
      }
      if (step.command === "preset") {
        const preset = combinedPresetMap()[String(step.preset || "").trim()];
        if (!preset) throw new Error(`Unbekanntes Preset: ${String(step.preset || "")}`);
        await runProgram({
          label: `${labelPrefix}Preset ${step.preset}`.trim(),
          kind: "pattern",
          buildPayload: ({ toyId, intensity, duration }) => ({
            toyId,
            strength: preset.pattern(intensity),
            time: duration,
            interval: preset.interval || 180,
            vibrate: true,
          }),
        }, step);
        getUiState().currentLabel = ctx.describeStep(step);
        ctx.setStatus(`Lovense: ${labelPrefix}Schritt ${index}/${total} laeuft (${step.command}).`);
        return await waitCancelable((Number(step.duration_seconds) || 1) * 1000, runId);
      }
      await runAction(step);
      getUiState().currentLabel = ctx.describeStep(step);
      ctx.setStatus(`Lovense: ${labelPrefix}Schritt ${index}/${total} laeuft (${step.command}).`);
      return await waitCancelable((Number(step.duration_seconds) || 1) * 1000, runId);
    }

    async function ensurePlanProcessor() {
      if (getPlanRunning()) return;
      setPlanRunning(true);
      const runId = getPlanRunId();
      try {
        while (runId === getPlanRunId() && getPlanQueue().length) {
          const current = getPlanQueue().shift();
          if (!current) continue;
          const total = Number(current.total || 0) || 1;
          const keepRunning = await executePlanStep(current.step, runId, Number(current.index || 1), total, current.title || "");
          if (!keepRunning) return;
        }
        if (runId === getPlanRunId()) {
          setPlanRunning(false);
          setPlanTitle("");
          getUiState().currentLabel = "fertig";
          ctx.renderPlanStatus({ state: "done", title: "Session-Plan", total: getPlanTotal(), current: getPlanTotal(), command: "" });
          ctx.setStatus("Lovense: Session-Plan abgeschlossen.");
        }
      } catch (err) {
        if (runId === getPlanRunId()) {
          setPlanRunning(false);
          const failedTitle = getPlanTitle() || "Session-Plan";
          setPlanTitle("");
          getUiState().currentLabel = "Fehler";
          ctx.renderPlanStatus({
            state: "error",
            title: failedTitle,
            total: getPlanTotal(),
            current: getPlanCurrentIndex(),
            command: getPlanCurrentCommand(),
          });
          ctx.setStatus(`Lovense: Session-Plan fehlgeschlagen (${String(err)})`);
          ctx.write("Lovense Plan Fehler", { error: String(err) });
        }
      }
    }

    async function queueSessionPlan(action) {
      const mode = String(action?.mode || "replace").trim().toLowerCase() === "append" ? "append" : "replace";
      const title = String(action?.title || "").trim();
      const steps = Array.isArray(action?.steps) ? action.steps.map(normalizePlanStep).filter(Boolean) : [];
      if (!steps.length) return;
      if (mode === "replace") {
        cancelPlan(true);
        await stopAction();
      }
      setPlanTitle(title);
      const queue = getPlanQueue();
      steps.forEach((step, index) => {
        queue.push({ step, index: index + 1, total: steps.length, title });
      });
      ctx.setPlanQueued(title, steps.length);
      ctx.setStatus(`Lovense: Session-Plan${title ? ` '${title}'` : ""} geladen (${steps.length} Schritte).`);
      try {
        await ctx.post(`/api/lovense/sessions/${ctx.sessionId}/events`, {
          source: "ai",
          phase: "queued",
          command: "plan",
          title: title || "Session-Plan",
          detail: `${steps.length} Schritte`,
        });
      } catch (_) {}
      await ensurePlanProcessor();
    }

    async function handleClientActions(actions, messageId = null) {
      const list = Array.isArray(actions) ? actions.filter(Boolean) : [];
      for (let index = 0; index < list.length; index += 1) {
        const action = list[index];
        const key = `${messageId || "standalone"}:${index}:${JSON.stringify(action)}`;
        if (ctx.handledKeys?.has(key)) continue;
        ctx.handledKeys?.add(key);
        try {
          if (action.type === "lovense_control") {
            if (String(action.command || "").trim().toLowerCase() === "stop" || getPlanRunning() || getPlanQueue().length) {
              cancelPlan(true);
            }
            await runAction(action);
            continue;
          }
          if (action.type === "lovense_session_plan") {
            await queueSessionPlan(action);
          }
        } catch (err) {
          ctx.setStatus(`Lovense: KI-Aktion fehlgeschlagen (${String(err)})`);
          ctx.write("Lovense Fehler", { action, error: String(err) });
        }
      }
    }

    return {
      cancelPlan,
      handleClientActions,
      init,
      loadPresetLibrary,
      stopAction,
      syncToys,
    };
  }

  window.ChasteasePlayLovenseController = {
    createController,
  };
})();
