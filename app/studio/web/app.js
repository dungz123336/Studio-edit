// © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
// Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
// Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"use strict";
/* Studio — bàn làm việc. Não + quy trình nằm trong skill; Studio chỉ hiện, chuyển lời, cho người kéo tài nguyên. */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
function el(tag, at = {}, ...con) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(at)) {
    if (v == null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k === "style") n.style.cssText = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of con.flat(Infinity)) if (c != null && c !== false) n.append(c.nodeType ? c : String(c));
  return n;
}
const media = (p, v) => `/media?p=${encodeURIComponent(p)}${v ? "&v=1" : ""}`;
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pad = (n) => String(Math.floor(n)).padStart(2, "0");
const mmss = (s) => `${Math.floor(s / 60)}:${pad(s % 60)}`;
const tenFile = (p) => (p || "").split(/[\\/]/).pop();
function gio(ts) { const d = new Date(ts * 1000); return `${pad(d.getHours())}:${pad(d.getMinutes())} · ${d.getDate()}/${d.getMonth() + 1}`; }
function luc(ts) {
  const d = (Date.now() / 1000 - ts);
  if (d < 60) return "vừa xong";
  if (d < 3600) return `${Math.floor(d / 60)} phút`;
  if (d < 86400) return `${Math.floor(d / 3600)} giờ`;
  const t = new Date(ts * 1000); return `${t.getDate()}/${t.getMonth() + 1}`;
}
const nho = { lay: (k, m) => { try { return localStorage.getItem(k) ?? m; } catch { return m; } }, dat: (k, v) => { try { localStorage.setItem(k, v); } catch {} } };

async function api(duong, body) {
  const r = await fetch(duong, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.loi || `lỗi ${r.status}`);
  return j;
}
let dangChonTep = false;
async function chonTepMay(loai) {
  if (dangChonTep) throw new Error("Hộp chọn tệp đang mở. Chọn tệp hoặc bấm Huỷ trong hộp đó trước.");
  dangChonTep = true;
  const nuts = [...document.querySelectorAll("[data-chon],#nutKem,#nutThuMuc,#nutMau,#giongMau")].map((n) => [n, n.disabled]);
  const trang = el("div", { role: "status" }, "Đang mở hộp chọn tệp của Windows… Nếu chưa thấy, kiểm tra cửa sổ chọn tệp trên thanh tác vụ.");
  nuts.forEach(([n]) => { n.disabled = true; n.setAttribute("aria-busy", "true"); });
  $("#thongBao").append(trang);
  try {
    const r = await api("/api/chon-tep", { loai });
    if (!(r.tep || []).length) bao("Chưa chọn tệp.");
    return r;
  } finally {
    dangChonTep = false;
    trang.remove();
    nuts.forEach(([n, disabled]) => { n.disabled = disabled; n.removeAttribute("aria-busy"); });
  }
}
function chonTepTrinhDuyet(loai = "tat-ca", muc = "") {
  const input = document.createElement("input");
  input.type = "file";
  input.hidden = true;
  input.accept = ["video", "mau"].includes(loai) ? "video/*,.mkv,.mts,.insv" : loai === "audio" ? "audio/*,.mp3,.wav,.m4a,.aac,.ogg"
    : "video/*,image/*,audio/*,.mkv,.mts,.insv,.xlsx,.xls,.docx,.pptx,.csv,.tsv,.txt,.md,.srt,.vtt,.rtf,.pdf,.cube,.3dl,.ttf,.otf";
  input.multiple = loai !== "mau" && loai !== "audio";
  if (loai === "thu-muc") {
    if (!("webkitdirectory" in input)) { bao("Trình duyệt này chưa chọn được cả thư mục. Bấm Thêm tư liệu để chọn các tệp.", true); return; }
    input.webkitdirectory = true;
    input.multiple = true;
  }
  const dong = () => input.remove();
  input.addEventListener("cancel", dong, { once: true });
  input.addEventListener("change", () => {
    const truoc = S.dgTha;
    try {
      const files = [...(input.files || [])];
      if (!files.length) return;
      const nhan = ["video", "mau"].includes(loai) ? files.filter((f) => loaiTep(f.name) === "video") : files;
      if (!nhan.length) { bao("Ô này nhận tệp video. Chọn .mp4, .mov, .mkv hoặc định dạng video khác.", true); return; }
      if (["chinh", "phu", "mau"].includes(muc)) S.dgTha = muc;
      else if (loai === "mau") S.dgTha = "mau";
      taiLen(nhan);
    } finally {
      S.dgTha = truoc;
      dong();
    }
  }, { once: true });
  document.body.append(input);
  try { input.click(); } // Phải nằm trong lần bấm của người dùng, trước mọi await/fetch.
  catch (loi) { dong(); bao("Không mở được hộp chọn tệp: " + loi.message, true); }
  return input;
}
function bao(chu, loi = false) {
  const n = el("div", { class: loi ? "loi" : "" }, chu);
  $("#thongBao").append(n); setTimeout(() => n.remove(), 3200);
}
function datMau(hex) {
  if (!/^#[0-9a-f]{6}$/i.test(hex || "")) hex = "#FFD200";
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  const L = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  document.documentElement.style.setProperty("--nhan", hex);
  document.documentElement.style.setProperty("--nhan-chu", L > 0.55 ? "#141518" : "#ffffff");
}
const viTat = (s) => { const w = (s || "?").replace(/^kênh\s+/i, "").trim().split(/\s+/); return ((w[0]?.[0] || "") + (w[1]?.[0] || "")).toUpperCase() || "?"; };

/* ---------- trạng thái ---------- */
const S = {
  tq: null, kd: null, hs: nho.lay("hs", ""), viec: nho.lay("viec", "") || null, tatCa: [], moc: {}, viecData: null,
  view: "chat", hsData: null, hsThe: "thuong-hieu", phai: "quy-trinh", kho: { loai: "hieu_ung", q: "", trang: 0, ds: [], tong: 0 },
  dinh: [], moNhom: new Set(), guiCho: false, daChao: false,
};
const hoSo = (ma) => S.tq?.ho_so.find((h) => h.ten === ma);

/* ---------- vòng lấy dữ liệu ---------- */
async function lay() {
  let tq;
  try { tq = await api(`/api/tong-quan?viec=${S.viec || ""}`); } catch { $("#chuCL").textContent = "Mất kết nối Studio"; $("#chamCL").className = "cham xau"; return; }
  const cuMoc = S.moc; S.tq = tq; S.moc = tq.moc_viec;
  if (!S.hs || !hoSo(S.hs)) { S.hs = tq.ho_so[0]?.ten || ""; nho.dat("hs", S.hs); }
  datMau(hoSo(S.hs)?.mau);
  const doiViec = JSON.stringify(cuMoc) !== JSON.stringify(S.moc);
  if (doiViec) {
    S.tatCa = await api("/api/viec").catch(() => S.tatCa);
    if (S.viec && cuMoc[S.viec] !== S.moc[S.viec]) await layViec();
  }
  if (S.viec && !S.tatCa.some((v) => v.id === S.viec)) { S.viec = null; S.viecData = null; nho.dat("viec", ""); }
  veTrai(); veDauGiua(); veDoLuong(); veBangBao(); veDangLam();
  if (S.phai === "quy-trinh") veQuyTrinh();
  if (doiViec || !S.daVe) { veTroChuyen(); S.daVe = true; }
}
async function layViec() {
  if (!S.viec) { S.viecData = null; return; }
  try { S.viecData = await api(`/api/viec/${S.viec}`); } catch { S.viecData = null; }
}

/* ---------- TRÁI ---------- */
const dangChay = () => S.tq?.dong_co?.dang_chay || (S.tq?.dong_co?.viec_chay ? { [S.tq.dong_co.viec_chay]: { bat_dau: S.tq.dong_co.bat_dau } } : {});
const viecChay = (vid) => !!dangChay()[vid];
function tinhTrangMay(bs = {}) {
  bs = bs || {};
  const kq = bs.kq || [];
  const hong = kq.filter((x) => x.ok === false && x.bat_buoc !== false);
  const tuyChon = kq.filter((x) => x.ok === false && x.bat_buoc === false);
  const cham = bs.dang_sua || bs.dang_kiem ? "cho" : !kq.length ? "" : hong.length ? "xau" : "tot";
  const chu = bs.dang_sua ? "Đang tự sửa máy…" : bs.dang_kiem ? "Đang kiểm tra máy…" : !kq.length ? "Chưa kiểm tra máy"
    : hong.length ? `Máy: ${hong.length} chỗ cần sửa` : tuyChon.length ? `Máy ổn · ${tuyChon.length} mục tuỳ chọn` : `Máy ổn · ${kq.length}/${kq.length} mục`;
  return { kq, hong, tuyChon, cham, chu };
}
function veTrai() {
  const dc = S.tq.dong_co, dch = dangChay(), soChay = Object.keys(dch).length, chay = soChay > 0;
  const ds = $("#dsHoSo");
  ds.replaceChildren(...S.tq.ho_so.map((h) => {
    const chon = h.ten === S.hs;
    const viecHs = S.tatCa.filter((v) => v.ho_so === h.ten);
    const hang = el("button", { class: "hs-hang" + (chon ? " chon" : ""), type: "button", onclick: () => chonHoSo(h.ten) },
      el("span", { class: "hs-o", style: `background:${h.mau};color:${chuTren(h.mau)}` }, viTat(h.kenh)),
      el("span", { class: "ten" }, h.kenh, el("span", { class: "phu" }, h.ten)),
      S.tatCa.some((v) => v.ho_so === h.ten && dch[v.id]) ? el("i", { class: "lam", title: "Claude đang làm" }) : el("span", { class: "dem" }, viecHs.length || ""));
    if (!chon) return hang;
    const vds = el("div", { class: "ds-viec" },
      viecHs.slice(0, 40).map((v) => el("button", { class: "viec-hang" + (v.id === S.viec && S.view === "chat" ? " chon" : ""), type: "button", title: v.ten, onclick: () => chonViec(v.id) },
        dch[v.id] ? el("i") : null, el("span", { class: "t" }, v.ten), v.cho && !dch[v.id] ? el("span", { class: "loai cho" }, "chờ bạn") : v.loai === "hoc" ? el("span", { class: "loai" }, "học") : null)),
      el("button", { class: "them", type: "button", onclick: () => moHoSo() }, "Hồ sơ, gu, học từ video →"));
    return [hang, vds];
  }).flat());
  // chân: bản quyền + Claude Code
  const ht = S.tq.he_thong, bq = ht.ban_quyen || {};
  $("#chamBQ").className = "cham " + (bq.hop_le ? "tot" : "xau");
  $("#chuBQ").textContent = bq.hop_le ? `Bản quyền · ${chuBQ(bq.chu)}` : "Chưa kích hoạt bản quyền";
  $("#chamCL").className = "cham " + (dc.san_sang ? (chay ? "cho" : "tot") : (dc.da_kiem ? "xau" : ""));
  $("#chuCL").textContent = dc.san_sang ? (chay ? `Claude đang làm ${soChay} việc` : "Claude sẵn sàng") : (dc.da_kiem ? dc.ly_do : "Đang kiểm tra Claude Code");
  $("#chuPB").textContent = "v" + ht.phien_ban + (ht.cap_nhat?.co_moi ? " · có bản mới" : "");
  // 1.2.21 (1h): ổ chứa dự án < 10 GB (hoặc ngưỡng cài đặt) → dòng đỏ ở chân cột trái
  const od = ht.o_dia || {}, nguong = Math.max(10, +ht.o_trong_toi_thieu_gb || 10), thap = od.trong_gb != null && od.trong_gb < nguong;
  $("#dongO").hidden = !thap;
  if (thap) $("#chuO").textContent = `Ổ dự án chỉ còn ${od.trong_gb} GB — bấm để dọn`;
  const may = tinhTrangMay(S.tq.bac_si);
  $("#chamMay").className = "cham " + may.cham;
  $("#chuMay").textContent = may.chu;
}
function chuTren(hex) {
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.55 ? "#141518" : "#fff";
}
function chonHoSo(ma) {
  if (ma === S.hs && S.view === "chat") return;
  S.hs = ma; nho.dat("hs", ma);
  const cuoi = S.tatCa.find((v) => v.ho_so === ma);
  S.view = "chat"; S.hsData = null;
  chonViec(cuoi?.id || null);
}
async function chonViec(id) {
  S.viec = id; nho.dat("viec", id || ""); S.view = "chat"; S.moNhom.clear();
  await layViec();
  datMau(hoSo(S.hs)?.mau);
  hienView(); veTrai(); veDauGiua(); veTroChuyen(); veDangLam(); veQuyTrinh();
  if (!id) $("#o").focus({ preventScroll: true });
}
async function viecMoi() {
  const nut = $("#nutViecMoi");
  if (nut.disabled) return;
  nut.disabled = true;
  try {
    if (!S.tq) await lay();
    if (!S.tq) throw new Error("Chưa kết nối được Studio. Vui lòng thử lại.");
    if (!S.tq.ho_so.length) { moTao(); return; }
    if (!hoSo(S.hs)) S.hs = S.tq.ho_so[0].ten;
    if (S.dinh.some((d) => d.xhr)) throw new Error("Đợi tải file xong rồi tạo việc mới.");
    const v = await api("/api/viec", { ho_so: S.hs });
    S.tatCa = [v, ...S.tatCa.filter((x) => x.id !== v.id)];
    // Giữ phần đang soạn để người dùng có thể chuyển nó sang việc mới.
    S.guiCho = false;
    await chonViec(v.id);
    o.focus();
    bao("Đã tạo việc mới — nhập yêu cầu hoặc thêm video để bắt đầu");
  } catch (e) { bao(e.message, true); }
  finally { nut.disabled = false; }
}
$("#nutViecMoi").addEventListener("click", viecMoi);
addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "n") { e.preventDefault(); viecMoi(); }
  if (e.key === "Escape") { $("#xemLon").hidden = true; if ($("#khung").classList.contains("kho-rong")) khoRong(false); }
});

/* ---------- GIỮA: đầu ---------- */
function hienView() {
  $("#troChuyen").hidden = S.view !== "chat";
  $("#hoSo").hidden = S.view !== "ho-so";
}
function veDauGiua() {
  const h = hoSo(S.hs);
  $("#dauKenh").textContent = h ? h.kenh : "Studio";
  const o = $("#dauTen");
  if (document.activeElement !== o) o.value = S.view === "ho-so" ? "Hồ sơ kênh" : (S.viecData?.ten || "Việc mới");
  o.disabled = S.view !== "chat" || !S.viec;
}
$("#dauTen").addEventListener("change", (e) => { if (S.viec) api(`/api/viec/${S.viec}/doi-ten`, { ten: e.target.value }).catch((x) => bao(x.message, true)); });
$("#dauTen").addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.blur(); });
$("#nutXoaViec").addEventListener("click", () => {
  if (!S.viec) return;
  const ten = $("#dauTen").value || "đoạn chat này", d = $("#hopXoa");
  $("#xoaMo").textContent = `“${ten}” — đoạn chat bị xoá (Claude đang làm thì dừng). Không tích ô dưới thì video đã giao và thư mục dự án vẫn giữ nguyên.`;
  $("#xoaDuAn").checked = false;
  d.showModal();
});
$("#xoaHuy").addEventListener("click", () => $("#hopXoa").close("huy"));
$("#hopXoa form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const vid = S.viec, xoaDA = $("#xoaDuAn").checked; $("#hopXoa").close("ok");
  if (!vid) return;
  try {
    const r = await api(`/api/viec/${vid}/xoa`, { xoa_du_an: xoaDA });   // 1.2.21: xoá kèm thư mục dự án + bản tải lên + nhật ký + phiếu
    const dx = r.da_xoa;
    bao(dx ? `Đã xoá đoạn chat và ${(dx.xoa_mb / 1000).toFixed(1)} GB dữ liệu của việc (${dx.so_muc} mục${dx.loi?.length ? `, ${dx.loi.length} mục chưa xoá được` : ""})` : "Đã xoá đoạn chat");
    S.viec = null; S.moc = {}; await lay(); chonViec(null);
  } catch (x) { bao(x.message, true); }
});
$("#nutDung").addEventListener("click", () => api(`/api/viec/${S.viec}/dung`, {}).catch((x) => bao(x.message, true)));
$("#nutDung2").addEventListener("click", () => $("#nutDung").click());
$("#nutMoHoSo").addEventListener("click", () => (S.view === "ho-so" ? dongHoSo() : moHoSo()));
$("#nutPhai").addEventListener("click", () => {
  const k = $("#khung");
  if (k.classList.contains("kho-rong")) { khoRong(false); return; }
  if (innerWidth <= 1020) k.classList.toggle("mo-phai"); else { k.classList.toggle("an-phai"); nho.dat("anPhai", k.classList.contains("an-phai") ? "1" : ""); }
});
if (nho.lay("anPhai", "")) $("#khung").classList.add("an-phai");

