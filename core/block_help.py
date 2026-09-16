# -*- coding: utf-8 -*-
"""Mo ta CHUC NANG cua mot LOAI khoi, phuc vu cua so Help (chuot phai -> Help).

Chi tra ve du lieu thuan (dict/chuoi), khong dinh Qt, de con dung lai duoc cho cho khac
(xuat bao cao, AI, kiem thu).

Nguon du lieu, theo thu tu tin cay:
  1. core/macro_catalog.json  - ten CHINH THUC tieng Anh + nhom + so chan/so tham so.
     Phu 299/300 ma dang dung trong 21 file .db du an (chi thieu E0B1 = dau cuc noi day).
  2. core/logic_sem.json / core/analog_sem.json - phep toan ("op") va ho timer ("tmr")
     ma bo mo phong dang thuc su chay. Nho vay chu giai thich va hanh vi mo phong
     KHONG the lech nhau.
  3. DEF cua hang (TAG_MCR.DEF) - than logic noi, dung o giai doan sau de VE lai khoi.
  4. core/manual_index.json - doan giai thich chep tu manual PDF (manual_note), hien
     them trong Help; la chu duy nhat cho cac khoi bo mo phong khong co op/tmr.
  5. core/module_docs.json - khoi giao tiep card EHC (VPCL/FDCL/PLUL) khong co trong DEF
     lan manual: mo ta card chep tu DEHC Hardware Specification + trang EHC.pdf (module_note).

Chu hien ra man hinh viet bang TIENG ANH (chuoi goc); moi chuoi deu qua tr() cua
core/help_i18n.py nen khi nguoi dung chon tieng Viet se ra ban dich viet tay. Chu thich
trong code van la tieng Viet khong dau nhu phan con lai cua du an.
"""
from __future__ import annotations
import os
import json
import re

from .help_i18n import tr

_CAT = None          # {macrocode: dong trong macro_catalog.json}
_SEM = None          # {macrocode: dong trong logic_sem/analog_sem}
_MM = None           # {macrocode: explain} tu macro_manual.json (du phong)
_MOD = None          # {macrocode: mo ta card} tu module_docs.json

# Ten nhom trong macro_catalog.json dang song ngu; Help lay phan tieng Anh roi qua tr().
_CATEGORY_EN = {
    "Khac (Other)": "Other",
    "Toan hoc (Math)": "Math",
    "Logic": "Logic",
    "Timer/Counter": "Timer / Counter",
    "Du lieu (Data/Move)": "Data / Move",
    "Chon/Nut nhan (Selector/PB)": "Selector / Pushbutton",
    "Van/Dong co (Valve/Motor)": "Valve / Motor",
    "Canh bao (Alarm)": "Alarm",
    "Chuyen doi (Converter)": "Converter",
    "Vao/Ra (I/O)": "I/O",
    "Tuan tu (Sequence)": "Sequence",
}

# (tieu de ngan, cach hoat dong) theo phep toan ma bo mo phong dang chay.
_OP_EN = {
    "AND": ("Logic AND",
            "The output is 1 only while EVERY connected input is 1. A single input at 0 "
            "forces the output to 0."),
    "OR": ("Logic OR",
           "The output is 1 while AT LEAST ONE input is 1. It returns to 0 only when every "
           "input is 0."),
    "NOT": ("Logic NOT",
            "The output is the inverse of the input: 1 becomes 0, 0 becomes 1."),
    "XOR": ("Exclusive OR",
            "The output is 1 when the two inputs DIFFER, and 0 when they are the same."),
    "MAJ": ("Majority vote",
            "The output is 1 when more than half of the inputs are 1 - the usual "
            "2-out-of-3 voting used on trip logic."),
    "SR": ("Set / Reset latch",
           "SET drives the output to 1 and it STAYS at 1 after SET returns to 0. Only RESET "
           "clears it. When SET and RESET are both 1, the priority built into this "
           "particular block decides which one wins."),
    "SELECT": ("Signal selector",
               "Passes one of the analog inputs straight to the output; the switch input "
               "decides which one is passed."),
    "CMP": ("Comparator",
            "Compares the analog input against a setpoint and gives a 0/1 result. The dead "
            "band keeps the output from chattering while the input sits on the threshold."),
    "CONST": ("Constant / signal generator",
              "Feeds a fixed value taken from the block parameters. It does not depend on "
              "any input."),
    "FUNC": ("Function generator F(x)",
             "Maps the input through a piecewise-linear curve defined by the parameter "
             "table of this block."),
    "PASS": ("Pass-through",
             "Hands the input to the output unchanged. Used for wiring, data links and "
             "type converters."),
    "ADD": ("Addition", "Output = the sum of the inputs."),
    "SUB": ("Subtraction", "Output = the first input minus the other input."),
    "MUL": ("Multiplication", "Output = the product of the inputs."),
    "MULG": ("Multiplication with gain",
             "Output = the product of the inputs, then scaled by the gain parameter."),
    "DIV": ("Division", "Output = the first input divided by the other input."),
    "GAIN": ("Gain",
             "Output = the input multiplied by a fixed gain taken from the block parameters."),
    "ABS": ("Absolute value", "Output = the magnitude of the input; the sign is dropped."),
    "AVG": ("Average", "Output = the arithmetic mean of the connected inputs."),
    "MAX": ("High selector", "Output = the LARGEST of the inputs."),
    "MIN": ("Low selector", "Output = the SMALLEST of the inputs."),
    "MID": ("Median selector",
            "Output = the middle value of three inputs, so one failed transmitter is "
            "rejected."),
    "WSUM": ("Weighted sum",
             "Output = the sum of the inputs, each one scaled by its own coefficient."),
    "SIGNSUM": ("Signed sum",
                "Output = the sum of the inputs, each one taken with the sign configured "
                "on its pin."),
    "CLAMPHI": ("High limiter",
                "Passes the input through, but never lets it rise above the upper limit."),
    "CLAMPLO": ("Low limiter",
                "Passes the input through, but never lets it fall below the lower limit."),
    "CLAMPHI_P": ("High limiter (parameter)",
                  "Passes the input through, but never lets it rise above the upper limit "
                  "set in the block parameters."),
    "CLAMPLO_P": ("Low limiter (parameter)",
                  "Passes the input through, but never lets it fall below the lower limit "
                  "set in the block parameters."),
    "LIMIT_P": ("High / low limiter",
                "Keeps the output inside the upper and lower limits set in the block "
                "parameters."),
    "CMPHI_P": ("High comparator",
                "The output turns 1 when the input rises above the setpoint held in the "
                "block parameters."),
    "CMPLO_P": ("Low comparator",
                "The output turns 1 when the input falls below the setpoint held in the "
                "block parameters."),
}

