# -*- coding: utf-8 -*-
"""Cau hoi (TIENG ANH) -> cac tu khoa THUC SU co trong ban ve.

Vi sao chi tieng Anh: doi chieu tren cung mot bo cau hoi, tra bang tieng Anh sai 3/14,
tra bang tieng Viet sai 11/12 khi ra ngoai von tu da liet ke. Nguyen nhan khong phai
thieu tu ma la BO DAU: "dung/dung", "van/van", "no/no", "do/do", "tai/tai" thu ve cung
mot chuoi, nen may khong the phan biet - va no tra ra ket qua SAI MA CHAC CHAN ("tu
dung" -> "dung" -> STOP -> "BC IDF F-STP"), thu nguy hiem hon la khong tra gi. Ten
trong DB von 100% tieng Anh, nen bo lop tieng Viet la bo dung nut that.

Viec con lai cua module: ban ve viet TAT gan het moi tu. Quet 21 DB duoc 5.868 tu khac
nhau, dang day du hau nhu vang mat - PULV 8.035 lan / MILL 14, IGNTR 4.462 / IGNITER 0,
STRT 3.529, FLW 1.579 / FLOW 278. Vi du that: duong cong luu luong nhien lieu khi khoi
dong lo nguoi ten la 'FIRING RATE PROG FOR INIT COLD STRT-UP' (01 UCS, sheet 105-06,
khoi 10-019) - go dung cum 'INITIAL COLD START-UP' thi ra RONG.

Ba bang, tat ca deu DO tren corpus that (project_index.tan_suat), khong doan:
  TU_TAT  day du <-> viet tat, 1 tu
  CUM     cum nhieu tu -> 1 viet tat ("AIR HEATER" -> AH, "FEEDWATER PUMP" -> BFP)
  _BO_QUA tu ngu phap tieng Anh, khong mang thong tin tra cuu

Cach dung:
  o_tra("initial cold start-up")  ->  [['INIT', 'INITIAL'], ['CLD', 'COLD'], [...]]
Moi phan tu la 1 O; trong o cac tu THAY THE nhau. Ben tim CHAM DIEM theo so o khop
duoc (project_index.find_muc / find_bo) chu khong bat khop het.
"""

# Tu nao ca `muc` lan `sig` deu 0 lan xuat hien thi KHONG dua vao bang: no chi lam
# loang diem chu khong bao gio khop duoc gi. Da do va loai bo: DRUM, SEPARATOR,
# CONVEYOR, ECON, OVLD, SWGR, SCANNER, EXC, FWH, LPH, HPH - khong ton tai trong 4 CPU
# nay (UCS / BMS_A / BMS_B / EHC-MC).
TU_TAT = {
    # --- trinh tu / dieu khien ---------------------------------------------
    "INITIAL": ["INIT"], "COLD": ["CLD"], "START": ["STRT"],
    "STARTUP": ["STRT-UP", "START-UP"], "CONTROL": ["CTRL"],
    "PROGRAM": ["PROG", "PRG"], "SIGNAL": ["SIG"], "COMMAND": ["CMD"],
    "SEQUENCE": ["SEQ"], "PERMIT": ["PRMT"], "PERMISSION": ["PRMT"],
    "CONDITION": ["CONDT"], "RESET": ["RST"], "SHUTDOWN": ["S/D"],
    "INTERLOCK": ["I/L"], "OPERATION": ["OPRT"], "ORDER": ["ORD"],
    "SELECT": ["SEL"], "SELECTION": ["SEL"], "DETECT": ["DET"],
    "COMPLETE": ["COMPL"], "CYCLIC": ["CYC"], "REMOTE": ["RMT"],
    "MANUAL": ["MAN"], "AUTOMATIC": ["AUTO"], "TRANSFER": ["TRANSF"],
    # --- dai luong do ------------------------------------------------------
    "PRESSURE": ["PRS", "PRESS"], "TEMPERATURE": ["TEMP"], "FLOW": ["FLW"],
    "LEVEL": ["LVL"], "SPEED": ["SPD"], "VIBRATION": ["VIB"],
    "POSITION": ["POSN", "POS"], "DEMAND": ["DMD"], "SETPOINT": ["SETP"],
    "DEVIATION": ["DEVN"], "CORRECTION": ["CORRN"], "LIMIT": ["LM"],
    "LOAD": ["LD"], "TOTAL": ["TOT"], "AVERAGE": ["AVE"],
    "UPPER": ["UPR"], "LOWER": ["LWR"], "NORMAL": ["NORM"],
    "ABNORMAL": ["ABN"], "VACUUM": ["VAC"],
    # --- thiet bi lo hoi ---------------------------------------------------
    "BOILER": ["BLR"], "FURNACE": ["FURN"], "STEAM": ["STM"], "WATER": ["WTR"],
    "FEEDWATER": ["FW"], "COAL": ["CL"], "MILL": ["PULV"],
    "PULVERIZER": ["PULV"], "FEEDER": ["FDR"], "CLASSIFIER": ["CLSFR"],
    "BURNER": ["BNR"], "IGNITOR": ["IGNTR"],
    # Ban ve viet IGNITOR (615 lan), nguoi tra hay go IGNITER - khong co dong nao.
    # Xep chinh ta khac vao chung 1 o de ca hai deu ra dung.
    "IGNITER": ["IGNITOR", "IGNTR"],
    "SUPERHEATER": ["SH", "SUPERHEAT"], "REHEATER": ["RH", "RHT", "REHEAT"],
    "ECONOMIZER": ["ECO"], "DESUPERHEATER": ["DSH", "SPRY"],
    "ATTEMPERATOR": ["SPRY", "DSH"], "SPRAY": ["SPRY"],
    "SOOTBLOWER": ["SB"], "WATERWALL": ["WW"], "DEAERATOR": ["DEA"],
    "CONDENSER": ["COND", "CNDR"], "CONDENSATE": ["COND", "CEP"],
    "HEATER": ["HTR"], "DAMPER": ["DMPR"], "VALVE": ["VLV"],
    "IGNITION": ["IGNTR"], "FLAME": ["FLM"], "ATOMIZING": ["ATOMG"],
    "WARMING": ["WARMG"], "PURGE": ["PRG"], "EXHAUST": ["EXH"],
    "DRAIN": ["DRN"], "CLEAN": ["CLN"],
    # --- tua bin / may phat ------------------------------------------------
    "TURBINE": ["TURB"], "GENERATOR": ["GEN"], "GOVERNOR": ["GOV"],
    "EXCITATION": ["AVR"], "BEARING": ["BRG"], "MOTOR": ["MOT"],
    "POWER": ["PWR"], "BREAKER": ["CB"], "AUXILIARY": ["AUX"],
    # --- trang thai / su co ------------------------------------------------
    "ALARM": ["ALM"], "STOP": ["STP"], "FAILURE": ["FLT", "FAIL"],
    "FAULT": ["FLT"], "TRIP": ["TRP"], "PROTECTION": ["PROT"],
    "CLOSED": ["CLSD"], "CLOSE": ["CLS"], "OPEN": ["OPN"],
    # --- huong / vi tri ----------------------------------------------------
    "OUTLET": ["O/L"], "INLET": ["INL"], "INPUT": ["I/P"], "OUTPUT": ["O/P"],
    "UNIT": ["UNT"], "MASTER": ["MSTR"],
}

