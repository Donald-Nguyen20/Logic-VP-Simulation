# -*- coding: utf-8 -*-
"""Goi AI qua HTTP cho moi nha cung cap ngoai Claude (13 cai - xem llm_providers.py).

Ban mau trong 'cach get API' chi co generate(prompt) -> str: hoi 1 lan, tra 1 lan.
Dung nguyen nhu the cho Explain thi 26% tin hieu se tra loi thieu, vi ngu canh cua
chung con tu 9 den 59 nhanh dieu kien bi cat o gioi han truy nguoc - phai TRA CUU
THEM moi du. Vi vay o day them VONG LAP GOI CONG CU (ask), giong dieu Claude dang
lam, cho ca 3 chuan giao thuc khac nhau:

  - Groq / NVIDIA     : chuan OpenAI  -> message.tool_calls  + role "tool"
  - Gemini            : chuan Google  -> parts.functionCall  + functionResponse
  - Ollama            : /api/chat     -> message.tool_calls  (ban moi)

Ba diem KHAC ban mau, deu co ly do do duoc:

1) max_tokens 900 -> 4000. Cau tra loi Explain dat muc tieu ~600 tu co bang bieu;
   900 token cat cau tra loi giua chung.
2) KHONG ghi cung ten model. Kiem tra ngay hom nay: 'gemini-2.0-flash' da bo, va
   'meta-llama/llama-3.3-70b-instruct:free' cung da bo (ban khong-':free' con song).
   Thay bang list_models(): hoi thang nha cung cap xem hien gio co gi.
3) API_PAGES: dia chi trang lay key, de nut 'Lay API key' mo dung cho.

Danh sach nha cung cap nam trong llm_providers.py, KHONG liet ke lai o day: 10 nha
dung chung chuan OpenAI nen chung mot lop client, chi khac goc dia chi va thoi gian
cho. Them mot nha moi = them mot muc trong bang do, khong sua file nay.
"""
from __future__ import annotations
import re
import time
from typing import Callable, Dict, List, Tuple

import requests

from . import ai_toolspec as TS
from . import llm_nvidia as NV
from . import llm_providers as PROV
from .llm_config import api_key as _cfg_key, load_llm_config

_MAX_TOKENS_CHAT = 4000
_MAX_TOKENS_TRACUU = 1200   # luot tra cuu chi can du cho mot loi goi cong cu
# Dong Gemini 3 SUY NGHI truoc khi tra loi, va phan suy nghi cung tru vao han muc
# nay. Do that tren tai khoan that: hoi dung 1 chu ma model suy nghi het 45-141
# token. Cau tra loi Explain dai hon nhieu nen phan suy nghi cung dai theo. Han muc
# cu 4096 de bi suy nghi an het -> model tra ve 200 ma khong co chu nao. Han muc chi
# la tran, khong tieu thi khong tinh tien, nen de rong.
_MAX_TOKENS_GEMINI = 16384
_OLLAMA_NUM_PREDICT = 2048
_OLLAMA_NUM_CTX = 32768

# So luot toi da AI duoc phep tra cuu them. Do tren 232 tin hieu: nang nhat can 59
# luot, trung binh 6,2. 40 phu het gan hoan toan phan thuong gap ma van chan duoc
# truong hop AI goi cong cu lap vo tan (co that voi cac model nho).
MAX_TURNS = 40

# Model cua so nho se vo giua chung: ngu canh Explain dai, lai con goi cong cu
# nhieu luot. 60k la nguong do tu ngu canh that cua 232 tin hieu trong du an.
MIN_CONTEXT = 60000

# Ten khong phai model tra loi (nhung ban nao co danh sach lan lon vao).
# Ten model co nhung tu nay thi no lam viec khac (ve anh, doc tieng noi, do an
# toan, nhung van ban) - dua vao o chon chi lam nguoi van hanh chon nham.
_NOT_CHAT = ("embed", "rerank", "whisper", "-tts", "tts-", "moderation",
             "imagen", "veo", "dall-e", "stable-diffusion", "image-generation",
             "-image", "guard", "-ocr", "aqa")

# Ten model co nhung tu nay la ban chay thu: hom nay chay duoc, mai bo, hoac thieu
# tinh nang. Vd 'antigravity-preview-05-2026' khong nhan ca loi dan he thong. Van
# de trong danh sach cho ai muon thu, nhung day xuong duoi.
_BAN_THU = ("preview", "-exp", "experimental", "antigravity", "thinking",
            "-rc", "alpha", "beta", "nightly")


# So phien ban trong ten model: '3.7' cua gemini-3.7-flash, '4' cua llama-4-scout.
# Chan chu ngay sau so de khong nham kich thuoc voi phien ban - '120b', '70b',
# '17b' la so tham so chu khong phai doi model.
_SO_BAN = re.compile(r"(\d+)(?:\.(\d+))?(?![a-z0-9])")


def _ban(ten: str):
    """('ho model', doi, ban nho). gemini-3.7-flash -> ('gemini--flash', 3, 7).

    'Ho model' la ten da boc so phien ban ra, de cac doi cua cung mot dong nam canh
    nhau. Ten khong co so phien ban thi ho la chinh no."""
    m = _SO_BAN.search(ten)
    if not m:
        return (ten, 0, 0)
    ho = ten[:m.start()] + "-" + ten[m.end():]
    return (ho, int(m.group(1)), int(m.group(2) or 0))


