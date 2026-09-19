# -*- coding: utf-8 -*-
"""Do duong day tren ban ve so tay (core/book_trace.py).

Phan dau dung ban ve gia lap nho, dung dung kieu net hang ve: cong = thanh vao doc +
hop ghep tu 3 net ho + day ra, mui ten = tam giac to xanh voi dau mui nam tren thanh
vao. Phan sau kiem tren ban ve that (tu skip khi may khong co cache core/book_drawings)."""
import math

import pytest

from core import book_trace as BT
from core import manual_drawing as MDW

DEN = "#000000"


# ---------------------------------------------------------------- dung ban ve gia
def _day(*p):
    """Mot net ho di qua cac diem p."""
    return {"s": DEN, "f": None, "w": 0.5, "c": 0, "d": [[0] + [v for q in p for v in q]]}


def _mui(x, y):
    """Mui ten chi sang phai, dau mui o (x, y); kem ban vien den nhu hang ve."""
    d = [1, x - 3.6, y - 0.6, x, y, x - 3.6, y + 0.6, x - 3.6, y - 0.6]
    return [{"s": None, "f": "#00FFFF", "w": 0, "c": 0, "d": [d]},
            {"s": DEN, "f": None, "w": 0.5, "c": 0, "d": [list(d)]}]


def _tron(cx, cy, rx, ry, n=64):
    p = [(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n))
         for k in range(n + 1)]
    return {"s": DEN, "f": None, "w": 0.5, "c": 0,
            "d": [[1] + [round(v, 2) for q in p for v in q]]}


def _cham(x, y):
    """Cham noi day: hinh tron nho kin."""
    return _tron(x, y, 0.9, 0.9, 16)


def _chan(cx, cy):
    """E-lip chan rong 20pt cao 6pt -> (net, o neo)."""
    return _tron(cx, cy, 10, 3, 128), [cx - 10, cy - 3, cx + 10, cy + 3]


def _cong(x, ys, ra_x):
    """Cong: thanh vao o x, chan vao o cac muc ys (moi chan co mui ten), hop 8.7pt,
    day ra tu giua canh phai toi ra_x. -> (cac net, (x_ra, y_ra))."""
    tren, duoi = ys[0], ys[-1]
    net = [_day((x, tren - 1.5), (x, duoi + 1.5)),
           _day((x, tren), (x + 8.7, tren)), _day((x + 8.7, tren), (x + 8.7, duoi)),
           _day((x + 8.7, duoi), (x, duoi))]
    for y in ys:
        net += _mui(x, y)
    giua = (tren + duoi) / 2
    net.append(_day((x + 8.7, giua), (ra_x, giua)))
    return net, (ra_x, giua)


def _ve(net, neo, chu=()):
    return {"khung": [300, 200], "net": net, "chu": list(chu),
            "neo": [{"nguon": n, "kieu": k, "nhan": n, "r": r, "hinh": "e"} for n, k, r in neo]}


def _mach_co_ban():
    """A, B -> cong AND o x=100 -> e-lip ra Z. Tra (ve, ten -> chi so neo)."""
    ea, ra = _chan(20, 50)
    eb, rb = _chan(20, 80)
    ez, rz = _chan(200, 52.2)
    cong, (xr, yr) = _cong(100, [50, 54.4], 190)
    net = [ea, eb, ez, _day((30, 50), (100, 50)),
           _day((30, 80), (70, 80), (70, 54.4), (100, 54.4))] + cong
    net += _mui(190, 52.2)
    return _ve(net, [("pin:1", "vao", ra), ("pin:2", "vao", rb), ("ra:1", "ra", rz)])


def _sang(ve, i):
    return BT.duong_sang(BT.ban_do(ve), ve["neo"][i])


def _co_net(sang, x0, y0, x1, y1):
    """Co doan sang nao nam tron trong hop (x0,y0)-(x1,y1) khong."""
    return any(min(a, c) >= x0 - 0.01 and max(a, c) <= x1 + 0.01 and
               min(b, d) >= y0 - 0.01 and max(b, d) <= y1 + 0.01 for a, b, c, d in sang)


