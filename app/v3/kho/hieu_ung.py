# -*- coding: utf-8 -*-
"""Kho hiệu ứng engine: video xem trước 540×960, 3 s cho từng hiệu ứng lớp (KIEN-TRUC §4).

sinh(ep=False, tien_do=None) → danh sách [{"id","ten","mo_ta","video","json","anh","cach":"engine|du_phong|placeholder"}]
   - danh sách hiệu ứng = 10 mẫu có sẵn + khối ```json trong ai/cheat_sheet.md (nếu có, có trường "id" và "kieu")
   - ưu tiên engine dung/ (dung.lop.tao_lop + .hop() + .ve(lt)); chưa có / lỗi → bộ vẽ dự phòng bằng skia (cùng tinh thần spec)
   - cả hai cùng lỗi → PNG placeholder ghi "chưa dựng được"
   - kết quả: kho-chi-muc/hieu-ung/<id>.mp4 + <id>.json (spec để chép) + <id>.jpg (khung bìa) + danh-sach.json
danh_sach() → đọc danh-sach.json (không sinh)
Chạy lại được bất cứ lúc nào (ep=True để ép dựng lại khi engine đã xong)."""
import os, sys, re, json, math, time, subprocess, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

W, H, FPS, DAI = 540, 960, 30, 3.0
VANG, XANH, TRANG, TOI = "#E6E6E6", "#9AD0F5", "#FFFFFF", "#15151A"     # 1.2.19: xem trước hiệu ứng dùng màu trung tính (không màu "nhà")

