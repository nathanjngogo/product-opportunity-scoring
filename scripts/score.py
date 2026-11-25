# -*- coding: utf-8 -*-
"""产品机会评分 —— 四层模型

用法:
    python score.py <看板.xlsx> [--out workdir] [选项]

四层模型：
  L1 类目内稳健标准化（Winsorize P10-P90 + min-max）
  L2 产品竞争力分（7 信号等权加权几何平均）
  L3 类目赛道分（有效容量/竞争度/新品机会）
  L4 两层乘法合成 + 硬约束

设计依据见 references/model-spec.md，踩坑记录见 references/pitfalls.md。
"""
import argparse
import bisect
import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dataio import load_workbook, zh_segs  # noqa: E402

# 信号定义：(语义名, 方向)  方向 +1 正向 / -1 反向
SIGNALS = [
    ("月销量", +1),
    ("评价增幅", +1),
    ("评价数", -1),
    ("跟卖数", -1),
    ("差评率", +1),
    ("完整度", -1),
    ("毛利额", +1),
]

DEFAULTS = {
    "min_cat_size": 15,
    "new_days": 365,
    "eps": 0.02,
    "cat_weight": 0.5,
    "use_trend": True,
    "winsor_lo": 0.10,
    "winsor_hi": 0.90,
    "trend_winsor_lo": 0.05,
    "trend_winsor_hi": 0.95,
    "cr_main": 10,
    "form_penalty": 0.15,
    "hard_v": 20000,
    "hard_w": 4.5,
    "hard_penalty": 20,
}


def pctile(vals, q):
    s = sorted(x for x in vals if x is not None)
    if not s:
        return 0.0
    return s[min(int(len(s) * q), len(s) - 1)]


def pct_rank(sv, v):
    if not sv:
        return 50.0
    return bisect.bisect_left(sv, v) / max(len(sv) - 1, 1) * 100


def winsorize(vals, lo, hi):
    a, b = pctile(vals, lo), pctile(vals, hi)
    if b <= a:
        mx = max((x for x in vals if x is not None), default=None)
        b = mx if (mx is not None and mx > a) else a + 1
    return [min(max(x, a), b) if x is not None else None for x in vals]


