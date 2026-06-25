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

test('all defined tokens are accepted in a permitted path', async () => {
  // With permittedPaths in place, every token must be accepted in at least one
  // permitted path. Use core/** (allowed for the app-chrome tokens) as the
  // common permitted location for everything that's allowed there, and use a
  // path inside themes/** for z-toast.
  const tokens = require(TOKENS_FILE).tokens;
  const permittedPaths = require(TOKENS_FILE).permittedPaths || {};
  for (const name of Object.keys(tokens)) {
    // Skip tokens with no registered path: this test verifies the token
    // exists; path-restriction is verified by the dedicated tests below.
    const paths = permittedPaths[name];
    if (!paths || paths.length === 0) {
      const r = await lint(`.x { z-index: var(--${name}); }`, '/app/static/css/test.css');
      if (name === 'z-debug') {
        assert.equal(r.warnings.length, 1, `expected --z-debug rejected in test file, got: ${JSON.stringify(r.warnings)}`);
      } else {
        assert.equal(r.warnings.length, 0, `expected --${name} accepted anywhere, got: ${JSON.stringify(r.warnings)}`);
      }
      continue;
    }
    // Pick the first permitted path. Strip any leading `**/` for the fake
    // code filename, since absolute test paths can have a leading slash.
    const samplePath = '/' + paths[0].replace(/^\*\*\//, '').replace(/\/\*\*$/, '/sample.css');
    const r = await lint(`.x { z-index: var(--${name}); }`, samplePath);
    assert.equal(
      r.warnings.length,
      0,
      `expected --${name} accepted at ${samplePath}, got: ${JSON.stringify(r.warnings)}`
    );
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

// --- permittedPaths tier discipline (added 2026-06) ------------------------

test('--z-app in core is accepted (default permittedPaths)', async () => {
  const r = await lint('.x { z-index: var(--z-app); }', '/app/static/css/core/navigation.css');
  assert.equal(r.warnings.length, 0);
});

test('--z-app in pages is rejected (wrong tier)', async () => {
  const r = await lint('.x { z-index: var(--z-app); }', '/app/static/css/pages/agenda/agenda-base.css');
  assert.equal(r.warnings.length, 1);
  // Must report the new tier-discipline "not permitted" message.
  assert.match(r.warnings[0].text, /not permitted/);
  assert.equal(r.warnings[0].rule, RULE);
});

test('--z-app-mid in core is accepted', async () => {
  const r = await lint('.x { z-index: var(--z-app-mid); }', '/app/static/css/core/responsive.css');
  assert.equal(r.warnings.length, 0);
});

test('--z-app-mid in components is rejected', async () => {
  const r = await lint('.x { z-index: var(--z-app-mid); }', '/app/static/css/components/date_range_picker.css');
  assert.equal(r.warnings.length, 1);
  assert.match(r.warnings[0].text, /not permitted/);
});

test('--z-app-high in core is accepted', async () => {
  const r = await lint('.x { z-index: var(--z-app-high); }', '/app/static/css/core/navigation.css');
  assert.equal(r.warnings.length, 0);
});

test('--z-app-high in pages is rejected', async () => {
  const r = await lint('.x { z-index: var(--z-app-high); }', '/app/static/css/pages/uploads.css');
  assert.equal(r.warnings.length, 1);
  assert.match(r.warnings[0].text, /not permitted/);
});

test('--z-toast in components is accepted', async () => {
  const r = await lint('.x { z-index: var(--z-toast); }', '/app/static/css/components/forms.css');
  assert.equal(r.warnings.length, 0);
});

test('--z-toast in themes is accepted', async () => {
  const r = await lint('.x { z-index: var(--z-toast); }', '/app/static/css/themes/christmas_theme.css');
  assert.equal(r.warnings.length, 0);
});

test('--z-toast in pages is rejected', async () => {
  const r = await lint('.x { z-index: var(--z-toast); }', '/app/static/css/pages/agenda/agenda-base.css');
  assert.equal(r.warnings.length, 1);
  assert.match(r.warnings[0].text, /not permitted/);
});

test('unrestricted tokens (z-popover, z-sticky-high) accept any path', async () => {
  for (const tok of ['z-popover', 'z-popover-mid', 'z-sticky', 'z-sticky-high', 'z-inline', 'z-inline-high']) {
    const r = await lint(`.x { z-index: var(--${tok}); }`, '/app/static/css/pages/agenda/agenda-base.css');
    assert.equal(r.warnings.length, 0, `${tok} should be allowed in pages/ — got: ${JSON.stringify(r.warnings)}`);
  }
});

test('path comparison works with repo-relative patterns', async () => {
  // The plugin should accept paths that, after stripping the cwd prefix,
  // match the pattern in the tokens file.
  const cwd = process.cwd();
  const r = await lint(
    '.x { z-index: var(--z-app); }',
    `${cwd}/app/static/css/core/navigation.css`
  );
  assert.equal(r.warnings.length, 0);
});

test('message template uses --${name} not --z-${name} (avoids double prefix)', async () => {
  const r = await lint('.x { z-index: var(--z-app); }', '/app/static/css/pages/agenda/agenda-base.css');
  assert.equal(r.warnings.length, 1);
  // Must reference the token by its full CSS form: var(--z-app), not var(--z-z-app).
  assert.match(r.warnings[0].text, /var\(--z-app\)/);
  assert.doesNotMatch(r.warnings[0].text, /var\(--z-z-app\)/);
});
