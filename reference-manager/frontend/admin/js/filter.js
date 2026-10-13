// AIP-160 filter subset: comparisons (= != : < <= > >=), AND, OR, NOT, parentheses, "field:*" for presence
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else (root.RM = root.RM || {}).filter = factory();
})(globalThis, function () {
  'use strict';

  class FilterError extends Error {}

  const OPERATORS = ['<=', '>=', '!=', '<', '>', '=', ':'];

  function tokenize(source) {
    const tokens = [];
    let i = 0;
    while (i < source.length) {
      const c = source[i];
      if (/\s/.test(c)) { i += 1; continue; }
      if (c === '(' || c === ')') { tokens.push({ type: c, at: i }); i += 1; continue; }
      const op = OPERATORS.find((o) => source.startsWith(o, i));
      if (op) { tokens.push({ type: 'op', value: op, at: i }); i += op.length; continue; }
      if (c === '"') {
        let j = i + 1;
        let text = '';
        while (j < source.length && source[j] !== '"') {
          if (source[j] === '\\' && j + 1 < source.length) j += 1;
          text += source[j];
          j += 1;
        }
        if (j >= source.length) throw new FilterError(`unterminated string at position ${i}`);
        tokens.push({ type: 'string', value: text, at: i });
        i = j + 1;
        continue;
      }
      const match = /^[^\s()<>=!:"]+/.exec(source.slice(i));
      if (!match) throw new FilterError(`unexpected character "${c}" at position ${i}`);
      tokens.push({ type: 'word', value: match[0], at: i });
      i += match[0].length;
    }
    return tokens;
  }

  function parse(source) {
    const tokens = tokenize(source);
    let position = 0;
    const peek = () => tokens[position];
    const next = () => tokens[position++];
    const isKeyword = (word) => peek() && peek().type === 'word' && peek().value.toUpperCase() === word;
    const describe = (token) => (token.type === 'op' || token.type === 'word' || token.type === 'string' ? token.value : token.type);

    function expression() {
      let left = conjunction();
      while (isKeyword('OR')) {
        next();
        left = { kind: 'or', left, right: conjunction() };
      }
      return left;
    }

    // terms separated by whitespace are joined with AND, the keyword is optional
    function conjunction() {
      let left = negation();
      while (peek() && peek().type !== ')' && !isKeyword('OR')) {
        if (isKeyword('AND')) next();
        left = { kind: 'and', left, right: negation() };
      }
      return left;
    }

    function negation() {
      if (isKeyword('NOT')) {
        next();
        return { kind: 'not', operand: negation() };
      }
      return primary();
    }

    function primary() {
      const token = next();
      if (!token) throw new FilterError('unexpected end of filter');
      if (token.type === '(') {
        const inner = expression();
        const closing = next();
        if (!closing || closing.type !== ')') throw new FilterError('missing ")"');
        return inner;
      }
      if (token.type !== 'word') throw new FilterError(`unexpected "${describe(token)}" at position ${token.at}`);
      const operator = peek();
      if (!operator || operator.type !== 'op') throw new FilterError(`expected an operator after "${token.value}"`);
      next();
      const value = next();
      if (!value || (value.type !== 'word' && value.type !== 'string')) {
        throw new FilterError(`expected a value after "${token.value} ${operator.value}"`);
      }
      return { kind: 'compare', field: token.value, operator: operator.value, value: value.value, quoted: value.type === 'string' };
    }

    const tree = expression();
    if (position < tokens.length) throw new FilterError(`unexpected "${describe(tokens[position])}" at position ${tokens[position].at}`);
    return tree;
  }

  function collectFields(node, into) {
    if (node.kind === 'compare') into.add(node.field);
    else if (node.kind === 'not') collectFields(node.operand, into);
    else { collectFields(node.left, into); collectFields(node.right, into); }
    return into;
  }

  function compare(actual, operator, value, quoted) {
    const present = actual !== null && actual !== undefined && actual !== '';
    if (operator === ':') {
      if (value === '*' && !quoted) return present;
      return present && String(actual).toLowerCase().includes(String(value).toLowerCase());
    }
    if (!present) return operator === '!=';
    const numeric = !quoted && typeof actual === 'number' && value !== '' && !Number.isNaN(Number(value));
    let order;
    if (numeric) order = actual - Number(value);
    else {
      const left = String(actual);
      const right = String(value);
      order = left < right ? -1 : left > right ? 1 : 0;
    }
    switch (operator) {
      case '=': return order === 0;
      case '!=': return order !== 0;
      case '<': return order < 0;
      case '<=': return order <= 0;
      case '>': return order > 0;
      case '>=': return order >= 0;
      default: return false;
    }
  }

  function evaluate(node, record) {
    switch (node.kind) {
      case 'and': return evaluate(node.left, record) && evaluate(node.right, record);
      case 'or': return evaluate(node.left, record) || evaluate(node.right, record);
      case 'not': return !evaluate(node.operand, record);
      default: return compare(record[node.field], node.operator, node.value, node.quoted);
    }
  }

  // returns a predicate over plain records, throws FilterError on syntax or unknown fields
  function compile(source, allowedFields) {
    if (!source || !source.trim()) return () => true;
    const tree = parse(source);
    const allowed = new Set(allowedFields || []);
    for (const field of collectFields(tree, new Set())) {
      if (!allowed.has(field)) throw new FilterError(`unknown field "${field}"`);
    }
    return (record) => evaluate(tree, record);
  }

  return { compile, parse, tokenize, FilterError };
});
