"""Generate ensemble learning framework diagram for academic paper."""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(1, 1, figsize=(10, 14), dpi=300)
ax.set_xlim(0, 10)
ax.set_ylim(0, 16)
ax.axis('off')

def draw_box(ax, xy, w, h, text, color='#E8F0FE', edgecolor='#4285F4', fontsize=10, bold=False):
    box = FancyBboxPatch(xy, w, h, boxstyle="round,pad=0.15",
                          facecolor=color, edgecolor=edgecolor, linewidth=1.5)
    ax.add_patch(box)
    weight = 'bold' if bold else 'normal'
    ax.text(xy[0] + w/2, xy[1] + h/2, text, ha='center', va='center',
            fontsize=fontsize, fontweight=weight, color='#1a1a1a')

def draw_arrow(ax, start, end, color='#555555'):
    ax.annotate('', xy=end, xytext=start,
                arrowprops=dict(arrowstyle='->', color=color, lw=1.5))

# Layer 1: Input
draw_box(ax, (2.5, 14.2), 5, 0.8, '融合指纹特征向量 $\\mathbf{F}$ (12维)\nFused Fingerprint Feature Vector (12-D)',
         color='#FFF3E0', edgecolor='#FB8C00', fontsize=9, bold=True)

# Arrows from input to classifiers
cx = 5.0
for xc in [1.2, 3.4, 5.6, 7.8]:
    draw_arrow(ax, (cx, 14.2), (xc + 0.8, 13.1))

# Layer 2: Four classifiers
clf_colors = ['#E3F2FD', '#E8F5E9', '#FFF3E0', '#F3E5F5']
clf_edges  = ['#1976D2', '#388E3C', '#F57C00', '#7B1FA2']
clf_names  = ['SVM\n支持向量机', 'RF\n随机森林', 'LDA\n线性判别分析', 'KNN\nK近邻']
clf_x = [0.4, 2.6, 4.8, 7.0]

for i, (x, name) in enumerate(zip(clf_x, clf_names)):
    draw_box(ax, (x, 12.2), 2.2, 0.9, name, color=clf_colors[i], edgecolor=clf_edges[i], fontsize=9, bold=True)

# Arrows from classifiers to posterior prob
for x in clf_x:
    draw_arrow(ax, (x + 1.1, 12.2), (x + 1.1, 11.3))

# Layer 3: Posterior probabilities
for i, x in enumerate(clf_x):
    draw_box(ax, (x, 10.4), 2.2, 0.9, f'后验概率 $\\mathbf{{p}}_{i+1}$\nPosterior Prob.',
             color='#F5F5F5', edgecolor='#9E9E9E', fontsize=8)

# Arrows to weighting block
for x in clf_x:
    draw_arrow(ax, (x + 1.1, 10.4), (cx, 9.5))

# Layer 4: Weighting
draw_box(ax, (1.8, 8.5), 6.4, 1.0,
         '静态权重 + 动态置信度 联合加权\nStatic Weight + Dynamic Confidence Joint Weighting',
         color='#E8EAF6', edgecolor='#3F51B5', fontsize=10, bold=True)

draw_arrow(ax, (cx, 8.5), (cx, 7.6))

# Layer 5: Fusion
draw_box(ax, (2.5, 6.7), 5, 0.8, '加权概率融合\nWeighted Probability Fusion',
         color='#E0F7FA', edgecolor='#00838F', fontsize=10, bold=True)

draw_arrow(ax, (cx, 6.7), (cx, 5.9))

# Layer 6: Decision diamond
diamond_cx, diamond_cy = 5.0, 5.0
diamond_w, diamond_h = 2.0, 0.9
diamond = plt.Polygon([
    [diamond_cx, diamond_cy + diamond_h],
    [diamond_cx + diamond_w, diamond_cy],
    [diamond_cx, diamond_cy - diamond_h],
    [diamond_cx - diamond_w, diamond_cy]
], closed=True, facecolor='#FFF9C4', edgecolor='#F9A825', linewidth=2)
ax.add_patch(diamond)
ax.text(diamond_cx, diamond_cy, '双阈值拒识判决\nDual-Threshold\nRejection',
        ha='center', va='center', fontsize=8, fontweight='bold', color='#1a1a1a')

# Output arrows
# Left: reject
draw_arrow(ax, (diamond_cx - diamond_w, diamond_cy), (1.0, diamond_cy))
draw_box(ax, (0.0, diamond_cy - 0.45), 1.8, 0.9, '拒识\n(未知设备)\nReject\n(Unknown)',
         color='#FFEBEE', edgecolor='#D32F2F', fontsize=8, bold=True)
ax.text(1.6, diamond_cy + 0.25, '$p_{max} < T_1$\nor $\\Delta p < T_2$', fontsize=7, color='#D32F2F')

# Right: accept
draw_arrow(ax, (diamond_cx + diamond_w, diamond_cy), (8.2, diamond_cy))
draw_box(ax, (8.2, diamond_cy - 0.45), 1.8, 0.9, '设备身份 $\\hat{c}$\nDevice ID',
         color='#E8F5E9', edgecolor='#2E7D32', fontsize=9, bold=True)
ax.text(7.2, diamond_cy + 0.25, '$p_{max} \\geq T_1$\nand $\\Delta p \\geq T_2$', fontsize=7, color='#2E7D32')

# Title
ax.text(5, 15.5, '集成学习加权融合分类框架', ha='center', va='center', fontsize=14, fontweight='bold')
ax.text(5, 15.1, 'Ensemble Learning Weighted Fusion Classification Framework', ha='center', va='center', fontsize=10, color='#555555')

plt.tight_layout()
plt.savefig(r'C:\Users\21398\Desktop\sophomore\SRTP\code\dual_frame_cfo_identification\results\fig_ensemble_framework.png',
            dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
plt.close()
print("Figure 1 saved successfully.")
