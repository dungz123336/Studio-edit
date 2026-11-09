# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""ĐỌC TÀI LIỆU KỊCH BẢN người dùng gửi kèm (1.2.11): .xlsx .docx .pptx .csv .tsv .txt .md .srt .rtf → văn bản thường
(không cần thư viện ngoài: xlsx/docx/pptx là zip XML). PDF: Claude đọc thẳng bằng Read, ở đây chỉ báo đường dẫn.

    <python skill> v2/doc/tai_lieu.py <file> [--ra <file.txt>]
    from doc.tai_lieu import doc_van_ban;  txt = doc_van_ban(path)
"""
import os, re, sys, csv, io, json, zipfile, argparse
import xml.etree.ElementTree as ET

DUOI = (".xlsx", ".xlsm", ".docx", ".pptx", ".csv", ".tsv", ".txt", ".md", ".srt", ".vtt", ".rtf", ".json", ".pdf")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _doc_text(p):
    b = open(p, "rb").read()
    for enc in ("utf-8-sig", "utf-16", "cp1258", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace")


def _docx(p):
    z = zipfile.ZipFile(p)
    root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for el in root.iter():
        if el.tag == _W + "p":
            s = "".join(t.text or "" for t in el.iter(_W + "t"))
            out.append(s)
        elif el.tag == _W + "tab":
            pass
    # bảng: các ô đã nằm trong đoạn <w:p>; gộp dòng trống liên tiếp
    txt = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", txt).strip()


def _cot(ref):
    m = re.match(r"([A-Z]+)", ref or "")
    n = 0
    for ch in (m.group(1) if m else "A"):
        n = n * 26 + ord(ch) - 64
    return n - 1


def _xlsx(p):
    z = zipfile.ZipFile(p)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(_S + "si"):
            ss.append("".join(t.text or "" for t in si.iter(_S + "t")))
    ten = {}
    try:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rel = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid = {r.get("Id"): r.get("Target") for r in rel}
        for sh in wb.iter(_S + "sheet"):
            rr = sh.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            t = rid.get(rr, "")
            ten["xl/" + t.lstrip("/").replace("xl/", "")] = sh.get("name")
    except Exception:
        pass
    out = []
    for f in sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)):
        out.append(f"## Sheet: {ten.get(f, os.path.basename(f))}")
        root = ET.fromstring(z.read(f))
        for row in root.iter(_S + "row"):
            o = {}
            for c in row.iter(_S + "c"):
                v = c.find(_S + "v"); t = c.get("t")
                if t == "inlineStr":
                    s = "".join(x.text or "" for x in c.iter(_S + "t"))
                elif v is None:
                    continue
                elif t == "s":
                    s = ss[int(v.text)] if v.text and int(v.text) < len(ss) else ""
                else:
                    s = v.text or ""
                o[_cot(c.get("r"))] = s.replace("\n", " ").strip()
            if any(o.values()):
                n = max(o) + 1
                out.append(" | ".join(o.get(i, "") for i in range(n)))
    return "\n".join(out)


def _pptx(p):
    z = zipfile.ZipFile(p)
    out = []
    so = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)), key=lambda n: int(re.findall(r"\d+", n)[-1]))
    for i, f in enumerate(so, 1):
        root = ET.fromstring(z.read(f))
        dong = ["".join(t.text or "" for t in p_.iter(_A + "t")) for p_ in root.iter(_A + "p")]
        out.append(f"## Slide {i}\n" + "\n".join(d for d in dong if d.strip()))
    return "\n\n".join(out)


def _rtf(p):
    s = _doc_text(p)
    s = re.sub(r"\\'([0-9a-f]{2})", lambda m: bytes.fromhex(m.group(1)).decode("cp1258", "replace"), s)
    s = re.sub(r"\\u(-?\d+)\??", lambda m: chr(int(m.group(1)) % 65536), s)
    s = re.sub(r"\\par[d]?", "\n", s)
    s = re.sub(r"\\[a-z]+-?\d* ?|[{}]", "", s)
    return s.strip()


def doc_van_ban(p, toi_da=200000):
    d = os.path.splitext(p)[1].lower()
    if d in (".xlsx", ".xlsm"):
        s = _xlsx(p)
    elif d == ".docx":
        s = _docx(p)
    elif d == ".pptx":
        s = _pptx(p)
    elif d in (".csv", ".tsv"):
        t = _doc_text(p)
        try:
            dia = csv.Sniffer().sniff(t[:4000], delimiters=",;\t|")
        except csv.Error:
            dia = csv.excel_tab if d == ".tsv" else csv.excel
        s = "\n".join(" | ".join(c.strip() for c in r) for r in csv.reader(io.StringIO(t), dia) if any(x.strip() for x in r))
    elif d == ".rtf":
        s = _rtf(p)
    elif d in (".pdf", ".xls"):                    # PDF: Claude đọc thẳng · .xls (Excel cũ, nhị phân): nhờ người dùng lưu lại .xlsx
        return None
    else:
        s = _doc_text(p)
    return s[:toi_da]


def chuyen(p, ra=None):
    """→ đường file .txt đọc được (hoặc chính file nếu đã là văn bản / PDF)"""
    d = os.path.splitext(p)[1].lower()
    if d in (".txt", ".md", ".srt", ".vtt", ".pdf", ".json", ".xls"):
        return p
    s = doc_van_ban(p)
    if s is None:
        return p
    ra = ra or os.path.splitext(p)[0] + ".doc-duoc.txt"
    with open(ra, "w", encoding="utf-8") as f:
        f.write(s)
    return ra


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("file"); ap.add_argument("--ra")
    a = ap.parse_args()
    s = doc_van_ban(a.file)
    if s is None:
        print(f"(PDF — đọc thẳng bằng Read: {a.file})")
        return
    if a.ra:
        open(a.ra, "w", encoding="utf-8").write(s); print(a.ra)
    else:
        sys.stdout.reconfigure(encoding="utf-8"); print(s)


if __name__ == "__main__":
    main()
