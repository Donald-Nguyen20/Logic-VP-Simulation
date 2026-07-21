# -*- coding: utf-8 -*-
"""Hop thoai 'Explain (AI)': gom ngu canh 1 tin hieu, goi Claude (Agent SDK)
trong LUONG NEN va hien loi giai thich. Dung dang nhap Claude Code co san tren may
(khong can dan token)."""
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
                               QPushButton, QPlainTextEdit, QMessageBox, QLineEdit)
from PySide6.QtCore import Qt, QThread, Signal

from core import ai_explain as AE
from core import ai_client as AC


class _Worker(QThread):
    done = Signal(str)

    def __init__(self, prompt, model=None):
        super().__init__()
        self.prompt = prompt; self.model = model

    def run(self):
        self.done.emit(AC.ask(self.prompt, self.model))


class AIExplainDialog(QDialog):
    def __init__(self, db, sheet, net, cpu_paths=None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint
                            | Qt.WindowType.WindowMaximizeButtonHint)
        self.resize(720, 640)
        try:
            name, ctx = AE.build_signal_context(db, sheet, net, cpu_paths=cpu_paths)
        except Exception as e:
            name, ctx = (net, "(context error: %s)" % e)
        self._name = name; self._ctx = ctx
        self.setWindowTitle("Explain (AI): %s" % name)
        lay = QVBoxLayout(self)
        hdr = QLabel(name); hdr.setStyleSheet("font-size:15px;font-weight:600;")
        lay.addWidget(hdr)

        self.status_lbl = QLabel(""); self.status_lbl.setStyleSheet("font-size:12px;color:#64748B;")
        lay.addWidget(self.status_lbl)

        self.answer = QTextEdit(); self.answer.setReadOnly(True)
        lay.addWidget(self.answer, 3)

        lay.addWidget(QLabel("Context sent to AI (facts from the database):"))
        self.ctxview = QPlainTextEdit(); self.ctxview.setReadOnly(True)
        self.ctxview.setPlainText(ctx); self.ctxview.setMaximumHeight(150)
        lay.addWidget(self.ctxview, 1)

        self._lang = "en"
        bar = QHBoxLayout()
        self.btn_login = QPushButton("Login to Claude"); self.btn_login.clicked.connect(self._login)
        self.btn_lang = QPushButton("Tiếng Việt"); self.btn_lang.clicked.connect(self._toggle_lang)
        self.btn_lang.setToolTip("Chuyen ngon ngu tra loi (English / Tieng Viet)")
        self.btn_ask = QPushButton("Ask Claude"); self.btn_ask.clicked.connect(self._run)
        bar.addWidget(self.btn_login); bar.addStretch(1)
        bar.addWidget(self.btn_lang); bar.addWidget(self.btn_ask)
        lay.addLayout(bar)

        self._refresh()

    def _refresh(self):
        err = AC.sdk_error(); sdk = err is None; cli = AC.cli_available()
        s = "SDK: " + ("OK" if sdk else ("LOI - %s" % err))
        s += "   |   CLI: " + ("OK" if cli else "chua co")
        self.status_lbl.setText(s)
        self.btn_ask.setEnabled(sdk)
        if sdk:
            self.answer.setPlaceholderText("Bam 'Ask Claude'. Neu chua dang nhap, bam 'Login to Claude' truoc.")
        else:
            self.answer.setText(AC.setup_hint())

    def _login(self):
        ok, msg = AC.start_login()
        QMessageBox.information(self, "Login to Claude", msg)

    def _toggle_lang(self):
        self._lang = "vi" if self._lang == "en" else "en"
        self.btn_lang.setText("English" if self._lang == "vi" else "Tiếng Việt")
        # neu da co cau tra loi thi hoi lai bang ngon ngu moi
        if AC.available() and self.btn_ask.isEnabled():
            self._run()

    def _run(self):
        self.btn_ask.setEnabled(False)
        self.answer.setText("Asking Claude... (lan dau co the mat vai giay)")
        prompt = AE.build_prompt(self._name, self._ctx, lang=self._lang)
        self._w = _Worker(prompt)
        self._w.done.connect(self._show)
        self._w.start()

    def _show(self, text):
        self.answer.setText(text or "(empty response)")
        self.btn_ask.setEnabled(True)
