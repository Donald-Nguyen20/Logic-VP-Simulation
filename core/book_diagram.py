# -*- coding: utf-8 -*-
"""Logic dung de TO MAU ban ve so tay (book diagram) cua mot ma khoi.

Ban ve thi lay NGUYEN tu so tay (core/manual_drawing.py tach net vector tu PDF). File
core/book_layouts/<ma>.json chi noi o nao tren giay ung voi nguon nao: e-lip chan vao
'pin:N', nut man hinh 'ops:OPS_INn', o hien thi 'S| ...' = 'reg:OPS_OUTn', e-lip chan
ra 'ra:N'. Gia tri cua cac nguon do tinh o day, tu CHINH than lenh DEF cua hang.

Dung LAI bo doc than lenh cua core/block_fbd.py nhung KHONG chay hai buoc rut gon cua no:

  _gon_mux()      gop chuoi FMV1 vao mot hop chon nhieu duong - tien cho ban ve tu sinh,
                  nhung khong can o day.
  _cat_nut_chet() bo nut khong chay toi chan ra nao - ma 13 phep gan OPS_OUT chinh la
                  nhu vay (chung day ra man hinh van hanh, khong day ra chan khoi), nen
                  chay buoc nay la mat sach gia tri cua cac o hien thi.

Doi chieu tren 8204: 13 phep gan OPS_OUT = 13 o 'S|' tren giay, 4 phep gan CNT_OUT = 4
e-lip dau ra (Auto, OP CMD, CL CMD, ABN). tests/test_book_diagram.py cho do thi nay chay
song song voi DefSim tren moi kich ban cua core/tag_docs/8204.json.
"""
from __future__ import annotations

import json
import os

from core import macro_def as MD
from core.block_fbd import _Doc, _than
from core.help_i18n import tr

_THU_MUC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "book_layouts")
_NHO = {}


def _rong():
    return {"ok": False, "why": "", "code": "", "nlenh": 0, "nodes": [], "outs": {},
            "pin_in": {}, "pin_out": {}, "regs": {}, "nguoc": {}}


def book_graph(code):
    """Do thi logic day du (chua rut gon) cua 1 ma khoi, hoac ly do khong dung duoc.

    -> {"ok","why","code","nlenh","nodes","outs","pin_in","pin_out","regs","nguoc"}
    `regs`  : {ten_o_nho: id_nut_hoac_nguon}  - vd OPS_OUT5 -> nut dang giu no.
    `nguoc` : {id_nut: [ten_o_nho...]}        - mot nut co the mang nhieu ten.
    Nut giong fbd_graph(): {"id","op","ins":[(vai,nguon)],"nhan","phu"}.
    """
    ket = _rong()
    ket["code"] = (code or "").upper()
    than = _than(code)
    if than is None:
        ket["why"] = _vi_sao_khong_co_than()
        return ket
    instrs = MD.parse_body(than)
    ket["nlenh"] = len(instrs)
    if not instrs:
        ket["why"] = tr("The vendor DEF holds no logic body for this macro.")
        return ket

    d = _Doc(code).chay(instrs)
    if d.bad:
        ket["why"] = (tr("The vendor logic body uses '%s', which this diagram cannot draw "
                      "faithfully yet.") % d.bad)
        return ket
    if not d.outs:
        ket["why"] = tr("The vendor logic body drives no output pin of this block.")
        return ket

    nguoc = {}
    for reg, src in d.alias.items():
        nguoc.setdefault(src, []).append(reg)
    for ds in nguoc.values():
        ds.sort()
    ket.update(ok=True, nodes=d.nodes, outs=d.outs, regs=dict(d.alias), nguoc=nguoc,
               pin_in=d.pin_in, pin_out=d.pin_out)
    return ket


def _vi_sao_khong_co_than():
    """Hai truong hop rat khac nhau, gop mot cau thi nguoi doc di tim file vo ich."""
    if not MD.find_all_def_files():
        return tr("The vendor DEF folder was not found on this machine, so the internal "
                  "logic of this block cannot be read here.")
    return tr("This macro has no logic body in the vendor DEF files, so there is nothing "
              "to redraw.")


def khung(code):
    """Noi dung core/book_layouts/<ma>.json (trang so tay + bang neo), hoac None.

    Chua co thi cua so Help bo han o "Book diagram" - khong co ban ve cua hang thi
    khong ve thay."""
    code = (code or "").upper()
    if code not in _NHO:
        _NHO[code] = _doc_khung(code)
    return _NHO[code]


def _doc_khung(code):
    duong = os.path.join(_THU_MUC, "%s.json" % code)
    if not os.path.isfile(duong):
        return None
    with open(duong, encoding="utf-8") as f:
        return json.load(f)


def co_khung(code):
    """Ma khoi nay co ban ve so tay de dung lai khong."""
    return khung(code) is not None
