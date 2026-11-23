// Theme toggle: light/dark with localStorage persistence.
(function () {
  var root = document.documentElement;
  var button = document.getElementById('theme-toggle');
  if (!button) return;

  function applyTheme(theme) {
    root.setAttribute('data-bs-theme', theme);
    localStorage.setItem('theme', theme);
    button.textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
    button.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
  }

  var current = root.getAttribute('data-bs-theme') || 'light';
  applyTheme(current);

  button.addEventListener('click', function () {
    var next = root.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    applyTheme(next);
  });
})();
