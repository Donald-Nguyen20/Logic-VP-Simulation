# -*- coding: utf-8 -*-
"""Cua so F1: chuc nang khoi duoc quy dinh o FILE NAO - trong phan mem goc (TOSMAP) va
trong app nay. Moi ben mot tab.

Moi tab: tren cung la vi tri THAT cua khoi dang tro chuot (neu co), ben duoi la ban tom
tat va thu tu tra. Chi DOC. Chu viet tieng Anh va qua tr() (core/help_i18n.py); nut
[English | Tieng Viet] o goc tab dien lai ca hai tab. Hai trang tom tat dai co ban tieng
Viet rieng o ui/source_help_vi.py.
"""
from __future__ import annotations
import html
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox,
                               QTabWidget)

from core import block_sources as BS
from core.help_i18n import tr, is_vi
from ui import source_help_vi as VI
from ui.help_lang_toggle import lang_toggle

_TYPE_EN = {"G": "General macro", "TAG": "Tag macro", "TBL": "Table macro",
            "IO": "IO macro", "C": "C macro", "Z": "Others"}


def _muted(text):
    return "<span class='muted'>%s</span>" % text

_CSS = ("<style>body{font-family:'Segoe UI';font-size:11pt} h2{margin:14px 0 4px 0}"
        "h3{margin:12px 0 2px 0;color:#1F4E79} td{padding:2px 10px 2px 0;vertical-align:top}"
        "code{font-family:Consolas;background:#F1F5F9} .muted{color:#64748B}"
        ".box{background:#F8FAFC;border:1px solid #CBD5E1;padding:8px}</style>")


def _p(*parts):
    """Duong dan hien thi, dung dau phan cach cua he dieu hanh."""
    return html.escape(os.path.join(*parts))


def _root_note(root):
    if root:
        return tr("Original software folder on this PC: <code>%s</code>") % html.escape(root)
    return _muted(tr("The original software folder (with DEF and the two manuals) was not "
                     "found on this PC."))


def _manual_row(m):
    if not m:
        return (tr("Manual"), _muted(tr("Not described in either manual.")))
    txt = tr("<code>%s</code><br>PDF page <b>%d</b> &nbsp; (group: %s)") % (
        html.escape(m["file"]), m["page"], html.escape(m["group"]))
    if m["shared"]:
        txt += "<br>" + _muted(tr("The explanation is written once for the whole group."))
    if not m["found"]:
        txt += "<br>" + _muted(tr("PDF not found on this PC."))
    return (tr("Manual (meaning)"), txt)


def _def_row(hits):
    if not hits:
        return (tr("Logic body"), _muted(tr("No .DEF body found.")))
    rows = []
    for (fn, sym), dirs in sorted(hits.items()):
        rows.append("<code>%s</code> &nbsp; <code>.DEF %s</code><br>%s"
                    % (_p("DEF", "SR21E", "TYPE_*", fn), html.escape(sym),
                       _muted(tr("in %d CPU folders: %s")
                              % (len(dirs), html.escape(", ".join(dirs))))))
    return (tr("Logic body (exact)"), "<br>".join(rows))


def _title(code, name):
    title = tr("Block %s") % html.escape(code)
    if name:
        title += " &nbsp;" + _muted("(%s)" % html.escape(name))
    return title


def block_html(code, name=""):
    """Bang vi tri cua 1 ma khoi trong cac nguon goc."""
    r = BS.locate(code)
    md = r["macrodef"]
    rows = []
    if md:
        kind = tr(_TYPE_EN.get(md["type"], md["type"] or ""))
        rows.append(("MacroDef.db", "%s<br>%s" % (
            html.escape(md["name"] or ""),
            _muted(tr("Symbol Int <code>%s</code>, Real <code>%s</code> &middot; %s &middot; "
                      "%s in / %s out / %s parameters")
                   % (html.escape(md["sym_int"] or "-"), html.escape(md["sym_real"] or "-"),
                      kind, md["n_in"], md["n_out"], md["n_par"])))))
    else:
        rows.append(("MacroDef.db", _muted(tr("Code not listed."))))
    rows.append(_manual_row(r["manual"]))
    rows.append(_def_row(r["def_hits"]))
    rows.append(("macro_param.csv", tr("%d parameter rows (default / max / min)")
                 % r["n_param_rows"] if r["n_param_rows"] else _muted(tr("No parameters."))))
    body = "".join("<tr><td><b>%s</b></td><td>%s</td></tr>" % rw for rw in rows)
    return "<h2>%s</h2><div class='box'><table>%s</table></div>" % (_title(r["code"], name), body)


