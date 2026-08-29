# -*- coding: utf-8 -*-
"""Luong nen goi AI cho o tim kiem.

Phai la luong RIENG: mot luot hoi model qua HTTP mat vai giay den vai chuc giay (do
that: 7,8s voi model nhanh, 98-118s voi model cham), goi thang tren luong giao dien
la dong bang ca cua so - nguoi dung tuong app treo va tat di.
"""
from PySide6.QtCore import QThread, Signal

from core import ai_tu_khoa as AK


class GoiYWorker(QThread):
    """Hoi AI xem cau nay con tu khoa nao khac. Phat (them, ghi_chu) khi xong.

    Khong bao gio nem ngoai le ra ngoai: tim kiem van phai chay duoc bang tu dien tinh
    khi mat mang, sai API key hay het han muc - loi chi la mot dong ghi chu."""

    xong = Signal(dict, str)

    def __init__(self, q, provider="", parent=None):
        super().__init__(parent)
        self.q = q
        self.provider = provider

    def run(self):
        try:
            them, ghi = AK.goi_y(self.q, provider=self.provider)
        except Exception as e:
            them, ghi = {}, "Khong goi duoc AI - %s: %s" % (type(e).__name__, e)
        self.xong.emit(them, ghi)
