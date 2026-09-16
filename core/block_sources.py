# -*- coding: utf-8 -*-
"""Chuc nang khoi trong phan mem goc (TOSMAP) duoc quy dinh o FILE NAO - noi dung cua
cua so F1.

Ba phan:
  - locate(code): vi tri THAT cua mot ma khoi trong tung nguon goc (trang PDF, dong trong
    MacroDef.db, file DEF chua than lenh, so tham so trong macro_param.csv).
  - app_locate(code): trong APP NAY khoi do do file nao quy dinh (ten, mo phong tren
    sheet, cua so Simulate block, do tin hieu, chu va hinh Help, ky hieu). Hoi CHINH cac
    ham ma app dang dung de chon duong chay, nen khong the lech voi hanh vi that.
  - Ban tom tat (app goc + app nay) nam o ui/source_help_dialog.py.

Chi DOC, khong dinh Qt. Van ban tra ra viet tieng Anh va qua tr() (core/help_i18n.py),
nen theo ngon ngu Help dang chon. Ten file, ma khoi, ten tap ma giu nguyen.
"""
from __future__ import annotations
import json
import os
import re
import sqlite3

from . import manual_index as MI
from . import block_params as BP
from .help_i18n import tr

_JSON = {}          # {ten_file: noi dung} - JSON canh module, doc 1 lan
_TEXT = {}          # {duong_dan_DEF: noi dung} - doc 1 lan, dung cho moi lan bam F1


def vendor_root():
    """Thu muc goc T-Designer (chua thu muc DEF va 2 file PDF manual), hoac None."""
    sr21e = BP._def_root()
    return os.path.dirname(os.path.dirname(sr21e)) if sr21e else None


def _macrodef_row(root, code):
    p = os.path.join(root, "DEF", "MCR", "MacroDef.db") if root else ""
    if not os.path.exists(p):
        return None
    try:
        cn = sqlite3.connect("file:%s?mode=ro" % p.replace("\\", "/"), uri=True)
        cn.text_factory = lambda b: b.decode("latin-1", "replace")
        r = cn.execute("SELECT SYMBOL_INT,SYMBOL_REAL,TYPE_CODE,MACROABBR,MACRONAME,"
                       "IN_NUM,OUT_NUM,PARAM_NUM FROM DEF_MACRO "
                       "WHERE LANGUAGE='E' AND UPPER(MACROCODE)=?", (code,)).fetchone()
        cn.close()
    except Exception:
        return None
    if not r:
        return None
    keys = ("sym_int", "sym_real", "type", "abbr", "name", "n_in", "n_out", "n_par")
    return dict(zip(keys, r))


def _def_hits(root, symbols):
    """{(ten_file, symbol): [thu muc CPU]} - file TODEN.DEF / TAG_MCR.DEF co '.DEF <symbol>'.

    Khoi REAL co tien to F_ (F_T_B1_I) van co than lenh, chi la ghi KHONG tien to
    (T_B1_I) - xem macro_def._bo_tien_to. Nen phai tim ca hai dang ten."""
    base = os.path.join(root, "DEF", "SR21E") if root else ""
    if not os.path.isdir(base):
        return {}
    out = {}
    for d in sorted(os.listdir(base)):
        for fn in ("TODEN.DEF", "TAG_MCR.DEF"):
            p = os.path.join(base, d, fn)
            if not os.path.isfile(p):
                continue
            if p not in _TEXT:
                try:
                    _TEXT[p] = open(p, encoding="latin-1", errors="replace").read()
                except Exception:
                    _TEXT[p] = ""
            for s in symbols:
                if re.search(r"^\.DEF\s+%s\s" % re.escape(s), _TEXT[p], re.M):
                    out.setdefault((fn, s), []).append(d)
                    break
    return out