MAU = [
    {"id": "hook_pop_tach_tu", "ten": "Hook pop tách từ", "mo_ta": "Chữ hook lớn, từng từ bật lên (pop, ease back) so le 0,06 s trên nền pill màu nhấn.",
     "lop": {"id": "hook", "kieu": "chu", "t0": 0.2, "t1": 2.8, "noi_dung": {"text": "3 LỖI\nKHI QUAY"},
             "kieu_dang": {"font": "tieu_de", "co": 120, "dam": 800, "mau": "#111", "hoa": True, "can": "giua", "nen": {"mau": VANG, "dem": [28, 16], "bo": 18}, "rong_max": 0.86},
             "vi_tri": {"anchor": "mc", "x": 0.5, "y": 0.3, "so_voi": "khung"},
             "anim": {"vao": {"kieu": "pop", "dai": 0.32, "ease": "back", "tu": {"scale": 0.6, "opacity": 0, "y": 24}}, "ra": {"kieu": "fade", "dai": 0.2, "toi": {"opacity": 0, "y": -16}}, "tach": "tu", "so_le": 0.06}}},
    {"id": "chu_gradient_truot", "ten": "Chữ gradient trượt", "mo_ta": "Tiêu đề tô gradient trắng → xanh, trượt vào từ trái (slide, ease out), bóng mềm.",
     "lop": {"id": "tieu_de", "kieu": "chu", "t0": 0.2, "t1": 2.8, "noi_dung": {"text": "EDIT NHANH\nGẤP 3 LẦN"},
             "kieu_dang": {"font": "tieu_de", "co": 110, "dam": 900, "hoa": True, "can": "giua", "gradient": {"mau": [TRANG, XANH], "goc": 90}, "bong": [{"x": 0, "y": 14, "mo": 24, "mau": "#0009"}]},
             "vi_tri": {"anchor": "mc", "x": 0.5, "y": 0.32, "so_voi": "khung"},
             "anim": {"vao": {"kieu": "slide", "dai": 0.4, "ease": "out", "tu": {"x": -80, "opacity": 0}}, "ra": {"kieu": "fade", "dai": 0.2}}}},
    {"id": "pill_slide", "ten": "Pill slide", "mo_ta": "Thẻ pill tối viền màu nhấn kèm chấm nhấn, trượt từ trái vào dưới cằm.",
     "lop": {"id": "the1", "kieu": "the", "t0": 0.2, "t1": 2.8, "noi_dung": {"text": "97% người mới mắc", "icon": None},
             "kieu_dang": {"hinh": "pill", "mau": "#111c", "vien": {"w": 2, "mau": VANG}, "dem": [32, 20], "chu": {"co": 44, "mau": TRANG, "font": "nhan", "dam": 700}, "bong": [{"x": 0, "y": 10, "mo": 20, "mau": "#0008"}]},
             "vi_tri": {"anchor": "bc", "x": 0.5, "y": 0.12, "so_voi": "duoi_cam"},
             "anim": {"vao": {"kieu": "slide", "tu": {"x": -60, "opacity": 0}, "dai": 0.3, "ease": "out"}, "ra": {"kieu": "fade", "dai": 0.2}}}},
    {"id": "the_so_lon", "ten": "Thẻ số lớn", "mo_ta": "Con số lớn tô gradient màu nhấn bật lên (back), dòng chú thích hiện sau 0,3 s.",
     "lop": [{"id": "so", "kieu": "chu", "t0": 0.2, "t1": 2.8, "noi_dung": {"text": "97%"},
              "kieu_dang": {"font": "tieu_de", "co": 220, "dam": 900, "can": "giua", "gradient": {"mau": [VANG, "#FF7A00"], "goc": 90}, "bong": [{"x": 0, "y": 16, "mo": 30, "mau": "#000a"}]},
              "vi_tri": {"anchor": "mc", "x": 0.5, "y": 0.42, "so_voi": "khung"},
              "anim": {"vao": {"kieu": "pop", "dai": 0.35, "ease": "back", "tu": {"scale": 0.5, "opacity": 0}}, "ra": {"kieu": "fade", "dai": 0.2}}},
             {"id": "chu_thich", "kieu": "chu", "t0": 0.5, "t1": 2.8, "noi_dung": {"text": "người mới mắc lỗi này"},
              "kieu_dang": {"font": "nhan", "co": 46, "dam": 600, "mau": TRANG, "can": "giua"},
              "vi_tri": {"anchor": "mc", "x": 0.5, "y": 0.56, "so_voi": "khung"},
              "anim": {"vao": {"kieu": "fade", "dai": 0.3, "tu": {"y": 20}}, "ra": {"kieu": "fade", "dai": 0.2}}}]},
    {"id": "phu_de_karaoke", "ten": "Phụ đề karaoke", "mo_ta": "Phụ đề cụm ≤ 22 chữ, từ đang nói đổi màu nhấn + nảy nhẹ, viền đen 8.",
     "phu_de": {"che_do": "cum", "toi_da_chu": 22, "karaoke": True,
                "kieu_dang": {"font": "phu_de", "co": 60, "dam": 800, "mau": TRANG, "mau_noi": VANG, "vien": [{"w": 8, "mau": "#000"}], "hoa": False},
                "vi_tri": {"anchor": "bc", "x": 0.5, "y": 0.3, "so_voi": "khung"}, "anim": {"vao": {"kieu": "pop", "dai": 0.12, "ease": "out", "tu": {"scale": 0.9}}}},
     "mau_loi": ["Ba", "lỗi", "khi", "quay", "video", "dọc"]},
    {"id": "gach_chan_ve_dan", "ten": "Gạch chân vẽ dần", "mo_ta": "Chữ nhấn + đường gạch chân màu nhấn vẽ dần từ trái sang trong 0,4 s.",
     "lop": [{"id": "chu", "kieu": "chu", "t0": 0.2, "t1": 2.8, "noi_dung": {"text": "QUAN TRỌNG"},
              "kieu_dang": {"font": "tieu_de", "co": 96, "dam": 900, "mau": TRANG, "can": "giua", "hoa": True},
              "vi_tri": {"anchor": "mc", "x": 0.5, "y": 0.4, "so_voi": "khung"}, "anim": {"vao": {"kieu": "fade", "dai": 0.25}}},
             {"id": "gach", "kieu": "duong", "t0": 0.5, "t1": 2.8, "noi_dung": {"loai": "gach_chan", "tu": [0.12, 0.455], "den": [0.88, 0.455]},
              "kieu_dang": {"w": 10, "mau": VANG, "ve": 0.4}}]},
    {"id": "khung_khoanh", "ten": "Khung khoanh", "mo_ta": "Khung bo góc màu nhấn vẽ dần quanh vùng cần chú ý + nhãn nhỏ ở góc.",
     "lop": [{"id": "khung", "kieu": "duong", "t0": 0.2, "t1": 2.8, "noi_dung": {"loai": "khung", "tu": [0.2, 0.28], "den": [0.8, 0.62]},
              "kieu_dang": {"w": 7, "mau": VANG, "ve": 0.6, "bo": 18}},
             {"id": "nhan", "kieu": "the", "t0": 0.8, "t1": 2.8, "noi_dung": {"text": "lỗi 1"},
              "kieu_dang": {"hinh": "rect", "mau": VANG, "bo": 8, "dem": [16, 8], "chu": {"co": 32, "mau": "#111", "dam": 800}},
              "vi_tri": {"anchor": "bl", "x": 0.2, "y": 0.27, "so_voi": "khung"}, "anim": {"vao": {"kieu": "pop", "dai": 0.2, "ease": "back"}}}]},
    {"id": "anh_ken_burns", "ten": "Ảnh Ken Burns", "mo_ta": "Ảnh minh hoạ bo góc, viền trắng, bóng; zoom chậm 1,0 → 1,08 suốt thời gian hiện.",
     "lop": {"id": "anh1", "kieu": "hinh", "t0": 0.0, "t1": 3.0, "noi_dung": {"duong": "<id kho|đường dẫn>"},
             "kieu_dang": {"fit": "cover", "bo": 24, "vien": {"w": 4, "mau": TRANG}, "bong": [{"x": 0, "y": 18, "mo": 30, "mau": "#000a"}]},
             "vi_tri": {"anchor": "mc", "x": 0.5, "y": 0.45, "w": 0.8, "h": 0.4}, "anim": {"vao": {"kieu": "fade", "dai": 0.3}, "ken_burns": {"z": [1.0, 1.08]}}}},
    {"id": "flash_chuyen_canh", "ten": "Flash chuyển cảnh", "mo_ta": "Chớp trắng 0,2 s tại mốc cắt kèm zoom nhẹ, dùng giữa hai cảnh.",
     "chuyen_canh": [{"t": 1.5, "kieu": "flash", "dai": 0.2}], "camera": [{"t": 1.5, "z": 1.0}, {"t": 1.5, "z": 1.1, "dai": 0}, {"t": 2.2, "z": 1.0, "ease": "out", "dai": 0.7}]},
    {"id": "chu_typewriter", "ten": "Chữ typewriter", "mo_ta": "Chữ hiện từng ký tự (0,05 s/ký tự) với con trỏ nhấp nháy, nền hộp tối.",
     "lop": {"id": "cau", "kieu": "chu", "t0": 0.2, "t1": 2.9, "noi_dung": {"text": "Bạn có biết…\n90% video bị lướt?"},
             "kieu_dang": {"font": "nhan", "co": 56, "dam": 600, "mau": TRANG, "can": "trai", "nen": {"mau": "#111d", "dem": [26, 20], "bo": 14}, "rong_max": 0.86},
             "vi_tri": {"anchor": "ml", "x": 0.07, "y": 0.4, "so_voi": "khung"},
             "anim": {"vao": {"kieu": "typewriter", "dai": 1.4}, "ra": {"kieu": "fade", "dai": 0.2}}}},
]


