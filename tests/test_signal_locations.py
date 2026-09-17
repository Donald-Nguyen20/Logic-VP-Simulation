# -*- coding: utf-8 -*-
"""Muc cuoi cua Explain: tin hieu nam o CPU/loop/sheet nao.

Cai de sai nhat la CHON CHO: mot ten co mat o hang chuc sheet, ghi nham sheet thi nguoi
doc lat ban ve ra cho khac. Thu hai la nhan nham manh chu thanh ten ('MWD' trong
'MWD>537MW') roi ghi vi tri cua mot tin hieu khong lien quan."""
import pytest

from core import signal_locations as SL

UCS, BMS = "01 UCS.db", "03 BMS_A.db"

CSDL = {
    UCS: {"cpuname": "UCS", "cpuno": 1,
          "num": {1: "167-24", 2: "167-15", 3: "044-03", 4: "090-06", 5: "127-12",
                  6: "113-21", 7: "072-21"},
          "sheetname": {1: "PAFL CTRL (A1)", 2: "PAFL CTRL (D5)", 3: "I/P SIG(1)",
                        4: "B/BLR MSTR (D2)", 5: "FURN PRS (D4)", 6: "CL FLW (D7)",
                        7: "NETWK SIG(3)"},
          "name2": {"SETP": [(1, "n1"), (2, "n2")],
                    "MFT": [(5, "m5"), (4, "m4"), (3, "m3"), (1, "m1")],
                    "WARMG CYC": [(7, "w7"), (6, "w6"), (1, "w1")],
                    "HLO": [(4, "h4"), (1, "h1")]}},
    BMS: {"cpuname": "BMS_A", "cpuno": 3,
          "num": {1: "050-10"}, "sheetname": {1: "MWD SEL"},
          "name2": {"MFT": [(1, "x1")], "MWD": [(1, "d1")]}},
}
# (db, sheet) -> cac net co khoi sinh ra tren sheet do
SINH = {(UCS, 1): {"n1"}, (UCS, 2): {"n2"}, (UCS, 3): {"m3"}, (UCS, 4): {"m4"},
        (UCS, 5): {"m5"}, (UCS, 6): {"w6"}, (UCS, 7): {"w7"}, (BMS, 1): {"x1", "d1"}}
TRANG = {UCS: ({1: "167", 2: "167", 3: "44", 4: "90", 5: "127", 6: "113", 7: "72"},
               {"167": "PULV A PAFL CTRL", "44": "I/P SIG PROCESSING 1",
                "90": "B/BLR MSTR CTRL 1", "127": "FURN PRS CTRL 1",
                "113": "CL FLW A CTRL", "72": "NETWK SIG 2"}),
         BMS: ({1: "50"}, {"50": "MWD SEL"})}


@pytest.fixture(autouse=True)
def csdl_gia(monkeypatch):
    monkeypatch.setattr(SL.SG, "_dbc", lambda p: CSDL[p])
    monkeypatch.setattr(SL.CT, "_producers",
                        lambda p, sid: {n: [object()] for n in SINH.get((p, sid), ())})
    monkeypatch.setattr(SL, "_trang", lambda p: TRANG[p])


def _nhan(cho):
    return [CSDL[p]["num"][sid] for p, sid in cho.cac_cho]


# ---------------------------------------------------------------- doc vet truy
def test_doc_vet_ca_dong_truy_nguoc_va_truy_xuoi():
    ctx = ("    SETP  [field measurement: x]  (produced on UCS / sheet 167-15):\n"
           "  -> WARMG CYC   (CPU 1 / sheet 113-21)\n"
           "  -> WARMG CYC (CPU 1 / sheet 072-21, as `w7`)\n"
           "SIGNAL: KHONG PHAI DONG VET\n")
    v = SL.doc_vet(ctx)
    assert v.theo_ten["SETP"] == [("UCS", "167-15")]
    assert v.theo_ten["WARMG CYC"] == [("1", "113-21"), ("1", "072-21")]
    assert v.da_qua == [("UCS", "167-15"), ("1", "113-21"), ("1", "072-21")]


# ---------------------------------------------------------------- chon cho
def test_cho_vet_ghi_cho_chinh_ten_nay_thang_ca_sheet_goc():
    vet = SL.doc_vet("    SETP  x  (produced on UCS / sheet 167-15):")
    cho = SL.tim_cho("SETP", [UCS], goc=[(UCS, 1)], vet=vet)
    assert _nhan(cho) == ["167-15"] and not cho.chi_dung


def test_vet_theo_thu_tu_xuat_hien():
    vet = SL.doc_vet("  -> WARMG CYC   (CPU 1 / sheet 113-21)\n"
                     "  -> WARMG CYC   (CPU 1 / sheet 072-21)")
    assert _nhan(SL.tim_cho("WARMG CYC", [UCS], vet=vet)) == ["113-21", "072-21"]


def test_khong_co_vet_thi_sheet_goc_co_khoi_sinh_ra_dung_truoc():
    assert _nhan(SL.tim_cho("MFT", [UCS, BMS], goc=[(UCS, 4)])) == ["090-06"]


