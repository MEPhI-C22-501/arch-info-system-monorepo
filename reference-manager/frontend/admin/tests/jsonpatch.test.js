const test = require('node:test');
const assert = require('node:assert/strict');
const jsonpatch = require('../js/jsonpatch.js');

test('add, replace and remove on a flat record, the input stays unchanged', () => {
  const doc = { name: 'Евро', decimals: 2 };
  const result = jsonpatch.apply(doc, [
    { op: 'replace', path: '/name', value: 'Euro' },
    { op: 'add', path: '/code', value: 'EUR' },
    { op: 'remove', path: '/decimals' },
  ]);
  assert.deepEqual(result, { name: 'Euro', code: 'EUR' });
  assert.deepEqual(doc, { name: 'Евро', decimals: 2 });
});

test('the state on a revision is the creation patch plus the following patches in order', () => {
  const revisions = [
    { revision_number: 3, change: [{ op: 'replace', path: '/account_state', value: 'DISABLED' }] },
    { revision_number: 1, change: [{ op: 'add', path: '/family_name', value: 'Petrova' }, { op: 'add', path: '/account_state', value: 'PENDING' }, { op: 'add', path: '/is_deleted', value: false }] },
    { revision_number: 2, change: [{ op: 'replace', path: '/account_state', value: 'ENABLED' }, { op: 'replace', path: '/account_user_id', value: 'abc' }] },
  ];
  assert.deepEqual(jsonpatch.stateAt(revisions, 1), { family_name: 'Petrova', account_state: 'PENDING', is_deleted: false });
  assert.deepEqual(jsonpatch.stateAt(revisions, 2), { family_name: 'Petrova', account_state: 'ENABLED', is_deleted: false, account_user_id: 'abc' });
  assert.equal(jsonpatch.stateAt(revisions, 3).account_state, 'DISABLED');
});

test('pointer tokens are unescaped and the field of an operation is its first token', () => {
  assert.deepEqual(jsonpatch.tokens('/a~1b/c~0d'), ['a/b', 'c~d']);
  assert.equal(jsonpatch.fieldOf({ op: 'replace', path: '/end_date', value: null }), 'end_date');
  assert.throws(() => jsonpatch.tokens('name'), /invalid JSON pointer/);
});

test('arrays, copy, move and test are supported, an unknown operation throws', () => {
  const doc = { tags: ['a', 'c'], n: 1 };
  const result = jsonpatch.apply(doc, [
    { op: 'add', path: '/tags/1', value: 'b' },
    { op: 'copy', from: '/n', path: '/m' },
    { op: 'move', from: '/m', path: '/k' },
    { op: 'test', path: '/k', value: 1 },
  ]);
  assert.deepEqual(result, { tags: ['a', 'b', 'c'], n: 1, k: 1 });
  assert.throws(() => jsonpatch.apply({}, [{ op: 'swap', path: '/x' }]), /unknown operation/);
  assert.throws(() => jsonpatch.apply({ k: 1 }, [{ op: 'test', path: '/k', value: 2 }]), /test failed/);
});