function veBangBao() {
  const b = $("#bangBao"), ht = S.tq.he_thong, dc = S.tq.dong_co;
  let h = "", do_ = false;
  const bs = S.tq.bac_si || {}, hong = tinhTrangMay(bs).hong.filter((x) => x.sua_duoc);
  if (bs.dang_sua) h = `<p><b>Đang tự sửa máy…</b> Studio đang cài và sửa những gì còn thiếu, có thể mất vài phút. Cứ để cửa sổ mở.</p><pre class="nhat-ky-sua">${esc((bs.log || []).slice(-8).join("\n") || "Bắt đầu…")}</pre>`;
  else if (hong.length) { do_ = true; h = `<p><b>Máy còn ${hong.length} chỗ cần sửa</b> — ${hong.map((x) => esc(x.ten)).join(" · ")}.</p><p>Bấm nút dưới, Studio tự cài và sửa giúp bạn (ffmpeg, thư viện Python, kho…). Không cần biết code.</p><form id="formSua"><button class="nut nut-chinh">Tự sửa tất cả</button></form>`; }
  else if (ht.ban_quyen && !ht.ban_quyen.hop_le && ht.ban_quyen.loai === "toan-ven") { do_ = true; h = `<p><b>Bộ cài đã bị thay đổi</b> — vì an toàn, Studio tạm khoá. ${esc(ht.ban_quyen.chu || "")}.</p><p>Hãy <b>cài lại Studio</b> từ link trong thư giao hàng (hồ sơ kênh, bài đã học của bạn được giữ nguyên), hoặc nhắn Zalo người bán.</p>`; }
  else if (ht.ban_quyen && !ht.ban_quyen.hop_le && ht.ban_quyen.loai === "het-han") { do_ = true; const link = esc(ht.ban_quyen.chu && /^https?:\/\//.test(ht.ban_quyen.chu) ? ht.ban_quyen.chu : "https://aizening.com/skill/edit-video/gia-han"); h = `<p><b>Gói tháng đã hết hạn</b> — gia hạn để chat/dựng tiếp. Hồ sơ kênh và bài đã học của bạn được giữ nguyên.</p><p><a class="nut nut-chinh" href="${link}" target="_blank" rel="noopener">Gia hạn ngay</a> &nbsp; <button class="nut" id="nutKiemLai" type="button">Tôi đã gia hạn — kiểm lại</button></p>`; }
  else if (ht.ban_quyen && !ht.ban_quyen.hop_le) { do_ = true; h = `<p><b>Chưa kích hoạt bản quyền</b> — chưa nhập mã thì chưa chat/dựng được. Nhập mã trong thư giao hàng (dạng EV123456-XXXX-XXXX-XXXX):</p><form id="formBQ"><input id="oBQ" placeholder="EV123456-XXXX-XXXX-XXXX" aria-label="Mã bản quyền"><button class="nut nut-chinh">Kích hoạt</button></form>`; }
  else if (!S.tq.ho_so.length) h = `<p><b>Chưa có hồ sơ kênh nào.</b> Mỗi kênh một hồ sơ (màu, font, gu). Bấm <b>Tạo hồ sơ kênh</b> ở cột trái để bắt đầu.</p>`;
  else if (!ht.da_cai) { do_ = true; h = `<p><b>Skill chưa cài xong.</b> Mở PowerShell, chạy: <code>py %USERPROFILE%\\.claude\\skills\\tro-ly-edit-video\\scripts\\cai_dat.py</code></p>`; }
  else if (dc.da_kiem && !dc.san_sang) { do_ = true; h = `<p><b>Claude chưa sẵn sàng</b> — ${esc(dc.ly_do)}.</p><p>Bấm nút dưới: Studio mở cửa sổ Claude (tự cài nếu máy chưa có). Đăng nhập bằng <b>đúng tài khoản Claude Pro/Max</b> của bạn — nếu trình duyệt không tự mở, bấm phím <code>c</code> để chép link, dán vào trình duyệt, chép mã về dán vào cửa sổ, Enter. Studio tự nhận sau khoảng 15 giây.</p><form id="formDN"><button class="nut nut-chinh">${/chưa có/.test(dc.ly_do) ? "Cài & đăng nhập Claude" : "Đăng nhập Claude"}</button></form>`; }
  else if (ht.cap_nhat?.co_moi) {
    const chay = !!dc.viec_chay, bb = !!ht.cap_nhat.bat_buoc;
    do_ = bb;
    h = `<p><b>${bb ? "Bắt buộc cập nhật" : "Có bản mới"} ${esc(ht.cap_nhat.ban || "")}</b> — ${bb ? "Studio tạm khoá gửi việc tới khi lên bản mới (mọi máy phải dùng cùng một bản để người bán hỗ trợ được)." : "tính năng mới và bản sửa lỗi."} Hồ sơ kênh, bài đã học, cấu hình máy giữ nguyên.${chay ? " Claude đang làm việc: đợi xong rồi cập nhật." : ""}</p><form id="formCN"><button class="nut nut-chinh"${chay ? " disabled" : ""}>Cập nhật ngay</button></form>`;
    if (bb && !chay && !S.daBaoCN) { S.daBaoCN = true; setTimeout(hopEpCapNhat, 400); }   // 1.2.19 (Thêm 5): hộp thoại hiện hẳn giữa màn hình
  }
  b.hidden = !h; b.classList.toggle("do", do_);
  if (b.dataset.h !== h) {
    b.innerHTML = h; b.dataset.h = h;
    $("#formBQ")?.addEventListener("submit", kichHoat);
    $("#formSua")?.addEventListener("submit", tuSua);
    $("#formDN")?.addEventListener("submit", (e) => { e.preventDefault(); dangNhapClaude(); });
    $("#formCN")?.addEventListener("submit", capNhatNgay);
    $("#nutKiemLai")?.addEventListener("click", kiemLaiGiaHan);
  }
  if (S.view === "chat") { nutGui(); const o = $("#o"); if (o && khoaChat()) o.placeholder = lyDoKhoa(); }
}
async function tuSua(e) {
  e?.preventDefault?.();
  try { await api("/api/bac-si/sua", {}); bao("Studio đang tự sửa máy"); S.tq.bac_si = { ...(S.tq.bac_si || {}), dang_sua: true, log: [] }; veBangBao(); }
  catch (x) { bao(x.message, true); }
}
async function kiemLaiGiaHan(e) {
  const nut = e.target; nut.disabled = true; nut.textContent = "Đang kiểm…";
  try { const r = await api("/api/nhip", {}); bao(r.ok ? "Đã gia hạn — mời bạn tiếp tục" : "Chưa thấy gia hạn, thử lại sau ít phút", !r.ok); lay(); }
  catch (x) { bao(x.message, true); }
  nut.disabled = false; nut.textContent = "Tôi đã gia hạn — kiểm lại";
}
async function kichHoat(e) {
  e.preventDefault();
  const o = e.target.querySelector("input"), ma = o.value.trim(); if (!ma) return;
  const nut = e.target.querySelector("button"); nut.disabled = true; nut.textContent = "Đang kích hoạt…";
  try {
    const r = await api("/api/kich-hoat", { ma });
    bao(r.ok ? "Đã kích hoạt bản quyền" : (r.chu || "Không kích hoạt được").split("\n").pop(), !r.ok);
    lay(); if ($("#hopHT").open) veHeThong();
  } catch (x) { bao(x.message, true); }
  nut.disabled = false; nut.textContent = "Kích hoạt";
}

/** "còn 6 ngày" là hạn của thẻ xác nhận (tự gia hạn), không phải hạn bản quyền → chỉ nói khi thật sự sắp hết */
function chuBQ(c) { const m = /còn\s+(\d+)\s+ngày/.exec(c || ""); return m && +m[1] >= 2 ? "đang hoạt động" : (c || ""); }
async function capNhatNgay(e) {
  e?.preventDefault?.();
  const n = $("#formCN button"); if (n) { n.disabled = true; n.textContent = "Đang tải và cài bản mới…"; }
  try {
    const r = await api("/api/cap-nhat/cai", {});
    if (r.khoi_dong_lai) {
      bao("Đã cập nhật — Studio đang mở lại bằng bản mới…");
      setTimeout(function thu() { fetch("/api/ping").then((x) => x.ok ? location.reload() : setTimeout(thu, 1500)).catch(() => setTimeout(thu, 1500)); }, 3500);
      return;
    }
    bao((r.chu || "Không cập nhật được").trim().split("\n").pop(), !r.ok);
  } catch (x) { bao(x.message, true); }
  if (n) { n.disabled = false; n.textContent = "Cập nhật ngay"; }
}
async function dangNhapClaude() {
  try { const r = await api("/api/claude/dang-nhap", {}); bao(r.co_san ? "Đã mở cửa sổ đăng nhập Claude" : "Đang cài Claude Code trong cửa sổ mới, xong sẽ tới bước đăng nhập"); }
  catch (x) { bao(x.message, true); }
}

/* ---------- GIỮA: trò chuyện ---------- */
function md(s) {
  const dong = esc(s).split("\n"); const ra = []; let ds = null, bang = null;
  const inl = (t) => t.replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  const dongDs = () => { if (ds) { ra.push(`<${ds.t}>${ds.i.map((x) => `<li>${inl(x)}</li>`).join("")}</${ds.t}>`); ds = null; } };
  const dongBang = () => { if (bang) { ra.push("<table>" + bang.filter((r) => !/^\s*\|?\s*:?-{2,}/.test(r)).map((r) => "<tr>" + r.replace(/^\||\|$/g, "").split("|").map((c) => `<td>${inl(c.trim())}</td>`).join("") + "</tr>").join("") + "</table>"); bang = null; } };
  for (const l of dong) {
    let m;
    if (/^\s*\|.*\|\s*$/.test(l)) { dongDs(); (bang ||= []).push(l.trim()); continue; } else dongBang();
    if ((m = l.match(/^\s*[-*•]\s+(.*)/))) { if (ds?.t !== "ul") { dongDs(); ds = { t: "ul", i: [] }; } ds.i.push(m[1]); continue; }
    if ((m = l.match(/^\s*\d+[.)]\s+(.*)/))) { if (ds?.t !== "ol") { dongDs(); ds = { t: "ol", i: [] }; } ds.i.push(m[1]); continue; }
    dongDs();
    if ((m = l.match(/^#{1,4}\s+(.*)/))) { ra.push(`<h3>${inl(m[1])}</h3>`); continue; }
    if (l.trim()) ra.push(`<p>${inl(l)}</p>`);
  }
  dongDs(); dongBang();
  return ra.join("");
}
function chuLoiDeDoc(noiDung) {
  const chu = String(noiDung ?? "");
  const loi522 = /\bAPI\s+Error\s*:\s*522\b|\bHTTP\s*(?:Error\s*)?[:=]?\s*522\b|["'](?:status|status_code|statusCode)["']\s*:\s*(?:522(?=\s*[,}])|["']522["'])/i.test(chu);
  return loi522 ? "Máy chủ API đang dùng không phản hồi (HTTP 522). Chờ máy chủ hoạt động lại rồi thử tiếp." : chu;
}
function theLoi(t) {
  const goc = String(t.noi_dung ?? ""), gon = chuLoiDeDoc(goc);
  if (gon === goc) return el("div", { class: "tin-loi" }, goc);
  return el("div", { class: "tin-loi", style: "overflow-wrap:anywhere" }, el("p", {}, gon),
    el("details", {}, el("summary", {}, "Chi tiết kỹ thuật"),
      el("pre", { style: "white-space:pre-wrap;overflow-wrap:anywhere;max-width:100%" }, goc)));
}
function veTroChuyen() {
  hienView();
  const tc = $("#troChuyen"), h = hoSo(S.hs);
  // trong mỗi lượt (giữa hai tin người dùng), thẻ video đã giao được dời xuống cuối — chỗ mắt người dùng đang nhìn
  const tin = [];
  let luot = [];
  const dongLuot = () => { tin.push(...luot.filter((t) => t.vai !== "video"), ...luot.filter((t) => t.vai === "video")); luot = []; };
  for (const t of S.viecData?.tin || []) { if (t.vai === "nguoi_dung") { dongLuot(); tin.push(t); } else luot.push(t); }
  dongLuot();
  // việc rất dài: chỉ vẽ ~300 tin gần nhất để khung chat không nặng khi đang dựng (giữ phần mắt đang nhìn)
  let luoc = 0;
  if (tin.length > 320) { luoc = tin.length - 300; tin.splice(0, luoc); }
  const trong = !tin.length;
  tc.classList.toggle("trong", trong);
  $("#chao").hidden = !trong; $("#goiY").hidden = !trong || !h;
  if (trong) {
    $("#chaoMau").style.background = h?.mau || "var(--chu-3)";
    $("#chaoChu").textContent = h ? `Dựng gì cho ${h.kenh}?` : "Tạo hồ sơ kênh đầu tiên";
    $("#chaoPhu").textContent = h ? "Thả video quay thô vào đây, nói cảm giác bạn muốn người xem có. Gõ /review, /sanpham… hoặc bấm Phong cách để chọn nhanh. Claude làm 3 phần: Đọc · Tư duy · Dựng (máy tự kiểm luật, tự sửa), bạn theo dõi phiếu và thời gian còn lại ở bên phải." : "Mỗi kênh một hồ sơ riêng: màu, font, gu, góp ý. Bấm “Tạo hồ sơ kênh” ở cột trái.";
  }
  $("#soan").hidden = !h;
  dgCapNhat();
  const cuon = $("#cuon"), sat = cuon.scrollHeight - cuon.scrollTop - cuon.clientHeight < 120;
  const nut = [];
  if (luoc) nut.push(el("div", { class: "tin-ht" }, `(đã ẩn ${luoc} dòng cũ cho nhẹ — việc vẫn đủ)`));
  for (let i = 0; i < tin.length; i++) {
    const t = tin[i];
    if (t.vai === "cong_cu") {
      const nhom = []; const dau = i;
      while (i < tin.length && tin[i].vai === "cong_cu") nhom.push(tin[i++]);
      i--;
      const cuoi = i === tin.length - 1 && viecChay(S.viec);
      const mo = S.moNhom.has(dau);
      nut.push(el("div", { class: "nhom-cc" + (mo ? " mo" : "") },
        el("button", { type: "button", onclick: (e) => { S.moNhom.has(dau) ? S.moNhom.delete(dau) : S.moNhom.add(dau); e.currentTarget.parentElement.classList.toggle("mo"); } },
          el("svg", { viewBox: "0 0 24 24", html: '<path d="M9 6l6 6-6 6"/>' }),
          cuoi ? nhom[nhom.length - 1].noi_dung : `${nhom.length} thao tác công cụ`),
        el("ol", {}, nhom.map((x) => el("li", {}, x.noi_dung)))));
      continue;
    }
    if (t.vai === "nguoi_dung") {
      const dinh = [...(t.tep || []).map((x) => el("span", { class: "dinh" }, el("b", {}, "video"), el("span", {}, x))),
        ...(t.mau || []).map((x) => el("span", { class: "dinh dinh-mau" }, el("b", {}, "video mẫu"), el("span", {}, x))),
        ...(t.anh || []).map((x) => el("span", { class: "dinh" }, el("b", {}, "ảnh"), el("span", {}, x))),
        ...(t.am || []).map((x) => el("span", { class: "dinh" }, el("b", {}, "âm thanh"), el("span", {}, x))),
        ...(t.tai_lieu || []).map((x) => el("span", { class: "dinh" }, el("b", {}, "kịch bản"), el("span", {}, x))),
        ...(t.thu_muc || []).map((x) => el("span", { class: "dinh" }, el("b", {}, "thư mục"), el("span", {}, x))),
        ...(t.giong || []).map((x) => el("span", { class: "dinh" }, el("b", {}, "giọng"), el("span", {}, x))),
        ...(t.kho || []).map((x) => el("span", { class: "dinh" }, el("b", {}, x.loai), el("span", {}, x.ten))),
        ...(t.links || []).map((x) => el("span", { class: "dinh" }, el("b", {}, "link"), el("span", {}, x)))];
      nut.push(el("div", { class: "tin-nguoi" }, t.noi_dung || "", dinh.length ? el("div", { class: "dinh-ds" }, dinh) : null));
    } else if (t.vai === "claude") nut.push(el("div", { class: "tin-claude", html: md(t.noi_dung) }));
    else if (t.vai === "hoi") nut.push(theHoi(t, !tin.slice(i + 1).some((x) => x.vai === "nguoi_dung")));
    else if (t.vai === "loi") nut.push(theLoi(t));
    else if (t.vai === "he_thong") nut.push(el("div", { class: "tin-ht" }, t.noi_dung));
    else if (t.vai === "video") nut.push(theVideo(t));
    else if (t.vai === "anh") nut.push(el("div", {}, t.noi_dung ? el("p", { class: "tin-ht", style: "text-align:left" }, t.noi_dung) : null,
      el("div", { class: "luoi-anh-tin" }, (t.anh || []).map((a) => el("button", { type: "button", onclick: () => xemLon(media(a)) }, el("img", { src: media(a), loading: "lazy", alt: tenFile(a) }))))));
  }
  $("#dsTin").replaceChildren(...nut);
  const cho = !!S.viecData?.cho_tra_loi && !viecChay(S.viec);
  $("#choTL").hidden = !cho; $("#soan").classList.toggle("cho", cho);
  o.placeholder = khoaChat() ? lyDoKhoa() : cho ? "Trả lời Claude…" : goiYSoan();
  if (sat || S.cuonDuoi) { cuon.scrollTop = cuon.scrollHeight; S.cuonDuoi = false; }
  nutGui();
}
function theHoi(t, conMo) {
  const tra = (c) => { o.value = c; tuCao(); gui(); };
  return el("div", { class: "the-hoi" + (conMo ? " mo" : "") },
    el("p", { class: "nhan-muc" }, conMo ? "Claude đang hỏi bạn" : "Claude đã hỏi"),
    el("div", { class: "cau", html: md(t.noi_dung) }),
    (t.lua_chon || []).length ? el("div", { class: "lc" }, t.lua_chon.map((c) => el("button", { class: "nut " + (conMo ? "nut-phu" : "nut-nho"), type: "button", disabled: !conMo, onclick: () => tra(c) }, c))) : null,
    conMo ? el("p", { class: "goi-y" }, (t.lua_chon || []).length ? "Bấm một lựa chọn, hoặc gõ câu trả lời của bạn ở ô bên dưới." : "Gõ câu trả lời ở ô bên dưới rồi Enter.") : null);
}
function theVideo(t) {
  return el("div", { class: "the-video", "data-tep": t.tep },
    el("video", { src: media(t.tep), controls: true, preload: "metadata", playsinline: true }),
    el("div", { class: "tt" },
      el("p", { class: "nhan-muc" }, "Đã giao"),
      el("div", { class: "ten" }, tenFile(t.tep)),
      t.bia ? el("button", { class: "bia", type: "button", style: `background-image:url("${media(t.bia)}")`, onclick: () => xemLon(media(t.bia)), "aria-label": "Xem ảnh bìa" }) : null,
      t.noi_dung ? el("div", { class: "tin-claude", html: md(t.noi_dung) }) : null,
      el("div", { class: "nut-ds" },
        el("button", { class: "nut nut-chinh", type: "button", onclick: () => api("/api/mo-thu-muc", { p: t.thu_muc || t.tep }).catch((x) => bao(x.message, true)) }, "Mở thư mục"),
        t.thu_muc ? el("button", { class: "nut nut-phu", type: "button", title: "Tạo project CapCut sửa tiếp được (CapCut quốc tế 9.x trở xuống)",
          onclick: (e) => { const n = e.currentTarget; n.disabled = true; api("/api/capcut", { thu_muc: t.thu_muc, viec: S.viec })
            .then(() => bao("Đang xuất sang CapCut — xong sẽ báo trong khung chat"))
            .catch((x) => { bao(x.message, true); n.disabled = false; }); } }, "Xuất sang CapCut") : null)));
}
function veDangLam() {
  const soCho = (S.tatCa || []).filter((v) => v.cho).length;
  document.title = (soCho ? `(${soCho}) Claude đang hỏi · ` : "") + "Studio dựng video";
  const dc = S.tq?.dong_co, cua = dangChay()[S.viec]; const dang = !!cua && S.view === "chat";
  const cho = (dc?.hang_doi || []).includes(S.viec);
  $("#dangLam").hidden = !(dang || (cho && S.view === "chat")); $("#dauLam").hidden = !cua;
  if (cho && !cua) { $("#dangLamGio").textContent = "⏳"; $("#dangLamChu").textContent = "Chờ máy rảnh — đang dựng việc khác"; $("#dangLamPhu").textContent = "Câu hỏi ở việc khác vẫn chạy bình thường"; return; }
  if (!cua) return;
  // 1.2.12: không hiện bước / mốc quy trình — chỉ báo đang làm + thời gian còn lại ước tính
  let chu = "Claude đang làm video";
  const p2 = (S.tq.phieu2_ds || []).slice(-1)[0];
  const e = p2?._eta || {};
  if (p2 && e.phan < 3 && e.con_lai) chu += ` · còn khoảng ${phut(e.con_lai)}`;
  const giay = Math.max(0, Math.round(Date.now() / 1000 - (cua.bat_dau || dc.bat_dau)));
  const cc = [...(S.viecData?.tin || [])].reverse().find((t) => t.vai === "cong_cu");
  $("#dangLamGio").textContent = mmss(giay);
  $("#dangLamChu").textContent = chu;
  $("#dangLamPhu").textContent = cc ? cc.noi_dung : "";
  $("#dauLamChu").textContent = mmss(giay);
}
function phut(g) { g = Math.max(0, +g || 0); return g < 90 ? "1 phút" : Math.round(g / 60) + " phút"; }
function xemLon(u) { const x = $("#xemLon"); $("img", x).src = u; x.hidden = false; }
$("#xemLon").addEventListener("click", () => ($("#xemLon").hidden = true));

/* ---------- soạn + gửi ---------- */
const o = $("#o");
function tuCao() { o.style.height = "auto"; o.style.height = Math.min(240, o.scrollHeight) + "px"; }
function khoaChat() { return !!lyDoKhoa(); }   // chưa kích hoạt / gói bị sửa / bắt buộc cập nhật → khoá gửi
function lyDoKhoa() {
  const bq = S.tq?.he_thong?.ban_quyen, cn = S.tq?.he_thong?.cap_nhat;
  if (bq && !bq.hop_le) return "Nhập mã bản quyền ở góc dưới bên trái để bắt đầu…";
  const dangDo = viecChay(S.viec) || !!S.viecData?.cho_tra_loi;          // 1.2.19: việc đang dở / Claude đang hỏi → vẫn trả lời được
  if (cn && cn.co_moi && cn.bat_buoc && !dangDo) return "Có bản Studio mới — bấm “Cập nhật ngay” ở bảng trên để dùng tiếp…";
  return "";
}
function hopEpCapNhat() {
  const cn = S.tq?.he_thong?.cap_nhat; if (!cn?.co_moi) return;
  let d = $("#hopEpCN");
  if (!d) { d = el("dialog", { class: "hop", id: "hopEpCN" }); document.body.appendChild(d); }
  d.replaceChildren(el("h3", {}, `Có bản Studio mới ${cn.ban || ""}`),
    el("p", {}, "Bản này là bắt buộc: Studio tạm khoá gửi việc tới khi cập nhật xong. Hồ sơ kênh, bài đã học, video đã giao và cấu hình máy giữ nguyên. Mất khoảng 1–3 phút, Studio tự mở lại."),
    el("pre", { style: "max-height:30vh;overflow:auto;white-space:pre-wrap" }, (cn.chu || "").slice(0, 1500)),
    el("div", { style: "display:flex;gap:8px;justify-content:flex-end" },
      el("button", { class: "nut nut-phu", type: "button", onclick: () => d.close() }, "Để sau (chỉ xem)"),
      el("button", { class: "nut nut-chinh", type: "button", onclick: (e) => { d.close(); capNhatNgay(e); } }, "Cập nhật ngay")));
  if (!d.open) d.showModal();
}
function nutGui() { if (dgBat()) { $("#nutGui").disabled = khoaChat() || S.guiCho || !(dgMoi() ? dgCoChinh() : (o.value.trim() || S.dinh.some((d) => !d.loi))); return; } $("#nutGui").disabled = khoaChat() || S.guiCho || (!o.value.trim() && !S.dinh.some((d) => d.kind === "kho" || d.kind === "giong" || d.duong_dan || !d.loi)); }
const TEN_DINH = { video: "video", mau: "video mẫu", anh: "ảnh", am: "âm thanh", tai_lieu: "kịch bản", thu_muc: "thư mục", lut: "LUT màu", font: "font" };
const DUOI = { video: /\.(mp4|mov|m4v|mkv|avi|webm|mts|insv)$/i, anh: /\.(png|jpe?g|webp|heic|bmp|gif)$/i, am: /\.(mp3|wav|m4a|aac|flac|ogg|aiff?)$/i,
  tai_lieu: /\.(xlsx|xlsm|xls|docx|pptx|csv|tsv|txt|md|srt|vtt|rtf|pdf)$/i, lut: /\.(cube|3dl)$/i, font: /\.(ttf|otf)$/i };
function loaiTep(ten) { for (const k of ["video", "anh", "am", "tai_lieu", "lut", "font"]) if (DUOI[k].test(ten)) return k; return null; }
function themDuong(ds) {           // ds: [{duong_dan, ten, loai}] từ hộp chọn của máy
  for (const x of ds || []) {
    if (!x.loai || S.dinh.some((d) => d.duong_dan === x.duong_dan)) continue;
    S.dinh.push(dgGan({ kind: ["tai_lieu", "thu_muc", "anh", "am", "mau", "lut", "font"].includes(x.loai) ? x.loai : "video", ten: x.ten || tenFile(x.duong_dan), duong_dan: x.duong_dan, mb: "" }));
  }
}
function loiMacDinh() {
  if (dgBat() || o.value.trim()) return;
  const k = new Set(S.dinh.map((d) => d.kind));
  if (k.has("mau") && k.has("video")) o.value = "Dựng video này theo phong cách của video mẫu";
  else if (k.has("mau")) o.value = "Phân tích phong cách video mẫu này (chữ, màu, chuyển cảnh, nhịp) để mình dùng cho video sắp dựng";
  else if (k.has("video")) o.value = "Dựng video này";
  else if (k.has("thu_muc")) o.value = "Đọc thư mục này rồi dựng video từ tư liệu trong đó";
  else if (k.has("tai_lieu")) o.value = "Đọc kịch bản này";
}
// 1.2.19 (Thêm 3): mẫu câu theo thứ đã đưa vào — dòng 1 "bạn đã đưa vào gì", dòng 2 "muốn video thế nào, để làm gì"; không trả lời vẫn dựng được
function goiYSoan() {
  if (dgBat()) return dgMoi() ? "Muốn video thế nào, để làm gì? Để trống thì AI tự quyết theo hồ sơ kênh." : "Muốn sửa gì ở video này?";
  const tep = S.dinh.filter((d) => d.duong_dan || d.kind === "video" || d.kind === "mau" || d.kind === "thu_muc");
  if (!tep.length) return "Thả video quay thô vào đây (hoặc bấm nút bên dưới), rồi gõ bạn muốn video thế nào — không gõ cũng được, AI tự dựng.";
  const ten = tep.slice(0, 3).map((d) => d.ten).join(", ") + (tep.length > 3 ? ` +${tep.length - 3}` : "");
  return `Bạn đã đưa vào: ${ten}.\nBạn muốn một video như thế nào, để làm gì? (vd: review 60 giây, chữ nhấn ý chính, nhạc nhẹ, đăng TikTok) — để trống cũng được, AI tự dựng theo hồ sơ kênh.`;
}
function veDinh() {
  const _o = $("#o"); if (_o && !khoaChat() && !(S.viecData?.cho_tra_loi)) _o.placeholder = goiYSoan();
  $("#soanDinh").replaceChildren(...S.dinh.map((d, i) => {
    const x = el("button", { class: "x", type: "button", "aria-label": "Bỏ", onclick: () => { d.xhr?.abort(); S.dinh.splice(i, 1); veDinh(); } }, "×");
    if (d.kind === "kho") return el("span", { class: "chip" }, el("span", { class: "l" }, d.loai_ten), el("span", { class: "t", title: d.ten }, d.ten), x);
    if (d.kind === "giong") return el("span", { class: "chip" }, el("span", { class: "l" }, "giọng"), el("span", { class: "t", title: d.ten }, d.ten), x);
    if (d.kind === "thu_muc") return el("span", { class: "chip" }, el("span", { class: "l" }, "thư mục"), el("span", { class: "t", title: d.duong_dan }, d.ten), x);
    // video ↔ video mẫu: bấm nhãn để đổi (video mẫu = chỉ để copy phong cách, không dựng)
    const nhan = (d.kind === "video" || d.kind === "mau")
      ? el("button", { class: "l l-doi" + (d.kind === "mau" ? " la-mau" : ""), type: "button", title: d.kind === "mau" ? "Đang là VIDEO MẪU (copy phong cách) — bấm để đổi về video cần dựng" : "Bấm để đánh dấu là VIDEO MẪU (copy phong cách edit)",
          onclick: () => { d.kind = d.kind === "mau" ? "video" : "mau"; veDinh(); } }, TEN_DINH[d.kind])
      : el("span", { class: "l" }, TEN_DINH[d.kind] || "file");
    return el("span", { class: "chip" + (d.loi ? " loi" : "") + (d.kind === "mau" ? " chip-mau" : "") },
      anhThuNho(d) ? el("img", { class: "chip-thumb", src: anhThuNho(d), alt: "", onerror: (e) => e.target.remove() }) : null, nhan, el("span", { class: "t", title: d.ten }, d.ten),
      el("span", { class: "s" }, d.loi ? "lỗi" : d.duong_dan ? (d.mb ? `${d.mb} MB` : "trên máy") : `${d.pct}%`), x,
      !d.duong_dan && !d.loi ? el("i", { class: "tien", style: `width:${d.pct}%` }) : null);
  }));
  if (dgBat()) veDg();
  nutGui();
}
function taiLen(files) {
  for (const f of files) {
    const lt = loaiTep(f.name);
    if (!lt) { bao(`${f.name}: Studio nhận video, ảnh, âm thanh, kịch bản (xlsx, docx, csv, txt, pdf…), LUT màu (.cube) và font (.ttf, .otf)`, true); continue; }
    const d = dgGan({ kind: lt, ten: f.name, mb: (f.size / 1e6).toFixed(1), pct: 0 });
    const x = new XMLHttpRequest(); d.xhr = x;
    // 1.2.21 (1h): trình duyệt cho biết ĐƯỜNG DẪN THẬT (vài vỏ app có f.path) → server hardlink/chép, không truyền thân tệp
    const nguon = typeof f.path === "string" && f.path.length > 3 ? f.path : "";
    x.open("POST", "/api/tai-len?ten=" + encodeURIComponent(f.name) + (nguon ? "&nguon=" + encodeURIComponent(nguon) : ""));
    x.setRequestHeader("Content-Type", "application/octet-stream");
    x.upload.onprogress = (e) => { if (e.lengthComputable) { d.pct = Math.round((e.loaded / e.total) * 100); veDinh(); } };
    x.onload = () => {
      try { const j = JSON.parse(x.responseText); if (x.status >= 300) throw new Error(j.loi); Object.assign(d, { duong_dan: j.duong_dan, ten: j.ten, mb: j.mb }); }
      catch (e) { d.loi = true; bao(e.message || "Tải video lên bị lỗi", true); }
      d.xhr = null; veDinh();
      if (S.guiCho && !S.dinh.some((z) => z.xhr)) gui();
    };
    x.onerror = () => { d.loi = true; d.xhr = null; veDinh(); };
    x.send(nguon ? null : f); S.dinh.push(d);
  }
  veDinh();
  loiMacDinh();
  if (!dgBat()) { o.focus(); o.select(); }
  tuCao();
}
function themKho(k) {
  if (S.dinh.some((d) => d.kind === "kho" && d.ten === k.ten && d.loai === k.loai)) return;
  S.dinh.push({ kind: "kho", loai: k.loai, loai_ten: TEN_LOAI[k.loai] || k.loai, ten: k.ten, duong: k.duong || "", ham: k.ham || "" });
  veDinh(); if (S.view !== "chat") dongHoSo(); o.focus();
}
async function gui() {
  if (!hoSo(S.hs)) return;
  if (S.dinh.some((d) => d.xhr)) { S.guiCho = true; nutGui(); bao("Đợi tải file xong sẽ tự gửi"); return; }
  S.guiCho = false;
  const dg = dgBat();
  if (dg) { const loi = dgKiem(); if (loi) { bao(loi, true); nutGui(); return; } }
  const noi = dg ? dgLoi() : o.value.trim();
  const tep = S.dinh.filter((d) => d.kind === "video" && d.duong_dan).map((d) => d.duong_dan);
  const kho = S.dinh.filter((d) => d.kind === "kho").map(({ loai, loai_ten, ten, duong, ham }) => ({ loai, loai_ten, ten, duong, ham }));
  const giong = S.dinh.filter((d) => d.kind === "giong" && d.duong_dan).map((d) => d.duong_dan);
  const lay_ = (k) => S.dinh.filter((d) => d.kind === k && d.duong_dan).map((d) => d.duong_dan);
  const them = { anh: lay_("anh"), am: lay_("am"), tai_lieu: lay_("tai_lieu"), mau: lay_("mau"), thu_muc: lay_("thu_muc"), lut: lay_("lut"), font: lay_("font") };
  const coThem = Object.values(them).some((x) => x.length);
  if (!noi && !tep.length && !kho.length && !giong.length && !coThem) return;
  try {
    if (!S.viec) { const v = await api("/api/viec", { ho_so: S.hs }); S.viec = v.id; nho.dat("viec", v.id); }
    await api(`/api/viec/${S.viec}/gui`, { noi_dung: noi, tep, kho, giong, ...them, nhanh: nho.lay("nhanh", "") === "1", ...(dg ? { don_gian: true } : {}) });
    o.value = ""; S.dinh = []; S.dgBaiChon = ""; S.dgHs = null; S.dgMoTiep = null; veDinh(); tuCao(); S.cuonDuoi = true;
    S.moc = {}; await lay(); await layViec(); veTroChuyen();
  } catch (e) { bao(e.message, true); }
}
$("#soan").addEventListener("submit", (e) => { e.preventDefault(); gui(); });
// 1.3: công tắc "⚡ Làm nhanh" — nhớ lựa chọn trên máy này; áp cho việc gửi tiếp theo
const veNhanh = () => $("#nutNhanh").setAttribute("aria-pressed", nho.lay("nhanh", "") === "1" ? "true" : "false");
$("#nutNhanh").addEventListener("click", () => {
  const bat = nho.lay("nhanh", "") !== "1"; nho.dat("nhanh", bat ? "1" : "");
  veNhanh(); bao(bat ? "Đã bật Làm nhanh — video gửi tiếp theo dựng nhanh (đủ cắt ghép, chữ, SFX, ảnh, cảnh trám; không xoá nền)" : "Đã tắt Làm nhanh — dựng đầy đủ");
});
veNhanh();
o.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing && !dgBat()) { e.preventDefault(); gui(); } });
o.addEventListener("input", () => { tuCao(); nutGui(); });
// "+" mở hộp chọn file của máy → lấy đường dẫn thật, không chép video nặng; kéo thả vẫn tải lên như cũ
$("#nutKem").addEventListener("click", () => chonTepTrinhDuyet("tat-ca"));
function chonDac(loai, nutId) {
  if (!hoSo(S.hs)) { bao("Tạo hồ sơ kênh trước đã", true); return; }
  return chonTepTrinhDuyet(loai, loai === "mau" ? "mau" : "phu");
}
$("#nutThuMuc").addEventListener("click", () => chonDac("thu-muc", "#nutThuMuc"));
$("#nutMau").addEventListener("click", () => chonDac("mau", "#nutMau"));
$("#chonTep").addEventListener("change", (e) => { taiLen([...e.target.files]); e.target.value = ""; });
$("#nutMoKho").addEventListener("click", () => { chonPhai("kho"); if (innerWidth <= 1020) $("#khung").classList.add("mo-phai"); else $("#khung").classList.remove("an-phai"); $("#khoTim").focus(); });
$("#goiY").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  const g = b.dataset.goi;
  if (g === "dung") chonTepTrinhDuyet("tat-ca");
  else if (g === "hoc") { moHoSo("hoc"); }
  else if (g === "bia") { o.value = "Làm lại 5 ảnh bìa cho video này (AI tự thiết kế): "; o.focus(); tuCao(); }
  else if (g === "hoi") { o.value = "Hỏi mình 6 câu trong HOI.md để hoàn thiện hồ sơ kênh này (màu, gu, thứ cấm, kiểu bìa)."; o.focus(); tuCao(); nutGui(); }
});
// thả: video từ máy → tải lên; tài nguyên từ kho → đính vào yêu cầu
let demKeo = 0;
const coFile = (e) => [...(e.dataTransfer?.types || [])].includes("Files");