def _xep_model(ten: str) -> tuple:
    """Khoa sap xep: (nhom, ho model, doi moi nhat truoc, ten).

    Muc dich la dong DAU TIEN cua danh sach phai la thu bam Luu vao la dung duoc -
    hop thoai cai dat chon san dong dau sau khi tai danh sach. Trong cung mot dong
    model thi ban MOI dung truoc: nha cung cap khai tu ban cu lien tuc (Gemini 2.5
    da bi chan voi nguoi dung moi chi sau mot nam), de ban cu lam mac dinh la day
    nguoi van hanh vao loi 404.

    Giua cac dong model khac nhau van xep theo bang chu cai - khong doan mo dong
    nao 'hay hon', do la viec cua nguoi van hanh."""
    t = (ten or "").lower()
    ho, doi, nho = _ban(t)
    return (1 if any(x in t for x in _BAN_THU) else 0, ho, -doi, -nho, t)

# Explain song bang viec AI tu tra cuu (goi cong cu). Model khong lam duoc viec do
# se bi may chu tu choi thang - moi nha lai noi mot kieu nen phai do nhieu cach.
_TOOL_REJECT = (
    "tool calling is not supported",
    "tool use is not supported",
    "tools is not supported",
    "does not support tools",
    "does not support tool",
    "function calling is not supported",
    "no endpoints found that support tool use",
)


def is_sysinstr_reject(err: object) -> bool:
    """Loi nay co phai 'model khong nhan loi dan he thong' khong?

    Google goi loi dan he thong la 'Developer instruction'; vai model (cac ban
    preview) khong bat tinh nang do va tu choi thang."""
    t = str(err).lower()
    return ("developer instruction" in t or "system_instruction" in t
            or "systeminstruction" in t)


def is_tool_reject(err: object) -> bool:
    """Loi nay co phai 'model khong biet goi cong cu' khong?

    Groq viet co dau ngoac nguoc: `tool calling` is not supported - nen phai bo dau
    nhay va gop khoang trang truoc khi so, khong so chuoi tho."""
    t = str(err).lower()
    for ch in ("`", "'", '"'):
        t = t.replace(ch, " ")
    t = " ".join(t.split())
    if any(x in t for x in _TOOL_REJECT):
        return True
    # Luat chung: nhac toi cong cu VA noi la khong ho tro - phong nhung cach dien
    # dat khac ma ta chua gap.
    co_tool = "tool" in t or "function calling" in t
    khong = ("not supported" in t or "unsupported" in t or "does not support" in t
             or "no endpoints" in t)
    return co_tool and khong

PROVIDERS: List[Tuple[str, str]] = PROV.providers()
API_PAGES: Dict[str, str] = PROV.key_pages()
NEEDS_KEY: Tuple[str, ...] = PROV.needs_key()


def label(provider: str) -> str:
    return PROV.info(provider).get("label") or provider or "?"


def short(provider: str) -> str:
    """Ten ngan de dat len nut ("Ask Groq") va trong cau bao loi."""
    return label(provider).split(" (")[0]


def free_count() -> int:
    """So nha cung cap (khong ke Claude) dung duoc ma khong mat tien - de hop thoai
    cai dat noi duoc con so that thay vi noi chung chung."""
    return len([p for p in PROV.free_ones() if p != "claude"])


def note(provider: str) -> str:
    """Mot cau nhac ve nha cung cap do: mien phi hay tra phi, lay key o dau."""
    return PROV.info(provider).get("note") or ""


# --------------------------------------------------------------------------- #
#  Danh sach model - hoi TRUC TIEP nha cung cap                                #
# --------------------------------------------------------------------------- #
def list_models(provider: str, key: str = "", host: str = "", timeout: int = 30) -> List[str]:
    """Ten cac model dang song cua 1 nha cung cap. Nem ngoai le neu hoi khong duoc,
    de hop thoai cai dat noi ro ly do (sai key / khong mang / Ollama chua chay)."""
    provider = (provider or "").strip().lower()
    key = (key or "").strip()

    # NVIDIA di duong RIENG (core/llm_nvidia.py): danh sach cua ho con lan ca
    # model da ngung chay va khong khai gi de loc ra - phai do that tung cai.
    if provider == "nvidia":
        return NV.models(key, timeout)

    if provider in PROV.OPENAI_COMPAT:
        return _openai_models(provider, key, timeout)

    if provider == "gemini":
        r = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": key, "pageSize": 200}, timeout=timeout)
        _raise_http(r, "Gemini")
        out = []
        for m in (r.json().get("models") or []):
            if "generateContent" not in (m.get("supportedGenerationMethods") or []):
                continue
            ten = (m.get("name") or "").replace("models/", "")
            if ten and not any(x in ten.lower() for x in _NOT_CHAT):
                out.append(ten)
        return sorted(out, key=_xep_model)

    if provider == "ollama":
        host = (host or "http://localhost:11434").rstrip("/")
        try:
            r = requests.get("%s/api/tags" % host, timeout=timeout)
        except requests.RequestException as e:
            raise RuntimeError(
                "Ollama: khong noi duoc toi %s. Ollama da chay chua? "
                "Mo cua so lenh go 'ollama serve' roi thu lai. (%s)"
                % (host, type(e).__name__))
        _raise_http(r, "Ollama")
        names = sorted((m.get("name", "") for m in (r.json().get("models") or [])
                        if m.get("name")
                        and not any(x in m["name"].lower() for x in _NOT_CHAT)),
                       key=_xep_model)
        if not names:
            raise RuntimeError("Ollama dang chay nhung CHUA co model nao. "
                               "Go 'ollama pull qwen2.5:7b' de tai mot model ve truoc.")
        return names

    raise ValueError("Khong biet nha cung cap: %s" % provider)


# Google noi thang trong cau bao loi la nen doi sang model nao:
#   "...is no longer available to new users. Please update your code to use
#    models/gemini-3.6-flash for the latest features..."
# Nhat lay ten do ra thay vi bat nguoi van hanh doc JSON.
_THAY_THE = re.compile(r"use\s+(?:models/)?([a-z0-9][a-z0-9./:_-]{2,60})",
                       re.I)


