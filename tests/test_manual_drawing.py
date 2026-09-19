# -*- coding: utf-8 -*-
"""Tach ban ve goc tu so tay va ve lai no: nhung phan KHONG can file DEF cua hang.

Hai cai bay da gap khi tach (xem core/manual_drawing.py) duoc giu bang test tren du lieu
tu dung, de may nao cung chay duoc; test doc PDF that thi skip khi thieu PyMuPDF / PDF."""
import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import manual_drawing as MDW  # noqa: E402


def _qapp():
    qtw = pytest.importorskip("PySide6.QtWidgets")
    return qtw.QApplication.instance() or qtw.QApplication([])


def _hop(x0, y0, x1, y1):
    """Net mot o chu nhat kin, dang luu trong cache."""
    return {"s": "#000000", "f": None, "w": 0.5, "c": 0,
            "d": [[1, x0, y0, x1, y0, x1, y1, x0, y1]]}


def _elip(cx, cy, rx, ry, n=24):
    d = [0]
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        d += [round(cx + rx * math.cos(a), 3), round(cy + ry * math.sin(a), 3)]
    return {"s": "#000000", "f": None, "w": 0.5, "c": 0, "d": [d]}


def _chu(x, y, t, co=5.0):
    """Cum chu cache: [x, y chan chu, co, font, chu, goc, dai, mau]; dai ~ 0.5*co/ky tu."""
    return [x, y, co, "MS-PGothic", t, 0, round(0.5 * co * len(t), 2), "#000000"]


# ---------------------------------------------------------------- be rong net
def test_stroke_width_takes_the_path_matrix_into_account():
    """get_drawings() ghi 10.0 cho net that ra ~0.53pt: phai nhan voi sqrt(|det|)."""
    svg = ('<svg><path transform="matrix(.05,0,0,-.05,10,20)" stroke-width="10" d="M0 0"/>'
           '<path stroke-width="10" transform="matrix(.05 0 0 -.05 0 0)" d="M1 1"/>'
           '<path stroke-width="1" d="M2 2"/><path d="M3 3"/></svg>')
    rong = MDW.be_rong_that(svg)
    assert rong[10.0] == pytest.approx(0.5)
    assert rong[1.0] == pytest.approx(1.0)


# ---------------------------------------------------------------- tim o
def test_ray_cast_finds_the_innermost_box():
    doan = MDW._doan_thang([_hop(0, 0, 40, 40), _hop(20, 20, 30, 30)])
    assert MDW._o_quanh((25, 25), doan) == [20, 20, 30, 30]
    assert MDW._o_quanh((8, 8), doan) == [0, 0, 40, 40]
    assert MDW._o_quanh((200, 50), doan) is None      # ngoai het: khong doan bua


def test_ray_cast_gives_up_beyond_its_reach():
    """Canh xa hon _TIA_XA thi khong phai o bao chu - vd khung ngoai ca ban ve."""
    doan = MDW._doan_thang([_hop(0, 0, 100, 100)])
    assert MDW._TIA_XA < 50
    assert MDW._o_quanh((50, 50), doan) is None


def test_ray_cast_works_on_an_ellipse_drawn_as_a_polyline():
    r = MDW._o_quanh((50, 30), MDW._doan_thang([_elip(50, 30, 20, 6)]))
    assert r == pytest.approx([30, 24, 70, 36], abs=0.05)


def test_unstroked_paths_do_not_count_as_box_edges():
    """Mang to dac (khong co net vien) khong phai canh o."""
    to = dict(_hop(15, 15, 25, 25), s=None, f="#000000")
    doan = MDW._doan_thang([_hop(0, 0, 40, 40), to])
    assert MDW._o_quanh((20, 20), doan) == [0, 0, 40, 40]


def _ve_mau():
    """Ban ve gia: 'Auto' vao (trai) va ra (phai), o 'S| Mode', 'Soft SW' + o '0',
    khung 'OPS Operation' co nut 'Open' - va mot 'Open' khac o xa."""
    net = [_elip(20, 20, 12, 4), _elip(180, 20, 12, 4),
           _hop(120, 40, 126, 48), _hop(126, 40, 160, 48),
           _hop(60, 60, 80, 70),
           _hop(60, 80, 80, 90), _hop(10, 80, 30, 90)]
    chu = [_chu(15, 22, "Auto"), _chu(175, 22, "Auto"),
           _chu(121, 46, "S"), _chu(128, 46, "Mode"),
           _chu(40, 67, "Soft SW"), _chu(68, 67, "0"),
           _chu(52, 84, "OPS Operation"), _chu(65, 87, "Open"), _chu(15, 87, "Open")]
    return {"khung": [200, 100], "net": net, "chu": chu}


def test_anchor_kinds_pick_the_right_label():
    spec = [["pin:1", "vao", "Auto"], ["ra:15", "ra", "Auto"],
            ["reg:OPS_OUT5", "ht", "Mode"], ["ops:OPS_IN6", "hop_sau", "Soft SW"],
            ["ops:OPS_IN2", "ops", "Open"], ["pin:9", "vao", "Missing"]]
    neo, thieu = MDW.tim_neo(_ve_mau(), spec)
    r = {o["nguon"]: o for o in neo}
    assert r["pin:1"]["r"] == pytest.approx([8, 16, 32, 24], abs=0.15)
    assert r["ra:15"]["r"] == pytest.approx([168, 16, 192, 24], abs=0.15)
    assert r["pin:1"]["hinh"] == "e" and r["reg:OPS_OUT5"]["hinh"] == "r"
    assert r["reg:OPS_OUT5"]["r"] == [120, 40, 160, 48]     # o 'S' GOP o nhan
    assert r["ops:OPS_IN6"]["r"] == [60, 60, 80, 70]        # o chua chu ngay sau nhan
    assert r["ops:OPS_IN2"]["r"] == [60, 80, 80, 90]        # 'Open' gan khung OPS nhat
    assert thieu == [["pin:9", "vao", "Missing"]]


