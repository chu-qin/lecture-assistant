import Store from '../store.js';
import { get, post, del } from '../api.js';
import { showToast } from '../components/toast.js';
import { navigate } from '../router.js';
import { t } from '../utils/i18n.js';
import { escapeHtml } from '../utils/dom.js';

export async function renderHomePage() {
  const main = document.getElementById('main-content');
  main.innerHTML = `<div class="home-page"><div class="home-loading empty-state"><p>${t('home.loading')}</p></div></div>`;

  let courses = [];
  try {
    const data = await get('/courses');
    courses = data.courses || [];
    Store.set('courses', courses);
  } catch (e) {
    main.innerHTML = `<div class="home-page"><div class="empty-state"><p>${t('home.load_failed', {error: e.message})}</p></div></div>`;
    return;
  }

  main.innerHTML = '';
  const page = document.createElement('div');
  page.className = 'home-page';

  // Active course hero
  const currentCourse = Store.get('currentCourse');
  if (currentCourse) {
    const currentData = courses.find(c => c.name === currentCourse);
    if (currentData) {
      page.appendChild(buildHero(currentData));
    }
  }

  // Create section — always visible at top
  page.appendChild(buildCreateSection(() => loadAndRender()));

  if (courses.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.innerHTML = `
      <div class="empty-icon">📚</div>
      <p class="empty-title">${t('home.no_courses_title')}</p>
      <p class="empty-desc">${t('home.no_courses_desc')}</p>
    `;
    page.appendChild(empty);
    main.appendChild(page);
    return;
  }

  const grid = document.createElement('div');
  grid.className = 'course-grid';
  courses.forEach(c => buildCourseCard(c, grid));
  page.appendChild(grid);

  main.appendChild(page);
}

function buildHero(course) {
  const hero = document.createElement('div');
  hero.className = 'course-hero';

  const kbClass = course.kb_ready ? 'ready' : 'off';
  const kbText = course.kb_ready ? t('home.kb_ready') : t('home.kb_not_built');

  hero.innerHTML = `
    <div class="hero-info">
      <div class="hero-course-name">${escapeHtml(course.name)}</div>
      <div class="hero-meta">
        <span class="kb-badge ${kbClass}">${kbText}</span>
        <span class="hero-stat">${t('home.stats_transcripts', {n: course.transcripts || 0})}</span>
        <span class="hero-stat">${t('home.stats_review', {n: course.review_materials || 0})}</span>
        <span class="hero-stat">${t('home.stats_audio', {n: course.audio_files || 0})}</span>
      </div>
    </div>
    <div class="hero-actions">
      <button class="btn btn-primary hero-btn" data-action="materials">${t('home.upload_materials')}</button>
      <button class="btn hero-btn" data-action="review">${t('home.enter_review')}</button>
    </div>
  `;

  hero.querySelector('[data-action="materials"]').onclick = () => {
    Store.set('currentCourse', course.name);
    localStorage.setItem('la-current-course', course.name);
    navigate('materials');
  };
  hero.querySelector('[data-action="review"]').onclick = () => {
    Store.set('currentCourse', course.name);
    localStorage.setItem('la-current-course', course.name);
    navigate('review');
  };

  return hero;
}

function buildCourseCard(course, grid) {
  const card = document.createElement('div');
  card.className = 'course-card';

  const kbClass = course.kb_ready ? 'ready' : 'off';
  const kbText = course.kb_ready ? t('home.kb_ready') : t('home.not_built_short');
  const isActive = Store.get('currentCourse') === course.name;

  card.innerHTML = `
    <div class="course-card-header">
      <span class="course-name">${escapeHtml(course.name)}</span>
      <span class="kb-badge ${kbClass}">${kbText}</span>
    </div>
    <div class="course-stats">
      <div class="stat"><span class="stat-num">${course.transcripts || 0}</span><span class="stat-label">转录</span></div>
      <div class="stat"><span class="stat-num">${course.review_materials || 0}</span><span class="stat-label">资料</span></div>
      <div class="stat"><span class="stat-num">${course.audio_files || 0}</span><span class="stat-label">音频</span></div>
    </div>
    <div class="course-actions">
      <button class="btn btn-primary btn-sm" data-action="enter">${t('home.enter_course')}</button>
      <button class="btn btn-sm" data-action="delete" title="${t('home.delete')}">${t('home.delete')}</button>
    </div>
  `;

  if (isActive) {
    card.classList.add('active-course');
  }

  card.querySelector('[data-action="enter"]').onclick = (e) => {
    e.stopPropagation();
    enterCourse(course.name);
  };
  card.querySelector('[data-action="delete"]').onclick = (e) => {
    e.stopPropagation();
    e.target.classList.add('btn-loading');
    e.target.disabled = true;
    deleteCourse(course.name);
  };

  card.onclick = () => enterCourse(course.name);
  grid.appendChild(card);
}

function buildCreateSection(onSuccess) {
  const section = document.createElement('div');
  section.className = 'create-section';

  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'create-input';
  input.placeholder = t('home.create_placeholder');
  input.maxLength = 50;

  const btn = document.createElement('button');
  btn.className = 'btn btn-primary';
  btn.textContent = t('home.create_btn');
  btn.onclick = async () => {
    const name = input.value.trim();
    if (!name) {
      showToast(t('home.name_required'), 'warning');
      return;
    }
    btn.disabled = true;
    btn.classList.add('btn-loading');
    try {
      await post('/courses', { name });
      input.value = '';
      showToast(t('home.created', {name}), 'success');
      onSuccess();
    } catch (e) {
      showToast(t('home.create_failed', {error: e.message}), 'error');
    }
    btn.disabled = false;
    btn.classList.remove('btn-loading');
  };

  // Enter key to submit
  input.onkeydown = (e) => {
    if (e.key === 'Enter') btn.click();
  };

  section.appendChild(input);
  section.appendChild(btn);
  return section;
}

async function loadAndRender() {
  await renderHomePage();
}

function enterCourse(name) {
  Store.set('currentCourse', name);
  localStorage.setItem('la-current-course', name);
  navigate('materials');
}

async function deleteCourse(name) {
  if (!confirm(t('home.delete_confirm', {name}))) return;
  try {
    await del(`/courses/${encodeURIComponent(name)}`);
    showToast(t('home.deleted', {name}), 'success');
    if (Store.get('currentCourse') === name) {
      Store.set('currentCourse', '');
      localStorage.removeItem('la-current-course');
    }
    await renderHomePage();
  } catch (e) {
    showToast(t('home.delete_failed', {error: e.message}), 'error');
  }
}
