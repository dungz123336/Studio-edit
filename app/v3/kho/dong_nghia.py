# -*- coding: utf-8 -*-
"""Bảng đồng nghĩa nhỏ Anh ↔ Việt cho kho tài nguyên (từ khoá đã bỏ dấu khi dùng).
Khoá: từ tiếng Anh (thường gặp trong tên file) → danh sách từ tiếng Việt / từ gần nghĩa.
`mo_rong(tokens)` trả về danh sách token mở rộng (2 chiều, bỏ dấu, không trùng)."""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

BANG = {
    # âm thanh
    "whoosh": ["vút", "lướt", "swoosh", "swish"], "swoosh": ["vút", "lướt", "whoosh"], "swish": ["vút", "lướt"],
    "pop": ["bụp", "bật", "nổ nhỏ"], "click": ["bấm", "nhấp", "tách"], "tap": ["gõ", "chạm"],
    "ding": ["chuông", "keng", "ting"], "bell": ["chuông", "thông báo"], "chime": ["chuông", "ngân"],
    "riser": ["dâng", "lên cao", "căng"], "rise": ["dâng"], "build": ["dâng", "cao trào"], "uplifter": ["dâng"],
    "impact": ["đập", "dằn", "hit", "va"], "hit": ["đập", "dằn", "impact"], "punch": ["đấm", "đập"], "slam": ["dằn", "đập"],
    "glitch": ["nhiễu", "giật", "lỗi"], "static": ["nhiễu", "rè"], "noise": ["nhiễu", "ồn"],
    "transition": ["chuyển", "chuyển cảnh"], "boom": ["bùm", "nổ"], "explosion": ["nổ", "bùm"], "bass": ["trầm"],
    "sub": ["trầm", "bass"], "drop": ["rơi", "thả", "trầm"], "subdrop": ["trầm", "rơi"],
    "typing": ["gõ phím", "bàn phím", "đánh máy"], "keyboard": ["bàn phím", "gõ phím"], "type": ["gõ phím"],
    "notification": ["thông báo", "tin nhắn", "alert"], "alert": ["thông báo", "cảnh báo"], "sms": ["tin nhắn", "thông báo"],
    "message": ["tin nhắn", "thông báo"], "ticker": ["tích tắc", "đếm"],
    "cinematic": ["điện ảnh", "phim", "hoành tráng"], "trailer": ["điện ảnh", "phim", "hồi hộp"],
    "lofi": ["lo-fi", "chill", "thư giãn"], "chill": ["thư giãn", "nhẹ", "lofi"], "relax": ["thư giãn", "nhẹ"], "calm": ["êm", "nhẹ", "thư giãn"],
    "upbeat": ["sôi động", "vui", "nhanh"], "energetic": ["sôi động", "năng lượng"], "dance": ["nhảy", "sôi động"],
    "funky": ["vui", "sôi động", "funk"], "funk": ["vui", "sôi động"], "funny": ["hài", "vui nhộn", "vui"], "quirky": ["ngộ", "hài"],
    "sad": ["buồn", "cảm động"], "emotional": ["cảm động", "cảm xúc", "xúc động"], "hopeful": ["hy vọng", "cảm động"],
    "epic": ["hùng tráng", "hoành tráng", "sử thi"], "dramatic": ["kịch tính", "gay cấn", "hồi hộp"], "tension": ["căng thẳng", "hồi hộp", "gay cấn"],
    "suspense": ["hồi hộp", "gay cấn"], "happy": ["vui", "vui vẻ"], "positive": ["tích cực", "vui"], "inspiring": ["truyền cảm hứng", "cảm động"],
    "motivational": ["động lực", "truyền cảm hứng"], "piano": ["dương cầm"], "guitar": ["ghi-ta"], "violin": ["vĩ cầm"],
    "drum": ["trống"], "drums": ["trống"], "orchestra": ["dàn nhạc", "giao hưởng"], "acapella": ["giọng hát", "hát"], "vocal": ["giọng hát"],
    "rock": ["rock", "mạnh"], "metal": ["mạnh", "rock"], "trap": ["trap", "rap"], "hip": ["hip hop", "rap"], "hop": ["hip hop"], "rap": ["rap"],
    "corporate": ["doanh nghiệp", "quảng cáo"], "advertising": ["quảng cáo"], "commercial": ["quảng cáo"], "ad": ["quảng cáo"],
    "vlog": ["vlog", "đời thường"], "cooking": ["nấu ăn"], "wedding": ["cưới"], "summer": ["hè"], "reggae": ["reggae", "vui"],
    "cartoon": ["hoạt hình"], "animation": ["hoạt hình"], "interface": ["giao diện", "ui"], "ui": ["giao diện"],
    "flash": ["chớp", "loé"], "sparkle": ["lấp lánh", "tia", "sao"], "magic": ["phép", "lấp lánh"], "shimmer": ["lấp lánh"],
    "reverse": ["ngược", "đảo"], "ambient": ["không gian", "nền"], "ambience": ["không gian", "nền"], "loop": ["lặp"],
    "stinger": ["chốt", "ngắn"], "ident": ["chốt", "nhận diện"], "logo": ["logo", "nhận diện"], "intro": ["mở đầu"], "outro": ["kết"],
    "slide": ["trượt"], "whistle": ["huýt sáo", "còi"], "cash": ["tiền", "đếm tiền", "tiền mặt"], "coin": ["tiền xu", "xu", "tiền"], "money": ["tiền", "tiền mặt", "đô", "lợi nhuận"],
    "camera": ["máy ảnh", "chụp", "máy quay", "camera", "quay"], "shutter": ["chụp", "màn trập"], "laser": ["tia", "laser"], "robot": ["robot", "máy", "ai"],
    "water": ["nước"], "wind": ["gió"], "fire": ["lửa", "hot", "nóng"], "thunder": ["sấm"], "rain": ["mưa"], "heartbeat": ["nhịp tim", "tim đập"],
    "clock": ["đồng hồ", "tích tắc", "thời gian"], "tick": ["tích tắc", "tích", "đúng"], "countdown": ["đếm ngược"], "applause": ["vỗ tay"], "clap": ["vỗ tay"],
    "laugh": ["cười"], "crowd": ["đám đông"], "scream": ["hét"], "error": ["lỗi", "sai"], "wrong": ["sai", "lỗi"], "correct": ["đúng"],
    "success": ["thành công", "đúng"], "win": ["thắng", "thành công"], "fail": ["thất bại", "sai"], "game": ["game", "trò chơi"],
    # hình ảnh / nền
    "neon": ["neon", "đèn", "đèn neon"], "paper": ["giấy"], "grid": ["lưới", "ô"], "gradient": ["chuyển màu", "gradient"], "bokeh": ["bokeh", "mờ"],
    "light": ["sáng", "ánh sáng", "mảnh", "nhẹ", "đèn"], "leak": ["loé sáng", "light leak", "ánh sáng"], "lens": ["ống kính"], "flare": ["loé", "chói"], "burn": ["cháy phim", "film burn"],
    "film": ["phim"], "particle": ["hạt"], "particles": ["hạt"], "dots": ["chấm"], "dot": ["chấm"], "texture": ["vân", "chất liệu"],
    "topography": ["địa hình", "đường đồng mức"], "topographic": ["địa hình", "đường đồng mức"], "fabric": ["vải"], "crumpled": ["nhàu"],
    "overlay": ["phủ", "lớp phủ"], "background": ["nền", "bg"], "bg": ["nền", "background"], "wavy": ["sóng", "lượn"], "twister": ["xoáy"],
    "black": ["đen", "siêu đậm"], "white": ["trắng"], "blue": ["xanh dương", "xanh"], "green": ["xanh lá", "xanh"], "red": ["đỏ"], "orange": ["cam"],
    "yellow": ["vàng"], "purple": ["tím"], "pink": ["hồng"], "gold": ["vàng kim", "vàng"], "golden": ["vàng kim"], "dark": ["tối"],
    "horizontal": ["ngang"], "vertical": ["dọc"], "large": ["lớn", "to"], "small": ["nhỏ"], "still": ["tĩnh"], "animated": ["động"],
    "character": ["nhân vật"], "characters": ["nhân vật"], "viral": ["viral", "trend"], "trending": ["trend", "xu hướng"],
    "doctor": ["bác sĩ"], "audience": ["khán giả", "đám đông"], "pointing": ["chỉ tay"], "mailing": ["thư", "email"], "mountain": ["núi"],
    "bag": ["túi"], "arms": ["tay", "khoanh tay"], "cross": ["khoanh", "chéo"], "thinking": ["suy nghĩ"], "idea": ["ý tưởng", "bóng đèn"],
    "icon": ["icon", "biểu tượng"], "sticker": ["nhãn dán"], "emoji": ["emoji", "biểu cảm"],
    # font
    "script": ["viết tay", "chữ thảo"], "handwriting": ["viết tay"], "serif": ["có chân"], "sans": ["không chân"], "display": ["tiêu đề"],
    "bold": ["đậm"], "thin": ["mảnh"], "italic": ["nghiêng"],
    "condensed": ["hẹp"], "rounded": ["bo tròn"], "retro": ["cổ điển", "vintage"], "vintage": ["cổ điển", "retro"], "modern": ["hiện đại"],
    "brush": ["cọ"], "comic": ["truyện tranh", "hài"], "pixel": ["pixel", "game"], "mono": ["đơn cách"], "code": ["mã", "lập trình"],
    # lut
    "lut": ["màu", "lut"], "cinema": ["điện ảnh"], "natural": ["tự nhiên"], "teal": ["xanh ngọc"], "matte": ["mờ", "matte"],
    "muted": ["trầm", "nhạt"], "warm": ["ấm"], "cool": ["lạnh"], "moody": ["u tối", "tâm trạng"], "portrait": ["chân dung"],
    "bleached": ["bạc màu"], "contrast": ["tương phản"], "slog": ["s-log", "sony"], "sony": ["sony"], "apple": ["apple", "iphone"],
    "log": ["log"], "rec709": ["rec709"], "thriller": ["kinh dị", "hồi hộp"], "neutral": ["trung tính"],
    # icon / hình (Anh → Việt; chiều Việt→Anh tự xây)
    "phone": ["điện thoại", "di động", "smartphone"], "cellphone": ["điện thoại", "di động"], "mobile": ["điện thoại", "di động"], "smartphone": ["điện thoại"],
    "dollar": ["đô", "tiền"], "wallet": ["ví", "tiền"],
    "text": ["chữ", "văn bản"], "letter": ["chữ", "thư"], "font": ["chữ", "font"], "sparkles": ["lấp lánh", "tia"],
    "star": ["sao", "ngôi sao", "lấp lánh"], "shine": ["sáng", "lấp lánh"], "scissors": ["kéo", "cắt"], "cut": ["cắt", "kéo"], "merge": ["ghép", "gộp"],
    "computer": ["máy tính", "laptop"], "laptop": ["máy tính", "laptop"], "pc": ["máy tính"], "arrow": ["mũi tên", "chỉ"], "pointer": ["con trỏ", "mũi tên"],
    "heart": ["tim", "trái tim", "yêu", "thích"], "like": ["thích", "like", "tim"], "comment": ["bình luận", "comment"], "share": ["chia sẻ"],
    "flame": ["lửa"], "house": ["nhà", "căn nhà"], "home": ["nhà"], "car": ["xe", "ô tô"], "check": ["tích", "đúng", "xong"],
    "warning": ["cảnh báo", "chú ý"], "question": ["hỏi", "câu hỏi"], "bulb": ["bóng đèn", "ý tưởng"],
    "video": ["video", "clip"], "mic": ["mic", "micro"], "microphone": ["mic", "micro"],
    "time": ["thời gian", "đồng hồ"], "calendar": ["lịch"], "gift": ["quà"], "cart": ["giỏ hàng", "mua"], "shop": ["cửa hàng", "mua"],
    "chart": ["biểu đồ", "tăng trưởng"], "graph": ["biểu đồ"], "growth": ["tăng trưởng", "tăng"], "rocket": ["tên lửa", "bứt phá"], "target": ["mục tiêu"],
    "people": ["người", "nhóm"], "person": ["người"], "team": ["đội", "nhóm"], "ai": ["ai", "trí tuệ"], "brain": ["não", "tư duy"],
    "thumbs": ["ngón cái", "like"], "hand": ["tay"], "eye": ["mắt", "xem"], "search": ["tìm", "kính lúp"], "magnifier": ["kính lúp", "tìm"],
    "lock": ["khoá", "bảo mật"], "key": ["chìa", "khoá"], "shield": ["khiên", "bảo vệ"], "book": ["sách", "học"], "pencil": ["bút"],
    "pen": ["bút"],
    "smoke": ["khói"], "dust": ["bụi"], "glow": ["phát sáng", "sáng"], "frame": ["khung"], "border": ["viền", "khung"],
    "preset": ["preset", "mẫu"], "capcut": ["capcut"], "combinado": ["kết hợp", "combo"], "clip": ["clip", "video"],
}

