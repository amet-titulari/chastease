(() => {
  const tabs = Array.from(document.querySelectorAll(".auth-tab"));
  const forms = {
    register: document.getElementById("register-form"),
    login: document.getElementById("login-form"),
  };

  const setActive = (target) => {
    tabs.forEach((tab) => {
      tab.classList.toggle("is-active", tab.dataset.authTarget === target);
    });
    Object.entries(forms).forEach(([key, form]) => {
      if (!form) {
        return;
      }
      form.classList.toggle("is-active", key === target);
    });
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => setActive(tab.dataset.authTarget));
  });
})();
