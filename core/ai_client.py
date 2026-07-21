# -*- coding: utf-8 -*-
"""Goi Claude qua Claude Agent SDK, xac thuc bang TAI KHOAN Claude (OAuth).
Dang nhap 1 lan: nut trong app chay `claude setup-token` (mo trinh duyet,
dang nhap Claude Pro/Max) -> nhan OAuth token -> dan vao app va Luu.
Token luu o ~/.tdesigner_claude_token va nap vao CLAUDE_CODE_OAUTH_TOKEN khi goi.
"""
from __future__ import annotations
import os
import asyncio
import shutil
import subprocess

_TOKEN_FILE = os.path.join(os.path.expanduser("~"), ".tdesigner_claude_token")


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
    """True neu co Claude Code CLI (`claude`) tren may."""
    return shutil.which("claude") is not None


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


def logged_in():
    return bool(load_token()) or bool(os.environ.get("ANTHROPIC_API_KEY"))


def start_login():
    """Mo cua so console chay `claude setup-token` de dang nhap trinh duyet.
    Nguoi dung copy token in ra roi dan vao app. Tra ve (ok, message)."""
    if not cli_available():
        return False, ("Chua co Claude Code CLI. Cai bang:\n"
                       "  npm i -g @anthropic-ai/claude-code")
    try:
        if os.name == "nt":
            subprocess.Popen('start "Claude login" cmd /k claude login', shell=True)
        else:
            subprocess.Popen(["claude", "login"])
        return True, ("Da mo cua so 'claude login'. Dang nhap tai khoan Claude trong trinh duyet, "
                      "xong dong cua so. Phien luu tren may, app tu dung - KHONG can token.")
    except Exception as e:
        return False, "Khong mo duoc: %s" % e


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


async def _ask_async(prompt, model=None):
    from claude_agent_sdk import query, ClaudeAgentOptions
    kwargs = dict(max_turns=8, permission_mode="bypassPermissions")
    # gan tool (neu SDK ho tro) de Claude tu tra nguon tin hieu
    try:
        from . import ai_tools
        if ai_tools.available():
            kwargs["mcp_servers"] = {"tdesigner": ai_tools.build_server()}
            kwargs["allowed_tools"] = ai_tools.TOOL_NAMES
    except Exception:
        pass
    opts = ClaudeAgentOptions(**kwargs)
    if model:
        try:
            opts.model = model
        except Exception:
            pass
    chunks = []
    async for msg in query(prompt=prompt, options=opts):
        content = getattr(msg, "content", None)
        if content is None:
            t = getattr(msg, "text", None)
            if t:
                chunks.append(t)
            continue
        if isinstance(content, str):
            chunks.append(content); continue
        for blk in content:
            t = getattr(blk, "text", None)
            if t:
                chunks.append(t)
    return "".join(chunks).strip()


def ask(prompt, model=None, timeout=180):
    if not available():
        return setup_hint()
    load_token()   # neu co token luu san thi dung; khong co thi SDK tu dung dang nhap Claude Code tren may
    try:
        return asyncio.run(asyncio.wait_for(_ask_async(prompt, model), timeout))
    except Exception as e:
        return ("Loi goi Claude: %s\n\n"
                "Neu la loi dang nhap: mo terminal chay `claude` (hoac `claude setup-token`) "
                "de dang nhap tai khoan Claude 1 lan, roi thu lai." % e)
