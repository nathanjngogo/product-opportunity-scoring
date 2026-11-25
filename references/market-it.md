# 意大利站（Amazon.it）类目规则

供 `product-opportunity-scoring` 的清洗阶段使用。
欧洲小语种市场的第一个落地样本，可作为西/法/德站的参考模板。

> **重要**：这份规则是为**清洗**服务的，不是评分模型的一部分。
> 评分模型（四层结构）与市场无关，只有类目词表需要本地化。

---

## 一、与美站/日站的结构差异

| 品类 | 美站位置 | 日本站位置 | **意大利站位置** |
|---|---|---|---|
| 保健品 | 健康与家庭/维生素矿物质 | ビューティー/栄養補助食品 | `Salute e cura della persona` > `Vitamine, minerali e integratori` |
| 药品 | 健康与家庭/保健产品 | ドラッグストア/医薬品 | `Salute e cura della persona` > `Prodotti per la medicazione` |
| 美妆 | 美容和个人护理 | ビューティー | `Bellezza`（独立一级类目） |
| 手机周边 | 手机和配件 | 家電＆カメラ/…/携帯電話 | `Elettronica` > `Telefonia` > `Cellulari e accessori` |
| 化工/清洁 | 健康与家庭/清洁用品 | ドラッグストア/日用品 | `Salute e cura della persona` > `Pulizia e cura della casa`（**与纸品混组**） |
| 相机 | 独立类目 | 家電＆カメラ | `Elettronica` > `Foto e videocamere` |
| 电脑周边 | 计算机和配件 | パソコン・周辺機器 | `Informatica` |
| 服装 | 服装鞋珠宝 | ファッション | `Moda` |

**关键差异**：意大利站把「清洁剂 + 卫生纸 + 口腔护理」都放在
`Salute e cura della persona`（健康与个人护理）下，需要按叶子分流。

---

## 二、一级类目全表（5000 条样本）

| 一级类目 | 数量 | 处理 |
|---|---|---|
| `Salute e cura della persona` | 889 | 按叶子分流（保健品/药品/化工/日化/口腔） |
| `Casa e cucina` | 688 | **保留**（家居厨房主战场） |
| `Bellezza` | 681 | **整类删**（美妆） |
| `Alimentari e cura della casa` | 484 | **整类删**（食品+清洁剂） |
| `Elettronica` | 390 | 按叶子（手机配件删、耳机保留） |
| `Cancelleria e prodotti per ufficio` | 277 | **保留**（文具） |
| `Informatica` | 198 | **整类删**（电脑周边） |
| `Prodotti per animali domestici` | 193 | 按叶子（食品/药品删、用品保留） |
| `Commercio, Industria e Scienza` | 190 | **保留**（工业科学） |
| `Moda` | 174 | **整类删**（服装） |
| `Prima infanzia` | 142 | **保留**（母婴用品） |
| `Sport e tempo libero` | 140 | **保留** |
| `Fai da te` | 121 | **保留**（DIY工具） |
| `Giochi e giocattoli` | 113 | **保留**（玩具） |
| `Auto e Moto` | 78 | **保留** |
| `Illuminazione` | 48 | **保留** |
| `Giardino e giardinaggio` | 45 | **保留** |
| `Videogiochi` | 27 | 软件删、配件保留 |
| `Strumenti Musicali` | 18 | **保留** |
| `Grandi elettrodomestici` | 12 | **保留** |

---

## 三、关键三级叶子清单

### 保健品（`Salute e cura della persona` 下）

```
Vitamine, minerali e integratori
Singole vitamine
Multivitamine e minerali
Singoli minerali
Aminoacidi
Enzimi
Integratori di sostanze e preparati vegetali
Proteine
Frullati e sostituti dei pasti
Alimentazione e nutrizione
```

**名称兜底**（仅品类专有词）：`integratore`、`supplemento`、
`proteine in polvere`、`omega 3`、`collagene`

> ⚠ 不要用 `vitamina` / `vitamin` —— 化妆品名里大量出现（见 pitfall 24）

### 药品与医疗（`Salute e cura della persona` 下）

```
Prodotti per la medicazione
Forniture sanitarie e igieniche
Dispositivi medici
Farmaci
Primo soccorso
Lenti a contatto
Cura della vista            ← 隐形眼镜护理液
Erotismo e contraccezione
Prodotti e apparecchiature mediche
```

### 美妆（`Bellezza` 整类 + `Salute` 下个护耗材）

`Bellezza` 下一律删，**但要保留硬件**：

| 保留的硬件叶子 |
|---|
| `Rasoi elettrici`（电动剃须刀） |
| `Rasoi manuali e lame`（手动剃须刀/刀片） |
| `Asciugacapelli`（吹风机） |
| `Piastre per capelli`（直发夹） |
| `Arricciacapelli`（卷发棒） |
| `Tagliacapelli`（理发器） |
| `Epilatori`（脱毛器） |
| `Spazzolini da denti elettrici`（电动牙刷） |
| `Spazzole e pettini`（梳子） |

### 化工 vs 日化（同在 `Pulizia e cura della casa` 下）

**必须按叶子分流**（见 pitfall 25）：

| 化工（化学品） | 日化（纸品耗材） |
|---|---|
| `Prodotti per il bucato` | `Carta igienica` |
| `Detergenti per la casa` | `Rotoli di carta igienica` |
| `Prodotti per lavare le stoviglie` | `Prodotti di carta` |
| `Ammorbidenti` | `Tovaglioli e fazzoletti` |
| `Candeggina` | `Panni e spugne` |
| `Anticalcare` | `Salviette umidificate` |
| `Disinfettanti` | `Pannolini` |
| `Insetticidi` | |
| `Deumidificatori` | |
| `Vernici e pitture` | |

