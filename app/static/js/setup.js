(() => {
  const steps = Array.from(document.querySelectorAll(".wizard-step"));
  const pills = Array.from(document.querySelectorAll("[data-step-pill]"));
  const prevBtn = document.getElementById("setup-prev");
  const nextBtn = document.getElementById("setup-next");
  const finishBtn = document.getElementById("setup-finish");
  let index = 0;

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

  refresh();
})();
