# -*- coding: utf-8 -*-
"""Tu dien tra cuu: cau hoi cua nguoi dung -> cac tu khoa THUC SU co trong DB.

Ly do can module nay: ban ve cua hang viet TAT gan nhu moi tu. Quet ca du an (21 DB,
4 bang ten) duoc 5.087 tu khac nhau, va dang day du hau nhu vang mat - 'PULV' 9.603
lan, 'IGNTR' 5.195, 'STRT' 4.467, 'FLW' 1.825, 'PRS' 1.668 - trong khi nguoi tra thi
go 'MILL', 'IGNITOR', 'START', 'FLOW', 'PRESSURE'. Vi du that: duong cong luu luong
nhien lieu khi khoi dong lo nguoi ten la 'FIRING RATE PROG FOR INIT COLD STRT-UP'
(01 UCS, sheet 105-06, khoi 10-019) - go dung cum 'INITIAL COLD START-UP' thi ra
RONG, phai go 'INIT' + 'COLD' moi thay.

Hai bang:
  VIET_ANH  tieng Viet -> tieng Anh (nguoi tra nghi bang tieng Viet, DB toan tieng Anh)
  VIET_TAT  day du <-> viet tat (DB viet tat, nguoi tra quen go day du)

Cach dung chinh:
  o_tra("initial cold")  ->  [['INIT'], ['CLD', 'COLD']]
Moi phan tu la 1 O; trong o cac tu THAY THE nhau. Ben tim CHAM DIEM theo so o khop
duoc (project_index.find_muc / find_bo) chu khong bat khop het - cau hoi cang day du
cang loc tot thay vi cang de tay trang.
  mo_rong("initial cold") -> [['INIT','CLD'], ['INIT','COLD']]  (trai o ra thanh tung
BO khop-het, dung khi can hien cho nguoi dung thay minh da tra nhung tu nao)

Bang o day chinh bang tay thoai mai - khong co gi sinh tu dong, khong co state.
"""
from __future__ import annotations

import itertools
import unicodedata

