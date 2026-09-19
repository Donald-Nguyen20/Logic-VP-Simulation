# -*- coding: utf-8 -*-
"""Cua so HELP cua 1 khoi tren ban ve (chuot phai len khoi -> Help).

Noi dung: mot doan giai thich ngan roi BAN VE LAI ruot khoi, chiem het cua so. Ban ve
chon theo tung loai khoi: gian do xung cho ho timer (core/block_timing.py), so do cong
logic noi cho ho cong (core/block_logic.py), duong dac tinh hoac bang gia tri cho ho
analog (core/block_curve.py), so do khoi chuc nang dung ban than than DEF cua hang cho
tat ca so con lai (core/block_fbd.py).

Khong con hai bang "Settings of this block" va "Pins and the signals": nhung gi chung
noi - cai dat cua khoi, ten tin hieu dang noi vao tung chan, tri so dang chay - nay
ghi thang tren ban ve, doc mot cho la thay het.

Chu tren man hinh viet bang tieng Anh va qua tr() (core/help_i18n.py); nut
[English | Tieng Viet] o goc tren dung lai toan bo chu theo ngon ngu vua chon. Chu thich
trong code van la tieng Viet khong dau.

Tram van hanh (MV, MV-POS, MV-FF-POS, SV, SV-BIAS, MOV2-NSH) con co o "How it works" o
tren cung: tai lieu viet tay tu than lenh DEF kem bieu do kich ban chay bang DefSim
(ui/tag_doc_view.py, core/tag_docs.py).

Ca than cua so nam trong MOT vung cuon doc: moi o cao dung bang noi dung that, cuon mot
lan tu tren xuong la het. Chi ban ve giu thanh cuon ngang rieng vi no rong toi ~3.900px.

Khac voi BlockParamDialog (sua tham so de mo phong), cua so nay CHI DOC.
"""
from __future__ import annotations
import html
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox, QFrame,
    QScrollArea, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from core.block_help import (
    describe, key_settings, manual_note, module_note, module_settings,
    MODE_NONE, MODE_GATES, MODE_TIMING, MODE_CURVE, MODE_FBD,
)
from core.block_params import block_pin_rows, block_param_rows
import core.sheet_sim as SS
import core.block_sources as BS
from core.help_i18n import tr
from core.book_diagram import co_khung, khung
from ui.help_lang_toggle import lang_toggle
from ui.tag_doc_view import has_doc, tag_doc_panel


def _legend():
    """'do = 1, xanh = 0' to dung mau cua sheet - dung chung cho moi chu thich ban ve."""
    return ("<b><span style='color:#DC2626'>%s</span></b>, "
            "<b><span style='color:#16A34A'>%s</span></b>" % (tr("red = 1"), tr("green = 0")))


def _ascii(s):
    """Ten khoi neu doc duoc, khong thi rong.

    SYMBOL trong CAD_BLOCK la tieng Nhat ma cp932 nhung duoc doc theo latin-1 nen ra rac
    (E0B1 do duoc 'o-I-p’[Zq'). Loc bo ky tu ngoai ASCII van con lai 'op[q' - van vo
    nghia - nen chi can THAY co mot ky tu ngoai ASCII la bo ca chuoi, quay ve dung ma
    khoi."""
    t = str(s or "")
    if any(ord(ch) > 126 for ch in t):
        return ""
    return "".join(ch for ch in t if ord(ch) >= 32).strip()


