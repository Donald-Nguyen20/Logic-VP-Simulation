# -*- coding: utf-8 -*-
"""Chi muc trang cua HAI quyen huong dan goc Toshiba cho tung ma khoi.

  - macro : VP1-C-L2-I-CB-00019-A (Macro Instructions)     - khoi thuong 4xxx/5xxx
  - tag   : VP1-C-L2-I-CB-00018-A (TAG Macro Instructions) - khoi tram/tag 82xx

Moi muc tra ve: quyen nao, nhom nao, cac doan trang [trang, y0, y1] (don vi point cua
PDF, trang dem tu 0) va doan "Explanation" boc ra tu PDF. Man hinh F1 dung cac doan trang
de VE LAI dung phan trang cua khoi do (QtPdf co san trong PySide6) - bang chan ly, cong
thuc va hinh ky hieu trong manual la anh/vector nen chu boc ra khong du.

File core/manual_index.json dung SAN mot lan bang PyMuPDF (chi can luc phat trien):
    python -m core.manual_index
Luc chay app chi doc JSON, khong can PyMuPDF.

Do tren 21 file .db du an: 300 ma dang dung, 211 ma co trang trong manual. 89 ma con lai
la ma cu "(obs)" va ho HCNT 20xx/21xx - hai quyen manual khong mo ta.
"""
from __future__ import annotations
import os
import re
import json

DOCS = {
    "macro": "VP1-C-L2-I-CB-00019-A Control Logic Programming Manual Macro Insructions.pdf",
    "tag": "VP1-C-L2-I-CB-00018-A Control Logic Programing Manual TAG Macro Instructions.pdf",
}
DOC_TITLE = {
    "macro": "Control Logic Programming Manual - Macro Instructions (VP1-C-L2-I-CB-00019-A)",
    "tag": "Control Logic Programming Manual - TAG Macro Instructions (VP1-C-L2-I-CB-00018-A)",
}

_JSON = os.path.join(os.path.dirname(__file__), "manual_index.json")
_RE_CODE = re.compile(r"Code\s+([0-9A-F]{4})\s*H")
# "(2) Difference : 4021H - 4026H", "(16) TagType26 --- MV Station", "[2] Flip Flop"
_RE_GROUP = re.compile(r"^\(\d+\)\s*(.+?(?::\s*[0-9A-F]{4}H.*|---.*))$")
_RE_CHAPTER = re.compile(r"^\[\d+\]\s+\S")
_TOP = 78.0            # duoi dong so trang / so tai lieu o dau moi trang
_BOTTOM = 30.0         # chan trang
_TITLE_UP = 22.0       # dong ten khoi nam ngay tren dong "Symbol"
_MAX_PAGES = {"macro": 3, "tag": 6}

_CACHE = None


def load():
    """{code: muc} tu manual_index.json. Rong neu chua dung file."""
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.load(open(_JSON, encoding="utf-8")).get("codes", {})
        except Exception:
            _CACHE = {}
    return _CACHE


def entry(code):
    return load().get((code or "").upper())


def pdf_path(doc_key):
    """Duong dan PDF tren may nay, hoac None. Tim canh thu muc DEF cua T-Designer truoc,
    roi canh app (ban .exe mang sang may khac co the de PDF ngay ben canh)."""
    name = DOCS.get(doc_key)
    if not name:
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    app = os.path.dirname(here)
    cands = [os.path.dirname(app), app, os.path.join(app, "manual")]
    try:
        from . import duong_dan as DD
        a = DD.thu_muc_app()
        cands += [a, os.path.join(a, "manual"), os.path.dirname(a)]
    except Exception:
        pass
    for d in cands:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


# ---------------------------------------------------------------- dung chi muc (PyMuPDF)

def _marks(doc):
    """Moc chia doan theo thu tu doc: ('code', trang, y, ma, nhom) va ('cut', trang, y)."""
    out, group = [], ""
    for i in range(doc.page_count):
        blocks = sorted(doc[i].get_text("blocks"), key=lambda b: (b[1], b[0]))
        for b in blocks:
            for ln in b[4].splitlines():
                s = " ".join(ln.split())
                m = _RE_GROUP.match(s)
                if m or _RE_CHAPTER.match(s):
                    group = m.group(1) if m else group
                    out.append(("cut", i, b[1] - 2))
            m = _RE_CODE.search(b[4])
            if m:
                out.append(("code", i, max(_TOP, b[1] - _TITLE_UP), m.group(1), group))
    return out


def _sections(doc, marks, k, max_pages):
    """[[trang, y0, y1]] tu moc thu k toi moc ke tiep (co the sang trang sau)."""
    _t, p, y = marks[k][:3]
    stop = next((m for m in marks[k + 1:] if (m[1], m[2]) > (p, y + 20)), None)
    out = []
    while len(out) < max_pages and p < doc.page_count:
        h = doc[p].rect.height
        if stop and stop[1] == p:
            if stop[2] - y > 20:
                out.append([p, round(y, 1), round(stop[2], 1)])
            break
        out.append([p, round(y, 1), round(h - _BOTTOM, 1)])
        p, y = p + 1, _TOP
    return out


def _is_sentence(s):
    return len(s.split()) >= 4 or (len(s.split()) >= 2 and s.endswith("."))


def _explain(doc, sections):
    """Doan van ban sau chu 'Explanation', chi giu dong dang CAU (nhan hinh ve, o bang,
    ky tu cong thuc bi boc rai rac deu ngan)."""
    import fitz
    lines, on, miss = [], False, 0
    for p, y0, y1 in sections:
        page = doc[p]
        clip = fitz.Rect(0, y0, page.rect.width, y1)
        for b in sorted(page.get_text("blocks", clip=clip), key=lambda b: (b[1], b[0])):
            for ln in b[4].splitlines():
                s = " ".join(ln.split())
                if not on:
                    on = s.startswith("Explanation")
                    continue
                if s.startswith("[ Parameter value detail") or s.startswith("Parameter detail"):
                    return " ".join(lines)
                if _is_sentence(s):
                    lines.append(s)
                    miss = 0
                elif s and lines:
                    miss += 1
                    if miss >= 6:
                        return " ".join(lines)
    return " ".join(lines)[:1500]


def build(root=None):
    """Quet ca hai PDF -> {code: muc}. Ma xuat hien nhieu lan thi giu lan DAU."""
    import fitz
    codes = {}
    for key, name in DOCS.items():
        path = os.path.join(root, name) if root else pdf_path(key)
        if not path or not os.path.exists(path):
            continue
        doc = fitz.open(path)
        marks = _marks(doc)
        last_by_group = {}
        for k, m in enumerate(marks):
            if m[0] != "code" or m[3] in codes:
                continue
            secs = _sections(doc, marks, k, _MAX_PAGES[key])
            text = _explain(doc, secs) if secs else ""
            shared = False
            if text:
                last_by_group[m[4]] = text
            elif last_by_group.get(m[4]):
                text, shared = last_by_group[m[4]], True
            codes[m[3]] = {"doc": key, "group": m[4], "sections": secs,
                           "explain": text, "shared": shared}
    return codes


if __name__ == "__main__":
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace",
                                  line_buffering=True)
    res = build()
    json.dump({"codes": res}, open(_JSON, "w", encoding="utf-8"), ensure_ascii=False,
              indent=0)
    print("manual_index.json: %d codes" % len(res))