# Tieng Viet -> tieng Anh. KHOA da bo dau + VIET HOA san (mo_rong chuan hoa truoc khi
# tra). Gia tri la cac lua chon THAY THE nhau, moi cai sinh 1 bo tu khoa rieng.
# Chu co dau ghi o cuoi dong cho de doc khi can sua.
VIET_ANH = {
    "DANH LUA": ["IGNTR", "IGNITOR", "IGNITION"],       # danh lua
    "VOI DAU": ["IGNTR", "OIL GUN", "OIL BNR"],         # voi dau
    "VOI LUA": ["IGNTR", "IGNITOR"],                    # voi lua
    "TRINH TU": ["SEQ", "SEQUENCE", "PROG"],            # trinh tu
    "KHOI DONG": ["STRT", "START"],                     # khoi dong
    "NGUOI": ["COLD", "CLD"],                           # nguoi (lanh)
    "LANH": ["COLD", "CLD"],                            # lanh
    "NONG": ["HOT"],                                    # nong
    "MAY NGHIEN": ["PULV", "MILL"],                     # may nghien
    "NGHIEN": ["PULV", "MILL"],                         # nghien
    "LUU LUONG": ["FLW", "FLOW"],                       # luu luong
    "NHIEN LIEU": ["FUEL"],                             # nhien lieu
    "AP SUAT": ["PRS", "PRESS"],                        # ap suat
    "NHIET DO": ["TEMP"],                               # nhiet do
    "MUC NUOC": ["WTR LVL", "LVL"],                     # muc nuoc
    "NUOC CAP": ["FW", "FEEDWATER"],                    # nuoc cap
    "NUOC": ["WTR", "WATER"],                           # nuoc
    "LO HOI": ["BLR", "BOILER"],                        # lo hoi
    "TUA BIN": ["TURB", "TURBINE"],                     # tua bin
    "MAY PHAT": ["GEN"],                                # may phat
    "VONG BI": ["BRG", "BEARING"],                      # vong bi
    "BAO VE": ["PROT", "TRIP", "MFT"],                  # bao ve
    "SU CO": ["TRIP", "FAIL", "ABN"],                   # su co
    "CANH BAO": ["ALM", "ALARM"],                       # canh bao
    "BAT THUONG": ["ABN"],                              # bat thuong
    "DIEU KHIEN": ["CTRL", "CONTROL"],                  # dieu khien
    "CAI DAT": ["SETP", "SET"],                         # cai dat
    "NGUONG": ["SETP", "LM"],                           # nguong
    "CHO PHEP": ["PRMT", "PERMIT"],                     # cho phep
    "DIEU KIEN": ["CONDT", "CONDITION"],                # dieu kien
    "LIEN DONG": ["I/L", "INTERLOCK"],                  # lien dong
    "THOI SACH": ["PURGE"],                             # thoi sach
    "THOI BUI": ["SB", "BLOW"],                         # thoi bui
    "NGON LUA": ["FLM", "FLAME"],                       # ngon lua
    "TIN HIEU": ["SIG"],                                # tin hieu
    "TOC DO": ["SPD", "SPEED"],                         # toc do
    "GIOI HAN": ["LM", "LIMIT"],                        # gioi han
    "SAI LECH": ["DEVN"],                               # sai lech
    "VI TRI": ["POSN"],                                 # vi tri
    "CHE DO": ["MODE"],                                 # che do
    "CHUONG TRINH": ["PROG", "PRG"],                    # chuong trinh
    "GIA NHIET": ["HTR", "HEATER"],                     # gia nhiet
    "BOI TRON": ["LUB"],                                # boi tron
    "DAP LUA": ["MFT", "TRIP"],                         # dap lua (MFT)
    "KHONG KHI": ["AIR"],                               # khong khi
    "AM": ["WARM"],                                     # am
    "MUC": ["LVL", "LEVEL"],                            # muc
    "VAN": ["VLV", "VALVE"],                            # van
    "BOM": ["PUMP", "BFP"],                             # bom
    "QUAT": ["FAN", "FDF", "IDF", "PAF"],               # quat
    "RUNG": ["VIB"],                                    # rung
    "DAU": ["OIL", "FO"],                               # dau
    "THAN": ["COAL", "CL"],                             # than
    "GIO": ["AIR"],                                     # gio
    "HOI": ["STM", "STEAM"],                            # hoi
    "LO": ["BLR", "FURN"],                              # lo
    "LENH": ["CMD", "ORD"],                             # lenh
    "DUNG": ["STP", "S/D", "STOP"],                     # dung (may)
    "CHAY": ["RUN"],                                    # chay
    "MO": ["OPN", "OPEN"],                              # mo
    "TAI": ["LD", "LOAD"],                              # tai
    "TONG": ["TOT"],                                    # tong
    "CAO": ["HI"],                                      # cao
    "THAP": ["LO"],                                     # thap
    "PHUN": ["SPRY", "SPRAY"],                          # phun
    "KHOI": ["ESP", "DUST"],                            # khoi (bui)
    "BUONG LUA": ["FURN", "FURNACE"],                   # buong lua
    "QUA TAI": ["OVERLOAD", "OVER"],                    # qua tai - KHONG phai O/L,
    #                                                     O/L trong DB la OUTLET (2.212)
    "BINH NGUNG": ["CONDR", "COND"],                    # binh ngung
    "SAY KHONG KHI": ["AH"],                            # bo say khong khi
    "QUA NHIET": ["SH", "SECSH", "PRISH"],              # bo qua nhiet
    "TAI NHIET": ["RH"],                                # bo tai nhiet
    "HAM NUOC": ["ECO"],                                # bo ham nuoc
    "GIO CAP 1": ["PA", "PAF"],                         # gio cap 1
    "GIO CAP 2": ["SA", "SEC"],                         # gio cap 2
    "DONG DIEN": ["AMP", "CURR"],                       # dong dien
    "DIEN AP": ["VOLT", "PT"],                          # dien ap
    "CONG SUAT": ["MW", "PWR"],                         # cong suat
    "KICH TU": ["AVR", "FIELD"],                        # kich tu
    "BOI TRON DAU": ["LUB"],                            # dau boi tron
    "LAM MAT": ["COOL", "CLG"],                         # lam mat
    "DONG": ["CLS", "CLOSE"],                           # dong (van)
}

