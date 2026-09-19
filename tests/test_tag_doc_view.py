# -*- coding: utf-8 -*-
"""O "How it works" trong cua so Help: dung duoc, co du bieu do, doi ngon ngu khong vo.

Chay khong man hinh (QT_QPA_PLATFORM=offscreen). Doi ngon ngu CHI trong bo nho - khong
ghi data/help_lang.json cua nguoi dung."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from core import help_i18n as I18N  # noqa: E402
from core import macro_def as MD  # noqa: E402
from core import tag_docs as TD  # noqa: E402

pytestmark = pytest.mark.skipif(not MD.body_of(MD.symbol_of("820E")),
                                reason="vendor DEF files not found")


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def lang_in_memory(monkeypatch):
    monkeypatch.setattr(I18N, "set_lang", lambda c: I18N._state.__setitem__("lang", c))
    old = I18N._state["lang"]
    yield
    I18N._state["lang"] = old


def _nhan(w):
    return " ".join(lb.text() for lb in w.findChildren(QtWidgets.QLabel))


@pytest.mark.parametrize("code", ["820C", "820D", "820E", "820F", "8211"])
def test_panel_builds_with_all_charts(app, lang_in_memory, code):
    from ui.tag_doc_view import tag_doc_panel, ScenarioChart
    I18N._state["lang"] = I18N.EN
    g = tag_doc_panel(code)
    so_bd = sum(1 for s in TD.doc_for(code)["scenarios"] if s.get("chart"))
    charts = g.findChildren(ScenarioChart)
    assert len(charts) == so_bd >= 1
    assert all(c.sizeHint().height() > 60 for c in charts)
    text = _nhan(g)
    assert "could not be run" not in text
    assert TD.doc_for(code)["summary"]["en"][:40] in text


def test_chart_paints_without_error(app):
    from ui.tag_doc_view import ScenarioChart
    sc = next(s for s in TD.doc_for("8211")["scenarios"] if s["id"] == "bias_inch_reset")
    c = ScenarioChart(sc, TD.run_scenario("8211", sc))
    c.resize(800, c.sizeHint().height())
    img = c.grab()
    assert not img.isNull() and img.width() == 800


def _vung_cuon(d):
    """Vung cuon chung cua than cua so - phai co dung MOT cai."""
    sc = [w for w in d.findChildren(QtWidgets.QScrollArea) if w.parentWidget() is d]
    assert len(sc) == 1
    return sc[0]


def _thu_tu(d):
    """Ba o theo dung thu tu tu tren xuong trong vung cuon chung."""
    lay = _vung_cuon(d).widget().layout()
    return [lay.itemAt(i).widget() for i in range(lay.count())
            if lay.itemAt(i).widget() is not None]


def test_help_dialog_toggles_language(app, lang_in_memory):
    from ui.block_help_dialog import BlockHelpDialog
    I18N._state["lang"] = I18N.VI
    I18N.MISSING.clear()
    d = BlockHelpDialog("8211", "")
    assert d._w_book is not None                      # SV (AA208) co ban ve so tay
    assert _thu_tu(d) == [d._w_tag, d._w_diag, d._w_book, d._w_what]
    assert d._w_tag.title() == "Cách hoạt động (đọc từ logic gốc)"
    assert TD.doc_for("8211")["summary"]["vi"][:30] in _nhan(d._w_tag)
    nut = [b for b in d.findChildren(QtWidgets.QPushButton) if b.objectName() == "en"][0]
    nut.click()
    app.processEvents()
    assert d._w_tag.title() == "How it works (read from the vendor logic)"
    assert _thu_tu(d) == [d._w_tag, d._w_diag, d._w_book, d._w_what]   # dung lai dung cho cu
    assert TD.doc_for("8211")["summary"]["en"][:30] in _nhan(d._w_tag)
    assert not I18N.MISSING
    d.deleteLater()


@pytest.mark.parametrize("code", ["8204", "820E", "8211"])
def test_panels_share_one_scroll_and_none_is_cut(app, lang_in_memory, code):
    """Moi o phai hien HET noi dung trong mot vung cuon chung.

    Cai de hong: tra lai thanh cuon rieng cho tung o. Luc do o nao cung bi nhot trong
    mot khe hep, doc vai dong lai phai keo, va keo o nay thi o kia teo lai."""
    from ui.block_help_dialog import BlockHelpDialog
    I18N._state["lang"] = I18N.EN
    d = BlockHelpDialog(code, "")
    d.resize(1280, 860)
    d.show()
    app.processEvents()
    than = _vung_cuon(d).widget()
    cho = [d._w_tag, d._w_diag, d._w_what]
    if d._w_book is not None:
        cho.insert(2, d._w_book)          # ban ve so tay nam ngay duoi ban ve tu sinh
    assert _thu_tu(d) == cho
    for o in cho:
        # do theo BE RONG THAT, khong dung sizeHint: chu tu xuong dong nen cao bao nhieu
        # con tuy rong bao nhieu, sizeHint tinh o mot be rong khac han
        assert o.height() >= o.layout().heightForWidth(o.width()), o.title()
        # o nao con thanh cuon DOC rieng la lai nhot noi dung nhu cu
        assert not any(s.verticalScrollBar().isVisible()
                       for s in o.findChildren(QtWidgets.QScrollArea)), o.title()
    for o in ([d._w_diag] if d._w_book is None else [d._w_diag, d._w_book]):
        ve = o.findChildren(QtWidgets.QScrollArea)[0]
        assert ve.viewport().height() >= ve.widget().minimumHeight(), o.title()
    assert than.height() > 1500          # cac o cong lai, cuon chung mot lan
    assert not _vung_cuon(d).horizontalScrollBar().isVisible()
    d.close()
    d.deleteLater()


def test_ordinary_block_has_no_station_panel(app, lang_in_memory):
    from ui.block_help_dialog import BlockHelpDialog
    I18N._state["lang"] = I18N.EN
    d = BlockHelpDialog("4011", "")
    assert d._w_tag is None
    d.deleteLater()
