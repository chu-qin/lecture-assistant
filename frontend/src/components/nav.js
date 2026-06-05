import Store from '../store.js';
import { setLanguage } from '../utils/i18n.js';
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
  brand.textContent = '课堂助手';
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
  defaultOpt.textContent = '选择课程...';
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
    themeBtn.textContent = getCurrentTheme() === 'dark' ? '浅色' : '深色';
  };
  themeBtn.textContent = getCurrentTheme() === 'dark' ? '浅色' : '深色';
  actions.appendChild(themeBtn);

  const langBtn = document.createElement('button');
  langBtn.className = 'nav-btn';
  langBtn.textContent = Store.get('language') === 'zh' ? 'EN' : '中';
  langBtn.onclick = async () => {
    const next = Store.get('language') === 'zh' ? 'en' : 'zh';
    await setLanguage(next);
    Store.set('language', next);
    langBtn.textContent = next === 'zh' ? 'EN' : '中';
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
    { hash: 'home', label: '课程' },
    { hash: 'materials', label: '资料录入' },
    { hash: 'review', label: '复习问答' },
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