# ---------------------------------------------------------------- di xuoi
def test_input_pin_lights_its_wire_the_gate_and_the_output():
    ve = _mach_co_ban()
    s = _sang(ve, 0)
    assert _co_net(s, 30, 50, 100, 50)                 # day cua A
    assert _co_net(s, 108.7, 50, 108.7, 54.4)          # canh phai cua cong
    assert _co_net(s, 108.7, 52.2, 190, 52.2)          # day ra
    assert _co_net(s, 190, 49, 210, 56)                # e-lip Z


def test_trace_never_flows_back_into_the_gates_other_inputs():
    """Thanh vao noi moi chan vao; khong cat o dau mui ten thi bam A sang luon B."""
    s = _sang(_mach_co_ban(), 0)
    assert not _co_net(s, 30, 80, 70, 80)
    assert not _co_net(s, 70, 54.4, 100, 54.4)
    assert not _co_net(s, 10, 77, 30, 83)              # e-lip B


def test_branch_at_a_junction_reaches_both_gates():
    ea, ra = _chan(20, 50)
    c1, _ = _cong(100, [50, 54.4], 150)
    c2, _ = _cong(100, [90, 94.4], 150)
    net = [ea, _day((30, 50), (100, 50)), _cham(60, 50), _day((60, 50), (60, 90), (100, 90)),
           _day((40, 54.4), (100, 54.4)), _day((40, 94.4), (100, 94.4))] + c1 + c2
    s = _sang(_ve(net, [("pin:1", "vao", ra)]), 0)
    assert _co_net(s, 108.7, 52.2, 150, 52.2) and _co_net(s, 108.7, 92.2, 150, 92.2)
    assert not _co_net(s, 40, 54.4, 100, 54.4) and not _co_net(s, 40, 94.4, 100, 94.4)


def test_wires_that_only_cross_are_not_joined():
    """Hai day cat ngang nhau (khong mut nao cham) la khong noi - quy uoc ban ve."""
    ea, ra = _chan(20, 50)
    net = [ea, _day((30, 50), (150, 50)), _day((80, 10), (80, 120))]
    s = _sang(_ve(net, [("pin:1", "vao", ra)]), 0)
    assert _co_net(s, 30, 50, 150, 50) and not _co_net(s, 80, 10, 80, 120)


def test_trace_passes_through_a_not_bubble():
    ea, ra = _chan(20, 50)
    cong, _ = _cong(100, [50, 54.4], 150)
    net = [ea, _day((30, 50), (60, 50)), _tron(63, 50, 3, 3), _day((66, 50), (100, 50)),
           _day((40, 54.4), (100, 54.4))] + cong
    s = _sang(_ve(net, [("pin:1", "vao", ra)]), 0)
    assert _co_net(s, 66, 50, 100, 50) and _co_net(s, 108.7, 52.2, 150, 52.2)


def test_arrow_tip_a_little_past_the_end_of_the_bar_still_enters_the_gate():
    """Cong 4 chan cua hang: dau mui chan tren cung le ra ngoai thanh vao ~0.7pt."""
    ea, ra = _chan(20, 40.7)
    cong, _ = _cong(100, [40.7, 45, 49.4, 53.7], 150)
    cong[0] = _day((100, 41.4), (100, 53))            # thanh vao ngan hon chan ngoai cung
    net = [ea, _day((30, 40.7), (100, 40.7))] + cong
    s = _sang(_ve(net, [("pin:1", "vao", ra)]), 0)
    assert _co_net(s, 108.7, 47.2, 150, 47.2)


def test_feedback_loop_ends():
    """Day ra cua cong vong ve chan vao cua chinh no: phai dung, khong lap mai."""
    ea, ra = _chan(20, 50)
    cong, (xr, yr) = _cong(100, [50, 54.4], 150)
    net = [ea, _day((30, 50), (100, 50)), _cham(130, yr),
           _day((130, yr), (130, 70), (90, 70), (90, 54.4), (100, 54.4))] + cong
    s = _sang(_ve(net, [("pin:1", "vao", ra)]), 0)
    assert _co_net(s, 90, 54.4, 100, 54.4)


