"""生成拒识率对比实验结果 Word 文档（含8台+18台未知设备对比）"""

import os, json
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

RESULTS_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(RESULTS_DIR, "拒识率对比实验结果.docx")

with open(os.path.join(RESULTS_DIR, "results_rejection_test.json"), "r", encoding="utf-8") as f:
    data = json.load(f)

doc = Document()
section = doc.sections[0]
section.page_width = Cm(21.0)
section.page_height = Cm(29.7)
section.left_margin = Cm(2.5)
section.right_margin = Cm(2.5)
section.top_margin = Cm(2.5)
section.bottom_margin = Cm(2.5)

HEADER_COLOR = "2E5A3E"
KNOWN_COLOR = "E8F5E9"
UNKNOWN_8_COLOR = "FFF3E0"
UNKNOWN_18_COLOR = "FCE4EC"


def set_cell_shading(cell, color):
    tc = cell._element.get_or_add_tcPr()
    shd = tc.makeelement(qn('w:shd'), {
        qn('w:val'): 'clear', qn('w:color'): 'auto', qn('w:fill'): color})
    tc.append(shd)


def set_cell(cell, text, bold=False, font_size=Pt(10), color=None,
             alignment=WD_ALIGN_PARAGRAPH.CENTER):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = alignment
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(str(text))
    run.font.name = "宋体"
    run._element.rPr.rFonts.set(qn('w:eastAsia'), "宋体")
    run.font.size = font_size
    run.font.bold = bold
    if color:
        run.font.color.rgb = color


def add_para(text, bold=False, font_size=Pt(12), alignment=WD_ALIGN_PARAGRAPH.LEFT,
             space_after=Pt(6)):
    p = doc.add_paragraph()
    p.alignment = alignment
    p.paragraph_format.space_after = space_after
    p.paragraph_format.line_spacing = Pt(22)
    run = p.add_run(text)
    run.font.name = "宋体"
    run._element.rPr.rFonts.set(qn('w:eastAsia'), "宋体")
    run.font.size = font_size
    run.font.bold = bold
    return p


