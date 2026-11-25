# -*- coding: utf-8 -*-
"""产品机会评分 —— 单元格读取与列定位

关键设计：同时支持两种字符串存储格式
  · inlineStr  字符串直接写在单元格里（Sorftime 原始导出）
  · sharedStrings  字符串存表，单元格只存索引（openpyxl 处理过的文件）

不写死列字母，按表头名称定位（文件加工过列会移位）。
"""
import re
import zipfile


def unescape_xml(s):
    """解码 XML 实体，含数字实体（中文常写成 &#NNNN;）。"""
    if not s:
        return ""
    s = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), s)
    s = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), s)
    return (s.replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&apos;", "'")
             .replace("&amp;", "&"))


class Workbook:
    """统一读取，屏蔽 inlineStr / sharedStrings 差异。"""

    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.names = self.z.namelist()
        self._ss = None

    def close(self):
        self.z.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    @property
    def shared_strings(self):
        if self._ss is None:
            self._ss = []
            if "xl/sharedStrings.xml" in self.names:
                raw = self.z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
                for m in re.finditer(r"<si>(.*?)</si>", raw, re.S):
                    # 拼接 <t> 片段（富文本会有多个 t）
                    parts = re.findall(r"<t[^>]*>(.*?)</t>", m.group(1), re.S)
                    self._ss.append(unescape_xml("".join(parts)))
        return self._ss

    def sheet_xml(self, idx=1):
        part = f"xl/worksheets/sheet{idx}.xml"
        return (self.z.read(part).decode("utf-8", "replace")
                if part in self.names else "")

    # ── 单元格解析
    def text(self, attrs, body):
        """返回单元格文本。"""
        if body is None:
            return ""
        if "inlineStr" in attrs:
            m = re.search(r"<is>.*?<t[^>]*>(.*?)</t>", body, re.S)
            return unescape_xml(m.group(1)) if m else ""
        m = re.search(r"<v>(.*?)</v>", body, re.S)
        if not m:
            return ""
        raw = m.group(1)
        if 't="s"' in attrs:
            try:
                return self.shared_strings[int(raw)]
            except (ValueError, IndexError):
                return ""
        if 't="str"' in attrs:
            return unescape_xml(raw)
        return unescape_xml(raw)

    @staticmethod
    def number(attrs, body):
        if body is None:
            return None
        m = re.search(r"<v>(.*?)</v>", body, re.S)
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None

    @staticmethod
    def iter_rows(xml):
        """产出 (行号, {列字母: (attrs, body)})。"""
        for rm in re.finditer(r'<row r="(\d+)"[^>]*>(.*?)</row>', xml, re.S):
            rn = int(rm.group(1))
            cells = {}
            for cm in re.finditer(
                    r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)',
                    rm.group(2), re.S):
                cells[cm.group(1)] = (cm.group(2), cm.group(3))
            yield rn, cells


# ══════════════ 语义名 -> 表头关键字（按顺序尝试）
SPEC = {
    "序号": ["序号"],
    "产品名称": ["产品名称", "产品名"],
    "ASIN": ["ASIN"],
    "URL": ["URL"],
    "类目路径": ["类目路径", "类目"],
    "大类": ["大类名称", "大类"],
    "小类": ["小类名称", "小类"],
    "月销量": ["Listing月销量", "月销量"],
    "月销额": ["Listing月销额", "月销额"],
    "评价数": ["评价数量", "评价数"],
    "评分": ["评分星级", "评分"],
    "差评率": ["差评率"],
    "毛利率": ["毛利率"],
    "毛利额": ["毛利($)", "毛利额", "毛利"],
    "价格": ["实际价格", "价格"],
    "跟卖数": ["跟卖数量", "跟卖数", "跟卖"],
    "完整度": ["Listing完整度", "完整度"],
    "上架天数": ["ASIN上架时长", "上架时长", "上架天数"],
    "评价增幅": ["评价数量增幅", "评价增幅"],
    "品牌": ["品牌"],
}

REQUIRED = ["类目路径", "月销量", "月销额", "评价数", "评分",
            "差评率", "毛利额", "跟卖数", "完整度", "上架天数"]


def resolve_columns(headers: dict):
    """{列字母: 表头文本} -> ({语义: 列字母}, [缺失的必需项])"""
    norm = {c: unescape_xml(str(t or "")).strip() for c, t in headers.items()}
    mapping, used = {}, set()

    for sem, keys in SPEC.items():
        found = None
        for key in keys:
            kl = key.lower()
            # 完全相等优先
            for col in sorted(norm, key=lambda c: (len(c), c)):
                if col in used or not norm[col]:
                    continue
                if norm[col].lower() == kl:
                    found = col
                    break
            if found:
                break
            # 其次包含
            for col in sorted(norm, key=lambda c: (len(c), c)):
                if col in used or not norm[col]:
                    continue
                if kl in norm[col].lower():
                    found = col
                    break
            if found:
                break
        if found:
            mapping[sem] = found
            used.add(found)

    return mapping, [s for s in REQUIRED if s not in mapping]


def describe(mapping, headers):
    lines = []
    for sem in SPEC:
        if sem in mapping:
            c = mapping[sem]
            lines.append(f"  {sem:<10} -> {c:>3}  {headers.get(c, '')}")
        else:
            tag = "" if sem in REQUIRED else "（可选）"
            lines.append(f"  {sem:<10} -> ---  {tag}")
    return "\n".join(lines)