// ---------------------------------------------------------------- 1.2.21: soạn việc ĐƠN GIẢN / ĐẦY ĐỦ
// Chỉ là giao diện: gom tệp + ghi chú vào đúng các trường gửi việc cũ (S.dinh, /api/viec/<id>/gui). Máy không thêm gu hay lời khuyên nào;
// ghi chú đi nguyên văn cho AI. Cờ don_gian duy nhất báo server không dò chữ trong ghi chú để tách việc.
const DG_MUC = ["chinh", "phu", "mau"];
const DG_GIU_Y = { chinh: "Ghi chú cho clip này (tuỳ chọn)", phu: "Dùng tệp này khi nào, ở đâu (tuỳ chọn)", mau: "Muốn lấy gì từ mẫu này (tuỳ chọn)" };
function cheDoSoan() {
  let m = nho.lay("che_do_soan", "");
  if (m !== "don_gian" && m !== "day_du") { m = nho.lay("viec", "") ? "day_du" : "don_gian"; nho.dat("che_do_soan", m); }   // máy đã dùng Studio giữ giao diện cũ; khách mới vào Đơn giản
  return m;
}
const anhThuNho = (d) => (d.duong_dan && ["video", "mau", "anh"].includes(d.kind)) ? `/api/thumb?p=${encodeURIComponent(d.duong_dan)}` : "";
const dgDung = () => !!hoSo(S.hs) && S.view === "chat" && S.viecData?.loai !== "hoc";
const dgMoi = () => dgDung() && !(S.viecData?.tin || []).length;
// việc mới theo lựa chọn đã nhớ; đoạn chat đang làm mặc định là ô chat, bấm Đơn giản thì mở form cho riêng việc đó, gửi xong đóng lại
const dgBat = () => dgDung() && (dgMoi() ? cheDoSoan() === "don_gian" : !!S.viec && S.dgMoTiep === S.viec);
const DG_HINH = {
  video: '<rect x="4" y="5" width="16" height="14" rx="2.5"/><path d="M10 9.5v5l4-2.5z"/>',
  mau: '<rect x="4" y="5" width="16" height="14" rx="2.5"/><path d="M10 9.5v5l4-2.5z"/>',
  anh: '<rect x="4" y="5" width="16" height="14" rx="2.5"/><circle cx="9" cy="10" r="1.5"/><path d="m5 17 5-4 3 2.5 2-1.5 4 3"/>',
  am: '<path d="M9 18V6l10-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/>',
  tai_lieu: '<path d="M7 3.5h7l4 4V20a.5.5 0 0 1-.5.5h-10.5a.5.5 0 0 1-.5-.5V4a.5.5 0 0 1 .5-.5z"/><path d="M9 12h6M9 16h6"/>',
  thu_muc: '<path d="M3.5 7.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
  khac: '<path d="M4 7.5 12 4l8 3.5-8 3.5z"/><path d="M4 12l8 3.5 8-3.5M4 16.5 12 20l8-3.5"/>',
};
function dgGan(d) {
  if (S.dgTha && DG_MUC.includes(S.dgTha)) { d.muc = S.dgTha; if (d.muc === "mau" && d.kind === "video") d.kind = "mau"; }
  return d;
}
function mucCua(d) {
  if (d.kind === "mau") return "mau";
  if (d.kind === "video" && d.muc !== "phu") return "chinh";
  return "phu";
}
const dgDs = (muc) => S.dinh.filter((d) => mucCua(d) === muc);
const dgCoChinh = () => dgDs("chinh").some((d) => !d.loi);
function dgDoiMuc(d, muc) { d.muc = muc; if (muc === "mau") d.kind = "mau"; else if (d.kind === "mau") d.kind = "video"; veDinh(); }
function dgDoiCho(d, buoc) {
  const ds = dgDs("chinh"), i = ds.indexOf(d), k = ds[i + buoc];
  if (!k) return;
  const a = S.dinh.indexOf(d), b = S.dinh.indexOf(k);
  [S.dinh[a], S.dinh[b]] = [S.dinh[b], S.dinh[a]];
  veDinh();
}
function dgNhan(d) { return d.kind === "kho" ? d.loai_ten : d.kind === "giong" ? "giọng" : TEN_DINH[d.kind] || "tệp"; }
function hangDg(d) {
  if (!d._h) {
    const trang = el("span", { class: "s" }), ten = el("span", { class: "t" });
    const chon = (d.kind === "video" || d.kind === "mau") ? el("select", { "aria-label": "Vai của clip", onchange: (e) => dgDoiMuc(d, e.target.value) },
      el("option", { value: "chinh" }, "Chính"), el("option", { value: "phu" }, "Phụ"), el("option", { value: "mau" }, "Mẫu")) : null;
    const len = el("button", { class: "dg-len", type: "button", "aria-label": "Đưa clip lên trước", onclick: () => dgDoiCho(d, -1) }, "↑");
    const xuong = el("button", { class: "dg-len", type: "button", "aria-label": "Đưa clip xuống sau", onclick: () => dgDoiCho(d, 1) }, "↓");
    const ghi = el("textarea", { rows: 2, maxlength: 1000, "aria-label": "Ghi chú cho " + (d.ten || "tệp"), oninput: (e) => { d.note = e.target.value; e.target.style.height = "auto"; e.target.style.height = e.target.scrollHeight + "px"; } });
    const tile = el("div", { class: "dg-tile" + (d.kind === "anh" ? " la-anh" : ""), html: `<svg viewBox="0 0 24 24">${DG_HINH[d.kind] || DG_HINH.khac}</svg>` });
    const anh = el("img", { alt: "", draggable: "false", onload: () => tile.classList.add("co-anh"), onerror: () => tile.classList.remove("co-anh") });
    tile.append(anh);
    d._h = el("div", { class: "dg-hang", draggable: "true",
        ondragstart: (e) => { if (e.target.closest?.("textarea,select")) { e.preventDefault(); return; } S.dgKeo = d; e.dataTransfer.setData("application/x-dg", "1"); },
        ondragover: (e) => { if (S.dgKeo && mucCua(S.dgKeo) === mucCua(d)) e.preventDefault(); },
        ondrop: (e) => { const k = S.dgKeo; S.dgKeo = null; if (!k || k === d || mucCua(k) !== mucCua(d)) return; e.preventDefault(); e.stopPropagation(); S.dinh.splice(S.dinh.indexOf(k), 1); S.dinh.splice(S.dinh.indexOf(d), 0, k); veDinh(); },
        ondragend: () => { S.dgKeo = null; } },
      tile,
      el("div", { class: "dg-hang-than" },
        el("div", { class: "dg-hang-tren" }, ten,
          el("button", { class: "x", type: "button", "aria-label": "Bỏ " + (d.ten || "tệp này"), onclick: () => { d.xhr?.abort(); S.dinh.splice(S.dinh.indexOf(d), 1); veDinh(); } }, "×")),
        el("div", { class: "dg-hang-phu" }, el("span", { class: "l" }, dgNhan(d)), trang, el("span", { class: "dg-gian" }), len, xuong, chon),
        ghi));
    d._v = { trang, ten, chon, ghi, len, xuong, anh };
  }
  const v = d._v, muc = mucCua(d), thumb = anhThuNho(d);
  if (thumb && v.anh.dataset.u !== thumb) { v.anh.dataset.u = thumb; v.anh.src = thumb; }
  v.ten.textContent = d.ten || ""; v.ten.title = d.duong_dan || d.ten || "";
  v.trang.textContent = d.dangLink ? "đang tải…" : d.loi ? "lỗi" : d.kind === "kho" || d.kind === "giong" ? "" : d.duong_dan ? (d.mb ? `${d.mb} MB` : "trên máy") : `${d.pct || 0}%`;
  d._h.classList.toggle("loi", !!d.loi);
  if (v.chon) v.chon.value = muc;
  v.len.hidden = v.xuong.hidden = muc !== "chinh";
  v.ghi.placeholder = DG_GIU_Y[muc];
  if (document.activeElement !== v.ghi) v.ghi.value = d.note || "";
  return d._h;
}
function veDg() {
  for (const muc of DG_MUC) {
    const o_ = $("#dgDs_" + muc), hang = dgDs(muc).map(hangDg);
    if (hang.length !== o_.children.length || hang.some((h, i) => h !== o_.children[i])) o_.replaceChildren(...hang);   // không thay khi không đổi: giữ con trỏ đang gõ ghi chú lúc tệp tải lên
    $("#dgRong_" + muc).hidden = hang.length > 0;
    o_.closest(".dg-muc").classList.toggle("co-tep", hang.length > 0);
  }
}
async function dgNapBai() {
  const hs = S.hs; if (S.dgHs === hs) return;
  S.dgHs = hs; S.dgBaiChon = "";
  $("#dgBaiO").hidden = true;
  let ds = [];
  try { ds = ((await api(`/api/ho-so/${hs}`)).thu_vien_hoc || []).filter((b) => b.bat).slice(0, 3); } catch { return; }   // tóm tắt chỉ đưa cho AI 3 bài đang bật mới nhất
  if (S.hs !== hs) return;
  $("#dgBai").replaceChildren(el("option", { value: "" }, "Không chỉ định"), ...ds.map((b) => el("option", { value: b.ten }, b.ten)));
  $("#dgBaiO").hidden = !ds.length;
}
function dgCapNhat() {
  const dung = dgDung(), bat = dgBat(), moi = dgMoi();
  if (bat && !S.dgDangMo) $("#soan").scrollTop = 0;                     // mở form luôn thấy từ đầu
  S.dgDangMo = bat;
  $("#dgDau").hidden = !dung; $("#dgThan").hidden = !bat; $("#dgYc").hidden = !bat;
  $("#soan").classList.toggle("don-gian", bat);
  $("#troChuyen").classList.toggle("soan-dg", bat);
  $("#dgNutDonGian").setAttribute("aria-pressed", bat ? "true" : "false");
  $("#dgNutDayDu").setAttribute("aria-pressed", dung && !bat ? "true" : "false");
  if (!dung) return;
  $("#dgKenh").textContent = (moi ? "Việc mới" : "Sửa tiếp video này") + " · " + (hoSo(S.hs)?.kenh || "");
  if (bat) {
    $("#dgTen_chinh").textContent = moi ? "Video chính" : "Thêm clip chính";
    $("#dgEm_chinh").textContent = moi ? "Bắt buộc" : "Tuỳ chọn";
    $("#dgRongTen_chinh").textContent = moi ? "Thêm video chính" : "Thêm clip chính";
    $("#dgRongMo_chinh").textContent = moi ? "Clip người nói. Nhiều clip sẽ nối theo thứ tự ở đây thành một video. Kéo thả vào đây cũng được." : "Chỉ thêm khi cần ghép thêm cảnh quay vào video này.";
    $("#dgChuGui").textContent = moi ? "Dựng video" : "Gửi yêu cầu sửa";
    veDg(); dgNapBai();
  }
}
function dgLoi() {
  const yc = o.value.trim(), chinh = dgDs("chinh"), phu = dgDs("phu"), mau = dgDs("mau"), bai = S.dgBaiChon || "";
  const ten = (d) => { const t = d.ten || d.duong_dan || ""; return S.dinh.filter((x) => x.ten === d.ten).length > 1 && d.duong_dan ? d.duong_dan : t; };
  const dong = (d, i) => `${i != null ? `${i + 1}.` : "-"} ${ten(d)}${d.link ? ` (tải từ ${d.link})` : ""}${d.note?.trim() ? `: ${d.note.trim()}` : ""}`;
  const coGhi = S.dinh.some((d) => d.note?.trim()), tiep = !dgMoi();
  if (tiep ? (!S.dinh.length && !bai) : (!coGhi && !phu.length && !mau.length && !bai && chinh.length <= 1)) return yc;   // không có gì thêm: gửi như đường cũ
  const p = [yc || (tiep ? "Làm theo ghi chú từng tệp bên dưới." : "Không có yêu cầu chung: tự quyết theo hồ sơ kênh.")];
  p.push(tiep ? "Đây là yêu cầu sửa tiếp video của việc này: giữ dự án và công thức hiện có, chỉ đổi phần được nêu. Vai từng tệp do người dùng chỉ rõ trong form."
              : "Vai từng tệp do người dùng chỉ rõ trong form, không hỏi lại tệp nào là chính.");
  if (chinh.length) p.push((tiep ? "CLIP CHÍNH THÊM (ghép vào video này theo đúng thứ tự):\n" : "VIDEO CHÍNH (clip người nói của MỘT video, nối đúng thứ tự này, dùng --video):\n") + chinh.map((d, i) => dong(d, i)).join("\n"));
  if (phu.length) p.push((tiep ? "TƯ LIỆU PHỤ MỚI (dùng trong công thức của dự án này):\n" : "TƯ LIỆU PHỤ (video ở đây dùng --phu, không phải clip chính):\n") + phu.map((d) => dong(d)).join("\n"));
  if (mau.length) p.push("VIDEO MẪU (ghi chú nói rõ muốn lấy gì):\n" + mau.map((d) => dong(d)).join("\n"));
  if (bai) p.push("Bài học ưu tiên trong các bài đang bật của kênh: " + bai);
  return p.join("\n\n");
}
function dgKiem() {
  if (S.dinh.some((d) => d.loi)) return "Có tệp bị lỗi. Bỏ tệp đó hoặc thêm lại rồi gửi.";
  if (dgMoi() && !dgCoChinh()) return "Thêm ít nhất một video chính.";
  if (!dgMoi() && !o.value.trim() && !S.dinh.length) return "Ghi yêu cầu sửa hoặc thêm tệp rồi gửi.";
  if (S.dinh.filter((d) => d.kind === "video").length > 20) return "Mỗi việc nhận tối đa 20 video chính và phụ.";
  if (dgDs("mau").length > 3) return "Mỗi việc nhận tối đa 3 video mẫu.";
  if (dgLoi().length > 12000) return "Yêu cầu và ghi chú quá dài (tối đa 12.000 ký tự). Rút gọn rồi gửi.";
  return "";
}
function dgDoi(m) {
  if (m === (dgBat() ? "don_gian" : "day_du")) return;
  if (m === "day_du") {                                                 // sang Đầy đủ: ghi chú chuyển thành chữ trong ô yêu cầu, không mất
    o.value = dgLoi(); S.dinh.forEach((d) => { d.note = ""; });
  }
  if (dgMoi()) nho.dat("che_do_soan", m);                               // đoạn chat đang làm: chỉ mở/đóng form của việc này, không đổi lựa chọn cho việc mới
  else S.dgMoTiep = m === "don_gian" ? S.viec : null;
  dgCapNhat(); veDinh(); tuCao();
  o.placeholder = khoaChat() ? lyDoKhoa() : goiYSoan();
}
$("#dgNutDonGian").addEventListener("click", () => dgDoi("don_gian"));
$("#dgNutDayDu").addEventListener("click", () => dgDoi("day_du"));
$("#dgBai").addEventListener("change", (e) => { S.dgBaiChon = e.target.value; });
async function dgThemLink() {
  const n = $("#dgLink"), url = n.value.trim();
  if (!url) { n.focus(); return; }
  if (!/^https?:\/\/\S+$/i.test(url)) { bao("Link phải bắt đầu bằng http:// hoặc https://", true); return; }
  if (S.dinh.some((x) => x.link === url)) { n.value = ""; return; }
  const d = { kind: "mau", muc: "mau", ten: url, link: url, pct: 0, dangLink: true, xhr: { abort() { d.huy = true; } } };
  S.dinh.push(d); n.value = ""; veDinh();
  try {
    const r = await api("/api/tai-mau", { url });
    if (!d.huy) Object.assign(d, { duong_dan: r.duong_dan, ten: r.ten, mb: r.mb });
  } catch (loi) { if (!d.huy) { d.loi = true; bao(loi.message, true); } }
  d.dangLink = false; d.xhr = null; veDinh();
  if (S.guiCho && !S.dinh.some((z) => z.xhr)) gui();
}
$("#dgNutLink").addEventListener("click", dgThemLink);
$("#dgLink").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); dgThemLink(); } });
$("#dgThan").addEventListener("click", (e) => {
  const n = e.target.closest("[data-chon]"); if (!n) return;
  if (!hoSo(S.hs)) { bao("Tạo hồ sơ kênh trước đã", true); return; }
  const c = n.dataset.chon;
  chonTepTrinhDuyet({ chinh: "video", phu: "tat-ca", "thu-muc": "thu-muc", mau: "mau" }[c], c === "thu-muc" ? "phu" : c);
});
for (const k of ["dragover", "dragleave", "drop"]) $("#dgThan").addEventListener(k, (e) => {
  const m = e.target.closest?.(".dg-muc");
  document.querySelectorAll(".dg-muc.tha").forEach((x) => { if (x !== m || k !== "dragover") x.classList.remove("tha"); });
  if (m && k === "dragover" && coFile(e)) m.classList.add("tha");
});