class Scorer:
    def __init__(self, data, cfg=None):
        self.d = data
        self.cfg = {**DEFAULTS, **(cfg or {})}
        self.rows = data["rows"]
        self.mp = data["mapping"]
        self.N = len(self.rows)

        if data["missing"]:
            raise SystemExit(f"缺少必需列: {data['missing']}")

    # 取信号原始值（方向已统一为「越大越好」）
    def sig_value(self, r, sem, direction):
        v = r["nums"].get(self.mp[sem])
        if v is None:
            return None
        if direction > 0:
            return v
        if sem == "评价数":
            return -math.log10(v) if v > 0 else None
        return -v

    # ── 类目归属
    def _assign(self):
        col = self.mp["类目路径"]
        c2, c1 = defaultdict(list), defaultdict(list)
        p2, p1 = {}, {}
        for r in self.rows:
            segs = zh_segs(r["txt"].get(col))
            k2 = "/".join(segs[:2]) if len(segs) >= 2 else (segs[0] if segs else "(无)")
            k1 = segs[0] if segs else "(无)"
            c2[k2].append(r)
            c1[k1].append(r)
            p2[r["row"]], p1[r["row"]] = k2, k1

        thr = self.cfg["min_cat_size"]
        self.lvl = {r["row"]: (("2", p2[r["row"]]) if len(c2[p2[r["row"]]]) >= thr
                               else ("1", p1[r["row"]]))
                    for r in self.rows}
        self.groups = defaultdict(list)
        for r in self.rows:
            self.groups[self.lvl[r["row"]]].append(r)

    # ── L1 类目内标准化
    def _normalize(self):
        self.X = {}
        for sem, direction in SIGNALS:
            col = [0.5] * self.N
            for gk, ps in self.groups.items():
                idxs = [i for i, r in enumerate(self.rows)
                        if self.lvl[r["row"]] == gk]
                if len(idxs) < 3:
                    continue
                vals = [self.sig_value(self.rows[i], sem, direction)
                        for i in idxs]
                pres = [(j, v) for j, v in enumerate(vals) if v is not None]
                if len(pres) < 3:
                    continue
                xs = winsorize([v for _, v in pres],
                               self.cfg["winsor_lo"], self.cfg["winsor_hi"])
                lo, hi = min(xs), max(xs)
                nx = ([(x - lo) / (hi - lo) for x in xs] if hi > lo
                      else [0.5] * len(xs))
                for j, (pos, _) in enumerate(pres):
                    col[idxs[pos]] = nx[j]
            self.X[sem] = col

    # ── L2 产品分
    def _product(self):
        eps = self.cfg["eps"]
        w = 1.0 / len(SIGNALS)
        raw = [math.exp(sum(w * math.log(self.X[sem][i] + eps)
                            for sem, _ in SIGNALS))
               for i in range(self.N)]
        lo, hi = min(raw), max(raw)
        self.PROD = ([(x - lo) / (hi - lo) * 100 for x in raw] if hi > lo
                     else [50.0] * self.N)

    # ── L3 类目分
    def _category(self):
        cfg = self.cfg
        cf = {}
        for gk, ps in self.groups.items():
            n = len(ps)
            amt = sum((p["nums"].get(self.mp["月销额"]) or 0) for p in ps)
            qtys = sorted((p["nums"].get(self.mp["月销量"]) or 0 for p in ps),
                          reverse=True)
            tot = sum(qtys)

            recent, prev = [], []
            if cfg["use_trend"] and self.d["months"]:
                mo = self.d["months"]
                for p in ps:
                    t = self.d["trend"].get(
                        p["row"] - self.d["trend_offset"], {})
                    for i, m in enumerate(mo):
                        if m in t:
                            (recent if i < 6 else prev if i < 12 else []).append(t[m])
            ra = sum(recent) / len(recent) if recent else 0
            pa = sum(prev) / len(prev) if prev else 0
            tg = ((ra / pa - 1) * 100) if pa > 0 else 0

            crs = {k: (sum(qtys[:k]) / tot * 100 if tot > 0 else 100.0)
                   for k in (3, 5, 10, 20)}

            news = [p for p in ps
                    if (v := p["nums"].get(self.mp["上架天数"])) is not None
                    and v < cfg["new_days"]]
            nq = sum((p["nums"].get(self.mp["月销量"]) or 0) for p in news)
            cf[gk] = {"n": n, "amt": amt, "trend": tg, "crs": crs,
                      "new_cnt_r": len(news) / n * 100,
                      "new_qty_r": nq / tot * 100 if tot else 0}

        keys = list(cf.keys())
        cap_r = [math.log10(cf[k]["amt"] + 1) for k in keys]
        trd_r = winsorize([cf[k]["trend"] for k in keys],
                          cfg["trend_winsor_lo"], cfg["trend_winsor_hi"])
        cmp_r = [100 - cf[k]["crs"][cfg["cr_main"]] for k in keys]
        new_r = [0.5 * cf[k]["new_qty_r"] + 0.5 * cf[k]["new_cnt_r"]
                 for k in keys]

        sv = {n: sorted(v) for n, v in
              (("cap", cap_r), ("trd", trd_r), ("cmp", cmp_r), ("new", new_r))}
        CAP = [pct_rank(sv["cap"], x) for x in cap_r]
        TRD = [pct_rank(sv["trd"], x) for x in trd_r]
        CMPm = [pct_rank(sv["cmp"], x) for x in cmp_r]
        NEW = [pct_rank(sv["new"], x) for x in new_r]

        # 有效容量：加权几何补偿
        ECAP = []
        for i in range(len(keys)):
            a, b = max(CAP[i], 1.0), max(TRD[i], 1.0)
            th = (100 - CAP[i]) / 100 * 0.5
            ECAP.append((a ** (1 - th)) * (b ** th))
        se = sorted(ECAP)
        ECAPp = [pct_rank(se, x) for x in ECAP]

        form = [(cf[k]["crs"][3] / cf[k]["crs"][cfg["cr_main"]]
                 if cf[k]["crs"][cfg["cr_main"]] > 0 else 1.0) for k in keys]
        sf = sorted(form)
        CMP = [max(0.0, CMPm[i] - pct_rank(sf, form[i]) * cfg["form_penalty"])
               for i in range(len(keys))]

        self.cat_detail = {}
        for i, k in enumerate(keys):
            self.cat_detail[k] = {
                "cat": round((ECAPp[i] + CMP[i] + NEW[i]) / 3, 2),
                "cap": round(CAP[i], 2), "trd": round(TRD[i], 2),
                "ecap": round(ECAPp[i], 2), "cmp": round(CMP[i], 2),
                "new": round(NEW[i], 2),
                "amt": cf[k]["amt"], "trend": round(cf[k]["trend"], 2),
                "cr3": round(cf[k]["crs"][3], 2),
                "cr5": round(cf[k]["crs"][5], 2),
                "cr10": round(cf[k]["crs"][10], 2),
                "cr20": round(cf[k]["crs"][20], 2),
                "new_cnt_r": round(cf[k]["new_cnt_r"], 2),
                "new_qty_r": round(cf[k]["new_qty_r"], 2),
                "n": cf[k]["n"],
            }
        self.CAT = {k: v["cat"] for k, v in self.cat_detail.items()}

    # ── L4 合成
    def _combine(self):
        cfg = self.cfg
        w = cfg["cat_weight"]
        self.FINAL, self.penalty, self.gates = [], [], []
        for i, r in enumerate(self.rows):
            cat = self.CAT[self.lvl[r["row"]]]
            s = self.PROD[i] * ((1 - w) + w * cat / 100)

            p, why = 0.0, []
            v = r["nums"].get(self.mp["评价数"])
            ww = r["nums"].get(self.mp["评分"])
            if (v is not None and v > cfg["hard_v"]
                    and (ww if ww is not None else 5) >= cfg["hard_w"]):
                p += cfg["hard_penalty"]
                why.append(f"评价{v:,.0f}+评分{ww}")
            self.FINAL.append(max(0.0, min(100.0, s - p)))
            self.penalty.append(p)
            self.gates.append(why)

    def _stars(self):
        sv = sorted(self.FINAL)

        def st(v):
            p = pct_rank(sv, v)
            return 5 if p >= 90 else 4 if p >= 70 else 3 if p >= 40 \
                else 2 if p >= 15 else 1

        self.STARS = [st(v) for v in self.FINAL]

    def fit(self):
        self._assign()
        self._normalize()
        self._product()
        self._category()
        self._combine()
        self._stars()
        return self

    def transform(self):
        recs = []
        for i, r in enumerate(self.rows):
            gk = self.lvl[r["row"]]
            cd = self.cat_detail[gk]
            recs.append({
                "row": r["row"],
                "asin": r["txt"].get(self.mp["ASIN"], ""),
                "name": r["txt"].get(self.mp["产品名称"], ""),
                "cat": gk[1], "cat_level": gk[0],
                "g": r["nums"].get(self.mp["月销量"]),
                "v": r["nums"].get(self.mp["评价数"]),
                "w": r["nums"].get(self.mp["评分"]),
                "aj": r["nums"].get(self.mp["差评率"]),
                "ad": (r["nums"].get(self.mp["毛利率"])
                       if "毛利率" in self.mp else None),
                "o": r["nums"].get(self.mp["毛利额"]),
                "price": (r["nums"].get(self.mp["价格"])
                          if "价格" in self.mp else None),
                "cap": cd["cap"], "trd": cd["trd"], "cmp": cd["cmp"],
                "new": cd["new"], "cat_score": cd["cat"],
                "cat_amt": cd["amt"], "cat_trend": cd["trend"],
                "cat_cr3": cd["cr3"], "cat_cr10": cd["cr10"],
                "cat_new_qty": cd["new_qty_r"],
                "prod_score": round(self.PROD[i], 2),
                "penalty": self.penalty[i], "gate": self.gates[i],
                "score": round(self.FINAL[i], 2),
                "stars": self.STARS[i],
            })
        return {"model": "four-layer opportunity scoring",
                "config": self.cfg, "col_mapping": self.mp,
                "records": recs,
                "cat_detail": {f"{k[0]}|{k[1]}": v
                               for k, v in self.cat_detail.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--out", default="workdir")
    ap.add_argument("--min-cat-size", type=int, default=15)
    ap.add_argument("--new-days", type=int, default=365)
    ap.add_argument("--eps", type=float, default=0.02)
    ap.add_argument("--cat-weight", type=float, default=0.5)
    ap.add_argument("--no-trend", action="store_true")
    ap.add_argument("--first-row", type=int, default=5)
    ap.add_argument("--header-row", type=int, default=4)
    ap.add_argument("--trend-offset", type=int, default=3)
    args = ap.parse_args()

    data = load_workbook(args.xlsx, args.header_row, args.first_row,
                         args.trend_offset)
    print(f"产品 {len(data['rows'])}  趋势月份 {len(data['months'])}")

    s = Scorer(data, {
        "min_cat_size": args.min_cat_size,
        "new_days": args.new_days,
        "eps": args.eps,
        "cat_weight": args.cat_weight,
        "use_trend": not args.no_trend,
    }).fit()
    out = s.transform()

    os.makedirs(args.out, exist_ok=True)
    p = os.path.join(args.out, "score_result.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    recs = out["records"]
    N = len(recs)
    dist = Counter(r["stars"] for r in recs)
    sv = sorted(r["score"] for r in recs)
    m = sum(sv) / N
    sd = math.sqrt(sum((x - m) ** 2 for x in sv) / N)

    print(f"\n分数 {sv[0]:.1f}~{sv[-1]:.1f}  均值 {m:.1f}  σ {sd:.1f}  "
          f"CV {sd/m:.3f}")
    for k in (5, 4, 3, 2, 1):
        print(f"  {k}星 {dist[k]:5d} ({dist[k]/N*100:5.1f}%)")
    print(f"硬约束命中: {sum(1 for r in recs if r['penalty'] > 0)}")

    print("\n类目分 Top 8:")
    for k, v in sorted(out["cat_detail"].items(),
                        key=lambda x: -x[1]["cat"])[:8]:
        print(f"  {v['cat']:>5.1f}  {k.split('|',1)[1][:32]:<32} "
              f"容量${v['amt']/1e4:>7.0f}万 趋势{v['trend']:>+6.1f}% "
              f"CR10={v['cr10']:>4.1f}% 新品{v['new_qty_r']:>4.1f}%")

    print("\n5星 Top 10:")
    for r in sorted([x for x in recs if x["stars"] == 5],
                    key=lambda x: -x["score"])[:10]:
        print(f"  {r['score']:>5.1f} 类目{r['cat_score']:>4.0f} "
              f"产品{r['prod_score']:>4.0f}  {r['name'][:40]}")

    print(f"\n已保存 {p}")


if __name__ == "__main__":
    main()
