# -*- coding: utf-8 -*-
"""Nut chuyen ngon ngu dung chung cho cua so Help va F1: [ English | Tieng Viet ].

Bam sang ngon ngu kia -> luu lua chon (core/help_i18n.set_lang) roi goi ham dung lai chu
cua cua so. Nut nam NGOAI phan duoc dung lai nen trang thai bam giu nguyen.
"""
from __future__ import annotations
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QButtonGroup

from core import help_i18n as I18N

_CSS = ("QPushButton{padding:4px 14px;border:1px solid #94A3B8;background:#F8FAFC;"
        "color:#334155;font-size:10pt}"
        "QPushButton:hover{background:#E2E8F0}"
        "QPushButton:checked{background:#1F4E79;border-color:#1F4E79;color:white;"
        "font-weight:bold}"
        "QPushButton#en{border-top-left-radius:5px;border-bottom-left-radius:5px;"
        "border-right:none}"
        "QPushButton#vi{border-top-right-radius:5px;border-bottom-right-radius:5px}")

# (ma, chu tren nut, goi y) - moi goi y viet bang chinh ngon ngu cua nut
_NUT = ((I18N.EN, "English", "Show this help in English"),
        (I18N.VI, "Tiếng Việt", "Hiện phần trợ giúp này bằng tiếng Việt"))


def lang_toggle(parent, on_change):
    """Cap nut bam loai tru nhau. on_change() chay SAU khi ngon ngu da doi."""
    box = QWidget(parent)
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    group = QButtonGroup(box)
    group.setExclusive(True)
    for code, text, tip in _NUT:
        b = QPushButton(text, box)
        b.setObjectName(code)
        b.setCheckable(True)
        b.setChecked(I18N.lang() == code)
        b.setToolTip(tip)
        b.clicked.connect(lambda _checked=False, c=code: _chon(c, on_change))
        group.addButton(b)
        row.addWidget(b)
    box.setStyleSheet(_CSS)
    return box


def _chon(code, on_change):
    if code == I18N.lang():
        return
    I18N.set_lang(code)
    on_change()