def _thu_muc():
    d = os.path.join(chung.duong("kho_chi_muc"), "hieu-ung")
    os.makedirs(d, exist_ok=True)
    return d


def _tu_cheat_sheet():
    """khối ```json trong ai/cheat_sheet.md có "id" + "kieu" (1 lớp) hoặc "lop" → thêm hiệu ứng"""
    p = os.path.join(chung.duong("app"), "ai", "cheat_sheet.md")
    ra = []
    if not os.path.isfile(p):
        return ra
    try:
        md = open(p, "r", encoding="utf-8").read()
    except Exception:
        return ra
    for kh in re.findall(r"```(?:json|jsonc)\s*(.*?)```", md, re.S):
        kh = re.sub(r"//[^\n]*", "", kh)
        try:
            j = json.loads(kh)
        except Exception:
            continue
        if isinstance(j, dict) and j.get("kieu") and j.get("id"):
            ra.append({"id": "cs_" + chung.slug(j["id"]), "ten": f"Cheat sheet: {j['id']}", "mo_ta": "Ví dụ từ ai/cheat_sheet.md", "lop": j})
        elif isinstance(j, dict) and isinstance(j.get("lop"), list):
            for l in j["lop"]:
                if isinstance(l, dict) and l.get("kieu") and l.get("id"):
                    ra.append({"id": "cs_" + chung.slug(l["id"]), "ten": f"Cheat sheet: {l['id']}", "mo_ta": "Ví dụ từ ai/cheat_sheet.md", "lop": l})
    return ra


def danh_sach_mau():
    ds = list(MAU)
    co = {h["id"] for h in ds}
    for h in _tu_cheat_sheet():
        if h["id"] not in co:
            ds.append(h); co.add(h["id"])
    return ds


# ============================================================================= bộ vẽ dự phòng (skia)
def _ease(ten, u):
    u = min(1.0, max(0.0, u))
    if ten == "in":
        return u * u
    if ten == "out":
        return 1 - (1 - u) ** 2
    if ten == "in_out":
        return 2 * u * u if u < 0.5 else 1 - (-2 * u + 2) ** 2 / 2
    if ten == "back":
        c1, c3 = 1.70158, 2.70158
        return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2
    if ten == "expo":
        return 1 if u >= 1 else 1 - 2 ** (-10 * u)
    if ten == "spring":
        return 1 - math.exp(-6 * u) * math.cos(10 * u)
    return u


def _mau(s, a=1.0):
    import skia
    s = s.lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    al = int(s[6:8], 16) if len(s) >= 8 else 255
    return skia.Color(r, g, b, int(al * a))


