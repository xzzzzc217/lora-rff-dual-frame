"""
融合双帧载波频偏特征的LoRa终端识别方法 - 主实验脚本

实验内容:
  1. 训练集训练集成学习分类器
  2. 在三种测试条件下评估:
     - 同天测试 (same_day)
     - 不同天测试 (another_day)
     - 非视距测试 (nlos)
  3. 输出30设备混淆矩阵 + 各条件准确率表
"""

import numpy as np
import os
import sys
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import ConfusionMatrixDisplay, classification_report

# 本地模块
sys.path.insert(0, os.path.dirname(__file__))
from data_loader import load_all_splits, NUM_DEVICES, FEATURE_NAMES
from ensemble_classifier import DualFrameCFOEnsemble

# ======================== 配置 ========================
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ======================== 绘图: 混淆矩阵 ========================

def plot_confusion_matrix(cm: np.ndarray, title: str, save_path: str,
                          normalize: bool = True):
    """绘制 30x30 混淆矩阵"""
    labels = [f"D{i+1}" for i in range(cm.shape[0])]

    if normalize:
        row_sums = cm.sum(axis=1, keepdims=True)
        cm_plot = np.divide(cm, row_sums,
                            out=np.zeros_like(cm, dtype=float),
                            where=row_sums != 0)
    else:
        cm_plot = cm.astype(float)

    fig, ax = plt.subplots(figsize=(18, 15))
    im = ax.imshow(cm_plot, interpolation="nearest", cmap="Blues",
                   vmin=0, vmax=1 if normalize else cm_plot.max())
    ax.set_title(title, fontsize=16, pad=15)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax.set_xticks(np.arange(len(labels)))
    ax.set_yticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=90, fontsize=7)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Predicted Device", fontsize=12)
    ax.set_ylabel("True Device", fontsize=12)

    # 在格子中标注数值 (只标非零)
    for i in range(cm_plot.shape[0]):
        for j in range(cm_plot.shape[1]):
            val = cm_plot[i, j]
            if val > 0.005:
                color = "white" if val > 0.5 else "black"
                text = f"{val:.0%}" if normalize else f"{int(val)}"
                ax.text(j, i, text, ha="center", va="center",
                        fontsize=5, color=color)

    plt.tight_layout()
    plt.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  混淆矩阵已保存: {save_path}")


# ======================== 绘图: 准确率对比柱状图 ========================

def plot_accuracy_comparison(results: dict, save_path: str):
    """绘制各条件 + 各分类器准确率对比"""
    conditions = list(results.keys())
    clf_names = ["SVM", "RF", "LDA", "KNN", "Ensemble"]

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(conditions))
    width = 0.15

    for i, clf in enumerate(clf_names):
        key = f"acc_{clf}" if clf != "Ensemble" else "acc_ensemble"
        accs = [results[c].get(key, 0) for c in conditions]
        bars = ax.bar(x + i * width, accs, width, label=clf, alpha=0.85)
        for bar, acc in zip(bars, accs):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                    f"{acc:.1%}", ha="center", va="bottom", fontsize=7)

    ax.set_xlabel("Test Condition", fontsize=12)
    ax.set_ylabel("Accuracy", fontsize=12)
    ax.set_title("Classification Accuracy under Different Conditions", fontsize=14)
    ax.set_xticks(x + width * 2)
    ax.set_xticklabels([
        "Same Day", "Another Day", "NLOS"
    ][:len(conditions)])
    ax.set_ylim(0, 1.15)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  准确率对比图已保存: {save_path}")


# ======================== 主函数 ========================

def main():
    print("=" * 70)
    print("  融合双帧载波频偏特征的LoRa终端识别方法 - 集成学习实验")
    print("=" * 70)

    # 1. 加载数据
    print("\n[1] 加载数据...")
    data = load_all_splits()
    X_train, y_train = data["train"]

    print(f"\n训练集特征维度: {X_train.shape[1]} 维")
    print(f"  特征: {FEATURE_NAMES}")

    # 2. 训练集成分类器
    print("\n[2] 训练集成分类器...")
    model = DualFrameCFOEnsemble(
        gamma=1.0,        # 动态置信度衰减
        tau_1=0.3,        # 绝对置信门限
        tau_2=0.1,        # 相对置信差门限
        n_neighbors=5,    # KNN的K
        n_estimators=200, # RF树数
        svm_C=10.0,       # SVM正则化
        random_state=42,
    )
    model.fit(X_train, y_train, val_ratio=0.2)

    # 3. 在各条件下评估
    print("\n[3] 评估各测试条件...")
    test_splits = {
        "same_day":    "Same-Day Test",
        "another_day": "Another-Day Test (Cross-day)",
        "nlos":        "NLOS Test",
    }

    all_results = {}

    for split_key, description in test_splits.items():
        X_test, y_test = data[split_key]
        print(f"\n{'─' * 50}")
        print(f"  {description}: {len(X_test)} 样本")
        print(f"{'─' * 50}")

        result = model.evaluate(X_test, y_test, description=description)
        all_results[split_key] = result

        # 打印结果
        print(f"  各分类器准确率:")
        for name in ["SVM", "RF", "LDA", "KNN"]:
            print(f"    {name:4s}: {result[f'acc_{name}']:.4f}")
        print(f"    集成 : {result['acc_ensemble']:.4f}")
        print(f"  拒识结果: 接受={result['n_accepted']}, "
              f"拒识={result['n_rejected']}, "
              f"接受样本准确率={result['acc_accepted']:.4f}, "
              f"拒识率={result['rejection_rate']:.2%}")

        # 混淆矩阵
        cm = result["confusion_matrix"]
        plot_confusion_matrix(
            cm, f"Confusion Matrix - {description}",
            os.path.join(OUTPUT_DIR, f"cm_{split_key}.png"),
            normalize=True
        )

    # 4. 准确率对比图 (只保留同天和跨天)
    print("\n[4] 生成准确率对比图...")
    bar_results = {k: v for k, v in all_results.items() if k != "nlos"}
    plot_accuracy_comparison(
        bar_results,
        os.path.join(OUTPUT_DIR, "accuracy_comparison.png")
    )

    # 5. 汇总报告
    print("\n" + "=" * 70)
    print("  实验结果汇总")
    print("=" * 70)

    header = f"{'Condition':20s} | {'SVM':8s} | {'RF':8s} | {'LDA':8s} | {'KNN':8s} | {'Ensemble':8s} | {'Reject%':8s}"
    print(header)
    print("-" * len(header))
    for split_key, description in test_splits.items():
        r = all_results[split_key]
        line = (f"{description:20s} | "
                f"{r['acc_SVM']:7.2%} | "
                f"{r['acc_RF']:7.2%} | "
                f"{r['acc_LDA']:7.2%} | "
                f"{r['acc_KNN']:7.2%} | "
                f"{r['acc_ensemble']:7.2%} | "
                f"{r['rejection_rate']:7.2%}")
        print(line)
    print()

    # 保存数值结果
    report = {}
    for k, r in all_results.items():
        report[k] = {key: val for key, val in r.items()
                     if key != "confusion_matrix"}
    with open(os.path.join(OUTPUT_DIR, "results.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"数值结果已保存: {os.path.join(OUTPUT_DIR, 'results.json')}")

    print("\n实验完成!")


if __name__ == "__main__":
    main()
