# -*- coding: utf-8 -*-
"""Cho dat cac file do app tu sinh: cau hinh AI, danh sach DB da mo, cache tu khoa.

Tat ca nam trong thu muc `data` CANH APP. Truoc day moi file mot noi trong thu muc
nha (~/.tdesigner_*.json) - an, kho sao luu, mang app sang may khac la mat sach, va
nguoi dung khong he biet chung ton tai de ma xoa.

CANH BAO cho nguoi sua tiep: thu muc nay chua API KEY. `.gitignore` co dong `data/`
va do chinh la thu chan `git add -A` day key len GitHub. Dung bo dong do, va dung
chuyen file cau hinh ra ngoai thu muc nay.

Neu thu muc app khong ghi duoc - ban .exe cai vao Program Files, hay chay tu o dia
chi doc - thi lui ve thu muc nha. Khong ghi noi cau hinh la phien, chet app moi la
hong; ly do lui duoc giu trong LY_DO_LUI de hop thoai cai dat noi cho nguoi dung.
"""
import os
import shutil
import sys

_TEN_DATA = "data"

# Vi sao dang dung thu muc nha thay vi canh app. Rong = dang dung canh app nhu y muon.
LY_DO_LUI = ""

_da_tim = None


def thu_muc_app():
    """Thu muc chua app. Ban dong goi thi la cho dat .exe, chay tu ma nguon thi la
    goc kho (thu muc cha cua core/)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ghi_duoc(d):
    """Thu tao va ghi that mot file. Chi kiem tra ton tai thu muc la khong du: o dia
    chi doc va thu muc thieu quyen deu van bao la 'co that'."""
    try:
        os.makedirs(d, exist_ok=True)
        thu = os.path.join(d, ".ghi_thu")
        with open(thu, "w") as f:
            f.write("x")
        os.remove(thu)
        return ""
    except Exception as e:
        return "%s: %s" % (type(e).__name__, e)


def thu_muc_du_lieu():
    """Thu muc dang dung de ghi. Tinh mot lan roi nho, vi moi lan goi deu cham o dia."""
    global _da_tim, LY_DO_LUI
    if _da_tim is not None:
        return _da_tim
    d = os.path.join(thu_muc_app(), _TEN_DATA)
    loi = _ghi_duoc(d)
    if loi:
        LY_DO_LUI = "Khong ghi duoc vao %s (%s) - dung tam thu muc nha." % (d, loi)
        d = os.path.expanduser("~")
    _da_tim = d
    return d


def duong(ten):
    """Duong dan day du cua mot file du lieu trong thu muc dang dung."""
    return os.path.join(thu_muc_du_lieu(), ten)


def duong_json(ten, ten_cu_o_nha=""):
    """Nhu duong() nhung chuyen not ban cu tu thu muc nha sang, neu ben moi chua co.

    CHEP chu khong CHUYEN: ban cu nam nguyen tai cho. Neu nguoi dung mo lai ban app
    doi truoc thi van con cau hinh ma dung, va mot lan doi cho khong the lam mat API
    key ho da nhap. Ho tu xoa ban cu khi thay yen tam."""
    moi = duong(ten)
    if ten_cu_o_nha and not os.path.exists(moi):
        cu = os.path.join(os.path.expanduser("~"), ten_cu_o_nha)
        if os.path.exists(cu) and os.path.abspath(cu) != os.path.abspath(moi):
            try:
                shutil.copy2(cu, moi)
            except Exception:
                # Chep khong duoc thi coi nhu chua co cau hinh: ben goi tu sinh ban
                # mac dinh. Bao loi o day chi lam app khong mo len duoc.
                pass
    return moi
