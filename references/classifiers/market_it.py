# -*- coding: utf-8 -*-
"""意大利站清洗分类器 v2 —— 修复 4 个缺陷

诊断发现：
  1 虚拟商品 139 条，其中 134 条误命中 'ricarica'
    'ricarica' 在意大利语是「充电/补充装」：
      · Batterie ricaricabili = 充电电池
      · Ricarica Rapida = 快充
      · Ricarica Universale = 补充装
    真正的虚拟商品是 'carta regalo' / 'gift card' / 'codice download'
  2 保健品 331 条，37 条名称判定误判
    'vitamin' / 'vitamina' 在化妆品名里也出现：
      · Crema Viso con Vitamina C（维C面霜）
      · Siero Vitamina C（维C精华）
    应只按类目判定，或用「Integratore」等专有词
  3 化工 241 条，含 Carta igienica（卫生纸）等日化
    因为 'Pulizia e cura della casa' 整组被划为化工，
    但该组下同时含纸品（Carta igienica / Rotoli）→ 需按 leaf 分流
  4 类目路径含空行（部分产品只有一行类目），latin_segs 已能处理
"""
import re

EXCLUDE_TOP = {
    "Alimentari e cura della casa": "食品与家居护理，合规/保质期风险",
    "Moda": "服装配饰，退货率高、SKU 爆炸",
    "Informatica": "电脑周边，品牌垄断+专利风险",
}

# ★ 修复1：虚拟商品只保留真正的虚拟品关键词
VIRTUAL_KW = [
    "gift card", "carta regalo", "buono regalo",
    "codice download", "codice digitale", "prodotto digitale",
    "abbonamento a", "PSN card", "Xbox Live Gold",
    "Nintendo eShop card", "Robux", "V-Bucks",
    "licenza digitale", "e-book", "audiolibro",
]
# 明确排除（避免误伤实物）
VIRTUAL_EXCLUDE = ["ricarica", "ricaricabile", "batteria", "batterie",
                   "power bank", "cavo", "caricatore", "alimentatore"]

GAME_SOFTWARE_KW = [
    "Nintendo Switch", "PS5", "PS4", "Xbox Series", "Xbox One",
    "videogioco",
]
GAME_HARDWARE_KW = ["accessori", "custodia", "pellicola", "cover",
                    "controller", "joy-con", "cavo", "supporto"]

# ★ 修复2：保健品只用类目判定 + 专有词
SUPP_TOP = {"Vitamine, minerali e integratori",
            "Alimentazione e nutrizione"}
SUPP_LEAVES = {
    "Vitamine, minerali e integratori", "Singole vitamine",
    "Multivitamine e minerali", "Singoli minerali", "Aminoacidi",
    "Enzimi", "Integratori di sostanze e preparati vegetali",
    "Integratori", "Proteine", "Frullati e sostituti dei pasti",
    "Alimentazione e nutrizione", "Integratori alimentari",
}
# 只在名称里出现这些词才判定（不用 vitamin/vitamina）
SUPP_NAME_KW = ["integratore", "integratore alimentare", "supplemento",
                "proteine in polvere", "collagene", "omega 3"]

DRUG_LEAVES = {
    "Prodotti per la medicazione", "Forniture sanitarie e igieniche",
    "Dispositivi medici", "Farmaci", "Primo soccorso",
    "Lenti a contatto", "Contatti e occhiali",
    "Erotismo e contraccezione", "Prodotti per la cura e la salute",
    "Test e strumenti di misura", "Prodotti e apparecchiature mediche",
    "Cura della vista", "Soluzione per lenti a contatto",
}

# 隐形眼镜护理液（名称判定）
CONTACT_KW = ["soluzione unica", "soluzione per lenti", "liquido per lenti",
              "detergente per lenti"]

BEAUTY_TOP = {"Bellezza"}
BEAUTY_LEAVES = {
    "Cura dei capelli", "Cura della pelle", "Trucco", "Bagno e corpo",
    "Viso", "Occhi", "Labbra", "Colore", "Shampoo e balsamo",
    "Prodotti per styling capelli", "Strumenti per lo styling",
    "Trattamenti corpo ed esfolianti", "Detergenti per il corpo",
    "Igiene intima", "Deodoranti e antitraspiranti",
    "Profumazione ambiente", "Profumi", "Capelli",
    "Unghie", "Manicure e pedicure", "Rasatura manuale",
    "Creme e lozioni", "Corpo", "Pulizia del viso", "Sieri",
    "Maschere viso", "Contorno occhi", "Make up",
}
BEAUTY_KEEP_HARDWARE = {
    "Rasoi elettrici", "Rasoi manuali e lame", "Rasoi", "Lame",
    "Asciugacapelli", "Piastre per capelli", "Arricciacapelli",
    "Spazzolini da denti elettrici", "Tagliacapelli", "Epilatori",
    "Spazzole e pettini", "Forbici", "Set manicure", "Spazzole",
}