# Cum tu chi dua vao day khi ca cum CO MOT viet tat rieng trong ban ve. Ghep cum quan
# trong hon ve hai: "feedwater pump" tach thanh FW + PUMP thi dong 'BFP A RECIRC' khop
# 0 o, con giu nguyen cum thi khop 1/1. Nguoc lai neu cum khong co viet tat rieng
# ("flame failure") thi de tach doi, FLM va FAIL deu tu khop duoc.
CUM = {
    "FEEDWATER PUMP": ["BFP", "BFPT", "FEEDWATER PUMP"],
    "FEED WATER PUMP": ["BFP", "BFPT"],
    "BOILER FEED PUMP": ["BFP", "BFPT"],
    "BOILER FEED PUMP TURBINE": ["BFPT"],
    "CONDENSATE PUMP": ["CEP"],
    "CIRCULATING WATER PUMP": ["CWP"],
    "COOLING WATER": ["CCW"],
    "AIR HEATER": ["AH", "APH"],
    "AIR PREHEATER": ["APH", "AH"],
    "SOOT BLOWER": ["SB", "SOOTBLOWER"],
    "MASTER FUEL TRIP": ["MFT"],
    "FORCED DRAFT FAN": ["FDF"], "FD FAN": ["FDF"],
    "INDUCED DRAFT FAN": ["IDF"], "ID FAN": ["IDF"],
    "PRIMARY AIR FAN": ["PAF"], "PA FAN": ["PAF"],
    "PRIMARY SUPERHEATER": ["PRISH"],
    "SECONDARY SUPERHEATER": ["SECSH", "SSH"],
    "MAIN STEAM VALVE": ["MSV"],
    "WATER WALL": ["WW"],
    "LUBE OIL": ["LUBE OIL", "L/O"],
}

# Tu ngu phap: de lot vao thi chung khop bay ba sang viet tat ("TO" nam trong 4.602
# ten, "ON"/"IN" hang nghin) va lam loang cham diem, dong thoi nang nguong _toi_thieu
# len vo co. Loc AN TOAN vi cum tu da duoc ghep xong truoc do.
_BO_QUA = {"OF", "FOR", "AND", "TO", "IN", "ON", "AT", "BY", "WITH", "FROM",
           "THE", "AN", "AS", "IS", "ARE", "WAS", "WERE", "BE", "BEEN",
           "DO", "DOES", "DID", "HAS", "HAVE", "HAD", "WILL", "WOULD",
           "CAN", "COULD", "SHOULD", "MAY", "MUST",
           "WHAT", "WHERE", "WHICH", "WHEN", "WHY", "HOW", "WHO",
           "THIS", "THAT", "THESE", "THOSE", "IT", "ITS", "THERE",
           "I", "ME", "MY", "WE", "OUR", "YOU", "YOUR",
           "SHOW", "FIND", "LOOK", "PLEASE", "ANY", "SOME", "ALL"}
