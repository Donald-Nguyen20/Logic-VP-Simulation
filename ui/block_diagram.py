# -*- coding: utf-8 -*-
"""Hai o ve chi-doc cho cua so Help: cong logic noi va dang song thoi gian.

Duong dac tinh analog nam o ui/block_curve_view.py (tach ra cho moi file duoi 800 dong).

Mau day theo DUNG quy uoc cua ban ve chinh (ui/sheetview._sim_wire_pen): dang 1 la DO,
dang 0 la XANH LA. Neu o day dung mau khac thi nguoi dung mo Help ra doi chieu se thay
hai cua so noi nguoc nhau.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QPolygonF

from . import wire_lanes as wl
from core.help_i18n import tr

COL_1 = QColor("#DC2626")      # dang 1 - do, y het ban ve chinh
COL_0 = QColor("#16A34A")      # dang 0 - xanh la
COL_NA = QColor("#94A3B8")     # chua biet
COL_NET = QColor("#334155")
COL_BOX = QColor("#1E293B")
COL_FILL = QColor("#FFFFFF")
COL_NHAT = QColor("#64748B")
COL_DAY = QColor("#475569")    # day chua ro 0/1, ve net lien kieu ban ve giay
COL_NEN = QColor("#FCFCFD")


def _pen(v, day=2.0):
    """But ve theo gia tri 0/1/None."""
    if v is None:
        p = QPen(COL_NA, 1.3)
        p.setStyle(Qt.PenStyle.DashLine)
        return p
    return QPen(COL_1 if v else COL_0, day)


# ---------------------------------------------------------------- cong logic
_RONG = 52          # be ngang than cong
_COT = 108          # khoang cach giua hai cot cong
_HANG = 30          # khoang cach hai chan vao ke nhau
_LE_T, _LE_P = 96, 104


class GateDiagram(QWidget):
    """Ve do thi tu core.block_logic.gate_graph(). Khong sua duoc gi - chi de doc."""

    # De o dang thuoc tinh lop (khong phai hang module) de lop con noi rong duoc: so do
    # KHOI CHUC NANG co hop to va nhan dai hon nen can cot rong hon nhieu.
    _le_t, _le_p, _hang, _rong_than = _LE_T, _LE_P, _HANG, _RONG
    # Khe ho NGANG giua mep phai cot truoc va mep trai cot sau. Truoc day chi co buoc
    # cot chung _COT = 108 tren than rong 52, tuc khe 56; giu dung 56 de day va chu
    # khong bi chen hep hon truoc.
    _khe_cot = _COT - _RONG
    # Khe ho giua hai VUNG CHIEM ke nhau (than khoi cong ba dong chu duoi no). Nho hon
    # khe than nhieu: hai dong chu dat gan nhau van doc duoc, con hai than khoi sat nhau
    # thi ban ve roi.
    _khe_chu = 8
    _khe = 14           # khe ho doc giua DAY hop tren va DINH hop duoi
    _cao_phu = 12       # cho danh cho dong chu nho thu hai duoi nhan chan
    _cao_nhan = 20      # cho doc toi thieu cua MOT nhan chan ra
    # Day chua ro gia tri: ban ve cua hang ve NET LIEN het, ban ve nay ve dut. Lop con
    # bat co nay len de giong ban ve giay; lop goc giu net dut vi so do cong logic gan
    # nhu luon biet 0/1, day dut o do la ngoai le dang duoc chu y.
    _net_lien = False
    _le_khung = 0       # dai thuoc A-Z / 1-15 quanh ban ve (lop con bat len)

    def __init__(self, graph, pin_vals=None, node_vals=None, pin_names=None,
                 parent=None):
        super().__init__(parent)
        self.g = graph
        self.pv = dict(pin_vals or {})
        self.nv = dict(node_vals or {})
        self.pn = dict(pin_names or {})
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._bo_tri()
        self.setMinimumHeight(self._cao + 2 * self._le_khung)
        self.setMinimumWidth(self._rong + 2 * self._le_khung)

    # ---------- bo tri ----------
    def _muc(self):
        """Muc (cot) cua tung nut = duong di dai nhat tu chan vao toi no."""
        byid = {b["id"]: b for b in self.g["nodes"]}
        muc, dang = {}, set()

        def m(nid):
            if nid in muc:
                return muc[nid]
            if nid in dang:                      # vong hoi tiep cua chot: cat tai day
                return 0
            dang.add(nid)
            k = 0
            for _r, s in byid[nid]["ins"]:
                if s in byid:
                    k = max(k, m(s) + 1)
            dang.discard(nid)
            muc[nid] = k
            return k

        for nid in byid:
            m(nid)
        return muc

    def _bo_tri(self):
        g = self.g
        muc = self._muc()
        self._cotnut = dict(muc)
        nmuc = (max(muc.values()) + 1) if muc else 1
        lop_ns = [[b for b in g["nodes"] if muc[b["id"]] == k] for k in range(nmuc)]

        cao_trai = self._cot_ngoai()
        # Thu tu ba buoc nay QUAN TRONG: cao do khong phu thuoc x, con be ngang hanh lang
        # thi phu thuoc so lan day chay doc trong do - ma muon biet so lan lai phai biet
        # cao do truoc. Nen xep doc -> chia lan -> moi xep ngang.
        self._xep_doc(lop_ns)
        cao_trai += self._day_xuong()
        self._lan, self._nlan = self._chia_lan(lop_ns)
        xcot, xk, truoc = self._xep_ngang(lop_ns)
        self.hop = {k: (xcot[muc[k]], v[1], v[2], v[3]) for k, v in self.hop.items()}
        self._xlan = {(c, ng): xcot[c] - wl.LE - j * wl.BUOC
                      for (c, ng), j in self._lan.items()}

        self._xep_ra()
        cao_nut = max([self.hop[b["id"]][1] + self.hop[b["id"]][3] + self._cao_duoi(b)
                       for b in g["nodes"]] or [60])
        cao_ra = max(list(self.yra.values()) or [0]) + self._cao_nhan
        self._cao = int(max(cao_trai, cao_nut, cao_ra) + 24)
        self._rong = int(max(xk - self._khe_cot, truoc or 0) + self._le_p)

    def _cao_duoi(self, b):
        """Chieu cao phan ve THEM ben duoi than khoi (lop con ghi chu thi bat len)."""
        return 0.0

    def _cot_ngoai(self):
        """Cot trai: cac chan vao + thanh ghi trong, theo dung thu tu so chan."""
        byid = {b["id"] for b in self.g["nodes"]}
        ngoai = []
        for b in self.g["nodes"]:
            for _r, s in b["ins"]:
                if s not in byid and s not in ngoai:
                    ngoai.append(s)
        ngoai.sort(key=lambda s: (0, int(s[4:])) if s.startswith("pin:") else (1, s))
        self.ngoai = ngoai
        self.ytrai = {}
        y = 24
        for s in ngoai:
            self.ytrai[s] = y
            y += self._hang
        return max(y - self._hang + 24, 60)

    def _cao_vao(self, b, i):
        """Cao do doan CHAY NGANG cua day vao chan thu i (chan tren/duoi thi la doan
        vong, khong phai cao do chan)."""
        huong, lech = self._huong(b, i)
        y = self._vao(b, i).y()
        return y - lech if huong == "tren" else (y + lech if huong == "duoi" else y)

    def _dung_day(self, b, dara):
        """Cao do hien tai cua b co lam doan ngang nao de len day cua NGUON KHAC khong.

        dara: {cao do lam tron -> tap nguon dang chiem cao do do}. Xet ca dau ra (doan
        ngang chay tu dau ra sang lan doc) lan tung chan vao (doan ngang tu lan doc vao
        chan). Cung mot nguon thi khong tinh: do la day re nhanh, nam chung mot duong
        la dung."""
        yr = round(self._ra(b["id"]).y())
        if any(dara.get(yr + d) for d in (-1, 0, 1)):
            return True
        for i, (_r, s) in enumerate(b["ins"]):
            yv = round(self._cao_vao(b, i))
            if any(dara.get(yv + d, frozenset()) - {s} for d in (-1, 0, 1)):
                return True
        return False

    def _xep_doc(self, lop_ns):
        """Cao do tung nut = trung binh cao do cac dau vao, roi day xuong cho khong
        chong nhau. Chua biet x nen tam dat x = 0; _bo_tri ghi de sau."""
        self.hop = {}
        # Cao do cac dau ra da dung, kem nguon chiem no. Buoc "day xuong cho khong chong
        # nhau" ben duoi chi lam trong PHAM VI MOT COT, nen hai nut o hai cot khac nhau
        # van hay trung cao do - khi do hai doan day chay ngang tu hai dau ra do nam de
        # len nhau va doc ra tuong mot day. Xe ra vai px la du tach ma bo cuc khong xo
        # lech.
        dara = {}
        for k, v in self.ytrai.items():
            dara.setdefault(round(v), set()).add(k)
        for lop in lop_ns:
            tam = []
            for b in lop:
                ys = []
                for _r, s in b["ins"]:
                    if s in self.hop:
                        ys.append(self.hop[s][1] + self.hop[s][3] / 2.0)
                    elif s in self.ytrai:
                        ys.append(self.ytrai[s])
                tam.append((sum(ys) / len(ys) if ys else 40.0, b))
            tam.sort(key=lambda t: t[0])
            day = None                       # day cua hop dat truoc do trong cot
            for yc, b in tam:
                h = self._cao_cong(b)
                if day is not None:
                    # Phai cong CA nua chieu cao hop truoc lan hop nay; chi lay nua hop
                    # nay thi hai hop cao bang nhau se de len nhau (thay ro o hop chuc
                    # nang, vi chung cao gap doi cong logic).
                    yc = max(yc, day + self._khe + h / 2.0)
                w = self._rong_cong(b)
                self.hop[b["id"]] = (0.0, yc - h / 2.0, w, h)
                for _ in range(8):
                    if not self._dung_day(b, dara):
                        break
                    yc += 3.0
                    self.hop[b["id"]] = (0.0, yc - h / 2.0, w, h)
                dara.setdefault(round(self._ra(b["id"]).y()), set()).add(b["id"])
                day = yc + h / 2.0

    def _day_xuong(self):
        """Keo ca ban ve xuong neu co hop nao am. Tra ve so px da day."""
        dy = min([v[1] for v in self.hop.values()] or [24])
        if dy >= 12:
            return 0
        d = 12 - dy
        self.hop = {k: (v[0], v[1] + d, v[2], v[3]) for k, v in self.hop.items()}
        self.ytrai = {k: v + d for k, v in self.ytrai.items()}
        return d

    def _chia_lan(self, lop_ns):
        """Xin mot lan doc cho moi day can be goc, theo hanh lang ben trai cot dich."""
        yc = []
        for k, lop in enumerate(lop_ns):
            for b in lop:
                for i, (_r, s) in enumerate(b["ins"]):
                    ay = self._ra(s).y()
                    p = self._vao(b, i)
                    huong, lech = self._huong(b, i)
                    by = p.y() - lech if huong == "tren" else (
                        p.y() + lech if huong == "duoi" else p.y())
                    if not huong and abs(ay - by) < 0.6:
                        continue        # day thang tap, khong co doan doc nao de xep
                    yc.append((k, s, min(ay, by), max(ay, by)))
        return wl.xep(yc)

    def _xep_ngang(self, lop_ns):
        """Moc x cua tung cot. Moi cot mot buoc RIENG, theo be ngang that cua cot do.

        Dung mot buoc chung cho ca ban ve thi cot nao cung rong bang cot rong nhat, ma
        cot 0 thuong chua ca chuc cong con cac cot sau chi con mot nut: do o 820D tong
        be ngang than that la 2340px trong khi buoc chung an 20 x 197 = 3940px, thua gan
        1600px giay trang lam nguoi doc phai keo ngang.

        Ba rang buoc: THAN cot sau cach than cot truoc dung _khe_cot; VUNG CHIEM (than
        cong ba dong chu tran ra hai ben) cua hai cot khong duoc dinh nhau; va hanh lang
        truoc cot phai du rong cho tat ca lan day chay doc trong do. Chi dung rang buoc
        dau thi 10 o chu de len than khoi cot ben canh (do tren 62 ma); chi dung rang
        buoc thu hai thi cot toan cong logic bi noi ra vo co.
        """
        xcot, xk, truoc = [], float(self._le_t), None
        than_p = float(self._le_t) - 44          # mep phai cua cot nguon ben trai
        for k, lop in enumerate(lop_ns):
            le = [self._le_o(b) for b in lop] or [(0.0, float(self._rong_than))]
            trai = max(t for t, _p in le)
            phai = max(p for _t, p in le)
            if truoc is not None:
                xk = max(xk, truoc + trai + self._khe_chu)
            xk = max(xk, than_p + wl.be_rong(self._nlan.get(k, 0)))
            xcot.append(xk)
            truoc = xk + phai
            rong = max([self._rong_cong(b) for b in lop] or [self._rong_than])
            than_p = xk + rong
            xk += rong + self._khe_cot
        return xcot, xk, truoc

    def _xep_ra(self):
        """Cao do NHAN cua tung chan ra, day xuong cho khong de len nhau.

        Nhieu chan ra cua mot khoi thuong dung chung MOT nut ben trong (do o 62 ma
        MODE_FBD: 33 cap nhan cach nhau duoi 42px, trong do 8 cap cach dung 0px - vi du
        8225 chan 16 va 18). Lay thang cao do cua nut thi hai nhan in de khit len nhau,
        doc ra mot dong be bet. Day xuong roi noi day gay khuc thi van thay ro chung
        cung mot nguon."""
        byid = {b["id"] for b in self.g["nodes"]}
        ds = sorted((self._ra(src).y(), no) for no, src in self.g["outs"].items()
                    if src in byid or src in self.ytrai)
        self.yra, truoc = {}, None
        for y, no in ds:
            if truoc is not None and y - truoc < self._cao_nhan:
                y = truoc + self._cao_nhan
            self.yra[no] = y
            truoc = y

    def _cao_cong(self, b):
        if b["op"] == "NOT":
            return 26.0
        return float(max(30, 15 * len(b["ins"]) + 12))

    def _le_o(self, b):
        """(cho phai chua ben TRAI moc x, cho phai chua ben PHAI moc x) cua mot nut.

        Bo tri cot theo hai so nay chu khong theo be ngang hop: lop con viet ba dong chu
        NGAY DUOI ky hieu va can giua theo than, dong dai co the thua than 117px - tuc
        tran ra hai ben gan 60px moi ben. Lay be ngang hop lam moc thi chu do de len
        than khoi cot ben canh."""
        return 0.0, self._rong_cong(b)

    def _rong_cong(self, b):
        if b["op"] == "NOT":
            return 34.0
        if b["op"] in ("SR", "SELECT"):
            return 62.0
        return float(self._rong_than)

    # ---------- but ve ----------
    def _but(self, v, day=2.0):
        """But cho mot doan day. Tach ra khoi ham _pen de lop con doi kieu net duoc."""
        if v is None and self._net_lien:
            # Mau day chua ro gia tri. Nhat hon net ky hieu mot bac de khong dua voi
            # than khoi, nhung van dam hon COL_NHAT (mau chu phu) de theo duoc day dai
            # 4.000px chay ngang ban ve.
            return QPen(COL_DAY, 1.1)
        return _pen(v, day)

    def _ve_khung(self, q):
        """Dai thuoc / khung quanh ban ve, ve trong he toa do CHUA dich. Lop goc bo trong."""
        return

    # ---------- gia tri ----------
    def _gt(self, src):
        if src.startswith("pin:"):
            return self.pv.get(int(src[4:]))
        if src.startswith("const:"):
            return int(src[6:])
        return self.nv.get(src)

    # ---------- diem noi ----------
    def _ra(self, src):
        if src in self.hop:
            x, y, w, h = self.hop[src]
            return QPointF(x + w, y + h / 2.0)
        return QPointF(self._le_t - 44, float(self.ytrai.get(src, 24)))

    def _vao(self, b, i):
        x, y, w, h = self.hop[b["id"]]
        n = len(b["ins"])
        dx = 3.0 if b["op"] in ("OR", "XOR") else 0.0
        return QPointF(x + dx, y + h * (i + 1) / (n + 1.0))

    def _huong(self, b, i):
        """('tren'|'duoi'|'', do lech doc) cua chan vao thu i.

        Chan nam tren DINH hoac DAY khoi thi day phai vong qua phia tren / phia duoi
        khoi roi cam vao, chu khong the di ngang toi duoc. Cong logic khong co chan
        kieu do; lop con (ky hieu cua hang) thi co nhieu."""
        return "", 0.0

    # ---------- ve ----------
    def paintEvent(self, ev):
        q = QPainter(self)
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        q.fillRect(self.rect(), COL_NEN)
        self._ve_khung(q)
        # Ve khung o he toa do goc, roi moi dich vao trong: nho vay toan bo phan bo tri
        # (self.hop, self.ytrai, self.yra) khong phai biet dai thuoc rong bao nhieu.
        q.translate(self._le_khung, self._le_khung)
        f = QFont(); f.setPointSize(8); q.setFont(f)
        byid = {b["id"]: b for b in self.g["nodes"]}

        for s in self.ngoai:
            self._ve_nguon(q, s)
        for b in self.g["nodes"]:
            k = self._cotnut.get(b["id"])
            for i, (_r, s) in enumerate(b["ins"]):
                huong, lech = self._huong(b, i)
                self._ve_day(q, self._ra(s), self._vao(b, i), self._gt(s),
                             src=s, cot=k, huong=huong, lech=lech)
        # Day chay ra le phai cung phai ve TRUOC than khoi: no bang qua ca ban ve nen
        # rat hay di trung dong chu duoi mot khoi nao do o giua (ro nhat la "max(a, lim)"
        # cua khoi LOW LIMIT). Ve truoc thi mieng nen trang cua dong chu che duoc no.
        for no, src in sorted(self.g["outs"].items()):
            if src in byid or src in self.ytrai:
                self._ve_day(q, self._ra(src), self._diem_ra(no, src), self._gt(src))
        for b in self.g["nodes"]:
            self._ve_cong(q, b)
        # Ten vai tro (S, R, sel, a, b, if 1...) phai ve SAU than hop: no nam ben trong
        # vien hop, ve truoc thi bi nen hop to de len va mat hut.
        for b in self.g["nodes"]:
            for i, (r, _s) in enumerate(b["ins"]):
                if r != "in":
                    self._nhan_vai(q, b, i, r)
        for no, src in sorted(self.g["outs"].items()):
            if src in byid or src in self.ytrai:
                self._ve_ra(q, no, src)
        q.end()

    def _lo_day(self, a, b, src=None, cot=None, huong="", lech=0.0):
        """Danh sach diem (x, y) cua mot day, tu nguon a toi chan b.

        Doan doc dat trong hanh lang ben trai cot dich (xem ui/wire_lanes.py). Khong xin
        duoc lan - vi du day di giat lui cua vong hoi tiep chot - thi quay ve trung diem
        nhu cu."""
        xm = self._xlan.get((cot, src))
        if xm is None:
            xm = (a.x() + b.x()) / 2.0
        if not huong and abs(a.y() - b.y()) < 0.6:
            return [(a.x(), a.y()), (b.x(), b.y())]
        if not huong:
            return [(a.x(), a.y()), (xm, a.y()), (xm, b.y()), (b.x(), b.y())]
        yg = b.y() - lech if huong == "tren" else b.y() + lech
        return [(a.x(), a.y()), (xm, a.y()), (xm, yg), (b.x(), yg), (b.x(), b.y())]

    def _ve_day(self, q, a, b, v, src=None, cot=None, huong="", lech=0.0):
        q.setPen(self._but(v))
        q.setBrush(Qt.BrushStyle.NoBrush)
        pts = self._lo_day(a, b, src, cot, huong, lech)
        if len(pts) == 2:
            q.drawLine(a, b)
            return
        p = QPainterPath(QPointF(*pts[0]))
        for x, y in pts[1:]:
            p.lineTo(x, y)
        q.drawPath(p)

    def _nhan_nguon(self, s):
        """Chu ghi ben trai cho mot nguon. Tach rieng de lop con doi duoc."""
        if s.startswith("pin:"):
            no = int(s[4:])
            ten = self.pn.get(no) or self.g["pin_in"].get(no) or ""
            return "%d %s" % (no, ten) if ten else tr("pin %d") % no
        if s.startswith("reg:"):
            return tr("%s (internal)") % s[4:]
        return s.split(":")[-1]

    def _nhan_phu_nguon(self, s):
        """Dong chu nho thu hai duoi nhan chan vao (lop con dung cho ten tin hieu). Lop
        goc khong co gi de noi them nen tra ve rong -> ban ve cong logic giu nguyen."""
        return ""

    def _nhan_phu_ra(self, no, src):
        """Nhu tren, nhung cho chan ra."""
        return ""

    def _ve_nguon(self, q, s):
        y = float(self.ytrai[s])
        x = self._le_t - 44
        v = self._gt(s)
        nhan = self._nhan_nguon(s)
        phu = self._nhan_phu_nguon(s)
        q.setPen(QPen(COL_NET, 1.0))
        dy = self._cao_phu // 2 if phu else 0
        q.drawText(QRectF(2, y - 9 - dy, self._le_t - 52, 18),
                   int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), nhan)
        if phu:
            f = q.font(); f.setPointSize(7); q.setFont(f)
            q.setPen(QPen(COL_NHAT, 1.0))
            # Ten tin hieu that dai toi 423px o cac db thuc te; ep mot dong la cat mat
            # dau chuoi (AlignRight cat ben trai) - dung ma KKS. Cho ngat dong.
            q.drawText(QRectF(2, y + 9 - dy, self._le_t - 52, self._cao_phu),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
                           | Qt.TextFlag.TextWordWrap), phu)
            f.setPointSize(8); q.setFont(f)
        q.setPen(self._but(v))
        q.setBrush(QBrush(COL_1 if v else COL_0) if v is not None else QBrush(COL_NA))
        q.drawEllipse(QPointF(x, y), 3.0, 3.0)
        if v is not None:
            f = q.font(); f.setBold(True); q.setFont(f)
            q.setPen(QPen(COL_1 if v else COL_0, 1.0))
            q.drawText(QRectF(x + 4, y - 18, 26, 14),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       str(v))
            f.setBold(False); q.setFont(f)

    def _diem_ra(self, no, src):
        """Cham tron cuoi day o le phai. Nhan da bi day xuong cho khoi de len nhan khac
        nen y cua no khong con bang y dau ra -> day la duong gay khuc."""
        return QPointF(self._rong - self._le_p + 30,
                       float(self.yra.get(no, self._ra(src).y())))

    def _ve_ra(self, q, no, src):
        v = self._gt(src)
        d = self._diem_ra(no, src)
        x2, y2 = d.x(), d.y()
        q.setPen(self._but(v)); q.setBrush(Qt.BrushStyle.NoBrush)
        q.setBrush(QBrush(COL_1 if v else COL_0) if v is not None else QBrush(COL_NA))
        q.drawEllipse(QPointF(x2, y2), 3.0, 3.0)
        ten = self.pn.get(no) or self.g["pin_out"].get(no) or ""
        nhan = "%d %s" % (no, ten) if ten else tr("pin %d") % no
        if v is not None:
            nhan += "  = %d" % v
        phu = self._nhan_phu_ra(no, src)
        dy = self._cao_phu // 2 if phu else 0
        q.setPen(QPen(COL_1 if v else (COL_0 if v is not None else COL_NET), 1.0))
        f = q.font(); f.setBold(v is not None); q.setFont(f)
        q.drawText(QRectF(x2 + 6, y2 - 9 - dy, self._rong - x2 - 8, 18),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), nhan)
        f.setBold(False); q.setFont(f)
        if phu:
            f.setPointSize(7); q.setFont(f)
            q.setPen(QPen(COL_NHAT, 1.0))
            q.drawText(QRectF(x2 + 6, y2 + 9 - dy, self._rong - x2 - 8, self._cao_phu),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                           | Qt.TextFlag.TextWordWrap), phu)
            f.setPointSize(8); q.setFont(f)

    def _nhan_vai(self, q, b, i, vai):
        """Ten dau vao co y nghia rieng (S, R, sel, 1, 0) - thieu no thi khong biet day
        nao la SET day nao la RESET."""
        p = self._vao(b, i)
        q.setPen(QPen(COL_NHAT, 1.0))
        q.drawText(QRectF(p.x() + 3, p.y() - 8, 16, 16),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), vai)

    def _ve_cong(self, q, b):
        x, y, w, h = self.hop[b["id"]]
        op = b["op"]
        v = self.nv.get(b["id"])
        q.setPen(QPen(COL_BOX, 1.4))
        q.setBrush(QBrush(COL_FILL))
        if op == "NOT":
            q.drawPolygon(QPolygonF([QPointF(x, y), QPointF(x + w - 9, y + h / 2),
                                     QPointF(x, y + h)]))
            q.drawEllipse(QPointF(x + w - 5, y + h / 2), 4.0, 4.0)
            return
        if op in ("SR", "SELECT"):
            q.drawRoundedRect(QRectF(x, y, w, h), 4, 4)
            f = q.font(); f.setBold(True); q.setFont(f)
            q.setPen(QPen(COL_BOX, 1.0))
            if op == "SR":
                # Uu tien doc tu THU TU LENH trong than goc cua hang, khong doan theo ten
                t = tr("S-R\nlatch\n%s wins") % ("RESET" if b.get("prio") == "R" else "SET")
            else:
                t = tr("2-way\nswitch")
            q.drawText(QRectF(x, y, w, h), int(Qt.AlignmentFlag.AlignCenter), t)
            f.setBold(False); q.setFont(f)
            return
        if op == "AND":
            r = min(h, w * 1.6)
            p = QPainterPath(QPointF(x, y))
            p.lineTo(x + w - r / 2, y)
            p.arcTo(QRectF(x + w - r, y, r, h), 90, -180)
            p.lineTo(x, y + h)
            p.closeSubpath()
            q.drawPath(p)
        else:                                   # OR / XOR - cung than, XOR them mot cung
            p = QPainterPath(QPointF(x, y))
            p.quadTo(x + w * 0.6, y, x + w, y + h / 2)
            p.quadTo(x + w * 0.6, y + h, x, y + h)
            p.quadTo(x + w * 0.3, y + h / 2, x, y)
            q.drawPath(p)
            if op == "XOR":
                a = QPainterPath(QPointF(x - 6, y))
                a.quadTo(x + w * 0.3 - 6, y + h / 2, x - 6, y + h)
                q.setBrush(Qt.BrushStyle.NoBrush)
                q.drawPath(a)
        if v is not None:
            q.setPen(QPen(COL_1 if v else COL_0, 1.0))
            f = q.font(); f.setBold(True); q.setFont(f)
            q.drawText(QRectF(x + w * 0.12, y + h / 2 - 8, w * 0.6, 16),
                       int(Qt.AlignmentFlag.AlignCenter), str(v))
            f.setBold(False); q.setFont(f)


# ---------------------------------------------------------------- dang song
class TimingDiagram(QWidget):
    """Ve ket qua core.block_timing.timing_wave(). Khong sua duoc gi."""

    def __init__(self, wave, parent=None):
        super().__init__(parent)
        self.w = wave
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(160)

    def _fmt(self, t):
        if self.w.get("tunit") == "min":
            return "%g" % round(t / 60.0, 2)
        return "%g" % round(t, 2)

    def paintEvent(self, ev):
        w = self.w
        q = QPainter(self)
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        q.fillRect(self.rect(), COL_NEN)
        if not w.get("ok") or not w["t"]:
            q.end()
            return
        f = QFont(); f.setPointSize(8); q.setFont(f)

        L, R, TOP = 78.0, 18.0, 18.0
        W = max(60.0, self.width() - L - R)
        tmax = w["t"][-1] or 1.0
        yx, yy, bien = TOP + 4, TOP + 62, 22.0

        def px(t):
            return L + W * t / tmax

        self._ve_hang(q, w["x"], w["t"], px, yx, bien, tr("Input"), L)
        self._ve_hang(q, w["y"], w["t"], px, yy, bien, tr("Output"), L)

        # truc thoi gian. Chua san cho o duoi duong ra: dau do cua ho PG/1SH nam o do,
        # de sat qua thi nhan de len chinh duong tin hieu, doc ra hai thu chong nhau.
        ytruc = yy + bien + 34
        q.setPen(QPen(QColor("#CBD5E1"), 1.0))
        q.drawLine(QPointF(L, ytruc), QPointF(L + W, ytruc))
        for k in range(5):
            t = k * tmax / 4.0
            q.setPen(QPen(QColor("#CBD5E1"), 1.0))
            q.drawLine(QPointF(px(t), ytruc - 3), QPointF(px(t), ytruc + 3))
            q.setPen(QPen(COL_NHAT, 1.0))
            q.drawText(QRectF(px(t) - 26, ytruc + 3, 52, 14),
                       int(Qt.AlignmentFlag.AlignCenter), self._fmt(t))
        q.setPen(QPen(COL_NHAT, 1.0))
        q.drawText(QRectF(2, ytruc + 3, L - 10, 14),
                   int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                   tr("time (%s)") % ("min" if w.get("tunit") == "min" else "s"))

        for t0, t1, nhan, hang in w.get("marks", []):
            ym = (yx + bien + yy) / 2.0 if hang == 0 else yy + bien + 10
            self._ve_dau(q, px(t0), px(t1), ym, nhan, hang == 0)
        q.end()

    def _ve_hang(self, q, a, ts, px, y0, bien, ten, L):
        """Mot duong xung: 1 o tren, 0 o duoi. Mau doi theo dung gia tri tung doan."""
        q.setPen(QPen(COL_NHAT, 1.0))
        q.drawText(QRectF(2, y0 + bien / 2 - 8, L - 10, 16),
                   int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), ten)
        q.setPen(QPen(QColor("#E2E8F0"), 1.0))
        q.drawLine(QPointF(L, y0 + bien), QPointF(px(ts[-1]), y0 + bien))
        for i in range(1, len(a)):
            v = a[i - 1]
            q.setPen(_pen(v, 2.2))
            yv = y0 if v else y0 + bien
            q.drawLine(QPointF(px(ts[i - 1]), yv), QPointF(px(ts[i]), yv))
            if a[i] != v:
                q.setPen(_pen(a[i], 2.2))
                q.drawLine(QPointF(px(ts[i]), y0), QPointF(px(ts[i]), y0 + bien))

    def _ve_dau(self, q, x0, x1, y, nhan, tren=True):
        """Mui ten hai dau danh dau doan thoi gian T - de nguoi doc thay so trong bang
        tham so nam dung cho nao tren hinh. tren=False thi nhan xuong duoi mui ten:
        dau do o hang duoi sat duong ra, dat nhan len tren la de chu vao dung duong."""
        q.setPen(QPen(QColor("#FCD34D"), 1.0))
        d = 14.0 if tren else 10.0
        for x in (x0, x1):
            q.drawLine(QPointF(x, y - d), QPointF(x, y + d))
        q.setPen(QPen(QColor("#B45309"), 1.2))
        q.drawLine(QPointF(x0, y), QPointF(x1, y))
        for x, d in ((x0, 1), (x1, -1)):
            q.drawLine(QPointF(x, y), QPointF(x + 5 * d, y - 3))
            q.drawLine(QPointF(x, y), QPointF(x + 5 * d, y + 3))
        f = q.font(); f.setBold(True); q.setFont(f)
        q.drawText(QRectF(min(x0, x1) - 34, (y - 17) if tren else (y + 3),
                          abs(x1 - x0) + 68, 14),
                   int(Qt.AlignmentFlag.AlignCenter), nhan)
        f.setBold(False); q.setFont(f)
