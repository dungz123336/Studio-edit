/* Studio — bộ điều khiển trang của lớp web (máy chèn ĐẦU <head>, chạy trước mã của trang).
   Đồng hồ ảo: thời gian chỉ trôi khi máy gọi __studio.dat(t, dur) → kết quả tất định, khung nào cũng vẽ lại được.
   - performance.now / Date.now / requestAnimationFrame / setTimeout / setInterval chạy theo đồng hồ ảo
   - Math.random có hạt giống cố định
   - Mọi Animation (CSS animation/transition, Element.animate) bị dừng và tua theo t: currentTime = (t − lúc sinh)
     · có sẵn khi tải trang → sinh lúc 0 · tạo trong veTai(t) → sinh lúc t · ganTimeline(anim, batDau) → sinh lúc batDau
   - Trang tự viết window.veTai(t, dur) (giây từ t0 của lớp) để đặt trạng thái; trả về giá trị ≠ undefined = khoá trạng thái
     (khoá giống khung trước → máy không chụp lại). Không trả → máy tự băm DOM + tiến độ hoạt ảnh. */
(function () {
  'use strict';
  var T = 0, DUR = 1, daDat = false;
  var GOC_DATE = 1767225600000;                 // 2026-01-01 cố định
  var loi = [], daGhi = {};
  // lỗi xảy ra TRONG veTai/rAF/hẹn giờ (lỗi lúc tải trang do DevTools báo, không ghi ở đây). Mỗi lỗi chỉ ghi lần đầu (kèm t).
  function ghiLoi(e, noi) {
    var s = e && e.name ? e.name + ': ' + e.message : String(e);
    var m = e && e.stack ? /\.html:(\d+):\d+/.exec(e.stack) : null;
    if (m) s += ' (dòng ' + m[1] + ')';
    if (daGhi[noi + s]) return;
    daGhi[noi + s] = 1;
    if (loi.length < 20) loi.push(noi + ' lúc t=' + T.toFixed(2) + 's: ' + s.slice(0, 300));
  }

  // ---- đồng hồ ảo
  try { Object.defineProperty(performance, 'now', { value: function () { return T * 1000; }, configurable: true }); } catch (e) {}
  Date.now = function () { return GOC_DATE + T * 1000; };
  var hat = 0x9E3779B9 | 0;
  Math.random = function () {
    hat = (hat + 0x6D2B79F5) | 0;
    var t = Math.imul(hat ^ (hat >>> 15), 1 | hat);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  var rafQ = [], rafId = 0, dungRaf = false;
  window.requestAnimationFrame = function (cb) { dungRaf = true; rafQ.push([++rafId, cb]); return rafId; };
  window.cancelAnimationFrame = function (id) { rafQ = rafQ.filter(function (x) { return x[0] !== id; }); };
  var hen = [], henId = 0;                      // [id, hạn(giây), cb, lặp(giây)|0, args]
  window.setTimeout = function (cb, ms) {
    var a = Array.prototype.slice.call(arguments, 2);
    hen.push([++henId, T + Math.max(0, +ms || 0) / 1000, cb, 0, a]); return henId;
  };
  window.setInterval = function (cb, ms) {
    var a = Array.prototype.slice.call(arguments, 2), p = Math.max(0.001, (+ms || 0) / 1000);
    hen.push([++henId, T + p, cb, p, a]); return henId;
  };
  window.clearTimeout = window.clearInterval = function (id) { hen = hen.filter(function (x) { return x[0] !== id; }); };
  function chayHen() {
    for (var vong = 0; vong < 10000; vong++) {
      var j = -1;
      for (var i = 0; i < hen.length; i++) if (hen[i][1] <= T + 1e-9 && (j < 0 || hen[i][1] < hen[j][1])) j = i;
      if (j < 0) return;
      var h = hen[j];
      if (h[3] > 0) h[1] += h[3]; else hen.splice(j, 1);
      try { typeof h[2] === 'function' ? h[2].apply(window, h[4]) : (0, eval)(String(h[2])); } catch (e) { ghiLoi(e, 'setTimeout'); }
    }
  }

  // ---- hoạt ảnh (Web Animations API — gồm cả CSS animation/transition)
  var anims = new Map();                        // Animation → lúc sinh (giây)
  window.ganTimeline = function (anim, batDau) {
    var b = +batDau || 0;
    try { anim.pause(); anims.set(anim, b); anim.currentTime = (T - b) * 1000; } catch (e) { ghiLoi(e, 'ganTimeline'); }
    return anim;
  };
  function quetAnim() {
    var ds = document.getAnimations ? document.getAnimations() : [];
    for (var i = 0; i < ds.length; i++) if (!anims.has(ds[i])) anims.set(ds[i], daDat ? T : 0);
  }
  function tuaAnim() {
    anims.forEach(function (b, a) {
      if (a.playState === 'idle') { anims.delete(a); return; }      // CSS gỡ class / trang tự huỷ
      try { if (a.playState !== 'paused') a.pause(); a.currentTime = (T - b) * 1000; } catch (e) {}
    });
  }

  function bam(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
    return (h >>> 0).toString(36);
  }

  window.__studio = {
    loi: loi,
    dat: function (t, dur) {
      T = +t || 0; DUR = +dur || DUR;
      chayHen();
      var q = rafQ; rafQ = [];
      for (var i = 0; i < q.length; i++) { try { q[i][1](T * 1000); } catch (e) { ghiLoi(e, 'requestAnimationFrame'); } }
      quetAnim(); tuaAnim();
      var k;
      if (typeof window.veTai === 'function') { try { k = window.veTai(T, DUR); } catch (e) { ghiLoi(e, 'veTai'); } }
      if (k && typeof k.then === 'function') {            // veTai bất đồng bộ (tua video làm texture, tải ảnh) → máy đợi rồi mới chụp
        var self = this;
        return k.then(function (v) { return self._ketThuc(v); }, function (e) { ghiLoi(e, 'veTai'); return self._ketThuc(undefined); });
      }
      return this._ketThuc(k);
    },
    _ketThuc: function (k) {
      quetAnim(); tuaAnim();
      daDat = true;
      var khoa;
      if (k !== undefined && k !== null && typeof k !== 'object' && typeof k !== 'function') khoa = 'k:' + String(k);
      else {
        var p = [];
        anims.forEach(function (b, a) {
          var ct = a.effect && a.effect.getComputedTiming ? a.effect.getComputedTiming() : null;
          p.push(ct ? (ct.progress == null ? 'n' : Math.round(ct.progress * 4000)) + '.' + (ct.currentIteration || 0) : '-');
        });
        khoa = bam(document.documentElement.outerHTML) + '|' + p.join(',');
        if (document.querySelector('canvas,video,iframe')) khoa += '|t' + Math.round(T * 1000);
      }
      var l = loi.splice(0, loi.length);
      return { khoa: khoa, loi: l };
    },
    thongTin: function () {
      return {
        veTai: typeof window.veTai === 'function',
        anim: anims.size, raf: dungRaf, hen: hen.length,
        canvas: !!document.querySelector('canvas,video,iframe'),
        rong: document.documentElement.scrollWidth, cao: document.documentElement.scrollHeight
      };
    },
    kiemTran: function () {                       // chữ nhìn thấy mà vượt khỏi hộp (viewport) > 2px → [{chu, trai, phai, tren, duoi}]
      var W = innerWidth, H = innerHeight, ra = [], r = document.createRange();
      var w = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
      for (var n = w.nextNode(); n && ra.length < 5; n = w.nextNode()) {
        if (!n.textContent.trim()) continue;
        var el = n.parentElement;
        if (!el || (el.checkVisibility && !el.checkVisibility({ opacityProperty: true, visibilityProperty: true }))) continue;
        r.selectNodeContents(n);
        var b = r.getBoundingClientRect();
        if (!b.width || !b.height) continue;
        var tr = Math.max(0, -b.left), ph = Math.max(0, b.right - W), te = Math.max(0, -b.top), du = Math.max(0, b.bottom - H);
        if (tr > 2 || ph > 2 || te > 2 || du > 2)
          ra.push({ chu: n.textContent.trim().slice(0, 40), trai: Math.round(tr), phai: Math.round(ph), tren: Math.round(te), duoi: Math.round(du) });
      }
      return ra;
    },
    sanSang: function () {
      var cho = [document.fonts ? document.fonts.ready : Promise.resolve()];
      (window.__STUDIO_FONT || []).forEach(function (f) { try { cho.push(document.fonts.load('400 32px "' + f + '"', 'ẤệởữđƯơ')); } catch (e) {} });
      if (window.sanSang && typeof window.sanSang.then === 'function') cho.push(window.sanSang);
      var anh = Array.prototype.slice.call(document.images || []).filter(function (im) { return !im.complete; })
        .map(function (im) { return new Promise(function (r) { im.addEventListener('load', r); im.addEventListener('error', r); }); });
      return Promise.all(cho.concat(anh)).then(function () { return document.fonts ? document.fonts.ready : null; })
        .then(function () { return true; }, function (e) { ghiLoi(e, 'sanSang'); return true; });
    }
  };
})();
