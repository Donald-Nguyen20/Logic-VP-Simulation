# -*- coding: utf-8 -*-
"""MA TRAN NHAN QUA (Cause & Effect Matrix): cho nhieu tin hieu DICH (effect, vd MFT,
ETS, RUNBACK), tim TAT CA nguyen nhan GOC dan toi tung tin hieu (xuyen sheet/CPU), gom
lai thanh 1 bang: hang = nguyen nhan, cot = tin hieu dich, o = OR (1 minh du) hay AND
(can du ca nhom). Xay tren core/cond_tree.py (da co san, dung cho "Xem dieu kien" cu).

Chi doc DB, khong sua gi.
"""
from __future__ import annotations
from . import cond_tree as CT
from . import signal_graph as SG
from . import project_index as PI


def resolve_target_candidates(name, db_paths=None):
    """Tim cac diem BAT DAU hop le cho 1 ten tin hieu DICH: (db, sheet) ma tin hieu
    ten NAY thuc su duoc SINH RA (co khoi xuat ra no tren sheet do) - khac voi
    project_index.locate_full() tra ve MOI noi ten do XUAT HIEN (ca noi chi la dau
    vao/tham chieu). Tra ve list dict {db, sheet, net, label, cpuname, sheetlbl}."""
    name = (name or "").strip()
    if not name:
        return []
    try:
        PI.ensure(db_paths or [])
    except Exception:
        pass
    # ten trong CAD_ID co the khac hoa/thuong voi nguoi go -> thu chinh xac truoc,
    # roi thu UPPER(), cuoi cung LIKE (khong phan biet hoa/thuong) roi loc lai dung ten
    rows = PI.locate_full(name)
    if not rows and name.upper() != name:
        rows = PI.locate_full(name.upper())
    if not rows:
        rows = [(cpuname, cpuno, slbl, db, sheet, sigid)
                for (nm, cpuname, cpuno, slbl, db, sheet, sigid) in PI.find(name, limit=50)
                if nm.strip().upper() == name.upper()]
    out = []
    seen = set()
    for (cpuname, cpuno, slbl, db, sheet, sigid) in rows:
        key = (db, sheet)
        if key in seen:
            continue
        try:
            if name.upper() not in SG._produced_names(db, sheet):
                continue
        except Exception:
            continue
        seen.add(key)
        out.append({"db": db, "sheet": sheet, "net": sigid, "label": name,
                    "cpuname": cpuname, "sheetlbl": slbl})
    return out


def expand_full(db, sheet, net, cpu_paths=None, max_expansions=400):
    """build() roi lap expand() tren MOI la co the mo rong, cho toi khi het (hoac
    cham tran max_expansions / vong lap). 2 loai la duoc mo rong:
    - kind='cross': tin hieu san xuat o SHEET/CPU khac -> nhay sang do dung logic that.
    - type='opaque' (khoi KHONG co trong logic_sem.json, vd khoi TAG/Data-Link nhu
      DDL_TG dang dung de xuat MFT ra ngoai) -> mo tiep 1 buoc vao chan vao cua no, vi
      da qua thuc te cac khoi nay chi la vo boc/chuyen tiep, nguyen nhan THAT (AND/OR/
      SR...) nam ngay phia sau. KHONG mo rong 'cmp' (so sanh nguong) - do la 1 nguyen
      nhan CO TEN hop le (vd "FURN PRS HI HI"), dung lai dung y nghia cho ma tran."""
    cpu_paths = cpu_paths or {}
    ctr = [0]
    tree = CT.build(db, sheet, net, depth=40, cpu_paths=cpu_paths, _ctr=ctr)
    visited = set()
    budget = [max_expansions]

    def walk(node):
        if budget[0] <= 0:
            return node
        t = node.get("type")
        if t == "gate":
            node["children"] = [walk(c) for c in node["children"]]
            return node
        if t == "leaf" and node.get("kind") == "cross" and node.get("expandable"):
            key = ("cross", node.get("db"), (node.get("label") or "").upper())
            if key in visited:
                node["kind"] = "source"
                node["note"] = "vong lap xuyen sheet (da gap ten nay roi)"
                return node
            visited.add(key)
            budget[0] -= 1
            sub = CT.expand(node, cpu_paths=cpu_paths, id_base=ctr[0], depth=40)
            if sub is None:
                return node
            ctr[0] = CT.max_id(sub) + 1
            return walk(sub)
        if t == "opaque":
            # CHI mo qua khoi vo boc THAT SU don gian (dung 1 chan vao co ten, vd khoi
            # TAG/Data-Link nhu DDL_TG dung de xuat tin hieu ra ngoai). Khoi opaque co
            # TU 2 chan vao tro len la 1 khoi chuc nang THAT (vd bang trang thai gop
            # nhieu tin hieu khong lien quan) - mo qua se lan sang logic KHONG lien
            # quan (da thay thuc te: no ra hang tram dong khong dinh dang gi den MFT).
            # Dung lai o do, coi no la 1 nguyen nhan co ten (dung y nghia hon).
            real_ins = [n for n in node.get("in_nets", []) if n]
            if len(real_ins) != 1:
                return node
            key = ("opaque", node.get("db"), node.get("sheet"), node.get("net"))
            if key in visited:
                return node
            visited.add(key)
            budget[0] -= 1
            sub = CT.expand(node, cpu_paths=cpu_paths, id_base=ctr[0], depth=40)
            if sub is None or not sub.get("children"):
                return node        # khong mo rong duoc (khong co chan vao co ten) -> giu nguyen la 1 hang
            ctr[0] = CT.max_id(sub) + 1
            sub["children"] = [walk(c) for c in sub["children"]]
            return sub
        return node

    return walk(tree)


