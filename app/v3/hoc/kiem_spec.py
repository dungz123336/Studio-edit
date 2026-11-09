# -*- coding: utf-8 -*-
"""Kiểm Style Spec theo nao/style_spec.schema.json (bộ kiểm JSON-schema tối giản, không cần thư viện jsonschema):
type · enum · pattern · minimum/maximum · maxItems · required · additionalProperties:false · $ref (#/definitions/...).
Khoá bắt đầu bằng "_" ở cấp trên cùng (vd "_nguon") được bỏ qua — là ghi chú máy, không phải nội dung spec.
    kiem(spec) -> [lỗi]   ·   python v3/hoc/kiem_spec.py spec.json
"""
import os, sys, re, json

V3 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCHEMA = None


def schema():
    global _SCHEMA
    if _SCHEMA is None:
        with open(os.path.join(V3, "nao", "style_spec.schema.json"), encoding="utf-8") as f:
            _SCHEMA = json.load(f)
    return _SCHEMA


_KIEU = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int, "number": (int, float)}


def _dung_kieu(v, t):
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return isinstance(v, _KIEU.get(t, object))


def _kiem(v, s, duong, loi, goc):
    if "$ref" in s:
        ten = s["$ref"].split("/")[-1]
        s = dict(goc.get("definitions", {}).get(ten, {}), **{k: x for k, x in s.items() if k != "$ref"})
    t = s.get("type")
    if t and not _dung_kieu(v, t):
        loi.append(f"{duong}: phải là {t}, đang là {type(v).__name__}")
        return
    if "enum" in s and v not in s["enum"]:
        loi.append(f"{duong}: '{v}' không thuộc {s['enum']}")
    if isinstance(v, str) and "pattern" in s and not re.match(s["pattern"], v):
        loi.append(f"{duong}: '{v}' sai mẫu {s['pattern']}")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in s and v < s["minimum"]:
            loi.append(f"{duong}: {v} < {s['minimum']}")
        if "maximum" in s and v > s["maximum"]:
            loi.append(f"{duong}: {v} > {s['maximum']}")
    if isinstance(v, str) and "maxLength" in s and len(v) > s["maxLength"]:
        loi.append(f"{duong}: dài {len(v)} > {s['maxLength']}")
    if isinstance(v, list):
        if "maxItems" in s and len(v) > s["maxItems"]:
            loi.append(f"{duong}: {len(v)} phần tử > {s['maxItems']}")
        if "items" in s:
            for i, x in enumerate(v):
                _kiem(x, s["items"], f"{duong}[{i}]", loi, goc)
    if isinstance(v, dict):
        for k in s.get("required", []):
            if k not in v:
                loi.append(f"{duong}: thiếu `{k}`")
        pr = s.get("properties", {})
        for k, x in v.items():
            if duong == "$" and k.startswith("_"):
                continue
            if k in pr:
                _kiem(x, pr[k], f"{duong}.{k}", loi, goc)
            elif s.get("additionalProperties") is False:
                loi.append(f"{duong}: trường lạ `{k}`")
            elif isinstance(s.get("additionalProperties"), dict):
                _kiem(x, s["additionalProperties"], f"{duong}.{k}", loi, goc)


def kiem(spec):
    """→ danh sách lỗi (rỗng = hợp lệ)"""
    g = schema()
    loi = []
    _kiem(spec, g, "$", loi, g)
    return loi


if __name__ == "__main__":
    for p in sys.argv[1:]:
        with open(p, encoding="utf-8") as f:
            o = json.load(f)
        o = o.get("spec", o) if "palette" not in o else o
        l = kiem(o)
        print(("✓ " if not l else "✗ ") + p + ("" if not l else "\n  " + "\n  ".join(l)))