const coKho = (e) => [...(e.dataTransfer?.types || [])].includes("application/x-kho");
addEventListener("dragenter", (e) => { if (coFile(e)) { demKeo++; if (!dgBat()) $("#lopTha").hidden = false; } else if (coKho(e)) $("#soan").classList.add("tha-vao"); });
addEventListener("dragleave", (e) => { if (coFile(e) && --demKeo <= 0) { demKeo = 0; $("#lopTha").hidden = true; } });
addEventListener("dragover", (e) => { if (coFile(e) || coKho(e)) e.preventDefault(); });
addEventListener("dragend", () => $("#soan").classList.remove("tha-vao"));
addEventListener("drop", (e) => {
  $("#soan").classList.remove("tha-vao");
  if (coKho(e)) { e.preventDefault(); try { themKho(JSON.parse(e.dataTransfer.getData("application/x-kho"))); } catch {} return; }
  if (!coFile(e)) return;
  e.preventDefault(); demKeo = 0; $("#lopTha").hidden = true;
  if (!hoSo(S.hs)) { bao("Tạo hồ sơ kênh trước đã", true); return; }
  if (S.view !== "chat") dongHoSo();
  S.dgTha = dgBat() ? (e.target.closest?.("[data-muc]")?.dataset.muc || null) : null;
  taiLen([...e.dataTransfer.files]);
  S.dgTha = null;
});

/* ---------- PHẢI ---------- */
function chonPhai(p) {
  S.phai = p;
  $$("#phaiThe button[data-p]").forEach((b) => b.classList.toggle("chon", b.dataset.p === p));
  $("#pQuyTrinh").hidden = p !== "quy-trinh"; $("#pKho").hidden = p !== "kho";
  $("#nutKhoRong").hidden = p !== "kho";
  if (p !== "kho") khoRong(false);
  if (p === "kho" && !S.kho.daTai) taiKho();
  if (p === "quy-trinh") veQuyTrinh();
}
$("#phaiThe").addEventListener("click", (e) => { const b = e.target.closest("button[data-p]"); if (b) chonPhai(b.dataset.p); });

// 1.2.19: KHO ĐẨY RỘNG tại chỗ — sidebar trái tự thu, kho chiếm ~60 % màn hình; bấm lại / Esc / đổi tab → thu về. Không mở cửa sổ mới.
function khoRong(bat) {
  const k = $("#khung");
  if (bat === undefined) bat = !k.classList.contains("kho-rong");
  if (bat && S.phai !== "kho") chonPhai("kho");
  k.classList.toggle("kho-rong", bat);
  if (bat) { k.classList.remove("an-phai"); if (innerWidth <= 1020) k.classList.add("mo-phai"); }
  const n = $("#nutKhoRong"); n.setAttribute("aria-pressed", bat ? "true" : "false"); n.title = bat ? "Thu kho về (Esc)" : "Đẩy rộng kho ra giữa màn hình (Esc để thu lại)";
  const m = $("#khoMoRong"); if (m) m.textContent = bat ? "⤡ Thu kho về" : "⤢ Đẩy rộng kho";
  nho.dat("khoRong", bat ? "1" : "");
}
$("#nutKhoRong").addEventListener("click", () => khoRong());
$("#khoMoRong").addEventListener("click", () => khoRong());

function veQuyTrinh() {
  if (!S.tq || !S.kd) return;
  const tb = S.kd.ten_buoc, dc = S.tq.dong_co;
  // một việc có thể dựng nhiều video — mỗi video một phiếu: phiếu mới nhất mở rộng, phiếu cũ thu gọn (bấm để mở)
  const ds = S.tq.phieu_ds?.length ? S.tq.phieu_ds : (S.tq.phieu ? [S.tq.phieu] : []);
  S.moPhieu ||= new Set();
  const vePhieu = (p, cuoi) => {
    const khoa = `${p.ten}|${p.mo_luc}`, xong = !!p.buoc["11"];
    const mo = cuoi ? !S.moPhieu.has("dong:" + khoa) : S.moPhieu.has(khoa);
    const hsP = hoSo(p.ho_so) || { kenh: p.ho_so, mau: "#888" };
    const ke = Object.keys(tb).find((k) => !p.buoc[k]);
    const daXong = Object.keys(p.buoc).length;
    const lat = () => { if (cuoi) S.moPhieu.has("dong:" + khoa) ? S.moPhieu.delete("dong:" + khoa) : S.moPhieu.add("dong:" + khoa); else S.moPhieu.has(khoa) ? S.moPhieu.delete(khoa) : S.moPhieu.add(khoa); veQuyTrinh(); };
    const dau = el("button", { type: "button", class: "phieu-dau", onclick: lat, "aria-expanded": String(mo) },
      el("p", { class: "nhan-muc" }, xong ? "✓ Phiếu đã giao" : "Phiếu đang mở", el("span", { class: "phieu-dem" }, `${daXong}/12`)),
      el("h3", {}, p.ten),
      el("div", { class: "phieu-tags" },
        el("span", { class: "tag-hs" }, el("i", { style: `background:${hsP.mau}` }), hsP.kenh),
        el("span", {}, { dung: "dựng video", hoc: "học từ video", "ho-so": "hồ sơ" }[p.loai] || p.loai),
        el("span", {}, "mở " + (p.mo_luc || "").slice(-5)),
        p.buoc["11"]?.dau_ra ? el("span", {}, "→ " + tenFile(p.buoc["11"].dau_ra)) : null));
    if (!mo) return el("div", { class: "phieu thu-gon" + (xong ? " da-giao" : "") }, dau);
    const buoc = Object.entries(tb).map(([k, ten]) => {
      const b = p.buoc[k], nhap = (p.nhap || {})[k];
      const lop = b ? "xong" : k === ke && !xong ? "ke" + (viecChay(S.viec) ? " chay" : "") : "";
      return el("li", { class: "buoc " + lop },
        el("span", { class: "so" }, b ? "✓" : k), el("span", { class: "ten" }, ten),
        b?.dau_ra ? el("span", { class: "ra", title: b.dau_ra }, (b.luc ? b.luc.slice(0, 5) + " · " : "") + b.dau_ra)
          : nhap?.length ? el("span", { class: "ra nhap", title: nhap.join("\n") }, `đang tra: ${nhap.length} lượt — ${nhap[nhap.length - 1].slice(6)}`) : null);
    });
    return el("div", { class: "phieu" }, dau, el("ol", { class: "buoc-ds" }, buoc),
      el("div", { class: "phieu-chan" }, p.ho_so !== S.hs ? `Phiếu này của hồ sơ “${hsP.kenh}”. ` : "",
        "Dựng thật cần đủ bước 1–7 (bước 5, 7 phải ghi lý do); giao cần 1–10 và ảnh bìa."));
  };
  const phieu = ds.length
    ? el("div", { class: "ds-phieu" },
      ds.length > 1 ? el("p", { class: "nhan-muc" }, `Phiếu của việc này · ${ds.length} video`) : null,
      ds.map((p, i) => vePhieu(p, i === ds.length - 1)))
    : el("div", {},
      el("p", { class: "phieu-trong" }, "Chưa có phiếu nào đang mở. Mỗi video đi 3 phần: ĐỌC (máy) · TƯ DUY (AI nghĩ một lần) · DỰNG (máy dựng một lần, AI nhìn lại). Luật cứng máy tự kiểm và tự sửa trong từng phần."),
      el("div", { class: "phieu mo-nhat" }, el("ol", { class: "buoc-ds" }, [
        ["1", "ĐỌC — máy đọc lời, mặt, cảnh, cắt lặng (~2 phút cho 1 phút quay)"],
        ["2", "TƯ DUY — AI nhìn khung hình, thiết kế toàn bộ video một lần (chữ, bố cục, nhạc, bìa)"],
        ["3", "DỰNG — máy kiểm luật chất lượng, dựng, vẽ 3 bìa; AI nhìn lại, sửa nếu cần, giao"],
      ].map(([k, ten]) => el("li", { class: "buoc" }, el("span", { class: "so" }, k), el("span", { class: "ten" }, ten))))));
  const hs = S.hsData && S.hsData.ten === S.hs ? S.hsData : null;
  if (!hs && S.hs && !S.dangTaiHs) taiHoSo();
  const khoi = hs ? el("div", { class: "khoi-phai" },
    el("h4", { class: "nhan-muc" }, "Đã ghi vào hồ sơ", el("button", { type: "button", onclick: () => moHoSo("lich-su") }, "Mở hồ sơ →")),
    el("div", { class: "so-hs" },
      el("div", {}, el("b", {}, hs.lich_su.filter((x) => x.loai === "dung").length), el("span", {}, "video đã giao")),
      el("div", {}, el("b", {}, hs.bai_hoc.length), el("span", {}, "bài đã học")),
      el("div", {}, el("b", {}, hs.gop_y.length), el("span", {}, "góp ý"))),
    el("ul", { class: "ls-mini" }, hs.lich_su.slice(0, 5).map((x) => el("li", {}, el("span", {}, x.ten), el("time", {}, (x.mo_luc || "").slice(5))))))
    : null;
  // đầu ra của việc đang xem: mỗi video đã giao một dòng có bìa — bấm để nhảy tới thẻ video trong chat
  const daGiao = (S.viecData?.tin || []).filter((t) => t.vai === "video");
  const dauRa = daGiao.length ? el("div", { class: "khoi-phai" },
    el("h4", { class: "nhan-muc" }, `Video đã giao · ${daGiao.length}`),
    el("div", { class: "ds-giao" }, daGiao.slice().reverse().map((t) => el("button", { type: "button", class: "giao-hang",
      onclick: () => { const n = [...$$(".the-video")].find((x) => x.dataset.tep === t.tep); if (S.view !== "chat") dongHoSo(); n?.scrollIntoView({ behavior: "smooth", block: "center" }); } },
      el("span", { class: "giao-bia", style: t.bia ? `background-image:url("${media(t.bia)}")` : "" }),
      el("span", { class: "giao-tt" }, el("b", {}, tenFile(t.tep)), el("small", {}, gio(t.luc) + " · bấm để xem"))))))
    : null;
  const p2 = vePhieu2DS();
  $("#pQuyTrinh").replaceChildren(...[dauRa, p2 || phieu, khoi].filter(Boolean));
}