def _model_thay_the(body: str) -> str:
    """Ten model nha cung cap bao dung thay, lay tu cau bao loi. Khong co thi ''."""
    t = body or ""
    if "no longer available" not in t.lower() and "deprecated" not in t.lower():
        return ""
    m = _THAY_THE.search(t)
    return (m.group(1).rstrip(".,;:'" + '"') if m else "")


# 'Limit 8000, Requested 8734' - con so that nam ngay trong than loi, doc ra de noi
# cho nguoi van hanh biet thieu bao nhieu thay vi bat ho doan.
_HAN_MUC = re.compile("limit[ ]+([0-9]+)[,.; ]+requested[ ]+([0-9]+)", re.I)


def _han_muc_phut(body: str) -> str:
    """413 vi han muc MOI PHUT cua tai khoan -> cau noi ro. Khong phai thi ''."""
    t = (body or "").lower()
    if "per minute" not in t and "tpm" not in t:
        return ""
    m = _HAN_MUC.search(t)
    if not m:
        return ("goi tin vuot han muc token MOI PHUT cua tai khoan (khong phai o nho "
                "cua model). Doi model khac - moi model mot han muc rieng - hoac nang "
                "cap tai khoan")
    han, xin = int(m.group(1)), int(m.group(2))
    cau = ("goi tin nay %d token nhung tai khoan chi duoc %d token MOI PHUT. Day la "
           "han muc cua TAI KHOAN, khong phai o nho cua model" % (xin, han))
    if xin > han:
        # Cho them mot phut cung vo ich: rieng mot goi da lon hon ca han muc ca phut.
        cau += (". Cho bao lau cung khong qua duoc vi rieng mot goi da lon hon ca han "
                "muc mot phut - phai doi model khac (moi model mot han muc rieng) hoac "
                "nang cap tai khoan")
    return cau


_DA_LUOC = "(ket qua tra cuu cu da luoc bot cho vua han muc cua tai khoan)"
_DA_CAT = "(phan sau da cat bot cho vua han muc cua tai khoan)"
_TOI_THIEU_TRA_CUU = 200    # ket qua tra cuu khong cat nho hon nay: con lai vo nghia
_TOI_THIEU_NGU_CANH = 900   # ngu canh de bai giu it nhat nay thi con tra loi duoc
_GON_TOI_DA = 3         # so lan duoc phep luoc bot roi gui lai


def _so_han_muc(body: str):
    """(han, xin) tu than loi 'Limit 8000, Requested 8734'. Khong doc duoc -> None."""
    t = (body or "").lower()
    if "per minute" not in t and "tpm" not in t:
        return None
    m = _HAN_MUC.search(t)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _uoc_token(msgs) -> int:
    """Uoc so token cua ca goi tin. ~4 ky tu mot token - du chinh xac de biet
    phai bot bao nhieu, khong can dem dung tung token."""
    n = 0
    for m in msgs or []:
        n += len(str(m.get("content") or "")) + 40
        for c in (m.get("tool_calls") or []):
            n += len(str(c))
    return n // 4


def _cat_duoi(noi_dung: str, giu_token: int) -> str:
    """Giu phan DAU, cat phan duoi. Dau ngu canh la ten tin hieu va khoi sinh ra no -
    thu quan trong nhat; duoi la cac nhanh phu, mat di van tra loi duoc."""
    giu = max(0, giu_token) * 4
    if len(noi_dung) <= giu:
        return noi_dung
    return noi_dung[:giu] + "\n" + _DA_CAT