def locate(code):
    """dict vi tri cua 1 ma khoi trong 4 nguon goc. Khoa co the rong khi khong tim thay."""
    code = (code or "").upper()
    root = vendor_root()
    row = _macrodef_row(root, code)
    syms = []
    if row:
        for s in (row["sym_int"], row["sym_real"]):
            if s and s != "-":
                for t in ([s, s[2:]] if s.startswith("F_") else [s]):
                    if t not in syms:
                        syms.append(t)
    man = MI.entry(code)
    manual = None
    if man and man.get("sections"):
        manual = {"file": MI.DOCS[man["doc"]], "title": MI.DOC_TITLE[man["doc"]],
                  "page": man["sections"][0][0] + 1, "group": man.get("group", ""),
                  "shared": bool(man.get("shared")),
                  "found": bool(MI.pdf_path(man["doc"]))}
    n_par = len(BP.param_meta().get(code, {}))
    hits = _def_hits(root, syms)
    return {"code": code, "root": root, "macrodef": row, "symbols": syms,
            "manual": manual, "def_hits": hits, "n_param_rows": n_par}


# ---- APP NAY ----
# (tap ma trong core/sheet_dyn.py, cach chay) - thu tu giong nhanh re trong sheet_dyn
_DYN_SETS = (
    ("INTEG_CODES", "integrator"), ("DERIV_CODES", "derivative"),
    ("LAG_CODES", "first-order lag"), ("RATE_CODES", "rate limiter"),
    ("DELAY_CODES", "dead time / sample delay"), ("CMP_CODES", "comparator with hysteresis"),
    ("LLG_CODES", "lead / lag"),
)
_MODE_FILE = {"timing": "core/block_timing.py", "gates": "core/block_logic.py",
              "curve": "core/block_curve.py", "fbd": "core/block_fbd.py"}


def _sim_rows(code):
    """Cac duong mo phong TREN SHEET ma app thuc su chon cho ma khoi nay.

    Moi dong: (file, chi tiet cho F1, cum tu cho nguoi doc Help - rong neu khong chay)."""
    from . import cond_tree as CT, sheet_sim as SS, sheet_dyn as SD
    from . import def_sim as DS, analog_sim as AS, macro_def as MD
    if code == CT.TERM:
        return [("core/cond_tree.py", tr("sheet I/O terminal - skipped, it only names the net"), "")]
    rows = []
    ls = CT._sem().get(code)
    if isinstance(ls, dict):
        det = "op %s" % ls.get("op")
        if ls.get("tmr"):
            det += tr(", timer family %s") % ls["tmr"]
        rows.append(("core/logic_sem.json", det + tr(" - digital, run by core/sheet_sim.py"),
                     tr("digital operation")))
    an = SS._analog_sem().get(code)
    if isinstance(an, dict):
        rows.append(("core/analog_sem.json",
                     tr("op %s - analog, run by core/sheet_sim.py") % an.get("op"),
                     tr("analog operation")))
    for name, what in _DYN_SETS:
        if code in getattr(SD, name):
            what = tr(what)
            rows.append(("core/sheet_dyn.py", tr("%s: %s, stepped every dt") % (name, what), what))
    if code in SD.timer_codes():
        rows.append(("core/sheet_dyn.py", tr("digital timer, stepped every dt"),
                     tr("digital timer")))
    station = code in SD.STATION_CODES and AS.has_analog(code)
    if DS.can_simulate(code) or station:
        if DS.has_def(code):
            sym = MD.symbol_of(code) or "?"
            rows.append(("core/def_sim.py", tr("runs the vendor body .DEF %s from "
                         "TAG_MCR.DEF") % sym, tr("the vendor's own logic body .DEF %s") % sym))
        else:
            rows.append(("core/macro_analog.json", tr("hand-built station model, "
                         "run by core/analog_sim.py"), tr("hand-built station model")))
    return rows or [("-", tr("Not simulated on the sheet - its outputs stay unknown."), "")]


def sim_status(code):
    """Mot cau (theo ngon ngu Help) cho Help: tren sheet app mo phong khoi nay ra sao. Cung nguon
    voi F1 (_sim_rows) nen hai cua so khong the noi khac nhau."""
    rows = _sim_rows((code or "").upper())
    plain = [r[2] for r in rows if r[2]]
    if plain:
        return tr("Simulated on the sheet as: %s.") % "; ".join(plain)
    return rows[0][1][:1].upper() + rows[0][1][1:].rstrip(".") + "."


