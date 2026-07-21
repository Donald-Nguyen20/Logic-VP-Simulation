# -*- coding: utf-8 -*-
"""Chi muc TRA CUU chung cho ca du an (nhieu file DB) -> tra tin hieu & C-NET tuc thi,
khong quet lai tung DB. Luu ra 1 file SQLite, cache theo dau thoi gian file.
KHONG dung embeddings - bo truy xuat chinh la engine do thi cua app."""
from __future__ import annotations
import os
import sqlite3
import hashlib
from . import dbreader as D


def index_path():
    return os.path.join(os.path.expanduser("~"), ".tdesigner_index.db")


def _sig(db_paths):
    h = hashlib.sha1()
    for p in sorted(db_paths):
        try:
            h.update(("%s|%d|%d;" % (os.path.abspath(p), int(os.path.getmtime(p)),
                                     os.path.getsize(p))).encode())
        except Exception:
            h.update(p.encode())
    return h.hexdigest()


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


def build(db_paths, out_path=None):
    """Dung lai index tu danh sach file DB. Tra ve duong dan file index."""
    out_path = out_path or index_path()
    tmp = out_path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    con.execute("CREATE TABLE sig(name TEXT, db TEXT, cpuno TEXT, cpuname TEXT, "
                "sheet INT, sheetlbl TEXT, signalid TEXT)")
    con.execute("CREATE TABLE cnet(systemline TEXT, name TEXT, cpuno TEXT, cpuname TEXT, "
                "db TEXT, sheet INT, sheetlbl TEXT)")
    con.execute("CREATE TABLE meta(key TEXT, val TEXT)")
    for p in db_paths:
        try:
            meta = D.db_meta(p)
        except Exception:
            meta = {}
        cpuno = str(meta.get("cpuno") or ""); cpuname = meta.get("cpuname") or ""
        try:
            c = sqlite3.connect(p).cursor()
        except Exception:
            continue
        num = _num_map(c)
        try:
            rows = c.execute("SELECT ID,SIGNALID,LINENAME,SYSTEMLINE FROM CAD_ID").fetchall()
        except Exception:
            rows = []
        for sid, sigid, ln, sysl in rows:
            ln = D._clean(ln); sysl = D._clean(sysl); sigid = D._clean(sigid)
            slbl = num.get(sid, str(sid))
            if ln:
                con.execute("INSERT INTO sig VALUES(?,?,?,?,?,?,?)",
                            (ln, p, cpuno, cpuname, sid, slbl, sigid))
            if sysl:
                con.execute("INSERT INTO cnet VALUES(?,?,?,?,?,?,?)",
                            (sysl, ln, cpuno, cpuname, p, sid, slbl))
    con.execute("CREATE INDEX ix_sig_name ON sig(name)")
    con.execute("CREATE INDEX ix_cnet_line ON cnet(systemline)")
    con.execute("CREATE INDEX ix_cnet_name ON cnet(name)")
    con.execute("INSERT INTO meta VALUES('sig', ?)", (_sig(db_paths),))
    con.commit(); con.close()
    if os.path.exists(out_path):
        os.remove(out_path)
    os.rename(tmp, out_path)
    return out_path


def ensure(db_paths, out_path=None):
    """Dung index neu chua co / DB da doi. Tra ve duong dan index."""
    out_path = out_path or index_path()
    want = _sig(db_paths)
    try:
        con = sqlite3.connect(out_path)
        cur = con.execute("SELECT val FROM meta WHERE key='sig'").fetchone()
        con.close()
        if cur and cur[0] == want:
            return out_path
    except Exception:
        pass
    return build(db_paths, out_path)


def find(query, limit=300, out_path=None):
    """Tim tin hieu theo ten (LIKE). Tra ve [(name, cpuname, cpuno, sheetlbl, db, sheet, signalid)]."""
    out_path = out_path or index_path()
    try:
        con = sqlite3.connect(out_path)
        rows = con.execute(
            "SELECT DISTINCT name,cpuname,cpuno,sheetlbl,db,sheet,signalid FROM sig "
            "WHERE UPPER(name) LIKE ? ORDER BY name LIMIT ?",
            ("%" + query.upper() + "%", limit)).fetchall()
        con.close()
        return rows
    except Exception:
        return []


def locate(name, out_path=None):
    """Cac vi tri (cpuname, cpuno, sheetlbl, db, sheet) cua tin hieu ten CHINH XAC."""
    out_path = out_path or index_path()
    try:
        con = sqlite3.connect(out_path)
        rows = con.execute(
            "SELECT DISTINCT cpuname,cpuno,sheetlbl,db,sheet FROM sig WHERE name=?",
            (name,)).fetchall()
        con.close()
        return rows
    except Exception:
        return []


def locate_full(name, out_path=None):
    """Vi tri kem signalid: [(cpuname, cpuno, slbl, db, sheet, signalid)] cho ten CHINH XAC."""
    out_path = out_path or index_path()
    try:
        con = sqlite3.connect(out_path)
        rows = con.execute(
            "SELECT DISTINCT cpuname,cpuno,sheetlbl,db,sheet,signalid FROM sig WHERE name=?",
            (name,)).fetchall()
        con.close()
        return rows
    except Exception:
        return []


def cnet_partners(name, out_path=None):
    """Cac CPU/sheet lien quan qua C-NET (cung SYSTEMLINE) voi tin hieu ten `name`."""
    out_path = out_path or index_path()
    try:
        con = sqlite3.connect(out_path)
        lines = [r[0] for r in con.execute("SELECT DISTINCT systemline FROM cnet WHERE name=?", (name,))]
        res = []
        for sl in lines:
            for r in con.execute(
                    "SELECT DISTINCT systemline,cpuname,cpuno,sheetlbl,name FROM cnet WHERE systemline=?", (sl,)):
                res.append(r)
        con.close()
        return res
    except Exception:
        return []
