# -*- coding: utf-8 -*-
"""O ve so do KHOI CHUC NANG cho cua so Help.

Dat rieng file vi ui/block_diagram.py da gan muc 800 dong toi da.

Ruot khoi duoc ve bang DUNG BO KY HIEU CUA HANG ma trang logic chinh dang dung
(core/symbol_shapes.json, ve qua ui/symbol_paint.py): cong AND la o vuong chu 'A',
OR la o chu 'OR', chuyen mach la o 'ASW', bo tre la o 'T:'... Nguoi mo Help thay
dung nhung hinh ho van doc hang ngay tren trang logic, khong phai hoc bo hinh thu hai.

Lop FbdDiagram KE THUA GateDiagram: giu nguyen cach xep cot, cach di day vuong goc va
quy uoc mau do/xanh. Chi thay phan VE THAN KHOI va DIEM NOI DAY.

Ma lenh nao khong co ky hieu tuong ung (FITG, chuyen mach nhieu duong da gop, chot uu
tien RESET - bo hinh cua hang khong co o FF/R hai chan) thi giu lai hop chu nhat co
nhan chu nhu truoc. Ve bua mot ky hieu gan dung con te hon la ve mot cai hop that tha.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRect, QRectF, QPointF
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QFontMetrics, QPainterPath

from .block_diagram import (GateDiagram, COL_BOX, COL_FILL, COL_NHAT, COL_NET,
                            COL_1, COL_0, _pen)
from . import symbol_paint as sp
import core.block_syms as bs
from core.block_curve import _so
from core.help_i18n import tr

COL_HOP = QColor("#EFF6FF")     # nen hop chuc nang - chi con dung cho ma khong co ky hieu
COL_MUX = QColor("#FFF7ED")     # nen chuyen mach
COL_KHUNG = QColor("#94A3B8")   # dai thuoc A-Z / 1-15 quanh ban ve

_CAO_O = 17.0       # chieu cao o dau day (bau duc o chan khoi, hop o hang so)
# Buoc luoi cua dai thuoc. Ban ve cua hang chia mot to thanh 27 cot x 15 hang; lay buoc
# xap xi the de mot ma co nhieu cot van doc duoc toa do kieu "cai OR o K6".
_O_W, _O_H = 132.0, 108.0


def _ten_cot(i):
    """0 -> A, 25 -> Z, 26 -> AA... dung cach danh cot cua ban ve cua hang."""
    s = ""
    while True:
        s = chr(65 + i % 26) + s
        i = i // 26 - 1
        if i < 0:
            return s

_TEN_HE = {"Ftime": "scan time", "Bsec_fc": "scans/sec", "Bmin_c": "scans/min",
           "Fsec_fc": "scans/sec"}

_MU = 18.0          # chieu cao dai tieu de tren dinh hop chuc nang (duong du phong)

# Ty le px tren mot don vi ban ve goc. Trang logic chinh dung 6.0; o day nho hon mot
# chut vi mot ma co toi 72 hop tren CUNG mot ban ve, con trang logic thi trai rong.
SC = 5.4

# Chan nam tren DINH hoac DAY ky hieu: day phai vong qua roi moi cam vao.
# _VONG la khoang cach tu mep khoi toi doan chay ngang; hai chan cung mot canh
# thi hai doan chay ngang phai le nhau _BUOC_VONG, khong thi chung de len nhau
# (F_RAL4_I va F_SHI2_I moi cai co hai chan duoi day).
_VONG, _BUOC_VONG = 8.0, 5.0

# Chu ghi duoi ky hieu cho hai op khong phai ham so hoc.
_PHU_SR = {"S": "set wins", "R": "reset wins"}


class FbdDiagram(GateDiagram):
    """Ve mot do thi tu core.block_fbd. Chi doc, khong sua duoc gi."""

    # Le trai/phai rong vi bang "Pins and the signals" da bo, ten tin hieu that duoc ghi
    # thang duoi nhan chan. Do tren 21 db: ten dai toi 423px, nhung 236px x 2 dong thi
    # 100% ten deu du cho, con ep mot dong thi 42% bi cat.
    _le_t, _le_p = 288, 276
    # Moi chan chiem 2 dong ten tin hieu + 1 dong nhan chan nen buoc hang phai gian ra.
    _hang, _cao_phu, _cao_nhan = 42, 21, 42
    # Khe ho phai chua duoc BA dong chu duoi ky hieu: ten ham, cong thuc, ten o dich.
    _khe = 38
    # Ky hieu cua hang keo doan day ra dai (ASW_T than 13 don vi, ca hinh 28) va ten
    # vai tro chan ghi ben TRAI chan, rong 47px - nen khe cot phai rong hon so do cong
    # logic. 46px la dung khe hep nhat ma buoc cot chung truoc day sinh ra.
    _khe_cot = 46
    # Ban ve giay cua hang ve NET LIEN va co dai thuoc A-Z / 1-15 quanh to giay. Ban ve
    # nay di theo: net dut chi con y nghia "chua biet 0/1" chu khong con lam roi mat.
    _net_lien = True
    _le_khung = 20

    def __init__(self, graph, pin_vals=None, node_vals=None, pin_names=None,
                 pin_nums=None, pin_sigs=None, par_vals=None, db_path=None,
                 parent=None):
        # db_path: db dang mo. Moi db duoc ve bang mot HO KY HIEU rieng (xem
        # core/block_syms.py): cong tac chon trong 01 UCS la F_TRA2_I con trong
        # 21 EHC la F_TRA1_I. Ve dung ho ma chinh db do dung thi nguoi doc nhan
        # ra hinh ngay; ve ho khac thi ho phai dich hinh sang hinh quen truoc.
        self.db = db_path
        # pin_nums: gia tri SO THUC dang chay o chan vao. Khong to mau duoc (khong phai
        # 0/1) nhung viet con so ra thi nguoi doc van doi chieu duoc voi ban ve chinh.
        # pin_sigs: ten tin hieu that dang noi vao chan, gop tu bang chan da bo di.
        self.pnum = dict(pin_nums or {})
        self.psig = {k: self._gon_ten(v) for k, v in (pin_sigs or {}).items()}
        # par_vals: {PARAMNO: (ten, gia tri)} - cai dat that cua khoi, ghi ngay duoi nut
        # nguon "parameter N" thay cho bang Settings da bo. Ghi o DONG PHU chu khong noi
        # vao dong chinh: "parameter 11 = -999999" da do 242px, qua 236px cho co.
        self.ppar = {k: self._gon_ten(("%s = %s" % (a, b)).strip(" ="))
                     for k, (a, b) in (par_vals or {}).items()}
        self._sc = SC
        self._kyc = {}                  # nho ky hieu da tra cuu, theo id nut
        self._byid = {b["id"]: b for b in graph["nodes"]}
        # So nhanh di ra tu moi nguon. Ban ve cua hang cham mot cham tron dac o cho day
        # re nhanh; khong co cham thi hai day cat nhau va day re nhanh trong y het nhau.
        self._nhanh = {}
        for b in graph["nodes"]:
            for _r, s in b["ins"]:
                self._nhanh[s] = self._nhanh.get(s, 0) + 1
        for s in graph["outs"].values():
            self._nhanh[s] = self._nhanh.get(s, 0) + 1
        # Vai ky hieu cua hang dua chan vao len DINH khoi (F_SUM2_I, ASW_T) hoac xuong
        # DAY khoi (F_SUM1_I, F_TRA1_I, F_RAL4_I - ho _I ma phan lon db dung). Day vao
        # nhung chan do phai vong qua mep khoi, ma ngay duoi moi khoi lai la ba dong chu
        # cua no: chu chiem 33px, doan vong them toi 18px nua. Noi khe ho doc ra cho du,
        # nhung CHI o ban ve that su co chan kieu do - bat moi ban ve cao them 14px nua
        # thi phi cho khong.
        if any(self._chan_ria(b) for b in graph["nodes"]):
            self._khe = 52
        super().__init__(graph, pin_vals=pin_vals, node_vals=node_vals,
                         pin_names=pin_names, parent=parent)

    # ---------- ky hieu cua hang ----------
    def _chan_ria(self, b):
        """Nut nay co chan vao nam tren DINH hoac DAY ky hieu khong."""
        return any(self._huong(b, i)[0] for i in range(len(b["ins"])))

    def _ky(self, b):
        """Ky hieu dung cho nut b, hoac None neu phai ve hop chu nhat."""
        nid = b["id"]
        if nid not in self._kyc:
            self._kyc[nid] = self._tim_ky(b)
        return self._kyc[nid]

    def _ho(self, khoa):
        """Ky hieu dau ho cho mot ma lenh, uu tien ban ma CHINH db nay dung nhieu nhat.

        Tra ve (ten ky hieu, thu tu chan) hoac (None, None) neu khong co ban nao co
        hinh. Danh sach ung vien va cach xep hang nam trong core/block_syms.py."""
        hinh = sp.shapes()
        for ten, thutu in bs.ung_vien(khoa, self.db):
            if ten in hinh:
                return ten, thutu
        return None, None

    def _tim_ky(self, b):
        op, n = b["op"], len(b["ins"])
        sym, thutu = None, None
        if op in ("AND", "OR") and 2 <= n <= 8:
            sym = "%s%d_I" % (op, n)
        elif op == "NOT" and n == 1:
            sym = "NOT_I"
        elif op == "XOR" and n == 2:
            sym = "XOR_I"
        elif op == "SR" and n == 2:
            # Hai uu tien la HAI HO KY HIEU RIENG cua hang (FLIP2/40BB uu tien SET,
            # FLIP1/FLIP3 uu tien RESET), khong phai mot hinh ghi them chu - nen chot
            # uu tien RESET nay cung co hinh chu khong con phai ve hop chu nhat.
            vai = [r for r, _s in b["ins"]]
            if vai.count("S") == 1 and vai.count("R") == 1:
                sym, thutu = self._ho("SR:R" if b.get("prio") == "R" else "SR:S")
        elif op == "MUX" and n == 3:
            sym, thutu = self._ho("MUX")
        elif op == "FN":
            sym, thutu = self._ho(b.get("ma") or "")
        shp = sp.shapes().get(sym) if sym else None
        if not shp:
            return None
        bb = sp.sym_bbox(shp)
        ps = sp.ports_of(shp)
        vao = [p for p in ps if p[2] == "in"]
        ra = [p for p in ps if p[2] == "out"]
        if op == "SR" and len(vao) >= 2:
            vt = {}
            for r, p in zip(sp.port_roles(shp, ps), ps):
                if p[2] == "in":
                    vt.setdefault(r, p)
            if "S" not in vt or "R" not in vt:
                # Ky hieu khong in chu S/R trong than -> theo quy uoc chung cua hang:
                # chan tren la SET, chan duoi la RESET (ports_of da xep tu tren xuong).
                vt = {"S": vao[0], "R": vao[1]}
            vao = [vt[r] for r, _s in b["ins"]]
        elif len(vao) != n or not ra:
            # Ky hieu goc co so stub khac so day that: vi du TON_T in san "T:" nhu mot
            # tham so, con o day thoi gian la mot day thuc su. Giu HINH cua hang, chi
            # rai lai diem noi deu tren canh trai - doi sang hinh khac thi nguoi doc
            # mat dung cai moc quen thuoc.
            bx, by, bw, bh = bb
            vao = [(bx, by + bh * (i + 1) / (n + 1.0), "in") for i in range(n)]
            ra = ra or [(bx + bw, by + bh / 2.0, "out")]
        elif thutu and len(thutu) == n:
            # Ky hieu cua hang xep chan theo NGHIA (o tich phan: X trai tren, T trai
            # duoi, chan giu tren dinh) con than lenh xep theo thu tu toan hang. Noi
            # thang theo thu tu mac dinh thi X cam vao chan giu - sai han phep tinh.
            vao = [vao[i] for i in thutu]
        if not ra:
            return None
        return {"sym": sym, "shp": shp, "bb": bb, "vao": vao, "ra": ra[0]}

    def _diem(self, b, ux, uy):
        """Doi toa do trong ky hieu sang toa do pixel tren ban ve."""
        x, y, _w, _h = self.hop[b["id"]]
        bx, by = self._ky(b)["bb"][0], self._ky(b)["bb"][1]
        return QPointF(x + (ux - bx) * self._sc, y + (uy - by) * self._sc)

    # ---------- kich thuoc ----------
    def _cao_cong(self, b):
        k = self._ky(b)
        if k:
            return max(24.0, k["bb"][3] * self._sc)
        if b["op"] in ("FN", "MUX"):
            # dai tieu de + mot dong cho moi dau vao
            return float(max(46, _MU + 17 * len(b["ins"]) + 8))
        if b["op"] == "NOT":
            return 26.0
        return float(max(30, 15 * len(b["ins"]) + 12))

    def _le_o(self, b):
        rong = self._rong_cong(b)
        # Nut ve HOP chu nhat viet chu BEN TRONG hop (xem _ve_hop) nen khong tran ra.
        d3 = self._chu_duoi(b) if self._ky(b) else ["", "", ""]
        if not any(d3):
            return 0.0, rong
        wb = self._than_o(b, rong)
        f = QFont()
        f.setPointSize(7)
        rc = 0.0
        for i, t in enumerate(d3):
            if not t:
                continue
            f.setBold(i == 0)
            rc = max(rc, QFontMetrics(f).horizontalAdvance(t) + 4.0)
        # Chu can giua theo THAN (xem _ve_than), nen no tran deu hai ben mep than.
        return max(0.0, (rc - wb) / 2.0), max(rong, (wb + rc) / 2.0)

    def _lech_chu(self, b):
        """Ba dong chu duoi khoi phai tut them bao nhieu de nhuong cho day chan day."""
        lech = 0.0
        for i in range(len(b["ins"])):
            huong, l = self._huong(b, i)
            if huong == "duoi":
                lech = max(lech, l + 5.0)
        return lech

    def _cao_duoi(self, b):
        """Dai ba dong chu duoi khoi cao bao nhieu - de ban ve chua du, khong cat mat.

        Dong cuoi cung con chu nam o hang thu (chi so + 1), moi hang 11px, ke tu
        y + h + 1 + _lech_chu (xem _ve_than)."""
        if self._ky(b) is None:
            return 0.0
        co = [i for i, t in enumerate(self._chu_duoi(b)) if t]
        if not co:
            return 0.0
        return 1.0 + self._lech_chu(b) + (co[-1] + 1) * 11.0

    def _than_o(self, b, rong):
        """Be ngang o THAN ky hieu - cai ma ba dong chu duoi khoi can giua theo."""
        k = self._ky(b)
        if not k:
            return rong
        wb = (k["shp"].get("w") or 0) * self._sc
        return rong if wb < 12 or wb > rong else wb

    def _rong_cong(self, b):
        k = self._ky(b)
        if k:
            return max(24.0, k["bb"][2] * self._sc)
        if b["op"] == "NOT":
            return 34.0
        if b["op"] in ("FN", "MUX"):
            return 128.0
        if b["op"] == "SR":
            return 62.0
        return float(self._rong_than)

    # ---------- diem noi ----------
    def _vao(self, b, i):
        k = self._ky(b)
        if k:
            ux, uy, _side = k["vao"][i]
            return self._diem(b, ux, uy)
        if b["op"] not in ("FN", "MUX"):
            return super()._vao(b, i)
        x, y, w, h = self.hop[b["id"]]
        n = len(b["ins"])
        return QPointF(x, y + _MU + (h - _MU) * (i + 1) / (n + 1.0))

    def _ra(self, src):
        b = self._byid.get(src)
        if b is not None and src in self.hop:
            k = self._ky(b)
            if k:
                return self._diem(b, k["ra"][0], k["ra"][1])
        return super()._ra(src)

    def _huong(self, b, i):
        """('tren'|'duoi'|'', do lech doc) cua chan vao thu i.

        Ky hieu cua hang cam chan o ca bon canh. Chan o DINH / DAY khoi thi day khong
        the di ngang toi: phai chay ngang qua phia tren (hoac phia duoi) khoi roi moi
        cam vao. Di thang nhu day thuong thi doan cuoi bo doc theo mep khoi hoac xuyen
        qua than, doc ra khong biet no cam vao dau."""
        k = self._ky(b)
        if not k:
            return "", 0.0
        bx, by, _bw, bh = k["bb"]
        ux, uy, side = k["vao"][i]
        # Chan sat mep TRAI van la chan di ngang binh thuong du no o goc tren cung.
        if side != "in" or ux <= bx + 0.5:
            return "", 0.0
        tren = uy <= by + 0.5
        if not tren and uy < by + bh - 0.5:
            return "", 0.0
        cung = [j for j, p in enumerate(k["vao"])
                if p[2] == "in" and p[0] > bx + 0.5
                and ((p[1] <= by + 0.5) if tren else (p[1] >= by + bh - 0.5))]
        return ("tren" if tren else "duoi"), _VONG + cung.index(i) * _BUOC_VONG

    # ---------- gia tri ----------
    def _gt(self, src):
        """Chi to mau khi CHAC CHAN la 0/1.

        Hang so 100.0 tren mot day so thuc ma to do nhu 'dang 1' thi doc sai han y nghia,
        nen chi hang so dung bang 0 hoac 1 moi duoc to."""
        if src.startswith("pin:"):
            return self.pv.get(int(src[4:]))
        if src.startswith("const:"):
            try:
                f = float(src[6:])
            except ValueError:
                return None
            return int(f) if f in (0.0, 1.0) else None
        return self.nv.get(src)

    # ---------- nhan ----------
    def _nhan_nguon(self, s):
        if s.startswith("par:"):
            return tr("parameter %s") % s[4:]
        if s.startswith("sys:"):
            return tr(_TEN_HE.get(s[4:], s[4:]))
        if s.startswith("ops:"):
            return tr("faceplate %s") % s[4:]
        if s.startswith("out:"):
            no = int(s[4:])
            ten = self.pn.get(no) or self.g["pin_out"].get(no) or ""
            return tr("%d %s (own output)") % (no, ten) if ten else tr("own output %d") % no
        return super()._nhan_nguon(s)

    def _gon_ten(self, t):
        """Cat ten tin hieu cho vua hai dong chu 7pt.

        Do tren 21 db thi 100% ten du cho, tru vai chan ra so thuc co ke them tri so o
        cuoi (vi du 40CA 'AJ1401 FUTUR THERMAL STRESS(HP SURFACE)(1 min) = 0'). Cat thi
        phai cat DOAN MO TA o giua: ma KKS dau chuoi va tri so cuoi chuoi la hai thu
        khong the mat, con Qt neu tu cat thi cat cut dung tri so do."""
        w = min(self._le_t - 52, self._le_p - 38)
        f = QFont()
        f.setPointSize(7)
        m = QFontMetrics(f)

        def vua(x):
            return m.boundingRect(QRect(0, 0, w, 400),
                                  int(Qt.TextFlag.TextWordWrap), x).height() <= self._cao_phu

        if vua(t):
            return t
        than, duoi = t, ""
        if " = " in t:
            than, so = t.rsplit(" = ", 1)
            duoi = " = " + so
        while len(than) > 12 and not vua(than + "..." + duoi):
            than = than[:-4]
        return than + "..." + duoi

    def _nhan_phu_nguon(self, s):
        if s.startswith("pin:"):
            return self.psig.get(int(s[4:]), "")
        if s.startswith("par:"):
            return self.ppar.get(int(s[4:]), "")
        return ""

    def _nhan_phu_ra(self, no, src):
        return self.psig.get(no, "")

    # ---------- dau day va khung, theo ban ve giay cua hang ----------
    def _rong_o(self, q, nhan, toi_da):
        """Be ngang o dau day vua khit chu, nhung khong duoc lan sang cot ky hieu."""
        w = QFontMetrics(q.font()).horizontalAdvance(nhan) + 16
        return float(min(max(w, 56.0), max(56.0, toi_da)))

    def _ve_o_dau(self, q, x, y, w, nhan, v, bau):
        """Mot o dau day, tam o cao do y.

        bau=True -> hinh BAU DUC: ban ve cua hang dung hinh nay cho tin hieu vao/ra cua
        khoi. bau=False -> HOP chu nhat: hang so, tham so cai dat, nut tren mat may -
        ban ve cua hang cung ve hop cho nhung thu do (o 'O', nhom 'OPS Operation')."""
        r = QRectF(x, y - _CAO_O / 2.0, w, _CAO_O)
        q.setPen(QPen(COL_1 if v else (COL_0 if v is not None else COL_BOX), 1.2))
        q.setBrush(QBrush(COL_FILL))
        if bau:
            q.drawRoundedRect(r, _CAO_O / 2.0, _CAO_O / 2.0)
        else:
            q.drawRect(r)
        q.setPen(QPen(COL_BOX, 1.0))
        q.drawText(r, int(Qt.AlignmentFlag.AlignCenter), nhan)
        q.setBrush(QBrush(Qt.BrushStyle.NoBrush))

    def _ve_cham(self, q, p, v, src=None):
        """Cham tron dac o cho mot duong re nhieu nhanh - dung quy uoc ban ve cua hang.

        Chi cham khi that su co tu HAI nhanh tro len: cham o moi dau ra thi ca ban ve
        day cham va cai cham khong con noi len dieu gi."""
        if src is not None and self._nhanh.get(src, 0) < 2:
            return
        q.setPen(Qt.PenStyle.NoPen)
        q.setBrush(QBrush(COL_1 if v else (COL_0 if v is not None else COL_NHAT)))
        q.drawEllipse(p, 2.8, 2.8)
        q.setBrush(QBrush(Qt.BrushStyle.NoBrush))

    def _ve_khung(self, q):
        """Dai thuoc A-Z ngang / 1-15 doc quanh ban ve, nhu khung to giay cua hang.

        Ve o he toa do CHUA dich (lop goc dich vao trong sau khi goi ham nay), nen o day
        (0, 0) la goc widget con (le, le) la goc ban ve."""
        R = float(self._le_khung)
        # Khung bam theo kich thuoc THAT cua widget khi no rong hon phan noi dung: ban ve
        # hep nam trong cua so mo toan man hinh, neu chi ke den mep noi dung thi khung
        # dung lung chung giua trang, khong con giong mep to giay nua.
        W = max(float(self._rong), self.width() - 2 * R)
        H = max(float(self._cao), self.height() - 2 * R)
        q.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        q.setPen(QPen(COL_KHUNG, 1.0))
        q.drawRect(QRectF(0.5, 0.5, W + 2 * R - 1, H + 2 * R - 1))
        q.drawRect(QRectF(R, R, W, H))
        f = q.font()
        f.setPointSize(7)
        q.setFont(f)
        giua = int(Qt.AlignmentFlag.AlignCenter)
        for i in range(max(1, int(-(-W // _O_W)))):
            x = R + i * _O_W
            wo = min(_O_W, W - i * _O_W)
            if i:
                q.setPen(QPen(COL_KHUNG, 1.0))
                q.drawLine(QPointF(x, 0), QPointF(x, R))
                q.drawLine(QPointF(x, R + H), QPointF(x, R + H + R))
            q.setPen(QPen(COL_NHAT, 1.0))
            q.drawText(QRectF(x, 0, wo, R), giua, _ten_cot(i))
            q.drawText(QRectF(x, R + H, wo, R), giua, _ten_cot(i))
        for j in range(max(1, int(-(-H // _O_H)))):
            y = R + j * _O_H
            ho = min(_O_H, H - j * _O_H)
            if j:
                q.setPen(QPen(COL_KHUNG, 1.0))
                q.drawLine(QPointF(0, y), QPointF(R, y))
                q.drawLine(QPointF(R + W, y), QPointF(R + W + R, y))
            q.setPen(QPen(COL_NHAT, 1.0))
            q.drawText(QRectF(0, y, R, ho), giua, str(j + 1))
            q.drawText(QRectF(R + W, y, R, ho), giua, str(j + 1))
        f.setPointSize(8)
        q.setFont(f)

    def _ve_nguon(self, q, s):
        """Dau day BEN TRAI. Chan cua khoi ve hinh bau duc co ten chan ben trong - dung
        hinh ma ban ve giay cua hang dung; ten tin hieu that ghi nho ngay duoi."""
        y = float(self.ytrai[s])
        x = self._le_t - 44             # diem day bat dau (lop goc dung dung so nay)
        mep = self._le_t - 52           # mep phai cua o dau day
        v = self._gt(s)
        nhan = self._nhan_nguon(s)
        w = self._rong_o(q, nhan, mep - 4)
        self._ve_o_dau(q, mep - w, y, w, nhan, v,
                       s.startswith("pin:") or s.startswith("out:"))
        q.setPen(self._but(v))
        q.drawLine(QPointF(mep, y), QPointF(x, y))
        self._ve_cham(q, QPointF(x, y), v, s)

        phu = self._nhan_phu_nguon(s)
        f = q.font()
        if phu:
            f.setPointSize(7)
            q.setFont(f)
            q.setPen(QPen(COL_NHAT, 1.0))
            # Ten tin hieu that dai toi 423px; ep mot dong la cat mat ma KKS dau chuoi.
            q.drawText(QRectF(2, y + _CAO_O / 2.0, mep - 2, self._cao_phu),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
                           | Qt.TextFlag.TextWordWrap), phu)
        # Tri so dang chay: 0/1 thi to mau, so thuc thi ghi den. Dat TREN doan day noi
        # vao o - trong o da co ten chan roi, nhet them so thi ten bi day ra khoi hinh.
        so, mau = None, COL_NET
        if v is not None:
            so, mau = str(v), (COL_1 if v else COL_0)
        elif s.startswith("pin:"):
            val = self.pnum.get(int(s[4:]))
            so = None if val is None else _so(val)
        if so:
            f.setPointSize(7)
            f.setBold(v is not None)
            q.setFont(f)
            q.setPen(QPen(mau, 1.0))
            # Ghi trong KHE giua o dau day va cot ky hieu dau tien (44px trong).
            # Dat de len o thi tri so va ten chan chong nhau, doc ra ca hai deu sai.
            q.drawText(QRectF(x + 2, y - 16, 42, 13),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       so)
            f.setBold(False)
        f.setPointSize(8)
        q.setFont(f)

    def _ve_ra(self, q, no, src):
        """Dau day BEN PHAI - cung hinh bau duc nhu chan vao. Doan day dan toi day da
        duoc ve tu truoc (xem paintEvent) de dong chu duoi khoi che duoc no."""
        v = self._gt(src)
        d = self._diem_ra(no, src)
        x2, y2 = d.x(), d.y()
        q.setPen(self._but(v))
        q.drawLine(QPointF(x2, y2), QPointF(x2 + 9, y2))
        ten = self.pn.get(no) or self.g["pin_out"].get(no) or ""
        nhan = "%d %s" % (no, ten) if ten else tr("pin %d") % no
        if v is not None:
            nhan += "  = %d" % v
        w = self._rong_o(q, nhan, self._rong - x2 - 11)
        self._ve_o_dau(q, x2 + 9, y2, w, nhan, v, True)
        phu = self._nhan_phu_ra(no, src)
        if not phu:
            return
        f = q.font()
        f.setPointSize(7)
        q.setFont(f)
        q.setPen(QPen(COL_NHAT, 1.0))
        q.drawText(QRectF(x2 + 9, y2 + _CAO_O / 2.0, self._rong - x2 - 11, self._cao_phu),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                       | Qt.TextFlag.TextWordWrap), phu)
        f.setPointSize(8)
        q.setFont(f)

    def _nhan_vai(self, q, b, i, vai):
        """Ten dau vao. Chuyen mach nhieu duong duoc danh so de doc duoc thu tu uu tien."""
        k = self._ky(b)
        if k and b["op"] == "SR":
            return          # moi ky hieu chot cua hang deu in san S/R ngay trong than
        if k and b["op"] == "MUX" and k["sym"] in bs.CO_SO_SAN:
            return          # o ASW/DSW in san so 1 / so 2; ho TRA thi khong, phai ghi
        if b["op"] == "MUX" and vai in ("if", "then"):
            n = i // 2 + 1
            vai = tr("if %d") % n if vai == "if" else tr("use %d") % n
        elif b["op"] == "MUX" and vai == "else":
            vai = tr("else")    # a, b, lim, mask... la ky hieu nen giu nguyen
        p = self._vao(b, i)
        huong, lech = self._huong(b, i) if k else ("", 0.0)
        f = q.font()
        f.setPointSize(7)
        q.setFont(f)
        q.setPen(QPen(COL_NHAT, 1.0))
        if huong:
            # Chan o dinh / day khoi: day vong sang TRAI roi cam vao, viet ten ben trai
            # thi ten nam lot giua khuyu day, doc ra nhu chu bi dong khung. Viet ben
            # PHAI, dung cao do voi doan day chay ngang - cho do chac chan con trong vi
            # doan day dung lai o chan chu khong chay tiep sang phai.
            yg = p.y() - lech if huong == "tren" else p.y() + lech
            q.drawText(QRectF(p.x() + 5, yg - 7, 47, 13),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       vai)
        elif k:
            # Ky hieu cua hang co net sat mep, khong con cho trong ben trong -> ghi ten
            # vai tro BEN NGOAI, ngay tren doan day dan vao.
            q.drawText(QRectF(p.x() - 50, p.y() - 15, 47, 13),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                       vai)
        else:
            q.drawText(QRectF(p.x() + 5, p.y() - 8, 48, 16),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       vai)
        f.setPointSize(8)
        q.setFont(f)

    # ---------- hinh ----------
    def _chu_duoi(self, b):
        """Ba dong chu ghi duoi ky hieu: ten ham, cong thuc, o dich."""
        op = b["op"]
        if op == "SR":
            return [tr("S-R latch"), tr(_PHU_SR.get(b.get("prio"), "set wins")), ""]
        if op == "MUX":
            # O cong tac ASW cua hang tu no da noi het: so 1 / so 2 in trong than, chan
            # dieu khien cam tren dinh. Ghi them "SELECT / on / off" chi lam ban ve ron
            # va noi rong cot ra vo ich, vi dong chu rong hon than o gan gap ba.
            return ["", "", ""] if self._ky(b) else ["SELECT", tr("on / off"), ""]
        if op == "FN":
            # Ban ve cua hang ghi o dich ngay duoi ky hieu trong ngoac nhon: "DT <TRC>",
            # "T <MSR>". Dung dung cach do thay cho mui ten "-> Rf001" tu nghi ra.
            return [b["nhan"], b["phu"],
                    ("<%s>" % b["dich"]) if b.get("dich") else ""]
        return ["", "", ""]

    def _ve_cong(self, q, b):
        self._ve_than(q, b)
        # Cham SAU khi ve than: ve truoc thi nen trang cua ky hieu quet mat cham.
        self._ve_cham(q, self._ra(b["id"]), self.nv.get(b["id"]), b["id"])

    def _ve_than(self, q, b):
        k = self._ky(b)
        if k is None:
            return self._ve_hop(q, b)
        x, y, w, h = self.hop[b["id"]]
        sp.paint(q, k["shp"], x, y, self._sc, col=sp.COL_SYM, nen=COL_FILL, ngoai=False)

        v = self.nv.get(b["id"])
        if v is not None:
            r = self._diem(b, k["ra"][0], k["ra"][1])
            q.setPen(QPen(COL_1 if v else COL_0, 1.0))
            f = q.font()
            f.setBold(True)
            q.setFont(f)
            q.drawText(QRectF(r.x() - 34, r.y() - 19, 32, 14),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                       str(v))
            f.setBold(False)
            q.setFont(f)

        ten, ct, dich = self._chu_duoi(b)
        if not (ten or ct or dich):
            return          # cong logic tron: hinh da noi het, them chu chi lam roi mat
        # Can chu theo THAN khoi, khong theo ca khung hinh: vai ky hieu (TON_T, DT_T...)
        # keo mot doan day ra dai gap doi than, can theo khung thi chu troi han sang phai
        # va khong con dinh vao cai hop nao ca.
        wb = self._than_o(b, w)
        f = q.font()
        f.setPointSize(7)
        q.setFont(f)
        # Khoi co chan o DAY thi doan day chay ngang nam ngay duoi khoi (xem _huong);
        # de chu o cho cu thi day cat thang qua dong ten ham. Day dai chu xuong duoi
        # doan day thay vi ep day di vong xa hon.
        yc = y + h + 1 + self._lech_chu(b)
        cx = x + wb / 2.0
        for i, (t, mau) in enumerate(((ten, COL_BOX), (ct, COL_NHAT), (dich, COL_NET))):
            if not t:
                continue
            f.setBold(i == 0)
            q.setFont(f)
            # Day di qua vung chu duoi khoi cat ngang than chu, doc ra nghia khac (Rf006
            # thanh Rf@06). Lot mot mieng trang vua khit dong chu - dung cach ky hieu
            # cua hang tu che day o sp.paint - roi moi viet len.
            wt = QFontMetrics(f).horizontalAdvance(t) + 4
            q.setPen(Qt.PenStyle.NoPen)
            q.setBrush(QBrush(COL_FILL))
            q.drawRect(QRectF(cx - wt / 2.0, yc + i * 11, wt, 11))
            q.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            q.setPen(QPen(mau, 1.0))
            # Do 432 nut co chu duoi tren 62 ma: dong dai nhat thua than khoi 117px,
            # nen cho 62px moi ben. Chu can giua theo than nen o rong hon khong lam
            # chu xe dich, chi thoi khong bi CAT. Da doi chieu 17.027 cap: khong o chu
            # nao de len chu hay than cua khoi ben canh o be rong that su can.
            q.drawText(QRectF(x - 62, yc + i * 11, wb + 124, 11),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), t)
        f.setBold(False)
        f.setPointSize(8)
        q.setFont(f)

    def _ve_chot(self, q, b):
        """Chot S-R uu tien RESET - bo ky hieu cua hang khong co o FF hai chan nao ghi
        dung uu tien do, nen ve hop chu nhat.

        Lop goc nhet ca ba dong "S-R / latch / RESET wins" vao trong hop 62x42: dong uu
        tien vua tran ra hai ben vien vua bi vien duoi cat ngang. Giu hai dong trong
        than, day dong uu tien xuong duoi hop - dung cho ma cac khoi co ky hieu dang ghi
        chu, nen ca ban ve doc theo mot kieu.
        """
        x, y, w, h = self.hop[b["id"]]
        q.setPen(QPen(COL_BOX, 1.4))
        q.setBrush(QBrush(COL_FILL))
        q.drawRoundedRect(QRectF(x, y, w, h), 4, 4)
        f = q.font()
        f.setBold(True)
        q.setFont(f)
        q.setPen(QPen(COL_BOX, 1.0))
        q.drawText(QRectF(x, y, w, h), int(Qt.AlignmentFlag.AlignCenter),
                   tr("S-R\nlatch"))
        f.setBold(False)
        f.setPointSize(7)
        q.setFont(f)
        q.setPen(QPen(COL_NHAT, 1.0))
        q.drawText(QRectF(x - 40, y + h + 1, w + 80, 11),
                   int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                   tr(_PHU_SR.get(b.get("prio"), "set wins")))
        f.setPointSize(8)
        q.setFont(f)

    def _ve_hop(self, q, b):
        """Hop chu nhat co nhan chu - dung cho ma khong co ky hieu tuong ung."""
        op = b["op"]
        if op == "SR":
            return self._ve_chot(q, b)
        if op in ("AND", "OR", "NOT", "XOR"):
            return super()._ve_cong(q, b)     # cong logic: hinh cua lop goc da du
        # Moi op CON LAI ve hop co ten. Truoc day cho "khac MUX" xuong lop goc, ma lop
        # goc chi biet 6 op cua so do cong logic: ham FN khong co ky hieu (FITG...) roi
        # vao nhanh cuoi cua no va bi ve thanh CONG OR - doc ra la mot phep hoac, sai
        # han nghia. Bo lay hop nhan chu, dung thu ban ve giay cua hang lam cho ham la.
        x, y, w, h = self.hop[b["id"]]
        if op == "MUX":
            nhanh = len(b["ins"]) // 2
            tren = "SELECT"
            duoi = tr("%d ways, first wins") % nhanh if nhanh > 1 else tr("on / off")
            nen = COL_MUX
        else:
            tren, duoi, nen = b["nhan"], b["phu"], COL_HOP
        # Than hop de trang nhu cong logic, chi DAI TIEU DE co mau - de tram cai hop
        # khong bien ban ve thanh mot mang mau kin.
        q.setPen(QPen(COL_BOX, 1.4))
        q.setBrush(QBrush(COL_FILL))
        q.drawRoundedRect(QRectF(x, y, w, h), 4, 4)
        q.setPen(Qt.PenStyle.NoPen)
        q.setBrush(QBrush(nen))
        q.drawRoundedRect(QRectF(x + 1, y + 1, w - 2, _MU), 4, 4)
        q.drawRect(QRectF(x + 1, y + _MU - 4, w - 2, 4.0))
        q.setPen(QPen(COL_BOX, 1.0))
        q.drawLine(QPointF(x, y + _MU), QPointF(x + w, y + _MU))

        f = q.font()
        f.setBold(True)
        q.setFont(f)
        q.drawText(QRectF(x + 3, y + 1, w - 6, _MU - 2),
                   int(Qt.AlignmentFlag.AlignCenter), tren)
        f.setBold(False)
        f.setPointSize(7)
        q.setFont(f)
        # Cong thuc va ten o dich nam DUOI hop: de trong hop thi chung tranh cho voi ten
        # dau vao, ma ten dau vao moi la thu bat buoc phai doc duoc.
        q.setPen(QPen(COL_NHAT, 1.0))
        q.drawText(QRectF(x - 24, y + h + 1, w + 48, 11),
                   int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop), duoi)
        if b.get("dich"):
            q.setPen(QPen(COL_NET, 1.0))
            q.drawText(QRectF(x - 24, y + h + 12, w + 48, 11),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                       "<%s>" % b["dich"])
        f.setPointSize(8)
        q.setFont(f)
