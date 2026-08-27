# -*- coding: utf-8 -*-
"""Goi Claude qua Claude Agent SDK, xac thuc bang TAI KHOAN Claude (OAuth).

Dang nhap 1 lan bang nut trong app -> chay `claude login` -> mo trinh duyet, dang
nhap tai khoan Claude. PHIEN duoc Claude Code luu tren may (~/.claude), app dung
lai phien do; KHONG can dan token, khong can API key.

Ban CLI `claude` da di kem ngay trong goi claude_agent_sdk (thu muc _bundled) nen
KHONG bat buoc cai npm toan cuc - xem _bundled_claude(). Van chap nhan token thu
cong (CLAUDE_CODE_OAUTH_TOKEN / ~/.tdesigner_claude_token) cho may khong dang nhap
duoc bang trinh duyet.
"""
from __future__ import annotations
import os
import sys
import asyncio
import shutil
import subprocess

_TOKEN_FILE = os.path.join(os.path.expanduser("~"), ".tdesigner_claude_token")


def bundled_claude():
    """Duong dan CLI `claude`. Uu tien ban DI KEM trong goi claude_agent_sdk
    (claude_agent_sdk/_bundled/claude[.exe]) - nho vay may khong cai
    `npm i -g @anthropic-ai/claude-code` van dang nhap va goi duoc.
    Khong co thi lui ve `claude` trong PATH."""
    try:
        import claude_agent_sdk
        from pathlib import Path
        p = (Path(claude_agent_sdk.__file__).parent / "_bundled" /
             ("claude.exe" if sys.platform == "win32" else "claude"))
        if p.exists():
            return str(p)
    except Exception:
        pass
    return shutil.which("claude") or "claude"


def sdk_error():
    """Tra ve None neu import claude_agent_sdk OK; nguoc lai tra chuoi loi that."""
    try:
        import claude_agent_sdk  # noqa
        return None
    except Exception as e:
        return "%s: %s" % (type(e).__name__, e)


def available():
    """True neu import claude_agent_sdk thanh cong."""
    return sdk_error() is None


def cli_available():
    """True neu co CLI `claude` dung duoc (ban di kem SDK hoac ban cai toan cuc)."""
    c = bundled_claude()
    return bool(c) and (os.path.exists(c) or shutil.which(c) is not None)


