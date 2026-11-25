# -*- coding: utf-8 -*-
"""产品机会评分 —— 数据结构探查

用法:
    python inspect.py <看板.xlsx> [--out workdir]
"""
import argparse
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from columns import describe, REQUIRED  # noqa: E402
from dataio import load_workbook, zh_segs  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--out", default=None)
    ap.add_argument("--header-row", type=int, default=4)
    ap.add_argument("--first-row", type=int, default=5)
    args = ap.parse_args()

    print("=" * 88)
    print(f"探查 {os.path.basename(args.xlsx)}")
    print("=" * 88)

    d = load_workbook(args.xlsx, args.header_row, args.first_row)
    rows, mp = d["rows"], d["mapping"]
    N = len(rows)
    print(f"\n表头 r{args.header_row}: {len(d['headers'])} 列   "
          f"数据行: {N}   "
          f"字符串格式: {'inlineStr' if d['has_inline'] else 'sharedStrings'}")

    # ══════════ 1. 列映射
    print("\n" + "=" * 88)
    print("1. 列映射（按表头名称定位）")
    print("=" * 88)
    print(describe(mp, d["headers"]))

    if d["missing"]:
        print(f"\n  ❌ 缺失必需列: {d['missing']}")
        print("  请检查表头名称，或在 columns.py 的 SPEC 里补充关键字")
        return 1
    print("\n  ✅ 必需列齐全")

    # ══════════ 2. 字段分布
    print("\n" + "=" * 88)
    print("2. 字段完整率与分布")
    print("=" * 88)
    print(f"{'语义':<10} {'列':>3} {'有效':>6} {'缺失%':>7} {'最小':>10} "
          f"{'中位':>10} {'最大':>11} {'偏度':>8} {'CV':>7}")
    print("-" * 88)

    stats = {}
    for sem in ["月销量", "月销额", "评价数", "评分", "差评率", "毛利率",
                "毛利额", "价格", "跟卖数", "完整度", "上架天数", "评价增幅"]:
        if sem not in mp:
            continue
        col = mp[sem]
        vals = [r["nums"].get(col) for r in rows]
        vals = [v for v in vals if v is not None]
        if not vals:
            print(f"{sem:<10} {col:>3} {'0':>6}  {'全缺失':>7}")
            continue
        srt = sorted(vals)
        n = len(srt)
        m = sum(srt) / n
        sd = math.sqrt(sum((x - m) ** 2 for x in srt) / n)
        sk = (sum((x - m) ** 3 for x in srt) / n / sd ** 3) if sd > 1e-12 else 0
        cv = sd / abs(m) if m else 0
        stats[sem] = {"n": n, "cv": cv, "skew": sk}
        print(f"{sem:<10} {col:>3} {n:>6} {(N-n)/N*100:>6.1f}% "
              f"{srt[0]:>10.2f} {srt[n//2]:>10.2f} {srt[-1]:>11.2f} "
              f"{sk:>8.2f} {cv:>7.2f}")

    low = [s for s, v in stats.items() if v["cv"] < 0.15]
    if low:
        print(f"\n  ⚠ 区分度差(CV<0.15): {low}")

    # ══════════ 3. 类目层级
    print("\n" + "=" * 88)
    print("3. 类目层级分布")
    print("=" * 88)
    catcol = mp.get("类目路径")
    if not catcol:
        print("  ✗ 无类目路径列")
    else:
        for name, fn in (
            ("一级", lambda s: s[0] if s else "(无)"),
            ("二级", lambda s: "/".join(s[:2]) if len(s) >= 2
                                else (s[0] if s else "(无)")),
        ):
            g = defaultdict(int)
            for r in rows:
                g[fn(zh_segs(r["txt"].get(catcol)))] += 1
            sizes = sorted(g.values())
            print(f"\n{name}类目: {len(sizes)} 个   min={sizes[0]} "
                  f"中位={sizes[len(sizes)//2]} max={sizes[-1]}")
            for th in (10, 15, 20, 30):
                cnt = sum(1 for s in sizes if s >= th)
                cov = sum(s for s in sizes if s >= th) / N * 100
                print(f"  ≥{th:>2} 条: {cnt:>4} 个类目，覆盖 {cov:>5.1f}%")

    # ══════════ 4. 趋势表
    print("\n" + "=" * 88)
    print("4. 趋势表结构")
    print("=" * 88)
    months = d["months"]
    if not months:
        print("  ✗ 无趋势表，趋势维度将降级为中性 50")
    else:
        print(f"  月份 {len(months)} 个: {months[-1]} ~ {months[0]}")
        ok = len(months) >= 12
        print(f"  {'✓ 可用' if ok else '⚠ 不足12个月，建议 --no-trend'}")
        hit = sum(1 for r in rows[:50]
                  if d["trend"].get(r["row"] - d["trend_offset"]))
        print(f"  对齐检验: 前50条 {hit}/50 "
              f"{'✓' if hit >= 45 else '✗ 偏移量需调整 --trend-offset'}")

    # ══════════ 5. 相关与 KMO
    print("\n" + "=" * 88)
    print("5. 相关矩阵与 KMO（决定权重方案）")
    print("=" * 88)

    use = [s for s in ["月销量", "评价增幅", "评价数", "跟卖数",
                       "差评率", "完整度", "毛利额"] if s in stats]
    if len(use) < 3:
        print("  ✗ 可用信号不足")
    else:
        def rank_col(vals):
            pres = [v for v in vals if v is not None]
            med = sorted(pres)[len(pres) // 2]
            f = [v if v is not None else med for v in vals]
            order = sorted(range(len(f)), key=lambda i: f[i])
            rk = [0.0] * len(f)
            i = 0
            while i < len(order):
                j = i
                while j + 1 < len(order) and f[order[j + 1]] == f[order[i]]:
                    j += 1
                avg = (i + j) / 2 + 1
                for t in range(i, j + 1):
                    rk[order[t]] = avg
                i = j + 1
            return rk

        R = [rank_col([r["nums"].get(mp[s]) for r in rows]) for s in use]
        k = len(use)

        def corr(a, b):
            n = len(a)
            ma, mb = sum(a) / n, sum(b) / n
            va = sum((x - ma) ** 2 for x in a)
            vb = sum((x - mb) ** 2 for x in b)
            if va <= 0 or vb <= 0:
                return 0.0
            return sum((a[i] - ma) * (b[i] - mb)
                       for i in range(n)) / math.sqrt(va * vb)

        C = [[corr(R[i], R[j]) for j in range(k)] for i in range(k)]
        print(f"{'':10}" + "".join(f"{s[:4]:>8}" for s in use))
        for i, s in enumerate(use):
            print(f"{s:<10}" + "".join(f"{C[i][j]:>8.2f}" for j in range(k)))

        red = [(use[i], use[j], C[i][j]) for i in range(k)
               for j in range(i + 1, k) if abs(C[i][j]) > 0.5]
        print("\n  冗余对 (|ρ|>0.5):")
        for a, b, v in red:
            print(f"    {a} × {b}  ρ={v:>6.3f}")
        if not red:
            print("    （无）")

        try:
            import numpy as np
            Rm = np.array(C)
            inv = np.linalg.pinv(Rm)
            dd = np.sqrt(np.diag(inv))
            P = -inv / np.outer(dd, dd)
            np.fill_diagonal(P, 0)
            Ro = Rm.copy()
            np.fill_diagonal(Ro, 0)
            r2 = (Ro ** 2).sum()
            kmo = r2 / (r2 + (P ** 2).sum())
            ev = np.linalg.eigvalsh(Rm.copy())[::-1]
            print(f"\n  KMO = {kmo:.4f}")
            print(f"  特征值: {[round(float(x), 3) for x in ev]}")
            print(f"  PC1 解释 {ev[0]/k*100:.1f}%")
            print("\n  → 权重建议:")
            if kmo < 0.6:
                print("    KMO<0.6 → 不支持因子分析，用【等权】")
            elif kmo < 0.8:
                print("    KMO 0.6-0.8 → 可考虑 PCA，需与等权对比")
            else:
                print("    KMO>0.8 → 可做因子分析")
            if ev[0] < 1.0:
                print("    最大特征值<1 → 无主导因子，等权最稳健")
        except ImportError:
            print("\n  （无 numpy，跳过 KMO）")

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        p = os.path.join(args.out, "inspect.json")
        json.dump({"n_rows": N, "col_mapping": mp,
                   "missing_required": d["missing"],
                   "field_stats": stats,
                   "trend_available": bool(months),
                   "header_row": args.header_row,
                   "first_row": args.first_row},
                  open(p, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"\n已保存 {p}")

    print("\n" + "=" * 88)
    return 0


if __name__ == "__main__":
    sys.exit(main())
