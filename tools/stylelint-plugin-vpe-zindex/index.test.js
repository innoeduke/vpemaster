'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const stylelint = require('stylelint');

const RULE = 'vpe/zindex-token';
const TOKENS_FILE = path.resolve(__dirname, '..', '..', 'tools', 'zindex-tokens.json');

async function lint(code, file = '/app/static/css/test.css') {
  const res = await stylelint.lint({
    code,
    codeFilename: file,
    config: {
      plugins: [path.resolve(__dirname, 'index.js')],
      rules: { [RULE]: [true, { tokensFile: TOKENS_FILE }] },
    },
  });
  return res.results[0];
}

test('var(--z-modal) is accepted', async () => {
  const r = await lint('.x { z-index: var(--z-modal); }');
  assert.equal(r.warnings.length, 0, JSON.stringify(r.warnings, null, 2));
});

test('auto is accepted', async () => {
  const r = await lint('.x { z-index: auto; }');
  assert.equal(r.warnings.length, 0);
});

test('raw integer is rejected', async () => {
  const r = await lint('.x { z-index: 1000; }');
  assert.equal(r.warnings.length, 1);
  assert.match(r.warnings[0].text, /raw integer/);
  assert.equal(r.warnings[0].rule, RULE);
});

test('raw negative integer is rejected', async () => {
  const r = await lint('.x { z-index: -1; }');
  assert.equal(r.warnings.length, 1);
  assert.match(r.warnings[0].text, /raw integer/);
});

test('unknown --z-* token is rejected', async () => {
  const r = await lint('.x { z-index: var(--z-not-a-token); }');
  assert.equal(r.warnings.length, 1);
  assert.match(r.warnings[0].text, /not a registered token/);
});

test('--z-debug in production file is rejected', async () => {
  const r = await lint('.x { z-index: var(--z-debug); }', '/app/static/css/chat.css');
  assert.equal(r.warnings.length, 1);
  assert.match(r.warnings[0].text, /reserved for development/);
});

test('--z-debug in *-dev.css is accepted', async () => {
  const r = await lint('.x { z-index: var(--z-debug); }', '/app/static/css/dev-overlay.css');
  assert.equal(r.warnings.length, 0);
});

test('--z-debug in debug*.css is accepted', async () => {
  const r = await lint('.x { z-index: var(--z-debug); }', '/app/static/css/debug-overlay.css');
  assert.equal(r.warnings.length, 0);
});

test('--z-debug in dev-*.css is accepted', async () => {
  const r = await lint('.x { z-index: var(--z-debug); }', '/app/static/css/dev-tools.css');
  assert.equal(r.warnings.length, 0);
});

test('all defined tokens are accepted', async () => {
  const tokens = require(TOKENS_FILE).tokens;
  for (const name of Object.keys(tokens)) {
    const r = await lint(`.x { z-index: var(--${name}); }`, '/app/static/css/test.css');
    if (name === 'z-debug') {
      assert.equal(r.warnings.length, 1, `expected --z-debug rejected in production, got: ${JSON.stringify(r.warnings)}`);
    } else {
      assert.equal(r.warnings.length, 0, `expected --${name} accepted, got: ${JSON.stringify(r.warnings)}`);
    }
  }
});

test('multiple declarations: only bad ones report', async () => {
  const code = `
    .a { z-index: var(--z-modal); }
    .b { z-index: 5000; }
    .c { z-index: var(--z-popover); }
    .d { z-index: 1; }
  `;
  const r = await lint(code);
  assert.equal(r.warnings.length, 2);
  assert.match(r.warnings[0].text, /5000/);
  assert.match(r.warnings[1].text, /raw integer/);
});

test('garbage value is rejected as invalid shape', async () => {
  const r = await lint('.x { z-index: nonsense; }');
  assert.equal(r.warnings.length, 1);
  assert.match(r.warnings[0].text, /not a recognised value/);
});

test('var() with non-z- prefix is rejected', async () => {
  const r = await lint('.x { z-index: var(--modal); }');
  assert.equal(r.warnings.length, 1);
  assert.match(r.warnings[0].text, /not a registered token/);
});