def _luoc_tra_cuu(msgs, can_bot: int) -> int:
    """Lam nhe goi tin di `can_bot` token. Tra ve so token that su da bot duoc.

    Vi sao khong xoa han dong ket qua: chuan OpenAI bat buoc moi loi goi cong cu phai
    co mot dong ket qua di kem. Xoa di la ca cuoc hoi thoai thanh sai dinh dang va nha
    cung cap tu choi thang. Nen giu dong lai, chi thay ruot.

    Luoc theo BA MUC, nhe tay truoc:
      1. Bo han ruot cac ket qua tra cuu CU (model doc xong tu may luot truoc roi).
      2. Van chua du: cat bot duoi cua cac ket qua con lai, giu phan dau.
      3. Van chua du: cat bot chinh ngu canh gui kem trong cau hoi.
    Muc 2 va 3 la ly do bat buoc phai co: o goi thu 3 moi chi co dung 2 ket qua tra
    cuu, neu chi biet lam muc 1 thi khong co gi de bot va van bao loi nhu cu."""
    da_bot = 0

    def con_thieu():
        return can_bot - da_bot

    tra = [i for i, m in enumerate(msgs) if m.get("role") == "tool"]

    # Muc 1: cac ket qua cu nhat - bo han ruot
    chua_luoc = [i for i in tra if not (msgs[i].get("content") or "").startswith(_DA_LUOC)]
    for i in chua_luoc[:max(0, len(chua_luoc) - 1)]:
        if con_thieu() <= 0:
            break
        cu = msgs[i].get("content") or ""
        msgs[i] = dict(msgs[i], content=_DA_LUOC)
        da_bot += max(0, (len(cu) - len(_DA_LUOC)) // 4)

    # Muc 2: cat bot duoi cua nhung cai con lai, moi lan mot nua
    for i in reversed(tra):
        if con_thieu() <= 0:
            break
        cu = msgs[i].get("content") or ""
        if len(cu) <= _TOI_THIEU_TRA_CUU * 4:
            continue
        moi = _cat_duoi(cu, max(_TOI_THIEU_TRA_CUU, len(cu) // 4 - con_thieu()))
        if len(moi) < len(cu):
            msgs[i] = dict(msgs[i], content=moi)
            da_bot += (len(cu) - len(moi)) // 4

    # Muc 3: ngu canh gui kem trong cau hoi. Cham vao day sau cung vi day chinh la
    # de bai - cat qua tay thi model tra loi truot.
    if con_thieu() > 0:
        for i, m in enumerate(msgs):
            if m.get("role") != "user":
                continue
            cu = m.get("content") or ""
            if len(cu) <= _TOI_THIEU_NGU_CANH * 4:
                continue
            moi = _cat_duoi(cu, max(_TOI_THIEU_NGU_CANH, len(cu) // 4 - con_thieu()))
            if len(moi) < len(cu):
                msgs[i] = dict(m, content=moi)
                da_bot += (len(cu) - len(moi)) // 4
            break
    return da_bot


# Google ghi ten han muc trong than loi, vd:
#   "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier", "quotaValue": "20"
_QUOTA_NGAY = re.compile('"quota(?:id|metric)"[^"]*"([^"]*per[_]?day[^"]*)"', re.I)
_QUOTA_MUC = re.compile('"quotavalue"[^0-9]*([0-9]+)', re.I)


def _han_muc_ngay(body: str) -> str:
    """429 vi han muc MOI NGAY -> cau noi ro. Khong phai thi ''.

    Phai tach rieng khoi han muc theo phut vi cach xu ly nguoc han nhau: han theo
    phut thi cho vai giay la qua, con han theo ngay thi cho bao lau cung vo ich."""
    t = body or ""
    if not _QUOTA_NGAY.search(t):
        return ""
    m = _QUOTA_MUC.search(t)
    muc = (" (goi mien phi chi cho %s luot moi ngay cho moi model)"
           % m.group(1)) if m else ""
    return ("het han muc SO LUOT MOI NGAY cua tai khoan%s. Day khong phai het token "
            "va cho cung khong giup - han nay sang ngay moi mo lai (Google tinh theo "
            "gio My, khoang 14-15h chieu gio Viet Nam). Muon dung tiep ngay bay gio "
            "thi doi sang model khac trong 'Cai dat AI' - moi model mot han muc rieng "
            "- hoac bat thanh toan cho tai khoan" % muc)


def _raise_http(r, who: str) -> None:
    """Ma loi HTTP -> cau noi ro phai lam gi. Van kem nguyen van loi cua nha cung cap
    o cuoi, vi ho hay noi chinh xac hon ta doan (vd 'model nay da ngung')."""
    code = r.status_code
    if code < 400:
        return
    why = {
        400: "yeu cau bi tu choi - thuong la ten model khong dung hoac key sai dinh dang",
        401: "API key sai, het han, hoac chep thieu ky tu",
        402: "tai khoan het tien / chua nap",
        403: "API key chua duoc cap quyen (co nha bat phai kich hoat truoc khi dung)",
        404: "khong tim thay - ten model co the da bi bo, bam 'Tai danh sach model' lai",
        410: "model nay da bi go han - bam 'Tai danh sach model' de lay ten moi",
        413: "goi tin qua lon so voi han muc cho phep - chon model khac, hoac hoi "
             "mot tin hieu don gian hon",
        429: "goi qua nhanh hoac het han muc mien phi - doi mot lat roi thu lai",
        502: "duong truyen toi may chu nha cung cap dang nghen - thu lai sau vai phut",
        503: "may chu cua nha cung cap dang QUA TAI - khong phai loi cua ban va khong "
             "phai loi cau hoi. App da tu cho va hoi lai %d lan van chua duoc. Thu lai "
             "sau vai phut, hoac doi model khac trong 'Cai dat AI'" % _RETRY_LAN,
        504: "may chu nha cung cap tra loi qua cham - thu lai sau vai phut",
    }.get(code, "may chu bao loi" if code >= 500 else "loi khong ro")
    # NVIDIA bao 404 bang mot cau rieng ("Function ... Not found for account")
    # ma loi 404 chung lai khuyen sai viec phai lam - xem llm_nvidia.
    nvda = NV.giai_thich_404(r.text or "") if code == 404 else ""
    if nvda:
        why = nvda
    ngay = _han_muc_ngay(r.text or "") if code == 429 else ""
    phut = _han_muc_phut(r.text or "") if code in (413, 429) else ""
    if ngay:
        why = ngay
    elif phut:
        why = phut
    thay = _model_thay_the(r.text or "")
    if thay:
        why = ("model nay da ngung, nha cung cap bao dung '%s' thay the - bam "
               "'Tai danh sach model' roi chon lai" % thay)
    raise RuntimeError("%s: %s (HTTP %d). %s" % (who, why, code, (r.text or "")[:300]))


_RETRY_LAN = 3          # so lan hoi lai khi bi chan vi goi qua nhanh
_RETRY_TOI_DA = 90.0    # cho lau hon the thi bao loi, dung bat nguoi dung ngoi doi

# Ma loi may chu ma CHINH nha cung cap noi la tam thoi: 503 qua tai, 502/504 nghen
# duong. Khong phai loi cua nguoi dung va khong sua bang cach doi cau hoi - cho vai
# giay roi hoi lai la qua. 500 KHONG nam day: no thuong la loi that, hoi lai cung the.
_MA_TAM_THOI = (502, 503, 504)
_CHO_TAM_THOI = (3.0, 8.0, 20.0)    # cho tang dan qua tung lan hoi lai


def _doc_giay(txt: str) -> float:
    """'1.1025s', '6m0s', '20' -> so giay. Khong doc duoc thi 0."""
    txt = (txt or "").strip()
    m = re.search(r"(?:(\d+)m)?([\d.]+)s", txt)
    try:
        if m:
            return float(m.group(1) or 0) * 60 + float(m.group(2))
        return float(txt)
    except ValueError:
        return 0.0


def _gui_co_cho(gui, who: str, on_event=None):
    """Goi 'gui()'; gap loi TAM THOI thi cho roi hoi lai thay vi bat nguoi dung bam lai.

    Hai loai tam thoi, cho khac nhau:
      429 - ta goi qua nhanh. Nha cung cap noi rat sat ('try again in 1.1s') nen nghe
            theo ho. Goi mien phi cua Groq chi 8000 token/phut ma Explain hoi nhieu
            luot, cham tran la chuyen thuong ngay.
      503 - may chu HO qua tai (502/504 la nghen duong). Ho khong noi cho bao lau nen
            ta tu cho tang dan. Khong phai loi cua nguoi dung, doi cau hoi khong giup."""
    r = None
    for lan in range(_RETRY_LAN):
        r = gui()
        if r.status_code in _MA_TAM_THOI:
            if lan == _RETRY_LAN - 1:
                return r            # de _raise_http noi ro cho nguoi dung
            cho = _CHO_TAM_THOI[min(lan, len(_CHO_TAM_THOI) - 1)]
            BaseLLMClient._say(on_event, "status",
                               "May chu %s dang qua tai - cho %d giay roi hoi lai "
                               "(lan %d/%d)..." % (who, int(cho), lan + 2, _RETRY_LAN))
            time.sleep(cho)
            continue
        if r.status_code != 429:
            return r
        body = r.text or ""
        # Han theo NGAY: nha cung cap van kem dong "thu lai sau 29s" nhung nghe theo
        # la bat nguoi dung ngoi cho 3 lan roi van hong. Bao that luon.
        if _han_muc_ngay(body):
            return r
        cho = (_doc_giay(r.headers.get("retry-after", ""))
               or _doc_giay(r.headers.get("x-ratelimit-reset-tokens", ""))
               or (_doc_giay(body.split("try again in ")[1][:24])
                   if "try again in " in body else 0.0)
               or (_doc_giay(body.split('retryDelay": "')[1][:12])
                   if 'retryDelay": "' in body else 0.0))
        if cho <= 0:
            cho = 5.0 * (lan + 1)       # nha khong noi ro thi tu doi, tang dan
        if cho > _RETRY_TOI_DA or lan == _RETRY_LAN - 1:
            return r                    # de _raise_http noi ro cho nguoi dung
        BaseLLMClient._say(on_event, "status",
                           "%s dang chan vi goi qua nhanh - cho %d giay roi hoi lai..."
                           % (who, int(cho + 0.9)))
        time.sleep(cho + 0.3)
    return r


def _openai_models(provider: str, key: str, timeout: int) -> List[str]:
    """Danh sach model cho moi nha theo chuan OpenAI: GET {goc}/models.

    Rieng NVIDIA mo cong khai diem cuoi nay nen xem duoc truoc khi co key - vi
    vay chi gan Authorization khi that su co key."""
    d = PROV.OPENAI_COMPAT[provider]
    h = dict(d.get("headers") or {})
    if key:
        h["Authorization"] = "Bearer %s" % key
    r = requests.get("%s/models" % d["base"], headers=h, timeout=timeout)
    _raise_http(r, short(provider))
    data = r.json()
    items = data.get("data") if isinstance(data, dict) else data
    out = []
    for m in (items or []):
        if not isinstance(m, dict):
            continue
        mid = (m.get("id") or m.get("name") or "").strip()
        if not mid or any(x in mid.lower() for x in _NOT_CHAT):
            continue
        # Nha nao co khai model nao goi duoc cong cu thi bo cac model khong goi
        # duoc - chon phai la Explain hong ngay tu luot tra cuu dau tien. Moi nha
        # dat ten truong mot kieu: co nha 'supported_parameters', Groq
        # 'supported_features' (groq/compound chi co json_mode nen bi loai o day).
        for truong in ("supported_parameters", "supported_features"):
            sp = m.get(truong)
            if isinstance(sp, list) and sp and "tools" not in sp:
                mid = ""
                break
        if not mid:
            continue
        # Nha nao co khai cua so ngu canh thi loc luon; nha khong khai thi giu het.
        ctx = m.get("context_length") or m.get("context_window") or 0
        try:
            if ctx and int(ctx) < MIN_CONTEXT:
                continue
        except (TypeError, ValueError):
            pass
        out.append(mid)
    return sorted(set(out), key=_xep_model)


# --------------------------------------------------------------------------- #
#  Cac client                                                                  #
# --------------------------------------------------------------------------- #
class BaseLLMClient:
    name = "?"

    def ask(self, system: str, prompt: str, use_tools: bool = True,
            on_event: Callable[[str, str], None] | None = None) -> str:
        raise NotImplementedError

    # Bao ra ngoai AI dang lam gi. Loi o cho hien thi khong duoc lam hong cuoc goi.
    @staticmethod
    def _say(on_event, kind, info):
        if on_event is None:
            return
        try:
            on_event(kind, info)
        except Exception:
            pass

    @staticmethod
    def _run_tools(calls, on_event):
        """calls: [(id, ten, tham_so_dict)] -> [(id, ten, ket_qua_chuoi)]"""
        out = []
        for cid, nm, args in calls:
            BaseLLMClient._say(on_event, "tool", "%s %s" % (
                nm, args.get("name") or args.get("code") or ""))
            out.append((cid, nm, TS.dispatch(nm, args)))
        return out


class OpenAICompatibleClient(BaseLLMClient):
    """Dung cho MOI nha theo chuan /chat/completions cua OpenAI (xem llm_providers).

    Chi khac nhau goc dia chi, thoi gian cho va vai dong tieu de - nen mot lop la du."""

    def __init__(self, key: str, base_url: str, model: str, timeout: int = 180,
                 extra_headers: Dict[str, str] | None = None):
        if not key:
            raise ValueError("Chua co API key.")
        if not model:
            raise ValueError("Chua chon model - bam 'Tai danh sach model' trong Cai dat AI.")
        self.key = key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.extra = extra_headers or {}
        # Han muc token/phut cua tai khoan. Khong nha nao noi truoc - chi biet duoc khi
        # bi tu choi mot lan. Hoc duoc roi thi cac luot sau tu giu duoi nguong, khoi
        # phai dam dau vao tuong them lan nua.
        self._han_biet = 0

    def _post(self, messages, tools, on_event=None, max_tokens=0):
        h = {"Authorization": "Bearer %s" % self.key, "Content-Type": "application/json"}
        h.update(self.extra)
        msgs = list(messages)
        for lan in range(_GON_TOI_DA + 1):
            payload = {"model": self.model, "messages": msgs, "temperature": 0.1,
                       "max_tokens": max_tokens or _MAX_TOKENS_CHAT}
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            r = _gui_co_cho(lambda: requests.post("%s/chat/completions" % self.base_url,
                                                  headers=h, json=payload,
                                                  timeout=self.timeout),
                            self.name, on_event)
            # Goi tin to hon han muc MOI PHUT cua tai khoan. Do that tren du lieu that:
            # goi thu nhat chi ~5000 token, nhung moi luot tra cuu cong them toi 1500
            # nen den goi thu 3-4 la vuot 8000 (han muc goi mien phi cua Groq). Cho lau
            # bao nhieu cung vo ich - phai lam goi tin NHE DI thi moi qua duoc.
            if r.status_code in (413, 429) and lan < _GON_TOI_DA:
                han = _so_han_muc(r.text or "")
                if han:
                    self._han_biet = han[0]
                if han and _luoc_tra_cuu(msgs, han[1] - han[0] + 200):
                    self._say(on_event, "status",
                              "Goi tin %d token vuot han muc %d token/phut - luoc bot "
                              "tra cuu cu roi gui lai..." % (han[1], han[0]))
                    continue
            # Giai thich ma loi bang tieng Viet, nhung van dua nguyen van cua nha cung
            # cap ra sau: ho noi chinh xac hon ("model nay da ngung", "het han muc").
            _raise_http(r, self.name)
            return r.json()
        _raise_http(r, self.name)
        return r.json()

    def probe_tools(self) -> bool:
        """May chu co nhan yeu cau CO kem cong cu khong?

        Chi xem may chu nhan hay tu choi: khong chay cong cu nao va khong doc ket
        qua - nen re va khong dung toi co so du lieu."""
        try:
            self._post([{"role": "user", "content": "Reply with: OK"}], TS.openai_tools())
            return True
        except RuntimeError as e:
            if is_tool_reject(e):
                return False
            raise

    def ask(self, system, prompt, use_tools=True, on_event=None):
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": prompt}]
        tools = TS.openai_tools() if use_tools else None
        for _ in range(MAX_TURNS):
            # Luot con duoc phep tra cuu: dat truoc it cho o tra loi. Nha cung cap
            # tinh ca phan dat truoc vao han muc theo phut, ma luot tra cuu thuc te
            # chi dai vai chuc token.
            data = self._post(msgs, tools, on_event,
                              _MAX_TOKENS_TRACUU if tools else 0)
            # Da tung bi tu choi vi qua han thi cac luot sau tu giu duoi nguong luon.
            # Khong lam the thi moi luot lai phinh len roi lai bi tu choi, moi lan deu
            # ton them mot vong gui - lau va van ton han muc.
            if self._han_biet:
                nguong = self._han_biet - _MAX_TOKENS_CHAT - 200
                thua = _uoc_token(msgs) - nguong
                if thua > 0:
                    _luoc_tra_cuu(msgs, thua)
            ch = (data.get("choices") or [{}])[0]
            msg = ch.get("message") or {}
            tc = msg.get("tool_calls") or []
            if not tc:
                # Model tra loi luon o luot nay - neu bi cat giua chung vi cho hep
                # thi hoi lai dung luot do voi cho rong day du.
                if tools and ch.get("finish_reason") == "length":
                    data = self._post(msgs, None, on_event)
                    msg = ((data.get("choices") or [{}])[0].get("message") or {})
                txt = (msg.get("content") or "").strip()
                self._say(on_event, "text", txt)
                return txt
            msgs.append({"role": "assistant", "content": msg.get("content") or "",
                         "tool_calls": tc})
            calls = []
            for c in tc:
                fn = c.get("function") or {}
                calls.append((c.get("id"), fn.get("name") or "", _json(fn.get("arguments"))))
            for cid, nm, res in self._run_tools(calls, on_event):
                msgs.append({"role": "tool", "tool_call_id": cid, "name": nm,
                             "content": res})
        # Het luot: hoi lai lan cuoi, cam goi cong cu, de con lay duoc cau tra loi
        # tu nhung gi da tra cuu duoc - thay vi tra ve chuoi rong.
        msgs.append({"role": "user",
                     "content": "Da du du lieu. Tra loi ngay bay gio, khong tra cuu them."})
        data = self._post(msgs, None, on_event)
        return (((data.get("choices") or [{}])[0].get("message") or {})
                .get("content") or "").strip()


def make_openai_client(provider: str, key: str, model: str) -> OpenAICompatibleClient:
    """Client cho bat ky nha nao theo chuan OpenAI, lay thong so tu bang."""
    d = PROV.OPENAI_COMPAT[provider]
    cl = OpenAICompatibleClient(key, d["base"], model, timeout=d.get("timeout", 180),
                                extra_headers=d.get("headers"))
    cl.name = short(provider)      # de cau bao loi ghi dung ten nha cung cap
    return cl


class LLMClientGroq(OpenAICompatibleClient):
    name = "Groq"

    def __init__(self, key, model):
        d = PROV.OPENAI_COMPAT["groq"]
        super().__init__(key, d["base"], model, timeout=d["timeout"])


# Google bao ly do dung but o 'finishReason'. Dich sang cau noi duoc phai lam gi.
_GEMINI_DUNG_BUT = {
    "MAX_TOKENS": "model dung het han muc token truoc khi kip viet cau tra loi. "
                  "Dong Gemini 3 suy nghi truoc khi tra loi va phan suy nghi cung "
                  "an vao han muc, nen han muc phai rong hon truoc",
    "SAFETY": "Google chan cau tra loi vi bo loc noi dung",
    "PROHIBITED_CONTENT": "Google chan cau tra loi vi bo loc noi dung",
    "RECITATION": "Google chan vi cau tra loi trung voi tai lieu co ban quyen",
    "BLOCKLIST": "Google chan vi cau tra loi chua tu bi cam",
    "MALFORMED_FUNCTION_CALL": "model goi cong cu sai dinh dang - doi model khac",
}


def _gemini_vi_sao_trong(data: dict) -> str:
    """Gemini tra ve 200 ma khong co chu nao - vi sao? Cau tieng Viet noi ro."""
    cand = (data.get("candidates") or [{}])[0]
    ly_do = (cand.get("finishReason") or "").upper()
    chan = ((data.get("promptFeedback") or {}).get("blockReason") or "").upper()
    if chan:
        return "Google chan CAU HOI truoc khi model doc (%s)" % chan
    if ly_do in _GEMINI_DUNG_BUT:
        return _GEMINI_DUNG_BUT[ly_do]
    if ly_do:
        return "model dung lai voi ly do '%s'" % ly_do
    return "model tra ve rong ma khong noi ly do"


class LLMClientGemini(BaseLLMClient):
    """Gemini qua REST (khong can SDK)."""
    name = "Gemini"
    BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, key: str, model: str, timeout: int = 180):
        if not key:
            raise ValueError("Chua co API key.")
        if not model:
            raise ValueError("Chua chon model - bam 'Tai danh sach model' trong Cai dat AI.")
        self.key = key
        self.model = model
        self.timeout = timeout

    def _post(self, payload, on_event=None):
        url = "%s/%s:generateContent" % (self.BASE, self.model)
        # Ban mien phi cua Gemini gioi han theo phut; 429 la chuyen thuong ngay chu
        # khong phai loi that -> cho roi thu lai thay vi bao loi cho nguoi dung.
        r = _gui_co_cho(lambda: requests.post(url, params={"key": self.key},
                                              json=payload, timeout=self.timeout),
                        "Gemini", on_event)
        _raise_http(r, "Gemini")
        return r.json()

    def ask(self, system, prompt, use_tools=True, on_event=None):
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        base = {"systemInstruction": {"parts": [{"text": system}]},
                "generationConfig": {"temperature": 0.2,
                                     "maxOutputTokens": _MAX_TOKENS_GEMINI}}
        if use_tools:
            base["tools"] = TS.gemini_tools()
        for turn in range(MAX_TURNS):
            payload = dict(base, contents=contents)
            if turn == MAX_TURNS - 1:
                payload.pop("tools", None)
            try:
                data = self._post(payload, on_event)
            except RuntimeError as e:
                # Model khong nhan loi dan he thong -> gop no vao ngay dau cau hoi
                # roi hoi lai. Chi xay ra o luot dau; bo di roi thi khong lap lai.
                if not (base.get("systemInstruction") and is_sysinstr_reject(e)):
                    raise
                self._say(on_event, "status", "Model nay khong nhan loi dan rieng - "
                                              "dang gop vao cau hoi roi hoi lai...")
                base.pop("systemInstruction", None)
                contents[0]["parts"][0]["text"] = "%s\n\n%s" % (
                    system, contents[0]["parts"][0]["text"])
                payload = dict(base, contents=contents)
                if turn == MAX_TURNS - 1:
                    payload.pop("tools", None)
                data = self._post(payload, on_event)
            cand = (data.get("candidates") or [{}])[0]
            parts = ((cand.get("content") or {}).get("parts")) or []
            calls, texts = [], []
            for p in parts:
                if "functionCall" in p:
                    fc = p["functionCall"] or {}
                    a = fc.get("args")
                    calls.append((None, fc.get("name") or "", a if isinstance(a, dict) else {}))
                elif p.get("text"):
                    texts.append(p["text"])
            if not calls:
                txt = "".join(texts).strip()
                if not txt:
                    # Tra ve chuoi rong thi o tra loi trong tron, nguoi van hanh
                    # khong biet chuyen gi xay ra - phai noi thang.
                    raise RuntimeError("Gemini khong tra loi duoc: %s."
                                       % _gemini_vi_sao_trong(data))
                self._say(on_event, "text", txt)
                return txt
            contents.append({"role": "model", "parts": parts})
            resp = []
            for _cid, nm, res in self._run_tools(calls, on_event):
                resp.append({"functionResponse": {"name": nm, "response": {"result": res}}})
            contents.append({"role": "user", "parts": resp})
        raise RuntimeError("Gemini tra cuu %d luot ma van chua ket luan duoc. "
                           "Thu hoi lai cau hoi ngan gon hon." % MAX_TURNS)


class LLMClientOllama(BaseLLMClient):
    """Ollama tai may. /api/chat co ho tro tool o ban moi; ban cu bo qua tham so
    'tools' va tra loi thang - van dung duoc, chi la khong tra cuu them."""
    name = "Ollama"

    def __init__(self, model: str, host: str, timeout: int = 280):
        if not model:
            raise ValueError("Chua chon model - bam 'Tai danh sach model' trong Cai dat AI.")
        self.model = model
        self.url = "%s/api/chat" % (host or "http://localhost:11434").rstrip("/")
        self.timeout = timeout

    def _post(self, messages, tools):
        payload = {"model": self.model, "messages": messages, "stream": False,
                   "options": {"temperature": 0.2, "num_predict": _OLLAMA_NUM_PREDICT,
                               "num_ctx": _OLLAMA_NUM_CTX}}
        if tools:
            payload["tools"] = tools
        r = requests.post(self.url, json=payload, timeout=self.timeout)
        _raise_http(r, "Ollama")
        return r.json()

    def ask(self, system, prompt, use_tools=True, on_event=None):
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": prompt}]
        tools = TS.openai_tools() if use_tools else None
        for _ in range(MAX_TURNS):
            msg = (self._post(msgs, tools).get("message") or {})
            tc = msg.get("tool_calls") or []
            if not tc:
                txt = (msg.get("content") or "").strip()
                self._say(on_event, "text", txt)
                return txt
            msgs.append(msg)
            calls = []
            for c in tc:
                fn = c.get("function") or {}
                a = fn.get("arguments")
                calls.append((None, fn.get("name") or "",
                              a if isinstance(a, dict) else _json(a)))
            for _cid, nm, res in self._run_tools(calls, on_event):
                msgs.append({"role": "tool", "name": nm, "content": res})
        return ""


# --------------------------------------------------------------------------- #
def _json(raw):
    """Tham so cong cu: co nha tra ve dict san, co nha tra ve chuoi JSON."""
    if isinstance(raw, dict):
        return raw
    import json
    try:
        v = json.loads(raw or "{}")
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def create_client(provider: str = "", model_override: str = "") -> BaseLLMClient:
    """Client cua nha cung cap dang chon. 'claude' KHONG di duong nay - no dung
    ai_client.py (Agent SDK + dang nhap Claude Code), khong phai HTTP."""
    cfg = load_llm_config()
    provider = (provider or cfg.get("provider") or "").strip().lower()
    model = (model_override or "").strip()

    if provider in PROV.OPENAI_COMPAT:
        return make_openai_client(provider, _cfg_key(provider, cfg),
                                  model or cfg.get("%s_model" % provider, ""))
    if provider == "gemini":
        return LLMClientGemini(_cfg_key("gemini", cfg), model or cfg.get("gemini_model", ""))
    if provider == "ollama":
        return LLMClientOllama(model or cfg.get("ollama_model", ""),
                               cfg.get("ollama_host", ""))
    raise ValueError("Nha cung cap '%s' khong goi qua HTTP duoc." % provider)


# Explain hoi nhieu luot chu khong phai mot luot. Mot luot ngan het bao lau thi
# nhan len chung do lan. Do that: 3.6 het 7,8s con 3.7 het 98-118s cho cung mot cau.
_CHAM_NHAC = 15.0     # tren muc nay: dung duoc nhung nen biet
_CHAM_NANG = 40.0     # tren muc nay: Explain se cho lau den muc khong dung duoc


def _cau_cham(giay: float, so_luot: int = MAX_TURNS) -> str:
    """Cau canh bao ve toc do, hoac '' neu model du nhanh."""
    if giay < _CHAM_NHAC:
        return ""
    muc = "  CANH BAO: model nay CHAM" if giay < _CHAM_NANG else "  MODEL NAY QUA CHAM"
    return ("%s - hoi 1 cau ngan het %.0f giay. Explain phai hoi lai nhieu luot "
            "(toi da %d) nen mot lan Explain co the mat rat lau. Nen chon model "
            "khac nhanh hon." % (muc, giay, so_luot))


def ping(provider: str, key: str = "", model: str = "", host: str = "") -> str:
    """Thu goi that 1 cau ngan. Tra ve cau tra loi; nem ngoai le neu hong."""
    provider = (provider or "").strip().lower()
    if provider in PROV.OPENAI_COMPAT:
        cl = make_openai_client(provider, key or _cfg_key(provider), model)
    elif provider == "gemini":
        cl = LLMClientGemini(key or _cfg_key("gemini"), model)
    elif provider == "ollama":
        cl = LLMClientOllama(model, host)
    else:
        raise ValueError("Khong kiem tra duoc nha cung cap: %s" % provider)
    t0 = time.time()
    txt = cl.ask("Answer in one short line.", "Reply with: OK", use_tools=False)
    cham = _cau_cham(time.time() - t0)
    # Explain song bang viec AI TU TRA CUU. Model tra loi duoc nhung khong goi duoc
    # cong cu thi coi nhu chua dung duoc - phai noi ngay o buoc kiem tra, dung de
    # den luc bam Ask moi vo.
    do = getattr(cl, "probe_tools", None)
    if do is not None:
        try:
            if not do():
                return ("%s - NHUNG model nay KHONG goi duoc cong cu tra cuu. Explain se "
                        "phai tra loi bang du lieu gui kem san, kem chinh xac hon. "
                        "Nen chon model khac.%s" % (txt, cham))
        except Exception:
            pass        # khong ket luan duoc thi thoi, dung lam hong buoc kiem tra
    return txt + cham