# ---------------------------------------------------------------- noi net
class _P:
    def __init__(self, x, y):
        self.x, self.y = x, y


def test_segments_that_meet_are_chained_and_closed():
    a, b, c = _P(10, 10), _P(20, 10), _P(20, 20)
    items = [("l", a, b), ("l", b, c), ("l", c, a), ("l", _P(50, 50), _P(60, 50))]
    ds = MDW._chuoi_hoa(items, 10, 10)
    assert ds == [[1, 0, 0, 10, 0, 10, 10, 0, 0], [0, 40, 40, 50, 40]]


# ---------------------------------------------------------------- cache
def test_cache_of_another_version_or_broken_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(MDW, "_THU_MUC", str(tmp_path))
    assert MDW._doc_cache("X1") is None
    (tmp_path / "X1.json").write_text("{hong", encoding="utf-8")
    assert MDW._doc_cache("X1") is None
    assert MDW.ghi_cache("X1", {"phien_ban": MDW.PHIEN_BAN - 1})
    assert MDW._doc_cache("X1") is None
    assert MDW.ghi_cache("X1", {"phien_ban": MDW.PHIEN_BAN, "net": []})
    assert MDW._doc_cache("X1") == {"phien_ban": MDW.PHIEN_BAN, "net": []}


def test_block_without_a_mapped_drawing_says_why():
    ve, why = MDW.load("4011")
    assert ve is None and why


def test_extraction_from_the_real_manual():
    """Doc thang PDF cua hang (chi may phat trien co): khung, chu, be rong net that."""
    pytest.importorskip("fitz")
    from core import manual_index as MI
    pdf = MI.pdf_path("tag")
    if not pdf:
        pytest.skip("vendor TAG manual not on this PC")
    ve = MDW.tach(pdf, 35)
    assert ve["khung"] == pytest.approx([495.9, 310.3], abs=0.1)
    assert any(c[4].strip() == "AA143" for c in ve["chu"])
    assert len(ve["net"]) > 300                      # mat day ngang/doc thi con ~390
    rong = {n["w"] for n in ve["net"] if n["s"]}
    assert any(0.4 < w < 0.7 for w in rong)          # khong phai 10.0 chua doi he


# ---------------------------------------------------------------- gia tri
def test_source_values_follow_the_logic_graph():
    from ui.book_diagram_view import gia_tri_nguon
    g = {"regs": {"OPS_OUT5": "n8", "OPS_OUT6": "pin:14"}, "outs": {16: "n3"}}
    pv, nv = {1: 1, 14: 0}, {"n3": 1}
    assert gia_tri_nguon("pin:1", g, pv, nv) == 1
    assert gia_tri_nguon("pin:2", g, pv, nv) is None
    assert gia_tri_nguon("reg:OPS_OUT6", g, pv, nv) == 0    # o nho gan thang tu chan
    assert gia_tri_nguon("reg:OPS_OUT5", g, pv, nv) is None  # chot: khong doan
    assert gia_tri_nguon("ra:16", g, pv, nv) == 1
    assert gia_tri_nguon("ops:OPS_IN2", g, pv, nv) is None
    assert gia_tri_nguon("reg:OPS_OUT99", g, pv, nv) is None
    assert gia_tri_nguon("pin:1", {}, pv, {}) == 1          # khong co DEF: chan van to


# ---------------------------------------------------------------- widget
def _widget():
    from ui.book_diagram_view import BookDrawing
    ve = {"khung": [100, 40], "net": [_hop(5, 5, 95, 35)],
          "chu": [_chu(12, 17, "Auto")],
          "neo": [{"nguon": "pin:1", "kieu": "vao", "nhan": "Auto",
                   "r": [10, 10, 30, 20], "hinh": "r"},
                  {"nguon": "ra:15", "kieu": "ra", "nhan": "Auto",
                   "r": [60, 10, 80, 20], "hinh": "e"}]}
    return BookDrawing(ve, {0: 1, 1: 0}, {0: "<b>Auto</b>", 1: "ra"})


def test_widget_tints_under_the_drawing_and_maps_the_mouse_back():
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QColor
    from ui.book_diagram_view import TL
    _qapp()
    w = _widget()
    assert w.minimumWidth() == int(100 * TL) + 2
    img = w.grab().toImage()

    def mau(x, y):
        return QColor(img.pixel(int(1 + x * TL), int(1 + y * TL)))

    do, xanh, trang = mau(26, 12), mau(70, 12), mau(50, 30)
    assert do.red() > do.green() + 40                  # 1 = do
    assert xanh.green() > xanh.red() + 40              # 0 = xanh
    assert trang.red() > 240 and trang.green() > 240   # ngoai o: giay trang
    assert w.o_tai(QPoint(int(1 + 20 * TL), int(1 + 15 * TL))) == 0
    assert w.o_tai(QPoint(int(1 + 70 * TL), int(1 + 15 * TL))) == 1
    assert w.o_tai(QPoint(int(1 + 50 * TL), int(1 + 30 * TL))) is None
    w.deleteLater()


def test_tooltip_names_the_real_signal_and_the_value():
    from ui.book_diagram_view import _chu_thich
    o = {"nguon": "pin:3", "nhan": "Auto OP"}
    t = _chu_thich(o, 1, {3: "MOV-AOP"})
    assert "Auto OP" in t and "MOV-AOP" in t and "1" in t
    assert "MOV-AOP" not in _chu_thich({"nguon": "reg:OPS_OUT5", "nhan": "x"}, None,
                                       {5: "MOV-AOP"})