class _Ve:
    """bộ vẽ dự phòng: dựng hiệu ứng bằng skia cho đúng tinh thần spec (không phải engine thật)"""

    def __init__(self):
        import skia
        self.sk = skia
        self.tf_dam = self._font_kho(900) or skia.Typeface("Segoe UI", skia.FontStyle.Bold()) or skia.Typeface.MakeDefault()
        self.tf_thuong = self._font_kho(600) or skia.Typeface("Segoe UI", skia.FontStyle.Normal()) or skia.Typeface.MakeDefault()
        self.anh = self._anh_mau()

    def _font_kho(self, dam):
        try:
            from kho import tim
            uu = ["poppins", "be vietnam", "montserrat", "inter", "roboto", "segoe"]
            ung = [m for m in tim.tat_ca() if m["loai"] == "font" and m.get("du_dau") and not m["so_do"].get("nghieng")]
            if not ung:
                return None
            ung.sort(key=lambda m: (next((i for i, u in enumerate(uu) if u in chung.khong_dau(m["ten"])), 99), abs((m["so_do"].get("dam") or 400) - dam)))
            return self.sk.Typeface.MakeFromFile(ung[0]["duong"])
        except Exception:
            return None

    def _anh_mau(self):
        try:
            from kho import xem_truoc
            p = xem_truoc.mau_anh()
            return self.sk.Image.open(p)
        except Exception:
            return None

    # ---- nền chung: gradient tối + vùng "mặt" mờ để thấy vị trí lớp
    def nen(self, c, t, mau=("#141622", "#07080c")):
        sk = self.sk
        p = sk.Paint(Shader=sk.GradientShader.MakeLinear([sk.Point(0, 0), sk.Point(0, H)], [_mau(mau[0]), _mau(mau[1])]))
        c.drawRect(sk.Rect.MakeWH(W, H), p)
        g = sk.Paint(AntiAlias=True, Color=sk.Color(255, 255, 255, 14), MaskFilter=sk.MaskFilter.MakeBlur(sk.kNormal_BlurStyle, 60))
        c.drawOval(sk.Rect.MakeXYWH(W * 0.28, H * 0.5, W * 0.44, H * 0.3), g)
        pv = sk.Paint(Color=sk.Color(255, 255, 255, 10), StrokeWidth=1, Style=sk.Paint.kStroke_Style)
        for x in range(0, W, 60):
            c.drawLine(x, 0, x, H, pv)
        for y in range(0, H, 60):
            c.drawLine(0, y, W, y, pv)

    def chu(self, c, text, x, y, co, mau=TRANG, dam=True, can="giua", vien=None, gradient=None, opacity=1.0, scale=1.0, bong=None):
        sk = self.sk
        font = sk.Font(self.tf_dam if dam else self.tf_thuong, co)
        font.setSubpixel(True)
        w = font.measureText(text)
        x0 = x - w / 2 if can == "giua" else (x - w if can == "phai" else x)
        c.save()
        c.translate(x0 + w / 2, y)
        c.scale(scale, scale)
        if bong:
            pb = sk.Paint(AntiAlias=True, Color=_mau("#000000", 0.6 * opacity), MaskFilter=sk.MaskFilter.MakeBlur(sk.kNormal_BlurStyle, bong))
            c.drawString(text, -w / 2, bong * 0.6, font, pb)
        if vien:
            pv = sk.Paint(AntiAlias=True, Color=_mau(vien[1], opacity), Style=sk.Paint.kStroke_Style, StrokeWidth=vien[0], StrokeJoin=sk.Paint.kRound_Join)
            c.drawString(text, -w / 2, 0, font, pv)
        p = sk.Paint(AntiAlias=True, Color=_mau(mau, opacity))
        if gradient:
            p.setShader(sk.GradientShader.MakeLinear([sk.Point(-w / 2, -co), sk.Point(w / 2, 0)], [_mau(gradient[0], opacity), _mau(gradient[1], opacity)]))
        c.drawString(text, -w / 2, 0, font, p)
        c.restore()
        return w

    def do_chu(self, text, co, dam=True):
        return self.sk.Font(self.tf_dam if dam else self.tf_thuong, co).measureText(text)

    def pill(self, c, x, y, w, h, mau, bo, vien=None, opacity=1.0, bong=True):
        sk = self.sk
        r = sk.Rect.MakeXYWH(x, y, w, h)
        if bong:
            pb = sk.Paint(AntiAlias=True, Color=_mau("#000000", 0.5 * opacity), MaskFilter=sk.MaskFilter.MakeBlur(sk.kNormal_BlurStyle, 14))
            c.drawRoundRect(sk.Rect.MakeXYWH(x, y + 10, w, h), bo, bo, pb)
        c.drawRoundRect(r, bo, bo, sk.Paint(AntiAlias=True, Color=_mau(mau, opacity)))
        if vien:
            c.drawRoundRect(r, bo, bo, sk.Paint(AntiAlias=True, Color=_mau(vien[1], opacity), Style=sk.Paint.kStroke_Style, StrokeWidth=vien[0]))

    # ---- từng hiệu ứng
    def hook_pop_tach_tu(self, c, t):
        self.nen(c, t)
        dong = ["3 LỖI", "KHI QUAY"]
        co, dem = 100, 0
        y0 = H * 0.3 - 40
        for i, d in enumerate(dong):
            tu = d.split(" ")
            widths = [self.do_chu(w, co) + 44 for w in tu]
            tong = sum(widths) + 16 * (len(tu) - 1)
            x = W / 2 - tong / 2
            for j, w in enumerate(tu):
                k = dem; dem += 1
                lt = t - (0.2 + k * 0.08)
                u = _ease("back", lt / 0.32) if lt >= 0 else 0
                if lt < 0:
                    x += widths[j] + 16; continue
                op = min(1, lt / 0.15)
                if t > 2.6:
                    op *= max(0, 1 - (t - 2.6) / 0.2)
                dy = 24 * (1 - min(1, lt / 0.32))
                sc = 0.6 + 0.4 * u
                cx, cy = x + widths[j] / 2, y0 + i * 150 + dy
                c.save(); c.translate(cx, cy); c.scale(sc, sc)
                self.pill(c, -widths[j] / 2, -co * 1.02, widths[j], co * 1.32, VANG, 18, opacity=op)
                self.chu(c, w, 0, 0, co, "#111111", opacity=op)
                c.restore()
                x += widths[j] + 16

    def chu_gradient_truot(self, c, t):
        self.nen(c, t)
        lt = t - 0.2
        if lt < 0:
            return
        u = _ease("out", lt / 0.4)
        op = min(1, lt / 0.25) * (max(0, 1 - (t - 2.8) / 0.2) if t > 2.8 else 1)
        dx = -80 * (1 - u)
        for i, d in enumerate(["EDIT NHANH", "GẤP 3 LẦN"]):
            self.chu(c, d, W / 2 + dx, H * 0.32 + i * 118, 104, gradient=(TRANG, XANH), opacity=op, bong=12)

    def pill_slide(self, c, t):
        self.nen(c, t)
        lt = t - 0.2
        if lt < 0:
            return
        u = _ease("out", lt / 0.3)
        op = min(1, lt / 0.2) * (max(0, 1 - (t - 2.8) / 0.2) if t > 2.8 else 1)
        text = "97% người mới mắc"
        co = 42; w = self.do_chu(text, co) + 64 + 34; h = 84
        x = W / 2 - w / 2 - 60 * (1 - u); y = H * 0.66
        self.pill(c, x, y, w, h, "#111111cc", 42, vien=(2, VANG), opacity=op)
        c.drawCircle(x + 40, y + h / 2, 10, self.sk.Paint(AntiAlias=True, Color=_mau(VANG, op)))
        self.chu(c, text, x + 66, y + h / 2 + co * 0.36, co, TRANG, can="trai", opacity=op)

    def the_so_lon(self, c, t):
        self.nen(c, t)
        lt = t - 0.2
        if lt >= 0:
            u = _ease("back", lt / 0.35)
            op = min(1, lt / 0.15) * (max(0, 1 - (t - 2.8) / 0.2) if t > 2.8 else 1)
            self.chu(c, "97%", W / 2, H * 0.42 + 70, 210, gradient=(VANG, "#FF7A00"), opacity=op, scale=0.5 + 0.5 * u, bong=16)
        lt2 = t - 0.5
        if lt2 >= 0:
            u = _ease("out", lt2 / 0.3)
            op = u * (max(0, 1 - (t - 2.8) / 0.2) if t > 2.8 else 1)
            self.chu(c, "người mới mắc lỗi này", W / 2, H * 0.56 + 20 * (1 - u), 44, TRANG, dam=False, opacity=op)

    def phu_de_karaoke(self, c, t):
        self.nen(c, t)
        tu = ["Ba", "lỗi", "khi", "quay", "video", "dọc"]
        co = 54
        ws = [self.do_chu(w, co) for w in tu]
        tong = sum(ws) + 18 * (len(tu) - 1)
        if tong > W * 0.9:
            co = co * W * 0.9 / tong
            ws = [self.do_chu(w, co) for w in tu]
            tong = sum(ws) + 18 * (len(tu) - 1)
        x = W / 2 - tong / 2; y = H * 0.7
        for i, w in enumerate(tu):
            tb = 0.3 + i * 0.4
            dang = tb <= t < tb + 0.4
            qua = t >= tb + 0.4
            mau = VANG if dang else TRANG
            sc = 1.0
            if dang:
                sc = 0.9 + 0.1 * _ease("out", (t - tb) / 0.12)
            self.chu(c, w, x + ws[i] / 2, y, co, mau, vien=(8, "#000000"), scale=sc)
            x += ws[i] + 18

    def gach_chan_ve_dan(self, c, t):
        self.nen(c, t)
        lt = t - 0.2
        if lt < 0:
            return
        op = min(1, lt / 0.25)
        self.chu(c, "QUAN TRỌNG", W / 2, H * 0.4, 92, TRANG, opacity=op, bong=10)
        lt2 = t - 0.5
        if lt2 >= 0:
            u = _ease("out", lt2 / 0.4)
            x0, x1 = W * 0.12, W * 0.88
            p = self.sk.Paint(AntiAlias=True, Color=_mau(VANG), StrokeWidth=10, StrokeCap=self.sk.Paint.kRound_Cap)
            c.drawLine(x0, H * 0.455, x0 + (x1 - x0) * u, H * 0.455, p)

    def khung_khoanh(self, c, t):
        sk = self.sk
        self.nen(c, t)
        lt = t - 0.2
        if lt < 0:
            return
        u = _ease("in_out", lt / 0.6)
        r = sk.Rect.MakeLTRB(W * 0.2, H * 0.28, W * 0.8, H * 0.62)
        path = sk.Path(); path.addRRect(sk.RRect.MakeRectXY(r, 18, 18))
        pm = sk.PathMeasure(path, False)
        seg = sk.Path()
        pm.getSegment(0, pm.getLength() * u, seg, True)
        c.drawPath(seg, sk.Paint(AntiAlias=True, Color=_mau(VANG), Style=sk.Paint.kStroke_Style, StrokeWidth=7, StrokeCap=sk.Paint.kRound_Cap))
        lt2 = t - 0.8
        if lt2 >= 0:
            s = 0.6 + 0.4 * _ease("back", lt2 / 0.2)
            c.save(); c.translate(W * 0.2 + 46, H * 0.27 - 20); c.scale(s, s)
            self.pill(c, -46, -22, 92, 44, VANG, 8, bong=False)
            self.chu(c, "lỗi 1", 0, 11, 30, "#111111")
            c.restore()

    def anh_ken_burns(self, c, t):
        sk = self.sk
        self.nen(c, t)
        op = min(1, t / 0.3)
        bw, bh = W * 0.8, H * 0.4
        r = sk.Rect.MakeXYWH(W / 2 - bw / 2, H * 0.45 - bh / 2, bw, bh)
        pb = sk.Paint(AntiAlias=True, Color=_mau("#000000", 0.6 * op), MaskFilter=sk.MaskFilter.MakeBlur(sk.kNormal_BlurStyle, 16))
        c.drawRoundRect(sk.Rect.MakeXYWH(r.left(), r.top() + 18, bw, bh), 24, 24, pb)
        c.save()
        c.clipRRect(sk.RRect.MakeRectXY(r, 24, 24), True)
        z = 1.0 + 0.08 * (t / DAI)
        if self.anh:
            iw, ih = self.anh.width(), self.anh.height()
            s = max(bw / iw, bh / ih) * z
            dw, dh = iw * s, ih * s
            c.drawImageRect(self.anh, sk.Rect.MakeXYWH(r.centerX() - dw / 2, r.centerY() - dh / 2, dw, dh), sk.SamplingOptions(sk.FilterMode.kLinear), sk.Paint(Alpha=int(255 * op)))
        else:
            c.drawRect(r, sk.Paint(Shader=sk.GradientShader.MakeLinear([sk.Point(r.left(), r.top()), sk.Point(r.right(), r.bottom())], [_mau(XANH, op), _mau("#7c3aed", op)])))
        c.restore()
        c.drawRoundRect(r, 24, 24, sk.Paint(AntiAlias=True, Color=_mau(TRANG, op), Style=sk.Paint.kStroke_Style, StrokeWidth=4))

    def flash_chuyen_canh(self, c, t):
        sk = self.sk
        if t < 1.5:
            self.nen(c, t, ("#1b2a4a", "#0a0f1c"))
            self.chu(c, "CẢNH 1", W / 2, H * 0.45, 90, TRANG, bong=10)
        else:
            z = 1.1 - 0.1 * _ease("out", (t - 1.5) / 0.7)
            c.save(); c.translate(W / 2, H / 2); c.scale(z, z); c.translate(-W / 2, -H / 2)
            self.nen(c, t, ("#3a1b2a", "#1c0a10"))
            self.chu(c, "CẢNH 2", W / 2, H * 0.45, 90, VANG, bong=10)
            c.restore()
        d = abs(t - 1.5)
        if t >= 1.4 and t <= 1.75:
            a = (t - 1.4) / 0.1 if t < 1.5 else max(0, 1 - (t - 1.5) / 0.25)
            c.drawRect(sk.Rect.MakeWH(W, H), sk.Paint(Color=_mau(TRANG, a)))

    def chu_typewriter(self, c, t):
        self.nen(c, t)
        lt = t - 0.2
        if lt < 0:
            return
        dong = ["Bạn có biết…", "90% video bị lướt?"]
        tong = sum(len(d) for d in dong)
        n = min(tong, int(lt / 0.05))
        op = max(0, 1 - (t - 2.9) / 0.1) if t > 2.9 else 1
        co = 52
        bw = max(self.do_chu(d, co, dam=False) for d in dong) + 52
        bh = co * 1.3 * len(dong) + 40
        x0, y0 = W * 0.07, H * 0.4 - bh / 2
        self.pill(c, x0, y0, bw, bh, "#111111dd", 14, opacity=op, bong=False)
        con_lai = n
        for i, d in enumerate(dong):
            phan = d[:max(0, con_lai)]
            con_lai -= len(d)
            y = y0 + 26 + co * 0.85 + i * co * 1.3
            w = self.chu(c, phan, x0 + 26, y, co, TRANG, dam=False, can="trai", opacity=op)
            if (con_lai < 0 or (con_lai == 0 and i == len(dong) - 1)) and int(t * 2) % 2 == 0:
                c.drawRect(self.sk.Rect.MakeXYWH(x0 + 26 + w + 6, y - co * 0.8, 4, co), self.sk.Paint(Color=_mau(VANG, op)))
                break

    def ve(self, hid, c, t):
        ham = getattr(self, hid, None)
        if ham is None:
            raise RuntimeError("không có bộ vẽ dự phòng cho " + hid)
        ham(c, t)