# Day du <-> viet tat. Chi ghi 1 chieu, _bang_tat() sinh chieu nguoc lai.
# Chi liet ke cap ma DB THUC SU dung - da doi chieu voi bang tan suat 5.087 tu.
VIET_TAT = {
    "INITIAL": ["INIT"], "COLD": ["CLD"], "START": ["STRT"],
    "STARTUP": ["STRT-UP", "START-UP"], "CONTROL": ["CTRL"], "FLOW": ["FLW"],
    "PRESSURE": ["PRS", "PRESS"], "TEMPERATURE": ["TEMP"], "DEMAND": ["DMD"],
    "PROGRAM": ["PROG", "PRG"], "SIGNAL": ["SIG"], "COMMAND": ["CMD"],
    "POSITION": ["POSN"], "VALVE": ["VLV"], "PULVERIZER": ["PULV"],
    "MILL": ["PULV"], "IGNITOR": ["IGNTR"], "MASTER": ["MSTR"],
    "SETPOINT": ["SETP"], "PERMIT": ["PRMT"], "PERMISSION": ["PRMT"],
    "CONDITION": ["CONDT"], "RESET": ["RST"], "SHUTDOWN": ["S/D"],
    "ABNORMAL": ["ABN"], "DEVIATION": ["DEVN"], "CORRECTION": ["CORRN"],
    "LIMIT": ["LM"], "LOAD": ["LD"], "STEAM": ["STM"], "WATER": ["WTR"],
    "BOILER": ["BLR"], "TURBINE": ["TURB"], "GENERATOR": ["GEN"],
    "ATOMIZING": ["ATOMG"], "WARMING": ["WARMG"], "SPEED": ["SPD"],
    "TOTAL": ["TOT"], "UPPER": ["UPR"], "LOWER": ["LWR"],
    "INTERLOCK": ["I/L"], "OUTLET": ["O/L"], "INLET": ["INL"],
    "INPUT": ["I/P"], "OUTPUT": ["O/P"], "CLEAN": ["CLN"], "DRAIN": ["DRN"],
    "SOOTBLOWER": ["SB"], "TRANSFER": ["TRANSF"], "EXHAUST": ["EXH"],
    "FURNACE": ["FURN"], "SELECT": ["SEL"], "SELECTION": ["SEL"],
    "DETECT": ["DET"], "BURNER": ["BNR"], "DAMPER": ["DMPR"],
    "LEVEL": ["LVL"], "BEARING": ["BRG"], "VIBRATION": ["VIB"],
    "MOTOR": ["MOT"], "POWER": ["PWR"], "HEATER": ["HTR"],
    "OPERATION": ["OPRT"], "ORDER": ["ORD"], "FLAME": ["FLM"],
    "SPRAY": ["SPRY"], "NORMAL": ["NORM"], "CYCLIC": ["CYC"],
    "UNIT": ["UNT"], "FEEDWATER": ["FW"], "COAL": ["CL"],
    "CLOSED": ["CLSD"], "CLOSE": ["CLS"], "OPEN": ["OPN"],
    "ALARM": ["ALM"], "STOP": ["STP"], "FAILURE": ["FLT"],
    "SEQUENCE": ["SEQ"], "AVERAGE": ["AVE"], "AUXILIARY": ["AUX"],
    "PROTECTION": ["PROT"], "REMOTE": ["RMT"], "COMPLETE": ["COMPL"],
}

# Tu qua chung: khong loc them duoc gi ma van nhan doi so to hop - bo khoi cau tra.
_BO_QUA = {"CUA", "CHO", "VA", "VOI", "TRONG", "O", "LA", "CAI", "CAC", "NHUNG",
           "THE", "NAO", "GI", "DE", "TU", "THI", "MA",
           "OF", "FOR", "AND", "TO", "IN", "ON", "IS", "BE"}
# CO Y khong bo "A": trong du an nay A/B/C/D/E la ma day thiet bi (PULV A, BSM_A,
# IGNTR A1.2), go "may nghien A" ma bo mat chu A thi ra ca 5 may.

_DAI_NHAT_CUM = 3       # cum tieng Viet dai nhat trong VIET_ANH la 2 tu, chua san 1 bac