ORAL_LEAVES = {"Igiene dentale", "Dentifrici", "Collutori",
               "Filo interdentale", "Sbiancamento dei denti"}
ORAL_KEEP_HARDWARE = {"Spazzolini da denti e accessori",
                      "Spazzolini da denti", "Spazzolini elettrici",
                      "Idropulsori", "Scovolini", "Spazzolini interdentali"}

# ★ 修复3：化工只按 leaf 精确判定，不用整组
CHEM_LEAVES = {
    "Prodotti per il bucato", "Detergenti per la casa",
    "Prodotti per lavare le stoviglie", "Ammorbidenti",
    "Candeggina", "Anticalcare", "Disinfettanti",
    "Insetticidi", "Antiparassitari", "Deumidificatori",
    "Vernici e pitture", "Detersivi", "Detersivo lavatrice",
    "Detersivo lavastoviglie", "Additivi", "Brillantanti",
    "Profumatori", "Deodoranti per ambienti",
    "Insetticidi e repellenti", "Esca per insetti", "Gel scarafaggi",
    "Filtri anticalcare", "Anticalcare per doccia",
    "Trattamento acque", "Decalcificante",
}

# 名称判定：杀虫剂/水垢剂
CHEM_NAME_KW = ["insetticida", "scarafaggi", "anticalcare", "decalk",
                "decalcificante", "disinfettante", "candeggina"]
# 化工组内要保留的纸品（划归日化）
CHEM_TO_DAILY = {
    "Carta igienica", "Rotoli di carta igienica", "Prodotti di carta",
    "Carta", "Tovaglioli e fazzoletti", "Salviette umidificate",
    "Panni e spugne", "Sacchi e sacchetti per la spazzatura",
}

DAILY_LEAVES = {
    "Prodotti di carta", "Carta", "Sacchi e sacchetti per la spazzatura",
    "Tovaglioli e fazzoletti", "Rotoli di carta igienica",
    "Carta igienica", "Panni e spugne", "Pannolini",
    "Salviette umidificate", "Salviette detergenti",
}

BATTERY_LEAVES = {"Pile monouso", "Pile ricaricabili", "Pile", "Batterie"}

PHONE_TOP = {"Telefonia"}
PHONE_LEAVES = {
    "Cellulari e accessori", "Accessori per cellulari",
    "Custodie e cover", "Pellicole e protezioni",
    "Caricabatterie e cavi", "Supporti e staffe",
    "Telefoni cellulari e smartphone", "SIM e schede",
    "Accessori per Tablet PC",
}

WATCH_LEAVES = {"Accessori per smartwatch", "Cinturini per orologi",
                "Smartwatch", "Cinturini"}

PET_TOP = {"Prodotti per animali domestici"}
PET_FOOD_LEAVES = {"Cibo", "Snack", "Crocchette", "Umido",
                   "Alimentazione", "Premi"}
PET_DRUG_LEAVES = {"Salute e cura", "Farmaci", "Antiparassitari"}

MIN_PRICE_EUR = 9.0


