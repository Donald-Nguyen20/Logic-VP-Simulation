# -*- coding: utf-8 -*-
"""Kho cau tra loi Explain.

Hai thu de hong nhat: (a) khoa khong doi khi ban ve doi -> nguoi dung doc cau cu cho
ban ve moi, (b) luu nham cau bao loi -> lan sau mo ra van la loi do, khong hoi lai duoc.
"""
import json
import os

import pytest

from core import ai_cache as C


@pytest.fixture
def kho(tmp_path, monkeypatch):
    """Moi test mot thu muc rieng: khong duoc dung toi data/ that cua nguoi dung."""
    monkeypatch.setattr(C.DD, "duong", lambda ten: str(tmp_path / "app_data" / ten))
    d = tmp_path / "du an"
    d.mkdir()
    return str(d / "01 UCS.db")


def test_cau_hoi_khac_thi_khoa_khac():
    g = C.khoa("ngu canh A", "vi", "groq", "m1")
    assert g == C.khoa("ngu canh A", "vi", "groq", "m1")
    assert g != C.khoa("ngu canh A doi mot chu", "vi", "groq", "m1")
    assert g != C.khoa("ngu canh A", "en", "groq", "m1")
    assert g != C.khoa("ngu canh A", "vi", "groq", "m2")
    assert g != C.khoa("ngu canh A", "vi", "gemini", "m1")


def test_file_nam_canh_db(kho):
    cho = C.luu(kho, "k1", "cau tra loi", name="PULV A TRIP")
    assert cho == os.path.join(os.path.dirname(kho), "01 UCS.ai.json")
    assert os.path.exists(cho)
    d = json.load(open(cho, encoding="utf-8"))
    assert d["version"] == C.PHIEN_BAN and d["entries"]["k1"]["name"] == "PULV A TRIP"


def test_luu_roi_tim_lai(kho):
    C.luu(kho, "k1", "day la cau tra loi", model="llama-3.3")
    m = C.tim(kho, "k1")
    assert m["answer"] == "day la cau tra loi" and m["model"] == "llama-3.3"
    assert m["at"] and C.tim(kho, "k2") is None
    assert C.dem(kho) == 1


def test_chep_sang_may_khac(tmp_path, monkeypatch, kho):
    """Chep ca thu muc du an sang cho khac: cau tra loi phai di theo."""
    C.luu(kho, "k1", "cau tra loi")
    may2 = tmp_path / "may khac"
    may2.mkdir()
    for t in os.listdir(os.path.dirname(kho)):
        (may2 / t).write_bytes(open(os.path.join(os.path.dirname(kho), t), "rb").read())
    assert C.tim(str(may2 / "01 UCS.db"), "k1")["answer"] == "cau tra loi"


def test_thu_muc_db_chi_doc_thi_lui_ve_data(tmp_path, monkeypatch):
    """Db nam tren dia chi doc: van phai luu duoc, chi la luu o cho khac."""
    monkeypatch.setattr(C.DD, "duong", lambda ten: str(tmp_path / "app_data" / ten))
    chan = tmp_path / "chan"
    chan.write_text("day la file, khong phai thu muc")   # tao thu muc trong do se hong
    db = str(chan / "01 UCS.db")
    cho = C.luu(db, "k1", "cau tra loi")
    assert cho == str(tmp_path / "app_data" / "ai_cache" / "01 UCS.ai.json")
    assert C.tim(db, "k1")["answer"] == "cau tra loi"


def test_file_hong_khong_lam_hong_duong_hoi(kho):
    C.luu(kho, "k1", "cau tra loi")
    open(os.path.join(os.path.dirname(kho), "01 UCS.ai.json"), "w").write("{ hong")
    assert C.tim(kho, "k1") is None          # coi nhu kho rong: cung lam la hoi lai
    assert C.luu(kho, "k2", "cau moi")       # va van ghi de duoc len file hong
    assert C.tim(kho, "k2")["answer"] == "cau moi"


def test_day_kho_thi_bo_cau_vao_truoc_nhat(kho, monkeypatch):
    monkeypatch.setattr(C, "TOI_DA", 3)
    for i in range(5):
        C.luu(kho, "k%d" % i, "cau %d" % i)
    con = json.load(open(C.cac_cho(kho)[0], encoding="utf-8"))["entries"]
    assert sorted(con) == ["k2", "k3", "k4"]


def test_ghi_lai_cau_cu_thi_no_ve_cuoi_hang(kho, monkeypatch):
    monkeypatch.setattr(C, "TOI_DA", 2)
    C.luu(kho, "k1", "cu")
    C.luu(kho, "k2", "cau 2")
    C.luu(kho, "k1", "moi")                  # dung lai -> khong duoc bi bo truoc k2
    C.luu(kho, "k3", "cau 3")
    con = json.load(open(C.cac_cho(kho)[0], encoding="utf-8"))["entries"]
    assert sorted(con) == ["k1", "k3"] and con["k1"]["answer"] == "moi"


CAU_THAT = "# PULV A TRIP\n\n## (1) NO LA GI\n" + "noi dai ra cho du bon tram ky tu. " * 15


@pytest.mark.parametrize("out,loi,mong", [
    (CAU_THAT, False, True),
    (CAU_THAT, True, False),                                   # luot ket thuc bang loi
    ("Khong goi duoc groq.\n\nTimeoutError: het gio", False, False),
    (CAU_THAT + "\n(Ghi chu: qua 420s nen bi cat giua chung.)", False, False),
    ("Chua dung duoc Groq: con thieu API key.", False, False),  # huong dan cai dat
    ("", False, False),
])
def test_chi_luu_cau_tra_loi_that(out, loi, mong):
    pytest.importorskip("PySide6.QtWidgets")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from ui.ai_dialog import luu_duoc
    assert luu_duoc(out, loi) is mong