def summary_html():
    """Ban tom tat 4 nguon goc va thu tu tra."""
    paths = (_p("DEF", "MCR", "MacroDef.db"), _p("DEF", "SR21E", "TYPE_*", "TODEN.DEF"),
             _p("DEF", "SR21E", "macro_master.csv"))
    if is_vi():
        return VI.summary_html(*paths)
    return (
        "<h2>Where block functions are defined in the original software</h2>"
        "<h3>1. Programming manuals (PDF) &mdash; meaning in words</h3>"
        "The only source with explanations, truth tables and formulas. Search for "
        "<code>&lt;code&gt;H</code>."
        "<ul><li><code>VP1-C-L2-I-CB-00019-A ... Macro Instructions.pdf</code> &mdash; general "
        "macros (4xxx, 5xxx). Example: <code>4011H</code> = F/F(R) on PDF page 29. "
        "Parameter tables start at page 191.</li>"
        "<li><code>VP1-C-L2-I-CB-00018-A ... TAG Macro Instructions.pdf</code> &mdash; tag and "
        "station macros (82xx). Example: <code>820DH</code> = MV-POS on PDF page 116.</li>"
        "<li>Not covered: obsolete (obs) macros and the HCNT family 20xx / 21xx.</li></ul>"
        "<h3>2. <code>%s</code> (SQLite) &mdash; official identity</h3>"
        "<ul><li><code>DEF_MACRO</code> (LANGUAGE = 'E'): code, Int / Real symbol, abbreviation, "
        "full name, type, number of inputs / outputs / parameters.</li>"
        "<li><code>DEF_MACRO_PIN</code>: pin positions. <code>DEF_MACRO_TYPE</code>: macro groups.</li>"
        "<li>Names only &mdash; it does not say how the block behaves.</li></ul>"
        "<h3>3. <code>%s</code> and <code>TAG_MCR.DEF</code> &mdash; the exact logic the controller runs</h3>"
        "<ul><li>One <code>.DEF &lt;symbol&gt; ... .DEFEND</code> body per macro. TODEN.DEF: general "
        "macros; TAG_MCR.DEF: tag and station macros.</li>"
        "<li>A Real symbol with the <code>F_</code> prefix is stored without it "
        "(<code>F_T_B1_I</code> &rarr; <code>T_B1_I</code>).</li>"
        "<li>Timer bodies differ between CPU types: use the folder that matches the CPU of "
        "the .db (<code>CAD_CPU.CPUTYPE</code>).</li></ul>"
        "<h3>4. <code>%s</code> and <code>macro_param.csv</code> &mdash; catalogue and parameter limits</h3>"
        "<ul><li>macro_master.csv: code, symbols, pin and parameter counts, English and Japanese names.</li>"
        "<li>macro_param.csv: for each parameter &mdash; text or number, tuning, default, max, min.</li>"
        "<li>Both files are encoded cp932.</li></ul>"
        "<h3>Lookup order</h3>"
        "<ol><li>Take the block's <code>MACROCODE</code> (table <code>CAD_BLOCK</code> in the .db).</li>"
        "<li>MacroDef.db or macro_master.csv &rarr; name and symbol.</li>"
        "<li>PDF, search <code>&lt;code&gt;H</code> &rarr; what the block means.</li>"
        "<li>TODEN.DEF / TAG_MCR.DEF, search <code>.DEF &lt;symbol&gt;</code> &rarr; exact logic.</li>"
        "<li>macro_param.csv &rarr; parameter defaults and limits.</li></ol>"
        % paths)


def app_block_html(code, name=""):
    """Bang: trong app nay ma khoi 'code' do file nao quy dinh."""
    title = _title((code or "").upper(), name)
    body, last = [], None
    for label, f, detail in BS.app_locate(code):
        cell = "<code>%s</code>" % html.escape(f) if f != "-" else ""
        cell += "%s<span class='muted'>%s</span>" % ("<br>" if cell else "", html.escape(detail))
        body.append("<tr><td><b>%s</b></td><td>%s</td></tr>"
                    % ("" if label == last else html.escape(label), cell))
        last = label
    return "<h2>%s</h2><div class='box'><table>%s</table></div>" % (title, "".join(body))