def save_token(tok):
    tok = (tok or "").strip()
    if not tok:
        return False
    with open(_TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(tok)
    os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = tok
    return True


def load_token():
    tok = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if tok:
        return tok
    try:
        with open(_TOKEN_FILE, encoding="utf-8") as f:
            tok = f.read().strip()
        if tok:
            os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = tok
        return tok
    except Exception:
        return ""


def _has_claude_session():
    """True neu Claude Code da co PHIEN dang nhap luu tren may (~/.claude...).
    Chi kiem tra su ton tai cua ho so dang nhap - khong doc noi dung."""
    home = os.path.expanduser("~")
    for p in (os.path.join(home, ".claude", ".credentials.json"),
              os.path.join(home, ".claude", "credentials.json"),
              os.path.join(home, ".claude.json")):
        try:
            if os.path.exists(p) and os.path.getsize(p) > 2:
                return True
        except Exception:
            continue
    return False


def logged_in():
    """Da co cach xac thuc nao do: phien Claude Code, token thu cong, hoac API key."""
    return (_has_claude_session() or bool(load_token())
            or bool(os.environ.get("ANTHROPIC_API_KEY")))


def status():
    """Trang thai ket noi de hien den bao tren giao dien.
    Tra (connected: bool, text: str). connected = co SDK VA da xac thuc."""
    err = sdk_error()
    if err:
        return False, "Chua co Claude Agent SDK (%s)" % err.split(":")[0]
    if not logged_in():
        return False, "Da co SDK nhung CHUA dang nhap - bam 'Login to Claude'"
    how = ("phien Claude Code" if _has_claude_session()
           else ("token da luu" if load_token() else "ANTHROPIC_API_KEY"))
    return True, "Da ket noi Claude (%s)" % how


def start_login():
    """Mo cua so console chay `claude login` -> dang nhap tai khoan Claude bang
    trinh duyet. Dung CLI DI KEM SDK neu co (khong bat buoc cai npm toan cuc).
    Tra ve (ok, message)."""
    cli = bundled_claude()
    if not cli_available():
        return False, ("Khong tim thay CLI `claude`.\n"
                       "Cach 1: cai lai goi SDK (co kem CLI):\n"
                       "  pip install -U claude-agent-sdk\n"
                       "Cach 2: cai CLI toan cuc:\n"
                       "  npm i -g @anthropic-ai/claude-code")
    try:
        if os.name == "nt":
            subprocess.Popen(
                [cli, "login"],
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        else:
            subprocess.Popen([cli, "login"])
        return True, ("Da mo cua so 'claude login'. Dang nhap tai khoan Claude trong trinh duyet, "
                      "xong dong cua so lai. Phien duoc luu tren may, app tu dung - "
                      "KHONG can dan token.\n\nDung CLI:\n  %s" % cli)
    except Exception as e:
        return False, "Khong mo duoc (%s): %s" % (cli, e)


def setup_hint():
    import sys
    err = sdk_error()
    detail = ("Loi import that:\n  %s\n\n" % err) if err else ""
    tip = ""
    if err and "No module named" in err:
        tip = "-> Goi CHUA cai trong python nay.\n"
    elif err:
        tip = "-> Goi da cai nhung import LOI (vd can Python >= 3.10, hien %s).\n" % sys.version.split()[0]
    return ("Python dang chay app:\n  %s  (%s)\n\n"
            "%s%s"
            "Cai/kiem tra dung python nay:\n"
            "  \"%s\" -m pip install claude-agent-sdk    (can >= 3.10)\n"
            "  \"%s\" -c \"import claude_agent_sdk\"      (thu import)\n\n"
            "Sau khi cai xong, DONG va mo lai app."
            % (sys.executable, sys.version.split()[0], detail, tip, sys.executable, sys.executable))


def _opt_fields(ClaudeAgentOptions):
    try:
        import inspect
        f = set(getattr(ClaudeAgentOptions, "__dataclass_fields__", {}) or {})
        return f or set(inspect.signature(ClaudeAgentOptions).parameters)
    except Exception:
        return set()


async def _ask_async(prompt, model=None, use_tools=True, on_event=None,
                     sink=None):
    from claude_agent_sdk import query, ClaudeAgentOptions
    # Nhieu luot HON khi co tool: prompt yeu cau AI tu di lay tung nhanh bi cat
    # (get_source) va tra nghia tung ma khoi (block_function) - sheet phuc tap can
    # hang chuc luot, de 8 se bi cat giua chung va tra loi thieu.
    kwargs = dict(max_turns=(24 if use_tools else 4),
                  permission_mode="bypassPermissions")
    flds = _opt_fields(ClaudeAgentOptions)
    # gan tool (neu SDK ho tro) de Claude tu tra nguon tin hieu
    if use_tools:
        try:
            from . import ai_tools
            if ai_tools.available():
                kwargs["mcp_servers"] = {"tdesigner": ai_tools.build_server()}
                kwargs["allowed_tools"] = ai_tools.TOOL_NAMES
        except Exception:
            pass
    # Chi ro duong dan CLI (ban di kem SDK) neu phien ban SDK cho phep - tranh phu
    # thuoc PATH cua may.
    for name in ("cli_path", "claude_path", "executable_path",
                 "path_to_claude_code_executable"):
        if name in flds:
            kwargs[name] = bundled_claude()
            break
    # THU MUC LAM VIEC: chay trong thu muc NHA. Claude Code hoi "co tin thu muc nay
    # khong?" khi lan dau chay o 1 thu muc LA - cau hoi do doi nguoi go phim, ma app
    # chay ngam nen se TREO cho toi khi het gio (da gap: TimeoutError sau 180s).
    if "cwd" in flds:
        kwargs["cwd"] = os.path.expanduser("~")
    opts = ClaudeAgentOptions(**kwargs)
    if model:
        try:
            opts.model = model
        except Exception:
            pass
    # sink: DUNG CHUNG danh sach voi ben goi, de khi het gio giua chung thi phan chu
    # AI da viet duoc VAN CON (truoc day mat sach, nguoi dung khong nhan duoc gi).
    chunks = sink if sink is not None else []

    def _add(t):
        # Moi message tra ve 1 khoi chu HOAN CHINH. Noi thang bang "" thi cau nay dinh
        # vao cau kia, nguy hiem nhat la tieu de bi dinh ("...alone.# Tin hieu MFT")
        # -> markdown mat tac dung. Chen dong trong khi khoi truoc chua xuong dong.
        if chunks and not chunks[-1].endswith("\n"):
            chunks.append("\n\n")
        chunks.append(t)

    def _say(kind, info):
        if on_event is None:
            return
        try:
            on_event(kind, info)
        except Exception:
            pass          # loi o cho hien thi khong duoc lam hong cuoc goi

    async for msg in query(prompt=prompt, options=opts):
        content = getattr(msg, "content", None)
        if content is None:
            t = getattr(msg, "text", None)
            if t:
                _add(t); _say("text", t)
            continue
        if isinstance(content, str):
            _add(content); _say("text", content); continue
        for blk in content:
            t = getattr(blk, "text", None)
            if t:
                _add(t); _say("text", t); continue
            # Khoi GOI CONG CU: bao ra ngoai xem AI dang tra cuu cai gi. Mot lan
            # giai thich MFT co 33 luot tra cuu chiem 86s - khong bao thi man hinh
            # dung im, nguoi dung tuong treo va tat di truoc khi cau tra loi ve.
            nm = getattr(blk, "name", None)
            if nm:
                arg = getattr(blk, "input", None) or {}
                if not isinstance(arg, dict):
                    arg = {}
                _say("tool", "%s %s" % (nm.split("__")[-1],
                                        arg.get("name") or arg.get("code") or ""))
    return "".join(chunks).strip()


def _run_async(coro, timeout):
    """Chay coroutine trong 1 vong lap RIENG.

    QUAN TRONG (Windows): SDK phai CHAY 1 TIEN TRINH CON (claude CLI) qua asyncio.
    Tren Windows, viec do CHI lam duoc voi ProactorEventLoop; neu dung vong lap mac
    dinh (Selector) trong luong phu - dung truong hop app goi tu QThread - se nem
    NotImplementedError co noi dung RONG, hien ra man hinh thanh "Loi goi Claude:"
    trong khong (loi da gap that). Vi vay tu tao dung loai vong lap o day."""
    loop = None
    try:
        if os.name == "nt" and hasattr(asyncio, "ProactorEventLoop"):
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(asyncio.wait_for(coro, timeout))
    finally:
        if loop is not None:
            try:
                loop.close()
            except Exception:
                pass
        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass


def ping(timeout=45):
    """KIEM TRA NHANH duong day: hoi 1 cau ngan, KHONG dung tool, khong ngu canh.
    Dung de biet loi nam o dau ma khong phai cho het 3 phut:
      - chay duoc  -> duong day + dang nhap OK, loi (neu co) nam o ngu canh/tool;
      - het gio    -> CLI khong tra loi (thuong do chua tin thu muc, hoac chua dang nhap).
    Tra (ok, text)."""
    if not available():
        return False, setup_hint()
    load_token()
    try:
        out = _run_async(_ask_async("Tra loi dung 2 chu: OK ROI", None, use_tools=False),
                         timeout)
        return True, (out or "(tra ve rong)")
    except Exception as e:
        name = type(e).__name__
        if name == "TimeoutError":
            return False, (
                "Qua %ds khong co tra loi - CLI chay nhung khong phan hoi.\n\n"
                "Hay thu THU CONG 1 lan de xem no dang hoi gi:\n"
                "  1. Mo Command Prompt\n"
                "  2. Chay:  \"%s\"\n"
                "  3. Neu no hoi 'Do you trust the files in this folder?' -> chon Yes,\n"
                "     hoac hoi dang nhap -> dang nhap.\n"
                "  4. Go /exit roi thu lai trong app.\n" % (timeout, bundled_claude()))
        return False, "%s: %s" % (name, str(e) or "(khong co mo ta)")


def ask(prompt, model=None, timeout=420, prompt_no_tools=None, on_event=None):
    """prompt_no_tools: ban prompt dung KHI phai chay lai o che do khong co tool
    (noi ro voi AI la dung goi tool). Khong truyen thi dung lai `prompt`.

    timeout 420s chu KHONG phai 180s. Do that tren tin hieu MFT (tin hieu lon nhat
    trong bo DB): tong 240s = 28s khoi dong CLI + 86s cho 33 luot tra cuu + 124s
    viet cau tra loi. De 180s thi dung nhung tin hieu quan trong nhat luon bi cat
    dung luc AI sap viet xong; roi rot sang ban chay lai khong tool - ban do voi
    45..60s cung khong kip (do duoc 65s) - nen nguoi dung KHONG nhan duoc gi.

    on_event(kind, info): goi tu LUONG DANG CHAY moi khi AI viet them chu
    (kind="text") hoac goi 1 cong cu tra cuu (kind="tool"). Dung de hien tien do."""
    if not available():
        return setup_hint()
    load_token()   # co token luu san thi dung; khong co thi SDK dung phien Claude Code tren may
    got = []
    try:
        return _run_async(_ask_async(prompt, model, on_event=on_event, sink=got),
                          timeout)
    except Exception as first:
        if type(first).__name__ == "TimeoutError":
            # Het gio nhung AI DA viet duoc kha nhieu -> tra phan do, con hon vut di:
            # doan dau (tin hieu nay la gi, trip vi dieu kien nao) thuong da du dung.
            part = "".join(got).strip()
            if len(part) > 400:
                return (part + "\n\n---\n(Ghi chu: qua %ds nen bi cat giua chung. "
                        "Phan tren van dung; bam 'Ask Claude' lai de co ban day du.)"
                        % timeout)
            # Chua duoc chu nao -> thu LAI khong tool. Phan khoi tao may chu MCP
            # trong tien trinh la cho hay treo nhat; bo no di thuong van tra loi duoc
            # (chi kem phan tu tra cuu them), con hon la nguoi dung khong nhan duoc gi.
            try:
                out = _run_async(_ask_async(prompt_no_tools or prompt, model,
                                            use_tools=False, on_event=on_event),
                                 max(150, timeout // 3))
                if out:
                    return (out + "\n\n---\n(Ghi chu: lan goi dau bi treo khi bat cong cu "
                            "tra cuu, da tra loi lai o che do khong dung cong cu.)")
            except Exception:
                pass
        return _err_text(first, timeout)


def _err_text(e, timeout):
    import traceback
    name = type(e).__name__
    detail = str(e).strip() or "(khong co mo ta)"
    tb = "".join(traceback.format_exception(type(e), e, e.__traceback__, limit=6))
    hint = ""
    if name == "NotImplementedError":
        hint = ("-> Windows khong chay duoc tien trinh con trong loai vong lap nay "
                "(da xu ly trong _run_async).\n")
    elif name == "TimeoutError" or "timeout" in detail.lower():
        hint = ("-> Qua %ds ma CLI KHONG tra loi gi (da thu lai ca o che do khong dung "
                "cong cu). Thuong la CLI dang CHO NGUOI TRA LOI 1 cau hoi ma app khong "
                "thay duoc - vd 'Do you trust the files in this folder?'.\n"
                "   Cach xu ly: mo Command Prompt, chay 1 lan:\n"
                "     \"%s\"\n"
                "   tra loi cac cau hoi (chon Yes / dang nhap), go /exit, roi thu lai.\n"
                % (timeout, bundled_claude()))
    elif "CLINotFound" in name or "not found" in detail.lower():
        hint = ("-> Khong tim thay CLI `claude`. Dang dung: %s\n"
                "   Cai lai goi SDK (co kem CLI): pip install -U claude-agent-sdk\n"
                % bundled_claude())
    elif "auth" in detail.lower() or "login" in detail.lower() or "401" in detail:
        hint = "-> Loi dang nhap: bam 'Login to Claude' roi dang nhap lai.\n"
    return ("Loi goi Claude [%s]: %s\n%s\n"
            "CLI dang dung: %s\n"
            "Meo: bam 'Kiem tra ket noi' de thu 1 cau ngan (45s) - biet ngay loi nam o "
            "duong day hay o ngu canh.\n\n"
            "Chi tiet ky thuat:\n%s" % (name, detail, hint, bundled_claude(), tb))