def _label_of(node):
    lb = node.get("label") or node.get("net") or "?"
    return ("NOT " + lb) if node.get("neg") else lb


def _row_key(node):
    # Chi dung TEN lam khoa (bo qua db) khi co ten - de nguyen nhan CUNG TEN tu 2
    # CPU du phong A/B (logic giong het nhau) gop thanh 1 dong duy nhat trong ma
    # tran, thay vi hien lap doi. Khong co ten (net thuan tuy) thi van phan biet
    # theo db/sheet/net vi khong the biet chac 2 net khac db la "cung 1 nguyen nhan".
    lb = node.get("label") or node.get("net") or ""
    if lb:
        return ("lbl", lb.strip().upper())
    return ("net", node.get("db"), node.get("sheet"), node.get("id"))


def _collect(node, target_disp, rows, and_stack):
    """Duyet cay (da mo rong xuyen sheet), gom moi la (leaf/cmp/opaque) thanh 1 hang
    trong `rows` (dict key -> row), danh dau OR / AND(nhom) cho cot target_disp.
    and_stack: list [(group_id, [nhan cac anh em AND khac])] tu goc toi node hien tai."""
    t = node.get("type")
    if t == "gate":
        op = node.get("op")
        if op == "SR":
            # chot SR (latch): chi nhanh SET (children[0]) moi la NGUYEN NHAN lam no
            # len 1. Nhanh RESET (children[1]) la dieu kien XOA chot (VD dieu kien cho
            # phep RESET MFT) - hoan toan KHAC y nghia "cai gi gay ra no", nen KHONG
            # theo vao, tranh lan sang toan bo logic permissive/interlock khong lien quan.
            ch = node.get("children") or []
            if ch:
                _collect(ch[0], target_disp, rows, and_stack)
            return
        if op == "AND":
            gid = "G%d" % node.get("id", 0)
            child_labels = [_label_of(c) for c in node.get("children", [])]
            for i, c in enumerate(node.get("children", [])):
                others = [child_labels[j] for j in range(len(child_labels)) if j != i]
                _collect(c, target_disp, rows, and_stack + [(gid, others)])
        else:
            for c in node.get("children", []):
                _collect(c, target_disp, rows, and_stack)
        return
    if t == "const":
        return
    if t == "opaque" and node.get("expanded") and node.get("children"):
        # khoi vo boc (TAG/Data-Link...) da duoc mo rong xuyen qua chan vao -> chi la
        # trung gian, KHONG tinh la 1 nguyen nhan rieng, di xuyen qua den cac con that
        for c in node["children"]:
            _collect(c, target_disp, rows, and_stack)
        return
    key = _row_key(node)
    row = rows.get(key)
    if row is None:
        row = {"label": _label_of(node), "db": node.get("db"), "sheet": node.get("sheet"),
               "sheetlbl": node.get("sheetlbl"), "net": node.get("net"),
               "kind": node.get("kind") or t, "marks": {}, "source": "tree"}
        rows[key] = row
    if and_stack:
        gid, others = and_stack[-1]
        row["marks"][target_disp] = {"kind": "and", "group": gid, "with": others}
    else:
        row["marks"][target_disp] = {"kind": "or"}


