const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../app/studio/web/app.js'), 'utf8');
const helper = source.slice(source.indexOf('let dangChonTep = false;'), source.indexOf('function bao('));

function setup() {
  const buttons = [false, false, true].map(disabled => ({
    disabled, attributes: {},
    setAttribute(k, v) { this.attributes[k] = v; },
    removeAttribute(k) { delete this.attributes[k]; },
  }));
  let resolve, reject;
  const response = new Promise((a, b) => { resolve = a; reject = b; });
  const state = { calls: [], statuses: [], removed: 0, messages: [] };
  const context = {
    document: { querySelectorAll() { return buttons; } },
    el: () => ({ remove() { state.removed++; } }),
    $: () => ({ append(node) { state.statuses.push(node); } }),
    bao: (message) => state.messages.push(message),
    api: async (route, body) => { state.calls.push({ route, body }); return response; },
  };
  vm.createContext(context);
  vm.runInContext(helper, context);
  return { context, buttons, state, resolve, reject };
}

test('Opening picker displays status and disables controls until a file is returned', async () => {
  const c = setup();
  const pending = c.context.chonTepMay('video');
  assert.equal(c.state.statuses.length, 1);
  assert.ok(c.buttons.every(b => b.disabled && b.attributes['aria-busy'] === 'true'));
  c.resolve({ tep: ['clip.mp4'], chi_tiet: [] });
  await pending;
  assert.deepEqual(c.buttons.map(b => b.disabled), [false, false, true]);
  assert.ok(c.buttons.every(b => !('aria-busy' in b.attributes)));
  assert.equal(c.state.removed, 1);
});

test('Repeated picker clicks do not spawn another native request', async () => {
  const c = setup();
  const pending = c.context.chonTepMay('video');
  await assert.rejects(c.context.chonTepMay('mau'), /đang mở/);
  assert.equal(c.state.calls.length, 1);
  c.resolve({ tep: [] });
  await pending;
});

test('Native picker errors remove waiting state and restore controls', async () => {
  const c = setup();
  const pending = c.context.chonTepMay('tat-ca');
  c.reject(new Error('Windows picker failed'));
  await assert.rejects(pending, /Windows picker failed/);
  assert.deepEqual(c.buttons.map(b => b.disabled), [false, false, true]);
  assert.equal(c.state.removed, 1);
});

test('Cancel returns normally and shows feedback', async () => {
  const c = setup();
  const pending = c.context.chonTepMay('audio');
  c.resolve({ tep: [] });
  await pending;
  assert.deepEqual(c.state.messages, ['Chưa chọn tệp.']);
});

function browserSetup(options = {}) {
  const state = { inputs: [], uploads: [], messages: [], apiCalls: 0 };
  const S = { dgTha: 'old-role' };
  const context = {
    S,
    document: {
      body: { append(input) { state.inputs.push(input); } },
      createElement() {
        const listeners = {};
        const input = {
          files: [], clicked: 0, removed: false,
          addEventListener(name, handler) { listeners[name] = handler; },
          click() { this.clicked++; if (options.blockClick) throw new Error('blocked'); },
          remove() { this.removed = true; },
          emit(name) { listeners[name]?.(); },
        };
        if (!options.noFolder) input.webkitdirectory = false;
        return input;
      },
    },
    taiLen(files) { state.uploads.push({ role: S.dgTha, files: files.map(f => f.name) }); },
    loaiTep: name => /\.(mp4|mov|mkv)$/i.test(name) ? 'video' : /\.png$/i.test(name) ? 'anh' : 'tai_lieu',
    bao(message) { state.messages.push(message); },
    api() { state.apiCalls++; throw new Error('Browser picker must not call server picker'); },
  };
  vm.createContext(context);
  vm.runInContext(helper, context);
  return { context, S, state };
}

test('Primary browser picker opens synchronously without a server round trip', () => {
  const c = browserSetup();
  const input = c.context.chonTepTrinhDuyet('video', 'chinh');
  assert.equal(input.clicked, 1);
  assert.equal(input.type, 'file');
  assert.equal(input.multiple, true);
  assert.match(input.accept, /video/);
  assert.equal(c.state.apiCalls, 0);
});

test('Main, material, and sample selections preserve their own role and restore prior state', () => {
  const c = browserSetup();
  for (const [kind, role] of [['video', 'chinh'], ['tat-ca', 'phu'], ['mau', 'mau']]) {
    const input = c.context.chonTepTrinhDuyet(kind, role);
    input.files = [{ name: 'clip.mp4' }];
    input.emit('change');
    assert.equal(c.state.uploads.at(-1).role, role);
    assert.equal(c.S.dgTha, 'old-role');
    assert.equal(input.removed, true);
    if (kind === 'mau') assert.equal(input.multiple, false);
  }
});

test('Delayed file selection keeps the role of its own picker', () => {
  const c = browserSetup();
  const main = c.context.chonTepTrinhDuyet('video', 'chinh');
  const sample = c.context.chonTepTrinhDuyet('mau', 'mau');
  sample.files = [{ name: 'sample.mp4' }]; sample.emit('change');
  main.files = [{ name: 'main.mp4' }]; main.emit('change');
  assert.deepEqual(c.state.uploads.map(x => x.role), ['mau', 'chinh']);
  assert.equal(c.S.dgTha, 'old-role');
});

test('Cancel cleans up the browser input without adding attachments', () => {
  const c = browserSetup();
  const input = c.context.chonTepTrinhDuyet('video', 'chinh');
  input.emit('cancel');
  assert.equal(input.removed, true);
  assert.equal(c.state.uploads.length, 0);
  assert.equal(c.S.dgTha, 'old-role');
});

test('Main video picker rejects an image instead of misclassifying it as main video', () => {
  const c = browserSetup();
  const input = c.context.chonTepTrinhDuyet('video', 'chinh');
  input.files = [{ name: 'picture.png' }]; input.emit('change');
  assert.equal(c.state.uploads.length, 0);
  assert.match(c.state.messages[0], /tệp video/);
  assert.equal(input.removed, true);
});

test('Folder picker selects directory contents as materials', () => {
  const c = browserSetup();
  const input = c.context.chonTepTrinhDuyet('thu-muc', 'phu');
  assert.equal(input.webkitdirectory, true);
  assert.equal(input.multiple, true);
  input.files = [{ name: 'clip.mp4' }, { name: 'notes.txt' }]; input.emit('change');
  assert.equal(c.state.uploads[0].role, 'phu');
  assert.equal(c.state.uploads[0].files.length, 2);
});

test('Unsupported directory picking gives a visible alternative', () => {
  const c = browserSetup({ noFolder: true });
  c.context.chonTepTrinhDuyet('thu-muc', 'phu');
  assert.equal(c.state.inputs.length, 0);
  assert.match(c.state.messages[0], /Thêm tư liệu/);
});

test('Browser picker failure cleans up and displays an error', () => {
  const c = browserSetup({ blockClick: true });
  const input = c.context.chonTepTrinhDuyet('video', 'chinh');
  assert.equal(input.removed, true);
  assert.match(c.state.messages[0], /blocked/);
});
