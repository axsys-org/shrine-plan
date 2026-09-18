// Exercise the shipped handler with a form whose named control shadows
// its action property, as browsers do for both select and input controls.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, 'codex_ui.foil'), 'utf8');
const script = JSON.parse(source.split('  + script\n    ^ nat\n    ')[1]);

async function check(kind) {
  let submit;
  const requests = [];
  const button = {disabled: false};
  const status = {textContent: ''};
  const form = {
    action: {toString: () => `[object HTML${kind}Element]`},
    getAttribute: name => name === 'action' ? '/post/0x11/io/codex' : null,
    matches: selector => selector === 'form',
    querySelector: selector => selector === 'button' ? button : null,
  };
  const fields = [['action', kind === 'Select' ? 'start' : 'reply'],
                  ['prompt', 'Keep this draft']];
  vm.runInNewContext(script, {
    document: {
      addEventListener: (name, handler) => { submit = handler; },
      getElementById: () => status,
    },
    FormData: class { constructor() { return fields; } },
    URLSearchParams,
    setInterval: () => {},
    fetch: async (url, options) => {
      requests.push({url, options});
      // Verify that errors also release the form and retain its fields.
      return {ok: false};
    },
  });
  await submit({target: form, preventDefault() {}});
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, '/post/0x11/io/codex');
  assert.equal(requests[0].options.method, 'POST');
  assert.equal(requests[0].options.body.get('action'), fields[0][1]);
  assert.equal(fields[1][1], 'Keep this draft');
  assert.equal(button.disabled, false);
  assert.match(status.textContent, /Submission failed/);
}
(async () => {
  await check('Select');
  await check('Input');
  console.log('PASS: composer and reply action shadowing; failure cleanup');
})().catch(error => { console.error(error); process.exitCode = 1; });
