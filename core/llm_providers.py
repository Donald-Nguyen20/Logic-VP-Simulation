# -*- coding: utf-8 -*-
"""BANG NHA CUNG CAP AI - chi la du lieu, khong goi mang, khong import gi cua app.

Tach rieng ra day vi ca llm_config.py (sinh khoa cau hinh) lan llm_client.py (goi
HTTP) deu can bang nay; de o mot trong hai file kia thi hai file phai import cheo.

Moi dia chi trong bang deu da DO THAT (thang 8-2026) bang cach goi {base}/models
khong kem key: 401/403 = dia chi dung, chi thieu key. Hai cai bi loai sau khi do:
  - GitHub Models : tra 410 'github_models_retirement_brownout' - dang khai tu.
  - Fireworks AI  : trang lay key 404 - khong dam chac dan nguoi dung di dau.

Bang nay chi giu nhung nha DUNG DUOC MIEN PHI.

KHONG ghi cung ten model o day. Ten model chet rat nhanh (gemini-2.0-flash va
llama-3.3-70b-instruct:free deu da bi bo trong vong may thang) - hop thoai cai dat
hoi thang nha cung cap xem HIEN GIO co gi.
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple

# Nha cung cap dung chuan /chat/completions cua OpenAI -> chung mot lop client.
#   base   : goc cua API (them /chat/completions, /models vao sau)
#   keys   : trang de nguoi dung tu lay API key (nut "Lay API key" mo trang nay)
#   env    : bien moi truong duoc uu tien hon key luu trong file
#   free   : True = co the dung that ma khong can the tin dung
#   public : True = xem duoc danh sach model TRUOC khi co key
OPENAI_COMPAT: Dict[str, Dict[str, Any]] = {
    "groq": {
        "label": "Groq (mien phi - nhanh nhat)",
        "base": "https://api.groq.com/openai/v1",
        "keys": "https://console.groq.com/keys",
        "env": "GROQ_API_KEY", "timeout": 180, "free": True, "public": False,
        "note": "Mien phi, tra loi nhanh nhat trong cac nha cloud. Dang ky bang email.",
    },
    "nvidia": {
        "label": "NVIDIA NIM (mien phi - nhieu model)",
        "base": "https://integrate.api.nvidia.com/v1",
        "keys": "https://build.nvidia.com/models",
        "env": "NVIDIA_API_KEY", "timeout": 220, "free": True, "public": True,
        "note": "Mien phi theo han muc. Chon 1 model roi bam 'Get API Key' tren trang do.",
    },
    "mistral": {
        "label": "Mistral (mien phi co han muc)",
        "base": "https://api.mistral.ai/v1",
        "keys": "https://console.mistral.ai/api-keys",
        "env": "MISTRAL_API_KEY", "timeout": 180, "free": True, "public": False,
        "note": "Ban mien phi phai bat trong Console truoc khi tao key.",
    },
}

# Ba nha cung cap KHONG theo chuan OpenAI - moi cai mot duong rieng.
SPECIAL: Dict[str, Dict[str, Any]] = {
    "claude": {
        "label": "Claude (Claude Code tren may)",
        "keys": "", "env": "", "free": True,
        "note": "Dung dang nhap Claude Code co san tren may nen KHONG can API key.",
    },
    "gemini": {
        "label": "Gemini (Google - mien phi co han muc)",
        "keys": "https://aistudio.google.com/apikey",
        "env": "GEMINI_API_KEY", "free": True,
        "note": "Mien phi theo han muc moi phut. Tao key ngay trong AI Studio. "
                "Goi Gemini Pro / Advanced tra tien la cho APP Gemini, KHONG cap "
                "key cho phan mem - van phai tao key rieng o AI Studio.",
    },
    "ollama": {
        "label": "Ollama (chay tai may - mien phi)",
        "keys": "https://ollama.com/download",
        "env": "", "free": True,
        "note": "Chay ngay tren may nay, khong can key va khong can mang. "
                "Cai Ollama roi tai model ve truoc.",
    },
}

# Thu tu hien trong o chon: Claude truoc, roi cac nha cloud, cuoi la Ollama.
# Chi giu nhung nha DUNG DUOC MIEN PHI - nguoi van hanh khong phai nap the de xem
# giai thich mot tin hieu. Da bo Together AI, DeepSeek, xAI Grok, OpenAI vi ca bon
# deu bat nap tien truoc moi goi duoc.
# Bo Cerebras 8-2026: ho doi phan mien phi thanh $5 credit het han sau 30 ngay,
# het credit la moi lan goi tra HTTP 402 payment_required du chua dung token nao.
# Bo OpenRouter 8-2026: ban ':free' chi cho 50 luot/ngay neu chua nap du $10, ma
# mot lan Explain an trung binh 6,2 luot tra cuu (xem MAX_TURNS) - chua toi 8 cau
# hoi la het ngay. Cac ban ':free' con chay chung mot be nen hay tra 429 kem
# 'limit_source: upstream_provider_shared_pool' du ta chua goi qua nhanh.
# Bo SambaNova 8-2026: diem cuoi /models cua ho khong khai model nao goi duoc
# cong cu (do that: 0/7 muc co 'supported_parameters'), nen bo loc o
# _openai_models mu hoan toan voi nha nay - nguoi dung chon phai gemma-4-31B-it
# la Explain hong ngay luot tra cuu dau ma app khong canh bao truoc duoc.
# Ngoai ra 3/6 model cua ho da co san o Groq va NVIDIA, nhanh hon.
ORDER: List[str] = [
    "claude",
    "groq", "nvidia", "mistral", "gemini",
    "ollama",
]


def info(provider: str) -> Dict[str, Any]:
    """Mo ta 1 nha cung cap. Ten la khong biet thi tra ve dict rong, khong nem loi."""
    p = (provider or "").strip().lower()
    return OPENAI_COMPAT.get(p) or SPECIAL.get(p) or {}


def providers() -> List[Tuple[str, str]]:
    """[(ma, nhan)] theo dung thu tu hien ra man hinh."""
    return [(p, info(p).get("label", p)) for p in ORDER if info(p)]


def needs_key() -> Tuple[str, ...]:
    """Nhung nha cung cap phai co API key moi goi duoc."""
    return tuple(p for p in ORDER if info(p).get("env"))


def free_ones() -> List[str]:
    """Nhung nha dung duoc THAT ma khong can the tin dung."""
    return [p for p in ORDER if info(p).get("free")]


def key_pages() -> Dict[str, str]:
    """Trang lay key/tai ve cua tung nha cung cap (Claude khong co - khong can key)."""
    return {p: info(p)["keys"] for p in ORDER if info(p).get("keys")}
