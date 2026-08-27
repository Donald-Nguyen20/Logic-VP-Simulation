# -*- coding: utf-8 -*-
"""DUONG RIENG cho NVIDIA NIM. Khong nha cung cap nao khac di qua day.

Vi sao phai tach rieng thay vi dung chung lop OpenAI:

NVIDIA la nha DUY NHAT trong bang tra ve mot danh sach model KHONG khop voi thuc
te goi duoc. Do that thang 8-2026: GET /v1/models tra 84 ten, nhung ten dau bang
theo bang chu cai la '01-ai/yi-large' - goi vao thi 404 'Function ... Not found
for account'. Model do da ngung tu lau, NVIDIA van de trong danh sach.

Hai bo loc dung chung cho cac nha khac deu VO HIEU o day, vi moi ban ghi cua
NVIDIA chi co dung 4 truong: id, object, created, owned_by.
  - loc theo 'supported_parameters' (biet model co goi duoc cong cu khong): khong co
  - loc theo 'context_length'      (biet cua so ngu canh du rong khong): khong co
  - 'created' thi 84 model deu cung mot so -> khong biet cai nao moi cai nao cu
Chi con loc theo TEN, ma ten thi khong noi len model con song hay da chet.

Vi vay o day doi cach: KHONG doan qua ten nua ma DO THAT - goi thu tung model mot
cau ngan (max_tokens=1), 404 la da ngung thi bo di. Chi tin dung mot dau hieu 404
vi do la dau hieu duy nhat da thay tan mat; cac ma loi khac deu xep vao 'chua ro'
va van giu lai trong danh sach, de mot ma loi la khong lam mat model dang chay.

File nay KHONG import llm_client (llm_client import nguoc lai day) va khong dung
toi duong cua Groq/Gemini/Ollama.
"""
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

import requests

from . import llm_providers as PROV

_D = PROV.OPENAI_COMPAT["nvidia"]

# Do song chet: goi that nhung xin dung 1 token, de khong ton han muc cua nguoi dung.
_CHO_MOI_LAN = 25.0     # cho toi da cho MOT lan do
_CHO_CA_ME = 55.0       # cho toi da cho CA me - qua thi phan con lai de 'chua ro'
_SO_LUONG = 10          # so lan do chay song song

# Ten khong phai model tra loi. Danh sach NVIDIA tron ca model nhung van ban, do an
# toan, doc anh vao mot cho - de nguyen thi nguoi van hanh chon nham.
_KHONG_CHAT = ("embed", "rerank", "guard", "safety", "topic-control", "moderation",
               "whisper", "-tts", "tts-", "-ocr", "diffusion", "stable-diffusion",
               "-image", "image-generation", "retriever")

# Cong cu gia chi de HOI may chu 'co nhan cong cu khong'. Khong dung cong cu that
# cua app: buoc do khong duoc dung toi co so du lieu va phai gui goi tin that nho.
_CONG_CU_THU = [{
    "type": "function",
    "function": {
        "name": "thu",
        "description": "chi de do xem may chu co nhan cong cu khong",
        "parameters": {"type": "object", "properties": {"x": {"type": "string"}}},
    },
}]

SONG = "song"                    # goi duoc, va goi duoc kem cong cu
SONG_KHONG_CONG_CU = "khong_cu"  # goi duoc nhung tu choi cong cu -> Explain kem chinh xac
CHET = "chet"                    # 404: model da ngung, khong bao gio goi duoc
CHUA_RO = "chua_ro"              # mang loi / bi chan / may chu ban -> giu lai, xep duoi
CAN_KEY = "can_key"              # 401/403: key bi tu choi CHO RIENG model nay

# Key sai thi MOI model deu bi tu choi. Thay tung nay lan lien tiep deu tu choi
# thi ket luan la key sai va dung do tiep - khong bat nguoi dung cho het ca me.
# Nguoc lai, vai lan 403 le te giua nhung lan thanh cong chi la model do rieng
# tai khoan nay khong duoc dung, khong duoc vi the ma bo ca danh sach.
_DU_DE_KET_LUAN = 8

