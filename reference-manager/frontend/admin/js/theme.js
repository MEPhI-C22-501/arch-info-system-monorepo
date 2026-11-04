// theme of the page before the first paint: "light", "dark" or the system setting, the choice is a convenience
// of one browser kept in localStorage, the page works the same without it
(function () {
  'use strict';

  const KEY = 'rm.theme';
  const CHOICES = ['system', 'light', 'dark'];
  const LABELS = { system: 'системная', light: 'светлая', dark: 'тёмная' };

  function read() {
    try {
      const value = localStorage.getItem(KEY);
      return CHOICES.includes(value) ? value : 'system';
    } catch (e) {
      return 'system';
    }
  }

  function apply(choice) {
    if (choice === 'system') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', choice);
  }

  function label(choice) {
    return `Тема: ${LABELS[choice]}`;
  }

  function next(choice) {
    return CHOICES[(CHOICES.indexOf(choice) + 1) % CHOICES.length];
  }

  let current = read();
  apply(current);

  document.addEventListener('DOMContentLoaded', () => {
    const button = document.getElementById('theme');
    if (!button) return;
    button.textContent = label(current);
    button.addEventListener('click', () => {
      current = next(current);
      try { localStorage.setItem(KEY, current); } catch (e) { /* storage is optional, the choice lasts until reload */ }
      apply(current);
      button.textContent = label(current);
    });
  });
})();
