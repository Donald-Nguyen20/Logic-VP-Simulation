# -*- coding: utf-8 -*-
"""AI doan TU KHOA cho o tim kiem - va chi duoc lam dung chung do.

Vi sao khong de AI quet thang DB: ghep het ten trong 21 file lai la 362.000 token cho
MOT cau hoi - vuot han gioi han 131k cua Groq, va dot sach han muc mien phi cua Gemini
sau vai cau. Cach dai vong (AI tu grep) thi mat hang phut va nhieu luot goi, khong the
dung cho mot o tim kiem bam Enter la phai co ket qua.

Nen phan viec nhu sau, dung dung so truong tung ben:
  AI     doan TU (MILL -> PULV, IGNITER -> IGNTR) - viec cua ngon ngu
  chi muc doi chieu tu do voi ten THAT trong DB - viec cua du lieu
AI khong bao gio duoc noi CPU nao / loop nao / trang nao. Vi tri luon do chi muc tra
ra tu dong that, nen du AI co bia ra tu gi thi cung khong the day ket qua di lac: tu
nao khong co trong bang `tu` la bi loai truoc khi tim.

Ket qua da nhan duoc luu lai (data/tukhoa.json canh app), nen hoi lan hai la offline
va mien phi. Khong co mang cung khong sao - ben goi van chay duoc voi tu dien tinh.
"""
import json
import os
import re

# Toi thieu 3 ky tu. Do that: hoi cau vo nghia "xyzzy nothing here", model van co
# ep ra dap an - NOTHING -> "NO", HERE -> "HR" - va ca hai deu la tu CO THAT trong DB
# nen lot qua duoc buoc kiem chung, keo ve 220 dong rac. Viet tat 2 ky tu that su can
# (SH, AH, RH, FW, WW, CL, SB) thi da nam san trong tu_dien.TU_TAT roi, nen cat o day
# khong mat gi ma bit duoc dung cai cua do.
_MAU_TOKEN = re.compile(r"^[A-Z0-9][A-Z0-9/\-]{2,11}$")

_NHAC = (
    "You expand search keywords for a DCS logic drawing database of a coal-fired "
    "power plant (Japanese vendor). Drawing titles and signal names are short "
    "UPPERCASE abbreviated text, for example: 'FIRING RATE PROG FOR INIT COLD "
    "STRT-UP', 'PULV A O/L TEMP SETP', 'IGNTR B3 LIGHT OFF BYPASS(PRE-LIGHT)', "
    "'CORRD FURN PRS DEVN'.\n"
    "Given the user's question, output the tokens that are LIKELY TO APPEAR "
    "LITERALLY in such names.\n"
    "Rules:\n"
    "- Output JSON only. No prose, no markdown fence.\n"
    "- Format: {\"<word or phrase taken from the question>\": [\"TOKEN\", ...]}\n"
    "- TOKEN is UPPERCASE, 3-12 chars, only letters, digits, '/' and '-'.\n"
    "- Prefer the ABBREVIATED form the drawings use (MILL->PULV, IGNITER->IGNTR, "
    "PRESSURE->PRS, OUTLET->O/L, TEMPERATURE->TEMP), and add the full word too "
    "when it is also plausible.\n"
    "- NEVER output CPU names, loop numbers, sheet numbers or KKS codes.\n"
    "- NEVER introduce equipment the question does not mention.\n"
    "- Skip any word that is not plant equipment, a process, a measurement or a "
    "state. Ordinary English words (nothing, here, thing, please) get no entry.\n"
    "- If the question is not about a power plant at all, output exactly {}.\n"
    "- At most 6 keys and at most 5 tokens per key."
)


def duong_cache():
    """File nho tu khoa da duoc duyet, nam canh app (xem duong_dan.py). RIENG han file
    cau hinh AI - cai do la cua nguoi dung, module nay khong duoc dong vao."""
    from . import duong_dan as DD
    return DD.duong_json("tukhoa.json", ".tdesigner_tukhoa.json")