# ============================================================================= engine thật (dung/)
def _engine(hu, c, t, ctx):
    """thử dựng bằng dung.lop (hợp đồng §5). Ném lỗi nếu engine chưa có."""
    lop_mod = importlib.import_module("dung.lop")
    import numpy as np, skia
    specs = hu.get("lop")
    if specs is None:
        raise RuntimeError("hiệu ứng không có lớp để engine dựng")
    specs = specs if isinstance(specs, list) else [specs]
    if "lops" not in ctx:
        ctx["lops"] = [lop_mod.tao_lop(s, ctx["ctx"]) for s in specs]
    for lop, spec in zip(ctx["lops"], specs):
        t0, t1 = float(spec.get("t0", 0)), float(spec.get("t1", DAI))
        if not (t0 <= t < t1):
            continue
        x0, y0, x1, y1 = lop.hop()
        rgba = lop.ve(t - t0)
        if rgba is None:
            continue
        arr = np.ascontiguousarray(rgba, dtype=np.uint8)
        img = skia.Image.fromarray(arr, skia.kRGBA_8888_ColorType)
        c.drawImage(img, x0, y0)


# ============================================================================= sinh video
def _ghi_mp4(duong, khung_iter, poster=None):
    """khung_iter: sinh bytes RGBA từng khung → mp4 h264"""
    cmd = [chung.duong("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", duong]
    e = dict(os.environ); e.setdefault("PYTHONUTF8", "1")
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=e, creationflags=chung._NO_WINDOW)
    try:
        for b in khung_iter:
            pr.stdin.write(b)
    finally:
        pr.stdin.close()
        err = pr.stderr.read().decode("utf-8", "replace")
        pr.wait()
    if pr.returncode != 0:
        raise RuntimeError("ffmpeg: " + err[-200:])


