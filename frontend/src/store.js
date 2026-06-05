const Store = {
  _state: {
    currentCourse: '',
    courses: [],
    theme: localStorage.getItem('la-theme') || 'dark',
    language: localStorage.getItem('la-language') || 'zh',
    kbReady: false,
    materialList: [],
    chatHistory: [],
    transcripts: [],
    documents: [],
  },
  _listeners: {},

  get(key) {
    return this._state[key];
  },

  set(key, value) {
    this._state[key] = value;
    (this._listeners[key] || []).forEach(fn => fn(value));
  },

  on(key, fn) {
    (this._listeners[key] = this._listeners[key] || []).push(fn);
  },

  off(key, fn) {
    const arr = this._listeners[key];
    if (arr) {
      const idx = arr.indexOf(fn);
      if (idx !== -1) arr.splice(idx, 1);
    }
  },

  batch(updates) {
    for (const [key, value] of Object.entries(updates)) {
      this._state[key] = value;
    }
    for (const key of Object.keys(updates)) {
      (this._listeners[key] || []).forEach(fn => fn(this._state[key]));
    }
  },
};

export default Store;
