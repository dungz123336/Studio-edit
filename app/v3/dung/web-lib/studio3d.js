/* studio3d.js — bộ tay cầm three.js cho lớp web của Studio (không gu: chỉ dựng cảnh, thẻ, video, chữ; AI quyết mọi thứ).
   Máy tự tiêm khi trang có chữ "S3D" (kèm three.min.js). Mọi hàm tất định theo t do veTai(t) truyền vào.
   S3D.canh({fov, z, sang})            → {renderer, scene, cam, ve()}   (nền trong suốt, kích thước = hộp lớp)
   S3D.the({w, h, mau, anh, bo, day})  → mesh tấm thẻ (ảnh hoặc màu; day > 0 = khối mỏng có cạnh)
   S3D.video(url)                      → {video, tex, sanSang(), tua(t)}  — tua(t) trả Promise (await trong veTai)
   S3D.chu(text, {font, co, mau, dam, rong})  → mesh chữ (canvas texture, trong suốt), đơn vị 1 = 1/400 px cỡ chữ
   S3D.ease(ten, u)                    → linear|out|in_out|back
   S3D.quay(mesh, {x, y, z})           → đặt góc (độ) */
(function () {
  if (typeof THREE === 'undefined') { console.warn('S3D: thiếu THREE'); return; }
  const kep = (u, a = 0, b = 1) => Math.max(a, Math.min(b, u));
  const ease = (ten, u) => { u = kep(u); switch (ten) {
    case 'in': return u * u * u; case 'out': return 1 - Math.pow(1 - u, 3);
    case 'in_out': return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
    case 'back': { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(u - 1, 3) + c1 * Math.pow(u - 1, 2); }
    default: return u; } };
  const mauCss = (v) => { if (!v) return '#ffffff'; if (v[0] === '#') return v;
    const s = getComputedStyle(document.documentElement).getPropertyValue('--mau-' + v).trim(); return s || '#ffffff'; };
  function canh(o) {
    o = o || {};
    const W = +(window.KHUNG && KHUNG.w) || innerWidth, H = +(window.KHUNG && KHUNG.h) || innerHeight;
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, preserveDrawingBuffer: true });
    renderer.setSize(W, H); renderer.setClearColor(0x000000, 0); renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.style.display = 'block'; document.body.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(o.fov || 38, W / H, 0.05, 200); cam.position.set(0, 0, o.z != null ? o.z : 7);
    if (o.sang !== false) {
      scene.add(new THREE.AmbientLight(0xffffff, o.sangNen != null ? o.sangNen : 0.75));
      const L = new THREE.DirectionalLight(0xffffff, o.sangChinh != null ? o.sangChinh : 0.9); L.position.set(2.5, 3.5, 5); scene.add(L);
    }
    return { renderer, scene, cam, W, H, ve: () => { cam.lookAt(o.nhin ? new THREE.Vector3(...o.nhin) : new THREE.Vector3(0, 0, 0)); renderer.render(scene, cam); } };
  }
  const _tai = new THREE.TextureLoader();
  function the(o) {
    o = o || {};
    const w = o.w || 2, h = o.h || 1.2, day = o.day || 0;
    let mat;
    if (o.anh) { const t = _tai.load(o.anh); t.colorSpace = THREE.SRGBColorSpace; mat = new THREE.MeshBasicMaterial({ map: t, transparent: true }); }
    else if (o.tex) { mat = new THREE.MeshBasicMaterial({ map: o.tex, transparent: true }); }
    else mat = new THREE.MeshStandardMaterial({ color: new THREE.Color(mauCss(o.mau || 'sang')), roughness: o.nham != null ? o.nham : 0.5, metalness: o.kim || 0 });
    let geo;
    if (day > 0) geo = new THREE.BoxGeometry(w, h, day); else geo = new THREE.PlaneGeometry(w, h);
    const m = new THREE.Mesh(geo, day > 0 ? [new THREE.MeshStandardMaterial({ color: new THREE.Color(mauCss(o.mauCanh || 'toi')) }),
      new THREE.MeshStandardMaterial({ color: new THREE.Color(mauCss(o.mauCanh || 'toi')) }), new THREE.MeshStandardMaterial({ color: new THREE.Color(mauCss(o.mauCanh || 'toi')) }),
      new THREE.MeshStandardMaterial({ color: new THREE.Color(mauCss(o.mauCanh || 'toi')) }), mat, mat] : mat);
    if (o.x != null || o.y != null || o.z != null) m.position.set(o.x || 0, o.y || 0, o.z || 0);
    return m;
  }
  function video(url) {
    const v = document.createElement('video'); v.muted = true; v.playsInline = true; v.preload = 'auto'; v.src = url; v.style.display = 'none';
    document.body.appendChild(v);
    const san = new Promise((r) => { v.addEventListener('loadeddata', r, { once: true }); v.addEventListener('error', r, { once: true }); });
    const tex = new THREE.VideoTexture(v); tex.minFilter = THREE.LinearFilter; tex.magFilter = THREE.LinearFilter; tex.colorSpace = THREE.SRGBColorSpace;
    async function tua(t) {
      await san;
      t = Math.max(0, Math.min(t, (v.duration || t) - 0.03));
      if (Math.abs(v.currentTime - t) > 0.02) { await new Promise((r) => { v.addEventListener('seeked', r, { once: true }); v.currentTime = t; }); }
      tex.needsUpdate = true;
    }
    return { video: v, tex, sanSang: () => san, tua, ti_le: () => (v.videoWidth && v.videoHeight) ? v.videoWidth / v.videoHeight : 9 / 16 };
  }
  function chu(text, o) {
    o = o || {};
    const co = o.co || 96, pad = Math.round(co * 0.3);
    const cv = document.createElement('canvas'), c = cv.getContext('2d');
    const font = `${o.dam || 700} ${co}px ${o.font ? 'var(--font-' + o.font + ')' : 'var(--font-tieu-de)'}`.replace('var(--font-tieu-de)', getComputedStyle(document.documentElement).getPropertyValue('--font-tieu-de') || 'sans-serif')
      .replace(/var\(--font-([a-z-]+)\)/, (m, v) => getComputedStyle(document.documentElement).getPropertyValue('--font-' + v) || 'sans-serif');
    c.font = font;
    const dong = String(text).split('\n'); const rong = Math.max(...dong.map((d) => c.measureText(d).width));
    cv.width = Math.ceil(rong + pad * 2); cv.height = Math.ceil(co * 1.25 * dong.length + pad * 2);
    c.font = font; c.textBaseline = 'top'; c.fillStyle = mauCss(o.mau || 'sang');
    if (o.vien) { c.lineWidth = o.vien; c.strokeStyle = mauCss(o.mauVien || 'toi'); }
    dong.forEach((d, i) => { const x = pad + (o.can === 'giua' ? (rong - c.measureText(d).width) / 2 : 0), y = pad + i * co * 1.25;
      if (o.vien) c.strokeText(d, x, y); c.fillText(d, x, y); });
    const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace;
    const s = (o.rong || (cv.width / 400));
    const m = new THREE.Mesh(new THREE.PlaneGeometry(s, s * cv.height / cv.width), new THREE.MeshBasicMaterial({ map: tex, transparent: true }));
    return m;
  }
  const quay = (m, g) => { if (g.x != null) m.rotation.x = g.x * Math.PI / 180; if (g.y != null) m.rotation.y = g.y * Math.PI / 180; if (g.z != null) m.rotation.z = g.z * Math.PI / 180; return m; };
  window.S3D = { canh, the, video, chu, ease, quay, mau: mauCss };
})();