# Ho timer - lay theo khoa "tmr" trong logic_sem.json, dung DUNG mo hinh ma
# core/sheet_dyn.py dang chay, de chu giai thich khong lech voi ket qua mo phong.
_TMR_EN = {
    "DI": ("On-delay timer (DI)",
           "The output turns ON only after the input has STAYED ON for the full delay time "
           "T. If the input drops before T is reached, the timer resets and nothing comes "
           "out. Once the input goes OFF, the output drops immediately."),
    "DIL": ("On-delay timer, long range (DIL)",
            "Same behaviour as DI, but the delay time is counted in MINUTES instead of "
            "seconds."),
    "DT": ("Off-delay timer (DT)",
           "The output follows the input ON straight away, but when the input goes OFF the "
           "output is HELD ON for the full time T before dropping. A new ON within that "
           "window restarts the hold."),
    "PO": ("One-shot pulse (PO / SS1)",
           "A rising edge on the input starts a pulse of fixed width T. The pulse runs to "
           "its full width even if the input drops in the middle of it."),
    "TDWO": ("One-shot pulse with wipe-out (TDWO / SS2)",
             "Same as PO, but the input going OFF CUTS the pulse immediately instead of "
             "letting it finish."),
    "PG": ("Square-wave generator (PG)",
           "While the input is ON, the output oscillates: ON for T, then OFF for the second "
           "time parameter, and repeats. Input OFF stops it."),
    "1SH1": ("One-scan shot on rising edge",
             "The output is ON for a SINGLE scan when the input goes from 0 to 1, then "
             "returns to 0 by itself."),
    "1SH2": ("One-scan shot on falling edge",
             "The output is ON for a SINGLE scan when the input goes from 1 to 0, then "
             "returns to 0 by itself."),
}

# Cach VE lai khoi cho de hieu. Giai doan 1 chi CHON va bao ten che do; ban ve that
# lam o cac giai doan sau.
MODE_TIMING = "timing"
MODE_GATES = "gates"
MODE_CURVE = "curve"
MODE_FBD = "fbd"
MODE_NONE = "none"

_MODE_EN = {
    MODE_TIMING: ("Timing diagram",
                  "Input / output waveforms on a time axis, with the delay time of THIS "
                  "block marked on it."),
    MODE_GATES: ("Internal gate diagram",
                 "The gates inside the block, redrawn from the vendor DEF body."),
    MODE_CURVE: ("Characteristic curve / value table",
                 "The input-to-output relation of the block, drawn as a curve or a table."),
    MODE_FBD: ("Internal function-block diagram",
               "The function blocks inside the macro - selectors, timers, limiters and "
               "arithmetic - redrawn from the vendor DEF body, every output pin on one "
               "picture."),
    # Khong duoc goi la "khoi noi day / giao tiep": nhom nay gom ca khoi tich phan, can
    # bac hai, bang tra... chi la app chua co mo hinh va khong doc duoc than DEF de ve.
    MODE_NONE: ("No internal diagram",
                "The app cannot redraw the inside of this block: it has no model of it and "
                "no vendor logic body (TAG_MCR.DEF) it can read."),
}

