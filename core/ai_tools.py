# -*- coding: utf-8 -*-
"""Bo TOOL cho Claude Agent SDK: boc lai cac ham san co cua app de Claude
tu goi khi can (tu di lan theo tin hieu thay vi hoi nguoi dung).
Neu ban SDK khong ho tro tool -> available()=False, ai_client se goi kieu thuong."""
from __future__ import annotations
from . import ai_explain as AE

try:
    from claude_agent_sdk import tool, create_sdk_mcp_server
    _OK = True
except Exception:
    _OK = False


if _OK:
    @tool("find_signal",
          "Find which CPU/sheet a signal name is on (partial name ok).",
          {"name": str})
    async def _find_signal(args):
        return {"content": [{"type": "text", "text": AE.locate_text(args.get("name", ""))}]}

    @tool("get_source",
          "Trace the full upstream logic chain that forms a signal, through every block "
          "and across sheets/CPUs, down to source inputs. Use this to find the real "
          "conditions behind any signal instead of asking the user.",
          {"name": str})
    async def _get_source(args):
        return {"content": [{"type": "text", "text": AE.trace_by_name(args.get("name", ""))}]}

    @tool("block_function",
          "Explain what a Toshiba DCS function block does, given its hex macrocode.",
          {"code": str})
    async def _block_function(args):
        return {"content": [{"type": "text", "text": AE.block_function(args.get("code", ""))}]}


def available():
    return _OK


def build_server():
    return create_sdk_mcp_server("tdesigner", "1.0",
                                 tools=[_find_signal, _get_source, _block_function])


TOOL_NAMES = [
    "mcp__tdesigner__find_signal",
    "mcp__tdesigner__get_source",
    "mcp__tdesigner__block_function",
]