def vendor_help_doc(code):
    """Ma tai lieu Toshiba ma phan mem goc mo khi xem Help cua ma khoi, vd '6F2K0653'.

    Lay cot 5 cua DEF/SR21E/MacroWindowDef.* (dong '1,411E,ISA,Others,6F2K0653'). Cac tai
    lieu nay KHONG di kem bo cai; chi 2 quyen PDF 00018/00019 la co tren may. '' neu khong ro."""
    if "_window" not in _JSON:
        idx = {}
        base = os.path.join(vendor_root() or "", "DEF", "SR21E")
        names = sorted(os.listdir(base)) if os.path.isdir(base) else []
        for fn in (n for n in names if n.startswith("MacroWindowDef.")):
            try:
                with open(os.path.join(base, fn), encoding="latin-1") as f:
                    for ln in f:
                        c = ln.strip().split(",")
                        if len(c) >= 5 and c[4].strip():
                            idx.setdefault(c[1].strip().upper(), c[4].strip())
            except OSError:
                continue
        _JSON["_window"] = idx
    doc = _JSON["_window"].get((code or "").upper(), "")
    return os.path.splitext(doc)[0] if doc.lower().endswith((".htm", ".pdf", ".tif")) else doc


def _json(name):
    """Doc 1 file JSON canh module (co nho). Loi doc -> {}."""
    if name not in _JSON:
        try:
            with open(os.path.join(os.path.dirname(__file__), name), encoding="utf-8") as f:
                _JSON[name] = json.load(f)
        except (OSError, ValueError):
            _JSON[name] = {}
    return _JSON[name]


def _look_rows(code, d, syms):
    """Chu + hinh cua Help, anh so do noi, ky hieu tren ban ve."""
    from . import block_help as BH
    out = []
    if d["headline"]:
        out.append((tr("Help text"), "core/block_help.py", tr("entry for %s") % (d["tmr"] or d["op"])))
    if BH.manual_note(code):
        out.append((tr("Help text"), "core/manual_index.json", tr("explanation copied from the manual")))
    if BH.module_note(code):
        out.append((tr("Help text"), "core/module_docs.json",
                    tr("card description from project PDFs, parameter meanings")))
    if not out:
        out.append((tr("Help text"), "-", tr("no description - name only")))
    out.append((tr("Help drawing"), _MODE_FILE.get(d["mode"], "-"), d["mode_name"]))
    fig = _json("macro_internal.json").get(code)
    if fig:
        out.append((tr("Internal picture"), "core/internal_figs/%s" % fig.get("img"),
                    tr("cropped from manual %s page %s") % (fig.get("manual"), fig.get("page"))))
    shapes = _json("symbol_shapes.json")
    drawn = [k for k in syms if k in shapes]
    out.append((tr("Symbol on sheet"), "core/symbol_shapes.json" if drawn else "-",
                ", ".join(drawn) if drawn else tr("no drawn symbol")))
    return out


def app_locate(code):
    """[(muc, file, chi tiet)] - trong app nay ma khoi 'code' duoc quy dinh o dau."""
    from . import block_help as BH, logic_sim as LS, analog_sim as AS
    from . import signal_graph as SG, sheet_render as SR
    code = (code or "").upper()
    d = BH.describe(code)
    cat = BH._catalog().get(code)
    syms = [k for k, v in SR._macro_pins().items()
            if str(v.get("macrocode", "")).upper() == code]
    out = [(tr("Name"), "core/macro_catalog.json" if cat else "-",
            "%s (%s)" % (cat.get("name"), d["category"]) if cat else tr("not listed")),
           (tr("Pins"), "core/macro_pins.json" if syms else "-",
            ", ".join(syms) if syms else tr("no pin table"))]
    out += [(tr("Sheet simulation"), r[0], r[1]) for r in _sim_rows(code)]
    if LS.has_behavior(code):
        out.append((tr("Simulate block"), "core/macro_behavior.json", tr("run by core/logic_sim.py")))
    elif AS.has_analog(code):
        out.append((tr("Simulate block"), "core/macro_analog.json", tr("run by core/analog_sim.py")))
    if code == SG.TERM:
        out.append((tr("Signal tracing"), "core/signal_graph.py", tr("wiring terminal - skipped")))
    elif code in SG._iodep():
        out.append((tr("Signal tracing"), "core/macro_iodep.json",
                    tr("which inputs drive each output")))
    else:
        out.append((tr("Signal tracing"), "-",
                    tr("every input is treated as driving every output")))
    return out + _look_rows(code, d, syms)
