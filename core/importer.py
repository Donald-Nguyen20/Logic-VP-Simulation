# -*- coding: utf-8 -*-
"""
Bo DOC LOGIC: tu file .DEF (TAG_MCR.DEF...) va tu PDF da xuat.

- parse_def_text(text)  -> list cac macro {name, params, stmts}
- def_to_circuit(macro) -> dung lai so do khoi (muc do macro) de xem trong editor
- read_pdf(path)        -> trich text; neu phat hien IL thi parse luon
"""
from __future__ import annotations
import re
from .model import Circuit

# cac opcode Instruction List biet den
OPCODES = {"A", "OR", "OUT", "SET", "CL", "XOR", "AR", "MV1", "MV", "FMV1",
           "TON", "TONL", "LH", "SS2", "F+", "F-", "F*", "F/", "CFB", "CBF",
           "FCP+", "FCP-", "FUL", "FLL", "FITG", "FNEG", "FABS", "FDLM", "FRCL"}


def parse_def_text(text: str):
    """Tach text .DEF thanh danh sach macro. Moi macro co statements."""
    macros = []
    cur = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.upper().startswith(".DEF") and not line.upper().startswith(".DEFEND"):
            parts = line.split()
            name = parts[1] if len(parts) > 1 else "MACRO"
            cur = {"name": name, "params": parts[2:], "stmts": []}
        elif line.upper().startswith(".DEFEND"):
            if cur:
                macros.append(cur)
                cur = None
        elif cur is not None:
            m = re.match(r"([A-Za-z*+/\-]+)\s+(.*)", line)
            if m:
                op, args = m.group(1), m.group(2)
            else:
                op, args = line, ""
            cur["stmts"].append((op.strip(), args.strip()))
    return macros


def _operands(args: str):
    """Tach danh sach toan hang, giu dau '-' (NOT)."""
    return [a.strip() for a in args.split(",") if a.strip()]


def def_to_circuit(macro: dict) -> Circuit:
    """Dung lai so do o MUC MACRO: liet ke tin hieu vao (chi doc) va ra (OUT/SET/CL).
    Day la ban tai dung don gian de XEM logic da import, khong phai giai ma tung cong.
    """
    c = Circuit(macro["name"])
    defined = set()   # tin hieu duoc tao ben trong (ngo ra)
    used = []         # tin hieu duoc doc (ngo vao)
    outputs = []      # tin hieu xuat ra

    for op, args in macro["stmts"]:
        ops = _operands(args)
        up = op.upper()
        if up in ("OUT", "SET", "CL"):
            if ops:
                tgt = ops[0].lstrip("-")
                outputs.append(tgt)
                defined.add(tgt)
        else:
            for o in ops:
                name = o.lstrip("-")
                if name and not re.fullmatch(r"[0-9A-Fa-f]+H?", name):
                    used.append(name)

    inputs = [s for s in dict.fromkeys(used) if s not in defined]
    outs = list(dict.fromkeys(outputs))

    # xep DI ben trai, DO ben phai, mot khoi MACRO o giua
    y = 40
    di_ids = []
    for name in inputs[:40]:
        b = c.add_block("DI", tag=name, x=40, y=y)
        di_ids.append(b.id)
        y += 70
    mac = c.add_block("MOVE", tag=macro["name"], x=360, y=60)  # dai dien khoi
    y = 40
    for name in outs[:40]:
        c.add_block("DO", tag=name, x=680, y=y)
        y += 70
    return c


def read_pdf(path: str):
    """Trich text tu PDF. Tra ve dict:
       {'text': <toan bo text>, 'macros': [...] neu phat hien IL}.
    Uu tien PyMuPDF (fitz), sau do pdfplumber, sau do pdfminer.
    """
    text = _extract_pdf_text(path)
    macros = []
    if ".DEF" in text.upper() or _looks_like_il(text):
        macros = parse_def_text(text)
    return {"text": text, "macros": macros}


def _extract_pdf_text(path: str) -> str:
    # 1) PyMuPDF
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        pass
    # 2) pdfplumber
    try:
        import pdfplumber
        out = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                out.append(page.extract_text() or "")
        return "\n".join(out)
    except Exception:
        pass
    # 3) pdfminer
    try:
        from pdfminer.high_level import extract_text
        return extract_text(path)
    except Exception as e:
        raise RuntimeError(
            "Khong doc duoc PDF. Hay cai mot trong: PyMuPDF / pdfplumber / pdfminer.six\n"
            f"Chi tiet: {e}")


def _looks_like_il(text: str) -> bool:
    hit = 0
    for ln in text.splitlines():
        w = ln.strip().split()
        if w and w[0].upper() in OPCODES:
            hit += 1
            if hit >= 5:
                return True
    return False
