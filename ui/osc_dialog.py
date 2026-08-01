# -*- coding: utf-8 -*-
"""Dialog cau hinh DAO DONG cho 1 diem ANALOG dang la dau vao mo phong (chuot phai
tren tin hieu -> 'Dat dao dong...'). Chi thuc su BAT/DUNG dao dong khi nguoi dung
bam nut ro rang (khong tu chay theo checkbox/o nhap khi con dang go so)."""
from __future__ import annotations
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
                               QDoubleSpinBox, QCheckBox, QPushButton, QLabel)


class OscillationDialog(QDialog):
    """cfg (neu co, dang dao dong san): {"mode","lo","hi","period","rate",...}
    Sau khi exec(): doc dlg.result_cfg (dict = muon BAT voi cau hinh nay, None = khong doi)
    va dlg.stop_requested (True = muon DUNG dao dong dang chay)."""

    def __init__(self, net, linename, cfg=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dao dong: %s" % (linename or net))
        self.resize(360, 280)
        self.result_cfg = None
        self.stop_requested = False

        lay = QVBoxLayout(self)
        hdr = QLabel("Dao dong gia tri cho tin hieu:\n%s" % (linename or net))
        hdr.setStyleSheet("font-weight:600;")
        lay.addWidget(hdr)
        if cfg:
            st = QLabel("(dang BAT dao dong)")
            st.setStyleSheet("color:#15803D;")
            lay.addWidget(st)

        form = QFormLayout()
        self.sp_lo = QDoubleSpinBox(); self.sp_lo.setRange(-1e9, 1e9); self.sp_lo.setDecimals(3)
        self.sp_hi = QDoubleSpinBox(); self.sp_hi.setRange(-1e9, 1e9); self.sp_hi.setDecimals(3)
        form.addRow("Min:", self.sp_lo)
        form.addRow("Max:", self.sp_hi)
        lay.addLayout(form)

        # 2 checkbox nhung LOAI TRU NHAU (tick 1 cai se tu bo cai kia)
        self.ck_rand = QCheckBox("Ngau nhien (di bo ngau nhien trong khoang Min-Max)")
        self.ck_period = QCheckBox("Theo chu ky (song hinh sin, deu dan)")
        self.ck_rand.toggled.connect(lambda on: on and self.ck_period.setChecked(False))
        self.ck_period.toggled.connect(lambda on: on and self.ck_rand.setChecked(False))
        lay.addWidget(self.ck_rand)
        lay.addWidget(self.ck_period)

        form2 = QFormLayout()
        self.sp_period = QDoubleSpinBox(); self.sp_period.setRange(1.0, 3600.0)
        self.sp_period.setDecimals(1); self.sp_period.setSuffix(" s"); self.sp_period.setValue(10.0)
        self.sp_rate = QDoubleSpinBox(); self.sp_rate.setRange(0.2, 60.0)
        self.sp_rate.setDecimals(1); self.sp_rate.setSuffix(" s"); self.sp_rate.setValue(0.5)
        form2.addRow("Chu ky 1 vong (khi chon 'Theo chu ky'):", self.sp_period)
        form2.addRow("Toc do cap nhat gia tri:", self.sp_rate)
        lay.addLayout(form2)

        if cfg:
            self.sp_lo.setValue(cfg.get("lo", 0.0))
            self.sp_hi.setValue(cfg.get("hi", 100.0))
            self.sp_period.setValue(cfg.get("period", 10.0))
            self.sp_rate.setValue(cfg.get("rate", 0.5))
            if cfg.get("mode") == "period":
                self.ck_period.setChecked(True)
            else:
                self.ck_rand.setChecked(True)
        else:
            self.sp_lo.setValue(0.0); self.sp_hi.setValue(100.0)
            self.ck_rand.setChecked(True)

        lay.addStretch(1)
        bar = QHBoxLayout()
        b_start = QPushButton("▶ Bắt đầu dao động")
        b_stop = QPushButton("■ Dừng dao động")
        b_stop.setEnabled(cfg is not None)
        b_close = QPushButton("Đóng")
        bar.addWidget(b_start); bar.addWidget(b_stop); bar.addStretch(1); bar.addWidget(b_close)
        lay.addLayout(bar)

        def _start():
            lo, hi = self.sp_lo.value(), self.sp_hi.value()
            if hi <= lo:
                hi = lo + 1.0
                self.sp_hi.setValue(hi)
            self.result_cfg = {
                "mode": "period" if self.ck_period.isChecked() else "random",
                "lo": lo, "hi": hi,
                "period": self.sp_period.value(),
                "rate": self.sp_rate.value(),
            }
            self.accept()

        def _stop():
            self.stop_requested = True
            self.accept()

        b_start.clicked.connect(_start)
        b_stop.clicked.connect(_stop)
        b_close.clicked.connect(self.reject)
