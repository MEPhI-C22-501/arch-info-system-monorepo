// JSON Patch (RFC 6902) for the revisions of a record: the state on a revision is the patches applied in order
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else (root.RM = root.RM || {}).jsonpatch = factory();
})(globalThis, function () {
  'use strict';

  function tokens(path) {
    if (path === '' || path === undefined || path === null) return [];
    if (path[0] !== '/') throw new Error(`invalid JSON pointer "${path}"`);
    return path.slice(1).split('/').map((t) => t.replace(/~1/g, '/').replace(/~0/g, '~'));
  }

  function clone(value) {
    return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
  }

  function parent(doc, parts) {
    let node = doc;
    for (const part of parts.slice(0, -1)) {
      if (node === null || typeof node !== 'object') throw new Error(`path "${parts.join('/')}" does not exist`);
      node = Array.isArray(node) ? node[Number(part)] : node[part];
    }
    return node;
  }

  function set(doc, path, value) {
    const parts = tokens(path);
    if (!parts.length) return clone(value);
    const node = parent(doc, parts);
    const key = parts[parts.length - 1];
    if (Array.isArray(node)) {
      if (key === '-') node.push(clone(value));
      else node.splice(Number(key), 0, clone(value));
    } else {
      node[key] = clone(value);
    }
    return doc;
  }

  function get(doc, path) {
    let node = doc;
    for (const part of tokens(path)) {
      if (node === null || typeof node !== 'object') return undefined;
      node = Array.isArray(node) ? node[Number(part)] : node[part];
    }
    return node;
  }

  function remove(doc, path) {
    const parts = tokens(path);
    if (!parts.length) return {};
    const node = parent(doc, parts);
    const key = parts[parts.length - 1];
    if (Array.isArray(node)) node.splice(Number(key), 1);
    else delete node[key];
    return doc;
  }

  // apply(document, operations) returns a new document, the input is not changed
  function apply(document, operations) {
    let doc = clone(document === undefined ? {} : document);
    for (const op of operations || []) {
      switch (op.op) {
        case 'add':
          doc = set(doc, op.path, op.value);
          break;
        case 'replace':
          doc = set(doc, op.path, op.value);
          break;
        case 'remove':
          doc = remove(doc, op.path);
          break;
        case 'copy':
          doc = set(doc, op.path, get(doc, op.from));
          break;
        case 'move': {
          const value = get(doc, op.from);
          doc = remove(doc, op.from);
          doc = set(doc, op.path, value);
          break;
        }
        case 'test':
          if (JSON.stringify(get(doc, op.path)) !== JSON.stringify(op.value)) throw new Error(`test failed at "${op.path}"`);
          break;
        default:
          throw new Error(`unknown operation "${op.op}"`);
      }
    }
    return doc;
  }

  // the state of a record after the revisions with numbers up to and including the given one
  function stateAt(revisions, number) {
    const sorted = [...revisions].sort((a, b) => a.revision_number - b.revision_number);
    let doc = {};
    for (const revision of sorted) {
      if (revision.revision_number > number) break;
      doc = apply(doc, revision.change);
    }
    return doc;
  }

  // the field a patch operation touches, "/family_name" -> "family_name"
  function fieldOf(op) {
    const parts = tokens(op.path);
    return parts.length ? parts[0] : '';
  }

  return { apply, stateAt, get, fieldOf, tokens };
});
