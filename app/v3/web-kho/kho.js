/* Kho tài nguyên — thuần JS, không framework. API: /api/kho/* (kho/api.py) */
(function () {
  "use strict";
  const API = "/api/kho";
  const LOAI = [
    ["", "Tất cả"], ["nhac", "Nhạc"], ["sfx", "SFX"], ["font", "Font"], ["nen", "Nền"], ["icon", "Icon"], ["video", "Video"],
    ["lut", "LUT"], ["hieu_ung", "Hiệu ứng"], ["preset_capcut", "Preset CapCut"], ["anh", "Ảnh"], ["khac", "Khác"],
  ];
  const TEN_LOAI = Object.fromEntries(LOAI);
  const $ = (s, p) => (p || document).querySelector(s);
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const giay = (d) => { d = Number(d || 0); const m = Math.floor(d / 60), s = d - m * 60; return m ? `${m}:${String(Math.floor(s)).padStart(2, "0")}` : (d < 10 ? s.toFixed(1) : Math.round(s)) + " s"; };

  const st = { loai: "", cd: "", q: "", sap: "ten", trang: 1, n: 60, tong: 0, het: false, dangTai: false, theoLoai: {}, fontDuDau: false, fontChu: "", phien: 0, chuaDung: false };
  const luoi = $("#luoi"), chips = $("#chips"), tim = $("#tim"), sap = $("#sap"), audio = $("#audio");
  const trongEl = $("#trong"), dangTaiEl = $("#dang-tai"), canh = $("#canh"), tomTat = $("#tom-tat");

  // ---------------------------------------------------------------- tiện ích
  let toastT;
  function toast(html) { const t = $("#toast"); t.innerHTML = html; t.classList.add("hien"); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("hien"), 2200); }
  async function chep(text, nhan) {
    try { await navigator.clipboard.writeText(text); }
    catch (e) { const ta = el("textarea"); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); }
    toast(nhan || `Đã chép <b>${esc(text)}</b> — dán vào yêu cầu cho AI`);
  }
  function dung(m) {
    const msg = { kieu: "kho_dung", id: m.id, loai: m.loai, ten: m.ten };
    if (window.parent && window.parent !== window) { window.parent.postMessage(msg, "*"); toast(`Đã gửi <b>${esc(m.id)}</b> vào ô yêu cầu`); }
    else chep(m.id, `Đã chép <b>${esc(m.id)}</b> (mở trong Studio để chèn thẳng vào yêu cầu)`);
  }
  const json = (u) => fetch(u).then((r) => r.json());

  // ---------------------------------------------------------------- lazy load (IntersectionObserver + quét dự phòng theo toạ độ)
  const cho = new Set();
  function nap(t) {
    cho.delete(t);
    if (t.dataset.src) { t.addEventListener("load", () => t.classList.add("ok"), { once: true }); t.addEventListener("error", () => t.closest(".hinh, .song")?.classList.add("loi"), { once: true }); t.src = t.dataset.src; delete t.dataset.src; }
    if (t.dataset.font) napFont(t);
    if (t.dataset.hieuUng) { const v = t; v.src = t.dataset.hieuUng; delete t.dataset.hieuUng; const go = () => v.play().catch(() => {}); v.addEventListener("canplay", go, { once: true }); go(); }
  }
  const io = new IntersectionObserver((ents) => { for (const e of ents) if (e.isIntersecting) { io.unobserve(e.target); nap(e.target); } }, { rootMargin: "300px 0px" });
  function theoDoi(t) { cho.add(t); io.observe(t); }
  setInterval(() => {   // dự phòng khi trình duyệt không vẽ (tab ẩn, iframe nền…): nạp phần tử đang nằm gần khung nhìn
    if (!cho.size) return;
    const H = window.innerHeight + 300;
    for (const t of Array.from(cho)) { if (!t.isConnected) { cho.delete(t); io.unobserve(t); continue; } const r = t.getBoundingClientRect(); if (r.bottom > -300 && r.top < H) { io.unobserve(t); nap(t); } }
  }, 700);

  const fontDaNap = new Map();
  async function napFont(mau) {
    const id = mau.dataset.font, ho = "kho-" + id.replace(/[^a-z0-9]/gi, "_");
    delete mau.dataset.font;
    try {
      if (!fontDaNap.has(id)) {
        const ff = new FontFace(ho, `url("${API}/file?id=${encodeURIComponent(id)}")`);
        fontDaNap.set(id, ff.load().then((f) => { document.fonts.add(f); return f; }));
      }
      await fontDaNap.get(id);
      mau.style.fontFamily = `"${ho}", var(--font)`;
      mau.classList.remove("cho");
    } catch (e) {
      mau.classList.add("cho"); mau.title = "Trình duyệt không nạp được font này — xem ảnh mẫu";
      const img = el("img"); img.src = `${API}/xem-truoc?id=${encodeURIComponent(id)}`; mau.innerHTML = ""; mau.appendChild(img);
    }
  }

  // ---------------------------------------------------------------- âm thanh (1 phát một lúc)
  let dangPhat = null;   // thẻ
  function phat(the, m) {
    if (dangPhat === the) { if (audio.paused) audio.play(); else audio.pause(); capNhatNut(); return; }
    if (dangPhat) { dangPhat.classList.remove("dang-phat"); $(".tien", dangPhat).style.width = "0"; $(".phat", dangPhat).textContent = "▶"; }
    dangPhat = the; the.classList.add("dang-phat");
    audio.src = `${API}/nghe?id=${encodeURIComponent(m.id)}`;
    audio.play().catch(() => toast("Không phát được âm thanh này"));
    capNhatNut();
  }
  function capNhatNut() { if (dangPhat) $(".phat", dangPhat).textContent = audio.paused ? "▶" : "❚❚"; }
  audio.addEventListener("timeupdate", () => { if (dangPhat && audio.duration) $(".tien", dangPhat).style.width = (audio.currentTime / audio.duration * 100) + "%"; });
  audio.addEventListener("ended", () => { if (dangPhat) { $(".tien", dangPhat).style.width = "0"; } capNhatNut(); });
  audio.addEventListener("pause", capNhatNut); audio.addEventListener("play", capNhatNut);

  // ---------------------------------------------------------------- kéo thẻ sang ô chat của Studio (1.2.19) — không cần mở cửa sổ mới
  function keoDuoc(the, m) {
    the.draggable = true;
    the.addEventListener("dragstart", (e) => {
      const d = { loai: m.loai, ten: m.ten, duong: m.duong || "", ham: m.id, id: m.id };
      e.dataTransfer.setData("application/x-kho", JSON.stringify(d));
      e.dataTransfer.setData("text/plain", m.id);
      e.dataTransfer.effectAllowed = "copy";
      the.classList.add("dang-keo");
    });
    the.addEventListener("dragend", () => the.classList.remove("dang-keo"));
    the.title = "Kéo thả vào ô chat của Studio, hoặc bấm Dùng";
  }
  // ---------------------------------------------------------------- thẻ
  function nutChung(m, the) {
    const d = el("div", "nut-dong");
    const b1 = el("button", "nut nut-chinh", "Dùng"); b1.title = "Chèn id vào ô yêu cầu của Studio"; b1.onclick = () => dung(m);
    const b2 = el("button", "nut", "Chép id"); b2.onclick = () => chep(m.id);
    const b3 = el("button", "nut nut-phu nho", "ⓘ"); b3.title = "Chi tiết"; b3.onclick = () => chiTiet(m);
    d.append(b1, b2, b3);
    if (m.loai === "nhac" || m.loai === "sfx") {            // 1.2.19: tiếng giống (vân tay mel) — "như tiếng này nhưng khác tệp"
      const b4 = el("button", "nut nut-phu nho", "≈"); b4.title = "Tiếng giống tiếng này"; b4.onclick = () => tiengGiong(m);
      d.appendChild(b4);
    }
    return d;
  }
  async function tiengGiong(m) {
    const r = await json(`${API}/giong?id=${encodeURIComponent(m.id)}&n=12`).catch(() => ({ muc: [] }));
    const nd = $("#modal-nd");
    nd.innerHTML = `<h3>Tiếng giống: ${esc(m.ten)}</h3><p class="mo-ta">Xếp theo vân tay âm (dải mel) — cùng chất tiếng, khác tệp. Kéo thẻ vào ô chat hoặc bấm Dùng.</p><div class="luoi giong"></div>`;
    const g = $(".luoi.giong", nd);
    if (!(r.muc || []).length) g.innerHTML = "<p>Chưa có vân tay cho mục này (lập lại chỉ mục để đo).</p>";
    (r.muc || []).forEach((x) => g.appendChild(taoThe(x)));
    $("#modal").classList.remove("an");
  }
  function tag(txt, cls) { return el("span", "tag" + (cls ? " " + cls : ""), txt); }
  function thanChung(m, the, soDo) {
    const than = el("div", "than");
    const ten = el("div", "ten", esc(m.ten)); ten.title = m.ten; ten.onclick = () => chiTiet(m);
    const nhom = el("div", "nhom", esc((m.nhom || []).join(" › ")));
    than.append(ten, nhom);
    const ai = m.ai;
    if (ai && ai.mo_ta) {                      // nghĩa do AI gắn (kho/gan_nghia.py)
      const mt = el("div", "mo-ta-ai", esc(ai.mo_ta)); mt.title = ai.mo_ta; than.appendChild(mt);
      const tg = el("div", "tags-ai");
      (ai.cong_dung || []).slice(0, 3).forEach((c) => {
        const gon = c.replace(/\s*(từ|tu)\s*['"‘“].*$/i, "").trim();
        const t = tag(esc(c), "cd"); t.title = "Lọc theo công dụng: " + gon;
        t.onclick = (e) => { e.stopPropagation(); st.cd = gon; veChipsCd(); lamMoi(); };
        tg.appendChild(t);
      });
      (ai.tu_khoa || []).slice(0, 4).forEach((k) => { const t = tag(esc(k), "tk"); t.title = "Tìm: " + k; t.onclick = (e) => { e.stopPropagation(); tim.value = k; st.q = k; lamMoi(); }; tg.appendChild(t); });
      if (ai.nang_luong) tg.appendChild(tag("⚡" + ai.nang_luong, "nl"));
      than.appendChild(tg);
    }
    if (soDo && soDo.length) { const sd = el("div", "so-do"); soDo.forEach((t) => t && sd.appendChild(t)); than.appendChild(sd); }
    than.appendChild(nutChung(m, the));
    return than;
  }
  function anhLazy(src, cls) { const img = el("img"); img.dataset.src = src; img.alt = ""; img.decoding = "async"; theoDoi(img); return img; }
  const xtUrl = (m) => `${API}/xem-truoc?id=${encodeURIComponent(m.id)}`;

  function theAm(m) {
    const the = el("div", "the am"); const sd = m.so_do || {};
    const song = el("div", "song");
    song.appendChild(anhLazy(xtUrl(m)));
    song.appendChild(el("div", "tien"));
    const nut = el("button", "phat", "▶"); nut.title = m.loai === "nhac" ? "Nghe 30 s đầu" : "Nghe"; nut.onclick = (e) => { e.stopPropagation(); phat(the, m); };
    song.appendChild(nut);
    if (sd.dur != null) song.appendChild(el("span", "dai", giay(sd.dur)));
    song.onclick = (e) => { // bấm vào dạng sóng để tua
      if (dangPhat !== the || !audio.duration) return phat(the, m);
      const r = song.getBoundingClientRect(); audio.currentTime = (e.clientX - r.left) / r.width * audio.duration;
    };
    the.appendChild(song);
    const tags = [tag(m.loai === "nhac" ? "Nhạc" : "SFX", "nhan")];
    if (sd.bpm) tags.push(tag(sd.bpm + " BPM"));
    if (sd.lufs != null) tags.push(tag(sd.lufs + " LUFS"));
    if (sd.peak != null) tags.push(tag("đỉnh " + sd.peak + " dB"));
    if (m.chu_ky && m.loai === "sfx") { const t = tag(esc(m.chu_ky), "ck"); t.title = "Chữ ký tiếng (máy đo): cao/trầm · bật/dâng · dài · ngân/khô · chuỗi · nhiễu/âm sắc"; tags.push(t); }
    tags.push(tag(m.da_dung ? `đã dùng ${m.da_dung}` : "chưa dùng", m.da_dung ? "dd" : "ok"));
    the.appendChild(thanChung(m, the, tags));
    keoDuoc(the, m);
    return the;
  }
  function theFont(m) {
    const the = el("div", "the font"); const sd = m.so_do || {};
    const mau = el("div", "mau cho");
    if (sd.du_dau === false && !st.fontChu) {   // font thiếu dấu: hiện ảnh skia (thấy ô vuông thật) thay vì để trình duyệt mượn glyph font khác
      mau.classList.remove("cho"); mau.style.padding = "0"; mau.appendChild(anhLazy(xtUrl(m))); mau.title = "Font này thiếu dấu tiếng Việt — ảnh mẫu dựng bằng chính font";
    } else {
      mau.dataset.font = m.id;
      const ho = el("div", "ho", esc(sd.ho || m.ten)); const cau = el("div", "cau", esc(st.fontChu || "Tiếng Việt có dấu: Ấ Ệ Ở Ỡ Ữ Đ 0123 — Edit video nhanh"));
      mau.append(ho, cau); theoDoi(mau);
    }
    the.appendChild(mau);
    const tags = [sd.du_dau ? tag("✓ đủ dấu Việt", "ok") : tag("✗ thiếu dấu", "loi"), tag("đậm " + (sd.dam || 400))];
    if (sd.kieu && sd.kieu !== "Regular") tags.push(tag(esc(sd.kieu)));
    if (sd.nghieng) tags.push(tag("nghiêng"));
    if (sd.var) tags.push(tag("variable " + (sd.truc || []).join("/"), "nhan"));
    the.appendChild(thanChung(m, the, tags));
    return the;
  }
  function theLut(m) {
    const the = el("div", "the lut");
    const h = el("div", "hinh ratio-16");
    h.appendChild(anhLazy(xtUrl(m)));
    h.appendChild(el("div", "vach")); h.appendChild(el("span", "nhan-goc", "Trước")); h.appendChild(el("span", "nhan-goc phai", "Sau"));
    the.appendChild(h);
    const sd = m.so_do || {};
    the.appendChild(thanChung(m, the, [tag("LUT " + (m.duong || "").split(".").pop().toUpperCase(), "nhan"), sd.kich ? tag(sd.kich + "³") : null]));
    return the;
  }
  function theNenVideo(m) {
    const the = el("div", "the " + m.loai); const sd = m.so_do || {};
    const dọc = sd.h > sd.w;
    const h = el("div", "hinh " + (dọc ? "ratio-9" : "ratio-16"));
    const img = anhLazy(xtUrl(m)); h.appendChild(img);
    const laVideo = /\.(mp4|mov|webm|mkv|m4v|avi)$/i.test(m.duong || "");
    h.appendChild(el("span", "nhan-goc", laVideo ? (sd.dur ? giay(sd.dur) : "video") : "ảnh"));
    if (sd.alpha) h.appendChild(el("span", "nhan-goc phai", "alpha"));
    if (laVideo) {
      let v = null, timer;
      const bat = () => { if (v) return; timer = setTimeout(() => {
        v = el("video"); v.muted = true; v.loop = true; v.playsInline = true; v.autoplay = true;
        v.setAttribute("muted", ""); v.setAttribute("autoplay", ""); v.setAttribute("playsinline", ""); v.setAttribute("loop", "");
        v.src = `${API}/thu?id=${encodeURIComponent(m.id)}`; v.addEventListener("loadeddata", () => v.play().catch(() => {}), { once: true });
        v.onerror = () => { v && v.remove(); v = null; };
        h.appendChild(v); img.style.opacity = "0";
      }, 180); };
      const tat = () => { clearTimeout(timer); if (v) { v.pause(); v.remove(); v = null; img.style.opacity = ""; } };
      h.addEventListener("mouseenter", bat); h.addEventListener("mouseleave", tat);
      h.addEventListener("click", () => (v ? tat() : bat()));
      h.title = "Rê chuột để xem 4 s đầu";
    }
    the.appendChild(h);
    const tags = [tag(m.loai === "nen" ? "Nền" : "Video", "nhan")];
    if (sd.w) tags.push(tag(sd.w + "×" + sd.h));
    the.appendChild(thanChung(m, the, tags));
    return the;
  }
  function theIconAnh(m) {
    const the = el("div", "the " + m.loai); const sd = m.so_do || {};
    const h = el("div", "hinh " + (m.loai === "icon" ? "caro ratio-1" : "ratio-16"));
    h.appendChild(anhLazy(xtUrl(m)));
    the.appendChild(h);
    const tags = [tag(m.loai === "icon" ? "Icon" : "Ảnh", "nhan")];
    if (sd.w) tags.push(tag(sd.w + "×" + sd.h));
    if (sd.alpha) tags.push(tag("alpha", "ok"));
    the.appendChild(thanChung(m, the, tags));
    return the;
  }
  function thePreset(m) {
    const the = el("div", "the preset");
    const h = el("div", "hinh ratio-16");
    if (m.xem_truoc) h.appendChild(anhLazy(xtUrl(m))); else h.classList.add("loi");
    h.appendChild(el("span", "nhan-goc", "CapCut"));
    the.appendChild(h);
    const sd = m.so_do || {};
    the.appendChild(thanChung(m, the, [tag("Preset CapCut", "nhan"), sd.kb ? tag(sd.kb + " KB") : null]));
    return the;
  }
  function theKhac(m) {
    const the = el("div", "the khac");
    const duoi = (m.duong || "").split(".").pop().toLowerCase();
    const bieu = { xmp: "🎨", lrtemplate: "🎨", dng: "🎨", pdf: "📄", txt: "📄", woff: "🔤", woff2: "🔤" }[duoi] || "📦";
    const h = el("div", "hinh"); h.innerHTML = `<div style="text-align:center">${bieu}<div class="duoi">${esc(duoi)}</div></div>`;
    the.appendChild(h);
    const nhom = (m.nhom || [])[0];
    the.appendChild(thanChung(m, the, [tag({ lightroom: "Lightroom preset", tai_lieu: "Tài liệu", font_web: "Font web" }[nhom] || "Khác", "nhan")]));
    return the;
  }
  function theHieuUng(h) {
    const the = el("div", "the hieu_ung");
    const hinh = el("div", "hinh ratio-9");
    if (h.video) {
      const v = el("video"); v.muted = true; v.loop = true; v.playsInline = true; v.preload = "none";
      v.setAttribute("muted", ""); v.setAttribute("autoplay", ""); v.setAttribute("playsinline", ""); v.setAttribute("loop", "");
      v.addEventListener("click", () => (v.paused ? v.play() : v.pause()));
      v.addEventListener("mouseenter", () => { if (v.paused) v.play().catch(() => {}); });
      v.poster = `${API}/hieu-ung/file?id=${encodeURIComponent(h.id)}&kieu=jpg`;
      v.dataset.hieuUng = `${API}/hieu-ung/file?id=${encodeURIComponent(h.id)}&kieu=mp4`;
      theoDoi(v); hinh.appendChild(v);
      hinh.appendChild(el("span", "nhan-goc", h.cach === "engine" ? "engine" : "mẫu dự phòng"));
    } else {
      const img = el("img"); img.src = `${API}/hieu-ung/file?id=${encodeURIComponent(h.id)}&kieu=png`; img.classList.add("ok"); hinh.appendChild(img);
      hinh.appendChild(el("span", "nhan-goc", "chưa dựng được"));
    }
    the.appendChild(hinh);
    const than = el("div", "than");
    than.appendChild(el("div", "ten", esc(h.ten)));
    than.appendChild(el("div", "mo-ta", esc(h.mo_ta || "")));
    const d = el("div", "nut-dong");
    const b1 = el("button", "nut nut-chinh", "Chép spec"); b1.title = "Chép JSON lớp để dán vào công thức";
    b1.onclick = async () => { const r = await fetch(`${API}/hieu-ung/file?id=${encodeURIComponent(h.id)}&kieu=json`); chep(await r.text(), `Đã chép spec <b>${esc(h.ten)}</b> — dán vào yêu cầu/công thức`); };
    const b2 = el("button", "nut", "Chép id"); b2.onclick = () => chep("hieu_ung." + h.id);
    d.append(b1, b2); than.appendChild(d);
    the.appendChild(than);
    return the;
  }
  function taoThe(m) {
    let the;
    switch (m.loai) {
      case "nhac": case "sfx": return theAm(m);
      case "font": the = theFont(m); break;
      case "lut": the = theLut(m); break;
      case "nen": case "video": the = theNenVideo(m); break;
      case "icon": case "anh": the = theIconAnh(m); break;
      case "preset_capcut": the = thePreset(m); break;
      default: the = theKhac(m);
    }
    keoDuoc(the, m);
    return the;
  }

  // ---------------------------------------------------------------- chi tiết
  async function chiTiet(m0) {
    const m = (await json(`${API}/lay?id=${encodeURIComponent(m0.id)}`)) || m0;
    const nd = $("#modal-nd"); const sd = m.so_do || {};
    const xt = m.loai === "nen" || m.loai === "video" ? (/\.(mp4|mov|webm|mkv)$/i.test(m.duong) ? `<video src="${API}/thu?id=${encodeURIComponent(m.id)}" muted loop autoplay playsinline controls></video>` : `<img src="${xtUrl(m)}">`)
      : ["font", "lut", "icon", "anh", "nhac", "sfx"].includes(m.loai) || m.xem_truoc ? `<img src="${xtUrl(m)}">` : "";
    nd.innerHTML = `<h3>${esc(m.ten)}</h3>
      <div class="id" title="bấm để chép">${esc(m.id)}</div>
      ${xt ? `<div class="xt">${xt}</div>` : ""}
      ${["nhac", "sfx"].includes(m.loai) ? `<audio controls src="${API}/nghe?id=${encodeURIComponent(m.id)}" style="width:100%"></audio>` : ""}
      <div class="duong" title="bấm để chép đường dẫn">${esc(m.duong)}</div>
      <div class="kv"><b>Loại</b><span>${esc(TEN_LOAI[m.loai] || m.loai)}</span><b>Thư mục</b><span>${esc((m.nhom || []).join(" › "))}</span>
      <b>Số đo</b><span>${esc(Object.entries(sd).filter(([k]) => k !== "loi").map(([k, v]) => k + ": " + (Array.isArray(v) ? v.join("/") : v)).join(" · "))}</span>
      ${m.ai ? `<b>Mô tả AI</b><span>${esc(m.ai.mo_ta || "")}</span>
      <b>Công dụng</b><span>${esc((m.ai.cong_dung || []).join(" · "))}</span>
      <b>Cảm xúc</b><span>${esc((m.ai.cam_xuc || []).join(", "))}${m.ai.nang_luong ? " · năng lượng " + m.ai.nang_luong + "/5" : ""}</span>
      <b>Phong cách</b><span>${esc((m.ai.phong_cach || []).join(", "))}${m.ai.mau_chu_dao ? " · màu " + esc(m.ai.mau_chu_dao) : ""}${m.ai.hop_khung ? " · khung " + esc(m.ai.hop_khung) : ""}</span>
      ${m.ai.hop_vai ? `<b>Vai chữ</b><span>${esc(m.ai.hop_vai.join(", "))}${m.ai.de_doc ? " · dễ đọc " + m.ai.de_doc + "/5" : ""}</span>` : ""}
      <b>Từ khoá AI</b><span style="color:var(--chu2)">${esc((m.ai.tu_khoa || []).join(", "))}</span>` : ""}
      <b>Từ khoá máy</b><span style="color:var(--chu3)">${esc((m.tu_khoa || []).join(", "))}</span>
      <b>Kích thước</b><span>${(m.size / 1024).toFixed(0)} KB</span></div>
      <div class="nut-dong"><button class="nut nut-chinh" id="md-dung">Dùng</button><button class="nut" id="md-chep">Chép id</button><a class="nut" href="${API}/file?id=${encodeURIComponent(m.id)}" target="_blank" rel="noopener">Mở file gốc</a></div>`;
    $("#md-dung").onclick = () => dung(m); $("#md-chep").onclick = () => chep(m.id);
    $(".id", nd).onclick = () => chep(m.id); $(".duong", nd).onclick = () => chep(m.duong, "Đã chép đường dẫn");
    $("#modal").classList.remove("an");
  }
  $("#modal-dong").onclick = () => { $("#modal").classList.add("an"); $("#modal-nd").innerHTML = ""; };
  $("#modal").addEventListener("click", (e) => { if (e.target === $("#modal")) $("#modal-dong").click(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#modal-dong").click(); if (e.key === "/" && document.activeElement !== tim && document.activeElement.tagName !== "INPUT") { e.preventDefault(); tim.focus(); } });

  // ---------------------------------------------------------------- chips + thống kê
  // 1.2.19: lướt ngang hàng nút lọc — lăn chuột (dọc → ngang) và kéo tay; bấm chip vẫn hoạt động (chỉ coi là kéo khi di > 6 px)
  function luotNgang(nav) {
    if (!nav || nav.dataset.luot) return;
    nav.dataset.luot = "1";
    nav.addEventListener("wheel", (e) => {
      if (nav.scrollWidth <= nav.clientWidth) return;
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) { nav.scrollLeft += e.deltaY; e.preventDefault(); }
    }, { passive: false });
    let x0 = 0, s0 = 0, keo = false, da = false;
    nav.addEventListener("pointerdown", (e) => { if (e.button !== 0) return; keo = true; da = false; x0 = e.clientX; s0 = nav.scrollLeft; });
    nav.addEventListener("pointermove", (e) => {
      if (!keo) return;
      const dx = e.clientX - x0;
      if (!da && Math.abs(dx) > 6) { da = true; nav.classList.add("dang-keo"); try { nav.setPointerCapture(e.pointerId); } catch {} }
      if (da) nav.scrollLeft = s0 - dx;
    });
    const tha = () => { keo = false; nav.classList.remove("dang-keo"); if (da) setTimeout(() => { da = false; }, 80); };
    nav.addEventListener("pointerup", tha); nav.addEventListener("pointercancel", tha); nav.addEventListener("pointerleave", tha);
    nav.addEventListener("click", (e) => { if (da) { e.stopPropagation(); e.preventDefault(); da = false; } }, true);
  }
  luotNgang(chips); luotNgang($("#chips-cd"));

  function veChips() {
    chips.innerHTML = "";
    const tong = Object.values(st.theoLoai).reduce((a, b) => a + b, 0);
    for (const [k, ten] of LOAI) {
      const so = k === "" ? tong : k === "hieu_ung" ? (st.soHieuUng || 0) : (st.theoLoai[k] || 0);
      if (k && !so && k !== "hieu_ung" && tong) continue;
      const c = el("button", "chip" + (st.loai === k ? " dang" : ""), `${esc(ten)}` + (tong ? ` <span class="so">${so}</span>` : ""));
      c.onclick = () => { st.loai = k; st.cd = ""; veChips(); taiCongDung(); lamMoi(); };
      chips.appendChild(c);
    }
  }
  // ---------------------------------------------------------------- lọc theo công dụng (nhãn AI)
  const chipsCd = $("#chips-cd");
  let dsCd = [];
  async function taiCongDung() {
    if (st.loai === "hieu_ung") { dsCd = []; veChipsCd(); return; }
    try { const r = await json(`${API}/cong-dung?loai=${encodeURIComponent(st.loai)}`); dsCd = r.muc || []; } catch (e) { dsCd = []; }
    veChipsCd();
  }
  function veChipsCd() {
    chipsCd.innerHTML = "";
    const co = dsCd.length || st.cd;
    chipsCd.classList.toggle("an", !co);
    if (!co) return;
    const tat = el("button", "chip" + (!st.cd ? " dang" : ""), "Mọi công dụng"); tat.onclick = () => { st.cd = ""; veChipsCd(); lamMoi(); };
    chipsCd.appendChild(tat);
    const ds = dsCd.slice(0, 18);
    if (st.cd && !ds.some(([t]) => t === st.cd)) ds.unshift([st.cd, ""]);
    for (const [t, so] of ds) {
      const c = el("button", "chip" + (st.cd === t ? " dang" : ""), esc(t) + (so ? ` <span class="so">${so}</span>` : ""));
      c.onclick = () => { st.cd = st.cd === t ? "" : t; veChipsCd(); lamMoi(); };
      chipsCd.appendChild(c);
    }
  }
  async function taiThongKe() {
    try {
      const tk = await json(`${API}/thong-ke`);
      st.theoLoai = tk.theo_loai || {}; st.soHieuUng = tk.hieu_ung || 0;
      tomTat.innerHTML = tk.tong ? `<b>${tk.tong}</b> mục · <b>${tk.co_ai || 0}</b> đã gắn nghĩa AI · lập lúc <b>${esc(tk.luc || "?")}</b> · font đủ dấu <b>${tk.font_du_dau || 0}/${(tk.theo_loai || {}).font || 0}</b>` : "Chưa có chỉ mục — bấm <b>Lập lại chỉ mục</b>.";
      veChips();
      if (tk.dang_lap) theoDoiLap();
    } catch (e) { tomTat.textContent = "Không nối được API kho."; }
  }

  // ---------------------------------------------------------------- tải danh sách
  function lamMoi() {
    st.trang = 1; st.het = false; st.phien++;
    if (dangPhat) { audio.pause(); audio.removeAttribute("src"); dangPhat = null; }
    luoi.innerHTML = ""; luoi.className = "luoi " + (st.loai || "tat-ca");
    trongEl.classList.add("an");
    $("#font-thu").classList.toggle("an", st.loai !== "font");
    taiTiep();
  }
  async function taiTiep() {
    if (st.dangTai || st.het) return;
    st.dangTai = true; dangTaiEl.classList.remove("an");
    const phien = st.phien;
    try {
      if (st.loai === "hieu_ung") {
        const r = await json(`${API}/hieu-ung`);
        if (phien !== st.phien) return;
        const ds = r.muc.filter((h) => !st.q || (h.ten + " " + h.mo_ta + " " + h.id).toLowerCase().includes(st.q.toLowerCase()));
        ds.forEach((h) => luoi.appendChild(theHieuUng(h)));
        st.het = true; st.tong = ds.length;
        if (!ds.length) trongEl.classList.remove("an");
        return;
      }
      const u = `${API}/ds?loai=${encodeURIComponent(st.loai)}&q=${encodeURIComponent(st.q)}&trang=${st.trang}&n=${st.n}&sap=${st.sap}&cd=${encodeURIComponent(st.cd)}${st.chuaDung ? "&chua_dung=1" : ""}`;
      const r = await json(u);
      if (phien !== st.phien) return;
      let muc = r.muc || [];
      if (st.loai === "font" && st.fontDuDau) muc = muc.filter((m) => m.so_do && m.so_do.du_dau);
      const frag = document.createDocumentFragment();
      muc.forEach((m) => frag.appendChild(taoThe(m)));
      luoi.appendChild(frag);
      st.tong = r.tong; st.trang++;
      if ((r.muc || []).length < st.n || luoi.children.length >= r.tong) st.het = true;
      if (!luoi.children.length) trongEl.classList.remove("an");
      // nếu lọc đủ dấu làm trang quá ngắn → tải tiếp
      if (!st.het && luoi.children.length < 24) { st.dangTai = false; dangTaiEl.classList.add("an"); return taiTiep(); }
    } catch (e) { toast("Lỗi tải danh sách: " + esc(e.message)); }
    finally { if (phien === st.phien) { st.dangTai = false; dangTaiEl.classList.add("an"); } }
  }
  new IntersectionObserver((es) => { if (es[0].isIntersecting) taiTiep(); }, { rootMargin: "600px 0px" }).observe(canh);

  // ---------------------------------------------------------------- lập lại chỉ mục (SSE)
  let es = null;
  function theoDoiLap(ep) {
    if (es) return;
    const td = $("#tien-do"), day = $("#td-day"), txt = $("#td-txt"); const nut = $("#nut-lap");
    td.classList.remove("an"); nut.disabled = true; day.classList.add("khong-ro"); txt.textContent = "Đang quét thư mục…";
    es = new EventSource(`${API}/lap${ep ? "?ep=1" : ""}`);
    es.addEventListener("tien_do", (e) => {
      const d = JSON.parse(e.data);
      if (d.n) { day.classList.remove("khong-ro"); day.style.width = (d.i / d.n * 100).toFixed(1) + "%"; txt.textContent = `${d.i}/${d.n} · ${d.ten}`; }
      else txt.textContent = d.ten || "…";
    });
    es.addEventListener("xong", (e) => { const d = JSON.parse(e.data); day.style.width = "100%"; txt.textContent = `Xong: ${d.tong} mục (${d.moi} mới, ${d.giu} giữ) trong ${d.giay} s`; toast(`Đã lập chỉ mục <b>${d.tong}</b> mục trong ${d.giay} s`); });
    es.addEventListener("loi", (e) => { txt.textContent = "Lỗi: " + JSON.parse(e.data).loi; });
    es.addEventListener("het", () => { es.close(); es = null; nut.disabled = false; setTimeout(() => td.classList.add("an"), 4000); taiThongKe().then(lamMoi); });
    es.onerror = () => { if (es) { es.close(); es = null; } nut.disabled = false; txt.textContent = "Mất kết nối tiến độ (lập vẫn chạy ngầm)."; };
  }
  $("#nut-lap").onclick = (e) => theoDoiLap(e.shiftKey);
  $("#chua-dung").addEventListener("change", (e) => { st.chuaDung = e.target.checked; lamMoi(); });
  // ---------------------------------------------------------------- gắn nghĩa AI cho kho riêng (1.2.19): ước tiền → hỏi → chạy nền (SSE)
  let esGan = null;
  $("#nut-gan").onclick = async () => {
    if (esGan) return;
    let u;
    try { u = await json(`${API}/gan-nghia?uoc=1`); } catch (e) { return toast("Không ước được: " + esc(e.message)); }
    if (!u.viec) return toast("Mọi tài nguyên đã có nghĩa AI — không cần gắn thêm.");
    if (!confirm(`Gắn nghĩa AI cho ${u.so_muc || "?"} mục chưa có nghĩa (${u.viec} lượt gọi, ước ≈ ${u.uoc_usd} USD tài khoản Claude của bạn, chạy nền vài phút). Tiếp tục?`)) return;
    const td = $("#tien-do"), day = $("#td-day"), txt = $("#td-txt"), nut = $("#nut-gan");
    td.classList.remove("an"); nut.disabled = true; day.classList.add("khong-ro"); txt.textContent = "Đang gắn nghĩa…";
    esGan = new EventSource(`${API}/gan-nghia?chay=1`);
    esGan.addEventListener("dong", (e) => { const d = JSON.parse(e.data); txt.textContent = d.chu || "…"; const mm = /\[(\d+)\/(\d+)\]/.exec(d.chu || ""); if (mm) { day.classList.remove("khong-ro"); day.style.width = (mm[1] / mm[2] * 100).toFixed(1) + "%"; } });
    esGan.addEventListener("xong", (e) => { const d = JSON.parse(e.data); day.style.width = "100%"; txt.textContent = `Xong: gắn ${d.gan || 0} mục, ${d.usd || 0} USD`; toast(`Đã gắn nghĩa <b>${d.gan || 0}</b> mục`); });
    esGan.addEventListener("loi", (e) => { txt.textContent = "Lỗi: " + JSON.parse(e.data).loi; });
    esGan.addEventListener("het", () => { esGan.close(); esGan = null; nut.disabled = false; setTimeout(() => td.classList.add("an"), 5000); taiThongKe().then(lamMoi); });
    esGan.onerror = () => { if (esGan) { esGan.close(); esGan = null; } nut.disabled = false; txt.textContent = "Mất kết nối tiến độ (gắn nghĩa vẫn chạy ngầm)."; };
  };
  $("#nut-lap").title = "Quét lại kho gốc, chỉ làm mục mới/đổi (Shift+bấm: làm lại toàn bộ)";

  // ---------------------------------------------------------------- sự kiện
  let timT;
  tim.addEventListener("input", () => { clearTimeout(timT); timT = setTimeout(() => { st.q = tim.value.trim(); lamMoi(); }, 260); });
  sap.addEventListener("change", () => { st.sap = sap.value; lamMoi(); });
  $("#font-du-dau").addEventListener("change", (e) => { st.fontDuDau = e.target.checked; lamMoi(); });
  let fontT;
  $("#font-chu").addEventListener("input", (e) => {
    const truoc = st.fontChu; st.fontChu = e.target.value;
    const c = st.fontChu || "Tiếng Việt có dấu: Ấ Ệ Ở Ỡ Ữ Đ 0123 — Edit video nhanh";
    document.querySelectorAll(".the.font .cau").forEach((x) => (x.textContent = c));
    if (!truoc !== !st.fontChu) { clearTimeout(fontT); fontT = setTimeout(lamMoi, 400); }   // đổi giữa ảnh ↔ chữ sống cho font thiếu dấu
  });
  // chấp nhận lệnh từ cửa sổ cha: {kieu:"kho_tim", q, loai}
  window.addEventListener("message", (e) => { const d = e.data || {}; if (d.kieu === "kho_tim") { st.q = d.q || ""; tim.value = st.q; if (d.loai != null) st.loai = d.loai; st.cd = d.cd || ""; veChips(); taiCongDung(); lamMoi(); } });
  // tham số URL: ?loai=&q=
  const p = new URLSearchParams(location.search); if (p.get("loai")) st.loai = p.get("loai"); if (p.get("q")) { st.q = p.get("q"); tim.value = st.q; } if (p.get("cd")) st.cd = p.get("cd");

  veChips(); lamMoi(); taiThongKe(); taiCongDung();          // chip + lưới hiện ngay; số đếm cập nhật khi thống kê về
})();
