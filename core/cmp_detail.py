# -*- coding: utf-8 -*-
"""NGUONG THAT cua 1 khoi so sanh analog, viet ra thanh cau doc duoc.

Ban cu chi in "<ten day vao> >= <param 2>". Voi 87% khoi so sanh cua du an
(3700/4237) the la du, nhung 537 khoi con lai co param 2 = 0 nen cau in ra thanh vo
nghia kieu "c6 >= 0". Ly do: khoi so sanh dat NGAY SAU khoi TRU hoac TRI TUYET DOI -
no so HAI TIN HIEU voi nhau chu khong so voi mot con so. ~80% so khoi nguong-0 la
kieu do (54% qua |X|, 26% qua DIF).

Vi du that - 06 BPS A, sheet 314 "BT-124 MFT ITEM":
    cu :  c6 >= 0
    moi:  SPR I/L MANF FLUID TEMP A >= SPR INL MAINF TEMP(MFT)(SDT O/L STM PRS)
          (set), hieu <= -5 degC (reset)
          Fx-1  SPR INL MAINF TEMP(MFT):  MPa -> degC
            0->363  5->363  8.4->392  ...  30->471
Nguong o day la mot DUONG CONG theo ap suat chu khong phai con so co dinh, nen in
luon cum diem gay khuc de tra cuu tai cho, khoi phai mo sheet.

Ngoai ra lay dung DON VI (param 4) - truoc day doc nham o CAD_ID.SENSOR cua day
vao, ma day trung gian thi khong co ban ghi do, do duoc 0/242 nhan lay duoc don vi -
va DIEM TRO VE (param 3). Ten macro cua hang goi 2 tham so nay la "S & R": S = Set
(nguong tac dong), R = Reset (nguong nha), deu la tri so tuyet doi cung don vi.
Giu nguyen 2 chu Set / Reset cua hang khi in ra, de nguoi doc doi chieu thang duoc
voi ban ve va tai lieu goc - va de khong ai doc nham thanh do tre thoi gian.

Van con 705/4276 khoi in ra ma net tho, va khong phai loi cua module nay: 504 cai
co day vao KHONG CO khoi nao tren sheet sinh ra (tin hieu tu sheet khac / card vao,
DB khong dat ten tren sheet nay), 201 cai con lai la mot bieu thuc so hoc that su
(ADD 48, SELECT 83, WSUM 32, MUL 22...) - muon in phai viet han bo dung bieu thuc,
khong nam trong pham vi ban nay. Tang do sau lan nguoc khong an gi: do voi sau = 2,
4 va 6 deu ra dung 705.

Chi doc DB, khong sua gi.
"""
from __future__ import annotations

from . import sheet_sim as SS
from . import signal_graph as SG

REL_TXT = {">=": "≥", "<=": "≤", ">": ">", "<": "<", "==": "="}

# Chieu NHA cua khoi so sanh la chieu nguoc lai chieu TAC DONG: len o 250 thi phai
# tut xuong duoi diem tro ve moi nha. '=' khong co chieu nguoc nen bo qua.
_NGUOC = {"≥": "≤", ">": "<", "≤": "≥", "<": ">"}

# DB ghi "-" cho tin hieu khong co don vi (dem cai, ty le...) - in ra thi rac mat
_KHONG_DON_VI = {"", "-", "--", "n/a"}

_MOI_DONG = 6           # so diem gay khuc in tren 1 dong cho de doc


def _so(v):
    """So thuc -> chuoi ngan: 30.0 -> '30', 8.4 -> '8.4'."""
    try:
        return "%g" % float(v)
    except (TypeError, ValueError):
        return str(v)


def don_vi(u):
    """Don vi ky thuat, bo cac ky hieu 'khong co don vi' ma DB hay ghi."""
    u = (u or "").strip()
    return "" if u.lower() in _KHONG_DON_VI else u


def _nhan_pass(code):
    """Nhan ngan cua 1 khoi "di thang" (op PASS trong analog_sem): 'ATA', 'DEAD TIME',
    '|>', 'DB'... Nhom PASS gom ca link thuan tuy lan khoi CO tac dung (han bien, vung
    chet, tre 1 chu ky) nen di xuyen qua ma khong ghi lai la noi doi: mach giam sat CPU
    o 01 UCS sheet 64 la 'AR2000 - ATA(AR2000)', bo chu ATA di thi thanh 'X - X'."""
    nm = ((SS._analog_sem().get(code) or {}).get("name") or "").strip()
    return nm.split(" - ")[0].strip() or code


def _ten(db, sheet, net, fxs, sau=2):
    """Ten doc duoc cua 1 tin hieu analog. Khong co ten thi lan nguoc toi khoi sinh ra
    no: F(x) -> ten duong cong (va ghi cum diem vao `fxs` de in kem), hang so -> tri
    so, khoi noi tiep -> di xuyen qua. Het cach thi tra ma net tho."""
    nm = (SG._name_of(db, sheet, net) or "").strip() if net else ""
    if nm:
        return nm
    ap = SS._analog_producers(db, sheet).get(net) if net else None
    if not ap or sau <= 0:
        return net or "?"
    op = ap.get("op")
    ins = ap.get("ins") or []
    if op == "PASS" and ins:
        trong = _ten(db, sheet, ins[0]["net"], fxs, sau - 1)
        return "%s(%s)" % (_nhan_pass(ap.get("code")), trong)
    if op == "CONST":
        v = SS._num((SS._params(db, sheet).get(ap["bid"], {})).get("2"))
        return _so(v) if v is not None else (net or "?")
    if op == "FUNC":
        fx = SS.func_info(db, sheet, ap["bid"])
        fx["arg"] = _ten(db, sheet, ins[0]["net"], fxs, sau - 1) if ins else ""
        fxs.append(fx)
        ten = fx["name"] or fx["tag"] or "F(x)"
        return "%s(%s)" % (ten, fx["arg"]) if fx["arg"] else ten
    return net or "?"


