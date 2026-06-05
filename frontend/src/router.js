const routes = {};

export function register(hash, renderFn, title) {
  routes[hash] = { render: renderFn, title: title || hash };
}

export function getCurrentRoute() {
  const hash = window.location.hash.replace('#', '');
  return routes[hash] ? hash : 'home';
}

export function navigate(hash) {
  window.location.hash = '#' + hash;
}

let _beforeChange = null;

export function onBeforeChange(fn) {
  _beforeChange = fn;
}

window.addEventListener('hashchange', () => {
  const route = getCurrentRoute();
  if (_beforeChange) _beforeChange(route);
  if (routes[route]) {
    routes[route].render();
  }
});

window.addEventListener('DOMContentLoaded', () => {
  if (!window.location.hash) {
    window.location.hash = '#home';
  } else {
    const route = getCurrentRoute();
    if (routes[route]) {
      routes[route].render();
    }
  }
});

export default { register, getCurrentRoute, navigate, onBeforeChange };
