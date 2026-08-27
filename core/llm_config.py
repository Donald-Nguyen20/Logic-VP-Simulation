# -*- coding: utf-8 -*-
"""Cau hinh nha cung cap AI cho tinh nang Explain (API key + ten model).

KHAC ban mau o 2 diem, deu vi ly do that:

1) File cau hinh nam trong THU MUC NHA (~/.tdesigner_llm.json), khong nam canh app.
   App nay la mot kho git; de file chua API key trong do thi chi can mot lan `git add -A`
   la key bi day len GitHub. Cach nay cung dong bo voi cho da luu token Claude san
   (~/.tdesigner_claude_token - xem ai_client.py). Ban .exe dong goi thi doc them file
   canh exe neu co, de mang di may khac van dung duoc.

2) Ten model MAC DINH de RONG, khong ghi cung. Do that ngay hom nay: ca hai ten trong
   ban mau deu da bi khai tu - 'gemini-2.0-flash' khong con, va
   'meta-llama/llama-3.3-70b-instruct:free' cung khong con (ban khong-":free" thi con).
   Ghi cung ten model chi la hen gio cho mot loi 404. Thay vao do, hop thoai cai dat
   co nut 'Tai danh sach model' hoi thang nha cung cap xem HIEN GIO co nhung gi.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from .llm_providers import ORDER, info

CONFIG_NAME = "llm_config.json"
HOME_NAME = ".tdesigner_llm.json"

def _defaults() -> Dict[str, Any]:
    """Sinh khoa cau hinh TU BANG nha cung cap, khong go tay tung dong. Them mot nha
    cung cap moi vao llm_providers.py la co san o key + o model, khong sot cho nao."""
    cfg: Dict[str, Any] = {
        # nha cung cap dang chon - xem danh sach trong llm_providers.ORDER
        "provider": "claude",
        "ollama_host": "http://localhost:11434",
        # Cho AI tu tra cuu them (get_source/block_function) khi ngu canh con nhanh
        # bo do. Tat di thi tra loi nhanh hon nhung thieu cac nhanh dieu kien bi cat.
        "use_tools": True,
    }
    for p in ORDER:
        if p == "claude":
            continue                      # Claude dung dang nhap Claude Code, khong co key
        if info(p).get("env"):
            cfg["%s_api_key" % p] = ""
        # De RONG co chu y: bam 'Tai danh sach model' de lay ten dang song.
        cfg["%s_model" % p] = ""
    return cfg


DEFAULT_CONFIG: Dict[str, Any] = _defaults()


def _exe_dir_path() -> str:
    """Duong dan file cau hinh CANH .exe (chi dung khi da dong goi)."""
    return str(Path(sys.argv[0]).resolve().parent / CONFIG_NAME)


def get_config_path() -> str:
    """File cau hinh dang dung. Uu tien ban canh .exe neu da co san (app xach tay),
    con lai luon la thu muc nha - de API key khong bao gio roi vao kho git."""
    if getattr(sys, "frozen", False):
        p = _exe_dir_path()
        if os.path.exists(p):
            return p
    return str(Path(os.path.expanduser("~")) / HOME_NAME)


def _atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    """Ghi ra file tam roi doi ten. Ghi thang de app tat giua chung la mat sach cau
    hinh, ke ca API key nguoi dung vua dan vao."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)      # file co API key: chi chu may doc duoc
        except OSError:
            pass


def load_llm_config() -> Dict[str, Any]:
    """Doc cau hinh. Moi truong hop hong (chua co / sai JSON / bi khoa) deu tra ve
    ban mac dinh de app van chay, khong nem loi ra giao dien."""
    path = get_config_path()
    if not os.path.exists(path):
        return dict(DEFAULT_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return dict(DEFAULT_CONFIG)
    cfg = dict(DEFAULT_CONFIG)
    if isinstance(data, dict):
        cfg.update({k: v for k, v in data.items() if k in cfg})
    return cfg


def save_llm_config(cfg: Dict[str, Any]) -> None:
    safe = dict(DEFAULT_CONFIG)
    safe.update({k: cfg.get(k, safe[k]) for k in safe})
    _atomic_write_json(get_config_path(), safe)


def api_key(provider: str, cfg: Dict[str, Any] | None = None) -> str:
    """API key cua 1 nha cung cap. Bien moi truong duoc uu tien hon file - de may nao
    khong muon luu key xuong dia thi dat bien moi truong la xong."""
    provider = (provider or "").strip().lower()
    env = info(provider).get("env") or ""
    if env and os.environ.get(env):
        return os.environ[env].strip()
    cfg = cfg or load_llm_config()
    return (cfg.get("%s_api_key" % provider) or "").strip()


def mask(key: str) -> str:
    """Hien key ra man hinh/nhat ky ma khong lo ca chuoi."""
    key = (key or "").strip()
    if not key:
        return "(chua co)"
    return "%s...%s (%d ky tu)" % (key[:4], key[-4:], len(key)) if len(key) > 12 else "(da co)"