def app_summary_html():
    """Ban tom tat: chuc nang khoi trong app nay nam o file nao."""
    if is_vi():
        return VI.app_summary_html()
    return (
        "<h2>Where block functions are defined in this app</h2>"
        "<h3>1. Name and pins &mdash; copied from the vendor sources</h3>"
        "<ul><li><code>core/macro_catalog.json</code> &mdash; 986 macros: name, group, pin and "
        "parameter counts.</li>"
        "<li><code>core/macro_pins.json</code> &mdash; 1,019 symbols: pin positions and names "
        "(from MacroDef.db).</li>"
        "<li><code>core/macro_manual.json</code> &mdash; 315 codes: pin names and short "
        "explanations taken from the manuals.</li></ul>"
        "<h3>2. Behaviour &mdash; what the simulator runs</h3>"
        "<ul><li><code>core/logic_sem.json</code> (130 codes) &mdash; digital gates, latches and "
        "timers (keys <code>op</code>, <code>tmr</code>), run by <code>core/sheet_sim.py</code>.</li>"
        "<li><code>core/analog_sem.json</code> (262 codes) &mdash; analog math, F(x), comparators, "
        "run by <code>core/sheet_sim.py</code>.</li>"
        "<li><code>core/sheet_dyn.py</code> &mdash; code lists of blocks with state (integrator, "
        "derivative, lag, rate limiter, dead time, lead/lag, hysteresis comparator, timers), "
        "stepped every dt.</li>"
        "<li><code>core/def_sim.py</code> &mdash; station (MV/SV) and TAG blocks run the vendor "
        "body in TAG_MCR.DEF, read by <code>core/macro_def.py</code>. A station without a "
        "vendor body falls back to <code>core/macro_analog.json</code> "
        "(<code>core/analog_sim.py</code>).</li>"
        "<li><code>core/macro_behavior.json</code> &mdash; MOV family in the Simulate block "
        "window (<code>core/logic_sim.py</code>).</li>"
        "<li><code>core/macro_iodep.json</code> &mdash; which inputs drive each output, used "
        "when tracing signals.</li>"
        "<li>In simulation, general blocks do not run their TODEN.DEF body yet "
        "(<code>USE_TODEN = False</code> in <code>core/def_sim.py</code>).</li></ul>"
        "<h3>3. Help window, parameters and symbols</h3>"
        "<ul><li><code>core/block_help.py</code> &mdash; description text, chosen by the op / "
        "timer family in logic_sem.json and analog_sem.json, so the text matches the simulator.</li>"
        "<li><code>core/manual_index.json</code> &mdash; explanation copied from the two PDF "
        "manuals, shown under it; for blocks with no op / timer it is the only text.</li>"
        "<li><code>core/module_docs.json</code> &mdash; for the EHC card interface blocks "
        "(VPCL, FDCL, PLUL): what the card does, copied from the DEHC hardware specification, "
        "with the EHC.pdf pages that show its logic, and what each parameter (SN, DI, FI, DO, "
        "CO, FO) means, read from the block body in TODEN.DEF.</li>"
        "<li><code>core/help_i18n.py</code> + <code>core/help_vi.json</code> + "
        "<code>core/help_vi_manual.json</code> &mdash; hand-written Vietnamese translation of "
        "Help and F1 (the English / Tiếng Việt button).</li>"
        "<li><code>core/block_timing.py</code> waveforms, <code>core/block_logic.py</code> gate "
        "diagram, <code>core/block_fbd.py</code> function-block diagram (both from the vendor "
        "DEF body), <code>core/block_curve.py</code> curves and value tables.</li>"
        "<li><code>core/block_params.py</code> &mdash; parameter values from "
        "<code>CAD_BLOCK_PARAM</code> in the .db, limits from macro_param.csv.</li>"
        "<li><code>core/macro_internal.json</code> + <code>core/internal_figs/</code> &mdash; 69 "
        "internal diagrams cropped from the manuals.</li>"
        "<li><code>core/symbol_shapes.json</code> + <code>core/block_syms.py</code> &mdash; block "
        "symbols drawn on the sheet.</li></ul>"
        "<h3>Lookup order</h3>"
        "<ol><li>macro_catalog.json &rarr; name.</li>"
        "<li>logic_sem.json &rarr; digital block; otherwise analog_sem.json.</li>"
        "<li>Code in one of the lists in sheet_dyn.py &rarr; stepped in time there.</li>"
        "<li>Vendor body in TAG_MCR.DEF with every instruction implemented &rarr; def_sim.py; "
        "station without a body &rarr; macro_analog.json.</li>"
        "<li>MOV family &rarr; macro_behavior.json (Simulate block window).</li></ol>")


class SourceHelpDialog(QDialog):
    """F1: hai tab - phan mem goc va app nay. Moi tab co vi tri cua khoi dang tro."""

    def __init__(self, code=None, name="", parent=None):
        super().__init__(parent)
        self._code, self._name = code, name
        self.resize(1000, 780)
        lay = QVBoxLayout(self)
        self._tabs = QTabWidget(self)
        self._orig = QTextBrowser(self)
        self._mine = QTextBrowser(self)
        self._tabs.addTab(self._orig, "")
        self._tabs.addTab(self._mine, "")
        self._tabs.setCornerWidget(lang_toggle(self, self._fill), Qt.Corner.TopRightCorner)
        lay.addWidget(self._tabs)
        self._bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        self._bb.rejected.connect(self.reject)
        lay.addWidget(self._bb)
        self._fill()

    def _fill(self):
        """Dien (lai) moi chu cua cua so theo ngon ngu Help dang chon."""
        code, name = self._code, self._name
        self.setWindowTitle(tr("F1 - Where block functions are defined"))
        hint = ("" if code else "<p class='muted'>%s</p>"
                % tr("Point at a block on the sheet and press F1 to see where that block "
                     "is defined."))
        orig = block_html(code, name) if code else hint
        self._orig.setHtml(_CSS + orig + "<p>%s</p>" % _root_note(BS.vendor_root())
                           + summary_html())
        mine = app_block_html(code, name) if code else hint
        self._mine.setHtml(_CSS + mine + app_summary_html())
        self._tabs.setTabText(0, tr("Original software (TOSMAP)"))
        self._tabs.setTabText(1, tr("This app"))
        self._bb.button(QDialogButtonBox.StandardButton.Close).setText(tr("Close"))