def latin_segs(at):
    for line in (at or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        has_latin = any("a" <= c.lower() <= "z" for c in line)
        has_cjk = any("\u3040" <= c <= "\u30ff" or "\u4e00" <= c <= "\u9fff"
                      for c in line)
        if has_latin and not has_cjk:
            return [s.strip() for s in line.split("->") if s.strip()]
    return []


def classify(txt, nums, price=None):
    hits = []
    name = (txt.get("产品名称", "") or txt.get("C", "") or "").lower()
    at = txt.get("类目路径", "") or txt.get("AN", "")
    segs = latin_segs(at)

    if not segs:
        al = (txt.get("大类", "") or txt.get("AM", "")).strip()
        if al and al != "--":
            segs = [al]
        else:
            ap = (txt.get("小类", "") or txt.get("AQ", "")).strip()
            ap = re.sub(r"^#\d+[,，.:：]?\s*", "", ap)
            if ap and ap != "--":
                segs = [ap]

    top = segs[0] if segs else ""
    sub = segs[1] if len(segs) >= 2 else ""
    leaf = segs[2] if len(segs) >= 3 else ""

    # 0 虚拟商品（先排除实物误伤）
    if any(k in name for k in VIRTUAL_KW):
        if not any(k in name for k in VIRTUAL_EXCLUDE):
            hits.append(("虚拟商品", f"非实物：{name[:30]}"))
            return hits

    # 0b 游戏软件
    if top == "Videogiochi":
        if not any(k in name for k in GAME_HARDWARE_KW):
            hits.append(("游戏软件", "Videogiochi：游戏内容无开发价值"))
            return hits

    # 1 整类剔除
    if top in EXCLUDE_TOP:
        hits.append(("整类剔除", f"{top}：{EXCLUDE_TOP[top]}"))
        return hits

    # 2 宠物食品与药品
    if top in PET_TOP:
        if sub in PET_FOOD_LEAVES or leaf in PET_FOOD_LEAVES:
            hits.append(("食品", f"{top} > {sub} > {leaf}：宠物食品"))
            return hits
        if sub in PET_DRUG_LEAVES or leaf in PET_DRUG_LEAVES:
            hits.append(("药品", f"{top} > {sub} > {leaf}：宠物医疗"))
            return hits
        if any(k in name for k in ("cibo", "crocchette", "umido",
                                    "snack per", "farmaco")):
            cat = ("食品" if any(k in name for k in
                                ("cibo", "crocchette", "umido"))
                   else "药品")
            hits.append((cat, f"{top}：名称判定"))
            return hits

    # 3 保健品（★ 修复：不再用 vitamin 关键词）
    if sub in SUPP_TOP or sub in SUPP_LEAVES or leaf in SUPP_LEAVES:
        hits.append(("保健品", f"{top} > {sub} > {leaf}"))
        return hits
    if any(k in name for k in SUPP_NAME_KW):
        hits.append(("保健品", f"名称判定：{name[:30]}"))
        return hits

    # 4 药品与医疗
    if sub in DRUG_LEAVES or leaf in DRUG_LEAVES:
        hits.append(("药品", f"{top} > {sub} > {leaf}"))
        return hits

    # 5 口腔护理（先判硬件）
    if sub in ORAL_LEAVES or leaf in ORAL_LEAVES:
        if leaf in ORAL_KEEP_HARDWARE or sub in ORAL_KEEP_HARDWARE:
            pass
        else:
            hits.append(("日化", f"{top} > {sub} > {leaf}：口腔耗材"))
            return hits

    # 6 美妆（先判硬件）
    if top in BEAUTY_TOP:
        if leaf in BEAUTY_KEEP_HARDWARE or sub in BEAUTY_KEEP_HARDWARE:
            pass
        else:
            hits.append(("美妆", f"{top} > {sub} > {leaf}"))
            return hits
    if sub in BEAUTY_LEAVES or leaf in BEAUTY_LEAVES:
        if leaf in BEAUTY_KEEP_HARDWARE:
            pass
        else:
            hits.append(("美妆", f"{top} > {sub} > {leaf}"))
            return hits

    # ★ 修复3：化工组内的纸品先划到日化
    if leaf in CHEM_TO_DAILY or sub in CHEM_TO_DAILY:
        hits.append(("日化", f"{top} > {sub} > {leaf}：纸品/耗材"))
        return hits

    # 6b 隐形眼镜护理液
    if "Cura della vista" in sub or any(k in name for k in CONTACT_KW):
        if "occhiali" not in name:
            hits.append(("药品", f"{top} > {sub} > {leaf}：隐形眼镜护理"))
            return hits

    # 6c 化工名称兜底
    if any(k in name for k in CHEM_NAME_KW):
        hits.append(("化工", f"名称判定：{name[:30]}"))
        return hits

    # 7 化工（只按 leaf 判定）
    if leaf in CHEM_LEAVES or sub in CHEM_LEAVES:
        hits.append(("化工", f"{top} > {sub} > {leaf}"))
        return hits

    # 8 日化耗材
    if leaf in DAILY_LEAVES or sub in DAILY_LEAVES:
        hits.append(("日化", f"{top} > {sub} > {leaf}"))
        return hits

    # 9 电池
    if leaf in BATTERY_LEAVES or sub in BATTERY_LEAVES:
        hits.append(("电池", f"{top} > {sub} > {leaf}"))
        return hits

    # 10 手机周边
    if top in PHONE_TOP or sub in PHONE_LEAVES or leaf in PHONE_LEAVES:
        hits.append(("手机周边", f"{top} > {sub} > {leaf}"))
        return hits
    if top == "Informatica" and ("accessori" in (leaf + sub).lower()):
        hits.append(("手机周边", f"{top} > {sub} > {leaf}"))
        return hits

    # 11 手表周边
    if leaf in WATCH_LEAVES or sub in WATCH_LEAVES:
        hits.append(("手表周边", f"{top} > {sub} > {leaf}"))
        return hits

    # 12 低客单价
    if price is not None and price < MIN_PRICE_EUR:
        hits.append(("低客单价", f"价格 €{price:.2f} < €{MIN_PRICE_EUR}"))

    return hits

