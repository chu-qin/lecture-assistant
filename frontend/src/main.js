import './styles/base.css';
import './styles/components.css';
import './styles/nav.css';
import './styles/home.css';
import './styles/materials.css';
import './styles/review.css';
import { initTheme } from './components/theme.js';
import { setLanguage } from './utils/i18n.js';
import { renderNav, updateNavTabs } from './components/nav.js';
import { register, getCurrentRoute } from './router.js';
import Store from './store.js';
import { renderHomePage } from './pages/home.js';
import { renderMaterialsPage } from './pages/materials.js';
import { renderReviewPage } from './pages/review.js';

register('home', renderHomePage);
register('materials', renderMaterialsPage);
register('review', renderReviewPage);

window.addEventListener('hashchange', () => {
  updateNavTabs(getCurrentRoute());
});

async function init() {
  initTheme();
  await setLanguage(Store.get('language'));

  // Restore last course
  const saved = localStorage.getItem('la-current-course');
  if (saved) Store.set('currentCourse', saved);

  await renderNav();
  updateNavTabs(getCurrentRoute());

  // Update theme toggle label
  const theme = document.documentElement.getAttribute('data-theme');
  const themeBtn = document.getElementById('themeToggle');
  if (themeBtn) themeBtn.textContent = theme === 'dark' ? '浅色' : '深色';
}

document.addEventListener('DOMContentLoaded', init);
