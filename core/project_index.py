# -*- coding: utf-8 -*-
"""Chi muc TRA CUU chung cho ca du an (nhieu file DB) -> tra tin hieu & C-NET tuc thi,
khong quet lai tung DB. Luu ra 1 file SQLite, cache theo dau thoi gian file.
KHONG dung embeddings - bo truy xuat chinh la engine do thi cua app.

QUAN TRONG (Windows): MOI ket noi sqlite3 mo ra o day PHAI duoc dong lai bang try/finally,
ke ca khi co loi giua chung - neu khong, file handle se con giu file .tdesigner_index.db,
va lan goi build()/rebuild ke tiep se bao WinError 32 (file dang duoc dung boi tien trinh
khac - thuc ra la CHINH minh, do ket noi truoc chua dong het)."""
from __future__ import annotations
import os
import math
import sqlite3
import hashlib
import re
from . import dbreader as D

# Doi so nay moi khi SO DO bang thay doi. No duoc tron vao chu ky file DB nen index cu
# tu dong dung lai, khoi phai nho bam "Dung lai chi muc" bang tay.
_PHIEN = "3"


def index_path():
    return os.path.join(os.path.expanduser("~"), ".tdesigner_index.db")


def _gon_duong(db_paths):
    """Bo cac duong dan TRUNG NHAU vi cach viet, giu lai cach viet gap dau tien.
    Tren Windows cung 1 file co the vao danh sach duoi nhieu dang (khac hoa/thuong o
    ten o dia, khac dau gach cheo): phien lam viec cu khoi phuc 1 dang, nguoi dung
    import them 1 dang nua. Neu khong gop, MOI ket qua tra cuu deu hien 2-3 lan y het
    nhau, va thoi gian dung chi muc cung tang gap doi."""
    thay, ra = set(), []
    for p in db_paths:
        try:
            k = os.path.normcase(os.path.abspath(p))
        except Exception:
            k = p
        if k not in thay:
            thay.add(k)
            ra.append(p)
    return ra


def _sig(db_paths):
    h = hashlib.sha1()
    h.update(("phien%s;" % _PHIEN).encode())
    for p in sorted(_gon_duong(db_paths)):
        try:
            h.update(("%s|%d|%d;" % (os.path.abspath(p), int(os.path.getmtime(p)),
                                     os.path.getsize(p))).encode())
        except Exception:
            h.update(p.encode())
    return h.hexdigest()


_RE_TU = re.compile(r"[A-Z0-9][A-Z0-9/\-]*")


def _tach_tu(s):
    """Ten -> tap TU. Giu ca dang co gach ("O/L", "PRE-LIGHT") lan cac manh cua no,
    vi ban ve dung lan lon: co cho viet "O/L STM TEMP", co cho viet "OUTLET"."""
    ra = set()
    for t in _RE_TU.findall((s or "").upper()):
        t = t.strip("/-")
        if len(t) < 2 or t.isdigit():
            continue
        ra.add(t)
        for m in re.split(r"[/\-]", t):
            if len(m) >= 2 and not m.isdigit():
                ra.add(m)
    return ra


def _nap_tu(con):
    """Bang `tu`: moi TU trong ten kem so ten chua no. Dung cho hai viec, ca hai deu
    la CHONG DOAN BUA:
      - kiem chung: tu nao AI (hoac nguoi dung) dua ra ma DB khong he co thi loai ngay,
        nen AI khong the day ket qua di lac;
      - goi y tu gan dung: nguoi tra go "IGNITER" trong khi ban ve viet "IGNITOR" -
        lech 1 chu cai, tim duoc bang khoang cach sua chuoi."""
    dm, ds = {}, {}
    for (t,) in con.execute("SELECT text FROM muc"):
        for w in _tach_tu(t):
            dm[w] = dm.get(w, 0) + 1
    for (n,) in con.execute("SELECT name FROM sig"):
        for w in _tach_tu(n):
            ds[w] = ds.get(w, 0) + 1
    for w in set(dm) | set(ds):
        con.execute("INSERT INTO tu VALUES(?,?,?)", (w, dm.get(w, 0), ds.get(w, 0)))