def test_the_big_frame_does_not_join_everything_it_touches():
    ea, ra = _chan(20, 50)
    khung = {"s": DEN, "f": None, "w": 0.5, "c": 0,
             "d": [[1, 0, 0, 300, 0, 300, 200, 0, 200]]}
    net = [ea, khung, _day((30, 50), (300, 50)), _day((0, 120), (150, 120))]
    s = _sang(_ve(net, [("pin:1", "vao", ra)]), 0)
    assert not _co_net(s, 0, 120, 150, 120) and not _co_net(s, 0, 0, 300, 0)


def test_stacked_pin_ellipses_that_touch_are_not_joined():
    """E-lip chan xep sat nhau cham vien: van la hai chan rieng."""
    ea, ra = _chan(20, 50)
    eb, rb = _chan(20, 56)
    ez, _ = _chan(110, 50)
    net = [ea, eb, ez, _day((30, 50), (100, 50)), _day((30, 56), (60, 56))]
    s = _sang(_ve(net, [("pin:1", "vao", ra), ("pin:2", "vao", rb)]), 1)
    assert _co_net(s, 30, 56, 60, 56) and not _co_net(s, 30, 50, 100, 50)


def test_dot_joins_two_wires_that_both_run_through_it():
    """Nga tu co cham noi: khong mut nao nam o cham nhung hai day van noi."""
    ea, ra = _chan(20, 50)
    net = [ea, _day((30, 50), (150, 50)), _day((80, 20), (80, 100)), _cham(80, 50)]
    s = _sang(_ve(net, [("pin:1", "vao", ra)]), 0)
    assert _co_net(s, 80, 20, 80, 100)


def test_wire_overshooting_the_arrow_tip_is_cut_there():
    """Hang ve day A chay lo qua dau mui, de len canh tren hop cong toi tan goc phai.
    Khong cat thi day A dinh vao hop: bam B sang nguoc ca A."""
    ve = _mach_co_ban()
    ve["net"][3] = _day((30, 50), (108.7, 50))
    s = _sang(ve, 1)
    assert _co_net(s, 108.7, 52.2, 190, 52.2)
    assert not _co_net(s, 10, 47, 30, 53)                 # e-lip A
    assert _co_net(_sang(ve, 0), 108.7, 52.2, 190, 52.2)


def test_connector_label_continues_the_wire_elsewhere_on_the_page():
    """Mui ten chi vao "(A)" -> day tiep tuc tu mot "(A)" khac, bat dau ngay sau chu."""
    ea, ra = _chan(20, 50)
    ez, rz = _chan(200, 100)
    net = [ea, ez, _day((30, 50), (80, 50)), _day((127.3, 100), (190, 100))] + _mui(80, 50)
    chu = [[81.5, 51.5, 4.3, "MS-PGothic", "(A)", 0, 5.3],
           [120, 101.5, 4.3, "MS-PGothic", "(A)", 0, 5.3]]
    ve = _ve(net, [("pin:1", "vao", ra), ("ra:1", "ra", rz)], chu)
    assert _co_net(_sang(ve, 0), 127.3, 100, 190, 100)
    assert _co_net(_sang(ve, 1), 30, 50, 80, 50)
    assert [m["nhan"] for m in BT.ban_do(ve)["mui"]] == ["(A)"]


def _hai_trang(ten_nguon):
    """Trang 1: A -> "AA1-2: X" (gui sang trang 2). Trang 2: ten_nguon -> Z."""
    ea, ra = _chan(20, 50)
    ez, rz = _chan(200, 100)
    net = [ea, ez, _day((30, 50), (80, 50)), _day((127.3, 100), (190, 100))] + _mui(80, 50)
    chu = [[81.5, 51.5, 4.3, "Arial", "AA1-2: X", 0, 16],
           [111.3, 101.5, 4.3, "Arial", ten_nguon, 0, 16]]
    return _ve(net, [("pin:1", "vao", ra), ("ra:1", "ra", rz)], chu)


