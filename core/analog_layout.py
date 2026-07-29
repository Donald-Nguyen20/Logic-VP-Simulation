# -*- coding: utf-8 -*-
"""Tu dong xep so do nut cho 1 spec trong macro_analog.json (khong dung Qt) -
dung chung cho ui/internal_sim_dialog.py. Cot 0 = input/param thuc su duoc dung;
cot sau = do sau phu thuoc cua tung node (topo, longest-path-from-source)."""
from __future__ import annotations
import os
import json
from collections import defaultdict

_MANUAL_POS = None


def load_manual_pos():
    """Toa do tay (px, khop dung anh manual) cho tung ma tram, neu co -
    xem core/analog_manual_pos.json. {code: {"leaves":{name:[x,y,w,h]},
    "nodes":{name:[x,y,w,h]}}}."""
    global _MANUAL_POS
    if _MANUAL_POS is None:
        p = os.path.join(os.path.dirname(__file__), "analog_manual_pos.json")
        try:
            _MANUAL_POS = json.load(open(p, encoding="utf-8"))
        except Exception:
            _MANUAL_POS = {}
    return _MANUAL_POS


def save_manual_pos(all_data):
    """Ghi lai toan bo toa do tay (dung khi nguoi dung tu keo-tha trong che do
    'Edit layout' cua InternalLogicSimDialog roi bam 'Save layout') va lam moi
    cache trong tien trinh hien tai de cac cua so mo sau dung ngay du lieu moi."""
    global _MANUAL_POS
    p = os.path.join(os.path.dirname(__file__), "analog_manual_pos.json")
    json.dump(all_data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _MANUAL_POS = all_data

# cac truong trong 1 node co the tham chieu ten node/input/param khac (ngoai "in")
_REF_FIELDS = ("a", "b", "sel", "s", "r", "hold", "preset", "preset_val",
               "sv", "pv", "auto", "ref", "k", "ki", "ti", "rate", "hi", "lo",
               "g", "td", "tle", "tla", "kp")


def node_refs(nd):
    """Danh sach ten (node/input/param) ma 1 node tham chieu toi (de dung do thi)."""
    out = []
    v = nd.get("in")
    if isinstance(v, list):
        out.extend(x for x in v if isinstance(x, str))
    for key in _REF_FIELDS:
        v = nd.get(key)
        if isinstance(v, str):
            out.append(v)
    return out


def layout_spec(spec):
    """Tra ve (pos{name:(col,row)}, edges[(from,to)]) tu 1 spec macro_analog.json."""
    nodes = spec.get("nodes", {})
    leaves = set(spec.get("inputs", {}).keys()) | set(spec.get("params", {}).keys()) | {"0"}
    depth = {}

    def dep(name, trail):
        if name in depth:
            return depth[name]
        if name in leaves or name not in nodes:
            depth[name] = 0
            return 0
        if name in trail:                 # vong lap bao ve (khong nen xay ra trong spec that)
            depth[name] = 0
            return 0
        preds = [p for p in node_refs(nodes[name]) if p in nodes]
        d = 1 + max((dep(p, trail | {name}) for p in preds), default=0)
        depth[name] = d
        return d

    for name in nodes:
        dep(name, frozenset())

    used_leaves = set()
    for nd in nodes.values():
        for p in node_refs(nd):
            if p in leaves and p != "0":     # "0" la hang so tram (khong phai tin hieu that) - bo qua
                used_leaves.add(p)

    cols = defaultdict(list)
    for name in used_leaves:
        cols[0].append(name)
    for name, d in depth.items():
        cols[d + 1].append(name)

    pos = {}
    for c, names in cols.items():
        for i, name in enumerate(sorted(names)):
            pos[name] = (c, i)

    edges = []
    for name, nd in nodes.items():
        for p in node_refs(nd):
            if p in pos:
                edges.append((p, name))
    return pos, edges


# ---------------------------------------------------------------------------
# Bo tri kieu "giong manual": xep nut theo VUNG (band) tren-xuong dung thu tu
# manual thuc te (chot che do -> SV -> MV/delta -> lech/MV ERR -> ABN), va
# chan wire xep thanh 1 cot ben trai THEO DUNG THU TU khai bao trong "inputs"
# (thu tu nay da duoc xay dung khop voi thu tu chan thuc te trong manual).
# Ten node dung lai xuyen suot 10 khoi tram (autoLatch, mv, sv, abn,...) nen
# 1 bang BAND duy nhat dung chung cho ca ho.
BAND = {
    "autoLatch": 0,
    "svHeld": 1, "svAutoSel": 1, "svOvr": 1, "svLim": 1, "sv": 1, "svOvrLatch": 1,
    "bias": 1, "svsum": 1,
    "dltClamped": 2, "manVal": 2, "ffsum": 2, "autoSel": 2, "mv_autoSel": 2,
    "ovrSel": 2, "mv_ovr": 2, "ovr1": 2, "ovr2": 2, "mv": 2,
    "mvOvrLatch": 2, "mvOvr1Latch": 2, "mvOvr2Latch": 2,
    "refSel": 3, "refDelay": 3, "refRL": 3, "dev": 3, "devAbs": 3, "overDHL": 3,
    "posOK": 3, "errGated": 3, "MVERR": 3,
    "ctlAbnLatch": 4, "drvAbnLatch": 4, "abn": 4,
}
def layout_manual(spec):
    """Bo tri giong manual: (pos{name:(x,y)-don vi luoi}, edges, leaf_order[list]).
    Cot 0 = chan wire (input) THEO DUNG THU TU khai bao trong spec['inputs']
    (roi den 'params' can duoi) - giong cot pin ellipse ben trai manual.
    Cac nut tinh toan xep theo BAND (hang doc tren-xuong = dung thu tu manual):
    0 chot che do, 1 chuoi SV, 2 chuoi MV/delta, 3 chuoi lech/MV ERR, 4 chuoi ABN.
    TRONG 1 band, thu tu trai->phai lay theo DO SAU PHU THUOC THAT (dependency
    depth) - de dung mach nao (svHeld... hay bias/svsum...) cung tu xep dung
    chieu tin hieu, khong phu thuoc 1 danh sach ten co dinh."""
    nodes = spec.get("nodes", {})
    leaves = set(spec.get("inputs", {}).keys()) | set(spec.get("params", {}).keys()) | {"0"}
    inputs = list(spec.get("inputs", {}).keys())
    params = list(spec.get("params", {}).keys())
    leaf_order = inputs + params

    pos = {}
    for i, name in enumerate(leaf_order):
        pos[name] = (0, i)

    depth = {}

    def dep(name, trail):
        if name in depth:
            return depth[name]
        if name in leaves or name not in nodes:
            depth[name] = 0
            return 0
        if name in trail:
            depth[name] = 0
            return 0
        preds = [p for p in node_refs(nodes[name]) if p in nodes]
        d = 1 + max((dep(p, trail | {name}) for p in preds), default=0)
        depth[name] = d
        return d

    for name in nodes:
        dep(name, frozenset())

    # nut khong nam trong BAND (truong hop la) -> mac dinh xep vao chuoi giua
    band_of = dict(BAND)
    for n in nodes:
        if n not in band_of:
            band_of[n] = 2

    slot_lists = defaultdict(list)
    for n in nodes:
        slot_lists[band_of.get(n, 2)].append(n)
    for b, names in slot_lists.items():
        names.sort(key=lambda n: (depth.get(n, 0), n))
        for i, n in enumerate(names):
            pos[n] = (i + 1, b)

    edges = []
    for name, nd in nodes.items():
        for p in node_refs(nd):
            if p in pos:
                edges.append((p, name))
    return pos, edges, leaf_order