def _sig_sheets(cur):
    """{systemline: [sheet_id,...]} cho DB kieu EHC - ten tin hieu nam o CAD_SIGNAL
    (khong co so sheet), phai tu tra xem dia chi do dung o sheet nao qua chan khoi.
    Uu tien sheet SINH RA (net tren chan RA); khong co thi lay cac sheet co dung."""
    from . import sheet_render as SR
    MP = SR._macro_pins()
    prod = {}
    used = {}
    try:
        for sid, sym, pn, sig in cur.execute(
                "SELECT b.ID,b.SYMBOL,p.PINNO,p.SIGNALID FROM CAD_BLOCK_PIN p "
                "JOIN CAD_BLOCK b ON p.BLOCK_ID=b.BLOCK_ID "
                "WHERE p.SIGNALID IS NOT NULL AND TRIM(p.SIGNALID)<>''"):
            s = D._clean(sig)
            if not s:
                continue
            side = (MP.get(sym) or {}).get("pins", {}).get(str(pn), {}).get("side")
            (prod if side == "out" else used).setdefault(s, set()).add(sid)
    except Exception:
        return {}
    out = {}
    for s in set(prod) | set(used):
        ids = prod.get(s) or used.get(s) or set()
        out[s] = sorted(ids)[:10]      # tin hieu he thong dung khap noi -> chan bot
    return out


def _num_map(cur):
    num = {}
    try:
        for sid, loop, sh in cur.execute("SELECT ID,LOOPNO,SHEETNO FROM CAD_DATA"):
            loop = D._clean(loop); sh = D._clean(sh)
            if loop and sh:
                num[sid] = "%s-%s" % (str(loop).zfill(3), str(sh).zfill(2))
            elif loop or sh:
                num[sid] = str(loop or sh)
    except Exception:
        pass
    return num


def _trang_map(cur):
    """{sid: (loopno, sheetlbl, sheetname)} - du lieu de dat TEN cho tung trang."""
    tr = {}
    try:
        for sid, loop, sh, nm in cur.execute(
                "SELECT ID,LOOPNO,SHEETNO,SHEETNAME FROM CAD_DATA"):
            loop = D._clean(loop); sh = D._clean(sh); nm = D._clean(nm)
            if loop and sh:
                lbl = "%s-%s" % (str(loop).zfill(3), str(sh).zfill(2))
            else:
                lbl = str(loop or sh or sid)
            tr[sid] = (str(loop or ""), lbl, nm or "")
    except Exception:
        pass
    return tr


def _muc_loop(cur, trang):
    """Ten cac LOOP - muc luc chuc nang cua CPU (~102 loop/CPU, 1.225 ca du an).
    Day la duong VAO duy nhat khi nguoi tra chi biet CHUC NANG chu khong biet ten tin
    hieu nao: 'IGNITOR PRE-LIGHT', 'FW/FUEL RATIO CTRL 3'... Gan san trang DAU cua loop
    de bam doi la mo duoc ngay, khong phai tra tiep."""
    dau = {}
    for sid, (loop, lbl, _nm) in trang.items():
        if loop and (loop not in dau or lbl < dau[loop][1]):
            dau[loop] = (sid, lbl)
    ra = []
    try:
        for loop, nm in cur.execute("SELECT LOOPNO,LOOPNAME FROM CAD_LOOP"):
            nm = D._clean(nm)
            if not nm:
                continue
            sid, lbl = dau.get(str(D._clean(loop) or ""), (None, ""))
            ra.append(("loop", nm, sid, lbl, "loop %s" % (D._clean(loop) or "?")))
    except Exception:
        pass
    return ra


def _muc_fx(path, sids):
    """Ten cac khoi F(x). Ca du an co 4.290 khoi ham va 100% DEU CO TEN mo ta
    ('FIRING RATE PROG FOR INIT COLD STRT-UP') - truoc day khong duoc danh chi muc o
    dau ca, tuc la mat han lop mo ta CHI TIET nhat cua ban ve. Doc qua sheet_sim de
    khong phu thuoc vao so do bang CAD_BLOCK (bang nay khong co cot PARTSCODE)."""
    from . import sheet_sim as SS
    ra = []
    for sid in sids:
        try:
            sx = SS._analog_producers(path, sid)
        except Exception:
            continue
        for ap in sx.values():
            if ap.get("op") != "FUNC":
                continue
            try:
                fx = SS.func_info(path, sid, ap["bid"])
            except Exception:
                continue
            nm = (fx.get("name") or "").strip()
            if nm:
                ra.append((sid, nm, (fx.get("tag") or "").strip()))
    return ra


