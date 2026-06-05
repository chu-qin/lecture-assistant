let _locale = {};
let _lang = 'zh';

export async function setLanguage(lang) {
  try {
    const resp = await fetch(`/locales/${lang}.json`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    _locale = await resp.json();
    _lang = lang;
    localStorage.setItem('la-language', lang);
  } catch (e) {
    console.warn('Failed to load locale:', lang, e);
  }
}

export function t(key, params) {
  let val = _locale[key] || key;
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      val = val.replace(`{${k}}`, String(v));
    }
  }
  return val;
}

export function currentLanguage() {
  return _lang;
}