def _don_vi_tin_hieu(db, sheet, net):
    """Du phong khi khoi so sanh khong ghi don vi: don vi cua chinh tin hieu do
    (CAD_ID.SENSOR dang '0 100 %'). Chi an voi day CO TEN - day trung gian thi rong."""
    if not net:
        return ""
    try:
        from . import dbreader as D2
        r = D2.connect(db).cursor().execute(
            "SELECT SENSOR FROM CAD_ID WHERE ID=? AND SIGNALID=?", (sheet, net)).fetchone()
        phan = ((D2._clean(r[0]) if r else "") or "").split()
        return don_vi(phan[-1]) if len(phan) >= 2 else ""
    except Exception:
        return ""


def _ve_trai(db, sheet, innet, fxs):
    """Ve trai cua phep so sanh. Khoi TRU / TRI TUYET DOI phai bung ra thanh "A - B"
    hay "|A - B|" - do moi la dieu kien that, chu "c6" thi khong noi len dieu gi.
    Tra (chuoi, cap) - cap = (A, B) khi la phep tru THUAN, luc do nguong 0 doc gon
    lai duoc thanh "A >= B"; None trong moi truong hop khac."""
    ap = SS._analog_producers(db, sheet).get(innet) if innet else None
    op = (ap or {}).get("op")
    ins = (ap or {}).get("ins") or []
    if op == "ABS" and ins:
        return "|%s|" % _ve_trai(db, sheet, ins[0]["net"], fxs)[0], None
    if op == "SUB" and len(ins) >= 2:
        a = next((d["net"] for d in ins if d.get("name") == "+"), ins[0]["net"])
        b = next((d["net"] for d in ins if d.get("name") == "-"), ins[1]["net"])
        cap = (_ten(db, sheet, a, fxs), _ten(db, sheet, b, fxs))
        return "%s - %s" % cap, cap
    return _ten(db, sheet, innet, fxs), None


def fx_dong(fx):
    """Cum F(x) cua 1 khoi, dang nhieu dong de dan vao chu thich:
        Fx-1  SPR INL MAINF TEMP(MFT)  (theo SDT O/L STM PRS):  MPa -> degC
          0->363   5->363   8.4->392 ...
    """
    dau = "  ".join(x for x in (fx.get("tag"), fx.get("name")) if x) or "F(x)"
    if fx.get("arg"):
        dau += "  (theo %s)" % fx["arg"]
    xu, yu = don_vi(fx.get("xunit")), don_vi(fx.get("yunit"))
    if xu or yu:
        dau += ":  %s -> %s" % (xu or "?", yu or "?")
    pts = fx.get("pts") or []
    dong = [dau]
    for i in range(0, len(pts), _MOI_DONG):
        dong.append("   " + "   ".join("%s->%s" % (_so(x), _so(y))
                                       for x, y in pts[i:i + _MOI_DONG]))
    return "\n".join(dong)


def describe(db, sheet, net):
    """Doc 1 net LA DAU RA khoi so sanh -> {'text', 'fx', 'note'}; None neu net do
    khong phai dau ra khoi so sanh nao.
      text = 1 dong ngan gon dat thang vao nhan (co don vi + diem set/reset)
      fx   = danh sach cum F(x) tham gia lam nguong (thuong rong)
      note = text + cac cum F(x) trai ra, de lam chu thich / xuat tai lieu"""
    c = SS.cmp_blocks(db, sheet).get(net)
    if not c:
        return None
    fxs = []
    trai, cap = _ve_trai(db, sheet, c["innet"], fxs)
    r = REL_TXT.get(c["rel"], c["rel"] or "so sanh")
    dv = don_vi(c["unit"]) or _don_vi_tin_hieu(db, sheet, c["innet"])
    thr = c["thr"]
    if thr is None:
        txt = "%s %s nguong (dong)" % (trai, r)
    elif cap and thr == 0:
        # "A - B >= 0" chinh la "A >= B" - viet thang ra cho khoi phai nham trong dau
        txt = "%s %s %s" % (cap[0], r, cap[1])
    else:
        txt = "%s %s %s%s" % (trai, r, _so(thr), (" " + dv) if dv else "")
    # param 3 la diem TRO VE (Reset) - tri so tuyet doi cung don vi, khong phai thoi
    # gian va khong phai do rong vung tre. Bang nguong tac dung thi khong co vung tre,
    # in ra chi lam nhieu (2882/4204 khoi cua du an roi vao truong hop nay).
    ve_lai = _NGUOC.get(r)
    if c["reset"] is not None and c["reset"] != thr and ve_lai:
        # dang gon "A >= B" da giau mat phep tru, nen phai noi ro diem tro ve do tren
        # HIEU cua 2 ve - lap lai ca 2 ten thi dong dai gap doi, khong doc noi
        dau = "hieu " if (cap and thr == 0) else ""
        txt += " (set), %s%s %s%s (reset)" % (dau, ve_lai, _so(c["reset"]),
                                              (" " + dv) if dv else "")
    note = "\n".join([txt] + [fx_dong(f) for f in fxs])
    return {"text": txt, "fx": fxs, "note": note}
