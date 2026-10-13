// small DOM helpers: every value becomes a text node, markup is never built from strings
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else (root.RM = root.RM || {}).dom = factory();
})(globalThis, function () {
  'use strict';

  // el('button', { class: 'primary', on: { click: fn } }, 'text', childNode, [more])
  function el(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs || {})) {
      if (value === null || value === undefined || value === false) continue;
      if (key === 'on') {
        for (const [event, handler] of Object.entries(value)) node.addEventListener(event, handler);
      } else if (key === 'dataset') {
        Object.assign(node.dataset, value);
      } else if (key === 'value' || key === 'checked' || key === 'selected' || key === 'disabled' || key === 'hidden' || key === 'readOnly' || key === 'required' || key === 'open') {
        node[key] = value;
      } else {
        node.setAttribute(key, value === true ? '' : String(value));
      }
    }
    append(node, children);
    return node;
  }

  function append(node, children) {
    for (const child of children) {
      if (child === null || child === undefined || child === false) continue;
      if (Array.isArray(child)) append(node, child);
      else if (child instanceof Node) node.appendChild(child);
      else node.appendChild(document.createTextNode(String(child)));
    }
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
    return node;
  }

  function replace(node, ...children) {
    clear(node);
    return append(node, children);
  }

  const $ = (selector, scope) => (scope || document).querySelector(selector);

  return { el, append, clear, replace, $ };
});
