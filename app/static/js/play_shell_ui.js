(() => {
  function bindMenu(options = {}) {
    const menu = document.getElementById(String(options.menuId || ""));
    const toggle = document.getElementById(String(options.toggleId || ""));
    const dropdown = document.getElementById(String(options.dropdownId || ""));
    const mobileClass = String(options.mobileClass || "is-open-mobile");
    const openClass = String(options.openClass || "is-open");
    const breakpoint = Number(options.mobileBreakpoint || 820);
    const onClose = typeof options.onClose === "function" ? options.onClose : () => {};
    if (!menu || !toggle || !dropdown) return { close: () => {} };

    function close() {
      dropdown.classList.remove(openClass);
      menu.classList.remove(mobileClass);
      toggle.setAttribute("aria-expanded", "false");
      onClose();
    }

    toggle.addEventListener("click", (event) => {
      event.stopPropagation();
      const open = dropdown.classList.toggle(openClass);
      if (window.innerWidth <= breakpoint) {
        menu.classList.toggle(mobileClass, open);
      }
      toggle.setAttribute("aria-expanded", String(open));
    });

    document.addEventListener("click", (event) => {
      if (!event.target.closest(`#${menu.id}`)) close();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    });

    return { close };
  }

  window.ChasteasePlayShellUI = {
    bindMenu,
  };
})();