_NGUOC = None


def _xay_nguoc():
    """cụm Việt (tuple token bỏ dấu) → các khoá Anh. Chỉ dùng ở phía TRUY VẤN (tránh nhiễu khi lập chỉ mục)"""
    global _NGUOC
    if _NGUOC is not None:
        return _NGUOC
    ng = {}
    for en, ds in BANG.items():
        for v in ds:
            tk = tuple(tach(v))
            if tk:
                ng.setdefault(tk, set()).add(en)
    _NGUOC = ng
    return ng


def _kd(s):
    """bỏ dấu, giữ đ → d (chung.khong_dau làm rơi 'đ': "đèn" → "en")"""
    return chung.khong_dau((s or "").replace("đ", "d").replace("Đ", "D"))


def tach(s, giu_1=False):
    """tách chuỗi thành token bỏ dấu, chữ thường; bỏ token 1 ký tự (giu_1=True: giữ — để ghép cụm "ý tưởng" → y_tuong)"""
    s = _kd(s)
    return [t for t in re.split(r"[^a-z0-9]+", s) if t and (giu_1 or len(t) >= 2 or t.isdigit())]


def xuoi(token):
    """token Anh → token Việt đồng nghĩa (bỏ dấu); dùng khi lập chỉ mục"""
    ra = []
    for v in BANG.get(token, ()):
        ra.extend(tach(v))
    return ra