/* kho */
const TEN_LOAI = { hieu_ung: "hiệu ứng", kieu_chu: "kiểu chữ", nhac: "nhạc", sfx: "SFX", font: "font", nen: "nền", chong: "lớp chồng", lut: "LUT", video: "video", icon: "icon", anh: "ảnh" };
async function taiKho(them = false) {
  const k = S.kho; k.daTai = true;
  if (!them) k.trang = 0;
  const r = await api(`/api/kho?loai=${k.loai}&q=${encodeURIComponent(k.q)}&trang=${k.trang}`).catch(() => ({ ds: [], tong: 0 }));
  k.ds = them ? k.ds.concat(r.ds) : r.ds; k.tong = r.tong;
  veKho();
}
function veKho() {
  const k = S.kho, nhom = S.kd?.kho?.nhom || [];
  $("#khoNhom").replaceChildren(...nhom.map((n) => el("button", { type: "button", class: n.ma === k.loai ? "chon" : "", onclick: () => { k.loai = n.ma; taiKho(); } }, n.ten, el("span", {}, n.so))));
  const ds = $("#khoDs");
  if (!k.ds.length) { ds.replaceChildren(el("p", { class: "kho-goi" }, k.q ? "Không thấy gì khớp." : "Kho trống ở mục này.")); return; }
  ds.replaceChildren(...k.ds.map(hangKho), k.ds.length < k.tong ? el("button", { class: "nut nut-phu kho-them", type: "button", onclick: () => { k.trang++; taiKho(true); } }, `Xem thêm (${k.tong - k.ds.length})`) : "");
  $$(".k-hang.font .k-ten", ds).forEach((n) => quanSat.observe(n));
}
const iconPhat = '<svg viewBox="0 0 24 24"><path d="M8 5.5v13l10-6.5z"/></svg>';
function hangKho(x) {
  const keo = (e) => { e.dataTransfer.setData("application/x-kho", JSON.stringify(x)); e.dataTransfer.setData("text/plain", x.ten); e.dataTransfer.effectAllowed = "copy"; };
  let dau, ten = x.ten, phu = "";
  if (x.loai === "hieu_ung") { dau = el("span", { class: "k-dau" }, x.so); phu = (x.che ? "tác giả chê · " : "") + x.dung_khi; ten = `${x.ten}`; }
  else if (x.loai === "kieu_chu") { dau = el("span", { class: "k-dau", style: x.mau[0] ? `color:${x.mau[0]}` : "" }, "Aa"); phu = x.dung_khi || x.nhom; }
  else if (x.loai === "nhac" || x.loai === "sfx") {
    dau = el("button", { class: "k-dau", type: "button", "aria-label": "Nghe thử", html: iconPhat, onclick: (e) => { e.stopPropagation(); ngheThu(x.duong, e.currentTarget.closest(".k-hang")); } });
    phu = [x.giay ? `${x.giay.toFixed(1)}s` : "", (x.the || []).slice(0, 3).join(", "), x.nhom].filter(Boolean).join(" · ");
  } else if (x.loai === "nen" || x.loai === "anh" || x.loai === "icon") {
    const anh = /\.(png|jpe?g|webp)$/i.test(x.duong);
    dau = el("button", { class: "k-dau", type: "button", onclick: () => anh && xemLon(media(x.duong, 1)) }, anh ? el("img", { src: media(x.duong, 1), loading: "lazy", alt: "" }) : "MP4");
    phu = [(x.the || []).slice(0, 3).join(", "), x.nhom].filter(Boolean).join(" · ");
  } else { dau = el("span", { class: "k-dau" }, (x.ten.split(".").pop() || "").slice(0, 4).toUpperCase()); phu = [(x.the || []).slice(0, 3).join(", "), x.nhom].filter(Boolean).join(" · "); }
  const tenNut = x.loai === "font" ? el("div", { class: "k-ten", "data-font": x.duong, title: x.ten }, "Dựng video " + x.ten.replace(/\.(ttf|otf)$/i, "")) : el("div", { class: "k-ten", title: ten }, ten);
  return el("div", { class: `k-hang ${x.loai}${x.che ? " che" : ""}`, draggable: "true", ondragstart: keo, title: x.duong || x.dung_khi || "" },
    dau, el("div", { class: "k-than" }, tenNut,
      el("div", { class: "k-phu" }, x.loai === "kieu_chu" && x.mau.length ? el("span", { class: "k-mau" }, x.mau.map((m) => el("i", { style: `background:${m}` }))) : null, phu)),
    el("button", { class: "k-them", type: "button", title: "Thêm vào yêu cầu", onclick: () => themKho(x) }, "+"));
}
let henTim;
$("#khoTim").addEventListener("input", (e) => { clearTimeout(henTim); henTim = setTimeout(() => { S.kho.q = e.target.value.trim(); taiKho(); }, 220); });
const fontNap = new Map();
function napFont(p) {
  if (fontNap.has(p)) return fontNap.get(p);
  const ho = "kho" + fontNap.size; fontNap.set(p, ho);
  new FontFace(ho, `url("${media(p, 1)}")`).load().then((f) => document.fonts.add(f)).catch(() => {});
  return ho;
}
const quanSat = new IntersectionObserver((ds) => { for (const d of ds) if (d.isIntersecting) { d.target.style.fontFamily = `"${napFont(d.target.dataset.font)}", var(--f-than)`; quanSat.unobserve(d.target); } }, { rootMargin: "120px" });
const nghe = $("#nghe");
function ngheThu(p, hang) {
  const dang = $(".k-hang.dang-nghe");
  if (dang === hang && !nghe.paused) { nghe.pause(); return; }
  nghe.src = media(p, 1); nghe.play().catch(() => {});
  dang?.classList.remove("dang-nghe"); hang.classList.add("dang-nghe");
}
nghe.addEventListener("pause", () => $(".k-hang.dang-nghe")?.classList.remove("dang-nghe"));

/* ---------- HỒ SƠ ---------- */
async function taiHoSo() {
  if (!S.hs) return; S.dangTaiHs = true;
  try { S.hsData = await api(`/api/ho-so/${S.hs}`); } catch { S.hsData = null; }
  S.dangTaiHs = false;
  if (S.phai === "quy-trinh") veQuyTrinh();
}
async function moHoSo(the) {
  if (!S.hs) return;
  S.view = "ho-so"; if (the) S.hsThe = the;
  hienView(); veTrai(); veDauGiua();
  await taiHoSo(); veHoSo();
}
function dongHoSo() { S.view = "chat"; hienView(); veTrai(); veDauGiua(); veTroChuyen(); }
$("#hsDong").addEventListener("click", dongHoSo);
$("#hsLuuTru").addEventListener("click", async () => {
  const h = hoSo(S.hs); if (!h) return;
  if (!confirm(`Lưu trữ hồ sơ “${h.kenh}”?\n\nHồ sơ và các việc của nó được cất đi, không hiện trong danh sách nữa. Dữ liệu không bị xoá (nằm ở nao/ca-nhan/.luu-tru).`)) return;
  try { await api(`/api/ho-so/${S.hs}/luu-tru`, {}); bao("Đã lưu trữ hồ sơ"); S.hs = ""; S.viec = null; S.view = "chat"; S.moc = {}; await lay(); chonViec(null); }
  catch (x) { bao(x.message, true); }
});
$("#hsXoa").addEventListener("click", async () => {
  const h = hoSo(S.hs); if (!h) return;
  const go = prompt(`XOÁ HẲN hồ sơ “${h.kenh}”?

Xoá: gu riêng, thương hiệu, thư viện học, góp ý và mọi đoạn chat của hồ sơ — KHÔNG lấy lại được.
Giữ nguyên: video đã giao và thư mục dự án.

Gõ đúng mã hồ sơ “${S.hs}” để xác nhận:`);
  if (go === null) return;
  if (go.trim() !== S.hs) { bao("Gõ chưa đúng mã hồ sơ — không xoá", true); return; }
  try { await api(`/api/ho-so/${S.hs}/xoa`, { xac_nhan: go.trim() }); bao("Đã xoá hồ sơ"); S.hs = ""; S.viec = null; S.view = "chat"; S.moc = {}; await lay(); chonViec(null); }
  catch (x) { bao(x.message, true); }
});
$("#hsThe").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { S.hsThe = b.dataset.the; veHoSo(); } });

