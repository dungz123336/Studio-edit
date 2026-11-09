const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../app/studio/web/app.js'), 'utf8');
const health = source.slice(source.indexOf('function tinhTrangMay('), source.indexOf('function veTrai('));
const banner = source.slice(source.indexOf('function veBangBao('), source.indexOf('async function tuSua('));
const left = source.slice(source.indexOf('function veTrai('), source.indexOf('function chuTren('));

function setup(checks, extra = {}) {
  const nodes = new Map();
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {
      hidden: false, className: '', textContent: '', innerHTML: '', dataset: {},
      classList: { values: {}, toggle(k, v) { this.values[k] = v; } },
      replaceChildren() {}, addEventListener() {},
    });
    return nodes.get(id);
  };
  const context = {
    S: {
      tq: { bac_si: { kq: checks, ...extra }, ho_so: [],
        he_thong: { ban_quyen: { hop_le: true, chu: '' }, da_cai: true, phien_ban: '1.2.21' },
        dong_co: { san_sang: true, da_kiem: true } },
      tatCa: [], view: 'ho-so',
    },
    $: node,
    dangChay: () => ({}),
    chuBQ: s => s,
    esc: s => s,
    nutGui() {},
    khoaChat: () => false,
    kichHoat() {}, tuSua() {}, dangNhapClaude() {}, capNhatNgay() {}, kiemLaiGiaHan() {},
  };
  vm.createContext(context);
  vm.runInContext(health + left + banner, context);
  return { context, nodes, node };
}

const ready = { ma: 'ffmpeg', ten: 'ffmpeg', ok: true, bat_buoc: true, sua_duoc: true };
const benchmark = { ma: 'chuan_may', ten: 'Đo tốc độ máy', ok: false, bat_buoc: false, sua_duoc: true };

test('Optional benchmark keeps the machine ready and does not show a repair alarm', () => {
  const c = setup([ready, benchmark]);
  c.context.veTrai();
  assert.equal(c.node('#chamMay').className, 'cham tot');
  assert.equal(c.node('#chuMay').textContent, 'Máy ổn · 1 mục tuỳ chọn');
  c.context.S.tq.ho_so = [{}];
  c.context.veBangBao();
  assert.equal(c.node('#bangBao').hidden, true);
  assert.equal(c.node('#bangBao').classList.values.do, false);
  assert.equal(c.node('#bangBao').innerHTML, '');
});

test('Required failure stays red and offers repair', () => {
  const c = setup([{ ...ready, ok: false }, benchmark]);
  c.context.veTrai();
  assert.equal(c.node('#chamMay').className, 'cham xau');
  assert.equal(c.node('#chuMay').textContent, 'Máy: 1 chỗ cần sửa');
  c.context.S.tq.ho_so = [{}];
  c.context.veBangBao();
  assert.equal(c.node('#bangBao').classList.values.do, true);
  assert.match(c.node('#bangBao').innerHTML, /Máy còn 1 chỗ cần sửa/);
  assert.match(c.node('#bangBao').innerHTML, /ffmpeg/);
  assert.doesNotMatch(c.node('#bangBao').innerHTML, /Đo tốc độ máy/);
});

test('Older diagnostics without an optional flag still expose required failures', () => {
  const c = setup([{ ten: 'Thư viện Python', ok: false, sua_duoc: true }]);
  const status = c.context.tinhTrangMay(c.context.S.tq.bac_si);
  assert.equal(status.cham, 'xau');
  assert.equal(status.hong.length, 1);
});

test('Checking is shown as pending even when previous results exist', () => {
  const c = setup([ready, benchmark], { dang_kiem: true });
  c.context.veTrai();
  assert.equal(c.node('#chamMay').className, 'cham cho');
  assert.equal(c.node('#chuMay').textContent, 'Đang kiểm tra máy…');
});

test('Repair progress remains visible without a red failure alarm', () => {
  const c = setup([ready, benchmark], { dang_sua: true, log: ['Đang chuẩn bị'] });
  c.context.veTrai();
  assert.equal(c.node('#chamMay').className, 'cham cho');
  assert.equal(c.node('#chuMay').textContent, 'Đang tự sửa máy…');
  c.context.S.tq.ho_so = [{}];
  c.context.veBangBao();
  assert.equal(c.node('#bangBao').hidden, false);
  assert.equal(c.node('#bangBao').classList.values.do, false);
  assert.match(c.node('#bangBao').innerHTML, /Đang chuẩn bị/);
});

test('Optional diagnostics do not hide an unrelated Claude setup failure', () => {
  const c = setup([ready, benchmark]);
  c.context.S.tq.ho_so = [{}];
  c.context.S.tq.dong_co = { da_kiem: true, san_sang: false, ly_do: 'chưa đăng nhập' };
  c.context.veBangBao();
  assert.equal(c.node('#bangBao').classList.values.do, true);
  assert.match(c.node('#bangBao').innerHTML, /Claude chưa sẵn sàng/);
  assert.doesNotMatch(c.node('#bangBao').innerHTML, /Đo tốc độ máy/);
});

test('Empty diagnostic state does not claim all checks passed', () => {
  assert.equal(setup([]).context.tinhTrangMay(null).chu, 'Chưa kiểm tra máy');
});

function errorRenderer() {
  const code = source.slice(source.indexOf('function chuLoiDeDoc('), source.indexOf('function veTroChuyen('));
  const context = { el: (tag, attributes, ...children) => ({ tag, attributes, children }) };
  vm.createContext(context);
  vm.runInContext(code, context);
  return context;
}

test('Historical API 522 payloads show a short explanation with collapsed original details', () => {
  const c = errorRenderer();
  const original = 'API Error: 522 ' + JSON.stringify({ error: { message: 'timeout ' + 'x'.repeat(10000) } });
  const message = { vai: 'loi', noi_dung: original };
  const rendered = c.theLoi(message);
  assert.match(rendered.children[0].children[0], /^Máy chủ API đang dùng không phản hồi \(HTTP 522\)/);
  assert.ok(rendered.children[0].children[0].length < 150);
  const details = rendered.children[1];
  assert.equal(details.tag, 'details');
  assert.equal(details.attributes.open, undefined);
  assert.equal(details.children[1].children[0], original);
  assert.match(details.children[1].attributes.style, /overflow-wrap:anywhere/);
  assert.equal(message.noi_dung, original);
});

test('Explicit HTTP and structured 522 statuses receive the same short explanation', () => {
  const c = errorRenderer();
  for (const text of ['HTTP 522: upstream timeout', 'HTTP522', '{"status":522,"message":"timeout"}', '{"status_code":"522"}', '{"statusCode": 522}']) {
    assert.match(c.chuLoiDeDoc(text), /^Máy chủ API đang dùng không phản hồi/, text);
  }
});

test('Authentication failures and unrelated messages retain their exact text', () => {
  const c = errorRenderer();
  for (const text of ['API Error: 401 invalid API key', 'HTTP 403: access denied', 'Claude gặp lỗi', 'Usage limit reached']) {
    assert.equal(c.chuLoiDeDoc(text), text);
    assert.deepEqual(c.theLoi({ noi_dung: text }).children, [text]);
  }
});

test('Unrelated numeric references are not misread as an HTTP 522 failure', () => {
  const c = errorRenderer();
  for (const text of ['Đã đọc 522 khung hình', 'Mã dự án 1522', 'API Error: 5223', '{"status":5223}', '{"status":"522x"}']) {
    assert.equal(c.chuLoiDeDoc(text), text);
  }
});
