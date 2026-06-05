export function $(selector, parent) {
  return (parent || document).querySelector(selector);
}

export function $$(selector, parent) {
  return Array.from((parent || document).querySelectorAll(selector));
}

export function createElement(tag, attrs, children) {
  const el = document.createElement(tag);
  if (attrs) {
    for (const [key, val] of Object.entries(attrs)) {
      if (key === 'class') {
        el.className = val;
      } else if (key.startsWith('on')) {
        el.addEventListener(key.slice(2).toLowerCase(), val);
      } else {
        el.setAttribute(key, val);
      }
    }
  }
  if (children) {
    if (typeof children === 'string') {
      el.innerHTML = children;
    } else if (Array.isArray(children)) {
      children.forEach(c => {
        el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
      });
    } else if (children instanceof Node) {
      el.appendChild(children);
    }
  }
  return el;
}

export function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}
