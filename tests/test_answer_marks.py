# -*- coding: utf-8 -*-
"""To mau ten tin hieu that trong cau tra loi Explain.

Cai de hong nhat khong phai mau ma la NHAN DANG ten: to nham chu viet hoa binh thuong
thi mau het nghia, to thieu thi nguoi doc tuong do khong phai ten tin hieu."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
QtGui = pytest.importorskip("PySide6.QtGui")

from ui.answer_marks import MAU, ten_trong_chu, to_mau  # noqa: E402

TEN = {"FURN PRS HI HI", "CWP 1 RUN", "CWP 1 RUN PERM", "PULV A TRIP",
       "BT-102 MFT(2)", "BNR B3 A/R TARGET VALUE"}


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_name_in_parentheses_is_found():
    assert ten_trong_chu("giu qua 2 giay (FURN PRS HI HI)", TEN) == {"FURN PRS HI HI"}


def test_two_names_on_one_line_are_both_found():
    got = ten_trong_chu("bom dang chay (CWP 1 RUN, PULV A TRIP)", TEN)
    assert got == {"CWP 1 RUN", "PULV A TRIP"}


def test_name_after_an_uppercase_word():
    """'tren DCS (CWP 1 RUN)': dau '(' dinh vao cum chu hoa, van phai ra dung ten."""
    assert ten_trong_chu("hien tren DCS (CWP 1 RUN)", TEN) == {"CWP 1 RUN"}


def test_longest_name_wins():
    """'CWP 1 RUN' nam trong 'CWP 1 RUN PERM': to ten ngan la cat doi ten dai."""
    assert ten_trong_chu("cho phep (CWP 1 RUN PERM)", TEN) == {"CWP 1 RUN PERM"}


def test_name_with_its_own_bracket_survives():
    assert ten_trong_chu("khoi dong (BT-102 MFT(2))", TEN) == {"BT-102 MFT(2)"}


def test_name_in_a_heading_and_mid_sentence():
    t = "# FURN PRS HI HI - ap suat buong lua\nKhi FURN PRS HI HI len thi lo dung."
    assert ten_trong_chu(t, TEN) == {"FURN PRS HI HI"}


@pytest.mark.parametrize("t", ["tren DCS", "CPU A va CPU B", "3.0 kPa", "MFT", "ABC XYZ"])
def test_ordinary_capitals_are_not_names(t):
    assert ten_trong_chu(t, TEN) == set()


def test_colour_lands_on_the_name_only(app, monkeypatch):
    import ui.answer_marks as AM
    monkeypatch.setattr(AM, "ten_du_an", lambda db, cpu=None: TEN)
    e = QtWidgets.QTextEdit()
    e.setMarkdown("## (2)\n- ap suat cao (FURN PRS HI HI)\n- bom chay tren DCS (CWP 1 RUN)\n")
    assert AM.to_mau(e, "db") == 2
    doc = e.document()
    for s, mau, dam in (("FURN PRS HI HI", MAU, 700), ("CWP 1 RUN", MAU, 700),
                        ("DCS", "#000000", 400)):
        c = doc.find(s)
        assert not c.isNull(), s
        assert c.charFormat().foreground().color().name().upper() == mau.upper(), s
        assert c.charFormat().fontWeight() == dam, s


def test_bold_does_not_lighten_a_heading(app, monkeypatch):
    """ai_dialog dat tieu de o 700; to dam phai dung dung 700, thap hon la lam nhat chu."""
    import ui.answer_marks as AM
    monkeypatch.setattr(AM, "ten_du_an", lambda db, cpu=None: TEN)
    e = QtWidgets.QTextEdit()
    e.setMarkdown("# FURN PRS HI HI\n")
    cur = QtGui.QTextCursor(e.document())
    cur.select(QtGui.QTextCursor.SelectionType.Document)
    cf = QtGui.QTextCharFormat()
    cf.setFontWeight(700)
    cur.mergeCharFormat(cf)
    assert AM.to_mau(e, "db") == 1
    assert e.document().find("FURN PRS HI HI").charFormat().fontWeight() == 700


def test_location_table_colours_only_the_signal_column(app, monkeypatch):
    """Muc vi tri do code gan: ten loop/sheet ('010 PULV A TRIP LOOP') trung chu ten tin
    hieu nhung khong phai tin hieu. Bang cua AI phia tren van to o moi cot."""
    import ui.answer_marks as AM
    monkeypatch.setattr(AM, "ten_du_an", lambda db, cpu=None: TEN)
    e = QtWidgets.QTextEdit()
    e.setMarkdown("## (4) SO\n\n| a | b |\n|---|---|\n| 1 | giu FURN PRS HI HI |\n\n"
                  "## (5) VI TRI\n\nloi dan co BT-102 MFT(2)\n\n"
                  "| Ten | Loop |\n|---|---|\n| CWP 1 RUN | 010 PULV A TRIP LOOP |\n")
    assert AM.to_mau(e, "db", tieu_de_bang="(5) VI TRI") == 2
    doc = e.document()
    for s, mau in (("FURN PRS HI HI", MAU), ("CWP 1 RUN", MAU),
                   ("PULV A TRIP", "#000000"), ("BT-102 MFT(2)", "#000000")):
        c = doc.find(s)
        assert c.charFormat().foreground().color().name().upper() == mau.upper(), s


def test_no_names_means_no_change(app, monkeypatch):
    import ui.answer_marks as AM
    monkeypatch.setattr(AM, "ten_du_an", lambda db, cpu=None: set())
    e = QtWidgets.QTextEdit()
    e.setMarkdown("khong co ten nao o day")
    assert AM.to_mau(e, "db") == 0