def _fmt(v):
    """Gia tri tin hieu -> chuoi ngan. Bool phai kiem TRUOC int (bool la con cua int)."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return "%.6g" % v
    return str(v)


class BlockHelpDialog(QDialog):
    """Giai thich chuc nang cua 1 khoi: mo ta, tham so dang cai, chan dang noi."""

    def __init__(self, code, name="", bid=None, db_path=None, sheet_id=None,
                 parent=None, sim_values=None, dig_env=None, ana_env=None,
                 on_params=None):
        super().__init__(parent)
        self.code = (code or "").upper()
        self.bid = bid
        self.db_path = db_path
        self.sheet_id = sheet_id
        self._sim_values = sim_values
        self._dig_env = dict(dig_env) if dig_env else {}
        self._ana_env = dict(ana_env) if ana_env else {}
        self._on_params = on_params
        self._cache_vals = None      # bang chan VA ban ve cung hoi -> chi giai sheet 1 lan

        self.info = describe(self.code)
        self._name = _ascii(name)
        self._dat_tieu_de()
        # Ban ve khoi tram rong toi 3.924px, nen cua so mo TOAN MAN HINH: cang nhieu
        # cho thi cang it phai cuon. Van de nut phong to/thu nho de dua ve cua so thuong.
        self.resize(1280, 860)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self._w_head = self._header()
        top.addWidget(self._w_head, 1)
        top.addWidget(lang_toggle(self, self._doi_ngon_ngu), 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        self._w_what = self._what_it_does()
        self._w_diag = self._diagram_slot()
        self._w_tag = self._tag_slot() if has_doc(self.code) else None
        self._w_book = self._book_slot() if co_khung(self.code) else None
        self._bo_cuc_than(lay)

        bar = QHBoxLayout()
        bar.addStretch(1)
        self._b_par = None
        if self._on_params is not None and self.bid is not None:
            self._b_par = QPushButton()
            self._b_par.clicked.connect(self._open_params)
            bar.addWidget(self._b_par)
        self._b_close = QPushButton()
        self._b_close.setDefault(True)
        self._b_close.clicked.connect(self.accept)
        bar.addWidget(self._b_close)
        lay.addLayout(bar)
        self._chu_nut()

    def _bo_cuc_than(self, lay):
        """Xep ca than cua so vao CHUNG mot vung cuon doc.

        Truoc day o "How it works" va ban ve moi o mot thanh cuon rieng, lai chia nhau
        chieu cao qua mot thanh keo: o nao cung chi con mot khe hep, doc vai dong da phai
        cuon, va noi o nay ra thi o kia teo lai. Nay moi o cao DUNG BANG noi dung that va
        ca ba cuon chung mot lan tu tren xuong, nen khong o nao bi cat.

        Hai bang "Settings" va "Pins" da bo han; nhung gi chung noi nay nam tren ban ve."""
        than = QWidget()
        v = QVBoxLayout(than)
        v.setContentsMargins(0, 0, 0, 0)
        for w in self._thu_tu_o():
            v.addWidget(w)
        v.addStretch(1)
        sc = QScrollArea()
        sc.setWidget(than)
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.Shape.NoFrame)
        lay.addWidget(sc, 1)

    def _thu_tu_o(self):
        """Thu tu cac o tu tren xuong.

        Tram van hanh: "How it works" (viet tu than lenh DEF) len dau vi day moi la cai
        nguoi doc can, roi ban ve, con doan chep tu manual chi vai cau nen xuong cuoi.
        Khoi thuong khong co o dau, chu cua app len truoc ban ve.

        Ban ve kieu so tay dat NGAY DUOI ban ve tu sinh: hai cai cung mot logic, xem
        lien nhau moi doi chieu duoc - do cung la cho nguoi doc dang cam quyen so tay
        tim thay hinh quen thuoc ma khong phai cuon qua het phan chu."""
        o = [self._w_diag] if self._w_book is None else [self._w_diag, self._w_book]
        if self._w_tag is None:
            return [self._w_what] + o
        return [self._w_tag] + o + [self._w_what]

    def _tag_slot(self):
        return tag_doc_panel(self.code, cuon=False)

    def _book_slot(self):
        """O ban ve so tay: net ve NGUYEN cua hang, chi them mau gia tri. Chi dung cho
        ma khoi da co file neo o core/book_layouts."""
        from ui.book_diagram_view import book_panel
        g = QGroupBox(tr("Book diagram (vendor original drawing)"))
        v = QVBoxLayout(g)
        pv, _pn, px, ps = self._pin_state_fbd()
        d, why = book_panel(self.code, pin_vals=pv, pin_sigs=ps, pin_nums=px)
        if d is None:
            v.addWidget(self._cho_trong(why))
            return g
        v.addWidget(self._khung_cuon(d), 1)
        v.addWidget(self._chu_thich_so_tay())
        return g

    def _chu_thich_so_tay(self):
        """Noi ro ban ve lay tu dau va vi sao co the khac o "So do" - de nguoi doc khong
        tuong hai ban ve mau thuan nhau. Khong noi chac "ban rut gon": co khoi hang ve rut
        gon (8204: 26 cong so voi 47), co khoi ve gan du."""
        k = khung(self.code) or {}
        noi = " / ".join(x for x in (k.get("ma_ban_ve"), k.get("trang_in")) if x)
        t = tr("Redrawn line for line from the vendor manual. The vendor may draw a "
               "simplified version with fewer gates than the real logic - the full logic "
               "is the diagram above. Tint: %s, none = no 0/1 here. Hover a pin or "
               "display cell for its real signal and value. Click a pin or display "
               "cell to light up its wire through the gates (inputs: where it goes; "
               "outputs and display cells: what drives it); click it again to clear."
               ) % _legend()
        return self._chu_thich("%s%s" % (t, ("  [%s]" % noi) if noi else ""))

    def _dat_tieu_de(self):
        title = self.info["short"] or self._name
        self.setWindowTitle(tr("Help - %s (%s)") % (title, self.code) if title
                            else tr("Help - %s") % self.code)

    def _chu_nut(self):
        if self._b_par is not None:
            self._b_par.setText(tr("Open block parameters..."))
            self._b_par.setToolTip(tr("Edit these values for simulation"))
        self._b_close.setText(tr("Close"))

    def _doi_ngon_ngu(self):
        """Dung lai moi chu theo ngon ngu vua chon. Gia tri mo phong da nho trong
        _cache_vals nen khong phai giai lai sheet; than DEF cung da nho o block_fbd."""
        self.info = describe(self.code)
        self._dat_tieu_de()
        self._chu_nut()
        pairs = [("_w_head", self._header), ("_w_what", self._what_it_does),
                 ("_w_diag", self._diagram_slot)]
        if self._w_tag is not None:
            pairs.append(("_w_tag", self._tag_slot))
        if self._w_book is not None:
            pairs.append(("_w_book", self._book_slot))
        for attr, build in pairs:
            self._thay(attr, build)

    def _thay(self, attr, build):
        """Dung lai 1 phan, dat dung cho cu. Phai hoi layout cua CHINH widget cha: ba o
        nam trong vung cuon chu khong phai con truc tiep cua cua so nua."""
        old, new = getattr(self, attr), build()
        old.parentWidget().layout().replaceWidget(old, new)
        old.hide()
        old.deleteLater()
        setattr(self, attr, new)

    # ---------- phan dau: ten chinh thuc cua hang ----------
    def _header(self):
        i = self.info
        short = i["short"] or self._name or self.code
        line1 = "<span style='font-size:15pt;font-weight:bold'>%s</span>" % short
        if i["title"]:
            line1 += "<span style='font-size:11pt;color:#555'> &nbsp;-&nbsp; %s</span>" % i["title"]

        bits = [tr("macro code <b>%s</b>") % self.code]
        if i["symbol"]:
            bits.append(tr("symbol <b>%s</b>") % i["symbol"])
        if i["category"]:
            bits.append(tr("group <b>%s</b>") % i["category"])
        for lbl, k in ((tr("in"), "n_in"), (tr("out"), "n_out"), (tr("param"), "n_par")):
            if i[k] is not None:
                bits.append("%s <b>%s</b>" % (lbl, i[k]))
        line2 = "<span style='color:#444'>%s</span>" % " &nbsp;|&nbsp; ".join(bits)

        warn = "<br><span style='color:#B45309'>%s</span>"
        if i["obsolete"]:
            line2 += warn % tr("<b>Obsolete block</b> - kept for existing drawings, not used "
                               "on new designs.")
        if not i["known"]:
            line2 += warn % tr("This macro code is not in the block catalogue - only the pin "
                               "table below is reliable.")

        lb = QLabel(line1 + "<br>" + line2)
        lb.setTextFormat(Qt.TextFormat.RichText)
        lb.setWordWrap(True)
        return lb

    # ---------- phan 1: khoi nay lam gi ----------
    def _what_it_does(self):
        i = self.info
        g = QGroupBox(tr("What this block does"))
        v = QVBoxLayout(g)
        if i["headline"]:
            h = QLabel(i["headline"])
            f = QFont(); f.setBold(True); h.setFont(f)
            v.addWidget(h)
        man = manual_note(self.code)
        mod = module_note(self.code)
        for txt in self._what_texts(man, mod):
            p = QLabel(txt)
            p.setTextFormat(Qt.TextFormat.RichText)
            p.setWordWrap(True)
            p.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            v.addWidget(p)

        # Cai dat quan trong nhat cua CHINH khoi nay. Tham so thoi gian cua khoi timer
        # nam o mot dong khong co ten trong bang ben duoi nen rat de bo sot.
        for lbl, val in key_settings(self.db_path, self.sheet_id, self.bid, self.code):
            k = QLabel("<span style='color:#B45309'><b>%s</b></span>"
                       % (tr("%s of this block: %s") % (lbl, val)))
            k.setTextFormat(Qt.TextFormat.RichText)
            k.setWordWrap(True)
            v.addWidget(k)

        # Khoi giao tiep card: 7 tham so khong co ten trong bang tham so, nen hien y nghia
        # tung tham so kem gia tri THAT cua khoi nay.
        rows = module_settings(self.db_path, self.bid, self.code)
        if rows:
            v.addWidget(self._module_table(rows, mod))

        s = QLabel("<span style='color:#777;font-size:9pt'>%s.</span>" % self._source_line(man, mod))
        s.setTextFormat(Qt.TextFormat.RichText)
        s.setWordWrap(True)
        v.addWidget(s)
        return g

    def _what_texts(self, man, mod=None):
        """Cac doan chu (HTML) cua o 'What this block does'.

        Thu tu: chu cua app (theo op/timer ma bo mo phong chay) -> doan chep tu manual PDF
        -> mo ta card (khoi giao tiep module EHC) -> neu app KHONG co chu rieng thi noi ro tren
        sheet khoi nay co chay khong, va khi ca manual lan mo ta card cung khong co thi chi ra
        tai lieu Toshiba ma phan mem goc dung cho khoi nay."""
        i = self.info
        out = [html.escape(i["how"])] if i["how"] else []
        if man:
            page = tr(", page %s") % man["page"] if man["page"] else ""
            out.append(tr("<b>From the %s%s:</b> %s")
                       % (man["manual"], page, html.escape(man["text"])))
        if mod:
            out.extend(self._module_texts(mod))
        if i["how"]:
            return out
        if not (man or mod):
            msg = tr("This block is not described in the app or in the two manuals it uses.")
            doc = BS.vendor_help_doc(self.code)
            if doc:
                msg += (tr(" The original software's help for this block is Toshiba document "
                           "<b>%s</b>, which is not part of those manuals.") % html.escape(doc))
            out.append(msg)
        out.append(html.escape(BS.sim_status(self.code)))
        return out

    @staticmethod
    def _module_texts(mod):
        """3 doan chu cho khoi giao tiep card: vai tro, nguyen van spec, trang can xem them."""
        out = [html.escape(tr(mod.get("role") or ""))]
        if mod.get("quote"):
            page = tr(", page %s") % mod["quote_page"] if mod.get("quote_page") else ""
            out.append(tr("<b>From the %s%s:</b> %s")
                       % (html.escape(tr(mod.get("quote_from") or "spec")), page,
                          html.escape(tr(mod["quote"]))))
        if mod.get("more"):
            out.append(tr("<b>More detail:</b>") + "<br>" + "<br>".join(
                "&bull; " + html.escape(tr(m)) for m in mod["more"]))
        return [t for t in out if t]

    @staticmethod
    def _module_table(rows, mod):
        """Bang HTML 'Configuration of this block': so tham so, nhan, gia tri, y nghia."""
        cell = "style='padding:2px 8px 2px 0;vertical-align:top'"
        head = "".join("<th align='left' %s>%s</th>" % (cell, h)
                       for h in (tr("Param"), tr("Label"), tr("This block"), tr("What it is")))
        body = "".join(
            "<tr><td %s>%s</td><td %s><b>%s</b></td>"
            "<td %s><span style='color:#B45309'><b>%s</b></span></td><td %s>%s</td></tr>"
            % (cell, no, cell, html.escape(lbl), cell, html.escape(val), cell, html.escape(what))
            for no, lbl, val, what in rows)
        note = (mod or {}).get("params_note") or ""
        if note:
            note = "<br><span style='color:#777;font-size:9pt'>%s</span>" % html.escape(tr(note))
        lb = QLabel("<b>%s</b><table cellspacing='0'>%s%s</table>%s"
                    % (tr("Configuration of this block (parameters):"),
                       "<tr>%s</tr>" % head, body, note))
        lb.setTextFormat(Qt.TextFormat.RichText)
        lb.setWordWrap(True)
        lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return lb

    def _source_line(self, man, mod=None):
        """Dong 'Source: ...' nho o cuoi o: chu phia tren lay tu dau."""
        i = self.info
        src = []
        if i["how"]:
            run = tr("vendor DEF body + the model the simulator actually runs")
            if i["tmr"]:
                run += tr(" (timer family <b>%s</b>, time in <b>%s</b>)") % (i["tmr"],
                                                                             i["tunit"] or "s")
            elif i["op"]:
                run += tr(" (operation <b>%s</b>)") % i["op"]
            src.append(run)
        if man:
            src.append(tr("text copied from the Toshiba manual"))
        if mod:
            src.append(tr("card description from the project's DEHC hardware specification "
                          "and EHC logic printout"))
        return tr("Source: %s") % (" + ".join(src) or tr("block catalogue only"))

    # ---------- phan 2: ve lai khoi cho de hieu ----------
    def _diagram_slot(self):
        i = self.info
        g = QGroupBox(tr("Diagram"))
        v = QVBoxLayout(g)
        if i["mode"] == MODE_TIMING:
            why = self._ve_dang_song(v)
        elif i["mode"] == MODE_GATES:
            why = self._ve_cong_logic(v)
        elif i["mode"] == MODE_CURVE:
            why = self._ve_duong_cong(v)
        elif i["mode"] == MODE_FBD:
            why = self._ve_khoi_chuc_nang(v)
        else:
            why = i["mode_note"]
        if why:
            v.addWidget(self._cho_trong(why))
        return g

    def _cho_trong(self, why):
        """Khung bao KHONG ve duoc, kem ly do that. Tha noi thang la khong ve duoc con
        hon ve mot phan roi de nguoi doc tuong day la toan bo khoi."""
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        box.setStyleSheet("QFrame{border:1px dashed #9CA3AF;border-radius:6px;"
                          "background:#F9FAFB;}")
        bv = QVBoxLayout(box)
        name = self.info["mode_name"]
        t = QLabel(name if self.info["mode"] == MODE_NONE else tr("%s - not drawn") % name)
        f = QFont(); f.setBold(True); t.setFont(f)
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet("border:none;color:#374151")
        bv.addWidget(t)
        n = QLabel(why)
        n.setWordWrap(True)
        n.setAlignment(Qt.AlignmentFlag.AlignCenter)
        n.setStyleSheet("border:none;color:#6B7280")
        bv.addWidget(n)
        box.setMinimumHeight(84)
        return box

    def _ve_cong_logic(self, v):
        """So do cong logic noi, to mau bang gia tri that cua khoi. -> ly do neu khong ve."""
        from core.block_logic import gate_graph, eval_graph
        from ui.block_diagram import GateDiagram
        gg = gate_graph(self.code)
        if not gg["ok"]:
            return gg["why"]
        pv, pn = self._pin_state()
        d = GateDiagram(gg, pin_vals=pv, node_vals=eval_graph(gg, pv), pin_names=pn)
        v.addWidget(self._khung_cuon(d), 1)
        cap = (tr("Redrawn from the vendor logic body of this macro (%d instructions), not "
                  "from a hand-written description.") % gg["nlenh"])
        if pv:
            cap += "  " + tr("Wires carry the values running on this block right now: %s, "
                             "grey dashed = not known - the same colours as the sheet.") % _legend()
        else:
            cap += "  " + tr("No live values are available for this block, so the wires are grey.")
        v.addWidget(self._chu_thich(cap))
        return ""

    def _ve_khoi_chuc_nang(self, v):
        """So do khoi chuc nang noi, ve TRON MOT BAN. -> ly do neu khong ve.

        Truoc day ban ve bi cat theo tung chan ra cho de doc; nay cua so mo toan man hinh
        nen ve gop lai: cac nhanh dung chung nut hien ro la dung chung, thu ma ban cat roi
        khong the thay."""
        from core.block_fbd import fbd_graph, eval_bool
        from ui.block_fbd_view import FbdDiagram
        g = fbd_graph(self.code)
        if not g["ok"]:
            return g["why"]
        pv, pn, px, ps = self._pin_state_fbd()
        d = FbdDiagram(g, pin_vals=pv, node_vals=eval_bool(g, pv), pin_names=pn,
                       pin_nums=px, pin_sigs=ps, par_vals=self._tham_so(),
                       db_path=self.db_path)
        v.addWidget(self._khung_cuon(d), 1)

        if g["nlenh"] == 1:
            cap = tr("Redrawn from the vendor logic body of this macro (%d instruction), not "
                     "from a hand-written description.")
        else:
            cap = tr("Redrawn from the vendor logic body of this macro (%d instructions), not "
                     "from a hand-written description.")
        cap = (cap % g["nlenh"]) + "  " + tr("Every output pin of the block is on this one "
                                             "picture.")
        if pv or px:
            cap += "  " + tr("Digital wires carry the values running on this block right now: "
                             "%s - the same colours as the sheet.  Wires that carry a number, "
                             "and everything downstream of a timer or a latch, stay grey: their "
                             "value is not a 0/1 this diagram can state.") % _legend()
        else:
            cap += "  " + tr("No live values are available for this block, so the wires are grey.")
        v.addWidget(self._chu_thich(cap))
        return ""

    def _tham_so(self):
        """{PARAMNO: (ten, gia tri)} cai dat THAT cua chinh khoi nay.

        Bang "Settings of this block" da bo, ma ban ve lai co nut nguon ghi "parameter 3":
        khong kem gia tri thi doc xong van khong biet khoi nay dang cai bao nhieu."""
        if not (self.db_path and self.bid is not None):
            return {}
        try:
            hang = block_param_rows(self.db_path, self.bid, self.code)
        except Exception:
            return {}
        return {int(r["no"]): (str(r["name"] or ""), str(r["value"] or "").strip())
                for r in hang if str(r["value"] or "").strip() != ""}

    def _khung_cuon(self, d):
        """Ban ve: cao TRON BAN, chi cuon ngang.

        Ca than cua so da nam trong mot vung cuon chung nen o day khong cuon doc nua -
        hai thanh cuon long nhau thi keo mai khong biet minh dang o dau, va ban ve luon
        bi nhot trong mot khe hep. Chieu cao dat dung bang chieu cao that cua ban ve.

        Chieu ngang thi van phai cuon rieng: ban ve khoi tram rong toi ~3.900px, keo
        ngang ca trang thi doan chu ben tren troi theo, doc khong noi."""
        sc = QScrollArea()
        sc.setWidget(d)
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.Shape.StyledPanel)
        sc.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        sc.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Chua thu chieu rong khung nen chua biet co thanh cuon ngang hay khong: cu chua
        # san cho no. Thieu cho thi ban ve bi thanh cuon che mat hang duoi cung.
        sc.setFixedHeight(d.minimumHeight() + 2 * sc.frameWidth()
                          + sc.horizontalScrollBar().sizeHint().height())
        return sc

    def _ve_dang_song(self, v):
        """Gian do xung, chay bang chinh bo mo phong. -> ly do neu khong ve."""
        from core.block_timing import timing_wave
        from ui.block_diagram import TimingDiagram
        w = timing_wave(self.code, self.db_path, self.sheet_id, self.bid)
        if not w["ok"]:
            return w["why"]
        v.addWidget(TimingDiagram(w), 1)
        if w["T"] is None:
            cap = tr("This block has no time setting at all - the pulse lasts one "
                     "controller cycle.")
        else:
            t = (tr("%g min") % (w["T"] / 60.0) if w["tunit"] == "min" else tr("%g s") % w["T"])
            if w["toff"]:
                t += tr(" on, %g s off") % w["toff"]
            cap = ((tr("Drawn with the real setting of THIS block: <b>T = %s</b>.") % t)
                   if w["from_db"] else
                   (tr("The time setting of this block could not be read, so the shape is "
                       "drawn with an example value of <b>T = %s</b>.") % t))
        cap += "  " + w["note"]
        cap += "  " + tr("The waveform is produced by the same timer engine the simulator "
                         "runs, so it cannot drift from what Simulate shows.")
        v.addWidget(self._chu_thich(cap))
        return ""

    def _ve_duong_cong(self, v):
        """Duong dac tinh (hoac bang gia tri) cua khoi analog. -> ly do neu khong ve."""
        from core.block_curve import curve, KIND_XY, KIND_TABLE
        from ui.block_curve_view import CurveDiagram, ValueTable
        c = curve(self.code, self.db_path, self.sheet_id, self.bid, self._values())
        if not c["ok"]:
            return c["why"]
        v.addWidget(CurveDiagram(c) if c["kind"] == KIND_XY else ValueTable(c), 1)
        cap = ""
        if c["kind"] == KIND_XY:
            cap = (tr("Drawn with the real settings of THIS block, read from the project "
                      "file.") if c["from_db"] else
                   tr("Not every setting of this block could be read from the project file, "
                      "so part of the shape comes from a live value instead."))
        if c["note"]:
            cap = (cap + "  " + c["note"]).strip()
        if c.get("digital") and c["kind"] == KIND_XY:
            # Ghi chu cua lop du lieu da noi "dau ra la co 0/1" roi, o day chi noi them
            # phan MAU - nhac lai ca cau thanh ra doc hai lan cung mot y.
            cap += "  " + tr("0 and 1 use the sheet colours: %s.") % _legend()
        if c["kind"] == KIND_XY:
            cap += "  " + tr("The line is traced by pushing a sweep of input values through "
                             "the same evaluator the simulator runs, so it cannot drift from "
                             "what Simulate shows.")
        elif c["kind"] == KIND_TABLE:
            cap += "  " + tr("The formula comes from the vendor definition of this macro, and "
                             "the output is computed by the same evaluator the simulator runs.")
        else:
            cap += "  " + tr("The number is read through the same evaluator the simulator "
                             "runs, so it cannot drift from what Simulate shows.")
        v.addWidget(self._chu_thich(cap))
        return ""

    def _chu_thich(self, html):
        n = QLabel(html)
        n.setTextFormat(Qt.TextFormat.RichText)
        n.setWordWrap(True)
        n.setStyleSheet("color:#6B7280")
        return n

    def _pin_state(self):
        """({so chan: 0/1}, {so chan: ten}) cua DUNG khoi nay, de to mau ban ve.

        Chi lay chan VAO: gia tri chan ra de chinh ban ve suy ra tu cong logic, neu lay
        san tu ket qua mo phong thi khong con kiem tra cheo duoc gi nua."""
        pv, pn = {}, {}
        if self.bid is None:
            return pv, pn
        vals = self._values()
        for r in block_pin_rows(self.db_path, self.bid, self.code):
            if r["name"]:
                pn[r["no"]] = r["name"]
            if r["side"] != "in" or not r["net"]:
                continue
            x = vals.get(r["net"])
            if isinstance(x, bool):
                pv[r["no"]] = 1 if x else 0
            elif isinstance(x, (int, float)):
                pv[r["no"]] = 1 if x > 0.5 else 0
        return pv, pn

    def _pin_state_fbd(self):
        """({chan: 0/1}, {chan: ten}, {chan: so thuc}, {chan: ten tin hieu}).

        Khac _pin_state o cho khong ep gia tri so thanh 0/1: mot dau vao analog dang la
        100.0 ma to do nhu 'dang 1' thi doc sai han. So do khoi chuc nang co ca day so
        thuc lan day logic nen phai tach ro hai loai.

        Cot thu tu la ten tin hieu that: bang "Pins and the signals" da bo, ten do gio
        ghi thang duoi nhan chan tren ban ve."""
        pv, pn, px, ps = {}, {}, {}, {}
        if self.bid is None:
            return pv, pn, px, ps
        vals = self._values()
        for r in block_pin_rows(self.db_path, self.bid, self.code):
            no = r["no"]
            if r["name"]:
                pn[no] = r["name"]
            sig = r["net"] or ""
            if r["label"]:
                # Cot label trong db duoc dem khoang trang cho thang cot; giu nguyen thi
                # ten dai them ca tram px ma khong them chu nao doc duoc.
                sig = " ".join(("%s  %s" % (sig, r["label"])).split())
            x = vals.get(r["net"]) if r["net"] else None
            if r["side"] == "in":
                if isinstance(x, bool):
                    pv[no] = 1 if x else 0
                elif isinstance(x, (int, float)):
                    px[no] = float(x)
            elif isinstance(x, (int, float)) and not isinstance(x, bool):
                # Chan ra so thuc: mau day khong noi duoc gi, va bang tri so da bo, nen
                # con so phai di kem ten tin hieu neu khong la mat han.
                sig = ("%s = %s" % (sig, _fmt(x))).strip()
            ps[no] = sig or tr("(not wired)")
        return pv, pn, px, ps

    # ---------- phan 3: tham so THAT cua dung khoi nay ----------
    def _values(self):
        """{net: gia tri} dang hien ngoai sheet. Neu chua co thi tinh lai voi DUNG dau
        vao nguoi dung da dat - khong thi cot Value se trong tron."""
        if self._sim_values:
            return self._sim_values
        if self._cache_vals is None:
            self._cache_vals = {}
            if self.db_path and self.sheet_id is not None:
                try:
                    val, _it = SS.simulate(self.db_path, self.sheet_id,
                                           self._dig_env, self._ana_env)
                    self._cache_vals = val
                except Exception:
                    pass
        return self._cache_vals

    def _open_params(self):
        self.accept()
        self._on_params()