_CAU_LOI_KEY = ("NVIDIA: API key bi tu choi - KHONG model nao goi duoc. Kiem "
                "tra lai key da chep du chua (key NVIDIA bat dau bang "
                "'nvapi-'), hoac tao key moi o trang build.nvidia.com")


# --------------------------------------------------------------------------- #
#  Danh sach tho + xep thu tu                                                  #
# --------------------------------------------------------------------------- #
def danh_sach_tho(timeout: int = 30) -> List[str]:
    """Cac ten NVIDIA dang khai. Diem cuoi nay CONG KHAI - khong can key."""
    r = requests.get("%s/models" % _D["base"], timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError("NVIDIA: khong lay duoc danh sach model (HTTP %d). %s"
                           % (r.status_code, (r.text or "")[:200]))
    d = r.json()
    items = d.get("data") if isinstance(d, dict) else d
    out = []
    for m in (items or []):
        if isinstance(m, dict):
            ten = (m.get("id") or "").strip()
            if ten and not any(x in ten.lower() for x in _KHONG_CHAT):
                out.append(ten)
    return sorted(set(out))


_SO = re.compile(r"(\d+)(?:\.(\d+))?(?![a-z0-9])")


def _khoa_ten(ten: str) -> tuple:
    """Xep trong cung mot nhom: cung dong model nam canh nhau, ban MOI dung truoc.

    Giong tinh than cua llm_client._xep_model nhung viet rieng o day de file nay
    khong phu thuoc vao llm_client - sua ben do khong lam hong duong NVIDIA va
    nguoc lai."""
    t = (ten or "").lower()
    m = _SO.search(t)
    if not m:
        return (t, 0, 0, t)
    ho = t[:m.start()] + "-" + t[m.end():]
    return (ho, -int(m.group(1)), -int(m.group(2) or 0), t)


def _xep(ket_qua: Dict[str, str]) -> List[str]:
    """Da do xong -> danh sach cuoi. Bo han model da chet, con lai xep:
         1. goi duoc VA goi duoc cong cu   (Explain can cong cu moi tra cuu them)
         2. goi duoc nhung khong co cong cu
         3. chua do duoc (mang loi, bi chan) - de cuoi cho ai muon thu

    Dong dau bang la thu hop thoai cai dat tu dien vao o Model, nen dong do bat
    buoc phai la thu bam Kiem tra vao la chay."""
    nhom = {SONG: 0, SONG_KHONG_CONG_CU: 1, CHUA_RO: 2, CAN_KEY: 2}
    con = [(nhom.get(v, 2), _khoa_ten(k), k) for k, v in ket_qua.items() if v != CHET]
    return [k for _, _, k in sorted(con)]


# --------------------------------------------------------------------------- #
#  Do song chet                                                                #
# --------------------------------------------------------------------------- #
def do_mot(key: str, ten: str, timeout: float = _CHO_MOI_LAN) -> str:
    """Goi thu MOT model. Tra ve SONG / SONG_KHONG_CONG_CU / CHET / CHUA_RO.

    Chi 404 moi ket luan la chet. Loi 400/422/429/5xx deu de CHUA_RO va van giu
    model lai: mot ma loi la khong duoc phep xoa mot model dang chay khoi o chon."""
    h = {"Authorization": "Bearer %s" % key, "Content-Type": "application/json"}
    h.update(_D.get("headers") or {})
    goi = {"model": ten, "messages": [{"role": "user", "content": "hi"}],
           "max_tokens": 1, "temperature": 0, "tools": _CONG_CU_THU}
    try:
        r = requests.post("%s/chat/completions" % _D["base"], headers=h,
                          json=goi, timeout=timeout)
    except requests.RequestException:
        return CHUA_RO
    if r.status_code < 300:
        return SONG
    if r.status_code == 404:
        return CHET
    if r.status_code in (401, 403):
        # Chua ket luan duoc o day: 403 co the la key sai, ma cung co the la
        # rieng model nay tai khoan khong duoc dung. De do_ca_me nhin ca me
        # roi moi ket luan.
        return CAN_KEY
    if r.status_code in (400, 422):
        t = (r.text or "").lower()
        # Tu choi vi cong cu = model VAN SONG, chi la khong goi duoc cong cu.
        if "tool" in t or "function" in t:
            return SONG_KHONG_CONG_CU
    return CHUA_RO


def do_ca_me(key: str, tens: List[str], timeout: float = _CHO_MOI_LAN,
             han_giay: float = _CHO_CA_ME) -> Dict[str, str]:
    """Do nhieu model mot luc. Ten nao chua do kip trong han thi de CHUA_RO.

    Nem loi khi - va chi khi - MOI lan do deu bi tu choi key: do moi la dau hieu
    key sai. Mot vai lan 403 le te chi la nhung model tai khoan nay khong duoc
    dung, khong duoc vi the ma bo ca danh sach."""
    ket = {t: CHUA_RO for t in tens}
    if not tens:
        return ket
    xong = 0
    so_key = 0
    with ThreadPoolExecutor(max_workers=_SO_LUONG) as pool:
        viec = {pool.submit(do_mot, key, t, timeout): t for t in tens}
        try:
            for f in as_completed(viec, timeout=han_giay):
                try:
                    v = f.result()
                except Exception:
                    v = CHUA_RO     # mot ten hong khong duoc lam hong ca me
                ket[viec[f]] = v
                xong += 1
                so_key += (v == CAN_KEY)
                if so_key == xong >= _DU_DE_KET_LUAN:
                    break           # key sai that: dung do tiep cho do mat thi gio
        except Exception:
            pass                    # het gio: phan con lai giu CHUA_RO
        finally:
            for f in viec:
                f.cancel()
    if xong and so_key == xong:
        raise RuntimeError(_CAU_LOI_KEY)
    return ket


# --------------------------------------------------------------------------- #
#  Ham hop thoai cai dat goi                                                   #
# --------------------------------------------------------------------------- #
def models(key: str = "", timeout: int = 30) -> List[str]:
    """Danh sach model NVIDIA DUNG DUOC THAT, dong dau la thu chay duoc ngay.

    Chua co key thi khong do duoc - tra ve danh sach tho nhu cu (van con model da
    ngung trong do, nhung do la tat ca nhung gi NVIDIA chiu noi)."""
    tho = danh_sach_tho(timeout)
    key = (key or "").strip()
    if not key or not tho:
        return tho
    ket = do_ca_me(key, tho, timeout=min(float(timeout), _CHO_MOI_LAN))
    ra = _xep(ket)
    # Chan an toan: neu do ma thanh ra khong con gi (may chu doi cach bao loi, mang
    # hong giua chung...) thi tra lai danh sach tho. O chon rong con te hon o chon
    # co lan model cu.
    return ra or tho


def thong_ke(ket_qua: Dict[str, str]) -> Dict[str, int]:
    """Dem theo tung loai, de noi duoc con so that cho nguoi van hanh."""
    d = {SONG: 0, SONG_KHONG_CONG_CU: 0, CHET: 0, CHUA_RO: 0, CAN_KEY: 0}
    for v in ket_qua.values():
        if v in d:
            d[v] += 1
    return d


# NVIDIA khong noi 'model khong ton tai' ma noi 'khong thay ham nay cho tai khoan':
#   {"status":404,"title":"Not Found","detail":"Function '23bd...' Not found for
#    account 'T2Yd...'"}
# Cau nay de nguyen thi nguoi van hanh tuong minh bi tu choi tai khoan, va loi
# chung 404 lai bao 'bam Tai danh sach model lai' - bam lai van ra dung ten do.
_LOI_404 = re.compile(r"function\s+'[^']*'\s+not found for account", re.I)


def giai_thich_404(body: str) -> str:
    """Than loi 404 cua NVIDIA -> cau noi ro phai lam gi. Khong phai thi ''."""
    if not _LOI_404.search(body or ""):
        return ""
    return ("model nay CON trong danh sach cua NVIDIA nhung da ngung chay - NVIDIA "
            "khong go ten da chet khoi danh sach nen bam 'Tai danh sach model' lai "
            "van ra dung ten do. Khong phai loi API key. Cach lam: dan API key vao o "
            "ben canh TRUOC, roi moi bam 'Tai danh sach model' - app se do thu tung "
            "model va chi giu lai nhung cai goi duoc that, sau do chon dong DAU tien")