def bo_dau(s):
    """Bo dau tieng Viet, doi d/D -> d/D thuong. 'danh lua' giu nguyen, 'do' -> 'do'."""
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


def _bang_tat():
    """VIET_TAT hai chieu. Can ca 2 chieu vi DB dung ca dang tat (STRT 4.467 lan) lan
    dang day du (FAILURE 2.664 lan), va nguoi tra co the go bat ky dang nao."""
    b = {}
    for day, tats in VIET_TAT.items():
        b.setdefault(day, []).extend(t for t in tats if t != day)
        for t in tats:
            if t != day:
                b.setdefault(t, []).append(day)
    return b


_TAT = _bang_tat()


def _gon(ds):
    """Bo trung, xep tu ngan truoc cho de doc.

    KHONG gop 'INITIAL' vao 'INIT' nua: ben tim khop theo BIEN TU chu khong phai chuoi
    con (xem project_index._quet), nen 'INIT' KHONG con khop duoc 'INITIAL' - gop lai
    la mat han mot dang. Ngay ca voi khop chuoi con thi viec gop cung sai voi cap
    OVER/OVERLOAD: 'OVER' khong duoc phep nuot 'OVERLOAD' vi hai tu khac nghia."""
    ra = []
    for x in sorted(set(ds), key=lambda t: (len(t), t)):
        ra.append(x)
    return ra


def _bien_the(tu):
    """Cac dang thay the duoc cua 1 tu don."""
    va = VIET_ANH.get(tu)
    if va:
        # Da co nghia tieng Anh thi THAY han tu goc. Giu lai ban tieng Viet chi ton to
        # hop: ten trong DB toan tieng Anh, 'DAU' chac chan 0 ket qua.
        return _gon(va)
    return _gon([tu] + _TAT.get(tu, []))


def _o_tra(s):
    """Chuoi da chuan hoa -> danh sach O, moi o la cac tu thay the nhau. Uu tien khop
    CUM dai truoc: 'may nghien' phai ra PULV chu khong phai MAY + NGHIEN."""
    # Ghep cum TRUOC roi moi bo tu chung: 'TU' va 'VOI' deu nam trong _BO_QUA, loc som
    # thi 'trinh tu' va 'voi dau' vo mat, ra ket qua sai han (do thanh TRINH + DAU).
    tu = [t for t in s.split() if t]
    o, i = [], 0
    while i < len(tu):
        for n in range(min(_DAI_NHAT_CUM, len(tu) - i), 1, -1):
            cum = " ".join(tu[i:i + n])
            if cum in VIET_ANH:
                o.append(_gon(VIET_ANH[cum]))
                i += n
                break
        else:
            if tu[i] not in _BO_QUA:
                o.append(_bien_the(tu[i]))
            i += 1
    return o


def o_tra(q):
    """Cau hoi -> danh sach O tu khoa: [['INIT'], ['CLD','COLD']].
    Trong 1 o cac tu THAY THE nhau (OR); giua cac o thi ben tim CHAM DIEM theo so o
    khop duoc, khong bat khop het - cau hoi day du kieu 'luu luong nhien lieu khoi
    dong nguoi' ra 4 o, ma khong ten nao trong DB chua ca 4."""
    s = bo_dau(q).upper().strip()
    return _o_tra(s) if s else []


def mo_rong(q, gioi_han=24):
    """Cau hoi -> danh sach cac BO tu khoa. Trong 1 bo: khop HET; giua cac bo: OR.

    gioi_han chan so bo sinh ra (moi bo la 1 cau SQL). Vuot thi cat bien the cua o
    dang co nhieu lua chon nhat, bo cai CUOI - tuc cai dai nhat sau _gon(), thuong la
    dang day du it xuat hien trong DB hon dang viet tat."""
    s = bo_dau(q).upper().strip()
    if not s:
        return []
    o = _o_tra(s)
    if not o:
        return []
    tong = 1
    for x in o:
        tong *= len(x)
    while tong > gioi_han:
        j = max(range(len(o)), key=lambda k: len(o[k]))
        if len(o[j]) <= 1:
            break
        tong = tong // len(o[j]) * (len(o[j]) - 1)
        o[j] = o[j][:-1]
    return [list(t) for t in itertools.product(*o)]