# CO Y khong bo "A": trong du an nay A/B/C/D/E la ma day thiet bi (PULV A, BMS_A,
# IGNTR A1.2), go "mill A" ma bo mat chu A thi ra ca 5 may.
# CO Y khong bo "NO", "OR", "OFF", "UP", "LOW": deu mang nghia trong ban ve
# ("NO FLM", "LOSS OF FLM", "OFF", "STRT-UP", "PRS LOW").

_DAI_NHAT_CUM = 4       # cum dai nhat trong CUM la "BOILER FEED PUMP TURBINE"


def _bang_tat():
    """TU_TAT hai chieu. Can ca 2 chieu vi DB dung ca dang tat (STRT 3.529 lan) lan
    dang day du (ALARM 458, IGNITOR 615), va nguoi tra co the go bat ky dang nao."""
    b = {}
    for day, tats in TU_TAT.items():
        b.setdefault(day, []).extend(t for t in tats if t != day)
        for t in tats:
            if t != day:
                b.setdefault(t, []).append(day)
    return b


_TAT = _bang_tat()


def _gon(ds):
    """Bo trung, xep tu ngan truoc cho de doc.

    KHONG gop 'INITIAL' vao 'INIT': ben tim khop theo BIEN TU chu khong phai chuoi con
    (xem project_index._re_o), nen 'INIT' KHONG con khop duoc 'INITIAL' - gop lai la
    mat han mot dang. Ngay ca voi khop chuoi con thi gop cung sai voi cap OVER/OVERLOAD:
    'OVER' khong duoc phep nuot 'OVERLOAD' vi hai tu khac nghia."""
    return sorted(set(ds), key=lambda t: (len(t), t))


def _bien_the(tu):
    """Cac dang thay the duoc cua 1 tu don."""
    return _gon([tu] + _TAT.get(tu, []))


def _tach(q):
    """Chuan hoa cau hoi -> danh sach tu HOA. Giu '/' va '-' o GIUA tu vi ban ve dung
    chung nhu mot phan cua tu (O/L, STRT-UP, I/L); dau cau khac thi bo."""
    ra = []
    for t in "".join(c if (c.isalnum() or c in "/-") else " "
                     for c in (q or "").upper()).split():
        t = t.strip("-/")
        if t:
            ra.append(t)
    return ra


def _o_tra(tu, them=None):
    """Danh sach tu -> danh sach O. Uu tien khop CUM dai truoc: 'feedwater pump' phai
    ra BFP chu khong phai FW + PUMP.

    `them` la bang tam {cum: [tu khoa]} do ai_tu_khoa.goi_y() dua ve (da kiem chung
    voi corpus). Ghep o day chu khong ghep vao ket qua sau cung, de tu AI vao DUNG O
    cua no - cham diem tinh theo so o khop, nen mot tu bo lac o rieng se lam lech ca
    nguong lan trong so vi tri."""
    them = them or {}
    dai = max([_DAI_NHAT_CUM] + [len(k.split()) for k in them])
    o, i = [], 0
    while i < len(tu):
        for n in range(min(dai, len(tu) - i), 1, -1):
            cum = " ".join(tu[i:i + n])
            if cum in them or cum in CUM:
                o.append(_gon(them.get(cum, []) + CUM.get(cum, [])))
                i += n
                break
        else:
            if tu[i] not in _BO_QUA:
                o.append(_gon(_bien_the(tu[i]) + them.get(tu[i], [])))
            i += 1
    return o


def o_tra(q, them=None):
    """Cau hoi -> danh sach O tu khoa: [['INIT','INITIAL'], ['CLD','COLD']].
    Trong 1 o cac tu THAY THE nhau (OR); giua cac o thi ben tim CHAM DIEM theo so o
    khop duoc, khong bat khop het - cau hoi day du kieu 'fuel flow for cold start of
    boiler' ra 4 o ma khong ten nao trong DB chua ca 4."""
    return _o_tra(_tach(q), them)


def o_sua(q, out_path=None, them=None):
    """Nhu o_tra() nhung con SUA CHINH TA dua tren tu that trong DB.

    Tra ve (o, sua) voi sua = [(tu da go, tu thay the)]. Chi dong den o nao MOI bien the
    deu vang mat trong corpus - luc do khong con gi de mat - va chi nhan tu lech <= 2 ky
    tu (project_index.gan_giong). Bat duoc ca loi go ("presure" -> "PRESSURE") lan loi
    chinh ta CO SAN TRONG BAN VE ("furnance" -> "FURNACE")."""
    from . import project_index as PI
    o = _o_tra(_tach(q), them)
    if not o:
        return [], []
    ts = PI.tan_suat([b for bien in o for b in bien], out_path=out_path)
    sua = []
    for k, bien in enumerate(o):
        if any(sum(ts.get(b, (0, 0))) > 0 for b in bien):
            continue
        goc = max(bien, key=len)
        gan = PI.gan_giong(goc, out_path=out_path)
        if gan:
            o[k] = _gon(gan)
            sua.append((goc, gan[0]))
    return o, sua
