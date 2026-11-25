# -*- coding: utf-8 -*-
"""产品机会评分 —— 统一数据加载

用法:
    from dataio import load_workbook
    d = load_workbook(path)
    d["rows"]        # [{row, txt, nums}]
    d["mapping"]     # {语义: 列字母}
    d["trend"]       # {趋势表行号: {月份: 销量}}
    d["months"]      # 月份降序列表
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from columns import Workbook, resolve_columns, unescape_xml  # noqa: E402


def load_workbook(path, header_row=4, first_row=5, trend_offset=3):
    wb = Workbook(path)
    s1 = wb.sheet_xml(1)
    s2 = wb.sheet_xml(2)

    # 表头
    headers = {}
    for rn, cells in Workbook.iter_rows(s1):
        if rn == header_row:
            headers = {c: wb.text(a, b) for c, (a, b) in cells.items()}
            break

    mapping, missing = resolve_columns(headers)

    # 产品行
    rows = []
    for rn, cells in Workbook.iter_rows(s1):
        if rn < first_row:
            continue
        txt, nums = {}, {}
        for col, (attrs, body) in cells.items():
            txt[col] = wb.text(attrs, body)
            n = Workbook.number(attrs, body)
            if n is not None:
                nums[col] = n
        rows.append({"row": rn, "txt": txt, "nums": nums})

    # 趋势表
    trend, months = {}, []
    if s2:
        col_month = {}
        for rn, cells in Workbook.iter_rows(s2):
            if rn != 1:
                break
            for col, (attrs, body) in cells.items():
                t = wb.text(attrs, body)
                if re.match(r"^\d{4}-\d{2}$", t):
                    col_month[col] = t
        months = sorted(col_month.values(), reverse=True)
        for rn, cells in Workbook.iter_rows(s2):
            if rn < 2:
                continue
            d = {}
            for col, (attrs, body) in cells.items():
                if col in col_month:
                    n = Workbook.number(attrs, body)
                    if n is not None:
                        d[col_month[col]] = n
            trend[rn] = d

    wb.close()
    return {
        "headers": headers, "mapping": mapping, "missing": missing,
        "rows": rows, "trend": trend, "months": months,
        "trend_offset": trend_offset,
        "has_inline": "inlineStr" in s1,
        "has_shared": "sharedStrings" in "".join(wb.names[:0]) or
                      any("sharedStrings" in n for n in []),
    }


def zh_segs(at):
    for line in (at or "").split("\n"):
        line = line.strip()
        if line and any("\u4e00" <= ch <= "\u9fff" for ch in line):
            return [s.strip() for s in line.split("->") if s.strip()]
    return []
