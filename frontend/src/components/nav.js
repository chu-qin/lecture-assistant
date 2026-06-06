import Store from '../store.js';
import { setLanguage, t } from '../utils/i18n.js';
import { navigate } from '../router.js';
import { toggleTheme as doToggleTheme, getCurrentTheme } from './theme.js';
import { get as apiGet } from '../api.js';

export async function renderNav() {
  const nav = document.getElementById('nav');
  nav.innerHTML = '';
  nav.className = 'top-nav';

  // Brand / home link
  const brand = document.createElement('a');
  brand.href = '#home';
  brand.className = 'nav-brand';
  brand.textContent = t('nav.brand');
  nav.appendChild(brand);

  // Course selector
  const courseSelect = document.createElement('select');
  courseSelect.id = 'courseSelect';
  courseSelect.className = 'nav-course-select';
  courseSelect.onchange = () => {
    Store.set('currentCourse', courseSelect.value);
    localStorage.setItem('la-current-course', courseSelect.value);
    const currentRoute = window.location.hash.replace('#', '');
    if (currentRoute === 'home' && courseSelect.value) navigate('materials');
    else window.dispatchEvent(new Event('hashchange'));
  };

  const defaultOpt = document.createElement('option');
  defaultOpt.value = '';
  defaultOpt.textContent = t('nav.select_course');
  courseSelect.appendChild(defaultOpt);
  nav.appendChild(courseSelect);

  // Divider
  const divider = document.createElement('span');
  divider.className = 'nav-divider';
  nav.appendChild(divider);

  // Tab bar
  const tabs = document.createElement('div');
  tabs.className = 'nav-tabs';
  tabs.id = 'navTabs';
  nav.appendChild(tabs);

  // Actions
  const actions = document.createElement('div');
  actions.className = 'nav-actions';

  const themeBtn = document.createElement('button');
  themeBtn.id = 'themeToggle';
  themeBtn.className = 'nav-btn';
  themeBtn.onclick = () => {
    doToggleTheme();
    themeBtn.textContent = getCurrentTheme() === 'dark' ? t('nav.theme_light') : t('nav.theme_dark');
  };
  themeBtn.textContent = getCurrentTheme() === 'dark' ? t('nav.theme_light') : t('nav.theme_dark');
  actions.appendChild(themeBtn);

  const langBtn = document.createElement('button');
  langBtn.className = 'nav-btn';
  langBtn.textContent = Store.get('language') === 'zh' ? t('nav.lang_en') : t('nav.lang_zh');
  langBtn.onclick = async () => {
    const next = Store.get('language') === 'zh' ? 'en' : 'zh';
    await setLanguage(next);
    Store.set('language', next);
    langBtn.textContent = next === 'zh' ? t('nav.lang_en') : t('nav.lang_zh');
    window.dispatchEvent(new Event('hashchange'));
  };
  actions.appendChild(langBtn);

  nav.appendChild(actions);

  // Load courses
  try {
    const data = await apiGet('/courses');
    Store.set('courses', data.courses || []);

    const saved = Store.get('currentCourse');
    if (saved && data.courses && data.courses.find(c => c.name === saved)) {
      courseSelect.value = saved;
    }
  } catch (e) {
    console.warn('Failed to load courses:', e);
  }
}

export function updateNavTabs(active) {
  const container = document.getElementById('navTabs');
  if (!container) return;

  const tabs = [
    { hash: 'home', label: t('nav.tab_courses') },
    { hash: 'materials', label: t('nav.tab_materials') },
    { hash: 'review', label: t('nav.tab_review') },
  ];

  container.innerHTML = '';
  tabs.forEach(t => {
    const btn = document.createElement('button');
    btn.className = 'nav-tab';
    if (t.hash === active) btn.classList.add('active');
    btn.textContent = t.label;
    btn.onclick = () => navigate(t.hash);
    const course = Store.get('currentCourse');
    if (t.hash !== 'home' && !course) btn.disabled = true;
    container.appendChild(btn);
  });
}