def _doc_cache():
    try:
        with open(duong_cache(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        # Cache hong hay chua co deu khong phai loi: chi la lan nay phai hoi AI.
        return {}


def _ghi_cache(d):
    tam = duong_cache() + ".tmp"
    try:
        with open(tam, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tam, duong_cache())
        return ""
    except Exception as e:
        try:
            os.remove(tam)
        except Exception:
            pass
        return "Khong ghi duoc %s: %s" % (duong_cache(), e)


def _khoa(q):
    return " ".join((q or "").upper().split())


def _tach_json(txt):
    """Lay object JSON dau tien trong cau tra loi. Nhieu model van kem theo loi giai
    thich hoac rao ```json du da dan dung, nen khong the json.loads thang.

    None = KHONG doc duoc (model tra ve van xuoi, JSON hong). {} = doc duoc va model
    noi 'khong co tu nao' - hai truong hop nay phai bao khac nhau cho nguoi dung, va
    chi truong hop sau moi dang luu vao cache."""
    txt = (txt or "").strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", txt)
    i, j = txt.find("{"), txt.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        d = json.loads(txt[i:j + 1])
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    ra = {}
    for k, v in d.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, str):
            v = [v]
        if not isinstance(v, list):
            continue
        tk = [t.strip().upper() for t in v if isinstance(t, str)]
        # Bat buoc co CHU CAI: chan tan goc moi thu "105-06", "127", "10-019" - tuc la
        # AI khong the tuon ra vi tri trang/loop du no co co tinh. Vi tri chi duoc phep
        # den tu chi muc, doi chieu voi dong that.
        tk = [t for t in tk if _MAU_TOKEN.match(t) and any(c.isalpha() for c in t)]
        if tk:
            ra[" ".join(k.upper().split())] = tk[:5]
        if len(ra) >= 6:
            break
    return ra


def kiem_chung(them, out_path=None):
    """Giu lai nhung tu CO THAT trong DB; tu nao lech chinh ta thi thay bang tu that.

    Day la cho AI khong the noi doi duoc: du no tu tin den may, tu nao bang `tu` bao
    la 0 lan xuat hien thi khong the lot vao cau tim. Tra ve (sach, bo)."""
    from . import project_index as PI
    moi = sorted(set(t for ds in them.values() for t in ds))
    if not moi:
        return {}, []
    ts = PI.tan_suat(moi, out_path=out_path)
    doi = {}
    for t in moi:
        if sum(ts.get(t, (0, 0))) > 0:
            continue
        gan = PI.gan_giong(t, out_path=out_path)
        doi[t] = gan[0] if gan else None
    sach, bo = {}, []
    for k, ds in them.items():
        giu = []
        for t in ds:
            t2 = doi.get(t, t)
            if t2 is None:
                bo.append(t)
            elif t2 not in giu:
                giu.append(t2)
        if giu:
            sach[k] = giu
    return sach, sorted(set(bo))


def _hoi(provider, cau, on_event=None):
    """Goi model. Tra ve (van ban, loi). Khong nem ngoai le ra ngoai: o tim kiem phai
    van chay duoc bang tu dien tinh khi mat mang hay het han muc."""
    provider = (provider or "").strip().lower()
    if not provider:
        try:
            from . import llm_config as LCFG
            provider = (LCFG.load_llm_config().get("provider") or "").strip().lower()
        except Exception:
            provider = ""
    try:
        if provider in ("", "claude"):
            from . import ai_client as AC
            return AC.ask(_NHAC + "\n\n" + cau, timeout=90, on_event=on_event), ""
        from . import llm_client as LC
        cl = LC.create_client(provider)
        return cl.ask(_NHAC, cau, use_tools=False, on_event=on_event), ""
    except Exception as e:
        return "", "%s: %s" % (type(e).__name__, e)


def goi_y(q, provider="", out_path=None, on_event=None, dung_cache=True):
    """Cau hoi -> ({cum: [tu khoa da kiem chung]}, ghi chu de hien cho nguoi dung).

    Truyen ket qua vao tu_dien.o_sua(q, them=...) de no ghep vao dung vi tri cum tu."""
    k = _khoa(q)
    if not k:
        return {}, "Chua co cau hoi."
    cache = _doc_cache()
    if dung_cache and k in cache:
        cu = cache[k]
        if isinstance(cu, dict) and cu:
            return cu, "Tu khoa da luu (khong goi AI)."
        return {}, "Da hoi AI cho cau nay truoc do, khong them duoc tu nao."
    txt, loi = _hoi(provider, "Question: %s" % q, on_event=on_event)
    if loi:
        return {}, ("Khong goi duoc AI - %s. Mo 'AI Setting' tren thanh cong cu de "
                    "chon nha cung cap va kiem tra API key." % loi)
    tho = _tach_json(txt)
    if tho is None:
        return {}, "AI tra ve khong dung dinh dang JSON, bo qua."
    sach, bo = kiem_chung(tho, out_path=out_path)
    cache[k] = sach
    canh = _ghi_cache(cache)
    if sach:
        ghi = "AI de xuat: %s" % ", ".join("%s = %s" % (a, "/".join(b))
                                           for a, b in sach.items())
    elif tho:
        ghi = "AI khong dua ra duoc tu nao co that trong ban ve."
    else:
        ghi = "AI khong tim duoc tu khoa nao cho cau nay."
    if bo:
        ghi += "   (da loai vi DB khong co: %s)" % ", ".join(bo)
    if canh:
        ghi += "   [%s]" % canh
    return sach, ghi
