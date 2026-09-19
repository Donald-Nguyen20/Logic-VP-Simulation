# -*- coding: utf-8 -*-
"""Ban ve so tay: bang neo co tro dung tin hieu khong, va do thi co dung logic goc khong.

Net ve thi lay nguyen tu so tay nen khong the "ve sai". Cai CON sai duoc la phan minh
them vao: o nao tren giay duoc to mau theo nguon nao. Gan nham 'Opening' vao OPS_OUT8
la hinh van y het so tay ma mau lai noi dieu nguoc lai - nguoi doc tin vi no giong hinh
ho van xem. Nen o day kiem bang neo doi voi than lenh DEF, roi lay DUNG kich ban cua
core/tag_docs/8204.json cho DefSim chay song song voi do thi tinh mau: lech mot vong
quet la hong test.

Phan tach net / ve / tim o nam o tests/test_manual_drawing.py (khong can file DEF)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import macro_def as MD  # noqa: E402
from core import tag_docs as TD  # noqa: E402
from core import def_sim as DS  # noqa: E402
from core.book_diagram import book_graph, khung  # noqa: E402

MA = "8204"
pytestmark = pytest.mark.skipif(not MD.body_of(MD.symbol_of(MA)),
                                reason="vendor DEF files not found")


@pytest.fixture(scope="module")
def g():
    return book_graph(MA)


@pytest.fixture(scope="module")
def neo():
    return [tuple(d) for d in khung(MA)["neo"]]


def _qapp():
    qtw = pytest.importorskip("PySide6.QtWidgets")
    return qtw.QApplication.instance() or qtw.QApplication([])


def _ban_ve_that():
    """Ban ve da tach cua 8204, hoac skip: cache bi gitignore, may khac chua co."""
    from core.manual_drawing import load
    ve, why = load(MA)
    if ve is None:
        pytest.skip(why)
    return ve


# ---------------------------------------------------------------- bang neo
def test_graph_builds(g):
    assert g["ok"], g["why"]
    assert len(g["nodes"]) > 60          # chua rut gon -> phai nhieu hon ban tu sinh
    assert sorted(g["outs"]) == [15, 16, 17, 18]


def test_every_mapped_source_exists_in_the_logic(g, neo):
    """Moi nguon ghi trong bang neo phai co that trong than lenh / bang chan.

    Go nham OPS_OUT12 thanh OPS_OUT21 thi o do chi dung trang mai, khong ai de y."""
    chan = MD.pins_of(MA, khoa=True).get("in", {})
    sai = []
    for nguon, _kieu, nhan in neo:
        loai, _, ten = nguon.partition(":")
        ok = {"pin": lambda: int(ten) in chan,
              "reg": lambda: ten in g["regs"],
              "ra": lambda: int(ten) in g["outs"],
              "ops": lambda: ten.startswith("OPS_IN")}.get(loai, lambda: False)()
        if not ok:
            sai.append((nguon, nhan))
    assert not sai, "bang neo tro toi nguon khong co: %s" % sai


def test_input_labels_match_the_vendor_pin_table(neo):
    """Nhan e-lip vao phai khop BANG CHAN cua hang, khong phai chu doc tu anh.

    Da tung doc nham tu anh: tuong chan 9 la Open/chan 10 la Closed, bang chan cho thay
    9 = Local, 10 = E-FAIL, 12/13 moi la Open/Closed."""
    ten = MD.pins_of(MA, khoa=True).get("in", {})
    vao = [(int(n[4:]), nhan) for n, kieu, nhan in neo if kieu == "vao"]
    assert [so for so, _ in vao] == list(range(1, 15))
    for so, nhan in vao:
        that = (ten.get(so) or "").lower()
        assert that, "chan %d khong co ten trong bang chan" % so
        g1 = set(nhan.lower().replace("-", " ").split())
        g2 = set(that.replace("-", " ").replace("_", " ").split())
        assert g1 & g2, "chan %d: bang neo ghi %r, bang chan ghi %r" % (so, nhan, that)


def test_every_display_cell_but_the_soft_switch_echo_is_mapped(g, neo):
    """13 phep gan OPS_OUT; OPS_OUT11 chi lap lai cong tac mem OPS_IN6 (o 'Soft SW 0'),
    12 cai con lai moi cai mot o 'S| ...'."""
    assert g["regs"]["OPS_OUT11"] == "ops:OPS_IN6"
    co = {n[4:] for n, kieu, _ in neo if kieu == "ht" and n.startswith("reg:")}
    can = {r for r in g["regs"] if r.startswith("OPS_OUT")} - {"OPS_OUT11"}
    assert co == can
    assert ("ops:OPS_IN6", "hop_sau", "Soft SW") in neo


def test_abnormal_cell_is_the_abn_output_not_a_register(neo):
    """'A| Abnormal' cung nguon voi e-lip ABN (chan 18) - da tung gan nham OPS_OUT11."""
    assert ("ra:18", "ht", "Abnormal") in neo
    assert ("ra:18", "ra", "ABN") in neo
    assert not any(n == "reg:OPS_OUT11" for n, _k, _t in neo)


def test_display_cells_share_a_node_with_the_outputs_they_mirror(g):
    """Opening = OP CMD, Closing = CL CMD, Auto Mode = chan ra Auto: cung mot nut, nen
    hai o tren giay luon cung mau. Manual Mode = NOT Auto Mode."""
    r, o = g["regs"], g["outs"]
    assert r["OPS_OUT7"] == o[16] and r["OPS_OUT8"] == o[17] and r["OPS_OUT5"] == o[15]
    byid = {b["id"]: b for b in g["nodes"]}
    m = byid[r["OPS_OUT4"]]
    assert m["op"] == "NOT" and [s for _v, s in m["ins"]] == [r["OPS_OUT5"]]


def test_real_drawing_resolves_every_anchor():
    """Ban ve that cua hang: moi dong bang neo tim ra o, vao ben trai, ra ben phai."""
    ve = _ban_ve_that()
    assert ve["thieu"] == [], ve["thieu"]
    w, _h = ve["khung"]
    for o in ve["neo"]:
        x = (o["r"][0] + o["r"][2]) / 2
        if o["kieu"] == "vao":
            assert x < w * 0.2, o
        elif o["kieu"] == "ra":
            assert x > w * 0.8, o
    assert any(c[4].strip() == "AA143" for c in ve["chu"])


def test_book_panel_tints_live_inputs_and_leaves_operator_buttons_blank():
    _qapp()
    _ban_ve_that()
    from ui.book_diagram_view import book_panel
    d, why = book_panel(MA, pin_vals={1: 1, 2: 0}, pin_sigs={1: "MOV-AUTO"})
    assert d is not None, why
    theo = {o["nguon"] + "|" + o["kieu"]: i for i, o in enumerate(d.ve["neo"])}
    assert d.gia_tri[theo["pin:1|vao"]] == 1
    assert d.gia_tri[theo["pin:2|vao"]] == 0
    assert d.gia_tri[theo["ops:OPS_IN2|ops"]] is None
    assert "MOV-AUTO" in d.chu_thich[theo["pin:1|vao"]]
    d.deleteLater()


# ---------------------------------------------------------------- doi chieu DefSim
def _nguon(g, src, s, truoc, ops):
    """Gia tri mot dau vao cua do thi, lay tu DefSim dang chay."""
    if src.startswith("pin:"):
        ten = MD.pins_of(MA, khoa=True).get("in", {}).get(int(src[4:]))
        return float(s.inputs.get(ten, 0.0)) if ten else 0.0
    if src.startswith("const:"):
        return float(src[6:])
    if src.startswith("par:"):
        return float(s._prm.get(int(src[4:]), 0.0))
    if src.startswith("ops:"):
        return float(ops.get(src[4:], 0.0))
    if src.startswith("reg:"):
        return float(truoc.get(src[4:], 0.0))     # o nho: gia tri VONG QUET TRUOC
    return None


def _eval(g, s, truoc, ops, sau):
    """{id_nut: 0/1} tinh tu do thi ban ve, voi DefSim cap gia tri chan va o nho.

    Nut co NHO (chot S-R, hop ham) thi khong tu tinh ma lay thang tu o nho tuong ung -
    day la phan khong dung lai bo mo phong; phan CON LAI, tuc toan bo mach to hop ma ban
    ve the hien, la phan dang duoc kiem."""
    byid = {b["id"]: b for b in g["nodes"]}
    nguoc = g["nguoc"]
    val = {}

    def lay(src):
        if src in byid:
            return tinh(src)
        return _nguon(g, src, s, truoc, ops)

    def tu_o_nho(nid):
        for ten in nguoc.get(nid, []):
            if ten in sau:
                return 1 if float(sau[ten]) > 0.5 else 0
        return None

    def tinh(nid):
        if nid in val:
            return val[nid]
        val[nid] = None                       # chan vong hoi tiep
        b = byid[nid]
        op = b["op"]
        if op in ("SR", "FN"):
            val[nid] = tu_o_nho(nid)
            return val[nid]
        xs = [lay(src) for _r, src in b["ins"]]
        bs = [None if x is None else (1 if float(x) > 0.5 else 0) for x in xs]
        val[nid] = _phep(op, bs, xs)
        return val[nid]

    for nid in byid:
        tinh(nid)
    return val


def _phep(op, bs, xs):
    if op == "NOT":
        return None if bs[0] is None else (0 if bs[0] else 1)
    if op == "AND":
        return 0 if any(b == 0 for b in bs) else (None if any(b is None for b in bs) else 1)
    if op == "OR":
        return 1 if any(b == 1 for b in bs) else (None if any(b is None for b in bs) else 0)
    if op == "XOR":
        return None if any(b is None for b in bs) else sum(bs) % 2
    if op == "MUX":
        return _mux(bs, xs)
    return None


def _mux(bs, xs):
    """Chuyen mach: nhanh co dieu kien 1 som nhat thang, het thi lay duong 'else'."""
    i = 0
    while i + 1 < len(bs):
        if bs[i] == 1:
            return bs[i + 1]
        if bs[i] is None:
            return None
        i += 2
    return bs[-1] if bs else None


# ---------------------------------------------------------------- o trong cua so Help
def test_panel_sits_under_the_generated_diagram_and_speaks_vietnamese():
    """O so tay dung ngay duoi o "So do", va khong sot chu nao chua dich.

    Hai ban ve cung mot logic; de xa nhau thi khong ai doi chieu duoc, ma do chinh la ly
    do nguoi dung muon co no."""
    import pytest as _p
    qtw = _p.importorskip("PySide6.QtWidgets")
    from core import help_i18n as I18N
    app = qtw.QApplication.instance() or qtw.QApplication([])
    cu = I18N._state["lang"]
    I18N._state["lang"] = I18N.VI
    I18N.MISSING.clear()
    try:
        from ui.block_help_dialog import BlockHelpDialog
        d = BlockHelpDialog(MA, "")
        app.processEvents()
        o = d._thu_tu_o()
        assert d._w_book is not None
        assert o.index(d._w_book) == o.index(d._w_diag) + 1
        assert not I18N.MISSING, "chua dich: %s" % sorted(I18N.MISSING)
        d.close()
        d.deleteLater()
    finally:
        I18N._state["lang"] = cu


def test_ordinary_block_gets_no_book_panel():
    """Ma khoi chua nhap toa do thi BO HAN o nay - ve bua mot bo cuc roi bao "theo so
    tay" thi te hon han la khong ve."""
    from core.book_diagram import co_khung
    assert co_khung(MA) and not co_khung("4011")