def mo_rong(tokens):
    """mở rộng khi LẬP CHỈ MỤC: chỉ chiều Anh → Việt (giữ thứ tự, không trùng)"""
    seen, out = set(), []
    for t in tokens:
        for x in [t] + xuoi(t):
            if x not in seen:
                seen.add(x); out.append(x)
    return out


def mo_rong_truy_van(tokens):
    """mở rộng khi TÌM: Anh → Việt và cụm Việt (1–3 token) → Anh → Việt"""
    ng = _xay_nguoc()
    them = []
    n = len(tokens)
    for i in range(n):
        for k in (3, 2, 1):
            cum = tuple(tokens[i:i + k])
            if len(cum) == k and cum in ng:
                for en in ng[cum]:
                    them.append(en); them.extend(xuoi(en))
    seen, out = set(), []
    for t in list(tokens) + [x for t in tokens for x in xuoi(t)] + them:
        if t not in seen:
            seen.add(t); out.append(t)
    return out

# 1.2.19 — từ tượng thanh / tính chất tiếng Việt (kho/tai.py dùng cùng bảng này để ràng buộc vật lý)
_THEM_1219 = {
    "ding": ["tinh", "ting", "tinh tinh", "ting ting", "đinh", "keng"], "bell": ["tinh", "keng", "leng keng", "trong"], "chime": ["tinh", "ngân", "trong"],
    "sparkle": ["lấp lánh", "tinh tinh"], "shimmer": ["lấp lánh", "ngân"], "glitter": ["lấp lánh"],
    "boom": ["bùm", "bùm bùm", "đùng"], "impact": ["bùm", "rầm", "đùng"], "explosion": ["bùm", "đùng"], "slam": ["rầm"], "crash": ["rầm", "vỡ"],
    "whoosh": ["vút", "vèo", "xoẹt", "vù"], "swoosh": ["vút", "vèo", "xoẹt"], "swish": ["xoẹt", "vút"], "wind": ["vù", "gió"],
    "click": ["tách", "cạch", "tích"], "tap": ["tách", "chạm"], "snap": ["tách", "búng"], "tick": ["tích", "tích tắc"], "ticker": ["tích tắc", "tích tích"],
    "knock": ["cốc", "cộc", "gõ cửa"], "wood": ["cốc", "gỗ"], "typing": ["lạch cạch", "gõ phím"], "keyboard": ["lạch cạch"],
    "pop": ["bụp", "bốp"], "bubble": ["bụp", "bong bóng"], "thud": ["bịch", "thịch"], "beep": ["bíp", "bíp bíp"], "blip": ["bíp"], "alarm": ["tít tít", "báo động"],
    "glitch": ["rè", "giật"], "static": ["rè", "xì"], "noise": ["rè", "ồn"], "hiss": ["xì"], "drone": ["ù", "ùng"], "hum": ["ù"], "rumble": ["ùng", "rung"],
    "riser": ["dâng"], "uplifter": ["dâng"], "low": ["trầm"], "deep": ["trầm"], "bright": ["chói", "sáng"], "high": ["cao", "chói"],
    "dry": ["khô"], "glass": ["trong", "thuỷ tinh"], "crystal": ["trong", "pha lê"],
}
for _k, _v in _THEM_1219.items():
    _cu = list(BANG.get(_k, ()))
    BANG[_k] = _cu + [x for x in _v if x not in _cu]
