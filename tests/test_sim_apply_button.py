# -*- coding: utf-8 -*-
"""Hang nut cua 3 hop cai dat khoi dong (timer / tich phan / tram).

Diem dang giu: nut "Apply" phai tinh lai sheet ma KHONG chay mo phong dong. Truoc day
hop chi co mot nut "Run dynamic", nen muon dua khoi tram sang Auto la buoc phai chay
dong - ma chay dong reset sach trang thai va bat len mot cua so do thi khong ai can.
"""
import os
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from ui.app import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def hop(app):
    """Hop thoai that + mot 'cua so chinh' gia chi ghi lai da goi nhung gi."""
    vet = {"luu": 0, "tinh": 0, "dong": 0}
    tu = types.SimpleNamespace(
        cur_sheet=7,
        _apply_sheet_sim=lambda *a, **k: vet.__setitem__("tinh", vet["tinh"] + 1),
        run_dynamic_sim=lambda: vet.__setitem__("dong", vet["dong"] + 1),
    )
    dlg = QtWidgets.QDialog()
    row = MainWindow._nut_cai_dat(tu, dlg, lambda: vet.__setitem__("luu", vet["luu"] + 1))
    nut = {}
    for i in range(row.count()):
        w = row.itemAt(i).widget()
        if isinstance(w, QtWidgets.QPushButton):
            nut[w.text().lstrip("▶ ")] = w
    return dlg, nut, vet


def test_apply_luu_va_tinh_lai_nhung_khong_chay_dong(hop):
    dlg, nut, vet = hop
    nut["Apply"].click()
    assert vet == {"luu": 1, "tinh": 1, "dong": 0}
    assert dlg.result() == QtWidgets.QDialog.DialogCode.Accepted


def test_run_dynamic_van_chay_dong_nhu_cu(hop):
    _dlg, nut, vet = hop
    nut["Run dynamic"].click()
    assert vet == {"luu": 1, "tinh": 1, "dong": 1}


def test_close_khong_luu_gi(hop):
    dlg, nut, vet = hop
    nut["Close"].click()
    assert vet == {"luu": 0, "tinh": 0, "dong": 0}
    assert dlg.result() == QtWidgets.QDialog.DialogCode.Rejected


def test_apply_la_nut_mac_dinh(hop):
    """Go Enter trong hop = Apply, khong phai chay dong."""
    _dlg, nut, _vet = hop
    assert nut["Apply"].isDefault()
    assert not nut["Run dynamic"].isDefault()


def test_tinh_lai_hong_thi_van_dong_hop(hop):
    """Sheet tinh loi khong duoc lam ket hop thoai - cai dat da luu roi."""
    dlg, nut, vet = hop
    dlg2 = QtWidgets.QDialog()

    def no(*a, **k):
        raise RuntimeError("sheet hong")
    tu = types.SimpleNamespace(cur_sheet=1, _apply_sheet_sim=no,
                               run_dynamic_sim=lambda: vet.__setitem__("dong", 1))
    row = MainWindow._nut_cai_dat(tu, dlg2, lambda: vet.__setitem__("luu", 9))
    row.itemAt(row.count() - 1).widget().click()          # nut Apply o cuoi hang
    assert vet["luu"] == 9 and vet["dong"] == 0
    assert dlg2.result() == QtWidgets.QDialog.DialogCode.Accepted
