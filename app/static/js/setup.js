(() => {
  const steps = Array.from(document.querySelectorAll(".wizard-step"));
  const pills = Array.from(document.querySelectorAll("[data-step-pill]"));
  const prevBtn = document.getElementById("setup-prev");
  const nextBtn = document.getElementById("setup-next");
  const finishBtn = document.getElementById("setup-finish");
  const styleSelect = document.getElementById("setup-role-style");
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

  refresh();
})();
