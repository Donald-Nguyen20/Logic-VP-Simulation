# -*- coding: utf-8 -*-
"""Kho cau tra loi cua Explain: hoi mot lan, nhung lan sau doc lai tu dia.

Khoa la BAM CUA CHINH CAU HOI - prompt da gom san toan bo ngu canh doc tu db. Nho
vay sua logic tren ban ve thi ngu canh doi, bam doi theo va app tu hoi lai; khong bao
gio dua cau tra loi cu cho mot ban ve da khac.

Prompt khong chua duong dan, ten may hay ngay thang, nen cung mot db o may khac se bam
ra dung khoa do: chep file cache sang may khac la dung duoc ngay.

File nam CANH FILE DB ("01 UCS.db" -> "01 UCS.ai.json") de di theo thu muc du an khi
chep. Thu muc db chi doc (dia mang, USB khoa) thi lui ve thu muc data canh app; luc doc
thi tim ca hai cho, nen chep file vao cho nao cung nhan ra.
"""
import hashlib
import json
import os
import time

from core import duong_dan as DD

PHIEN_BAN = 1        # doi cach dung prompt thi tang so nay: cache cu tu bi bo qua
TOI_DA = 1000        # so cau giu trong mot file; vuot thi bo cau cu nhat
_DUOI = ".ai.json"


def khoa(prompt, lang="en", provider="", model=""):
    """Bam cau hoi thanh khoa. Doi model hay doi ngon ngu tuc la mot cau tra loi khac."""
    s = "|".join([str(PHIEN_BAN), lang or "", provider or "", model or "", prompt or ""])
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:32]


def cac_cho(db):
    """Cac cho co the chua cache cua db nay, cho tot nhat dung truoc."""
    canh_db = os.path.splitext(db)[0] + _DUOI
    return [canh_db, os.path.join(DD.duong("ai_cache"), os.path.basename(canh_db))]


def tim(db, k):
    """Cau tra loi da luu (dict) hoac None."""
    for p in cac_cho(db):
        m = _doc(p).get("entries", {}).get(k)
        if m and m.get("answer"):
            return m
    return None


def luu(db, k, answer, **thong_tin):
    """Ghi lai mot cau tra loi. Tra ve duong dan da ghi, "" neu khong cho nao ghi duoc."""
    m = dict(thong_tin)
    m["answer"] = answer
    m["at"] = time.strftime("%Y-%m-%d %H:%M")
    for p in cac_cho(db):
        d = _doc(p)
        e = d.setdefault("entries", {})
        e.pop(k, None)             # ghi lai cau cu -> cho no ve cuoi hang
        e[k] = m
        _bo_cu(e)
        d["version"] = PHIEN_BAN
        if _ghi(p, d):
            return p
    return ""


def dem(db):
    """So cau da luu, gop ca hai cho - de noi cho nguoi dung biet kho dang co gi."""
    ra = set()
    for p in cac_cho(db):
        ra |= set(_doc(p).get("entries", {}))
    return len(ra)


def _doc(p):
    """Chua co file, file hong, khong doc duoc: deu coi nhu kho rong. Mot file cache
    hong khong duoc phep lam hong duong hoi - cung lam la hoi lai AI mot lan."""
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and isinstance(d.get("entries"), dict) else {}
    except Exception:
        return {}


def _bo_cu(e):
    """Day kho thi bo cau vao truoc nhat. Thu tu trong file JSON chinh la thu tu ghi,
    nen khong can nhin moc thoi gian - va moc thoi gian cung khong tach duoc cac cau
    ghi trong cung mot phut."""
    for k in list(e)[:max(0, len(e) - TOI_DA)]:
        e.pop(k, None)


def _ghi(p, d):
    """Ghi ra file tam roi doi ten: dang ghi ma mat dien thi ban cu van con nguyen,
    khong bien thanh file JSON do dang lam mat sach ca kho."""
    try:
        thu = os.path.dirname(p)
        if thu:
            os.makedirs(thu, exist_ok=True)
        tam = p + ".tmp"
        with open(tam, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tam, p)
        return True
    except Exception:
        return False
