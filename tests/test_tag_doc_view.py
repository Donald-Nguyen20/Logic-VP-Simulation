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


def test_help_dialog_toggles_language(app, lang_in_memory):
    from ui.block_help_dialog import BlockHelpDialog
    I18N._state["lang"] = I18N.VI
    I18N.MISSING.clear()
    d = BlockHelpDialog("8211", "")
    assert isinstance(d._w_tag.parentWidget(), QtWidgets.QSplitter)
    assert d._w_tag.title() == "Cách hoạt động (đọc từ logic gốc)"
    assert TD.doc_for("8211")["summary"]["vi"][:30] in _nhan(d._w_tag)
    nut = [b for b in d.findChildren(QtWidgets.QPushButton) if b.objectName() == "en"][0]
    nut.click()
    app.processEvents()
    assert d._w_tag.title() == "How it works (read from the vendor logic)"
    assert isinstance(d._w_tag.parentWidget(), QtWidgets.QSplitter)
    assert TD.doc_for("8211")["summary"]["en"][:30] in _nhan(d._w_tag)
    assert not I18N.MISSING
    d.deleteLater()


def test_ordinary_block_has_no_station_panel(app, lang_in_memory):
    from ui.block_help_dialog import BlockHelpDialog
    I18N._state["lang"] = I18N.EN
    d = BlockHelpDialog("4011", "")
    assert d._w_tag is None
    d.deleteLater()