def test_page_link_label_continues_the_wire_on_the_other_page():
    """Ban ve 2 trang: "AA1-2: X" o trang 1 noi voi "AA1-1: X" o trang 2."""
    ve = _hai_trang("AA1-1: X")
    assert _co_net(_sang(ve, 0), 127.3, 100, 190, 100)
    assert _co_net(_sang(ve, 1), 30, 50, 80, 50)


@pytest.mark.parametrize("ten_nguon", ["AA1-1: Y", "AA1-2: X", "X"])
def test_page_link_label_needs_same_name_on_a_different_page(ten_nguon):
    assert not _co_net(_sang(_hai_trang(ten_nguon), 0), 127.3, 100, 190, 100)


def _hop_t():
    """Hop chuyen mach T: A vao canh trai co mui ten, B vao goc tren-trai bang net cheo
    KHONG mui ten, ra o giua canh phai."""
    ea, ra = _chan(20, 54.35)
    eb, rb = _chan(20, 40)
    net = [ea, eb, _day((30, 54.35), (100, 54.35)), _day((30, 40), (95, 40), (100, 50)),
           _day((100, 50), (108.7, 50)), _day((108.7, 50), (108.7, 58.7)),
           _day((108.7, 58.7), (100, 58.7)), _day((100, 58.7), (100, 50)),
           _day((108.7, 54.35), (150, 54.35))] + _mui(100, 54.35)
    return _ve(net, [("pin:1", "vao", ra), ("pin:2", "vao", rb)])


def test_switch_box_diagonal_input_acts_as_an_arrow():
    ve = _hop_t()
    a, b = _sang(ve, 0), _sang(ve, 1)
    assert _co_net(a, 108.7, 54.35, 150, 54.35) and not _co_net(a, 30, 40, 95, 40)
    assert _co_net(b, 108.7, 54.35, 150, 54.35) and not _co_net(b, 30, 54.35, 100, 54.35)


# ---------------------------------------------------------------- widget
def test_clicking_a_pin_lights_its_path_and_clicking_again_clears_it():
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from ui.book_diagram_view import TL, BookDrawing
    _app = QApplication.instance() or QApplication([])
    w = BookDrawing(_mach_co_ban(), {}, {})
    w.resize(w.sizeHint())

    def diem(x, y):
        return QPoint(int(1 + x * TL), int(1 + y * TL))

    def mau(x, y):
        return QColor(w.grab().toImage().pixel(diem(x, y)))

    assert mau(150, 52.2 + 0.5).blue() > 240                  # truoc khi bam: giay trang
    QTest.mouseClick(w, Qt.MouseButton.LeftButton, pos=diem(20, 50))
    assert w.chon_o == 0
    cam = mau(150, 52.2 + 0.5)                                # sat day ra cua cong
    assert cam.red() > 240 and cam.blue() < 200
    QTest.mouseClick(w, Qt.MouseButton.LeftButton, pos=diem(20, 50))
    assert w.chon_o is None and mau(150, 52.2 + 0.5).blue() > 240
    QTest.mouseClick(w, Qt.MouseButton.LeftButton, pos=diem(20, 80))
    assert w.chon_o == 1
    QTest.mouseClick(w, Qt.MouseButton.LeftButton, pos=diem(250, 150))
    assert w.chon_o is None
    w.deleteLater()


# ---------------------------------------------------------------- di nguoc
def test_output_pin_lights_everything_that_drives_it():
    s = _sang(_mach_co_ban(), 2)
    assert _co_net(s, 30, 50, 100, 50) and _co_net(s, 70, 54.4, 100, 54.4)
    assert _co_net(s, 108.7, 52.2, 190, 52.2)


def test_anchor_with_nothing_under_it_lights_nothing():
    ve = _mach_co_ban()
    o = {"nguon": "pin:9", "kieu": "vao", "nhan": "X", "r": [250, 150, 260, 160], "hinh": "e"}
    assert BT.duong_sang(BT.ban_do(ve), o) == []


