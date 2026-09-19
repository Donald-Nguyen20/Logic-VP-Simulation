# -*- coding: utf-8 -*-
"""Moi file core/book_layouts/*.json (ban ve so tay cua tung khoi TAG dung trong db).

tests/test_book_diagram.py kiem ky 8204 - khoi duy nhat map ca o hien thi / nut OPS. O
day kiem CHUNG cho moi khoi: bang neo tro dung chan that cua khoi, nhan tren giay khop
ten chan (tru vai cho hang ghi khac, liet ke het o DONG_NGHIA), va tren ban ve that thi
moi dong tim ra o, vao nam ben trai, ra nam ben phai.

Test doc ban ve that tu skip khi may khong co cache (core/book_drawings bi gitignore)
lan PDF so tay; test doi chieu ten chan skip khi thieu file DEF cua hang."""
import glob
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import macro_def as MD  # noqa: E402
from core import manual_drawing as MDW  # noqa: E402

THU_MUC = os.path.join(os.path.dirname(__file__), os.pardir, "core", "book_layouts")
MA_CAC_KHOI = sorted(os.path.basename(p)[:-5]
                     for p in glob.glob(os.path.join(THU_MUC, "*.json")))

# Khoi TAG dung trong 21 file db ma so tay CO ve logic ben trong. 19 khoi dung trong db
# con lai (8227..8240, 824B, 82D5, 82FD) so tay chi co ky hieu + bang chan.
KHOI_CO_BAN_VE = {"8200", "8201", "8204", "8205", "8206", "8207", "8208", "8209", "820C",
                  "820D", "820E", "820F", "8211", "8214", "8215", "8225", "8226"}

# Ten chan trong bang -> chu hang ghi tren giay, khi hai cai khac nhau.
DONG_NGHIA = {("8209", "OP DMD"): "OP COM", ("8214", "DEV HI"): "DEV HH",
              ("8215", "A DEV HI"): "SENS-A DEV HH", ("8215", "B DEV HI"): "SENS-B DEV HH",
              ("8215", "C DEV HI"): "SENS-C DEV HH"}


def _spec(code):
    with open(os.path.join(THU_MUC, code + ".json"), encoding="utf-8") as f:
        return json.load(f)


def _hop(x0, y0, x1, y1):
    """Mot phan tu get_drawings() chi co mot hinh chu nhat."""
    fitz = pytest.importorskip("fitz")
    return {"items": [("re", fitz.Rect(x0, y0, x1, y1), 1)]}


# ---------------------------------------------------------------- khung ban ve
def test_one_frame_is_the_drawing():
    assert MDW.tim_khung([_hop(50, 100, 546, 410)]) == (50, 100, 546, 410)


def test_two_stacked_frames_are_taken_together_with_the_gap_between():
    """CB, D-SOV... hang ve 2 khung (AA101B1 + AA101B2): lay ca hai, giu khoang cach."""
    k = MDW.tim_khung([_hop(50, 100, 546, 540), _hop(50, 560, 546, 760)])
    assert k == (50, 100, 546, 760)


def test_small_boxes_and_page_margins_are_not_frames():
    """O ma ban ve / o hien thi qua nho; khung le trang to nhung dung, khong nam ngang."""
    assert MDW.tim_khung([_hop(460, 380, 546, 410), _hop(20, 20, 575, 820)]) is None
    assert MDW.tim_khung([]) is None


# ---------------------------------------------------------------- bang neo
def test_every_used_block_with_a_vendor_drawing_has_a_layout():
    assert set(MA_CAC_KHOI) == KHOI_CO_BAN_VE


@pytest.mark.parametrize("code", MA_CAC_KHOI)
def test_layout_file_is_well_formed(code):
    s = _spec(code)
    assert s["code"] == code and s["tai_lieu"] == "tag"
    assert isinstance(s["trang"], int) and s["trang_in"].startswith("P-")
    assert s["ma_ban_ve"].startswith("AA") and s["neo"]
    dong = [tuple(d) for d in s["neo"]]
    assert len(dong) == len(set(dong)), "neo trung dong"
    for nguon, kieu, nhan in dong:
        assert nguon.split(":")[0] in ("pin", "ra", "reg", "ops") and nhan.strip()
        assert kieu in ("vao", "ra", "ops", "ht", "hop_sau")


@pytest.mark.parametrize("code", MA_CAC_KHOI)
def test_anchors_point_at_real_pins_with_matching_labels(code):
    """Chan vao/ra trong bang neo co that tren khoi, va nhan tren giay la ten chan do (hoac
    chu hang ghi khac: ...DMD -> ...CMD, va DONG_NGHIA)."""
    pins = MD.pins_of(code)
    if not pins.get("in"):
        pytest.skip("vendor DEF files not found")
    for nguon, kieu, nhan in _spec(code)["neo"]:
        loai, _, so = nguon.partition(":")
        if loai not in ("pin", "ra") or kieu not in ("vao", "ra"):
            continue
        ten = pins["in" if loai == "pin" else "out"].get(int(so))
        assert ten, "%s khong co tren khoi" % nguon
        assert (loai == "pin") == (kieu == "vao"), nguon
        hop_le = {ten, ten.replace("DMD", "CMD"), DONG_NGHIA.get((code, ten))}
        assert nhan in hop_le, (nguon, ten, nhan)


@pytest.mark.parametrize("code", MA_CAC_KHOI)
def test_real_drawing_resolves_every_anchor_on_the_right_side(code):
    ve, why = MDW.load(code)
    if ve is None:
        pytest.skip(why)
    assert ve["thieu"] == [], ve["thieu"]
    w, _h = ve["khung"]
    for o in ve["neo"]:
        x = (o["r"][0] + o["r"][2]) / 2
        if o["kieu"] == "vao":
            assert x < w * 0.2, o
        elif o["kieu"] == "ra":
            assert x > w * 0.8, o
    ma = {c[4].strip() for c in ve["chu"]}
    assert all(m in ma for m in _spec(code)["ma_ban_ve"].split(" + "))


# ---------------------------------------------------------------- chu thich
def test_tooltip_of_an_analog_input_shows_its_number_not_unknown():
    """Khoi analog (SV, PV, SENS-A...): o khong to mau vi khong phai 0/1, nhung con so van
    phai hien - noi 'khong biet' la sai."""
    from ui.book_diagram_view import _chu_thich
    t = _chu_thich({"nguon": "pin:3", "nhan": "PV"}, None, {3: "FW-FLOW"}, 45.5)
    assert "45.5" in t and "FW-FLOW" in t
    assert "45.5" not in _chu_thich({"nguon": "pin:3", "nhan": "PV"}, None, {})


def test_book_panel_passes_analog_numbers_to_the_tooltips():
    qtw = pytest.importorskip("PySide6.QtWidgets")
    qtw.QApplication.instance() or qtw.QApplication([])
    from ui.book_diagram_view import book_panel
    ve, why = MDW.load("820C")
    if ve is None:
        pytest.skip(why)
    i = next(i for i, o in enumerate(ve["neo"]) if o["nhan"] == "PV")
    so = int(ve["neo"][i]["nguon"][4:])
    w, _ = book_panel("820C", pin_vals={}, pin_sigs={}, pin_nums={so: 12.25})
    assert w.gia_tri[i] is None and "12.25" in w.chu_thich[i]
    w.deleteLater()
