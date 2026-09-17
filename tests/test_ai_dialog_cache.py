# -*- coding: utf-8 -*-
"""Hop thoai Explain doc/ghi kho cau tra loi. KHONG goi model lan nao trong bai nay:
chi di duong "da co san" va duong luu lai."""
import os
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from core import ai_cache as C  # noqa: E402

CAU = "# NET1\n\n## (1) NO LA GI\n" + "cau tra loi dai cho du bon tram ky tu. " * 15


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(C.DD, "duong", lambda ten: str(tmp_path / "app_data" / ten))
    d = tmp_path / "du an"
    d.mkdir()
    return str(d / "01 UCS.db")


def _mo(db):
    from ui.ai_dialog import AIExplainDialog
    return AIExplainDialog(db, 1, "NET1")


def _khoa(d):
    return C.khoa(d._prompt(), d._lang, d._provider(), d._model())


def test_chua_co_gi_thi_cua_so_de_trong(app, db):
    d = _mo(db)
    assert d.answer.toPlainText().strip() == "" or "Bam" in d.answer.toPlainText()
    d.deleteLater()


def test_mo_lai_la_hien_ngay_cau_da_luu(app, db):
    d = _mo(db)
    k = _khoa(d)
    d.deleteLater()
    C.luu(db, k, CAU, name="NET1", model="llama-3.3")
    d2 = _mo(db)
    assert "NO LA GI" in d2.answer.toPlainText()
    tt = d2.status_lbl.text()
    assert "kho" in tt and "llama-3.3" in tt and "Hoi lai" in tt
    d2.deleteLater()


def test_cau_cua_ngon_ngu_khac_khong_bi_dem_ra_dung(app, db):
    d = _mo(db)
    C.luu(db, _khoa(d), CAU)          # luu cho ngon ngu dang chon
    d._lang = "vi" if d._lang == "en" else "en"
    assert C.tim(db, _khoa(d)) is None
    d.deleteLater()


def test_luu_lai_sau_mot_luot_hoi_that(app, db):
    d = _mo(db)
    d._khoa = _khoa(d)
    d._w = types.SimpleNamespace(loi=False)
    assert "Da luu" in d._luu(CAU)
    assert C.tim(db, d._khoa)["answer"] == CAU
    d.deleteLater()


def test_luot_hong_thi_khong_luu(app, db):
    d = _mo(db)
    d._khoa = _khoa(d)
    d._w = types.SimpleNamespace(loi=True)
    assert d._luu("Khong goi duoc groq.") == ""
    assert C.tim(db, d._khoa) is None
    d.deleteLater()


@pytest.fixture
def muc_gia(monkeypatch):
    """Muc vi tri gia: ghi lai ten nhan duoc va so muc, khoi can CSDL that."""
    from core import signal_locations as SL
    from ui import answer_marks as AM
    monkeypatch.setattr(AM, "ten_du_an", lambda db, cpu_paths=None: {"NET1"})
    monkeypatch.setattr(SL, "muc_vi_tri", lambda ten, dbs, **kw:
                        "\n\n## (%d) VI TRI %s\n" % (kw["so"], ",".join(ten)))


def test_muc_vi_tri_chi_de_hien_kho_van_luu_cau_goc(app, db, muc_gia):
    """Gan luc hien, khong luu: khoa kho khong doi va vi tri luon tra theo ban ve moi."""
    d = _mo(db)
    d._khoa = _khoa(d)
    d._w = types.SimpleNamespace(loi=False)
    d._t0, d._ntool = 0, 0
    d._show(CAU)
    assert "(5) VI TRI NET1" in d.answer.toPlainText()
    assert C.tim(db, d._khoa)["answer"] == CAU.strip()       # _show cat khoang trang cuoi
    d.deleteLater()


def test_cau_cu_mo_tu_kho_cung_co_muc_vi_tri(app, db, muc_gia):
    d = _mo(db)
    k = _khoa(d)
    d.deleteLater()
    C.luu(db, k, CAU)
    d2 = _mo(db)
    assert "NO LA GI" in d2.answer.toPlainText()
    assert "VI TRI NET1" in d2.answer.toPlainText()
    d2.deleteLater()


def test_luot_hong_thi_khong_gan_muc_vi_tri(app, db, muc_gia):
    d = _mo(db)
    assert d._muc_vi_tri("Khong goi duoc groq.", False) == ""
    assert d._muc_vi_tri(CAU, True) == ""
    d.deleteLater()


def test_cau_da_luu_khong_bat_nut_len_khi_chua_cau_hinh(app, db, monkeypatch):
    """Hien lai cau cu la mot chuyen, cho bam Ask khi chua co API key lai la chuyen khac."""
    d = _mo(db)
    k = _khoa(d)
    d.deleteLater()
    C.luu(db, k, CAU)
    from ui import ai_dialog as AD
    that = AD.AIExplainDialog._refresh

    def chua_cau_hinh(self):
        that(self)
        self._bat_nut(False)
    monkeypatch.setattr(AD.AIExplainDialog, "_refresh", chua_cau_hinh)
    d2 = _mo(db)
    assert "NO LA GI" in d2.answer.toPlainText()
    assert not d2.btn_ask.isEnabled() and not d2.btn_again.isEnabled()
    d2.deleteLater()