**名称兜底**（杀虫剂/水垢剂散落在其它类目）：
`insetticida`、`scarafaggi`、`anticalcare`、`decalcificante`、
`disinfettante`、`candeggina`

### 口腔护理

| 保留（硬件） | 删除（耗材） |
|---|---|
| `Spazzolini da denti e accessori` | `Dentifrici`（牙膏） |
| `Spazzolini elettrici` | `Collutori`（漱口水） |
| `Idropulsori`（冲牙器） | `Filo interdentale`（牙线） |
| `Scovolini`（牙缝刷） | `Sbiancamento dei denti`（美白） |

### 宠物（`Prodotti per animali domestici`）

| 删（食品/药品） | 保留（用品） |
|---|---|
| `Cibo` | `Lettiere e accessori` |
| `Snack` | `Giochi` |
| `Crocchette` | `Trasportini` |
| `Umido` | `Guinzagli e collari` |
| `Antiparassitari` | `Tiragraffi` |
| `Salute e cura` | |

**注意结构**：`Prodotti per animali domestici > Gatti > Cibo`
—— 第二层是**宠物种类**（Gatti/Cani），第三层才是**品类型**。
判定要同时检查 `sub` 和 `leaf`。

### 手机周边（`Elettronica > Telefonia`）

```
Cellulari e accessori          ← 190 条
Custodie e cover
Pellicole e protezioni
Caricabatterie e cavi
Supporti e staffe
Telefoni cellulari e smartphone
Accessori per Tablet PC
```

### 电池

`Elettronica > Pile, caricabatterie e accessori > Pile monouso / Pile ricaricabili`

> 注意：**充电器不删**，只删电池本体。

### 虚拟商品

`carta regalo`、`gift card`、`codice digitale`、`codice download`、
`Robux`、`V-Bucks`、`abbonamento a`、`licenza digitale`

> ⚠ `ricarica` 是**三义词**（充电/补充装/充值），必须配排除表（见 pitfall 23）

### 游戏软件（`Videogiochi`）

删软件（`Nintendo Switch` / `PS5` / `Xbox Series` 标题），
保留配件（`accessori` / `custodia` / `pellicola` / `controller`）。

---

## 四、价格门槛

**€9**（约合 $10，按 1 EUR ≈ 1.1 USD）

| 市场 | 门槛 | 依据 |
|---|---|---|
| 美站 | $10 | 原始设定 |
| 日本站 | ¥1500 | $10 × 150 |
| 意大利站 | €9 | $10 ÷ 1.1 |

> 门槛应按「该市场最低客单价的合理下限」调整，
> 不是机械汇率换算。意大利站 €9 删除 582 条（11.6%）。

---

## 五、实施顺序

```
1  虚拟商品       ← 最先，避免被价格筛选误伤
2  游戏软件
3  整类剔除       ← Alimentari / Moda / Informatica
4  宠物食品与药品
5  保健品
6  药品与医疗
6b 隐形眼镜护理液
6c 化工名称兜底
7  化工（按叶子）
8  日化耗材
9  电池
10 手机周边
11 手表周边
12 低客单价       ← 最后
```

**为什么虚拟商品要最先判**：
预付卡有「面值」会通过价格筛选，若放在后面会被误归为「低客单价」。

---

## 六、实测效果

| 步骤 | 删除数 | 占比 |
|---|---|---|
| 整类剔除 | 856 | 17.1% |
| 美妆 | 770 | 15.4% |
| 低客单价 | 582 | 11.6% |
| 保健品 | 322 | 6.4% |
| 药品 | 224 | 4.5% |
| 化工 | 214 | 4.3% |
| 手机周边 | 190 | 3.8% |
| 日化 | 132 | 2.6% |
| 食品（宠物） | 89 | 1.8% |
| 电池 | 31 | 0.6% |
| 游戏软件 | 16 | 0.3% |
| 虚拟商品 | 4 | 0.1% |
| **合计** | **3430** | **68.6%** |

保留 1570 条（31.4%），5 星 157 个（10%）。

**数值守恒**：删 8,810,560 + 保留 3,475,903 = 12,286,463 ✓

---

## 七、三版迭代记录（v1 → v3）

| 版本 | 虚拟商品 | 保健品误判 | 化工误判 | 保留 |
|---|---|---|---|---|
| v1 | **139**（全错） | 37 条化妆品 | 50+ 条卫生纸 | 1534 |
| v2 | 4 | 9 | 0 | 1591 |
| v3 | 4 | 4 | 0 | **1570** |

**v1 → v2 的修复**：
- `ricarica` 加排除表
- 保健品弃用 `vitamina` 关键词
- 化工按叶子分流纸品

**v2 → v3 的修复**：
- 加 `Cura della vista` 判隐形眼镜护理液
- 加杀虫剂/水垢剂名称兜底（散落在 `Giardino`、`Bagno` 下）

---

## 八、推广到其他欧洲市场

| 语言 | 需改的部分 | 可复用的部分 |
|---|---|---|
| 西语（Amazon.es） | 类目词表 + `recarga` 排除表 | 四层模型、阈值逻辑、判定顺序 |
| 法语（Amazon.fr） | 类目词表 + `recharge` 排除表 | 同上 |
| 德语（Amazon.de） | 类目词表 + `Aufladen` 排除表 | 同上 |

**通用规律**（三个市场都一样）：

1. **保健品位置不固定** —— 意大利在 `Salute`，日本在 `Beauty`，美站在 `Health`
2. **清洁剂与纸品常混组** —— 必须按叶子分流
3. **剃须/口腔/美发都是「硬件保留、耗材删除」**
4. **虚拟商品要最先判** —— 否则被价格筛选吃掉
5. **充电类词汇是虚拟商品判定的头号陷阱**
