// Theme toggle (dark/light mode) with localStorage persistence
(function () {
  const STORAGE_KEY = 'chastease_theme';
  const html = document.documentElement;
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === 'light') {
    html.classList.remove('dark');
  } else {
    html.classList.add('dark');
  }

  function updateIcons() {
    const isDark = html.classList.contains('dark');
    const iconDark = document.getElementById('themeIconDark');
    const iconLight = document.getElementById('themeIconLight');
    if (iconDark) iconDark.classList.toggle('hidden', !isDark);
    if (iconLight) iconLight.classList.toggle('hidden', isDark);
  }

  document.addEventListener('DOMContentLoaded', function () {
    updateIcons();
    const btn = document.getElementById('themeToggle');
    if (btn) {
      btn.addEventListener('click', function () {
        html.classList.toggle('dark');
        const isDark = html.classList.contains('dark');
        localStorage.setItem(STORAGE_KEY, isDark ? 'dark' : 'light');
        updateIcons();
      });
    }
  });
})();
