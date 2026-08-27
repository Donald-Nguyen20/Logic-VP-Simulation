# -*- coding: utf-8 -*-
"""Hop thoai 'Cai dat AI': chon nha cung cap, lay API key, chon model.

Ba nut lam nen cong dung cua hop thoai nay:
  - Lay API key       : mo dung trang cap key cua nha cung cap dang chon
  - Tai danh sach model: hoi thang nha cung cap xem HIEN GIO co model gi
  - Kiem tra          : goi that 1 cau, de biet key + model co chay khong

Vi sao khong ghi cung ten model: kiem tra hom nay thi 'gemini-2.0-flash' va
'meta-llama/llama-3.3-70b-instruct:free' deu da bi bo. Ten model doi lien tuc, ghi
cung chi la hen gio cho mot loi 404 xay ra vao luc nguoi dung can dung nhat.

Moi viec cham (goi mang) deu chay o LUONG NEN: hop thoai bi dong bang 20-30 giay
thi nguoi dung tuong app treo.
"""
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QLabel, QComboBox, QLineEdit, QPushButton,
                               QCheckBox, QMessageBox, QDialogButtonBox, QWidget)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from core import llm_config as LC
from core import llm_client as LClient
from core import llm_providers as PROV


class _Net(QThread):
    """1 viec mang chay nen. ok=(True, ket_qua) hoac (False, loi)."""
    done = Signal(bool, object)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(True, self.fn())
        except Exception as e:
            self.done.emit(False, "%s: %s" % (type(e).__name__, e))


class LLMSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cai dat AI - nha cung cap va model")
        self.resize(560, 300)
        self.cfg = LC.load_llm_config()
        self._job = None

        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cb_prov = QComboBox()
        for k, v in LClient.PROVIDERS:
            self.cb_prov.addItem(v, k)
        i = self.cb_prov.findData(self.cfg.get("provider", "claude"))
        self.cb_prov.setCurrentIndex(max(0, i))
        self.cb_prov.currentIndexChanged.connect(self._on_provider)
        form.addRow("Nha cung cap:", self.cb_prov)

        # --- API key + nut lay key ---
        self.ed_key = QLineEdit()
        self.ed_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_key.setPlaceholderText("dan API key vao day")
        self.btn_get = QPushButton("Lay API key")
        self.btn_get.setToolTip("Mo trang cap API key cua nha cung cap dang chon")
        # Nut nay la ly do chinh de mo hop thoai -> to mau cho khoi lan giua cac nut xam
        self.btn_get.setStyleSheet(
            "QPushButton{background:#2563EB;color:#FFFFFF;border:none;border-radius:6px;"
            "padding:6px 14px;font-weight:600;}"
            "QPushButton:hover{background:#1D4ED8;}"
            "QPushButton:disabled{background:#CBD5E1;color:#F8FAFC;}")
        self.btn_get.clicked.connect(self._open_key_page)
        self.chk_show = QCheckBox("Hien")
        self.chk_show.toggled.connect(
            lambda on: self.ed_key.setEchoMode(QLineEdit.EchoMode.Normal if on
                                               else QLineEdit.EchoMode.Password))
        self.row_key = _row(self.ed_key, self.chk_show, self.btn_get)
        self.lbl_key = QLabel("API key:")
        form.addRow(self.lbl_key, self.row_key)

        # --- Ollama host (chi hien khi chon Ollama) ---
        self.ed_host = QLineEdit(self.cfg.get("ollama_host", "http://localhost:11434"))
        self.lbl_host = QLabel("Dia chi Ollama:")
        form.addRow(self.lbl_host, self.ed_host)

        # --- model + nut tai danh sach ---
        self.cb_model = QComboBox()
        self.cb_model.setEditable(True)        # cho go tay ten model moi ra
        self.cb_model.setMinimumWidth(260)
        self.btn_models = QPushButton("Tai danh sach model")
        self.btn_models.clicked.connect(self._load_models)
        self.lbl_model = QLabel("Model:")
        self.row_model = _row(self.cb_model, self.btn_models)
        form.addRow(self.lbl_model, self.row_model)

        lay.addLayout(form)

        self.chk_tools = QCheckBox(
            "Cho AI tu tra cuu them (chinh xac hon, cham hon)")
        self.chk_tools.setChecked(bool(self.cfg.get("use_tools", True)))
        self.chk_tools.setToolTip(
            "Ngu canh gui di co the con nhanh dieu kien bi cat. Bat thi AI tu goi\n"
            "get_source/block_function de doc tiep; tat thi tra loi nhanh nhung thieu.")
        lay.addWidget(self.chk_tools)

        self.lbl_note = QLabel("")
        self.lbl_note.setWordWrap(True)
        self.lbl_note.setStyleSheet("font-size:12px;color:#64748B;")
        lay.addWidget(self.lbl_note)

        bar = QHBoxLayout()
        self.btn_ping = QPushButton("Kiem tra")
        self.btn_ping.clicked.connect(self._ping)
        bar.addWidget(self.btn_ping)
        bar.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        bar.addWidget(bb)
        lay.addLayout(bar)

        self._on_provider()

    # ------------------------------------------------------------------ #
    def provider(self) -> str:
        return self.cb_prov.currentData() or "claude"

    def _on_provider(self):
        """Doi nha cung cap -> nap lai key/model DA LUU cua nha cung cap do."""
        p = self.provider()
        if p in LClient.NEEDS_KEY:
            self.ed_key.setText(self.cfg.get("%s_api_key" % p, ""))
        self.cb_model.setCurrentText(self.cfg.get("%s_model" % p, ""))
        self._sync()

    def _sync(self):
        """Chi bat/tat va viet ghi chu. KHONG dung toi noi dung nguoi dung dang go."""
        p = self.provider()
        need_key = p in LClient.NEEDS_KEY
        # Giau han hang API key khi chon Claude la sai lam: nguoi dung mo hop thoai
        # DE TIM nut 'Lay API key', thay hop thoai trong ron thi khong biet phai lam gi.
        # Vi vay luon HIEN, chi lam mo di va noi ro vi sao.
        self.ed_key.setEnabled(need_key)
        self.chk_show.setEnabled(need_key)
        self.btn_get.setEnabled(p in LClient.API_PAGES)
        self.ed_key.setPlaceholderText(
            "dan API key vao day" if need_key else "%s khong dung API key" % LClient.short(p))
        for w in (self.lbl_host, self.ed_host):
            w.setVisible(p == "ollama")
        has_model = p != "claude"
        self.cb_model.setEnabled(has_model)
        self.btn_models.setEnabled(has_model)
        self.btn_ping.setEnabled(has_model)
        self.chk_tools.setEnabled(has_model)

        self.btn_get.setText("Lay API key (%s)" % p if p in LClient.API_PAGES
                             else "Lay API key")

        # Moi nha cung cap co mot cau gioi thieu rieng trong llm_providers.py
        # (mien phi hay tra phi, lay key o dau) - dua len dau ghi chu.
        head = LClient.note(p)
        if p == "claude":
            self.lbl_note.setText(
                head + " Vi vay o key dang mo di.\n"
                "Muon dung API key: doi o 'Nha cung cap' o tren sang mot nha khac "
                "(co 12 nha, %d nha dung duoc mien phi), roi bam nut xanh 'Lay API key'."
                % LClient.free_count())
        else:
            env = PROV.info(p).get("env") or ""
            if need_key and not self.ed_key.text().strip():
                msg = (head + "\nBuoc 1: bam nut xanh 'Lay API key' -> trang web mo ra, "
                       "tao key, chep ve dan vao o ben canh.\nBuoc 2: bam 'Tai danh sach "
                       "model' roi chon 1 model.  Buoc 3: bam 'Kiem tra'.")
            else:
                msg = (head + "\nBam 'Tai danh sach model' de lay ten model dang song "
                       "(ten model doi luon).")
            if env:
                msg += ("\nKhong muon luu key xuong dia: dat bien moi truong %s "
                        "- app se uu tien dung bien do." % env)
            self.lbl_note.setText(msg)

    def _open_key_page(self):
        url = LClient.API_PAGES.get(self.provider())
        if not url:
            return
        QDesktopServices.openUrl(QUrl(url))
        self.lbl_note.setText(
            "Da mo trinh duyet: %s\nTao key roi dan vao o 'API key' va bam Save." % url)

    # ------------------------------------------------------------------ #
    def _busy(self, on, what=""):
        for w in (self.btn_models, self.btn_ping, self.cb_prov):
            w.setEnabled(not on)
        if not on:
            self._sync()                 # tra lai trang thai nut, KHONG dung toi o key
        if on:
            self.lbl_note.setText("Dang %s..." % what)

    def _start(self, fn, what, cb):
        if self._job is not None and self._job.isRunning():
            return
        self._busy(True, what)
        self._job = _Net(fn)
        self._job.done.connect(lambda ok, res: (self._busy(False), cb(ok, res)))
        self._job.start()

    def _load_models(self):
        p = self.provider()
        key = self.ed_key.text().strip() or LC.api_key(p, self.cfg)
        host = self.ed_host.text().strip()
        self._start(lambda: LClient.list_models(p, key, host),
                    "hoi danh sach model", self._got_models)

    def _got_models(self, ok, res):
        if not ok:
            self.lbl_note.setText("Khong lay duoc danh sach model - %s" % res)
            return
        cur = self.cb_model.currentText().strip()
        self.cb_model.clear()
        self.cb_model.addItems(res)
        # Danh sach da xep ban moi nhat len dau (core/llm_client._xep_model), nen
        # dong 0 luon la thu chon vao la chay duoc.
        if cur and cur in res:
            self.cb_model.setCurrentText(cur)
        elif res:
            self.cb_model.setCurrentIndex(0)
        note = "Co %d model dung duoc. Chon 1 cai roi bam 'Kiem tra'." % len(res)
        if res and self.cb_model.currentText().strip() != res[0]:
            # Nha cung cap khai tu ban cu lien tuc - nhac ten ban moi nhat de nguoi
            # van hanh khong om mai mot ten cu roi mot hom bi tra ve 404.
            note += "  Moi nhat la '%s'." % res[0]
        self.lbl_note.setText(note)

    def _ping(self):
        p = self.provider()
        key = self.ed_key.text().strip() or LC.api_key(p, self.cfg)
        model = self.cb_model.currentText().strip()
        host = self.ed_host.text().strip()
        if p != "ollama" and not key:
            QMessageBox.warning(self, "Thieu API key",
                                "Bam 'Lay API key' de tao key, roi dan vao o ben canh.")
            return
        if not model:
            QMessageBox.warning(self, "Thieu model",
                                "Bam 'Tai danh sach model' roi chon 1 model.")
            return
        self._start(lambda: LClient.ping(p, key, model, host), "kiem tra", self._got_ping)

    def _got_ping(self, ok, res):
        if ok:
            # Cau tra ve co the kem canh bao ve cong cu - dung cat mat.
            self.lbl_note.setText("OK - model tra loi: %s" % str(res)[:300])
        else:
            self.lbl_note.setText("Goi khong duoc - %s" % res)

    # ------------------------------------------------------------------ #
    def _save(self):
        p = self.provider()
        cfg = dict(self.cfg)
        cfg["provider"] = p
        cfg["use_tools"] = self.chk_tools.isChecked()
        if p in LClient.NEEDS_KEY:
            cfg["%s_api_key" % p] = self.ed_key.text().strip()
        if p == "ollama":
            cfg["ollama_host"] = self.ed_host.text().strip() or "http://localhost:11434"
        if p != "claude":
            cfg["%s_model" % p] = self.cb_model.currentText().strip()
        try:
            LC.save_llm_config(cfg)
        except Exception as e:
            QMessageBox.critical(self, "Khong luu duoc", str(e))
            return
        self.cfg = cfg
        self.accept()

    def closeEvent(self, ev):
        if self._job is not None and self._job.isRunning():
            self._job.wait(3000)      # tranh QThread bi huy khi con dang chay
        super().closeEvent(ev)


def _row(*widgets) -> QWidget:
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    for x in widgets:
        h.addWidget(x)
    return w