const lay2 = (o, d) => d.split(".").reduce((a, k) => (a == null ? a : a[k]), o);
function dat2(o, d, v) { const k = d.split("."); let a = o; k.slice(0, -1).forEach((x) => (a = a[x] ||= {})); a[k[k.length - 1]] = v; }
function veHoSo() {
  const h = S.hsData; if (!h) return;
  const c = h.cau_hinh, mau = lay2(c, "mau.nhan") || hoSo(h.ten)?.mau;
  datMau(mau);
  $("#hsMau").textContent = viTat(lay2(c, "kenh.ten") || h.ten);
  $("#hsMa").textContent = `Hồ sơ · ${h.ten}` + (c._tu_bo ? ` · từ bộ ${c._tu_bo}` : "") + (h.dang_dung ? " · đang dùng" : "");
  $("#hsTen").textContent = lay2(c, "kenh.ten") || h.ten;
  $$("#hsThe button").forEach((b) => b.classList.toggle("chon", b.dataset.the === S.hsThe));
  const than = $("#hsThan");
  const ve = { "thuong-hieu": veThuongHieu, gu: veGu, hoc: veHoc, "lich-su": veLichSu }[S.hsThe];
  than.replaceChildren(...[ve(h)].flat().filter(Boolean));
}
function nhom(tieu, mo, ...truong) { return el("section", { class: "hs-nhom" }, el("div", {}, el("h3", {}, tieu), mo ? el("p", { class: "mo" }, mo) : null), el("div", { class: "truong-ds" }, truong)); }
function veThuongHieu(h) {
  const sua = JSON.parse(JSON.stringify(h.cau_hinh));
  const o_ = (nhan, d, kieu = "text", rong) => {
    const v = lay2(sua, d) ?? "";
    if (kieu === "mau") {
      const t = el("input", { value: v, maxlength: 7, spellcheck: "false" });
      const m = el("input", { type: "color", value: /^#[0-9a-f]{6}$/i.test(v) ? v : "#000000", "aria-label": nhan });
      m.addEventListener("input", () => { t.value = m.value.toUpperCase(); dat2(sua, d, t.value); if (d === "mau.nhan") datMau(t.value); });
      t.addEventListener("input", () => { if (/^#[0-9a-f]{6}$/i.test(t.value)) { m.value = t.value; dat2(sua, d, t.value.toUpperCase()); if (d === "mau.nhan") datMau(t.value); } });
      return el("label", {}, nhan, el("div", { class: "mau-truong" }, m, t));
    }
    const i = el("input", { value: v, type: kieu === "so" ? "number" : "text", step: "any", list: kieu === "font" ? "dsFont" : null, spellcheck: "false" });
    i.addEventListener("input", () => dat2(sua, d, kieu === "so" ? (i.value === "" ? null : +i.value) : i.value));
    return el("label", { class: rong ? "rong" : "" }, nhan, i);
  };
  const bo3 = lay2(sua, "phong_cach.bo_3_mau") || ["#FFFFFF", "#101012", "#FFD200"];
  dat2(sua, "phong_cach.bo_3_mau", bo3);
  const mau3 = ["Sáng", "Tối", "Nhấn"].map((n, i) => {
    const t = el("input", { value: bo3[i] || "", maxlength: 7 }), m = el("input", { type: "color", value: /^#[0-9a-f]{6}$/i.test(bo3[i]) ? bo3[i] : "#000000" });
    m.addEventListener("input", () => { t.value = m.value.toUpperCase(); bo3[i] = t.value; });
    t.addEventListener("input", () => { if (/^#[0-9a-f]{6}$/i.test(t.value)) { m.value = t.value; bo3[i] = t.value.toUpperCase(); } });
    return el("label", {}, `Bộ 3 màu · ${n}`, el("div", { class: "mau-truong" }, m, t));
  });
  napDsFont();
  // 1.2.15: mặc định AI chọn màu nhấn + font RIÊNG cho từng video; tick "Khoá" = mọi video của hồ sơ luôn dùng đúng giá trị ở đây
  const khoaO = (nhan, k) => {
    const ds = (sua.khoa ||= []);
    const c = el("input", { type: "checkbox" }); c.checked = ds.includes(k);
    c.addEventListener("change", () => { const i = ds.indexOf(k); if (c.checked && i < 0) ds.push(k); if (!c.checked && i >= 0) ds.splice(i, 1); });
    return el("label", { class: "bh-bat" }, c, nhan);
  };
  return [
    nhom("Kênh", "Tên hiện trên Studio và trong báo cáo giao.", o_("Tên kênh", "kenh.ten"), o_("Tên series", "kenh.seri")),
    nhom("Màu", "Màu nhấn của hồ sơ trên Studio. Trong video, AI tự chọn màu nhấn hợp từng video — tick Khoá nếu muốn mọi video luôn dùng màu thương hiệu này.", o_("Màu nhấn", "mau.nhan", "mau"), khoaO("Khoá màu nhấn cho mọi video", "mau_nhan"), o_("Màu nhấn phụ (tuỳ chọn)", "mau.nhan2", "mau"), o_("Chữ chính", "mau.chu_chinh", "mau"), o_("Nền thẻ", "mau.nen_card", "mau"), mau3),
    nhom("Sáng tạo", "Mức làm mới giữa các video khi bạn không đưa video mẫu. Màu gốc của video luôn được giữ (trừ khi bạn yêu cầu hoặc chọn phong cách).",
      (() => {
        const v = lay2(sua, "sang_tao.muc") || "vua";
        const s_ = el("select", {}, [["giu", "Giữ đúng chất kênh — ít thay đổi"], ["vua", "Làm mới vừa phải (khuyên dùng)"], ["tao_bao", "Thử nghiệm táo bạo"]]
          .map(([k, t]) => el("option", { value: k, selected: k === v ? "" : null }, t)));
        s_.addEventListener("change", () => dat2(sua, "sang_tao.muc", s_.value));
        return el("label", { class: "rong" }, "Mức sáng tạo", s_);
      })()),
    nhom("Chữ", "Để trống / không khoá = AI chọn font hợp từng video từ kho (đủ dấu tiếng Việt). Tick Khoá để mọi video luôn dùng font ở đây.", o_("Phụ đề", "chu.phu_de", "font"), khoaO("Khoá font phụ đề", "font_phu_de"), o_("Tiêu đề lớn", "chu.title_to", "font"), khoaO("Khoá font tiêu đề", "font_tieu_de"), o_("Ảnh bìa", "chu.bia", "font")),
    nhom("Nhịp & âm thanh", "Mức đích khi trộn; càng gần 0 càng to.", o_("Tốc độ nói (×)", "dung.toc_do", "so"), o_("Giọng (LUFS)", "am_thanh.giong", "so"), o_("Nhạc nền (LUFS)", "am_thanh.nhac", "so"), o_("Âm lượng cuối (LUFS)", "am_thanh.dich_cuoi", "so")),
    nhom("Từ cần giữ nguyên", "Tên sản phẩm, thương hiệu, thuật ngữ của kênh. Claude không bao giờ tự “sửa” những từ này khi nhận giọng nói.",
      (() => {
        const i = el("input", { value: (lay2(sua, "tu_giu") || []).join(", "), placeholder: "viền nẻ, vải đũi, Tên Shop của bạn", spellcheck: "false" });
        i.addEventListener("input", () => dat2(sua, "tu_giu", i.value.split(",").map((x) => x.trim()).filter(Boolean)));
        return el("label", { class: "rong" }, "Danh sách, cách nhau bằng dấu phẩy", i);
      })()),
    nhom("Bìa & giao", "Để trống kiểu bìa = Claude thiết kế riêng theo anh-bia.md (tab Gu riêng).", o_("Kiểu bìa", "bia.kieu"), o_("Logo (đường dẫn file)", "logo.duong_dan"), o_("Thư mục giao video", "ban_giao.thu_muc", "text", true)),
    el("div", { class: "hs-luu" }, el("button", { class: "nut nut-chinh", type: "button", onclick: async () => {
      try { S.hsData = await api(`/api/ho-so/${h.ten}`, { cau_hinh: sua }); bao("Đã lưu hồ sơ"); S.moc = {}; lay(); veHoSo(); } catch (e) { bao(e.message, true); }
    } }, "Lưu thương hiệu")),
  ];
}
let daNapFont = false;
async function napDsFont() {
  if (daNapFont) return; daNapFont = true;
  const r = await api("/api/kho?loai=font&n=1000").catch(() => ({ ds: [] }));
  document.body.append(el("datalist", { id: "dsFont" }, r.ds.map((f) => el("option", { value: f.ten }))));
}
function veGu(h) {
  const pc = el("textarea", { class: "md-o" }); pc.value = h.phong_cach;
  const ab = el("textarea", { class: "md-o", style: "min-height:160px" }); ab.value = h.anh_bia;
  return [
    nhom("Phong cách", "Luật riêng của kênh: Thích · Cấm · Ảnh bìa. Chỉ ghi điều bạn đã nói hoặc đã duyệt — luật gốc của nghề vẫn áp dụng.", el("label", { class: "rong" }, "phong-cach.md", pc)),
    nhom("Ảnh bìa", "Mô tả kiểu bìa của kênh (bố cục, chữ, màu). Claude đọc file này khi làm bìa.", el("label", { class: "rong" }, "anh-bia.md", ab)),
    el("div", { class: "hs-luu" }, el("button", { class: "nut nut-chinh", type: "button", onclick: async () => {
      try { S.hsData = await api(`/api/ho-so/${h.ten}`, { phong_cach: pc.value, anh_bia: ab.value }); bao("Đã lưu gu riêng"); } catch (e) { bao(e.message, true); }
    } }, "Lưu gu riêng")),
  ];
}
function veHoc(h) {
  // 1.2.15: TAB HỌC của hồ sơ — tách khung → AI phân tích chi tiết kỹ thuật → hành động cho máy dựng → máy dựng lại so với gốc
  const links = el("textarea", { class: "link-o", placeholder: "Dán link video TikTok / Facebook / YouTube, mỗi dòng một link\nhttps://www.tiktok.com/@kenh/video/…\nhttps://www.facebook.com/reel/…" });
  const ghi = el("input", { placeholder: "Muốn học gì? Ví dụ: cách mở đầu 3 giây, kiểu chữ chạy, cách chèn thẻ bằng chứng" });
  const tep = [];
  const dsTep = el("ul", { class: "ds-dong rong" });
  const veTep = () => dsTep.replaceChildren(...(tep.length ? tep.map((p, i) => el("li", {}, el("span", {}, el("span", { class: "the-tag" }, "máy"), p.split(/[\/]/).pop()),
    el("button", { class: "nut", type: "button", onclick: () => { tep.splice(i, 1); veTep(); } }, "Bỏ"))) : [el("span", { class: "rong" }, "Chưa chọn video nào trên máy.")]));
  veTep();
  const chon = async () => {
    try { const r = await chonTepMay("video"); (r.tep || []).forEach((p) => { if (!tep.includes(p)) tep.push(p); }); veTep(); }
    catch (e) { bao(e.message, true); }
  };
  const nguon = h.nguon_hoc || [];
  const hoc = async () => {
    const ds = links.value.split(/\s+/).map((x) => x.trim()).filter((x) => /^https?:\/\//.test(x));
    if (!ds.length && !tep.length) { bao("Dán link hoặc chọn ít nhất một video", true); return; }
    try {
      if (ds.length) {
        const moi = nguon.concat(ds.filter((u) => !nguon.some((n) => n.url === u)).map((u) => ({ url: u, nen_tang: /tiktok/.test(u) ? "tiktok" : /facebook|fb\.watch/.test(u) ? "facebook" : /youtu/.test(u) ? "youtube" : "khác", them_luc: Date.now() / 1000 })));
        await api(`/api/ho-so/${h.ten}`, { nguon_hoc: moi });
      }
      const v = await api(`/api/ho-so/${h.ten}/hoc`, { links: ds, tep, ghi_chu: ghi.value });
      bao("Đã giao việc học — AI tách khung, phân tích rồi báo lại đã học gì"); S.moc = {}; await lay(); chonViec(v.id);
    } catch (e) { bao(e.message, true); }
  };
  const tv = h.thu_vien_hoc || [];
  const suaBai = async (id, body) => { try { S.hsData = await api(`/api/ho-so/${h.ten}/hoc/${id}`, body); veHoSo(); } catch (e) { bao(e.message, true); } };
  const theBai = (x) => {
    const bat = el("input", { type: "checkbox" }); bat.checked = x.bat !== false;
    bat.addEventListener("change", () => suaBai(x.id, { bat: bat.checked }));
    const ul = (ds) => el("ul", { class: "bh-ds" }, ...(ds.length ? ds.map((t) => el("li", {}, t)) : [el("li", { class: "mo" }, "—")]));
    return el("article", { class: "bh-the" + (x.bat === false ? " tat" : "") },
      el("header", {}, el("div", {}, el("strong", {}, x.ten), el("span", { class: "mo" }, ` · ${x.nguon || "?"} · ${x.luc || ""}`)),
        el("div", { class: "bh-nut" }, el("label", { class: "bh-bat" }, bat, x.bat === false ? "Đang tắt" : "AI đang dùng"),
          el("button", { class: "nut", type: "button", onclick: () => { if (confirm(`Xoá bài học «${x.ten}»?`)) suaBai(x.id, { xoa: true }); } }, "Xoá"))),
      x.anh ? el("a", { class: "bh-anh", href: `/api/ho-so/${h.ten}/hoc/${x.id}.jpg`, target: "_blank", title: "Bảng khung mẫu (hoặc đối chiếu gốc | máy dựng lại nếu đã chạy vòng kiểm) — bấm để xem to" },
        el("img", { src: `/api/ho-so/${h.ten}/hoc/${x.id}.jpg`, alt: "bảng khung mẫu / đối chiếu", loading: "lazy" })) : null,
      el("div", { class: "bh-2cot" }, el("div", {}, el("h4", {}, "Đã học"), ul(x.da_hoc || [])), el("div", {}, el("h4", {}, "Hành động cho AI"), ul(x.hanh_dong || []))),
      el("p", { class: "mo" }, `Hợp: ${(x.hop || []).join(", ") || "—"} · Cần tư liệu: ${(x.can || []).join(", ") || "không"}` + ((x.thieu || []).length ? ` · Máy chưa làm được: ${x.thieu.join(", ")}` : "")));
  };
  return [
    nhom("Dạy cho hồ sơ này", "AI tách khung từng khoảnh khắc có chuyện trong video mẫu, đọc và phân tích chi tiết kỹ thuật (chữ, đồ hoạ, nhịp, camera, âm thanh), viết thành HÀNH ĐỘNG cho máy dựng, rồi máy dựng lại để so với gốc. Chỉ học cách làm — không chép nội dung, logo, tên kênh.",
      el("label", { class: "rong" }, "Link video", links),
      el("div", { class: "rong", style: "display:flex;gap:10px;align-items:center" }, el("button", { class: "nut", type: "button", onclick: chon }, "Chọn video trên máy…")),
      dsTep, el("label", { class: "rong" }, "Ghi chú cho AI (tuỳ chọn)", ghi),
      el("div", { class: "rong", style: "display:flex;gap:10px" }, el("button", { class: "nut nut-chinh", type: "button", onclick: hoc }, "Bắt đầu học"))),
    nhom(`Đã học (${tv.length})`, "Mỗi bài: AI đã học gì và hành động nó sẽ dùng. Bài đang bật thì AI thấy trong mọi video của hồ sơ này và TỰ quyết dùng khi hợp nội dung. Tắt để AI bỏ qua.",
      el("div", { class: "rong bh-lua" }, ...(tv.length ? tv.map(theBai) : [el("span", { class: "rong" }, "Chưa có bài nào — dạy hồ sơ bằng một vài video mẫu ở trên.")]))),
    nhom("Nguồn đã đưa", `${nguon.length} link`, el("ul", { class: "ds-dong rong" }, nguon.length ? nguon.slice().reverse().map((n) => el("li", {}, el("span", {}, el("span", { class: "the-tag" }, n.nen_tang), n.url), el("span", { class: "n" }, luc(n.them_luc)))) : el("span", { class: "rong" }, "Chưa có."))),
    nhom("Bài nguyên tắc (não)", "Bài học dạng nguyên tắc chung của hồ sơ trong tầng kiến thức của não.", el("ul", { class: "ds-dong rong" }, h.bai_hoc.length ? h.bai_hoc.map((b) => el("li", {}, el("span", {}, b.tieu || b.file), el("span", { class: "n" }, b.ngay), el("span", { class: "p" }, `${b.nguon} · tin cậy ${b.tin_cay} · ${b.the}`))) : el("span", { class: "rong" }, "Chưa có."))),
  ];
}
function veLichSu(h) {
  return [
    nhom("Việc đã giao", "Mỗi dòng là một phiếu đã giao (skill lưu ở .phieu-cu).", el("ul", { class: "ds-dong rong" }, h.lich_su.length ? h.lich_su.map((x) => el("li", {},
      el("span", {}, el("span", { class: "the-tag" }, { dung: "dựng", hoc: "học", "ho-so": "hồ sơ" }[x.loai] || x.loai), x.ten), el("span", { class: "n" }, x.mo_luc),
      x.giao ? el("span", { class: "p" }, el("button", { class: "nut-nho", type: "button", onclick: () => api("/api/mo-thu-muc", { p: x.giao }).catch((e) => bao(e.message, true)) }, "Mở thư mục"), " ", x.giao) : null,
      x.gop_y ? el("span", { class: "p" }, "Góp ý: " + x.gop_y) : null)) : el("span", { class: "rong" }, "Chưa giao việc nào."))),
    nhom("Góp ý cho cả kênh", "1.2.21: góp ý được AI chuyển thành QUYẾT ĐỊNH KÊNH (quyet-dinh.json, giữ lịch sử, hoàn tác được) — máy không tự đặt số.",
      veGopYKenh(h),
      el("ul", { class: "ds-dong rong" }, h.gop_y.length ? h.gop_y.map((g) => el("li", {}, el("span", {}, g[1]), el("span", { class: "n" }, g[0]), el("span", { class: "p" }, [g[2], g[3]].filter(Boolean).join(" · ")))) : el("span", { class: "rong" }, "Chưa có góp ý."))),
  ];
}
/* 1.2.21 (A4): ô gửi góp ý kênh → POST /api/ho-so/<hs>/gop-y — "Cần AI…" là lời nhắc, không phải lỗi; có tep_quyet_dinh → "đã lưu quyết định kênh (phiên n)" */
function veGopYKenh(h) {
  const o = el("input", { placeholder: "vd: lần sau phụ đề để giữa, bỏ nhạc, chữ to hơn", "aria-label": "Góp ý cho kênh", style: "flex:1;min-width:200px" });
  const nut = el("button", { class: "nut nut-chinh", type: "submit" }, "Gửi góp ý");
  const kq = el("div", { class: "ht-ghi", style: "width:100%;margin-top:6px" });
  const f = el("form", { style: "display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:8px", onsubmit: async (e) => {
    e.preventDefault();
    const cau = o.value.trim(); if (!cau) return;
    nut.disabled = true; nut.textContent = "AI đang chuyển… (1–3 phút)"; kq.textContent = "";
    try {
      const r = await api(`/api/ho-so/${h.ten}/gop-y`, { cau });
      const dong = [];
      if (r.can_ai) dong.push(el("span", {}, r.tom_tat || "Cần AI để chuyển góp ý thành quyết định kênh — đăng nhập Claude ở bảng Máy rồi gửi lại."));
      else {
        if (r.tom_tat) dong.push(el("span", {}, r.tom_tat));
        if (r.tep_quyet_dinh) dong.push(el("b", { style: "color:var(--xong)" }, ` · đã lưu quyết định kênh${r.phien != null ? ` (phiên ${r.phien})` : ""}`));
        if ((r.loi_quyet_dinh || []).length) dong.push(el("span", { style: "color:var(--cat)" }, " · chưa lưu, sai khuôn: " + r.loi_quyet_dinh.slice(0, 3).join("; ")));
        if ((r.loi_schema || []).length) dong.push(el("span", { style: "color:var(--cat)" }, " · Style Spec chưa đổi: " + r.loi_schema.slice(0, 2).join("; ")));
      }
      kq.replaceChildren(...dong); o.value = "";
      if (!r.can_ai) api(`/api/ho-so/${h.ten}`).then((hs) => { S.hsData = hs; }).catch(() => {});
    } catch (x) { kq.replaceChildren(el("span", { style: "color:var(--cat)" }, x.message)); }
    nut.disabled = false; nut.textContent = "Gửi góp ý";
  } }, o, nut, kq);
  return f;
}

/* ---------- tạo hồ sơ ---------- */
const MAU_KENH = ["#FFD200", "#FF5B4A", "#FF8A3D", "#F25FA4", "#A979FF", "#4C9EFF", "#2EC4B6", "#5BD16E", "#E8E2D4", "#9AA0A6"];
let taoMau = MAU_KENH[0], taoBo = "";
$("#nutTaoHoSo").addEventListener("click", moTao);
function moTao() {
  $("#taoKenh").value = ""; $("#taoMa").value = "";
  const dung = S.tq?.ho_so.map((h) => h.mau.toUpperCase()) || [];
  taoMau = MAU_KENH.find((m) => !dung.includes(m)) || MAU_KENH[0]; taoBo = "";
  veTaoMau(); veTaoBo(); $("#hopTao").showModal(); $("#taoKenh").focus();
}
function veTaoMau() {
  datMau(taoMau);
  const tuy = el("input", { type: "color", value: taoMau, title: "Màu khác", oninput: (e) => { taoMau = e.target.value.toUpperCase(); veTaoMau(); } });
  $("#taoMauDs").replaceChildren(...MAU_KENH.map((m) => el("button", { type: "button", class: m === taoMau ? "chon" : "", style: `background:${m}`, "aria-label": m, onclick: () => { taoMau = m; veTaoMau(); } })), tuy);
}
function veTaoBo() {
  const ds = [{ ma: "", ten: "Trống", hop: "Tự dựng gu từ đầu bằng 6 câu hỏi", mau: [] }, ...(S.kd?.bo || [])];
  $("#taoBo").replaceChildren(...ds.map((b) => el("button", { type: "button", class: "bo" + (b.ma === taoBo ? " chon" : ""), onclick: () => { taoBo = b.ma; veTaoBo(); } },
    el("b", {}, b.ten.replace(/\s*\(.*\)/, "")), b.mau.length ? el("span", { class: "k-mau" }, b.mau.map((m) => el("i", { style: `background:${m}` }))) : null, el("span", {}, b.hop))));
}
$("#taoKenh").addEventListener("input", (e) => { $("#taoMa").placeholder = e.target.value.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/gi, "d").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "tự tạo từ tên kênh"; });
$("#taoHuy").addEventListener("click", () => $("#hopTao").close());
$("#hopTao").addEventListener("close", () => datMau(hoSo(S.hs)?.mau));
$("#formTao").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const gu = { ve: $("#taoVe").value.trim(), cam_giac: $("#taoCam").value.trim(), cam: $("#taoCam2").value.trim(), link: $("#taoLink").value.trim() };
    const r = await api("/api/ho-so", { kenh: $("#taoKenh").value.trim(), mau: taoMau, bo: taoBo, ma: $("#taoMa").value.trim(), gu });
    $("#hopTao").close(); bao("Đã tạo hồ sơ"); await lay(); chonHoSo(r.ten); await chonViec(null);
    ["#taoVe", "#taoCam", "#taoCam2", "#taoLink"].forEach((s) => { const e = $(s); if (e) e.value = ""; });
    o.value = gu.link ? "Học phong cách từ link mình vừa ghi trong hồ sơ (thẻ Học từ video), rồi hỏi mình thêm nếu còn thiếu." : "Hỏi mình 6 câu trong HOI.md để hoàn thiện hồ sơ kênh này (màu, gu, thứ cấm, kiểu bìa)."; tuCao(); nutGui();
  } catch (x) { bao(x.message, true); }
});

/* ---------- bản quyền & cập nhật ---------- */
$("#nutHeThong").addEventListener("click", () => { veHeThong(); $("#hopHT").showModal(); });
$("#htDong").addEventListener("click", () => $("#hopHT").close());

/* ---------- Giọng nói AI ---------- */
$("#nutGiong").addEventListener("click", () => { $("#hopGiong").showModal(); veGiong(); });
$("#giongDong").addEventListener("click", () => $("#hopGiong").close());
function themGiongVaoChat(tep, ten) {
  if (!hoSo(S.hs)) { bao("Chọn một hồ sơ kênh trước", true); return; }
  if (!S.dinh.some((d) => d.duong_dan === tep)) S.dinh.push({ kind: "giong", ten: ten || tenFile(tep), duong_dan: tep });
  if (S.view !== "chat") dongHoSo();
  veDinh(); if (!o.value.trim()) o.value = "Lồng giọng này vào video"; tuCao(); nutGui();
  $("#hopGiong").close(); o.focus();
}
async function veGiong(doiKhoa) {
  const t = $("#giongThan"); t.replaceChildren(el("p", { class: "giong-cho" }, "Đang tải…"));
  let st; try { st = await api("/api/giong"); } catch (e) { st = { co_khoa: null, loi_mang: e.message }; }
  if (st.loi_mang && !doiKhoa) {                                   // 1.2.19: lỗi nối máy chủ ≠ chưa có khoá — không bắt dán lại khoá
    t.replaceChildren(el("p", { class: "giong-loi" }, "Không nối được máy chủ giọng nói (mạng, tường lửa hoặc proxy) — khoá của bạn vẫn còn. Thử lại sau, hoặc kiểm tra mạng."),
      el("button", { class: "nut nut-phu", type: "button", onclick: () => veGiong() }, "Thử lại"), " ",
      el("a", { href: "#", onclick: (e) => { e.preventDefault(); veGiong(true); } }, "đổi khoá"));
    return;
  }
  if (!st.co_khoa || doiKhoa) {
    const inp = el("input", { placeholder: "aizn_… (khoá giọng nói của bạn)", "aria-label": "Khoá giọng nói" });
    t.replaceChildren(
      el("p", { class: "hop-mo" }, "Dán khoá API giọng nói của bạn (lấy ở trang ", el("b", {}, "aizening.com"), " → Nối Claude AI / khoá API). Mỗi người một khoá; khoá lưu trên máy bạn."),
      el("form", { onsubmit: async (e) => {
        e.preventDefault(); const k = inp.value.trim(); if (k.length < 20) return bao("Khoá chưa đúng", true);
        const n = e.target.querySelector("button"); n.disabled = true; n.textContent = "Đang lưu…";
        try { const r = await api("/api/giong/khoa", { khoa: k }); if (r.ok || r.co_khoa) { bao(r.canh_bao ? "Đã lưu khoá (chưa kiểm được với máy chủ: " + r.canh_bao + ")" : "Đã lưu khoá — máy chủ xác nhận" + (r.quota?.con != null ? `, còn ${r.quota.con} lượt` : "")); veGiong(); } else bao(r.loi || "Không lưu được", true); }
        catch (x) { bao(x.message, true); } n.disabled = false; n.textContent = "Lưu khoá";
      } }, inp, el("button", { class: "nut nut-chinh" }, "Lưu khoá")));
    return;
  }
  const q = st.quota || {}; const conLuot = (q.con == null) ? "" : ` · còn ${q.con} lượt hôm nay`;
  let voices = []; try { voices = (await api("/api/giong/voices")).voices || []; } catch (e) {}
  const sel = el("select", { class: "giong-sel", "aria-label": "Chọn giọng" },
    ...(voices.length ? voices : [{ index: 0, ten: "Giọng mặc định" }]).map((v) => el("option", { value: String(v.index) }, `${v.index} — ${v.ten}`)));
  // 1.2.11: nghe thử giọng trước khi tạo (mẫu có sẵn → không tốn lượt)
  const ngheThu = el("audio", { style: "display:none" });
  const nutThu = el("button", { class: "nut nut-phu giong-thu", type: "button", title: "Nghe thử giọng này" }, "▶ Nghe thử");
  nutThu.addEventListener("click", async () => {
    nutThu.disabled = true; const cu = nutThu.textContent; nutThu.textContent = "Đang mở…";
    try {
      const v = voices.find((x) => String(x.index) === sel.value) || {};
      const r = await api("/api/giong/nghe-thu", { voice: sel.value, ten: v.ten || "" });
      if (!r.ok || !r.tep) { bao(r.loi || "Không nghe thử được", true); }
      else { ngheThu.src = media(r.tep); ngheThu.play().catch(() => {}); if (r.mat_luot) bao("Đã tạo mẫu nghe thử (dùng 1 lượt) — lần sau nghe lại không tốn lượt"); }
    } catch (x) { bao(x.message, true); }
    nutThu.disabled = false; nutThu.textContent = cu;
  });
  sel.addEventListener("change", () => { ngheThu.pause(); });
  const ta = el("textarea", { class: "giong-ta", rows: "3", placeholder: "Gõ lời cần đọc thành giọng…" });
  const kq = el("div", { class: "giong-kq" });
  const nghe = el("audio", { controls: true, style: "width:100%;margin-top:8px", hidden: true });
  const tao = async (clone, mau) => {
    const text = ta.value.trim(); if (!text) return bao("Gõ lời cần đọc", true);
    kq.replaceChildren(el("p", { class: "giong-cho" }, el("span", { class: "spin" }), "Đang tạo giọng (20–60 giây)…")); nghe.hidden = true;
    try {
      const r = await api("/api/giong/tao", { text, voice: sel.value, ten: text.slice(0, 30), clone: clone ? 1 : "", mau: mau || "" });
      if (!r.ok || !r.tep) { kq.replaceChildren(el("p", { class: "giong-loi" }, r.loi || "Không tạo được giọng")); return; }
      nghe.src = media(r.tep); nghe.hidden = false;
      kq.replaceChildren(nghe,
        el("div", { class: "giong-nut" },
          el("button", { class: "nut nut-chinh", type: "button", onclick: () => themGiongVaoChat(r.tep, text.slice(0, 24)) }, "Dùng cho video này"),
          el("button", { class: "nut nut-phu", type: "button", onclick: () => api("/api/mo-thu-muc", { p: r.tep }).catch((x) => bao(x.message, true)) }, "Mở thư mục")));
    } catch (x) { kq.replaceChildren(el("p", { class: "giong-loi" }, x.message)); }
  };
  t.replaceChildren(
    el("p", { class: "giong-quota" }, "Đọc văn bản thành giọng" + conLuot,
      " · ", el("a", { href: "#", onclick: (e) => { e.preventDefault(); veGiong(true); } }, "đổi khoá")),
    el("label", { class: "giong-nhan" }, "Giọng mẫu"), el("div", { class: "giong-chon" }, sel, nutThu, ngheThu),
    ta, el("div", { class: "giong-nut" }, el("button", { class: "nut nut-chinh", type: "button", onclick: () => tao(false) }, "Tạo giọng")),
    kq,
    el("details", { class: "giong-clone" }, el("summary", {}, "Nhân bản giọng của bạn (nâng cao)"),
      el("p", { class: "hop-mo" }, "Chọn một tệp .mp3 bạn nói rõ 10–60 giây, gõ lời cần đọc, rồi tạo — giọng ra sẽ giống giọng mẫu."),
      el("button", { class: "nut nut-phu", type: "button", id: "giongMau" }, "Chọn mp3 mẫu…"),
      el("span", { class: "giong-mau-ten", id: "giongMauTen" }, "")));
  $("#giongMau").addEventListener("click", async () => {
    try { const r = await chonTepMay("audio"); const m = (r.tep || [])[0];
      if (m) { $("#giongMauTen").textContent = tenFile(m); $("#giongMau").dataset.mau = m; $("#giongMau").textContent = "Tạo giọng nhân bản";
        $("#giongMau").onclick = () => tao(true, m); } } catch (x) { bao(x.message, true); }
  });
}
function veHeThong() {
  const ht = S.tq.he_thong, bq = ht.ban_quyen || {}, dc = S.tq.dong_co, kh = S.kd?.kho || {};
  const out = el("pre", { hidden: true });
  const fBQ = el("form", { onsubmit: kichHoat }, el("input", { placeholder: "EV123456-XXXX-XXXX-XXXX", "aria-label": "Mã bản quyền" }), el("button", { class: "nut nut-chinh" }, "Kích hoạt"));
  const kiemCN = async (e) => {
    const n = e.currentTarget; n.disabled = true; n.textContent = "Đang kiểm tra…";
    try { const r = await api("/api/cap-nhat"); out.hidden = false; out.textContent = r.chu; if (r.co_moi) cai.hidden = false; } catch (x) { bao(x.message, true); }
    n.disabled = false; n.textContent = "Kiểm tra bản mới";
  };
  const cai = el("button", { class: "nut nut-chinh", type: "button", hidden: true, onclick: async (e) => {
    const n = e.currentTarget; n.disabled = true; n.textContent = "Đang cài…";
    try { const r = await api("/api/cap-nhat/cai", {}); out.textContent = r.chu; bao(r.ok ? "Đã cập nhật — Studio đang mở lại bằng bản mới…" : "Cập nhật lỗi", !r.ok);
      if (r.khoi_dong_lai) setTimeout(function thu() { fetch("/api/ping").then((x) => x.ok ? location.reload() : setTimeout(thu, 1500)).catch(() => setTimeout(thu, 1500)); }, 3500); } catch (x) { bao(x.message, true); }
    n.disabled = false; n.textContent = "Cài bản mới";
  } }, "Cài bản mới");
  $("#htThan").replaceChildren(
    el("div", { class: "ht-dong" }, el("h4", {}, el("i", { class: "cham " + (bq.hop_le ? "tot" : "xau") }), "Bản quyền"), el("p", {}, bq.hop_le ? `Hợp lệ · ${chuBQ(bq.chu)}. Bản quyền trọn đời; máy tự xác nhận lại với máy chủ mỗi vài ngày khi có mạng.` : (bq.chu || "Chưa kích hoạt")), bq.hop_le ? null : fBQ),
    el("div", { class: "ht-dong" }, el("h4", {}, "Phiên bản ", ht.phien_ban), el("p", {}, "Cập nhật chỉ thay phần của người bán; hồ sơ, bài tự học, cấu hình máy giữ nguyên. Bản cập nhật phải có chữ ký số mới được cài."),
      el("div", { style: "display:flex;gap:8px" }, el("button", { class: "nut nut-phu", type: "button", onclick: kiemCN }, "Kiểm tra bản mới"), cai), out),
    el("div", { class: "ht-dong" }, el("h4", {}, el("i", { class: "cham " + (dc.san_sang ? "tot" : "xau") }), "Claude Code"), el("p", {}, dc.san_sang ? "Đã đăng nhập — Studio tự gọi Claude chạy ngầm." : `${dc.ly_do}.`),
      dc.san_sang ? null : el("button", { class: "nut nut-chinh", type: "button", onclick: dangNhapClaude }, "Đăng nhập Claude")),
    el("div", { class: "ht-dong" }, el("h4", {}, "Gói chẩn đoán"), el("p", {}, "Gặp lỗi khó tả? Bấm để gom nhật ký, việc gần nhất và thông số máy (không chứa khoá/mật khẩu) thành một tệp zip gửi người bán."),
      el("button", { class: "nut nut-phu", type: "button", onclick: async (e) => { const n = e.currentTarget; n.disabled = true; n.textContent = "Đang gom…";
        try { const r = await api("/api/chan-doan", {}); bao(`Đã tạo gói chẩn đoán ${r.mb} MB — ${r.tep}`); api("/api/mo-thu-muc", { p: r.tep }).catch(() => {}); } catch (x) { bao(x.message, true); }
        n.disabled = false; n.textContent = "Xuất gói chẩn đoán"; } }, "Xuất gói chẩn đoán")),
    (() => {
      const bs = S.tq.bac_si || {}, kq = bs.kq || [];
      const nhanCham = (x) => "cham " + (x.ok ? "tot" : x.ok === false && x.bat_buoc !== false ? "xau" : "");
      return el("div", { class: "ht-dong" }, el("h4", {}, "Máy của bạn"),
        el("p", {}, "Studio tự kiểm các điều kiện cần để chạy. Mục đỏ cần sửa; các mục tuỳ chọn có thể làm sau."),
        el("ul", { class: "bs-ds" }, kq.map((x) => el("li", {}, el("i", { class: nhanCham(x) }), el("span", {}, x.ten + (x.bat_buoc === false ? " (tuỳ chọn)" : ""), el("small", {}, x.chi_tiet))))),
        bs.log?.length ? el("pre", {}, bs.log.slice(-12).join("\n")) : null,
        el("div", { style: "display:flex;gap:8px" },
          el("button", { class: "nut nut-phu", type: "button", onclick: () => api("/api/bac-si/kiem", {}).then(() => bao("Đang kiểm tra lại máy")) }, "Kiểm tra lại"),
          el("button", { class: "nut nut-chinh", type: "button", disabled: bs.dang_sua || null, onclick: () => tuSua().then(() => $("#hopHT").close()) }, bs.dang_sua ? "Đang tự sửa…" : "Tự sửa máy")));
    })(),
    veCaiDatMay(),
    veNangLucMay(),
    veDungLuong(),
    el("div", { class: "ht-dong" }, el("h4", {}, "Kho tài nguyên"), el("p", {}, "Kho sạch: ", el("code", {}, kh.goc || "—")), el("p", {}, "Bộ quà tặng: ", el("code", {}, kh.bo_mua || "chưa có"))));
}

/* ---------- 1.2.21 (1a): cài đặt máy — dựng cùng lúc, tăng tốc auto/cpu, dọn rác tự động ---------- */
function veCaiDatMay() {
  const ghi = el("div", { class: "ht-ghi" });
  const hop = el("div", { class: "ht-dong" }, el("h4", {}, "Máy: dựng cùng lúc · tăng tốc · dọn rác"), el("p", {}, "Đang đọc cài đặt…"), ghi);
  const luu = async (moi, chu) => {
    try { const cd = await api("/api/cai-dat", moi); ghi.textContent = chu || "Đã lưu."; S.caiDat = cd; return cd; }
    catch (e) { ghi.textContent = "Không lưu được: " + e.message; throw e; }
  };
  api("/api/cai-dat").then((cd) => {
    S.caiDat = cd;
    const tdn = cd.toi_da_nang, tuDong = !cd.song_song;
    const soSS = el("input", { type: "number", min: 1, max: 32, step: 1, value: tuDong ? String(tdn || 1) : String(cd.song_song), disabled: tuDong || null, "aria-label": "Số video dựng cùng lúc" });
    const oTD = el("input", { type: "checkbox", checked: tuDong || null });
    const apSS = () => {
      if (oTD.checked) { soSS.disabled = true; soSS.value = String(tdn || 1); return luu({ song_song: "" }, `Đã lưu — tự động theo máy (${cd.luong} luồng · ${cd.ram_gb} GB RAM → ${tdn} video cùng lúc).`); }
      soSS.disabled = false;
      const n = Math.max(1, Math.min(32, parseInt(soSS.value, 10) || 1)); soSS.value = String(n);
      return luu({ song_song: String(n) }, `Đã lưu — ${n} video dựng cùng lúc (áp dụng cho việc gửi tiếp theo).`);
    };
    oTD.addEventListener("change", apSS); soSS.addEventListener("change", apSS);
    const nutTT = (gt, nhan) => el("button", { type: "button", class: (cd.tang_toc || "auto") === gt ? "chon" : "", onclick: async (e) => {
      await luu({ tang_toc: gt }, gt === "cpu" ? "Đã lưu — chỉ dùng CPU: mọi bước dựng/đọc từ việc tiếp theo nhận STUDIO_CPU_ONLY=1 (không thử card đồ hoạ)." : "Đã lưu — tự động: máy tự đo card đồ hoạ, lỗi thì tự về CPU và nhớ.");
      [...e.currentTarget.parentElement.children].forEach((b) => b.classList.toggle("chon", b === e.currentTarget)); } }, nhan);
    const dr = cd.don_rac || {};
    const oDR = el("input", { type: "checkbox", checked: dr.tu_dong !== false || null });
    const oNg = el("input", { type: "number", min: 0, max: 10000, step: 1, value: String(dr.o_trong_toi_thieu_gb ?? 10) });
    const oGi = el("input", { type: "number", min: 0, max: 3650, step: 1, value: String(dr.giu_cache_ngay ?? 3) });
    const apDR = () => luu({ don_rac: { tu_dong: oDR.checked, o_trong_toi_thieu_gb: +oNg.value, giu_cache_ngay: +oGi.value } },
      oDR.checked ? `Đã lưu — tự dọn lúc mở, mỗi 6 giờ, và trước khi dựng nếu ổ trống < ${oNg.value} GB; cache dự án đã đóng giữ ${oGi.value} ngày.` : "Đã lưu — không tự dọn; bạn dọn tay ở khối Dung lượng.");
    [oDR, oNg, oGi].forEach((o) => o.addEventListener("change", apDR));
    hop.replaceChildren(el("h4", {}, "Máy: dựng cùng lúc · tăng tốc · dọn rác"),
      el("div", { class: "ht-may" },
        el("label", {}, "Dựng cùng lúc", el("span", { class: "hang" }, soSS, el("label", { style: "flex-direction:row;align-items:center;gap:5px" }, oTD, "tự động")),
          el("small", {}, `Máy này: ${cd.luong} luồng · ${cd.ram_gb} GB RAM → tự động ${tdn}. Số lớn hơn sức máy sẽ chậm, không nhanh hơn.`)),
        el("label", {}, "Tăng tốc phần cứng", el("span", { class: "hang" }, el("span", { class: "nut-bat" }, nutTT("auto", "Tự động"), nutTT("cpu", "Chỉ CPU"))),
          el("small", {}, "Card đồ hoạ lỗi lặp (NVENC, hwaccel) → chọn Chỉ CPU; chậm hơn nhưng chắc.")),
        el("label", {}, "Dọn rác tự động", el("span", { class: "hang" }, oDR, el("span", {}, "bật")),
          el("small", {}, "Chỉ xoá thứ máy tạo lại được (cache dự án đã đóng, bản chép tư liệu, cache trình duyệt).")),
        el("label", {}, "Dọn khi ổ dự án trống dưới (GB)", el("span", { class: "hang" }, oNg), el("small", {}, "trước khi gửi việc dựng")),
        el("label", {}, "Giữ cache dự án đã đóng (ngày)", el("span", { class: "hang" }, oGi), el("small", {}, "sửa lại video trong khoảng này không phải dựng lại từ đầu"))),
      ghi, veCaiDatKho());
  }).catch((e) => { hop.replaceChildren(el("h4", {}, "Máy"), el("p", {}, "Không đọc được cài đặt: " + e.message)); });
  return hop;
}

/* 1.2.21 (A6): cấu hình kho mới — cau-hinh.json → v3.kho; máy chủ kho đọc lúc bật nên đổi xong cần mở lại Studio */
function veCaiDatKho() {
  const ghi = el("div", { class: "ht-ghi" });
  const hop = el("div", { style: "margin-top:10px;border-top:1px dashed var(--vach-2);padding-top:8px" }, el("h4", {}, "Kho tài nguyên (tra theo nghĩa)"), el("p", {}, "Đang đọc…"), ghi);
  api("/api/cau-hinh-kho").then((k) => {
    const o = (ten, kieu, gt, them) => el("input", { type: kieu, value: String(gt), "aria-label": ten, ...them });
    const oBac = o("bac_it_dung", "number", k.bac_it_dung, { min: 0, max: 1, step: 0.01 }), oUV = o("so_ung_vien", "number", k.so_ung_vien, { min: 1, max: 50 }),
      oLS = o("n_lich_su", "number", k.n_lich_su, { min: 1, max: 500 }), oTh = o("thang_dem", "number", k.thang_dem, { min: 1, max: 120 }),
      oNong = el("input", { type: "checkbox", checked: k.lam_nong !== false || null }), oLuot = o("toi_da_luot", "number", k.toi_da_luot ?? 2, { min: 1, max: 10 });
    const luu = async () => {
      try { await api("/api/cau-hinh-kho", { bac_it_dung: +oBac.value, so_ung_vien: +oUV.value, n_lich_su: +oLS.value, thang_dem: +oTh.value, lam_nong: oNong.checked, toi_da_luot: +oLuot.value }); ghi.textContent = "Đã lưu vào cau-hinh.json — máy chủ kho đọc lúc bật: mở lại Studio để áp dụng; số lần nhắc AI áp dụng cho việc tiếp theo."; }
      catch (e) { ghi.textContent = "Không lưu được: " + e.message; }
    };
    [oBac, oUV, oLS, oTh, oNong, oLuot].forEach((x) => x.addEventListener("change", luu));
    hop.replaceChildren(el("h4", {}, "Kho tài nguyên (tra theo nghĩa)"),
      el("div", { class: "ht-may" },
        el("label", {}, "Ứng viên mỗi bảng", el("span", { class: "hang" }, oUV), el("small", {}, "số mục kho đưa cho AI chọn mỗi loại")),
        el("label", {}, "Lịch sử chống lặp (video)", el("span", { class: "hang" }, oLS), el("small", {}, "đếm tài nguyên đã dùng trong N video gần nhất")),
        el("label", {}, "Bậc “ít dùng”", el("span", { class: "hang" }, oBac), el("small", {}, "0–1, tỉ lệ dùng dưới mức này coi là ít dùng")),
        el("label", {}, "Đếm toàn máy (tháng)", el("span", { class: "hang" }, oTh), el("small", {}, "cửa sổ thống kê dùng tài nguyên")),
        el("label", {}, "Làm nóng ảnh/âm xem trước", el("span", { class: "hang" }, oNong, el("span", {}, "bật")), el("small", {}, "tắt trên máy yếu / kho lớn")),
        el("label", {}, "AI: số lần nhắc khi JSON hỏng", el("span", { class: "hang" }, oLuot), el("small", {}, "v3.ai.toi_da_luot — mỗi lần nhắc tốn một lượt AI"))),
      ghi);
  }).catch((e) => hop.replaceChildren(el("p", {}, "Không đọc được cấu hình kho: " + e.message)));
  return hop;
}

/* ---------- 1.2.21 (1b): khối NĂNG LỰC MÁY — bản kê đo bằng việc thật (phan-cung.json nang_luc), Đo lại / Thử lại GPU ---------- */
function veNangLucMay() {
  const than = el("div", {}, el("p", {}, "Đang đọc…"));
  const hop = el("div", { class: "ht-dong", id: "htNangLuc" }, el("h4", {}, "Năng lực máy"), than);
  const ve = async () => {
    let m;
    try { m = await api("/api/may"); } catch (e) { than.replaceChildren(el("p", {}, "Không đọc được: " + e.message)); return; }
    const nl = m.nang_luc || {}, ghi = el("div", { class: "ht-ghi" }, m.loi ? "Lần đo trước lỗi: " + m.loi : "");
    const doLai = async (e) => {
      const n = e.currentTarget; const cu = n.textContent; n.disabled = true; n.textContent = "Đang đo (~1 phút)…"; ghi.textContent = "Máy đang đo mã hoá, giải mã, tách người, nghe — để máy rảnh.";
      try { const r = await api("/api/may/do-lai", {}); bao(r.loi ? "Đo máy lỗi: " + r.loi : "Đã đo lại máy"); ve(); }
      catch (x) { ghi.textContent = x.message; n.disabled = false; n.textContent = cu; }
    };
    const hang = (ten, gt, phu) => el("tr", {}, el("td", {}, ten, phu ? el("small", {}, phu) : null), el("td", { class: "so" }, gt));
    const rows = [];
    for (const [enc, v] of Object.entries(nl.ma_hoa || {})) rows.push(hang("Mã hoá " + enc, v.loi ? "lỗi: " + v.loi : `${v.fps_1080x1920 ?? "?"} fps`, "1080×1920"));
    for (const [k, v] of Object.entries(nl.giai_ma || {})) rows.push(hang("Giải mã " + k.replace("|", " · ") + " bit", `${v.fps ?? "?"} fps`, v.hwaccel ? "hwaccel " + v.hwaccel : "CPU"));
    const tn = nl.tach_nguoi; if (tn) rows.push(hang("Tách người", tn.loi ? "lỗi: " + tn.loi : `${tn.ms_khung_540 ?? tn.ms_khung ?? "?"} ms/khung`, tn.provider ? "provider " + tn.provider : "mạng 512"));
    const ng = nl.nhan_giong; if (ng) rows.push(hang("Nghe (Whisper)", ng.loi ? "lỗi: " + ng.loi : `${ng.giay_moi_phut ?? "?"} giây / phút video`, (ng.model || "").split("/").pop()));
    const od = nl.o_dia; if (od) rows.push(hang("Ổ đĩa", `ghi ${od.mb_s ?? "?"} · đọc ${od.doc_mb_s ?? "?"} MB/s`));
    const loiNho = [...Object.entries(m.encoder_loi || {}).map(([k, v]) => `${k}: ${v?.lan || 1} lần${v?.loi ? " — " + String(v.loi).slice(0, 80) : ""}`),
      ...Object.keys(m.hwaccel_loi || {}).map((k) => `hwaccel ${k}`)];
    than.replaceChildren(
      el("p", {}, m.mo_ta_may || (rows.length ? "Chưa có dòng mô tả." : "Chưa đo — bấm “Đo lại máy” (khoảng 1 phút, lúc máy rảnh).")),
      rows.length ? el("table", { class: "bang-rac bang-may" }, el("tr", {}, el("th", {}, "Đo bằng việc thật"), el("th", {}, "Kết quả")), rows) : null,
      nl.luc ? el("small", { style: "color:var(--chu-3)" }, `Đo lúc ${nl.luc}${nl.tong_giay ? " · " + Math.round(nl.tong_giay) + " s" : ""}${nl.do_luc_may_ban ? " · máy đang bận lúc đo (số có thể thấp)" : ""}`) : null,
      loiNho.length ? el("p", { style: "color:var(--cat);margin-top:8px" }, "Lỗi phần cứng đã nhớ (không thử lại tới khi bấm): " + loiNho.join(" · ")) : null,
      el("div", { style: "display:flex;gap:8px;flex-wrap:wrap;margin-top:8px" },
        el("button", { class: "nut nut-phu", type: "button", disabled: m.dang_do || null, onclick: doLai }, m.dang_do ? "Đang đo…" : "Đo lại máy"),
        loiNho.length ? el("button", { class: "nut nut-chinh", type: "button", disabled: m.dang_do || null, onclick: doLai }, "Thử lại GPU") : null),
      ghi);
  };
  ve();
  return hop;
}

/* ---------- 1.2.21 (1h): khối DUNG LƯỢNG — thanh ổ trống, bảng nhóm rác, nút dọn ---------- */
function veDungLuong() {
  const than = el("div", {}, el("p", {}, "Đang quét…"));
  const hop = el("div", { class: "ht-dong", id: "htDungLuong" }, el("h4", {}, "Dung lượng"), than);
  const TEN_NHOM = { a: ["Tái tạo được", "bản chép tư liệu kéo thả, cache trình duyệt, bản Studio cũ, tệp tạm, ảnh xem trước kho cũ"],
                     b: ["Cache dự án đã đóng", "sprite, khúc, proxy, alpha, base, âm, web của video đã giao"],
                     c: ["Đầu ra trùng", "giao/*.mp4 khi Downloads còn bản, base cũ hơn bản mới nhất"] };
  const ve = async (moi) => {
    let r;
    try { r = await api("/api/don-rac" + (moi ? "?moi=1" : "")); } catch (e) { than.replaceChildren(el("p", {}, "Không quét được: " + e.message)); return; }
    const o = r.o || {}, nguong = r.cau_hinh?.o_trong_toi_thieu_gb ?? 10, thap = o.trong_gb != null && o.trong_gb < nguong;
    const pct = o.tong_gb ? Math.max(1, Math.round(100 * (o.tong_gb - o.trong_gb) / o.tong_gb)) : 0;
    const tt = r.tom_tat || {};
    const tongMB = ["a", "b", "c"].reduce((s, k) => s + (tt[k]?.mb || 0), 0);
    const dl = (mb) => (mb || 0) >= 1000 ? (mb / 1000).toFixed(1) + " GB" : Math.round(mb || 0) + " MB";
    const ghi = el("div", { class: "ht-ghi" });
    const don = async (nhom, xacNhan, nhan) => {
      const chuXN = nhom.length > 1 ? `Dọn mọi thứ tái tạo được (${dl(tongMB)})?` : `Dọn nhóm “${TEN_NHOM[nhom[0]][0]}” (${dl(tt[nhom[0]]?.mb)})?`;
      if (!confirm(chuXN + "\n\nChỉ xoá thứ máy tạo lại được; việc đang chạy, hồ sơ, công thức, video đã giao ra Downloads không bị đụng.")) return;
      ghi.textContent = "Đang dọn…";
      try {
        const k = await api("/api/don-rac", { nhom, ngay: 0, xac_nhan: !!xacNhan });
        ghi.textContent = `Đã dọn ${dl(k.xoa_mb)} (${k.so_tep} tệp, ${k.so_muc} mục)${k.loi?.length ? ` · ${k.loi.length} mục chưa xoá được (đang mở?)` : ""} — ổ còn ${k.o?.trong_gb} GB.`;
        bao(ghi.textContent); lay(); setTimeout(() => ve(true), 400);
      } catch (e) { ghi.textContent = "Dọn lỗi: " + e.message; }
    };
    than.replaceChildren(
      el("div", { class: "dl-thanh" + (thap ? " thap" : "") }, el("i", { style: `width:${pct}%` })),
      el("div", { class: "dl-so" }, el("span", {}, "Ổ chứa dự án ", el("code", {}, o.duong || "")), el("b", { class: thap ? "do" : "" }, `còn ${o.trong_gb ?? "?"} / ${o.tong_gb ?? "?"} GB${thap ? " — dưới ngưỡng " + nguong + " GB" : ""}`)),
      el("table", { class: "bang-rac" },
        el("tr", {}, ...["Nhóm", "Dọn được", "Số tệp", "Đang dùng", ""].map((h) => el("th", {}, h))),
        ...["a", "b", "c"].map((k) => { const t = tt[k] || {}; return el("tr", {},
          el("td", {}, TEN_NHOM[k][0], el("small", {}, TEN_NHOM[k][1] + (t.can_xac_nhan_mb ? ` · gói CapCut ${dl(t.can_xac_nhan_mb)} (hỏi trước khi xoá)` : ""))),
          el("td", { class: "so" }, dl(t.mb)),
          el("td", { class: "so" }, String(t.so_tep || 0)),
          el("td", { class: "so" }, t.dang_dung_mb ? dl(t.dang_dung_mb) : "—"),
          el("td", {}, el("button", { class: "nut nut-phu nut-nho", type: "button", disabled: !(t.mb || t.can_xac_nhan_mb) || null, onclick: () => don([k], k === "b" && t.can_xac_nhan_mb && confirm("Xoá cả gói tách lớp CapCut (.mov) của các dự án đã đóng? Chỉ nên xoá khi đã mở xong trong CapCut.")) }, "Dọn nhóm này"))); })),
      el("div", { style: "display:flex;gap:8px;flex-wrap:wrap;align-items:center" },
        el("button", { class: "nut nut-chinh", type: "button", disabled: !tongMB || null, onclick: () => don(["a", "b", "c"], false) }, `Dọn mọi thứ tái tạo được (${dl(tongMB)})`),
        el("button", { class: "nut nut-phu", type: "button", onclick: () => { than.replaceChildren(el("p", {}, "Đang quét lại…")); ve(true); } }, "Quét lại"),
        el("small", { style: "color:var(--chu-3)" }, `${r.so_muc} mục · “đang dùng” là của việc đang chạy, không xoá`)),
      ghi);
  };
  ve(false);
  return hop;
}

/* ---------- chạy ---------- */
(async function () {
  S.kd = await api("/api/khoi-dau").catch(() => ({ bo: [], ten_buoc: {}, kho: { nhom: [] } }));
  batKhoMoi();                                   // 1.2.21: cổng kho từ cấu hình
  await lay();
  if (S.viec) { await layViec(); veTroChuyen(); veDauGiua(); }
  setInterval(lay, 1200);
  setInterval(veDangLam, 1000);
})();


/* ---------- Studio 1.3: phiếu 3 phần (Đọc · Tư duy · Dựng) — kiểm tự động bên trong ---------- */
function vePhieu2DS() {
  const ds = S.tq?.phieu2_ds || [], B2 = S.kd?.buoc2;
  if (!ds.length || !B2?.buoc) return null;
  S.moPhieu ||= new Set();
  const dc = S.tq.dong_co;
  const ve1 = (p, cuoi) => {
    const khoa = "v2|" + p.du_an, xong = !!p.dong;
    const mo = cuoi ? !S.moPhieu.has("dong:" + khoa) : S.moPhieu.has(khoa);
    const hsP = hoSo(p.ho_so) || { kenh: p.ho_so, mau: "#888" };
    const daXong = Object.keys(p.buoc || {}).length;
    const ke = B2.buoc.find((b) => !p.buoc[b.id]);
    const lat = () => { const k = cuoi ? "dong:" + khoa : khoa; S.moPhieu.has(k) ? S.moPhieu.delete(k) : S.moPhieu.add(k); veQuyTrinh(); };
    const pc = p.thong_tin?.goi;
    const dau = el("button", { type: "button", class: "phieu-dau", onclick: lat, "aria-expanded": String(mo) },
      el("p", { class: "nhan-muc" }, xong ? "✓ Đã giao" : "Đang làm · 3 phần",
        el("span", { class: "phieu-dem" }, xong ? "3/3" : `phần ${Math.min(3, (p._eta?.phan ?? 0) + 1)}/3` + (p._eta?.con_lai ? ` · còn ~${phut(p._eta.con_lai)}` : ""))),
      el("h3", {}, p.ten),
      el("div", { class: "phieu-tags" },
        el("span", { class: "tag-hs" }, el("i", { style: `background:${hsP.mau}` }), hsP.kenh),
        pc ? el("span", {}, "phong cách /" + pc) : null,
        el("span", {}, "mở " + (p.mo_luc || "").slice(11, 16)),
        p._may ? el("span", { class: "tag-may", title: "Lựa chọn máy đo được cho video này (doc/nguon.json)" }, "Máy: " + p._may) : null),   // 1.2.21 (1b)
      el("div", { class: "thanh-tien" }, el("i", { style: `width:${Math.round(100 * daXong / B2.buoc.length)}%` })));
    if (!mo) return el("div", { class: "phieu thu-gon" + (xong ? " da-giao" : "") }, dau);
    // 1.3: 3 PHẦN (Đọc · Tư duy · Dựng) — bước con chỉ là mốc + phép kiểm tự động bên trong
    const P3 = B2.phan || [], eta = p._eta || {};
    const nhom = P3.map((ph, i) => {
      const bs = ph.buoc, so = bs.filter((b) => p.buoc[b]).length, xongP = so === bs.length;
      const dang = !xong && eta.phan === i;
      const congs = Object.entries(B2.cong).filter(([n, c]) => bs.includes(c.sau));
      return el("li", { class: "gd phan3" + (xongP ? " xong" : "") + (dang ? " dang" + (viecChay(S.viec) ? " chay" : "") : "") },
        el("p", { class: "gd-ten" }, `Phần ${i + 1} · ${ph.ten}`,
          el("small", {}, xongP ? "✓ xong" : dang ? `còn ~${phut(eta.con_phan)}` : "chờ")),
        el("p", { class: "phan-mo" }, ph.mo_ta),
        el("div", { class: "thanh-tien" }, el("i", { style: `width:${Math.round(100 * so / bs.length)}%` })),
        congs.length ? el("div", { class: "phan-kiem" }, congs.map(([n, c]) => {
          const k = (p.cong || {})[n];
          return el("span", { class: "kiem " + (k ? (k.dat ? "dat" : "truot") : ""), title: c.ten + ((k?.loi || []).length ? "\n" + k.loi.join("\n") : "") },
            (k ? (k.dat ? "✓ " : "⛔ ") : "◇ ") + (c.ngan || c.ten.split(/[·:]/)[0].trim()));
        })) : null);
    });
    return el("div", { class: "phieu phieu2" }, dau,
      p._ke_hoach_png ? el("button", { type: "button", class: "kh-anh", onclick: () => xemLon(media(p._ke_hoach_png)) },
        el("img", { src: media(p._ke_hoach_png), alt: "Đường cường độ kế hoạch" }), el("small", {}, "Kế hoạch từng giây — bấm để xem")) : null,
      el("ol", { class: "ds-gd" }, nhom),
      el("div", { class: "phieu-chan" }, "Luật cứng được máy tự kiểm và tự sửa trong từng phần. Thời gian còn lại học theo tốc độ thật của máy này."));
  };
  return el("div", { class: "ds-phieu" },
    ds.length > 1 ? el("p", { class: "nhan-muc" }, `Phiếu của việc này · ${ds.length} video`) : null,
    ds.map((p, i) => ve1(p, i === ds.length - 1)));
}

/* ---------- phong cách nhanh: thư viện + lệnh /review /sanpham … ---------- */
function bangLenh() { return (S.kd?.phong_cach_nhanh || []).flatMap((g) => (g.lenh || []).map((l) => ({ l, g }))); }
const NHOM_PC = [
  ["Dạy & chia sẻ kiến thức", ["kienthuc", "huongdan", "giaoduc", "congnghe", "taichinh", "podcast"]],
  ["Bán hàng & sản phẩm", ["review", "sanpham", "batdongsan", "thoitrang", "amthuc"]],
  ["Đời sống & cảm xúc", ["vlog", "tamsu", "dulich", "thethao", "sukien"]],
  ["Điện ảnh · tin tức · giải trí", ["dienanh", "tintuc", "hai", "showcase"]],
];
async function moPhongCach() {
  const hop = $("#hopPC"), than = $("#pcThan");
  if (!(S.kd?.phong_cach_nhanh || []).length) {          // cửa sổ mở trước khi máy chủ có dữ liệu → tự tải lại, không để trống
    than.replaceChildren(el("p", { class: "pc-cho" }, "Đang tải danh mục phong cách…"));
    hop.showModal();
    try { S.kd = await api("/api/khoi-dau"); } catch (e) { /* thử lại ở dưới */ }
  }
  const ds = S.kd?.phong_cach_nhanh || [];
  if (!ds.length) {
    than.replaceChildren(el("p", { class: "pc-cho" }, "Chưa tải được danh mục. ", el("button", { type: "button", class: "nut nut-chinh", onclick: () => location.reload() }, "Tải lại Studio")));
    if (!hop.open) hop.showModal();
    return;
  }
  const theoId = Object.fromEntries(ds.map((g) => [g.id, g]));
  const dung = (g) => { o.value = (g.lenh?.[0] || "/" + g.id) + " " + o.value.replace(/^\/\S+\s*/, ""); tuCao(); nutGui(); hop.close(); o.focus(); };
  const the = (g) => el("article", { class: "pc-the", tabindex: "0", onclick: () => dung(g), onkeydown: (e) => { if (e.key === "Enter") dung(g); } },
    el("div", { class: "pc-anh" },
      g.anh ? el("img", { src: media(g.anh, 1), alt: "Minh hoạ " + g.ten, loading: "lazy" }) : el("span", {}, "chưa có ảnh"),
      el("button", { type: "button", class: "pc-phong", title: "Xem lớn", onclick: (e) => { e.stopPropagation(); xemLon(media(g.anh, 1)); } }, "⤢")),
    el("div", { class: "pc-tt" },
      el("div", { class: "pc-dong1" }, el("h4", {}, g.ten),
        el("span", { class: "pc-mau" }, ...["sang", "toi", "nhan"].map((k) => g.mau?.[k] ? el("i", { style: `background:${g.mau[k]}` }) : null))),
      el("p", { class: "pc-mo" }, g.mo_ta),
      el("div", { class: "pc-chan" }, el("code", {}, g.lenh?.[0] || "/" + g.id), el("span", { class: "pc-dung" }, "Dùng →"))));
  const daXep = new Set();
  const khoi = NHOM_PC.map(([ten, ids]) => {
    const gs = ids.map((i) => theoId[i]).filter(Boolean); gs.forEach((g) => daXep.add(g.id));
    return gs.length ? el("section", { class: "pc-nhom" }, el("h3", {}, ten, el("small", {}, gs.length)), el("div", { class: "pc-luoi" }, gs.map(the))) : null;
  });
  const con = ds.filter((g) => !daXep.has(g.id));
  if (con.length) khoi.push(el("section", { class: "pc-nhom" }, el("h3", {}, "Khác"), el("div", { class: "pc-luoi" }, con.map(the))));
  than.replaceChildren(
    el("p", { class: "pc-ghi" }, `${ds.length} phong cách dựng sẵn — bấm một thẻ để dùng. Hoặc gõ thẳng lệnh trong ô chat, vd. `, el("code", {}, "/review"), ". Claude vẫn tự quyết thủ pháp theo nội dung video."),
    el("div", { class: "pc-cuon" }, khoi));
  if (!hop.open) hop.showModal();
}

(function ganPhongCach() {
  const chan = $(".soan-chan");
  if (chan && !$("#nutPC")) {
    const n = el("button", { class: "nut-chip", id: "nutPC", type: "button", title: "20 phong cách edit dựng sẵn", onclick: moPhongCach },
      el("span", { html: '<svg viewBox="0 0 24 24"><rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/></svg>' }), "Phong cách");
    $("#nutMoKho").after(n);
  }
  if (!$("#hopPC")) {
    document.body.append(el("dialog", { class: "hop hop-pc", id: "hopPC" },
      el("div", { class: "hop-dau" }, el("h2", {}, "Phong cách nhanh"), el("button", { type: "button", class: "nut nut-phu", onclick: () => $("#hopPC").close() }, "Đóng")),
      el("div", { id: "pcThan" })));
  }
  const goi = el("div", { class: "goi-lenh", id: "goiLenh", hidden: true });
  $("#soan").prepend(goi);
  o.addEventListener("input", () => {
    const m = o.value.match(/^\/(\S*)$/);
    if (!m) { goi.hidden = true; return; }
    const q = m[1].toLowerCase();
    const kq = bangLenh().filter(({ l }) => l.slice(1).toLowerCase().startsWith(q)).slice(0, 8);
    goi.replaceChildren(...kq.map(({ l, g }) => el("button", { type: "button", onclick: () => { o.value = l + " "; goi.hidden = true; tuCao(); nutGui(); o.focus(); } },
      el("code", {}, l), el("span", {}, g.ten), el("small", {}, (g.hop_voi || []).slice(0, 2).join(", ")))));
    goi.hidden = !kq.length;
  });
})();


/* ---------- model của việc đang xem (1.2.21: bỏ hẳn token/USD; model nhập tự do, không chip "sai") ---------- */
const TEN_MODEL = { "claude-opus-5-5": "Opus 5.5", "claude-sonnet-5-5": "Sonnet 5.5", "claude-fable-5-1": "Fable 5.1", "claude-haiku-4-5-20251001": "Haiku 4.5" };
function veDoLuong() {
  let chip = $("#chipDL");
  if (!chip) {
    chip = el("button", { type: "button", class: "chip-dl", id: "chipDL", title: "Model AI của việc này — bấm để đổi model / số lượt", onclick: moDoLuong });
    $("#dauLam").before(chip);
  }
  const v = S.viecData, t = v?.tong;
  if (!v) { chip.hidden = true; return; }
  chip.hidden = false;
  chip.className = "chip-dl";
  chip.replaceChildren(el("b", {}, v.model ? (TEN_MODEL[v.model] || v.model) : "model"),
    t?.so_luot ? el("span", { class: "ten-may" }, `${t.so_luot} lượt · ${Math.round((t.giay || 0) / 60)} phút`) : null);
}
async function moDoLuong() {
  const v = S.viecData || {}, t = v.tong || {};
  let hop = $("#hopDL");
  if (!hop) { hop = el("dialog", { class: "hop hop-dl", id: "hopDL" }); document.body.append(hop); }
  const cd = await api("/api/cai-dat").catch(() => ({ model: "claude-opus-5-5", ten_model: TEN_MODEL }));
  const ten = cd.ten_model || TEN_MODEL, biet = Object.prototype.hasOwnProperty.call(ten, cd.model || "");
  const chon = el("select", { class: "dl-chon", "aria-label": "Model cho các lượt sau" },
    Object.entries(ten).map(([k, n]) => el("option", { value: k, selected: k === cd.model }, n)),
    el("option", { value: "__khac", selected: !biet || null }, "Khác (nhập tên)…"));
  const khac = el("input", { class: "dl-khac", type: "text", placeholder: "vd claude-opus-5-5", value: biet ? "" : (cd.model || ""), hidden: biet || null, "aria-label": "Tên model" });
  const bao = el("small", { class: "dl-bao" });
  const luuModel = async (m) => {
    try { await api("/api/cai-dat", { model: m }); bao.textContent = `Đã lưu ${m || "(để Claude Code tự chọn)"} — áp dụng từ lượt Claude tiếp theo.`; }
    catch (e) { bao.textContent = "Không lưu được: " + e.message; }
  };
  chon.addEventListener("change", () => { if (chon.value === "__khac") { khac.hidden = false; khac.focus(); } else { khac.hidden = true; luuModel(chon.value); } });
  khac.addEventListener("change", () => { const m = khac.value.trim(); if (!/^[a-z0-9.\-]{1,80}$/.test(m)) { bao.textContent = "Tên model chỉ gồm a-z, 0-9, dấu chấm, gạch ngang."; return; } luuModel(m); });
  const luot = (v.luot || []).slice().reverse().slice(0, 40);
  hop.replaceChildren(
    el("div", { class: "hop-dau" }, el("h2", {}, "Model · lượt Claude"), el("button", { type: "button", class: "nut nut-phu", onclick: () => hop.close() }, "Đóng")),
    el("div", { class: "dl-model" }, el("span", {}, "Việc này đang chạy: ", el("b", {}, v.model ? (TEN_MODEL[v.model] || v.model) : "—")),
      el("label", {}, "Khoá model cho Studio: ", chon, khac),
      el("small", { class: "dl-ghi" }, "Số video dựng cùng lúc, Chỉ CPU, dọn rác: bảng “Máy, bản quyền & cập nhật” ở góc dưới bên trái."), bao),
    el("div", { class: "dl-luoi" },
      el("div", { class: "dl-o" }, el("span", {}, "Số lượt"), el("b", {}, String(t.so_luot || 0))),
      el("div", { class: "dl-o" }, el("span", {}, "Thời gian Claude làm"), el("b", {}, `${Math.round((t.giay || 0) / 60)} phút`))),
    luot.length ? el("table", { class: "dl-bang" },
      el("tr", {}, ...["Lúc", "Bước", "Thời gian", "Kết quả"].map((h) => el("th", {}, h))),
      luot.map((l) => el("tr", { class: l.loi ? "loi" : "" },
        el("td", {}, gio(l.luc)), el("td", {}, l.so_buoc ?? ""), el("td", {}, mmss(Math.round(l.giay || 0))), el("td", {}, l.loi ? "lỗi" : "xong"))))
      : el("p", { class: "dl-trong" }, "Chưa có lượt nào."));
  hop.showModal();
}

// 1.3: KHO MỚI — nghe nhạc/SFX, xem font bằng chính font đó, nền, LUT, video hiệu ứng mẫu (máy chủ kho, cổng cai_dat.cong_kho — Studio tự bật).
// Nút "Dùng" trong kho → chèn mã tài nguyên vào ô chat để Claude dùng đúng thứ đó. 1.2.21: cổng đọc từ /api/khoi-dau (không ghi cứng 4789).
function batKhoMoi() {
  const f = document.getElementById("khoMoi"), mr = document.getElementById("khoMoRong");
  if (!f || S.khoDaBat) return;
  S.khoDaBat = true;
  const cong = S.kd?.cong_kho || 4789;
  const url = `http://127.0.0.1:${cong}/kho.html`;
  let thu = 0;
  const bat = () => {
    const anh = new Image();          // dò máy chủ kho bằng một ảnh nhỏ (không vướng CORS)
    anh.onload = anh.onerror = () => {
      if (anh.width > 0 || thu > 20) {
        if (anh.width > 0) {
          f.src = url; f.hidden = false; mr.hidden = false;
          if (nho.lay("khoRong", "") && S.phai === "kho") khoRong(true);     // nhớ trạng thái đẩy rộng lần trước
          ["khoNhom", "khoDs"].forEach((id) => { const e = document.getElementById(id); if (e) e.hidden = true; });
          const t = document.querySelector(".kho-tim"), g = document.querySelector(".kho-goi");
          if (t) t.hidden = true; if (g) g.hidden = true;
        }
        return;
      }
      thu++; setTimeout(bat, 1500);
    };
    anh.src = `http://127.0.0.1:${cong}/favicon-kho.png?` + Date.now();
  };
  bat();
  window.addEventListener("message", (e) => {
    const d = e.data || {};
    if (d.kieu !== "kho_dung" || !d.id) return;
    const o = document.getElementById("o");
    if (!o) return;
    o.value = (o.value ? o.value.replace(/\s*$/, " ") : "") + d.id + " ";
    o.dispatchEvent(new Event("input", { bubbles: true }));
    o.focus();
  });
}