_GATE_OPS = {"AND", "OR", "NOT", "XOR", "MAJ", "SR", "SELECT"}


def _catalog():
    global _CAT
    if _CAT is not None:
        return _CAT
    _CAT = {}
    try:
        p = os.path.join(os.path.dirname(__file__), "macro_catalog.json")
        for m in json.load(open(p, encoding="utf-8")).get("macros", []):
            _CAT[str(m.get("code", "")).upper()] = m
    except Exception:
        pass
    return _CAT


def _sem():
    global _SEM
    if _SEM is not None:
        return _SEM
    _SEM = {}
    for fn in ("analog_sem.json", "logic_sem.json"):     # logic_sem uu tien, nap sau
        try:
            p = os.path.join(os.path.dirname(__file__), fn)
            for k, v in json.load(open(p, encoding="utf-8")).items():
                if isinstance(v, dict):
                    _SEM[str(k).upper()] = v
        except Exception:
            pass
    return _SEM


def draw_mode(sem):
    """Chon che do ve lai cho de hieu, tu ban ngu nghia cua khoi."""
    if not sem:
        return MODE_NONE
    if sem.get("tmr"):
        return MODE_TIMING
    op = sem.get("op")
    if op in _GATE_OPS:
        return MODE_GATES
    if op in _OP_EN and op != "PASS":
        return MODE_CURVE
    return MODE_NONE


def describe(code):
    """Mo ta 1 LOAI khoi -> dict. Khong doc file .db, khong phu thuoc khoi cu the.

    Khoa tra ve: code, symbol, short, title, category, obsolete, n_in, n_out, n_par,
    op, tmr, tunit, headline, how (theo ngon ngu Help dang chon), mode, mode_name, mode_note.
    """
    code = (code or "").upper()
    cat = _catalog().get(code) or {}
    sem = _sem().get(code) or {}
    tmr = sem.get("tmr")
    op = sem.get("op")

    if tmr and tmr in _TMR_EN:
        headline, how = _TMR_EN[tmr]
    elif op in _OP_EN:
        headline, how = _OP_EN[op]
    else:
        headline, how = "", ""
    headline, how = tr(headline), tr(how)

    # macro_catalog ghi "DI - Delay Initiation": bo ky hieu ve o dau, giu phan mo ta
    full = (cat.get("name") or "").strip()
    title = full.split(" - ", 1)[1].strip() if " - " in full else full

    mode = draw_mode(sem)
    if mode == MODE_NONE:
        # Khong co mo hinh ngu nghia nao khop, nhung than lenh trong DEF van co the doc
        # thanh so do khoi chuc nang (ho tram van hanh, cac khoi so hoc dai). Hoi sau
        # cung vi no phai doc file DEF; ket qua co nho lai trong block_fbd.
        try:
            from . import block_fbd
            if block_fbd.can_draw(code):
                mode = MODE_FBD
        except Exception:
            pass
    mode_name, mode_note = (tr(s) for s in _MODE_EN[mode])
    return {
        "code": code,
        "symbol": cat.get("id") or "",
        "short": cat.get("short") or "",
        "title": title,
        "category": tr(_CATEGORY_EN.get(cat.get("category") or "", cat.get("category") or "")),
        "obsolete": bool(cat.get("obs")),
        "n_in": cat.get("inputs"),
        "n_out": cat.get("outputs"),
        "n_par": cat.get("params"),
        "op": op,
        "tmr": tmr,
        "tunit": sem.get("tunit"),
        "tpar": sem.get("tpar"),
        "toff": sem.get("toff"),
        "headline": headline,
        "how": how,
        "mode": mode,
        "mode_name": mode_name,
        "mode_note": mode_note,
        "known": bool(cat or sem),
    }


# Ten ngan cua 2 quyen manual PDF (khoa "doc" trong core/manual_index.json)
_MANUAL_EN = {"macro": "Macro Instructions manual (00019)",
              "tag": "TAG Macro Instructions manual (00018)"}
# Bang bit 0/1 cat tu hinh vi du trong PDF: doc thanh chu thi vo nghia, thay bang "..."
_RE_BITS = re.compile(r"(?:\b[01]\s+){7,}[01]\b")


def _manual_old():
    """{code: explain} tu core/macro_manual.json - chi dung khi manual_index.json de trong."""
    global _MM
    if _MM is None:
        try:
            p = os.path.join(os.path.dirname(__file__), "macro_manual.json")
            _MM = {k.upper(): (v.get("explain") or "")
                   for k, v in json.load(open(p, encoding="utf-8"))["by_code"].items()}
        except Exception:
            _MM = {}
    return _MM


