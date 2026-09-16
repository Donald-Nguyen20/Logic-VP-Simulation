# -*- coding: utf-8 -*-
"""Song ngu cho cua so Help va F1: tieng Anh (goc) / tieng Viet.

Kieu gettext: CHUOI TIENG ANH la khoa. Cho nao in chu ra man hinh thi boc bang tr("..."):
  - dang chon tieng Anh  -> tra nguyen chuoi;
  - dang chon tieng Viet -> tra ban dich trong core/help_vi.json (chu cua app) hoac
    core/help_vi_manual.json (doan chep tu manual Toshiba). Thieu ban dich thi van tra
    tieng Anh va ghi khoa vao MISSING - kiem thu doc tap nay de bat cho quen dich.

Chuoi co %s/%d: boc tr() quanh MAU truoc khi dien so; ban dich phai giu du va dung thu tu
cac dau %. Ten chinh thuc cua hang, ten chan, ten tag, ma khoi KHONG dich.

Ban dich viet tay, khong goi AI. Ngon ngu dang chon luu o data/help_lang.json (xem
duong_dan) nen mo lai app van giu.
"""
from __future__ import annotations
import json
import os

EN, VI = "en", "vi"
MISSING = set()           # khoa da hoi o che do VI ma chua co ban dich

_FILES = ("help_vi.json", "help_vi_manual.json")
_TEN_LUU = "help_lang.json"
_state = {"lang": None, "cat": None}


def _catalog():
    """{tieng Anh: tieng Viet} gop tu cac file dich. Khoa bat dau '_' la ghi chu."""
    if _state["cat"] is None:
        cat = {}
        for fn in _FILES:
            try:
                with open(os.path.join(os.path.dirname(__file__), fn), encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                continue
            if isinstance(data, dict):
                cat.update((k, v) for k, v in data.items()
                           if not k.startswith("_") and isinstance(v, str) and v)
        _state["cat"] = cat
    return _state["cat"]


def _duong_luu():
    from . import duong_dan
    return duong_dan.duong(_TEN_LUU)


def lang():
    """Ngon ngu dang dung cho Help: EN hoac VI. Mac dinh EN."""
    if _state["lang"] is None:
        _state["lang"] = EN
        try:
            with open(_duong_luu(), encoding="utf-8") as f:
                v = json.load(f).get("lang")
            if v in (EN, VI):
                _state["lang"] = v
        except (OSError, ValueError, AttributeError):
            pass
    return _state["lang"]


def set_lang(code):
    """Doi ngon ngu va luu lai. Khong luu duoc thi van doi cho phien nay."""
    if code not in (EN, VI):
        raise ValueError("help language must be %r or %r, got %r" % (EN, VI, code))
    _state["lang"] = code
    try:
        with open(_duong_luu(), "w", encoding="utf-8") as f:
            json.dump({"lang": code}, f)
    except OSError:
        pass


def is_vi():
    return lang() == VI


def tr(en):
    """Ban dich cua chuoi tieng Anh 'en' theo ngon ngu dang chon."""
    if not en or not isinstance(en, str) or lang() != VI:
        return en
    vi = _catalog().get(en)
    if vi is None:
        MISSING.add(en)
        return en
    return vi