def add_heading(text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.name = "黑体"
        run._element.rPr.rFonts.set(qn('w:eastAsia'), "黑体")
    return h


def add_caption(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(text)
    run.font.name = "宋体"
    run._element.rPr.rFonts.set(qn('w:eastAsia'), "宋体")
    run.font.size = Pt(10.5)
    run.font.bold = True


def pct(v):
    return f"{v*100:.2f}%"


# ===== 标题 =====
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
title.paragraph_format.space_after = Pt(16)
run = title.add_run("拒识率对比实验结果")
run.font.name = "黑体"
run._element.rPr.rFonts.set(qn('w:eastAsia'), "黑体")
run.font.size = Pt(18)
run.font.bold = True

# ===== 一、实验设计 =====
add_heading("一、实验设计", level=1)

add_para("本实验旨在评估集成学习框架的双阈值拒识机制对已知设备和未知设备的区分能力。"
         "实验设计三个对比场景：")
add_para("场景A（已知设备）：以30台设备（数据集C，Heltec CubeCell, SX1262芯片）训练集成模型，"
         "用同源30台设备的同天/跨天测试集进行测试。已知设备的拒识率应尽可能低。")
add_para("场景B（未知设备-8台）：相同30台设备模型，"
         "用8台不同设备（数据集A，Heltec LoRa32, SX1262芯片）测试。"
         "这8台设备从未出现在训练集中，与训练设备芯片相同（SX1262）但型号不同。")
add_para("场景C（未知设备-18台）：相同30台设备模型，"
         "用18台不同设备（数据集B，RA01-SC, LLCC68芯片）测试。"
         "这18台设备芯片型号（LLCC68）与训练设备（SX1262）完全不同。")

add_para("拒识判决规则（双阈值机制）：对集成后验概率进行两项检验——"
         "(i) 绝对置信条件：最大后验概率 P_(1) >= tau_1；"
         "(ii) 相对置信条件：类间置信差 Delta_p = P_(1) - P_(2) >= tau_2。"
         "两条件均满足时输出设备身份，否则判定为未知设备予以拒识。"
         "默认参数：tau_1 = 0.3，tau_2 = 0.1。")

# ===== 二、核心对比结果 =====
add_heading("二、核心对比结果（默认阈值）", level=1)

rows_data = [
    ("known_30dev_same_day",     "同天", "已知(30台)", KNOWN_COLOR),
    ("known_30dev_another_day",  "跨天", "已知(30台)", KNOWN_COLOR),
    ("unknown_8dev_same_day",    "同天", "未知(8台,SX1262)", UNKNOWN_8_COLOR),
    ("unknown_8dev_another_day", "跨天", "未知(8台,SX1262)", UNKNOWN_8_COLOR),
    ("unknown_18dev_same_day",   "同天", "未知(18台,LLCC68)", UNKNOWN_18_COLOR),
    ("unknown_18dev_another_day","跨天", "未知(18台,LLCC68)", UNKNOWN_18_COLOR),
]

t = doc.add_table(rows=len(rows_data) + 1, cols=7)
t.alignment = WD_TABLE_ALIGNMENT.CENTER
t.style = "Table Grid"

headers = ["测试场景", "设备类型", "样本数", "拒识数", "拒识率", "平均置信度", "关键指标"]
for j, h in enumerate(headers):
    cell = t.rows[0].cells[j]
    set_cell_shading(cell, HEADER_COLOR)
    set_cell(cell, h, bold=True, font_size=Pt(9), color=RGBColor(0xFF, 0xFF, 0xFF))

for i, (key, scene, dev_type, bg) in enumerate(rows_data):
    r = data[key]
    row = t.rows[i + 1]
    is_unknown = "unknown" in key

    for c in row.cells:
        set_cell_shading(c, bg)

    set_cell(row.cells[0], scene, font_size=Pt(9))
    set_cell(row.cells[1], dev_type, font_size=Pt(9), bold=True)
    set_cell(row.cells[2], str(r["n_total"]), font_size=Pt(9))
    set_cell(row.cells[3], str(r["n_rejected"]), font_size=Pt(9))
    set_cell(row.cells[4], pct(r["rejection_rate"]), font_size=Pt(9), bold=True)
    set_cell(row.cells[5], f"{r['mean_confidence']:.4f}", font_size=Pt(9))

    if is_unknown:
        far = r.get("false_accept_rate", 1 - r["rejection_rate"])
        set_cell(row.cells[6], f"误接受率={pct(far)}", font_size=Pt(9),
                 color=RGBColor(0xC6, 0x28, 0x28))
    else:
        set_cell(row.cells[6], f"接受准确率={r['acc_on_accepted']}", font_size=Pt(9),
                 color=RGBColor(0x2E, 0x7D, 0x32))

add_caption("表1  已知设备与未知设备拒识率对比（tau_1=0.3, tau_2=0.1）")

add_para("")
add_para("结果分析：")
add_para("(1) 已知设备（30台）拒识率极低（同天0.34%、跨天0.68%），"
         "被接受样本的识别准确率达99.18%/98.04%，说明模型对已注册设备置信度高。")
add_para("(2) 未知8台设备（同芯片SX1262、不同型号）拒识率为13.77%（同天）和12.05%（跨天），"
         "误接受率约86%~88%。虽然芯片相同，但不同型号的硬件差异使少部分样本"
         "落入低置信区域被拒识。")
add_para("(3) 未知18台设备（不同芯片LLCC68）拒识率几乎为零——同天0.00%、跨天仅0.22%，"
         "误接受率接近100%。这一看似反常的结果说明：LLCC68芯片设备的CFO和相位特征"
         "恰好落入了SX1262训练设备的某些类别的高置信区域，"
         "模型以极高的确定性将其错误分类为已知设备，反而比同芯片的8台设备更难被拒识。")
add_para("(4) 这一现象揭示了基于后验概率的拒识机制的根本局限：当未知设备的特征分布"
         "恰好与某个已知类别高度重叠时，模型的置信度反而很高，双阈值机制完全失效。"
         "不同芯片类型并不意味着特征空间中的距离更远。")

# ===== 三、置信度分布对比 =====
add_heading("三、置信度分布对比", level=1)

t2 = doc.add_table(rows=len(rows_data) + 1, cols=4)
t2.alignment = WD_TABLE_ALIGNMENT.CENTER
t2.style = "Table Grid"

h2 = ["测试场景", "整体平均置信度", "被拒识样本平均置信度", "被接受样本平均置信度"]
for j, h in enumerate(h2):
    cell = t2.rows[0].cells[j]
    set_cell_shading(cell, "4472C4")
    set_cell(cell, h, bold=True, font_size=Pt(9), color=RGBColor(0xFF, 0xFF, 0xFF))

for i, (key, scene, dev_type, bg) in enumerate(rows_data):
    r = data[key]
    row = t2.rows[i + 1]
    set_cell(row.cells[0], f"{dev_type} {scene}", font_size=Pt(9))
    set_cell(row.cells[1], f"{r['mean_confidence']:.4f}", font_size=Pt(9))
    rej_val = r['mean_conf_rejected'] if r['mean_conf_rejected'] != "N/A" else "N/A"
    acc_val = r['mean_conf_accepted'] if r['mean_conf_accepted'] != "N/A" else "N/A"
    set_cell(row.cells[2], f"{rej_val}", font_size=Pt(9))
    set_cell(row.cells[3], f"{acc_val}", font_size=Pt(9))

add_caption("表2  各场景置信度分布统计")

add_para("")
add_para("18台未知设备的平均置信度甚至高于8台未知设备，进一步证实其特征与已知类别的重叠程度更高。"
         "8台设备的平均置信度（0.72）介于已知设备（0.94）和随机水平之间，尚存一定的区分空间；"
         "而18台设备的置信度分布与已知设备更为接近，使得基于阈值的拒识策略几乎无法生效。")

# ===== 四、阈值敏感性分析 =====
add_heading("四、阈值敏感性分析", level=1)

add_para("在7组不同阈值配置下，分别测试已知设备（30台）、未知8台和未知18台的同天拒识率：")

sens = data["sensitivity"]
t3 = doc.add_table(rows=len(sens) + 1, cols=8)
t3.alignment = WD_TABLE_ALIGNMENT.CENTER
t3.style = "Table Grid"

h3 = ["阈值配置", "tau_1", "tau_2", "已知拒识率", "已知接受准确率",
      "未知8台拒识率", "未知18台拒识率", "18台误接受率"]
for j, h in enumerate(h3):
    cell = t3.rows[0].cells[j]
    set_cell_shading(cell, HEADER_COLOR)
    set_cell(cell, h, bold=True, font_size=Pt(8), color=RGBColor(0xFF, 0xFF, 0xFF))

for i, s in enumerate(sens):
    row = t3.rows[i + 1]
    is_default = (s["name"] == "默认")
    if is_default:
        for c in row.cells:
            set_cell_shading(c, "E3F2FD")

    set_cell(row.cells[0], s["name"], font_size=Pt(9), bold=is_default)
    set_cell(row.cells[1], f"{s['tau_1']:.2f}", font_size=Pt(9))
    set_cell(row.cells[2], f"{s['tau_2']:.2f}", font_size=Pt(9))
    set_cell(row.cells[3], pct(s["known_rejection_rate"]), font_size=Pt(9))
    set_cell(row.cells[4], f"{s['known_acc_accepted']}", font_size=Pt(9))
    set_cell(row.cells[5], pct(s["unknown_8dev_rejection_rate"]), font_size=Pt(9), bold=True)
    set_cell(row.cells[6], pct(s["unknown_18dev_rejection_rate"]), font_size=Pt(9), bold=True)
    far_18 = s["unknown_18dev_false_accept"]
    set_cell(row.cells[7], pct(far_18), font_size=Pt(9),
             color=RGBColor(0xC6, 0x28, 0x28) if far_18 > 0.5 else RGBColor(0x2E, 0x7D, 0x32))

add_caption("表3  不同阈值配置下的三组设备拒识性能对比（同天测试）")

add_para("")
add_para("趋势分析：")
add_para("(1) 8台未知设备（同芯片）的拒识率随阈值提升从5.18%增至42.96%，改善空间有限。")
add_para("(2) 18台未知设备（异芯片）在tau_1<0.4时拒识率始终为0%，"
         "仅在极严格阈值（0.70/0.30）下才达到25.49%。"
         "这说明该批设备的特征被模型高度匹配到已有类别。")
add_para("(3) 两组未知设备的拒识难度呈现反直觉的差异：芯片不同的18台设备反而比同芯片的8台设备更难拒识，"
         "说明芯片差异并不直接对应特征空间的距离，射频指纹的特征分布受多种硬件因素共同影响。")

# ===== 五、结论与改进方向 =====
add_heading("五、结论与改进方向", level=1)

add_para("(1) 双阈值拒识机制对已知设备表现优异（拒识率<1%），不影响正常识别性能。")
add_para("(2) 对未知设备的拒识能力严重不足：同芯片8台设备误接受率86%，异芯片18台设备误接受率接近100%。"
         "后验概率拒识机制的根本局限在于——当未知设备特征恰好落入已知类别的高密度区域时，"
         "无论如何调整阈值均无法有效拒识。")
add_para("(3) 18台设备（LLCC68芯片）的CFO范围（-1~-6 Hz）与30台设备（SX1262芯片）的CFO分布"
         "在归一化后可能存在高度重叠，导致模型无法通过现有特征区分已知与未知设备。")
add_para("改进方向：")
add_para("  - 引入基于特征空间距离的拒识策略（马氏距离、LOF异常检测），"
         "    在后验概率之外增加特征分布一致性检验。")
add_para("  - 构建设备指纹嵌入空间（如Triplet Loss或ArcFace），"
         "    使已知设备在嵌入空间中形成紧致聚类，未知设备自然落在聚类之外。")
add_para("  - 引入开集识别算法（如OpenMax），替代闭集softmax概率作为拒识依据。")
add_para("  - 增加设备特有的辅助特征（如IQ不平衡系数、功放非线性特征），"
         "    增强不同芯片类型设备在特征空间中的可区分性。")

doc.save(OUTPUT_PATH)
print(f"已生成: {OUTPUT_PATH}")
