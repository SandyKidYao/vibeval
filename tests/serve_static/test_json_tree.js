// Node-based regression test for the JSON tree renderer in app.js.
// Loads only the renderer slice (the `$` helper and the jsonPre/jsonNode
// family), runs it against a minimal DOM stub, and asserts behavior on
// representative inputs.

'use strict';

const fs = require('fs');
const path = require('path');

// ---- minimal DOM stub --------------------------------------------------

function makeNode(tag) {
  const node = {
    tagName: tag,
    children: [],
    attributes: {},
    listeners: {},
    style: {},
    _classes: new Set(),
    _text: null,
    appendChild(c) {
      this.children.push(c);
      return c;
    },
    setAttribute(k, v) { this.attributes[k] = v; },
    addEventListener(ev, fn) {
      (this.listeners[ev] = this.listeners[ev] || []).push(fn);
    },
    get className() { return [...this._classes].join(' '); },
    set className(v) {
      this._classes = new Set(String(v).split(/\s+/).filter(Boolean));
    },
    set textContent(v) {
      this._text = String(v);
      this.children = [];
    },
    get textContent() {
      if (this._text !== null) return this._text;
      return this.children
        .map((c) => {
          if (c == null) return '';
          if (typeof c === 'string') return c;
          if (c._isTextNode) return c.textContent;
          return c.textContent || '';
        })
        .join('');
    },
    set innerHTML(v) { this._text = String(v); },
  };
  node.classList = {
    add: (c) => node._classes.add(c),
    remove: (c) => node._classes.delete(c),
    toggle: (c) => {
      if (node._classes.has(c)) { node._classes.delete(c); return false; }
      node._classes.add(c); return true;
    },
    contains: (c) => node._classes.has(c),
  };
  return node;
}

const documentStub = {
  createElement: makeNode,
  createTextNode: (s) => ({ _isTextNode: true, textContent: String(s) }),
};

// ---- load only the renderer slice from app.js --------------------------

const appJsPath = path.resolve(__dirname, '..', '..', 'src', 'vibeval', 'serve', 'static', 'app.js');
const appJs = fs.readFileSync(appJsPath, 'utf8').split('\n');

// Lines are 1-indexed in the file; arrays are 0-indexed here.
// Helper `$` is lines 4..17, JSON renderer block is lines 30..119.
const helperSlice = appJs.slice(3, 17).join('\n');
const rendererSlice = appJs.slice(29, 119).join('\n');

// Compile in a sandbox where `document` is our stub. Functions are
// captured into the surrounding scope via assignment-by-eval.
const sandbox = { document: documentStub };
const compile = new Function(
  'document',
  helperSlice + '\n' + rendererSlice + '\n' +
    'return { jsonPre, jsonNode, jsonString, jsonArray, jsonObject, jsonCollapsible };'
);
const api = compile(documentStub);

// ---- assertion harness -------------------------------------------------

let failures = 0;
function assert(cond, msg) {
  if (!cond) {
    console.error('FAIL: ' + msg);
    failures += 1;
  }
}

function findClass(node, cls) {
  if (!node || typeof node !== 'object') return false;
  if (node._classes && node._classes.has && node._classes.has(cls)) return true;
  if (Array.isArray(node.children)) {
    for (const c of node.children) {
      if (findClass(c, cls)) return true;
    }
  }
  return false;
}

// ---- tests -------------------------------------------------------------

// 1. jsonPre wraps in .json-tree
{
  const r = api.jsonPre({ foo: 'bar' });
  assert(r._classes.has('json-tree'), '1a: jsonPre returns a .json-tree wrapper');
  assert(r.children.length > 0, '1b: wrapper has child nodes');
}

// 2. Object content is reachable via textContent and is structured (not raw stringify)
{
  const r = api.jsonPre({ foo: 'bar', n: 1 });
  const text = r.textContent;
  assert(text.includes('foo'), '2a: tree exposes the "foo" key');
  assert(text.includes('bar'), '2b: tree exposes the "bar" value');
  assert(text.includes('1'), '2c: tree exposes the numeric value');
  assert(!text.includes('JSON.stringify'), '2d: not falling back to raw stringify');
}

// 3. JSON-shaped strings are auto-parsed into a tree (the original bug)
{
  const r = api.jsonPre('{"answer":"yes","score":0.9}');
  const text = r.textContent;
  assert(text.includes('answer'), '3a: serialized JSON object string is parsed and exposes "answer"');
  assert(text.includes('yes'), '3b: parsed value "yes" is exposed');
  assert(text.includes('0.9'), '3c: parsed numeric value is exposed');
}

// 4. JSON-shaped array string is auto-parsed
{
  const r = api.jsonPre('[1,2,3]');
  assert(r.textContent.includes('[3]'), '4: serialized JSON array string is parsed');
}

// 5. Invalid JSON-looking string falls back to plain string render (no crash)
{
  const r = api.jsonPre('{not valid json');
  assert(r.textContent.includes('not valid json'), '5: invalid JSON falls back to string');
}

// 6. Multi-line strings use the multiline class so CSS preserves newlines
{
  const r = api.jsonPre('line1\nline2\nline3');
  assert(findClass(r, 'jt-multiline'), '6: multi-line string carries the jt-multiline class');
}

// 7. Arrays render with a length summary
{
  const r = api.jsonPre([1, 2, 3]);
  assert(r.textContent.includes('[3]'), '7: array shows length summary');
}

// 8. Nested structures render without crashing and preserve deep values
{
  const r = api.jsonPre({ a: { b: { c: [1, { d: 'deep' }] } } });
  assert(r.textContent.includes('deep'), '8: nested structure renders deep value');
}

// 9. null, boolean, number primitives render
{
  const r = api.jsonPre({ n: null, b: true, num: 42 });
  const text = r.textContent;
  assert(text.includes('null'), '9a: null is rendered');
  assert(text.includes('true'), '9b: boolean is rendered');
  assert(text.includes('42'), '9c: number is rendered');
}

// 10. Empty containers render compactly
{
  const r1 = api.jsonPre({});
  assert(r1.textContent.includes('{}'), '10a: empty object renders as {}');
  const r2 = api.jsonPre([]);
  assert(r2.textContent.includes('[]'), '10b: empty array renders as []');
}

// 11. The collapsible header has a click listener so the tree is interactive
{
  const r = api.jsonPre({ foo: 'bar' });
  function findListener(node) {
    if (node && node.listeners && Array.isArray(node.listeners.click)) return true;
    if (node && Array.isArray(node.children)) {
      for (const c of node.children) {
        if (findListener(c)) return true;
      }
    }
    return false;
  }
  assert(findListener(r), '11: collapsible header has a click handler');
}

// 12. Trace-shaped step.data with a nested JSON string is fully expanded
{
  const stepData = {
    name: 'search',
    args: '{"query":"weather","limit":5}',
    output: 'result1\nresult2',
  };
  const r = api.jsonPre(stepData);
  const text = r.textContent;
  assert(text.includes('query'), '12a: nested JSON string inside a field is parsed');
  assert(text.includes('weather'), '12b: nested JSON string value is exposed');
  assert(findClass(r, 'jt-multiline'), '12c: multi-line string field uses multiline class');
}

if (failures > 0) {
  console.error(failures + ' assertion(s) failed');
  process.exit(1);
}
console.log('All json-tree assertions passed (' + 12 + ' scenarios)');