def tag_fid_causes(name, db_paths):
    """Tim nguyen nhan GOC qua CAD_TAG_FID: nhan da duoc CON NGUOI ghi san dang
    '<mo ta nguyen nhan> (<TEN TIN HIEU DICH>)', vd 'LOSS OF BOTH FDF (MFT)' cho
    tin hieu dich 'MFT'. Day la quy uoc lam tai lieu TRIP CIRCUIT rat pho bien trong
    du an nay - sach va dung y con nguoi da xac nhan, nen UU TIEN dung truoc khi phai
    suy luan tu day (xem build_matrix). Chi ap dung duoc voi tin hieu co quy uoc nay
    (thuong la TRIP/BAO DONG tong hop qua khoi TAG, khong phai moi tin hieu deu co).
    Tra ve list dict {label, db, sheet, block_id} da loai trung theo (db, nhan)."""
    import sqlite3
    from . import dbreader as D
    out = []
    seen = set()
    suffix = "(%s)" % (name or "").strip().upper()
    for db in (db_paths or []):
        try:
            c = sqlite3.connect(db).cursor()
            rows = c.execute(
                "SELECT DISTINCT f.BLOCK_ID, f.FIDVALUE, b.ID "
                "FROM CAD_TAG_FID f JOIN CAD_BLOCK b ON f.BLOCK_ID=b.BLOCK_ID "
                "WHERE UPPER(f.FIDVALUE) LIKE ?", ("%" + suffix,)).fetchall()
        except Exception:
            continue
        for bid, fv, sheet in rows:
            fv = (D._clean(fv) or "").strip()
            if not fv.upper().endswith(suffix):
                continue
            label = fv[: -len(suffix)].strip()
            if not label:
                continue
            key = (db, label.upper())
            if key in seen:
                continue
            seen.add(key)
            out.append({"label": label, "db": db, "sheet": sheet, "block_id": bid})
    return out


def _merge_mark(row, disp, new_mark, cpuname=None):
    """Ghi mark[disp] cho 1 hang, gop dung khi CUNG 1 ten nguyen nhan duoc gap lai
    (vd tu nhieu CPU/candidate khac nhau cho cung 1 tin hieu dich). KHONG duoc ghi
    de vo dieu kien theo thu tu xu ly (bug da gap: candidate xu ly SAU de len OR
    lam mat thong tin candidate truoc do tinh la AND) - AND phai THANG OR, vi AND
    la ket qua "chat che" hon (nguyen nhan nay o it nhat 1 noi KHONG du 1 minh gay
    hieu ung, nen khong the coi la OR doc lap chung cho ca 2 noi). Van luu lai o
    dau (CPU nao) tung thay OR truc tiep, de sau nay co the chu thich neu can."""
    old = row["marks"].get(disp)
    cpus = (old or {}).get("_or_at") or set()
    if new_mark.get("kind") == "or" and cpuname:
        cpus = cpus | {cpuname}
    if old is None:
        m = dict(new_mark)
        if cpus:
            m["_or_at"] = cpus
        row["marks"][disp] = m
        return
    if old.get("kind") == "and":
        old["_or_at"] = cpus
        return
    if new_mark.get("kind") == "and":
        m = dict(new_mark)
        m["_or_at"] = cpus
        row["marks"][disp] = m
        return
    old["_or_at"] = cpus