def manual_note(code):
    """Doan giai thich CHEP NGUYEN VAN tu manual PDF cua Toshiba -> dict hoac None.

    Uu tien core/manual_index.json (cat dung tung doan "Code xxxxH" trong PDF). 'explain'
    trong macro_manual.json lay doan DAU cua trang nen lech khi 1 trang co nhieu khoi (vd
    4033 Square Root lai ghi 'Y = -X' cua 4079) - chi dung no khi manual_index de trong;
    voi cac ma dang dung trong .db, truong hop do chi co 8200, 4079, 405D va da doi chieu dung.
    Khoa: text, manual (ten quyen), page (so trang PDF, dem tu 1 - co the None).
    """
    from . import manual_index as MI
    code = (code or "").upper()
    e = MI.entry(code) or {}
    raw = e.get("explain") or _manual_old().get(code) or ""
    text = " ".join(_RE_BITS.sub(" ... ", raw).split())
    if not text:
        return None
    sec = e.get("sections") or []
    return {"text": tr(text),
            "manual": tr(_MANUAL_EN.get(e.get("doc"), "manual")),
            "page": sec[0][0] + 1 if sec else None}


def module_note(code):
    """Mo ta CARD ma khoi giao tiep module noi toi (core/module_docs.json) -> dict hoac None.

    Khoa: card, role (tom tat cua app), quote (chep nguyen van spec), quote_from, quote_page
    (so trang PDF dem tu 1), more (danh sach trang can xem them).
    """
    global _MOD
    if _MOD is None:
        try:
            p = os.path.join(os.path.dirname(__file__), "module_docs.json")
            _MOD = {k.upper(): v for k, v in json.load(open(p, encoding="utf-8")).items()
                    if not k.startswith("_")}
        except Exception:
            _MOD = {}
    return _MOD.get((code or "").upper())


def module_settings(db_path, bid, code):
    """Bang cau hinh cua khoi giao tiep card: [(so tham so, nhan, gia tri cua khoi nay, y nghia)].

    Y nghia lay tu "params" trong module_docs.json; gia tri doc tu CAD_BLOCK_PARAM cua DUNG
    khoi dang mo ("-" khi khong co file .db). Khong dung param_names() vi ham do con phuc vu
    bo mo phong. Rong neu loai khoi khong co "params".
    """
    mod = module_note(code)
    if not (mod and mod.get("params")):
        return []
    vals = {}
    if db_path and bid is not None:
        try:
            from core.block_params import read_block_params
            vals = read_block_params(db_path, bid)
        except Exception:
            vals = {}
    out = []
    for p in mod["params"]:
        val = str(vals.get(str(p.get("no")), "") or "").strip()
        if val and p.get("size"):
            val = "%s (%s)" % (val, tr(p["size"]))
        out.append((p.get("no"), p.get("label") or "", val or "-", tr(p.get("what") or "")))
    return out


def key_settings(db_path, sheet_id, bid, code):
    """[(nhan, gia tri)] cac cai dat QUAN TRONG cua DUNG khoi nay, da doi ra don vi doc
    duoc. Rong khi khong doc duoc file .db.

    Bang tham so ben duoi van hien du moi dong, nhung tham so quan trong nhat cua khoi
    timer nam o mot dong KHONG CO TEN (macro_analog.json chi dat ten cho ho analog), nen
    nhin bang khong ra ngay. Vi du DI: param 1 la ten tag, param 2 moi la thoi gian.
    """
    if not (db_path and sheet_id is not None and bid is not None):
        return []
    info = describe(code)
    if not info["tmr"]:
        # Ho analog cung co cai dat rieng quyet dinh hinh dang khoi (he so, muc gioi han,
        # bang gay khuc). Module duong dac tinh da mo dung ban ghi cua khoi de ve roi nen
        # de no tra luon - nap muon de tranh vong import.
        try:
            from core.block_curve import key_settings as _analog
            return _analog(db_path, sheet_id, bid, code)
        except Exception:
            return []
    out = []
    try:
        import core.sheet_sim as SS
        sem = _sem().get((code or "").upper()) or {}
        T = SS.timer_secs(db_path, sheet_id, sem, bid)
        if T is None:
            # bien the "T:input": thoi gian den tu day noi vao chan ten "T"
            out.append((tr("Time T"), tr("taken from the input pin named T, not from a parameter")))
        elif info["tunit"] == "min":
            out.append((tr("Time T"), tr("%g min  (= %g s)") % (T / 60.0, T)))
        else:
            out.append((tr("Time T"), tr("%g s") % T))
        if sem.get("toff"):
            off = SS._num(SS._params(db_path, sheet_id).get(bid, {}).get(sem["toff"]))
            if off is not None:
                out.append((tr("OFF time"), tr("%g s") % off))
    except Exception:
        return out
    return out