def _placeholder(hu, duong_png, ly_do):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGB", (W, H), (14, 14, 18))
    dr = ImageDraw.Draw(im)
    try:
        f1 = ImageFont.truetype("segoeuib.ttf", 40); f2 = ImageFont.truetype("segoeui.ttf", 24)
    except Exception:
        f1 = f2 = ImageFont.load_default()
    dr.text((40, H * 0.4), hu["ten"], fill=(255, 210, 0), font=f1)
    dr.text((40, H * 0.4 + 70), "chưa dựng được", fill=(220, 220, 230), font=f2)
    dr.text((40, H * 0.4 + 110), (ly_do or "")[:60], fill=(140, 140, 150), font=f2)
    im.save(duong_png)
    return duong_png


def _sinh_mot(hu, d, ep, ve_du_phong):
    import skia
    hid = hu["id"]
    mp4 = os.path.join(d, hid + ".mp4"); js = os.path.join(d, hid + ".json"); jpg = os.path.join(d, hid + ".jpg")
    spec = {k: v for k, v in hu.items() if k not in ("id", "ten", "mo_ta")}
    spec["ghi_chu"] = f"{hu['ten']} — {hu['mo_ta']}"
    chung.ghi_json(js, spec)
    ra = {"id": hid, "ten": hu["ten"], "mo_ta": hu["mo_ta"], "json": os.path.basename(js), "video": "", "anh": "", "cach": ""}
    if not ep and os.path.isfile(mp4) and os.path.getsize(mp4) > 0 and os.path.isfile(jpg):
        cu = chung.doc_json(os.path.join(d, "danh-sach.json"), []) or []
        c_cu = next((x for x in cu if x.get("id") == hid), None)
        ra.update({"video": os.path.basename(mp4), "anh": os.path.basename(jpg), "cach": (c_cu or {}).get("cach") or "du_phong"})
        return ra
    info = skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType)
    surf = skia.Surface.MakeRaster(info)
    canvas = surf.getCanvas()
    n = int(DAI * FPS)
    poster_idx = int(1.2 * FPS)

    def chay(cach):
        ctx = {"ctx": {"W": W, "H": H, "fps": FPS, "font": None, "kho": None, "mat": None, "alpha": None}}
        poster = {}

        def khung():
            for i in range(n):
                t = i / FPS
                canvas.clear(skia.Color(14, 14, 18))
                if cach == "engine":
                    ve_du_phong.nen(canvas, t)
                    _engine(hu, canvas, t, ctx)
                else:
                    ve_du_phong.ve(hid, canvas, t)
                img = surf.makeImageSnapshot()
                if i == poster_idx:
                    img.save(jpg, skia.kJPEG)
                yield img.tobytes()
        _ghi_mp4(mp4, khung())

    loi = ""
    for cach in ("engine", "du_phong"):
        try:
            chay(cach)
            ra.update({"video": os.path.basename(mp4), "anh": os.path.basename(jpg), "cach": cach})
            if loi:
                ra["ghi_chu"] = "engine lỗi, dùng dự phòng: " + loi
            return ra
        except Exception as ex:
            loi = f"{type(ex).__name__}: {str(ex)[:160]}"
            ra["loi_" + cach] = loi
    png = os.path.join(d, hid + ".png")
    _placeholder(hu, png, loi)
    ra.update({"anh": os.path.basename(png), "cach": "placeholder", "ghi_chu": "chưa dựng được: " + loi})
    try:
        if os.path.isfile(mp4):
            os.remove(mp4)
    except Exception:
        pass
    return ra