# ---------------------------------------------------------------- ban ve that
def _that(code):
    ve, why = MDW.load(code)
    if ve is None:
        pytest.skip(why)
    return ve


def _o(ve, nhan, kieu):
    return next(o for o in ve["neo"] if o["nhan"] == nhan and o["kieu"] == kieu)


def _trong(sang, r):
    return any(r[0] - 0.5 <= (a + c) / 2 <= r[2] + 0.5 and r[1] - 0.5 <= (b + d) / 2 <= r[3] + 0.5
               for a, b, c, d in sang)


def test_real_mov2_auto_pin_reaches_the_auto_output_through_the_latch():
    ve = _that("8204")
    s = BT.duong_sang(BT.ban_do(ve), _o(ve, "Auto", "vao"))
    assert _trong(s, _o(ve, "Auto", "ra")["r"])
    assert not _trong(s, _o(ve, "POS", "vao")["r"])


def test_real_mov2_pos_only_feeds_its_display_cell():
    """POS di thang vao o 'Position Indicate' - khong duoc lan sang day nao khac."""
    ve = _that("8204")
    bd = BT.ban_do(ve)
    s = BT.duong_sang(bd, _o(ve, "POS", "vao"))
    assert _trong(s, _o(ve, "Position Indicate", "ht")["r"])
    for o in ve["neo"]:
        if o["nhan"] not in ("POS", "Position Indicate"):
            assert not _trong(s, o["r"]), o["nhan"]


def test_real_mov2_output_traced_back_reaches_its_input_pins():
    ve = _that("8204")
    s = BT.duong_sang(BT.ban_do(ve), _o(ve, "OP CMD", "ra"))
    assert _trong(s, _o(ve, "F-OP", "vao")["r"])
    assert not _trong(s, _o(ve, "POS", "vao")["r"])


def test_real_two_page_drawing_is_traced_across_the_page_link():
    """8215: SENS-A vao o trang 1, SENS-A DEV HH ra o trang 2."""
    ve = _that("8215")
    bd = BT.ban_do(ve)
    s = BT.duong_sang(bd, _o(ve, "SENS-A", "vao"))
    assert _trong(s, _o(ve, "SENS-A DEV HH", "ra")["r"])
    s = BT.duong_sang(bd, _o(ve, "ABN", "ra"))
    assert _trong(s, _o(ve, "SENS-A", "vao")["r"])


CAC_KHOI = ["8200", "8201", "8204", "8205", "8206", "8207", "8208", "8209", "820C",
            "820D", "820E", "820F", "8211", "8214", "8215", "8225", "8226"]


@pytest.mark.parametrize("code", CAC_KHOI)
def test_real_every_arrow_has_a_wire_behind_and_something_ahead(code):
    """Phia truoc mui ten: net (cong, o hien thi...) hoac chu (ten tin hieu ra ngoai /
    nhan noi). Nhan noi "(A)" thi phai tim thay day xuat phat o nhan cung ten."""
    ve = _that(code)
    bd = BT.ban_do(ve)
    thieu = [m["dau"] for m in bd["mui"] if not m["vao"] or not (m["toi"] or m["nhan"])]
    assert not thieu, thieu
    noi = [m["dau"] for m in bd["mui"]
           if m["nhan"] and BT._NHAN_NOI.fullmatch(m["nhan"]) and not m["toi"]]
    assert not noi, noi


@pytest.mark.parametrize("code", CAC_KHOI)
def test_real_every_input_pin_lights_more_than_its_own_ellipse(code):
    ve = _that(code)
    bd = BT.ban_do(ve)
    for o in ve["neo"]:
        if o["kieu"] != "vao":
            continue
        s = BT.duong_sang(bd, o)
        ngoai = [d for d in s if not (o["r"][0] - 0.5 <= min(d[0], d[2]) and
                                      max(d[0], d[2]) <= o["r"][2] + 0.5)]
        assert ngoai, o["nhan"]
