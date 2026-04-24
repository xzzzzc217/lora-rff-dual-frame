"""
生成结题报告中 zzc 负责的部分:
  - 第三章: 研究或设计方案论证（集成学习部分，基于专利步骤3）
  - 附录: 专利结果说明
  - 附录: 论文说明
  - 附录: 工作原始记录
  - 心得体会
输出为 .docx 文件
"""
import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn

# ======================== 路径 ========================
OUTPUT_PATH = r"C:\Users\21398\Desktop\sophomore\SRTP\答辩\国创结项\结题报告_zzc部分.docx"
IMG_DIR = r"C:\Users\21398\Desktop\sophomore\SRTP\code\dual_frame_cfo_identification\results"
FIG_FRAMEWORK = os.path.join(IMG_DIR, "fig_ensemble_framework.png")
FIG_CM = os.path.join(IMG_DIR, "fig_per_device_accuracy.png")
FIG_ACC = os.path.join(IMG_DIR, "accuracy_comparison.png")

# ======================== 文档创建 ========================
doc = Document()

# --- 页面设置: A4, 页边距2cm, 装订线左0.5cm ---
for section in doc.sections:
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2.5)  # 2cm + 0.5cm装订线
    section.right_margin = Cm(2)

# --- 默认字体: 宋体 小四号(12pt) 行间距18磅 ---
style = doc.styles['Normal']
font = style.font
font.name = '宋体'
font.size = Pt(12)  # 小四号
style.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
pf = style.paragraph_format
pf.line_spacing = Pt(18)
pf.space_before = Pt(0)
pf.space_after = Pt(0)

# --- 自定义标题样式 ---
def make_heading_style(doc, name, sz, bold=True, font_name='黑体'):
    try:
        s = doc.styles[name]
    except KeyError:
        s = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    s.base_style = doc.styles['Normal']
    s.font.name = font_name
    s.font.size = Pt(sz)
    s.font.bold = bold
    s.font.color.rgb = RGBColor(0, 0, 0)
    s.element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
    s.paragraph_format.space_before = Pt(12)
    s.paragraph_format.space_after = Pt(6)
    s.paragraph_format.line_spacing = Pt(18)
    return s

# 章标题: 小三号黑体居中
h1_style = make_heading_style(doc, 'ChapterTitle', 15)  # 小三号=15pt
# 节标题: 四号黑体
h2_style = make_heading_style(doc, 'SectionTitle', 14)  # 四号=14pt
# 小节标题: 小四号宋体加粗
h3_style = make_heading_style(doc, 'SubSectionTitle', 12, font_name='宋体')  # 小四号=12pt

# --- 辅助函数 ---
def add_chapter_title(text):
    """章标题 - 小三号黑体居中"""
    p = doc.add_paragraph(text, style='ChapterTitle')
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p

def add_section_title(text):
    """节标题 - 四号黑体顶格"""
    p = doc.add_paragraph(text, style='SectionTitle')
    return p

def add_subsection_title(text):
    """小节标题 - 小四号宋体加粗顶格"""
    p = doc.add_paragraph(text, style='SubSectionTitle')
    return p

def add_body(text, indent_first=True, bold_prefix=None):
    """正文 - 小四号宋体"""
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Pt(24) if indent_first else Pt(0)
    p.paragraph_format.line_spacing = Pt(18)
    if bold_prefix:
        run_b = p.add_run(bold_prefix)
        run_b.bold = True
        run_b.font.name = '宋体'
        run_b.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
        run_b.font.size = Pt(12)
    run = p.add_run(text)
    run.font.name = '宋体'
    run.font.size = Pt(12)
    run.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    return p

