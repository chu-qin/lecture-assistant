export function initTheme() {
  const saved = localStorage.getItem('la-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  updateToggleLabel(saved);
}

export function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('la-theme', next);
  updateToggleLabel(next);
}

function updateToggleLabel(theme) {
  const btn = document.getElementById('themeToggle');
  if (btn) btn.textContent = theme === 'dark' ? '浅色' : '深色';
}

export function getCurrentTheme() {
  return document.documentElement.getAttribute('data-theme') || 'dark';
}