def build(db_paths, out_path=None):
    """Dung lai index tu danh sach file DB. Tra ve duong dan file index."""
    out_path = out_path or index_path()
    tmp = out_path + ".tmp"
    if os.path.exists(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass    # file .tmp cu bi khoa (vd lan build truoc loi giua chung) - ghi de len van duoc
    con = sqlite3.connect(tmp)
    try:
        con.execute("CREATE TABLE sig(name TEXT, db TEXT, cpuno TEXT, cpuname TEXT, "
                    "sheet INT, sheetlbl TEXT, signalid TEXT)")
        con.execute("CREATE TABLE cnet(systemline TEXT, name TEXT, cpuno TEXT, cpuname TEXT, "
                    "db TEXT, sheet INT, sheetlbl TEXT)")
        # `muc` = chi muc theo CHUC NANG (ten loop / ten trang / ten khoi F(x)), khac
        # han `sig` la chi muc theo TEN TIN HIEU. Can ca hai vi nguoi tra thuong bat dau
        # tu chuc nang ("trinh tu danh lua voi dau") chu chua biet ten tin hieu nao.
        con.execute("CREATE TABLE muc(kind TEXT, text TEXT, db TEXT, cpuno TEXT, "
                    "cpuname TEXT, sheet INT, sheetlbl TEXT, extra TEXT)")
        con.execute("CREATE TABLE tu(t TEXT, dm INT, ds INT)")
        con.execute("CREATE TABLE meta(key TEXT, val TEXT)")
        for p in _gon_duong(db_paths):
            try:
                meta = D.db_meta(p)
            except Exception:
                meta = {}
            cpuno = str(meta.get("cpuno") or ""); cpuname = meta.get("cpuname") or ""
            pc = None
            try:
                pc = sqlite3.connect(p)
                c = pc.cursor()
                trang = _trang_map(c)
                num = dict((k, v[1]) for k, v in trang.items())
                loops = _muc_loop(c, trang)
                ten_loop = {}
                for kind, txt, sid, slbl, extra in loops:
                    con.execute("INSERT INTO muc VALUES(?,?,?,?,?,?,?,?)",
                                (kind, txt, p, cpuno, cpuname, sid, slbl, extra))
                    ten_loop[extra.split()[-1]] = txt
                for sid, (loop, slbl, nm) in trang.items():
                    if nm:
                        con.execute("INSERT INTO muc VALUES(?,?,?,?,?,?,?,?)",
                                    ("sheet", nm, p, cpuno, cpuname, sid, slbl,
                                     ten_loop.get(loop, "")))
                for sid, nm, tag in _muc_fx(p, list(trang.keys())):
                    _l, slbl, _n = trang.get(sid, ("", str(sid), ""))[0:3]
                    con.execute("INSERT INTO muc VALUES(?,?,?,?,?,?,?,?)",
                                ("fx", nm, p, cpuno, cpuname, sid, slbl, tag))
                try:
                    rows = c.execute("SELECT ID,SIGNALID,LINENAME,SYSTEMLINE FROM CAD_ID").fetchall()
                except Exception:
                    rows = []
                seen_names = set()
                for sid, sigid, ln, sysl in rows:
                    ln = D._clean(ln); sysl = D._clean(sysl); sigid = D._clean(sigid)
                    slbl = num.get(sid, str(sid))
                    if ln:
                        seen_names.add(ln.upper())
                        con.execute("INSERT INTO sig VALUES(?,?,?,?,?,?,?)",
                                    (ln, p, cpuno, cpuname, sid, slbl, sigid))
                    if sysl:
                        con.execute("INSERT INTO cnet VALUES(?,?,?,?,?,?,?)",
                                    (sysl, ln, cpuno, cpuname, p, sid, slbl))
                # Nguon ten thu 2 (DB kieu EHC): CAD_SIGNAL. Nhieu DB (21 EHC MC, 23/25
                # BFPT...) KHONG dat ten trong CAD_ID - vd 'TURBINE TRIP COMMAND' chi co o
                # CAD_SIGNAL - neu khong nap vao day thi tim kiem se khong ra du man hinh
                # van hien ten. Chi nap ten CHUA co trong CAD_ID de khong sinh dong trung.
                try:
                    srows = c.execute("SELECT SYSTEMLINE,LINENAME FROM CAD_SIGNAL").fetchall()
                except Exception:
                    srows = []
                if srows:
                    sheets_of = _sig_sheets(c) if any(
                        D._clean(l) and D._clean(l).upper() not in seen_names
                        for _s, l in srows) else {}
                    for sysl, ln in srows:
                        sysl = D._clean(sysl); ln = D._clean(ln)
                        if not ln or ln.upper() in seen_names:
                            continue
                        for sid in (sheets_of.get(sysl) or [None]):
                            slbl = num.get(sid, str(sid)) if sid is not None else ""
                            con.execute("INSERT INTO sig VALUES(?,?,?,?,?,?,?)",
                                        (ln, p, cpuno, cpuname, sid, slbl, sysl))
                        if sysl:
                            con.execute("INSERT INTO cnet VALUES(?,?,?,?,?,?,?)",
                                        (sysl, ln, cpuno, cpuname, p, None, ""))
            except Exception:
                continue
            finally:
                if pc is not None:
                    pc.close()
        con.execute("CREATE INDEX ix_sig_name ON sig(name)")
        con.execute("CREATE INDEX ix_cnet_line ON cnet(systemline)")
        con.execute("CREATE INDEX ix_cnet_name ON cnet(name)")
        con.execute("CREATE INDEX ix_muc_text ON muc(text)")
        _nap_tu(con)
        con.execute("CREATE INDEX ix_tu_t ON tu(t)")
        con.execute("INSERT INTO meta VALUES('sig', ?)", (_sig(db_paths),))
        con.commit()
    finally:
        con.close()     # LUON dong, ke ca khi loi o tren - neu khong tmp se bi khoa mai
    if os.path.exists(out_path):
        try:
            os.remove(out_path)
        except OSError as e:
            # con noi khac dang mo file index cu (vd 1 truy van truoc chua dong het) ->
            # bao ro nguyen nhan thay vi de WinError 32 kho hieu lot ra ngoai
            raise OSError("Khong the ghi de index cu (dang bi khoa boi 1 tien trinh/ket noi "
                          "khac): %s. Thu dong cac cua so tim kiem/ma tran dang mo roi thu "
                          "lai." % e)
    os.rename(tmp, out_path)
    return out_path


def ensure(db_paths, out_path=None):
    """Dung index neu chua co / DB da doi. Tra ve duong dan index."""
    out_path = out_path or index_path()
    want = _sig(db_paths)
    con = None
    try:
        con = sqlite3.connect(out_path)
        cur = con.execute("SELECT val FROM meta WHERE key='sig'").fetchone()
        if cur and cur[0] == want:
            return out_path
    except Exception:
        pass
    finally:
        if con is not None:
            con.close()
    return build(db_paths, out_path)


def tan_suat(tu, out_path=None):
    """{TU: (so ten trang/loop/Fx, so ten tin hieu)}. Tu khong co mat -> (0, 0)."""
    tu = [t.upper() for t in tu if t]
    if not tu:
        return {}
    con, ra = None, dict((t, (0, 0)) for t in tu)
    try:
        con = sqlite3.connect(out_path or index_path())
        q = "SELECT t,dm,ds FROM tu WHERE t IN (%s)" % ",".join("?" * len(tu))
        for t, dm, ds in con.execute(q, tu):
            ra[t] = (dm, ds)
    except Exception:
        return ra
    finally:
        if con is not None:
            con.close()
    return ra


def _cach(a, b):
    """Khoang cach sua chuoi (Levenshtein). Viet tay cho khoi them thu vien ngoai."""
    if a == b:
        return 0
    truoc = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        nay = [i]
        for j, cb in enumerate(b, 1):
            nay.append(min(truoc[j] + 1, nay[j - 1] + 1,
                           truoc[j - 1] + (ca != cb)))
        truoc = nay
    return truoc[-1]


def gan_giong(tu, toi_da=2, so=4, out_path=None):
    """Cac tu CO THAT trong DB gan giong `tu` nhat. Chi de sua loi chinh ta/bien the:
    "IGNITER" -> "IGNITOR" (lech 1 chu). Chan chat dau vao (cung chu cai dau, do dai
    lech khong qua 2) vi noi long ra thi "COLD" hoa "COAL" va ket qua thanh vo nghia."""
    tu = (tu or "").upper()
    if len(tu) < 4:
        return []
    # Lech 2 ky tu tren tu NGAN la doi han tu: "HERE" cach "HTR" dung 2 buoc, va neu
    # nhan thi cau vo nghia "xyzzy nothing here" lai ra 4 dong ve binh gia nhiet - dung
    # cai bay nguy hiem nhat cua tra cuu. Tu dai thi 2 buoc van con la mot tu do.
    toi_da = min(toi_da, 1 if len(tu) < 7 else 2)
    con = None
    try:
        con = sqlite3.connect(out_path or index_path())
        ung = con.execute(
            "SELECT t,dm+ds FROM tu WHERE t LIKE ? AND LENGTH(t) BETWEEN ? AND ?",
            (tu[0] + "%", len(tu) - 2, len(tu) + 2)).fetchall()
    except Exception:
        return []
    finally:
        if con is not None:
            con.close()
    ra = []
    for t, n in ung:
        if t == tu:
            return []          # go dung roi, khong phai sua gi
        d = _cach(tu, t)
        if d <= toi_da:
            ra.append((d, -n, t))
    ra.sort()
    return [t for _d, _n, t in ra[:so]]


def find(query, limit=300, out_path=None):
    """Tim tin hieu theo ten (LIKE). Tra ve [(name, cpuname, cpuno, sheetlbl, db, sheet, signalid)]."""
    out_path = out_path or index_path()
    con = None
    try:
        con = sqlite3.connect(out_path)
        return con.execute(
            "SELECT DISTINCT name,cpuname,cpuno,sheetlbl,db,sheet,signalid FROM sig "
            "WHERE UPPER(name) LIKE ? ORDER BY name LIMIT ?",
            ("%" + query.upper() + "%", limit)).fetchall()
    except Exception:
        return []
    finally:
        if con is not None:
            con.close()


# loop truoc (1.225 ban ghi - trung 1 loop la dinh huong duoc ca mang), roi den F(x)
# (4.290 - chi tiet nhat), cuoi cung la ten trang (16.179 - nhieu nhat, nhieu nhat).
# Nhan them vao diem chu KHONG xep truoc vo dieu kien: ten loop la duong vao tot nhat
# (1 loop dinh huong ca mang), ten trang thi nhieu va chung chung nhat - nhung mot ten
# trang khop that sat van phai thang mot ten loop khop ho.
_HE_SO = {"loop": 1.15, "fx": 1.08, "sheet": 1.0}


def _re_o(o):
    """Moi O -> 1 regex khop BIEN TU: '(?<![A-Z])(INIT|INITIAL)(?![A-Z])'.

    Phai khop bien tu chu khong phai chuoi con, neu khong ket qua thanh rac: 'CO'
    trung 'CONTROL', 'FO' trung moi chu 'FOR', 'IGN' trung 'SIGNAL'. Chan hai dau bang
    CHU CAI thoi (khong chan chu so) de '2SH O/L STM TEMP' van khop duoc 'SH'."""
    import re
    ra = []
    for bien in o:
        bien = [b for b in bien if b]
        if bien:
            ra.append(re.compile(r"(?<![A-Z])(?:%s)(?![A-Z])"
                                 % "|".join(re.escape(b) for b in sorted(
                                     bien, key=len, reverse=True))))
    return ra


def _loc_sql(o, cot):
    """(menh de WHERE, tham so) chan truoc bang LIKE. Khop bien tu bao gio cung keo
    theo khop chuoi con, nen loc nay chac chan khong bo sot - ma cat duoc phan lon so
    hang truoc khi cham diem bang regex (regex Python cham hon LIKE cua SQLite)."""
    # Khong dung ESCAPE: neu tu khoa lo co '%' hay '_' thi LIKE chi NOI RONG them chu
    # khong bo sot, ma day chi la loc tho - regex cham diem phia sau van gat phan thua.
    ts = ["%" + b + "%" for bien in o for b in bien if b]
    if not ts:
        return "", []
    dk = " OR ".join(["%s LIKE ?" % cot] * len(ts))
    return " WHERE " + dk, ts


def _toi_thieu(n):
    """So o it nhat phai khop thi ket qua moi dang tin. Cau 1-2 tu thi khop 1 la du;
    cau dai hon ma chi khop 1 o thuong la trung nham tu vun ('khong', 'co') - phai
    khop qua nua. Nho vay cau vo nghia tra ve RONG thay vi 400 dong rac."""
    return 1 if n <= 2 else (n + 1) // 2


def _quet(con, cot_sel, bang, cot, o, limit, chi_tiet=None):
    """Cham diem tung dong theo do HIEM cua cac o khop duoc. Tra ve [(diem, dong)].

    Khong dung 'AND cac tu' trong SQL vi cau hoi day du se khong bao gio khop het:
    'luu luong nhien lieu khoi dong nguoi' ra 4 o (FLW|FLOW, FUEL, STRT|START,
    CLD|COLD) ma ten dich - 'FIRING RATE PROG FOR INIT COLD STRT-UP' - chi chua 2.

    Cung khong dem deu moi o 1 diem: 'may nghien A qua tai' co 3 o (MILL|PULV, A,
    OVER|OVERLOAD); dem deu thi hang tram dong 'PULV A ...' cung dat 2/3 diem va hoa
    nhau, ket qua la 8 dong dau khong dong nao dinh dang gi den QUA TAI. Can theo do
    hiem: 'A' co trong hang nghin ten nen gan nhu khong dang ke, 'OVER' chi vai tram
    nen dong nao co OVER phai len tren."""
    o = [x for x in o if x]
    if not o:
        return []
    res = _re_o(o)
    if not res:
        return []
    dk, ts = _loc_sql(o, cot)
    try:
        rows = con.execute("SELECT %s FROM %s%s" % (cot_sel, bang, dk), ts).fetchall()
        tong = con.execute("SELECT COUNT(*) FROM %s" % bang).fetchone()[0] or 1
    except Exception:
        return []
    vt = [x.strip() for x in cot_sel.split(",")].index(cot)
    cham, df = [], [0] * len(res)
    if chi_tiet is not None:
        chi_tiet["df"] = df
    for r in rows:
        t = (r[vt] or "").upper()
        kh = [i for i, rx in enumerate(res) if rx.search(t)]
        if kh:
            for i in kh:
                df[i] += 1
            cham.append((kh, r))
    if not cham:
        return []
    # df dem tren dong DA QUA LOC LIKE van dung bang dem tren ca bang: khop bien tu bao
    # gio cung keo theo khop chuoi con, nen dong nao chua tu do chac chan da lot loc.
    # Trong so VI TRI: o dung TRUOC nang hon. Cau hoi ky thuat luon dat danh tu chinh
    # len dau ("furnace pressure low", "feedwater pump overload"), nen o 0 gan nhu luon
    # la CHU NGU. Thieu he so nay thi khi hai dong cung khop 2 o, do hiem se chon dong
    # co tu HIEM hon chu khong chon dong co CHU NGU: "furnace pressure low" tra ve
    # "EMERGENCY OIL PRESS LOW SIM" (khop PRESS+LOW) trong khi "FURN PRS CTRL (A1..A12)"
    # nam san trong DB. Do la mat dung cai nguoi ta hoi.
    vi_tri = [1.0 / (1.0 + 0.6 * i) for i in range(len(res))]
    w = [math.log(1.0 + float(tong) / (1 + d)) * vi_tri[i]
         for i, d in enumerate(df)]
    dinh = max(len(kh) for kh, _r in cham)
    # Nguong tinh tren so o CON SONG (co it nhat 1 dong khop), khong phai tong so o.
    # "ham nuoc tiet kiem" ra 3 o nhung ban ve chi co ECO - tinh tren tong thi doi khop
    # 2/3, khong dong nao dat, tra ve RONG du ECO la dung y. Van chan duoc cau vo nghia
    # vi tu ngu phap ("khong", "co") da bi tu_dien loc tu truoc, khong con thanh o nua.
    song = sum(1 for d in df if d > 0)
    if dinh < _toi_thieu(song):
        return []
    # SO O khop moi la chinh, do hiem chi de pha the hoa. Neu lay do hiem lam chinh thi
    # 'may nghien A qua tai' dua 'BFPT A OVER SPEED' len dau - dung 'OVER' hiem hon
    # 'PULV' - tuc la vut mat chinh cai CHU NGU nguoi ta hoi. Chi giu hang khop nhieu o
    # nhat: cau hoi cang day du thi hang nay cang hep, dung y nghia loc dan.
    ra = [(sum(w[i] for i in kh), r) for kh, r in cham if len(kh) == dinh]
    ra.sort(key=lambda x: -x[0])
    return ra[:limit * 4]


def find_muc(o, limit=200, out_path=None, chi_tiet=None):
    """Tra chi muc CHUC NANG. `o` la ket qua tu_dien.o_tra().
    Tra ve [(kind, text, db, cpuno, cpuname, sheet, sheetlbl, extra)]."""
    out_path = out_path or index_path()
    con = None
    try:
        con = sqlite3.connect(out_path)
        ra = _quet(con, "kind,text,db,cpuno,cpuname,sheet,sheetlbl,extra",
                   "muc", "text", o, limit, chi_tiet)
    except Exception:
        return []
    finally:
        if con is not None:
            con.close()
    # gop dong trung, giu diem cao nhat; ten NGAN hon = tu khoa chiem ty le lon hon
    # trong ten = khop sat hon, dung lam tieu chi phu khi diem bang nhau
    tot = {}
    for d, r in ra:
        d *= _HE_SO.get(r[0], 1.0)
        if r not in tot or d > tot[r]:
            tot[r] = d
    kq = sorted(tot.items(), key=lambda x: (-x[1], len(x[0][1] or ""), x[0][1] or ""))
    return [r for r, _d in kq[:limit]]


def find_bo(o, limit=200, out_path=None, chi_tiet=None):
    """Nhu find() nhung nhan cac O tu khoa tu tu dien thay vi 1 chuoi tho.
    Tra ve [(name, cpuname, cpuno, sheetlbl, db, sheet, signalid)] - dung thu tu cot
    ma UI dang dung cho find()."""
    out_path = out_path or index_path()
    con = None
    try:
        con = sqlite3.connect(out_path)
        ra = _quet(con, "name,cpuname,cpuno,sheetlbl,db,sheet,signalid",
                   "sig", "name", o, limit, chi_tiet)
    except Exception:
        return []
    finally:
        if con is not None:
            con.close()
    tot = {}
    for d, r in ra:
        if r not in tot or d > tot[r]:
            tot[r] = d
    kq = sorted(tot.items(), key=lambda x: (-x[1], len(x[0][0] or ""), x[0][0] or ""))
    return [r for r, _d in kq[:limit]]


def o_hut(o, *chi_tiet):
    """Cac o tu khoa KHONG khop duoc dong nao - tra ve danh sach chi so o.
    Bao duoc dieu nay la de nguoi dung biet ngay vi sao ket qua lech: hoi 'may nghien
    A qua tai' ma ca du an khong co ten trang nao noi den QUA TAI thi ket qua chi con
    la 'may nghien A', khong phai chuong trinh tra sai."""
    hut = []
    for i in range(len(o)):
        if all((ct or {}).get("df", [0] * len(o))[i] == 0 for ct in chi_tiet if ct):
            hut.append(i)
    return hut


def locate(name, out_path=None):
    """Cac vi tri (cpuname, cpuno, sheetlbl, db, sheet) cua tin hieu ten CHINH XAC."""
    out_path = out_path or index_path()
    con = None
    try:
        con = sqlite3.connect(out_path)
        return con.execute(
            "SELECT DISTINCT cpuname,cpuno,sheetlbl,db,sheet FROM sig WHERE name=?",
            (name,)).fetchall()
    except Exception:
        return []
    finally:
        if con is not None:
            con.close()


def locate_full(name, out_path=None):
    """Vi tri kem signalid: [(cpuname, cpuno, slbl, db, sheet, signalid)] cho ten CHINH XAC."""
    out_path = out_path or index_path()
    con = None
    try:
        con = sqlite3.connect(out_path)
        return con.execute(
            "SELECT DISTINCT cpuname,cpuno,sheetlbl,db,sheet,signalid FROM sig WHERE name=?",
            (name,)).fetchall()
    except Exception:
        return []
    finally:
        if con is not None:
            con.close()


def cnet_partners(name, out_path=None):
    """Cac CPU/sheet lien quan qua C-NET (cung SYSTEMLINE) voi tin hieu ten `name`."""
    out_path = out_path or index_path()
    con = None
    try:
        con = sqlite3.connect(out_path)
        lines = [r[0] for r in con.execute("SELECT DISTINCT systemline FROM cnet WHERE name=?", (name,))]
        res = []
        for sl in lines:
            for r in con.execute(
                    "SELECT DISTINCT systemline,cpuname,cpuno,sheetlbl,name FROM cnet WHERE systemline=?", (sl,)):
                res.append(r)
        return res
    except Exception:
        return []
    finally:
        if con is not None:
            con.close()
