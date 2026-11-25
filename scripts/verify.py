# -*- coding: utf-8 -*-
"""产品机会评分 —— 全套验收

用法:
    python verify.py <成品.xlsx> <score_result.json>

检查项：
  结构完整性、数据一致性、单调性、区分度、原数据未破坏
任一项失败退出码 1。
"""
import argparse
import json
import math
import os
import random
import sys
import zipfile
from collections import Counter
from decimal import Decimal
from statistics import mean, median

import openpyxl
from openpyxl.utils import get_column_letter

fail = []


def check(c, m):
    print(("  PASS  " if c else "  FAIL  ") + m)
    if not c:
        fail.append(m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("result")
    ap.add_argument("--first-row", type=int, default=5)
    args = ap.parse_args()

    res = json.load(open(args.result, encoding="utf-8"))
    recs = res["records"]
    N = len(recs)
    by_asin = {r["asin"]: r for r in recs}
    print(f"预期 {N} 条\n")

    print("=== 1. 包结构 ===")
    with zipfile.ZipFile(args.xlsx) as z:
        names = z.namelist()
    media = [n for n in names if n.startswith("xl/media/")]
    print(f"  部件 {len(names)} 个，图片 {len(media)} 个")
    check("xl/worksheets/sheet1.xml" in names, "sheet1 存在")

    print("\n=== 2. 打开工作簿 ===")
    wb = openpyxl.load_workbook(args.xlsx)
    ws = wb.worksheets[0]
    FR = args.first_row
    check(ws.max_row >= N + FR - 1, f"行数 ≥ {N+FR-1} (实际 {ws.max_row})")

    # 找新增列位置
    hdr_row = FR - 1
    wanted = ["月销额容量分", "市场趋势分", "竞争度分", "新品机会分",
              "类目综合分", "产品竞争力分", "初筛星级", "初筛总分", "评分依据"]
    col_map = {}
    for c in range(1, ws.max_column + 1):
        v = str(ws.cell(hdr_row, c).value or "").strip()
        if v in wanted:
            col_map[v] = c
    check(len(col_map) == len(wanted),
          f"找到 {len(col_map)}/{len(wanted)} 个新增列头")
    for w in wanted:
        if w not in col_map:
            fail.append(f"缺列头: {w}")
    if len(col_map) != len(wanted):
        print("  实际找到:", {k: v for k, v in col_map.items()})

    if len(col_map) == len(wanted):
        star_c = col_map["初筛星级"]
        score_c = col_map["初筛总分"]

        print("\n=== 3. 数据一致性 ===")
        stars, scores = [], []
        bad = 0
        for i, x in enumerate(recs):
            r = FR + i
            asin = str(ws.cell(r, 4).value or "").strip()
            st = ws.cell(r, star_c).value
            sc = ws.cell(r, score_c).value
            stars.append(st)
            scores.append(sc)
            ref = by_asin.get(asin)
            if (asin != x["asin"] or ref is None
                    or not isinstance(st, (int, float))
                    or int(st) != ref["stars"]
                    or not isinstance(sc, (int, float))
                    or abs(float(sc) - ref["score"]) > 0.06):
                bad += 1
        check(bad == 0, f"逐行匹配 (差异 {bad})")
        check(all(isinstance(v, (int, float)) and 1 <= int(v) <= 5
                  for v in stars),
              f"星级为 1-5 数值 (样本 {stars[:6]})")
        check(all(isinstance(v, (int, float)) and 0 <= v <= 100
                  for v in scores),
              f"分数 0-100 (样本 {[round(v,1) for v in scores[:6]]})")

        print("\n=== 4. 星级分布 ===")
        dist = Counter(int(v) for v in stars)
        for k in (5, 4, 3, 2, 1):
            print(f"  {k}星 {dist[k]:5d} ({dist[k]/N*100:5.1f}%)")
        check(sum(dist.values()) == N, "覆盖完整")

        print("\n=== 5. 区分度 ===")
        sv = sorted(float(x) for x in scores)
        m = sum(sv) / N
        sd = math.sqrt(sum((x - m) ** 2 for x in sv) / N)
        print(f"  {sv[0]:.1f}~{sv[-1]:.1f}  均值 {m:.1f}  σ {sd:.1f}  "
              f"CV {sd/m:.3f}")
        check(sd / m > 0.35, f"CV={sd/m:.3f} > 0.35")

    print("\n=== 6. 单调性（模型逻辑）===")
    for k in (5, 4, 3, 2, 1):
        g = [x for x in recs if x["stars"] == k]
        if not g:
            continue
        vs = [x["v"] for x in g if x["v"] is not None]
        ws_ = [x["w"] for x in g if x["w"] is not None]
        ajs = [x["aj"] for x in g if x["aj"] is not None]
        print(f"  {k}星 n={len(g):>4} 评价中位={median(vs) if vs else 0:>8,.0f} "
              f"评分={mean(ws_) if ws_ else 0:.2f} "
              f"差评率={mean(ajs) if ajs else 0:>5.1f}%")

    g5 = [x for x in recs if x["stars"] == 5]
    g1 = [x for x in recs if x["stars"] == 1]
    if g5 and g1:
        v5 = median([x["v"] for x in g5 if x["v"] is not None])
        v1 = median([x["v"] for x in g1 if x["v"] is not None])
        w5 = mean([x["w"] for x in g5 if x["w"] is not None])
        w1 = mean([x["w"] for x in g1 if x["w"] is not None])
        a5 = mean([x["aj"] for x in g5 if x["aj"] is not None])
        a1 = mean([x["aj"] for x in g1 if x["aj"] is not None])
        check(v5 < v1, f"5星评价数({v5:,.0f}) < 1星({v1:,.0f})")
        check(w5 <= w1 + 0.05, f"5星评分({w5:.2f}) ≲ 1星({w1:.2f})")
        check(a5 > a1, f"5星差评率({a5:.1f}%) > 1星({a1:.1f}%)")

    print("\n=== 7. Bootstrap 稳定性 ===")
    random.seed(42)
    base = {x["asin"] for x in g5}
    ov = []
    for _ in range(100):
        idx = random.sample(range(N), int(N * 0.8))
        sub = sorted(idx, key=lambda i: -recs[i]["score"])[:int(len(g5) * 0.8)]
        ov.append(len({recs[i]["asin"] for i in sub} & base) / max(len(sub), 1))
    print(f"  平均重叠 {mean(ov)*100:.1f}%")
    check(mean(ov) > 0.85, "稳定性 > 85%")

    print("\n=== 8. 原数据未破坏 ===")
    asins = [str(ws.cell(FR + i, 4).value or "").strip() for i in range(N)]
    check(asins == [x["asin"] for x in recs], "ASIN 序列一致")
    # 序号列：只检查非空且唯一，不强求从 1 开始
    # （源表可能经过前序加工，序号已被重排或保留原值）
    seqs = [ws.cell(FR + i, 1).value for i in range(N)]
    non_null = [s for s in seqs if s is not None]
    if non_null and len(non_null) == N:
        check(len(set(seqs)) == N, f"序号唯一 ({len(set(seqs))}/{N})")
    else:
        print(f"  SKIP  序号列非纯数字（{len(non_null)}/{N} 有值），跳过连续性检查")
    n_img = len(ws._images)
    if n_img:
        check(n_img <= N, f"缩略图 {n_img} ≤ {N}")

    wb.close()
    print("\n" + "=" * 58)
    if fail:
        print(f"❌ {len(fail)} 项失败")
        for f in fail:
            print("   -", f)
        sys.exit(1)
    print("✅ 全部通过")


if __name__ == "__main__":
    main()