def sinh(ep=False, tien_do=None):
    """sinh/cập nhật toàn bộ hiệu ứng → danh sách; ep=True ép dựng lại"""
    d = _thu_muc()
    ds = danh_sach_mau()
    ve = None
    try:
        ve = _Ve()
    except Exception as ex:
        ve = None
        loi_ve = str(ex)
    ra = []
    for i, hu in enumerate(ds):
        if tien_do:
            tien_do(i, len(ds), hu["ten"])
        if ve is None:
            png = os.path.join(d, hu["id"] + ".png")
            _placeholder(hu, png, loi_ve)
            ra.append({"id": hu["id"], "ten": hu["ten"], "mo_ta": hu["mo_ta"], "anh": os.path.basename(png), "video": "", "json": "", "cach": "placeholder"})
            continue
        ra.append(_sinh_mot(hu, d, ep, ve))
    chung.ghi_json(os.path.join(d, "danh-sach.json"), ra)
    if tien_do:
        tien_do(len(ds), len(ds), "xong")
    return ra


def danh_sach():
    d = _thu_muc()
    return chung.doc_json(os.path.join(d, "danh-sach.json"), []) or []


def duong_file(hid, kieu="mp4"):
    """đường dẫn tuyệt đối file của hiệu ứng (mp4|json|jpg|png) hoặc None"""
    hid = re.sub(r"[^a-z0-9_\-]", "", hid or "")
    p = os.path.join(_thu_muc(), f"{hid}.{kieu}")
    return p if os.path.isfile(p) else None


if __name__ == "__main__":
    t = time.time()
    for h in sinh(ep="--ep" in sys.argv, tien_do=lambda i, n, ten: print(f"  {i}/{n} {ten}", flush=True)):
        print(h["id"], h["cach"], h.get("video"), h.get("ghi_chu", ""))
    print("giây:", round(time.time() - t, 1))
