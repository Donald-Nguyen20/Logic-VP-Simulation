# -*- coding: utf-8 -*-
"""Xuat ma tran nhan qua (core/ce_matrix.py) ra file .xlsx."""
from __future__ import annotations


def export_matrix(path, columns, rows):
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "CE Matrix"

    hdr_fill = PatternFill("solid", fgColor="1D4ED8")
    hdr_font = Font(color="FFFFFF", bold=True)
    or_font = Font(color="1D4ED8", bold=True)
    and_font = Font(color="B45309", bold=True)
    center = Alignment(horizontal="center", vertical="center")

    headers = ["Nguyen nhan goc", "Nguon", "Sheet"] + list(columns)
    for ci, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=ci, value=h)
        c.fill = hdr_fill; c.font = hdr_font; c.alignment = center
    ws.freeze_panes = "A2"

    for ri, row in enumerate(rows, start=2):
        ws.cell(row=ri, column=1, value=row.get("label"))
        ws.cell(row=ri, column=2, value=("Tai lieu (TAG)" if row.get("source") == "tag"
                                         else "Suy luan tu day"))
        ws.cell(row=ri, column=3, value=row.get("sheetlbl") or row.get("sheet") or "")
        for ci, col in enumerate(columns, start=4):
            m = row.get("marks", {}).get(col)
            if not m:
                continue
            cell = ws.cell(row=ri, column=ci)
            cell.alignment = center
            if m["kind"] == "or":
                cell.value = "OR"
                cell.font = or_font
            else:
                with_txt = ", ".join(m.get("with") or [])
                cell.value = "AND (%s)" % m.get("group", "")
                cell.font = and_font
                if with_txt:
                    from openpyxl.comments import Comment
                    cell.comment = Comment("Can du ca nhom:\n" + with_txt, "T-Designer")

    from openpyxl.utils import get_column_letter
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 12
    for ci in range(4, 4 + len(columns)):
        ws.column_dimensions[get_column_letter(ci)].width = 16

    wb.save(path)
