# -*- coding: utf-8 -*-
"""Lập DANH MỤC PRESET CAPCUT từ các project CapCut có sẵn (bộ tài nguyên 10 GB có project 'Preset hiệu ứng siêu chuyên nghiệp
capcut'; thêm project/preset của chính CapCut trên máy). Chỉ ĐỌC các project nguồn.

    python v2/xuat/lap_preset.py [thư mục project CapCut …]   → v2/xuat/capcut_preset.json

Mỗi preset giữ NGUYÊN khuôn JSON CapCut đã ghi (id hiệu ứng, resource_id, đường bộ nhớ đệm) — bộ xuất chỉ đổi id vật liệu,
thời điểm, thời lượng. Đường bộ nhớ đệm được quy về máy đang chạy (%LOCALAPPDATA%/CapCut/User Data/Cache/effect/…).
"""
import copy, glob, json, os, re, sys

V2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, V2)
import chung as C  # noqa: E402

RA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "capcut_preset.json")
CACHE_GOC = os.path.join(os.environ.get("LOCALAPPDATA", ""), "CapCut", "User Data", "Cache") if os.name == "nt" else \
    os.path.expanduser("~/Movies/CapCut/User Data/Cache")


def cache_may(p):
    """đường bộ nhớ đệm trong project nguồn (máy khác) → đường tương ứng trên máy này"""
    if not p:
        return p
    m = re.search(r"[\\/]Cache[\\/](.+)$", p.replace("\\", "/"))
    return os.path.join(CACHE_GOC, *m.group(1).split("/")).replace("\\", "/") if m else p


def nguon_mac_dinh():
    ds = []
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(V2), "scripts"))
        import kit
        b = kit.bo_mua()
        if b:
            ds += [os.path.dirname(p) for p in glob.glob(os.path.join(b, "**", "draft_content.json"), recursive=True)]
    except Exception:
        pass
    ds.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "CapCut", "User Data", "Presets", "Combination"))
    return [d for d in ds if os.path.exists(os.path.join(d, "draft_content.json"))]


def lap(nguon):
    kq = {"chu_vao": {}, "chu_ra": {}, "chu_lap": {}, "hinh": {}, "hieu_ung": {}, "_seg_hieu_ung": None, "_nguon": []}

    def them(nhom, key, x):
        if key and key not in kq[nhom]:
            x = copy.deepcopy(x)
            x["path"] = cache_may(x.get("path", ""))
            x["_co_san"] = bool(x["path"]) and os.path.exists(x["path"])
            kq[nhom][key] = x

    def walk(dr):
        idx = {}
        for k, v in dr.get("materials", {}).items():
            if isinstance(v, list):
                for x in v:
                    if isinstance(x, dict) and "id" in x:
                        idx[x["id"]] = (k, x)
        for t in dr.get("tracks", []):
            for s in t.get("segments", []):
                if t.get("type") == "effect" and kq["_seg_hieu_ung"] is None:
                    kq["_seg_hieu_ung"] = copy.deepcopy(s)
        for k, v in dr.get("materials", {}).items():
            if not isinstance(v, list):
                continue
            for x in v:
                if not isinstance(x, dict):
                    continue
                if k == "material_animations":
                    for a in x.get("animations") or []:
                        nhom = {"in": "chu_vao", "out": "chu_ra", "loop": "chu_lap"}.get(a.get("type"))
                        if nhom:
                            a2 = dict(a); a2["_loai_vat_lieu"] = x.get("type")
                            them(nhom, a.get("resource_id") or a.get("id"), a2)
                elif k == "video_effects":
                    them("hinh", x.get("effect_id") or x.get("resource_id"), x)
                elif k == "effects":
                    them("hieu_ung", x.get("effect_id") or x.get("resource_id"), x)
                elif k == "drafts":
                    walk(x.get("draft") or {})

    for d in nguon:
        try:
            walk(json.load(open(os.path.join(d, "draft_content.json"), encoding="utf-8")))
            kq["_nguon"].append(d)
        except Exception as e:
            print("  bỏ qua", d, e)
    for nhom in ("chu_vao", "chu_ra", "chu_lap", "hinh", "hieu_ung"):
        kq[nhom] = sorted(kq[nhom].values(), key=lambda x: (not x["_co_san"], x.get("name", "")))
    return kq


if __name__ == "__main__":
    ng = sys.argv[1:] or nguon_mac_dinh()
    kq = lap(ng)
    json.dump(kq, open(RA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for nhom in ("chu_vao", "chu_ra", "chu_lap", "hinh", "hieu_ung"):
        print(f"{nhom}: {len(kq[nhom])} (có sẵn trên máy {sum(x['_co_san'] for x in kq[nhom])})")
    print("khuôn đoạn hiệu ứng:", bool(kq["_seg_hieu_ung"]), "· nguồn:", len(kq["_nguon"]))
