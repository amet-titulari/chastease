(() => {
  const steps = Array.from(document.querySelectorAll(".wizard-step"));
  const pills = Array.from(document.querySelectorAll("[data-step-pill]"));
  const prevBtn = document.getElementById("setup-prev");
  const nextBtn = document.getElementById("setup-next");
  const finishBtn = document.getElementById("setup-finish");
  const styleSelect = document.getElementById("setup-role-style");
  const goalInput = document.getElementById("setup-primary-goal");
  const goalPresets = Array.from(document.querySelectorAll('input[name="goal_preset"]'));
  const boundaryChecks = Array.from(document.querySelectorAll(".boundary-presets input[type='checkbox']"));
  const boundaryCustom = document.getElementById("setup-boundary-custom");
  const boundaryApplyBtn = document.getElementById("setup-boundary-apply");
  const boundaryNote = document.getElementById("setup-boundary-note");
  const styleImpactTitle = document.getElementById("style-impact-title");
  const styleImpactList = document.getElementById("style-impact-list");
  let index = 0;

  const STYLE_IMPACTS = {
    strict: {
      title: "Auswirkungen: Strict",
      points: [
        "Haertere Tonalitaet und engere Kontrolle bei Updates.",
        "Tasks werden kuerzer getaktet und klarer sanktioniert.",
        "Weniger Verhandlungsspielraum in laufenden Routinen.",
      ],
    },
    structured: {
      title: "Auswirkungen: Structured",
      points: [
        "Aufgaben sind klar formuliert und zeitlich planbar.",
        "Tonalitaet bleibt verbindlich, aber weniger hart als Strict.",
        "Routinen und Verlaufskonsistenz stehen im Vordergrund.",
      ],
    },
    supportive: {
      title: "Auswirkungen: Supportive",
      points: [
        "Motivierender, ruhiger Stil mit Safety-zentrierter Sprache.",
        "Sanftere Eskalation bei Fehlern, mehr Coaching-Momente.",
        "Regelbindung bleibt aktiv, aber emotional abgefedert.",
      ],
    },
  };

  const renderStyleImpact = (styleKey) => {
    const selected = STYLE_IMPACTS[styleKey] || STYLE_IMPACTS.structured;
    if (styleImpactTitle) {
      styleImpactTitle.textContent = selected.title;
    }
    if (styleImpactList) {
      styleImpactList.innerHTML = selected.points.map((point) => `<li>${point}</li>`).join("");
    }
  };

  const syncGoalPreset = (value) => {
    if (!goalInput) {
      return;
    }
    if (value === "__custom__") {
      goalInput.value = "";
      goalInput.placeholder = "Dein eigenes Hauptziel";
      goalInput.focus();
      return;
    }
    goalInput.value = value;
    goalInput.placeholder = "z.B. Routine und bessere Compliance";
  };

  const refresh = () => {
    steps.forEach((step, i) => {
      step.classList.toggle("is-active", i === index);
    });
    pills.forEach((pill, i) => {
      pill.classList.toggle("is-active", i === index);
    });

    prevBtn.disabled = index === 0;
    nextBtn.classList.toggle("is-hidden", index === steps.length - 1);
    finishBtn.classList.toggle("is-hidden", index !== steps.length - 1);
  };

  prevBtn.addEventListener("click", () => {
    if (index > 0) {
      index -= 1;
      refresh();
    }
  });

  nextBtn.addEventListener("click", () => {
    if (index < steps.length - 1) {
      index += 1;
      refresh();
    }
  });

  if (styleSelect) {
    styleSelect.addEventListener("change", () => {
      renderStyleImpact(styleSelect.value);
    });
    renderStyleImpact(styleSelect.value);
  }

  goalPresets.forEach((preset) => {
    preset.addEventListener("change", () => {
      if (preset.checked) {
        syncGoalPreset(preset.value);
      }
    });
  });

  if (boundaryApplyBtn && boundaryNote) {
    boundaryApplyBtn.addEventListener("click", () => {
      const selected = boundaryChecks
        .filter((el) => el.checked)
        .map((el) => String(el.value).trim())
        .filter(Boolean);

      const custom = String(boundaryCustom?.value || "").trim();
      if (custom) {
        selected.push(custom);
      }

      if (!selected.length) {
        return;
      }

      const block = selected.map((item) => `- ${item}`).join("\n");
      if (boundaryNote.value.trim()) {
        boundaryNote.value = `${boundaryNote.value.trim()}\n${block}`;
      } else {
        boundaryNote.value = block;
      }
    });
  }

  refresh();
})();
