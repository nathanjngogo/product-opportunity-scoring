# 快速开始

## 完整流程（4 步）

```bash
# 0. 设置（把 SKILL 指向本技能 scripts 目录）
SKILL=/path/to/skills/product-opportunity-scoring/scripts

# 1. 探查数据结构（必做第一步）
python "$SKILL/probe.py" 看板.xlsx --out workdir

# 2. 跑评分模型
python "$SKILL/score.py" 看板.xlsx --out workdir

# 3. 写入 Excel
python "$SKILL/write_scores.py" 看板.xlsx workdir/score_result.json \
        输出_含评分.xlsx

# 4. 验收
python "$SKILL/verify.py" 输出_含评分.xlsx workdir/score_result.json
```

## 第 1 步：探查（决定模型形式）

`probe.py` 输出四块信息，**必须看完再跑第 2 步**：

### 1.1 字段完整率

```
字段   有效   缺失%   最小   中位   最大   偏度   CV
G      2143   0.0%   1388  2452  82202  6.26  1.15
V      2143   0.0%      1    1264  130875  ...
AJ     2095   2.2%      1     10     32   0.60  0.55
```

**看什么**：
- 缺失率 >5% 的信号要考虑是否降级
- |偏度| > 2 的信号在标准化时会被 log 压缩
- CV < 0.15 的信号区分度差，等权时会稀释总分

### 1.2 类目层级分布

```
一级类目: 18 个，中位 116 条
二级类目: 161 个，中位 7 条
三级类目: 538 个，中位 2 条
```

**看什么**：决定用哪一级分组。
判据：`n≥15 的类目覆盖了多少产品`。覆盖 <60% 说明类目太碎，考虑用一级。

### 1.3 趋势表结构

```
月份列 24 个，范围 2024-11 ~ 2026-10
趋势行 2143 条，对齐检验 50/50 通过
```

**看什么**：
- 月份数 <12 → 趋势维度不可靠，建议关掉
- 对齐检验失败 → 偏移量要重新实测

### 1.4 信号相关矩阵与 KMO

```
KMO = 0.4839
Bartlett χ² = 3720.1, df = 28
PC1 特征值 = 1.904，解释 23.8%
显著冗余对: BE×V (0.665), M×O (0.706)
```

**看什么**：
- KMO < 0.6 → **用等权**，不要再折腾自定义权重
- 冗余对 |ρ|>0.7 → 考虑合并或去掉一个

## 第 2 步：评分

```bash
python "$SKILL/score.py" 看板.xlsx --out workdir
```

可选参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `--min-cat-size` | 15 | 类目样本量下限，低于则退上一级 |
| `--new-days` | 365 | 新品判定阈值（天） |
| `--eps` | 0.02 | 几何平均的防零常数 |
| `--no-trend` | 关 | 关闭趋势维度（无趋势表时） |
| `--cat-weight` | 0.5 | 类目分权重（`mult = 1-w + w*CAT/100`） |

输出 `workdir/score_result.json`，含：
- 每个产品的四维分、两层分、总分、星级
- 类目级指标（容量/趋势/CR/新品）
- 模型元信息（权重、检验结果）

## 第 3 步：写入 Excel

```bash
python "$SKILL/write_scores.py" 看板.xlsx workdir/score_result.json 输出.xlsx
```

新增 9 列，追加在表格末尾：

```
CA 月销额容量分    CB 市场趋势分     CC 竞争度分
CD 新品机会分      CE 类目综合分     CF 产品竞争力分
CG 初筛星级        CH 初筛总分       CI 评分依据
```

## 第 4 步：验收

```bash
python "$SKILL/verify.py" 输出.xlsx workdir/score_result.json
```

检查项：

```
[ ] 部件与源文件一致（图片、超链接未丢）
[ ] 列数 = 原列数 + 9
[ ] 星级为 1-5 数值（不是文本）
[ ] 分数在 0-100
[ ] 逐行与 score_result.json 匹配
[ ] 星级单调性：5星评价数 < 1星、5星差评率 > 1星
[ ] 区分布 CV > 0.4
[ ] 原数据未破坏（ASIN/序号/超链接/缩略图）
[ ] 汇总行正确
```

## 单独调用模型

```python
import sys
sys.path.insert(0, "…/skills/product-opportunity-scoring/scripts")
from score import Scorer

s = Scorer(product_rows, trend_table=None)
s.fit()
result = s.transform()

for r in result["records"][:5]:
    print(r["score"], r["stars"], r["cat"], r["gate"])
```

## 调整模型

| 需求 | 改哪里 |
|---|---|
| 换权重方案 | `score.py` 的 `WEIGHTS` 常量 |
| 加/减信号 | `SIGNALS` 列表 + `build_features()` |
| 改准入约束 | `apply_penalty()` |
| 改星级切分 | `star_by_quantile()` 的分位阈值 |
| 类目层级策略 | `assign_level()` 的 `min_size` |

**改完必须重跑 `verify.py`**，并检查星级单调性是否还成立。

## 常见问题

**Q: 跑出来所有产品都是 3 星？**
A: 检查是否用了秩变换标准化（会把分布压平）。
   应该用 Winsorize + min-max。

**Q: 5 星全是同一个类目？**
A: 检查是否做了类目内标准化。
   如果做了还这样，说明该类目确实占优，看 `cat_score` 分布确认。

**Q: 趋势维度全 50 分？**
A: 趋势表没读到。检查 `--no-trend` 是否误开，或趋势表对齐偏移是否不同。

**Q: CR10 全是 100%？**
A: 类目样本太少。调大 `--min-cat-size`，或退到一级分类。

**Q: 区分度 CV < 0.4？**
A: 两个原因：① 信号太少 ② 用了会压平分布的方法。
   先看 `probe.py` 里各信号的 CV，替换掉区分度差的信号。

**Q: 能不能不用类目维度？**
A: 可以，`--cat-weight 0` 即退化为纯产品评分。
   但会失去"赛道"信息，5 星里会混进红海类目的产品。

