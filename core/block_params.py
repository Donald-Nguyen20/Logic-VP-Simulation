# -*- coding: utf-8 -*-
"""Tham so CAI DAT cua tung khoi tren ban ve.

Nguon du lieu:
  - Gia tri THAT cua tung khoi cu the : bang CAD_BLOCK_PARAM trong file .db du an
    (BLOCK_ID, PARAMNO, PARAMVALUE)
  - Kieu / mac dinh / gioi han theo LOAI khoi : DEF/SR21E/macro_param.csv
    (macrocode, so_tham_so, kind[1=chu,0=so], tuning, mac_dinh, max, min)
  - Ten tham so (MSR, MFR, TRC, ULD, LLD...) : core/macro_analog.json (cho cac tram
    da co mo hinh) - ghep theo thu tu cac tham so KIEU SO.

Luu y ve danh so: trong than lenh DEF (TAG_MCR.DEF) tham so ghi la PRM_n, ung voi
PARAMNO = n + 1. Vi du 820E: PRM_6=MSR -> paramno 7, PRM_10=LLD -> paramno 11.
"""
from __future__ import annotations
import os
import csv
import json

_META = None
_NAMES = {}


def _def_root():
    """Thu muc DEF/SR21E cua T-Designer (chua macro_param.csv)."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for base in (os.path.join(root, "DEF", "SR21E"),
                 os.path.join(root, "T_Designer", "DEF", "SR21E")):
        if os.path.exists(os.path.join(base, "macro_param.csv")):
            return base
    return None


def param_meta():
    """{macrocode: {paramno(int): {'kind','default','max','min'}}} tu macro_param.csv."""
    global _META
    if _META is not None:
        return _META
    _META = {}
    base = _def_root()
    if not base:
        return _META
    try:
        for r in csv.reader(open(os.path.join(base, "macro_param.csv"),
                                 encoding="latin-1", errors="ignore")):
            if not r or len(r) < 5 or r[0].startswith(";"):
                continue
            code = r[0].strip().upper()
            try:
                pno = int(r[1])
            except (ValueError, IndexError):
                continue
            _META.setdefault(code, {})[pno] = {
                "kind": (r[2].strip() if len(r) > 2 else "0"),      # '1'=chu, '0'=so
                "default": (r[4].strip() if len(r) > 4 else ""),
                "max": (r[5].strip() if len(r) > 5 else ""),
                "min": (r[6].strip() if len(r) > 6 else ""),
            }
    except Exception:
        pass
    return _META


def param_names(code):
    """{paramno: ten} - ghep ten tham so tu macro_analog.json theo thu tu tham so KIEU SO.
    Rong neu khoi chua co mo hinh ten."""
    code = (code or "").upper()
    if code in _NAMES:
        return _NAMES[code]
    out = {}
    try:
        p = os.path.join(os.path.dirname(__file__), "macro_analog.json")
        spec = json.load(open(p, encoding="utf-8")).get(code, {})
        names = list(spec.get("params", {}).keys())
        nums = sorted(n for n, m in param_meta().get(code, {}).items() if m.get("kind") == "0")
        for i, nm in enumerate(names):
            if i < len(nums):
                out[nums[i]] = nm
    except Exception:
        pass
    _NAMES[code] = out
    return out


def read_block_params(db_path, bid):
    """{paramno(str): gia_tri(str)} cua 1 khoi cu the tren ban ve."""
    if not (db_path and bid is not None):
        return {}
    try:
        import core.dbreader as D
        c = D.connect(db_path).cursor()
        return {str(pno): pv for pno, pv in c.execute(
            "SELECT PARAMNO,PARAMVALUE FROM CAD_BLOCK_PARAM WHERE BLOCK_ID=? ORDER BY PARAMNO",
            (bid,))}
    except Exception:
        return {}


def block_pin_rows(db_path, bid, code):
    """Danh sach chan cua khoi kem TIN HIEU NGOAI dang noi vao:
    [{no, name, side, net, label}] - net/label lay tu CAD_BLOCK_PIN.SIGNALID cua chinh
    khoi do, phan giai ten qua sheet_render._res."""
    rows = []
    if not (db_path and bid is not None):
        return rows
    try:
        import core.dbreader as D
        import core.sheet_render as SR
    except Exception:
        return rows
    # ten + phia cua tung chan theo LOAI khoi (macro_pins.json)
    names = {}
    try:
        p = os.path.join(os.path.dirname(__file__), "macro_pins.json")
        raw = json.load(open(p, encoding="utf-8"))
        for _sym, v in raw.items():
            if str(v.get("macrocode", "")).upper() == (code or "").upper():
                for k, pin in v.get("pins", {}).items():
                    names[str(k)] = (pin.get("name") or "", pin.get("side", "in"))
                break
    except Exception:
        pass
    try:
        c = D.connect(db_path).cursor()
        R = D._resolvers(db_path)
        srow = c.execute("SELECT ID FROM CAD_BLOCK WHERE BLOCK_ID=? LIMIT 1", (bid,)).fetchone()
        sheet_id = srow[0] if srow else None
        for pno, sig in c.execute(
                "SELECT PINNO,SIGNALID FROM CAD_BLOCK_PIN WHERE BLOCK_ID=? ORDER BY PINNO", (bid,)):
            sig = D._clean(sig)
            label = ""
            if sig and sheet_id is not None:
                label, _ref = SR._res(R, sheet_id, sig)
            nm, side = names.get(str(pno), ("", "in"))
            rows.append({"no": pno, "name": nm, "side": side, "net": sig, "label": label})
    except Exception:
        pass
    return rows


def block_param_rows(db_path, bid, code):
    """Danh sach dong de hien trong bang: [{no, name, value, kind, default, min, max}].
    Gop tham so co trong DB va tham so dinh nghia theo loai khoi (ke ca chua dat)."""
    vals = read_block_params(db_path, bid)
    meta = param_meta().get((code or "").upper(), {})
    names = param_names(code)
    nums = sorted({int(k) for k in vals} | set(meta.keys()))
    rows = []
    for n in nums:
        m = meta.get(n, {})
        rows.append({
            "no": n,
            "name": names.get(n, ""),
            "value": vals.get(str(n), m.get("default", "")),
            "kind": m.get("kind", "0"),
            "default": m.get("default", ""),
            "min": m.get("min", ""),
            "max": m.get("max", ""),
        })
    return rows
