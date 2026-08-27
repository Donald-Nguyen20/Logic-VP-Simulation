# -*- coding: utf-8 -*-
"""Dinh nghia 3 cong cu tra cuu duoi dang KHONG PHU THUOC nha cung cap.

ai_tools.py da co ban danh cho Claude Agent SDK (@tool + may chu MCP). File nay la
ban tuong duong cho cac nha cung cap goi qua HTTP thuong (Groq/OpenRouter theo chuan
OpenAI, Gemini theo chuan Google), vi hai ben dung dinh dang JSON Schema khac nhau.
Phan RUOT - ham that su chay - la chung: deu goi ai_explain.

Vi sao phai co cong cu: do tren 232 tin hieu lay mau, 66% co ngu canh du de tra loi
ngay, nhung 26% con lai co tu 9 den 59 nhanh dieu kien bi cat o gioi han truy nguoc.
Dung 26% do lai la cac tin hieu quan trong nhat (permissive khoi dong, dieu kien trip).
Khong co cong cu thi phan do bi bo trong.
"""
from __future__ import annotations
from . import ai_explain as AE

# Mo ta dung nguyen van cua ban Claude de hai duong cho AI cung mot chi dan.
TOOLS = [
    {
        "name": "get_source",
        "description": (
            "Trace the full upstream logic chain that forms a signal, through every "
            "block and across sheets/CPUs, down to source inputs. Use this to find the "
            "real conditions behind any signal instead of asking the user."),
        "param": "name",
        "param_desc": "Exact signal name, e.g. 'CWP 1 RUN'.",
    },
    {
        "name": "block_function",
        "description": "Explain what a Toshiba DCS function block does, given its hex macrocode.",
        "param": "code",
        "param_desc": "Hex macrocode of the block, e.g. '210F'.",
    },
    {
        "name": "find_signal",
        "description": "Find which CPU/sheet a signal name is on (partial name ok).",
        "param": "name",
        "param_desc": "Signal name or part of it.",
    },
]

_RUN = {
    "get_source": lambda a: AE.trace_by_name(a.get("name", "")),
    "block_function": lambda a: AE.block_function(a.get("code", "")),
    "find_signal": lambda a: AE.locate_text(a.get("name", "")),
}

# Ket qua tra cuu nang nhat do duoc la 16.361 ky tu (~4.090 token) cho 1 luot. Nhieu
# luot nhu vay don lai se pha vo cua so cua model 128k, nen cat bot o day.
MAX_RESULT_CHARS = 6000


def openai_tools():
    """Dinh dang cho cac diem cuoi tuong thich OpenAI (Groq, OpenRouter)."""
    return [{
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": {
                "type": "object",
                "properties": {t["param"]: {"type": "string",
                                            "description": t["param_desc"]}},
                "required": [t["param"]],
            },
        },
    } for t in TOOLS]


def gemini_tools():
    """Dinh dang cho Gemini REST (functionDeclarations)."""
    return [{"functionDeclarations": [{
        "name": t["name"],
        "description": t["description"],
        "parameters": {
            "type": "OBJECT",
            "properties": {t["param"]: {"type": "STRING",
                                        "description": t["param_desc"]}},
            "required": [t["param"]],
        },
    } for t in TOOLS]}]


def dispatch(name, args):
    """Chay 1 cong cu. Luon tra ve CHUOI - ke ca khi loi - vi cuoc hoi thoai bat buoc
    phai co phan hoi cho moi loi goi; nem ngoai le ra day la ket cuoc hoi thoai giua
    chung va nguoi dung khong nhan duoc gi."""
    fn = _RUN.get(name)
    if fn is None:
        return "No such tool: %s" % name
    if not isinstance(args, dict):
        args = {}
    try:
        out = fn(args) or ""
    except Exception as e:
        return "Tool %s failed: %s: %s" % (name, type(e).__name__, e)
    out = str(out)
    if len(out) > MAX_RESULT_CHARS:
        out = out[:MAX_RESULT_CHARS] + "\n...(cat bot cho vua cua so ngu canh)"
    return out or "(no result)"