def _kich_ban():
    return TD.doc_for(MA)["scenarios"]


def test_there_are_scenarios_to_check_against():
    assert len(_kich_ban()) >= 20


def _toi_thoi_diem(s, events, j, t, xung):
    """Dua dau vao cua def_sim ve dung trang thai tai thoi diem t. -> (j moi, xung moi).

    Xung phai TU HA xuong 0 ngay vong sau: kich ban ghi "pulse" la nhan nut roi nha ra.
    Quen ha thi cai nut coi nhu bi giu, chot nao an theo suon len se khong bao gio nha."""
    for sig in xung:
        TD._dat(s, sig, 0.0)
    xung = {}
    while j < len(events) and float(events[j]["t"]) <= t + 1e-9:
        for sig, v in (events[j].get("set") or {}).items():
            TD._dat(s, sig, v)
        for sig, v in (events[j].get("pulse") or {}).items():
            TD._dat(s, sig, v)
            xung[sig] = True
        j += 1
    return j, xung


@pytest.mark.parametrize("sc", _kich_ban() if MD.body_of(MD.symbol_of(MA)) else [],
                         ids=lambda s: s["id"])
def test_book_graph_agrees_with_def_sim(g, sc):
    """Moi vong quet: do thi ban ve phai ra DUNG dau ra ma than lenh goc ra.

    Chi doi chieu nhung vong ma do thi ket luan duoc 0/1 that su (khong phai None) -
    None la cho da khai rang "cho nay lay tu o nho, khong tu tinh", bat loi o do thi la
    bat chinh cai minh da khong kiem."""
    dt = float(sc.get("dt", 0.5))
    n = int(round(float(sc["until"]) / dt)) + 1
    s = DS.DefSim(MA, dt=dt)
    TD._mac_dinh(s, MA)
    for sig, v in (sc.get("set") or {}).items():
        TD._dat(s, sig, v)
    events = sorted(sc.get("events", []), key=lambda e: float(e["t"]))
    ra_ten = MD.pins_of(MA, khoa=True).get("out", {})

    byid = {b["id"]: b for b in g["nodes"]}
    # Chan ra nao CHINH LA mot chot/hop ham thi gia tri cua no duoc moi tu o nho cua
    # DefSim, doi chieu lai chinh no la doi chieu vong tron - dem rieng, va o duoi bat
    # buoc phan doi chieu THAT phai la phan chinh. Khong tach ra thi mai sau co ai doi
    # them nut thanh chot la test tu rong ruot ma van xanh.
    moi = {no for no, src in g["outs"].items()
           if src in byid and byid[src]["op"] in ("SR", "FN")}
    j, xung, so_sanh, vong_tron = 0, {}, 0, 0
    for k in range(n):
        t = round(k * dt, 9)
        j, xung = _toi_thoi_diem(s, events, j, t, xung)
        truoc = dict(s.state)
        ops = dict(s.ops)
        out = s.step()
        val = _eval(g, s, truoc, ops, s.state)
        for no, src in sorted(g["outs"].items()):
            cho = val.get(src) if src in byid else None
            if cho is None:
                continue
            ten = ra_ten.get(no)
            that = 1 if float(out.get(ten, 0.0)) > 0.5 else 0
            assert cho == that, (
                "%s t=%g chan ra %d (%s): ban ve tinh ra %d, than lenh goc ra %d"
                % (sc["id"], t, no, ten, cho, that))
            if no in moi:
                vong_tron += 1
            else:
                so_sanh += 1
    assert so_sanh >= 2 * vong_tron, (
        "%s: chi doi chieu that duoc %d lan, trong khi %d lan la lay tu o nho roi so lai"
        % (sc["id"], so_sanh, vong_tron))