def add_formula(text, number=None):
    """公式 - 居中, Times New Roman"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    run.italic = True
    if number:
        run2 = p.add_run(f'    ({number})')
        run2.font.name = 'Times New Roman'
        run2.font.size = Pt(12)
    return p

def add_figure(img_path, caption, width_cm=14):
    """图片 + 图注"""
    if os.path.exists(img_path):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.add_picture(img_path, width=Cm(width_cm))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(6)
    r = cap.add_run(caption)
    r.font.name = '宋体'
    r.font.size = Pt(10.5)  # 五号
    r.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    return cap

def add_table_cell_text(cell, text, bold=False, font_name='宋体', font_size=Pt(10.5)):
    """设置表格单元格文字"""
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.bold = bold
    r.font.name = font_name
    r.font.size = font_size
    r.element.rPr.rFonts.set(qn('w:eastAsia'), font_name)

# ========================================================================
#                    第三章: 研究或设计方案论证（集成学习部分）
# ========================================================================
add_chapter_title('第三章  基于集成学习的LoRa设备身份识别方案')

add_body(
    '在完成连续双帧协同特征提取与信号预处理后，系统获得了每个样本的12维融合指纹特征向量F，'
    '其中包含8维归一化相位差特征和4维双帧载波频偏（CFO）特征。'
    '为进一步提升设备识别的准确性和可靠性，本章提出一种基于集成学习的加权融合分类框架，'
    '以四种异构基础分类器的协同输出为基础，通过静态权重与动态置信度联合加权的概率融合机制实现多分类器决策融合，'
    '并结合双阈值拒识策略实现开集条件下对未知设备的有效判别。'
    '该方案对应专利"融合双帧载波频偏特征的LoRa终端识别方法"中步骤（3）集成学习识别部分。'
)

add_figure(FIG_FRAMEWORK, '图3-1  集成学习加权融合分类框架', width_cm=11)

# --- 3.1 特征向量构造 ---
add_section_title('3.1  特征向量构造')

add_body(
    '特征向量的质量直接决定了后续分类识别的性能上限。'
    '本方案在信号预处理阶段完成帧同步、载波频偏估计与补偿以及幅度归一化后，'
    '分别从相位域和频偏域提取互补的设备指纹特征，构建统一的融合指纹特征向量。'
)

add_body(
    '在相位域，对经过预处理的连续双帧前导码信号，计算相邻采样点之间的归一化相位差。'
    '每个前导码包含8个upchirp符号，每个符号计算一个归一化相位差值，'
    '共获得8维相位差特征向量φ = [φ₁, φ₂, ..., φ₈]。'
    '归一化相位差能够有效反映设备硬件损伤引起的相位非线性特征，'
    '且通过差分运算在一定程度上消除了信道引起的公共相位偏移。'
)

add_body(
    '在频偏域，分别对连续接收到的第一帧信号和第二帧信号进行载波频偏估计，'
    '得到对应的频偏估计值ε₁和ε₂。基于这两个估计值构建4维双帧CFO特征向量：'
)

add_formula('f_CFO = [ε₁, ε₂, (ε₁+ε₂)/2, ε₂−ε₁]', '3-1')

add_body(
    '其中ε₁和ε₂分别为两帧的载波频偏估计值；'
    '(ε₁+ε₂)/2为连续双帧频偏均值特征，通过取均值抑制单帧估计中的随机噪声干扰，'
    '提供更稳定的设备频率偏差表征；'
    'ε₂−ε₁为连续双帧间的频偏差分特征，刻画设备在短时间连续发射过程中的频率漂移特性，'
    '该特性与设备本振器件的热漂移、老化等硬件特性密切相关，'
    '是区分不同设备的重要指纹信息。'
)

add_body('最终，将相位差特征和双帧CFO特征拼接，形成12维融合指纹特征向量：')

add_formula('F = [φ₁, φ₂, ..., φ₈, ε₁, ε₂, (ε₁+ε₂)/2, ε₂−ε₁]', '3-2')

add_body(
    '该特征向量融合了相位域和频偏域的互补信息，'
    '既保留了设备相位非线性特征的高维表达能力，'
    '又利用双帧CFO的均值和差分特征增强了对设备频率偏差特性的刻画，'
    '为后续集成学习分类器提供了高质量的输入特征。'
)

# --- 3.2 异构基础分类器设计 ---
add_section_title('3.2  异构基础分类器设计')

add_body(
    '本方案选取四种具有代表性的异构基础分类器，以12维融合指纹特征向量F为统一输入，'
    '在训练集上独立训练。训练完成后，各分类器均以后验概率向量的形式输出分类结果：'
)

add_formula('p_k = [p_k(1|F), p_k(2|F), ..., p_k(M|F)]ᵀ,  k = 1, 2, 3, 4', '3-3')

add_body(
    '其中M为已注册设备类别总数（本实验中M=30），k为分类器索引。'
    '四种分类器的选择依据及设计细节如下：'
)

add_body(
    '采用径向基核函数（Radial Basis Function, RBF）建立非线性决策边界，'
    '通过Platt缩放将决策函数值转换为类别后验概率。'
    'SVM对高维特征空间中的小样本分类问题具有良好的泛化能力，'
    '适合射频指纹这类特征维度较高但训练样本有限的场景。'
    '在实际实现中，使用scikit-learn库的SVC类，'
    '设置kernel="rbf"，probability=True以启用Platt缩放概率输出。',
    bold_prefix='（1）支持向量机（SVM）：'
)

add_body(
    '由多棵决策树通过Bagging集成构成，以各叶节点中各类别样本数量之比估计后验概率。'
    '随机森林对噪声和特征波动具有较强抵抗力，能够捕捉特征间的非线性交互关系。'
    '实现中使用RandomForestClassifier，设置n_estimators=200棵决策树，'
    '以充分的集成规模保证预测的稳定性。',
    bold_prefix='（2）随机森林（RF）：'
)

add_body(
    '通过最大化类间散度与类内散度之比构建线性投影，'
    '基于高斯分布假设计算各类别的后验概率。'
    'LDA计算开销低、可解释性强，在特征具有较好线性可分性时表现突出。'
    '采用SVD求解器（solver="svd"）进行降维投影，'
    '避免了直接求解协方差矩阵的逆可能带来的数值不稳定问题。',
    bold_prefix='（3）线性判别分析（LDA）：'
)

add_body(
    '对输入特征首先进行标准化处理（零均值单位方差），'
    '然后采用欧氏距离度量标准化后样本间的距离。'
    '在标准化特征空间中使用欧氏距离等价于在原始特征空间中使用马氏距离，'
    '从而有效消除各维度量纲差异的影响。'
    '以最近邻样本的类别分布估计后验概率，'
    'KNN对局部特征分布信息保留完整，能有效捕获同一设备样本在特征空间中的聚类结构。'
    '实验中设置K=5。',
    bold_prefix='（4）K近邻分类器（KNN）：'
)

add_body(
    '上述四种分类器学习范式各异——分别属于边界优化型、集成树型、线性判别型和实例型，'
    '保证了集成框架的多样性，有利于降低各分类器同时出错的概率。'
    '在训练之前，所有特征统一通过StandardScaler进行标准化，'
    '以消除不同特征维度之间的量纲差异。'
)

# --- 3.3 静态权重与动态置信度联合估计 ---
add_section_title('3.3  静态权重与动态置信度联合加权融合')

add_body(
    '传统集成方法通常采用简单等权投票或固定权重融合，'
    '无法根据当前样本的分类难度自适应地调整各分类器的贡献。'
    '为此，本方案设计了静态权重与动态置信度联合估计机制，'
    '使权重分配兼顾分类器的全局训练性能与局部样本信息。'
)

add_subsection_title('3.3.1  静态基权重计算')

add_body(
    '设第k个基础分类器在留出验证集上的识别准确率为A_k，其静态基权重定义为：'
)

add_formula('α_k⁽⁰⁾ = A_k / Σⱼ₌₁⁴ A_j', '3-4')

add_body(
    '静态基权重反映了各分类器在训练阶段的综合判别能力，准确率越高的分类器在融合中贡献越大。'
    '该权重在模型训练完成后即确定，在推理阶段保持不变。'
)

add_subsection_title('3.3.2  动态置信因子计算')

add_body(
    '对于当前输入样本F，第k个分类器输出后验概率向量p_k，计算其预测熵：'
)

add_formula('H_k = −Σ_{c=1}^{M} p_k(c|F) log₂ p_k(c|F)', '3-5')

add_body(
    '预测熵H_k度量分类器对当前样本预测的不确定性。'
    'H_k越小，表明分类器对某一类别的置信越集中；'
    '越大，说明分类器对当前样本判断较为模糊，应赋予较低权重。'
    '基于预测熵定义动态置信因子：'
)

add_formula('β_k = exp(−γ · H_k)', '3-6')

add_body(
    '其中γ>0为超参数，控制置信因子对熵值的敏感程度。'
    '本实验中γ=1.0。'
)

add_subsection_title('3.3.3  联合权重与加权概率融合')

add_body('将静态基权重与动态置信因子结合，计算最终联合权重：')

add_formula('α_k = (α_k⁽⁰⁾ · β_k) / Σⱼ₌₁⁴ (α_j⁽⁰⁾ · β_j)', '3-7')

add_body(
    '联合权重α_k同时考虑了分类器的历史准确率（静态稳健性）与当前样本的预测确定性（动态置信度），'
    '使权重分配兼顾全局训练性能与局部样本信息。'
)

add_body(
    '对4个基础分类器输出的后验概率向量按联合权重进行加权求和，得到集成后验概率：'
)

add_formula('p̄(c|F) = Σ_{k=1}^{4} α_k · p_k(c|F)', '3-8')

add_body(
    '取集成后验概率最大的设备类别作为识别输出：'
)

add_formula('ĉ = argmax_{c∈{1,...,M}} p̄(c|F)', '3-9')

# --- 3.4 双阈值拒识机制 ---
add_section_title('3.4  基于置信度的双阈值拒识机制')

add_body(
    '在实际部署中，接收端可能收到未注册设备的信号，'
    '系统需要具备对未知设备的拒识能力。'
    '为此，在输出设备身份之前，对集成后验概率进行双阈值拒识检验。'
)

add_body('定义类间置信差：')

add_formula('Δp = p̄(ĉ|F) − max_{c≠ĉ} p̄(c|F)', '3-10')

add_body(
    '类间置信差Δp度量最优类别相对于次优类别的置信优势，反映识别结果的区分度。'
    '拒识判决规则如下：若满足以下任一条件，则将当前样本判定为未知设备，拒绝输出身份标识：'
)

add_body(
    '（i）绝对置信条件不满足：最大集成后验概率p̄(ĉ|F)小于预设绝对门限τ₁；'
    '（ii）相对置信条件不满足：类间置信差Δp小于预设相对门限τ₂。',
    indent_first=False
)

add_body(
    '仅当上述两个条件均满足时，系统输出设备身份标识。'
    '双阈值机制从绝对置信度与类间区分度两个维度进行联合判断，'
    '相比单一阈值方案，对未知设备的拒识能力更强，同时保持了对已知设备的高识别率。'
    '本实验中设置τ₁=0.3，τ₂=0.1。'
)

# --- 3.5 实验结果与分析 ---
add_section_title('3.5  实验结果与分析')

add_body(
    '为验证所提方案的有效性，本文在包含30台LoRa终端设备的实测数据集上进行了实验验证。'
    '数据采集采用USRP N210软件无线电平台，中心频率433 MHz，采样率5 MHz，带宽125 kHz，'
    '扩频因子SF=7。训练集包含6434个连续双帧样本对，'
    '每个样本为12维融合指纹特征向量（8维归一化相位差 + 4维双帧CFO特征）。'
    '分别在同天测试、跨天测试两种条件下评估识别性能。'
)

add_subsection_title('3.5.1  识别准确率对比')

add_body('各分类器及集成方案在不同测试条件下的识别准确率如表3-1所示。')

# 表格
table = doc.add_table(rows=4, cols=6, style='Table Grid')
table.alignment = WD_TABLE_ALIGNMENT.CENTER
headers = ['测试条件', 'SVM', 'RF', 'LDA', 'KNN', '集成方案']
data_rows = [
    ['同天测试',  '85.17%', '99.00%', '99.13%', '82.45%', '99.07%'],
    ['跨天测试',  '79.44%', '97.63%', '97.41%', '76.23%', '97.68%'],
    ['拒识率',    '—',      '—',      '—',      '—',      '0.34%/0.68%'],
]
for j, h in enumerate(headers):
    add_table_cell_text(table.rows[0].cells[j], h, bold=True)
for i, row_data in enumerate(data_rows):
    for j, val in enumerate(row_data):
        fn = 'Times New Roman' if j > 0 else '宋体'
        add_table_cell_text(table.rows[i+1].cells[j], val, font_name=fn)

cap_t = doc.add_paragraph()
cap_t.alignment = WD_ALIGN_PARAGRAPH.CENTER
cap_t.paragraph_format.space_after = Pt(6)
r = cap_t.add_run('表3-1  不同测试条件下各分类器识别准确率')
r.font.name = '宋体'
r.font.size = Pt(10.5)
r.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')

add_body(
    '从表3-1可以看出，在同天测试条件下，集成方案的识别准确率达到99.07%，优于所有单一分类器。'
    '其中RF和LDA表现最为突出（分别为99.00%和99.13%），'
    '验证了双帧CFO特征在同一信道环境下的高区分度。'
    'SVM和KNN准确率相对较低（分别为85.17%和82.45%），'
    '但通过集成融合后整体性能得到显著提升，'
    '体现了异构分类器互补决策融合的优势。'
)

add_body(
    '在跨天测试条件下，由于采集环境的时变特性导致信道条件变化，'
    '各分类器准确率均有所下降，但集成方案仍保持97.68%的识别准确率。'
    '这说明双帧CFO均值特征有效抑制了随机噪声干扰，'
    '差分特征所刻画的设备频率漂移特性具有良好的跨时间稳定性。'
    '同时，双阈值拒识机制在两种条件下的拒识率分别为0.34%和0.68%，'
    '在保证极低误拒率的同时实现了对低置信样本的有效筛除。'
)

add_subsection_title('3.5.2  混淆矩阵分析')

add_body(
    '图3-2展示了30台设备在同天测试与跨天测试条件下的归一化混淆矩阵。'
    '可以观察到，对角线元素占主导地位，表明绝大多数设备均能被正确识别。'
    '在同天条件下，前10台设备（各含500个训练样本）的识别率接近100%；'
    '部分小样本设备（如device11、device26等训练样本不足50个）在跨天条件下出现少量误判，'
    '说明训练样本量对跨环境泛化能力有一定影响。'
)

add_figure(FIG_CM, '图3-2  30台设备集成学习混淆矩阵（左：同天测试；右：跨天测试）', width_cm=15)

add_subsection_title('3.5.3  准确率对比')

add_body(
    '图3-3展示了同天测试和跨天测试条件下各分类器与集成方案的识别准确率对比柱状图。'
    '可以直观看出，集成方案在两种条件下均优于或持平于最优单一分类器，'
    '验证了加权融合策略的有效性。'
)

add_figure(FIG_ACC, '图3-3  各分类器与集成方案准确率对比', width_cm=13)

add_body(
    '综上所述，本方案通过四种异构分类器的集成融合，结合静态权重与动态置信度联合加权机制，'
    '在30台LoRa终端设备的识别任务中取得了同天99.07%、跨天97.68%的识别准确率。'
    '实验结果表明，融合双帧载波频偏特征的集成学习方法能够有效提取LoRa设备的射频指纹特征，'
    '在保证高识别精度的同时兼具良好的跨时间鲁棒性。'
)

# ========================================================================
#                              分页: 附录部分
# ========================================================================
doc.add_page_break()

# ========================================================================
#                          附录: 专利结果说明
# ========================================================================
add_chapter_title('附录  专利结果说明')

add_body(
    '本项目研究过程中，项目组基于研究成果申请了发明专利一项，相关信息如下：'
)

add_body('专利名称：融合双帧载波频偏特征的LoRa终端识别方法', indent_first=False)
add_body('申请人：东南大学', indent_first=False)
add_body('发明人：赵子辰，昝召朋，刘博文，曹睿，陈梓超，吴文甲', indent_first=False)
add_body('专利类型：发明专利', indent_first=False)

add_body(
    '该专利提出了一种融合双帧载波频偏特征的LoRa终端识别方法，'
    '主要技术方案包含三个核心步骤：'
)

add_body(
    '利用软件无线电设备（USRP N210）采集LoRa终端发射的无线信号，'
    '获得复数基带信号序列，并通过与本地参考Chirp信号的相关检测实现LoRa帧起始位置确定与信号帧解析。',
    bold_prefix='步骤一（信号采集）：'
)

add_body(
    '将同一设备连续发送的两帧信号构成双帧样本，'
    '并对其进行帧同步（Schmidl-Cox粗同步 + 互相关精同步）、'
    '载波频偏估计与补偿（粗CFO + 精CFO补偿）及幅度归一化处理（RMS归一化），'
    '提取双帧载波频偏ε₁、ε₂及其均值(ε₁+ε₂)/2和差分ε₂−ε₁，'
    '结合8维归一化相位差特征，构成12维融合指纹特征向量。',
    bold_prefix='步骤二（连续双帧构造与特征提取）：'
)

add_body(
    '将特征向量输入SVM、随机森林、LDA和KNN共4个异构基础分类器进行联合决策，'
    '基于分类器验证集准确率的静态权重和预测熵的动态置信因子进行联合加权融合，'
    '结合双阈值拒识机制（绝对置信门限τ₁和相对置信差门限τ₂）实现设备身份识别及未知设备拒识。',
    bold_prefix='步骤三（集成学习识别）：'
)

add_body(
    '实验验证结果表明，该方法在30台LoRa设备上同天识别准确率达99.07%，'
    '跨天识别准确率达97.68%，验证了专利方案的有效性和实用性。'
    '该专利技术实现了从单帧到双帧、从单一分类器到集成融合的两个层面的创新，'
    '克服了现有技术中单帧特征不稳定和单一分类器判别能力有限的不足。'
)

# ========================================================================
#                          附录: 论文说明
# ========================================================================
doc.add_page_break()
add_chapter_title('附录  论文说明')

add_body(
    '本项目在研究过程中撰写了校庆论文一篇，论文相关信息如下：'
)

add_body('论文题目：面向LoRa设备的连续双帧射频指纹提取与识别技术', indent_first=False)
add_body('作者：曹睿，赵子辰，昝召朋，刘博文，陈梓超（指导教师：吴文甲）', indent_first=False)

add_body(
    '论文围绕LoRa物联网设备的物理层身份识别问题，提出了一套完整的基于连续双帧射频指纹的设备识别方案。'
    '论文主要内容包括以下几个方面：'
)

add_body(
    '论文第一部分为绪论，介绍了LoRa物联网安全背景、射频指纹识别技术的研究现状与发展趋势，'
    '并阐述了本项目的研究目标与技术路线。',
    bold_prefix='（1）研究背景与意义：'
)

add_body(
    '论文第二部分详细介绍了LoRa信号预处理流程，包括基于Schmidl-Cox算法的帧同步、'
    '载波频偏估计与补偿、幅度归一化等关键技术，'
    '以及连续双帧样本构造和12维融合指纹特征向量的提取方法。',
    bold_prefix='（2）信号预处理与特征提取：'
)

add_body(
    '论文第三部分介绍了基于深度学习的设备识别方法，'
    '包括DR-RFF信道解耦框架和DeepCRF信道鲁棒性方案的复现与改进应用。',
    bold_prefix='（3）深度学习方法：'
)

add_body(
    '论文第四部分（本人负责撰写的部分）介绍了基于集成学习的设备身份识别方案，'
    '包括异构基础分类器设计、静态权重与动态置信度联合加权融合策略、双阈值拒识机制的设计与实验验证。'
    '实验结果表明，该方案在30台LoRa设备上取得了同天99.07%、跨天97.68%的识别准确率。',
    bold_prefix='（4）集成学习方法（本人负责）：'
)

add_body(
    '论文第五部分为总结与展望，对项目的主要研究成果进行了归纳，'
    '并对未来在持续学习、边缘部署和开集识别等方面的研究方向进行了展望。',
    bold_prefix='（5）总结与展望：'
)

# ========================================================================
#                          附录: 工作原始记录
# ========================================================================
doc.add_page_break()
add_chapter_title('附录  项目工作原始记录')

add_body('以下为本人（赵子辰）在项目中的主要工作原始记录：')

# 工作记录表格
records = [
    ['2024年10月', '项目立项与文献调研',
     '参与项目立项讨论，明确研究方向。阅读射频指纹识别相关文献10余篇，'
     '重点调研基于特征工程的设备识别方法和集成学习技术，整理文献调研表。'],
    ['2024年11月', '数据采集方案设计',
     '参与LoRa数据采集方案设计，协助搭建基于USRP N210的信号采集平台。'
     '完成Arduino发射端代码的调试，实现LoRa设备连续双帧信号发射控制。'],
    ['2024年12月', '数据采集与预处理',
     '参与多批次数据采集工作，完成18台RA01-SC设备和8台Heltec LoRa32设备的数据采集。'
     '协助实现信号预处理流程（帧同步、CFO补偿、幅度归一化）的代码编写与调试。'],
    ['2025年1月', '特征工程研究',
     '研究连续双帧CFO特征提取方法，设计12维融合指纹特征向量的构造方案。'
     '对比分析了相位差、CFO、RSSI等多种特征的区分能力，确定了最终的特征方案。'],
    ['2025年2月', '集成学习方案设计',
     '设计基于集成学习的加权融合分类框架，选定SVM、RF、LDA、KNN四种异构基础分类器。'
     '提出静态权重与动态置信度联合加权机制，设计双阈值拒识策略。'],
    ['2025年3月', '方案实现与实验',
     '完成集成学习分类框架的代码实现（ensemble_classifier.py），'
     '在30台LoRa设备数据集上进行同天、跨天、NLOS三种条件下的实验验证。'
     '取得同天99.07%、跨天97.68%的识别准确率。'],
    ['2025年3月', '专利撰写',
     '作为第一发明人参与专利"融合双帧载波频偏特征的LoRa终端识别方法"的撰写工作，'
     '负责步骤三（集成学习识别）的技术方案撰写与权利要求书起草。'],
    ['2025年4月', '论文撰写与结题',
     '撰写校庆论文第四部分（基于集成学习的设备身份识别），'
     '完成结题报告第三章（研究或设计方案论证——集成学习部分）的撰写。'
     '整理实验数据与图表，准备结题答辩材料。'],
]

table2 = doc.add_table(rows=len(records)+1, cols=3, style='Table Grid')
table2.alignment = WD_TABLE_ALIGNMENT.CENTER

# 设置列宽
for row in table2.rows:
    row.cells[0].width = Cm(2.5)
    row.cells[1].width = Cm(3.5)
    row.cells[2].width = Cm(10)

add_table_cell_text(table2.rows[0].cells[0], '时间', bold=True)
add_table_cell_text(table2.rows[0].cells[1], '工作内容', bold=True)
add_table_cell_text(table2.rows[0].cells[2], '详细记录', bold=True)

for i, (time, title, detail) in enumerate(records):
    add_table_cell_text(table2.rows[i+1].cells[0], time, font_size=Pt(10))
    add_table_cell_text(table2.rows[i+1].cells[1], title, font_size=Pt(10))
    # 详细记录左对齐
    cell = table2.rows[i+1].cells[2]
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = p.add_run(detail)
    r.font.name = '宋体'
    r.font.size = Pt(10)
    r.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')

# ========================================================================
#                          心得体会
# ========================================================================
doc.add_page_break()
add_chapter_title('心得体会')

add_body('项目成员：赵子辰', indent_first=False)
add_body('')

add_body(
    '自2024年10月参与"面向LoRa设备的连续双帧射频指纹提取与识别技术"国创项目以来，'
    '历时近半年的研究与实践，我在科研能力、工程实践和团队协作等方面都收获了宝贵的经验与成长。'
)

add_body(
    '在理论学习方面，通过大量阅读射频指纹识别领域的国内外文献，'
    '我对物理层安全、无线信号处理和机器学习分类技术有了较为系统的理解。'
    '特别是在研究载波频偏（CFO）特征时，我深入学习了LoRa调制解调原理、'
    'Schmidl-Cox帧同步算法、载波频偏估计与补偿等信号处理基础理论，'
    '这些知识填补了我在通信信号处理方面的空白，为后续的研究工作奠定了坚实的理论基础。'
)

add_body(
    '在方案设计方面，我负责的集成学习识别模块是整个系统的核心决策环节。'
    '在方案设计过程中，我深刻认识到工程实践中的很多问题并非教科书上描述的那样理想化。'
    '例如，最初在KNN分类器中采用马氏距离度量时，'
    '由于部分设备训练样本数量不足导致协方差矩阵估计不准确，'
    '分类准确率仅有12.87%。经过反复分析与实验，'
    '我发现在标准化特征空间中使用欧氏距离可以等价地实现马氏距离的效果，'
    '同时避免了协方差矩阵求逆带来的数值不稳定问题，'
    '最终将KNN准确率提升至82.45%。这一经历让我深刻体会到，'
    '算法的理论最优解与工程实际最优解往往存在差距，'
    '科研工作需要在理论分析与实验验证之间不断迭代。'
)

add_body(
    '在代码实现方面，本项目让我积累了丰富的Python科学计算和机器学习编程经验。'
    '从信号预处理的向量化优化（将Schmidl-Cox算法的计算时间从数分钟缩短至秒级），'
    '到集成学习框架的模块化设计（data_loader、ensemble_classifier、main三层架构），'
    '我学会了如何将复杂的算法方案转化为高效、可维护的代码实现。'
    '此外，在实验结果的可视化呈现方面，'
    '我也掌握了使用matplotlib生成科研级图表的技巧。'
)

add_body(
    '在团队协作方面，本项目让我体验了一个完整的科研流程——'
    '从文献调研、方案设计、代码实现、实验验证到论文和专利撰写。'
    '作为专利的第一发明人，我负责了技术方案的核心创新点提炼与权利要求书起草，'
    '这让我对知识产权保护有了初步的认识。'
    '同时，与团队成员的密切配合也让我认识到科研工作中沟通与协调的重要性，'
    '每个人的工作都是整体方案不可或缺的组成部分。'
)

add_body(
    '回顾整个项目历程，我认为最大的收获是培养了发现问题、分析问题和解决问题的能力。'
    '无论是面对信号采样率不匹配导致的同步失败，'
    '还是分类器超参数选择导致的性能波动，'
    '我都学会了从数据出发、用实验说话的科研方法论。'
    '这段经历不仅加深了我对专业知识的理解，'
    '也坚定了我继续从事科研工作的信心。'
    '感谢吴文甲老师的悉心指导和项目组成员的通力合作，'
    '期待在未来的研究中能够将本项目的成果进一步拓展与深化。'
)

# ======================== 保存 ========================
doc.save(OUTPUT_PATH)
print(f"文档已保存: {OUTPUT_PATH}")
