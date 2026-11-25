# -*- coding: utf-8 -*-
"""产品机会评分 —— 写入 Excel

用法:
    python write_scores.py <源.xlsx> <score_result.json> <输出.xlsx>

采用 OOXML 部件级操作，不破坏样式/超链接/图片。
新增 9 列追加在表格最末。

支持两种字符串格式（inlineStr / sharedStrings），按表头名称定位 ASIN 列。
"""
import argparse
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from columns import Workbook, resolve_columns  # noqa: E402


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def col_to_idx(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def idx_to_col(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


COLUMNS = [
    ("月销额容量分", "cap"),
    ("市场趋势分", "trd"),
    ("竞争度分", "cmp"),
    ("新品机会分", "new"),
    ("类目综合分", "cat_score"),
    ("产品竞争力分", "prod_score"),
    ("初筛星级", "stars"),
    ("初筛总分", "score"),
    ("评分依据", None),
]
WIDTHS = [11, 10, 10, 11, 11, 12, 9, 10, 70]


def build_reason(r):
    p = [f"总分{r['score']:.1f}",
         f"类目{r['cat_score']:.0f}[容量{r['cap']:.0f}/趋势{r['trd']:.0f}"
         f"/竞争{r['cmp']:.0f}/新品{r['new']:.0f}]"]
    if r.get("gate"):
        p.append("扣:" + ";".join(r["gate"]))
    return " | ".join(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("result")
    ap.add_argument("dst")
    ap.add_argument("--header-row", type=int, default=4)
    ap.add_argument("--first-row", type=int, default=5)
    args = ap.parse_args()

    res = json.load(open(args.result, encoding="utf-8"))
    recs = res["records"]
    by_asin = {r["asin"]: r for r in recs}
    print(f"评分记录 {len(recs)}")

    with zipfile.ZipFile(args.src) as z:
        parts = {n: z.read(n) for n in z.namelist()}
        infos = {n: z.getinfo(n) for n in z.namelist()}

    s1 = parts["xl/worksheets/sheet1.xml"].decode("utf-8")

    # 共享字符串（若有）
    ss = []
    if "xl/sharedStrings.xml" in parts:
        raw = parts["xl/sharedStrings.xml"].decode("utf-8", "replace")
        from columns import unescape_xml
        for m in re.finditer(r"<si>(.*?)</si>", raw, re.S):
            ss.append(unescape_xml("".join(
                re.findall(r"<t[^>]*>(.*?)</t>", m.group(1), re.S))))

    def text_of(attrs, body):
        if body is None:
            return ""
        if "inlineStr" in attrs:
            m = re.search(r"<is>.*?<t[^>]*>(.*?)</t>", body, re.S)
            from columns import unescape_xml
            return unescape_xml(m.group(1)) if m else ""
        m = re.search(r"<v>(.*?)</v>", body, re.S)
        if not m:
            return ""
        raw = m.group(1)
        if 't="s"' in attrs:
            try:
                return ss[int(raw)]
            except (ValueError, IndexError):
                return ""
        from columns import unescape_xml
        return unescape_xml(raw)

    # 表头 -> 定位 ASIN 列
    hdr = {}
    for rm in re.finditer(r'<row r="(\d+)"[^>]*>(.*?)</row>', s1, re.S):
        if int(rm.group(1)) != args.header_row:
            continue
        for cm in re.finditer(
                r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)',
                rm.group(2), re.S):
            hdr[cm.group(1)] = text_of(cm.group(2), cm.group(3))
        break
    mapping, missing = resolve_columns(hdr)
    if "ASIN" not in mapping:
        raise SystemExit(f"未找到 ASIN 列。表头: {list(hdr.values())[:10]}")
    asin_col = mapping["ASIN"]
    print(f"ASIN 列 = {asin_col}")

    # 新列位置
    cols = set(m.group(1) for m in re.finditer(r'<c r="([A-Z]+)\d+"', s1))
    start = max(col_to_idx(c) for c in cols) + 1 if cols else 1
    letters = [idx_to_col(start + i) for i in range(len(COLUMNS))]
    print(f"新列 {letters[0]}~{letters[-1]}（第 {start}~{start+len(COLUMNS)-1} 列）")

    added, missing_rows = 0, []

    def patch(mm):
        nonlocal added
        tag, rn_s, body, close = mm.group(1), mm.group(2), mm.group(3), mm.group(4)
        rn = int(rn_s)
        if rn < args.first_row:
            return mm.group(0)

        # 取 ASIN
        am = re.search(rf'<c r="{asin_col}\d+"([^>]*?)>(.*?)</c>', body, re.S)
        asin = text_of(am.group(1), am.group(2)).strip() if am else ""

        r = by_asin.get(asin)
        if r is None:
            missing_rows.append((rn, asin))
            return mm.group(0)

        cells = []
        for (label, key), letter in zip(COLUMNS, letters):
            if key is None:
                cells.append(
                    f'<c r="{letter}{rn}" s="2" t="inlineStr">'
                    f'<is><t xml:space="preserve">{esc(build_reason(r))}'
                    f'</t></is></c>')
            elif key == "stars":
                cells.append(f'<c r="{letter}{rn}" s="2" t="n">'
                             f'<v>{int(r[key])}</v></c>')
            else:
                cells.append(f'<c r="{letter}{rn}" s="2" t="n">'
                             f'<v>{float(r[key]):.2f}</v></c>')
        added += 1
        return tag + body + "".join(cells) + close

    s1_new = re.sub(r'(<row r="(\d+)"[^>]*>)(.*?)(</row>)', patch, s1, flags=re.S)
    print(f"写入 {added} 行，未匹配 {len(missing_rows)}")
    if missing_rows[:3]:
        print(f"  未匹配样例: {missing_rows[:3]}")

    # 表头
    hdr_cells = "".join(
        f'<c r="{letter}{args.header_row}" s="1" t="inlineStr">'
        f'<is><t>{label}</t></is></c>'
        for (label, _), letter in zip(COLUMNS, letters))
    m4 = re.search(rf'(<row r="{args.header_row}"[^>]*>)(.*?)(</row>)',
                   s1_new, re.S)
    if m4:
        s1_new = s1_new[:m4.start(3)] + hdr_cells + s1_new[m4.start(3):]

    last = max(int(x) for x in re.findall(r'<row r="(\d+)"', s1_new))
    s1_new = re.sub(r'<dimension ref="[^"]*"',
                    f'<dimension ref="A1:{letters[-1]}{last}"',
                    s1_new, count=1)

    cw = "".join(f'<col min="{start+i}" max="{start+i}" width="{w}" '
                 f'customWidth="1"/>' for i, w in enumerate(WIDTHS))
    s1_new = s1_new.replace("</cols>", cw + "</cols>", 1)

    parts["xl/worksheets/sheet1.xml"] = s1_new.encode("utf-8")

    if os.path.exists(args.dst):
        os.remove(args.dst)
    with zipfile.ZipFile(args.dst, "w", zipfile.ZIP_DEFLATED) as zo:
        for n in parts:
            zo.writestr(infos[n], parts[n])

    print(f"\n已写出 {args.dst}")
    print(f"大小 {os.path.getsize(args.dst):,} bytes")


if __name__ == "__main__":
    main()