def test_sheet_vet_da_di_qua_dung_truoc_sheet_khac():
    vet = SL.doc_vet("    Y  x  (produced on UCS / sheet 127-12):")
    assert _nhan(SL.tim_cho("MFT", [UCS, BMS], vet=vet)) == ["127-12"]


def test_khong_dinh_vet_thi_moi_cho_sinh_ra_db_dau_truoc_roi_theo_nhan():
    cho = SL.tim_cho("MFT", [UCS, BMS])
    assert _nhan(cho) == ["044-03", "090-06", "127-12"] and cho.them == 1


def test_khong_dau_sinh_ra_thi_ghi_noi_dung():
    cho = SL.tim_cho("HLO", [UCS])
    assert cho.chi_dung and _nhan(cho) == ["090-06", "167-24"]


def test_ten_khong_co_trong_csdl():
    assert SL.tim_cho("KHONG CO", [UCS, BMS]) == SL.Cho([], 0, False)


# ---------------------------------------------------------------- manh chu
@pytest.mark.parametrize("ten, ctx", [
    ("MWD", "    MWD>537MW(75%TMCR)  (produced on UCS / sheet 167-57):"),
    ("PULV A PAFL", "LOCATION: loop 'PULV A PAFL CTRL'"),
    ("DURING LD CHGE", "CASE  DURING LD CHGE(TDO 600s) = 1  ->  b3 follows a4"),
    ("A MS TEMP", "  -> B/BLR O/L A MS TEMP   (CPU 1 / sheet 048-21)"),
])
def test_ten_chi_nam_trong_nhan_dai_hon_la_manh(ten, ctx):
    assert SL.chi_la_manh(ten, ctx)
    assert SL.bo_manh([ten], ctx) == []


@pytest.mark.parametrize("ten, ctx", [
    ("MS TEMP SETP BIAS", "a8  <= SV-BIAS  [settings: MS TEMP SETP BIAS, INC, DEC] of:"),
    ("CL FDR A AUTO CMD", "CASE  X = 0  ->  CL FDR A AUTO CMD follows Y"),
    ("MFT (UCS CTLR)", "  MFT (UCS CTLR) QB  <= IO_DI\n  MFT (UCS CTLR)  (produced on UCS"),
    ("WARMG CYC", "  -> WARMG CYC   (CPU 1 / sheet 113-21)"),
    ("NO.1 PUMP", "SIGNAL: NO.1 PUMP."),       # dau cham het cau khong noi dai ten
])
def test_ten_dung_rieng_it_nhat_mot_lan_thi_giu(ten, ctx):
    assert not SL.chi_la_manh(ten, ctx)


def test_ten_vang_mat_khoi_ngu_canh_van_giu():
    """AI tra them bang get_source: khong co trong ngu canh nhung la ten that."""
    assert SL.bo_manh(["HP TURB I/L MS TEMP"], "SETP  x") == ["HP TURB I/L MS TEMP"]


# ---------------------------------------------------------------- dung bang
def test_loop_so_duoc_dem_du_ba_chu_so():
    assert SL.mo_ta_cho(UCS, 7) == ("UCS (CPU 1)", "072 NETWK SIG 2",
                                    "072-21 NETWK SIG(3)")


def test_thoat_ky_tu_markdown():
    assert SL._o("BMS_A") == r"BMS\_A"
    assert SL._o("DEVN<3degC|x*") == r"DEVN\<3degC\|x\*"


def test_muc_tieng_viet_du_cot_va_gop_cho_thua():
    md = SL.muc_vi_tri(["MFT"], [UCS, BMS], lang="vi")
    assert "## (5) TÍN HIỆU NẰM Ở ĐÂU" in md
    assert "| Tín hiệu | CPU | Loop | Sheet |" in md
    assert "| MFT | UCS (CPU 1) | 044 I/P SIG PROCESSING 1 | 044-03 I/P SIG(1) |" in md
    assert "|  | UCS (CPU 1) | 090 B/BLR MSTR CTRL 1 |" in md     # ten chi ghi dong dau
    assert "+1 nơi khác" in md


def test_muc_loop_danh_so_6_tieng_anh_va_ghi_noi_dung():
    md = SL.muc_vi_tri(["HLO"], [UCS], lang="en", so=6)
    assert md.lstrip().startswith("## (6) WHERE EACH SIGNAL LIVES")
    assert "(used here)" in md


def test_bo_manh_truoc_khi_dung_bang():
    ctx = "    MWD>537MW(75%TMCR)  (produced on UCS / sheet 167-57):"
    md = SL.muc_vi_tri(["MWD", "SETP"], [UCS, BMS], ctx=ctx)
    assert "050-10" not in md and "SETP" in md


def test_khong_ten_nao_tra_ra_cho_thi_khong_co_muc():
    assert SL.muc_vi_tri([], [UCS]) == ""
    assert SL.muc_vi_tri(["KHONG CO"], [UCS, BMS]) == ""


def test_qua_nhieu_ten_thi_bao_so_con_lai(monkeypatch):
    monkeypatch.setattr(SL, "TOI_DA_TEN", 1)
    md = SL.muc_vi_tri(["SETP", "MFT", "HLO"], [UCS], lang="vi")
    assert "Còn 2 tín hiệu khác không liệt kê." in md and "| MFT |" not in md