def build_matrix(targets, cpu_paths=None):
    """targets: [{'disp', 'cands':[{'db','sheet','net'},...]}] (disp = ten hien cot,
    VD 'MFT'; 'cands' = TAT CA noi (db/sheet) thuc su san xuat ra tin hieu ten do -
    khong con bat nguoi dung chon 1 noi duy nhat, ma GOP nguyen nhan tu MOI noi tim
    duoc, vd 2 CPU du phong A/B cung san xuat 1 ten tin hieu se duoc gop chung).
    Nguyen nhan TRUNG TEN (vd tu 2 CPU du phong A/B co logic giong het nhau) chi
    hien 1 dong duy nhat trong bang - khong lap doi (khoa theo TEN, khong theo db).
    QUAN TRONG: neu cung 1 ten nguyen nhan duoc tinh khac nhau o cac candidate/CPU
    (vd 1 he thong coi no la AND-voi-cai-khac, he thong khac coi no la OR-truc-tiep -
    day KHONG phai luon la CPU du phong giong het nhau, co the la 2 he thong khac
    nhau nhu UCS va BMS), thi AND THANG OR khi gop (_merge_mark) - an toan hon cho
    tai lieu trip circuit, tranh bao sai rang 1 minh no da du gay hieu ung trong
    khi thuc te co it nhat 1 he thong yeu cau ket hop them dieu kien khac.
    (Van chap nhan targets kieu cu {'db','sheet','net','disp'} - tu quy thanh 1 cand).
    Tra ve (columns=[disp,...], rows=[{'label','db','sheet','net','kind','source',
    'marks':{disp:{...}}}]), rows sap theo so cot lien quan giam dan roi theo ten.
    CHI GIU quan he OR (1 nguyen nhan minh no da du gay hieu ung O MOI NOI da gap) -
    cac nguyen nhan dang AND (it nhat 1 noi phai ket hop voi nguyen nhan khac) bi AN
    hoan toan khoi ma tran, theo yeu cau: ma tran chi liet ke nhung nguyen nhan doc
    lap, tu no du gay ra tin hieu dich, khong can biet no ket hop voi gi.
    Voi MOI ung vien (db/sheet): uu tien lay nguyen nhan tu CAD_TAG_FID TRONG CHINH
    DB cua ung vien do (nhan nguoi lam tai lieu san, sach hon) - CHI khi khong co gi
    (tin hieu khong theo quy uoc do) moi suy luan tu day qua cond_tree (expand_full/
    _collect), co the sot/lan hon vi phai tu doan qua cac khoi TAG/chot SR."""
    cpu_paths = cpu_paths or {}
    rows = {}
    columns = []
    for tg in targets:
        disp = tg.get("disp") or tg.get("net")
        columns.append(disp)
        cands = tg.get("cands") or [tg]
        for cand in cands:
            cpuname = cand.get("cpuname") or ""
            fid_causes = tag_fid_causes(disp, [cand["db"]])
            if fid_causes:
                for fc in fid_causes:
                    # Chi khoa theo TEN (bo db) - nguyen nhan cung ten tu CPU du
                    # phong A/B se gop chung 1 dong, khong lap doi.
                    key = ("lbl", fc["label"].strip().upper())
                    row = rows.get(key)
                    if row is None:
                        row = {"label": fc["label"], "db": fc["db"], "sheet": fc["sheet"],
                               "sheetlbl": None, "net": None, "kind": "tag",
                               "marks": {}, "source": "tag"}
                        rows[key] = row
                    _merge_mark(row, disp, {"kind": "or"}, cpuname)
            else:
                local = {}
                tree = expand_full(cand["db"], cand["sheet"], cand["net"], cpu_paths=cpu_paths)
                _collect(tree, disp, local, [])
                for key, lrow in local.items():
                    row = rows.get(key)
                    if row is None:
                        row = {k: v for k, v in lrow.items() if k != "marks"}
                        row["marks"] = {}
                        rows[key] = row
                    mk = lrow["marks"].get(disp)
                    if mk:
                        _merge_mark(row, disp, mk, cpuname)
    out_rows = []
    for row in rows.values():
        marks = {}
        for k, v in row["marks"].items():
            if v.get("kind") != "or":
                continue
            v = {kk: vv for kk, vv in v.items() if kk != "_or_at"}
            marks[k] = v
        if not marks:      # nguyen nhan nay it nhat 1 noi la AND -> an hoan toan
            continue
        row = dict(row)
        row["marks"] = marks
        out_rows.append(row)
    out_rows.sort(key=lambda r: (-len(r["marks"]), (r["label"] or "").upper()))
    return columns, out_rows


def is_valid_target(db, sheet, net):
    """True neu tin hieu nay co y nghia boolean (dung duoc cho ma tran nhan qua)."""
    try:
        return CT.is_boolean_signal(db, sheet, net)
    except Exception:
        return True
