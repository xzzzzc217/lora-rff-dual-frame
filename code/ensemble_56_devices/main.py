"""
56台设备集成学习实验主脚本 (v2 - 重新提取数据后)

策略:
  任务 a: 分三批独立训练集成学习模型 (8/18/30台), 各自在自己的特征空间中运行,
         再拼接为56×56的分块混淆矩阵, 给出总体准确率.
  任务 b: 18台设备消融实验. 使用重新提取的 outputcsv18 数据:
         - CFO 来自 frame_info (真实设备频偏 ~-1 到 -6 Hz, 有区分度)
         - 训练集 2745 样本, 同天测试 910, 跨天测试 930
         - 正常 train/test 分割, 无需交换.
"""

import numpy as np
import os
import sys
import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "..", "dual_frame_cfo_identification"))
from ensemble_classifier import DualFrameCFOEnsemble

# ======================== 配置 ========================
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DATA_ROOT = r"C:\Users\21398\Desktop\sophomore\SRTP\data"

rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False


# ======================== 数据加载工具 ========================

def _load_csv_dir(root, subdir, prefix, device_ids):
    """加载一批CSV, 返回 (raw_10col, labels)"""
    split_dir = os.path.join(root, subdir)
    X_list, y_list = [], []
    for idx, dev_id in enumerate(device_ids):
        path = os.path.join(split_dir, f"{prefix}{dev_id}.csv")
        tmp_path = path + ".tmp"
        if os.path.exists(tmp_path):
            path = tmp_path
        elif not os.path.exists(path):
            continue
        df = pd.read_csv(path, header=None)
        if df.shape[1] != 10:
            continue
        X_list.append(df.values.astype(np.float64))
        y_list.append(np.full(len(df), idx, dtype=np.int32))
    if not X_list:
        return np.zeros((0, 10)), np.zeros(0, dtype=np.int32)
    return np.vstack(X_list), np.concatenate(y_list)


def build_features_12d(raw):
    """10列 -> 12维特征"""
    ph = raw[:, 0:8]
    e1, e2 = raw[:, 8:9], raw[:, 9:10]
    return np.hstack([ph, e1, e2, (e1+e2)/2, e2-e1])


def clean_cfo_outliers(raw, threshold=100):
    """将 |CFO| > threshold 的值替换为该列中位数; 再将任何 NaN/Inf 置零"""
    out = raw.copy()
    for col in [8, 9]:
        mask = np.abs(out[:, col]) > threshold
        if mask.any():
            good = out[~mask, col]
            median_val = np.median(good) if len(good) > 0 else 0.0
            out[mask, col] = median_val
    # 安全: 清除残余 NaN / Inf
    out = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
    return out


# ======================== 绘图 ========================

def plot_confusion_matrix(cm, title, save_path, labels=None, normalize=True):
    n = cm.shape[0]
    if labels is None:
        labels = [f"D{i+1}" for i in range(n)]
    if normalize:
        rs = cm.sum(axis=1, keepdims=True)
        cm_p = np.divide(cm, rs, out=np.zeros_like(cm, dtype=float), where=rs != 0)
    else:
        cm_p = cm.astype(float)

    fs = (22, 18) if n > 40 else (18, 15)
    fz = 4 if n > 40 else (5 if n > 20 else 7)
    fig, ax = plt.subplots(figsize=fs)
    im = ax.imshow(cm_p, interpolation="nearest", cmap="Blues", vmin=0,
                   vmax=1 if normalize else cm_p.max())
    ax.set_title(title, fontsize=16, pad=15)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_xticks(np.arange(n)); ax.set_yticks(np.arange(n))
    ax.set_xticklabels(labels, rotation=90, fontsize=fz)
    ax.set_yticklabels(labels, fontsize=fz)
    ax.set_xlabel("Predicted Device", fontsize=12)
    ax.set_ylabel("True Device", fontsize=12)
    plt.tight_layout()
    plt.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"  -> {save_path}")


def plot_accuracy_bars(results, save_path, title=""):
    conditions = list(results.keys())
    clf_names = ["SVM", "RF", "LDA", "KNN", "Ensemble"]
    colors = ['#4C72B0', '#55A868', '#C44E52', '#8172B2', '#CCB974']
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(conditions))
    w = 0.15
    for i, clf in enumerate(clf_names):
        key = f"acc_{clf}" if clf != "Ensemble" else "acc_ensemble"
        accs = [results[c].get(key, 0) for c in conditions]
        bars = ax.bar(x + i*w, accs, w, label=clf, alpha=0.85, color=colors[i])
        for bar, acc in zip(bars, accs):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.005,
                    f"{acc:.1%}", ha="center", va="bottom", fontsize=7)
    cond_map = {"same_day": "Same Day", "another_day": "Another Day"}
    ax.set_xticks(x + w*2)
    ax.set_xticklabels([cond_map.get(c, c) for c in conditions])
    ax.set_xlabel("Test Condition", fontsize=12)
    ax.set_ylabel("Accuracy", fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.set_ylim(0, 1.15); ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  -> {save_path}")


# ========================================================================
#  任务 a: 分三批训练, 组装56×56混淆矩阵
# ========================================================================

# 数据源定义
SOURCES = {
    "8dev": {
        "root": os.path.join(DATA_ROOT, "outputcsv8", "outputcsv8"),
        "ids": ["009","010","011","012","020","021","022","023"],
        "splits": {
            "train": ("train_dataset", "train_data_device_"),
            "same_day": ("test_same_day", "test_same_data_device_"),
            "another_day": ("test_another_day", "test_another_data_device_"),
        },
        "labels": [f"8dev_{d}" for d in ["009","010","011","012","020","021","022","023"]],
    },
    "18dev": {
        "root": os.path.join(DATA_ROOT, "outputcsv18", "outputcsv18"),
        "ids": [str(i) for i in range(1, 19)],
        "splits": {
            "train": ("train_dataset", "train_data_device_"),
            "same_day": ("test_same_day", "test_same_data_device_"),
            "another_day": ("test_another_day", "test_another_data_device_"),
        },
        "labels": [f"18dev_{i}" for i in range(1, 19)],
    },
    "30dev": {
        "root": os.path.join(DATA_ROOT, "output_csv"),
        "ids": [str(i) for i in range(1, 31)],
        "splits": {
            "train": ("train_dataset", "train_data_device"),
            "same_day": ("test_same_day", "test_same_data_device"),
            "another_day": ("test_another_day", "test_another_data_device"),
        },
        "labels": [f"30dev_{i}" for i in range(1, 31)],
    },
}


def _train_and_eval_one_source(src_name, src_cfg, test_key):
    """对单个数据源训练集成模型并评估, 返回 (result_dict, confusion_matrix)"""
    root = src_cfg["root"]
    ids = src_cfg["ids"]
    sp = src_cfg["splits"]

    # 加载
    raw_tr, y_tr = _load_csv_dir(root, *sp["train"], ids)
    raw_te, y_te = _load_csv_dir(root, *sp[test_key], ids)

    X_tr = build_features_12d(raw_tr)
    X_te = build_features_12d(raw_te)

    n_dev = len(ids)
    print(f"\n  [{src_name}] {test_key}: 训练{len(X_tr)}, 测试{len(X_te)}, "
          f"设备{n_dev}")

    model = DualFrameCFOEnsemble(
        gamma=1.0, tau_1=0.3, tau_2=0.1,
        n_neighbors=min(5, max(1, len(X_tr)//n_dev - 1)),
        n_estimators=200, svm_C=10.0, random_state=42,
    )
    model.fit(X_tr, y_tr, val_ratio=0.2)
    result = model.evaluate(X_te, y_te, description=f"{src_name}_{test_key}")

    for name in ["SVM", "RF", "LDA", "KNN"]:
        print(f"    {name:4s}: {result[f'acc_{name}']:.2%}")
    print(f"    集成 : {result['acc_ensemble']:.2%}")

    return result


def task_a():
    print("\n" + "="*70)
    print("  任务 a: 56台设备集成学习 (分三批独立训练)")
    print("="*70)

    all_labels = []
    for s in ["8dev", "18dev", "30dev"]:
        all_labels.extend(SOURCES[s]["labels"])

    for test_key in ["same_day", "another_day"]:
        print(f"\n{'─'*60}")
        print(f"  测试条件: {test_key}")
        print(f"{'─'*60}")

        cm_blocks = []
        total_correct, total_samples = 0, 0
        all_acc = {"SVM": [], "RF": [], "LDA": [], "KNN": [], "ensemble": []}
        all_n = []

        for src_name in ["8dev", "18dev", "30dev"]:
            src_cfg = SOURCES[src_name]
            n_dev = len(src_cfg["ids"])
            result = _train_and_eval_one_source(src_name, src_cfg, test_key)

            cm = result["confusion_matrix"]
            cm_blocks.append(cm)

            n_test = cm.sum()
            n_correct = np.diag(cm).sum()
            total_correct += n_correct
            total_samples += n_test
            all_n.append(n_test)

            for k in ["SVM", "RF", "LDA", "KNN", "ensemble"]:
                all_acc[k].append(result[f"acc_{k}"])

        # 组装56×56分块对角混淆矩阵
        cm_56 = np.zeros((56, 56), dtype=int)
        offset = 0
        for cm_block in cm_blocks:
            n = cm_block.shape[0]
            cm_56[offset:offset+n, offset:offset+n] = cm_block
            offset += n

        overall_acc = total_correct / total_samples if total_samples > 0 else 0
        print(f"\n  56台总体准确率 ({test_key}): {overall_acc:.2%} "
              f"({int(total_correct)}/{int(total_samples)})")

        # 加权平均各分类器准确率
        weights = np.array(all_n, dtype=float)
        weights /= weights.sum()
        result_combined = {}
        for k in ["SVM", "RF", "LDA", "KNN", "ensemble"]:
            result_combined[f"acc_{k}"] = float(np.dot(all_acc[k], weights))
            print(f"    {k:>8s}: {result_combined[f'acc_{k}']:.2%} (加权)")
        result_combined["acc_ensemble"] = result_combined["acc_ensemble"]

        # 绘图
        plot_confusion_matrix(
            cm_56,
            f"56-Device Confusion Matrix ({test_key.replace('_',' ').title()})"
            f" — Overall Acc: {overall_acc:.1%}",
            os.path.join(OUTPUT_DIR, f"cm_56_{test_key}.png"),
            labels=all_labels, normalize=True
        )

        # 保存
        with open(os.path.join(OUTPUT_DIR, f"results_56_{test_key}.json"), "w") as f:
            json.dump(result_combined, f, indent=2, default=str)

    # 准确率对比图 (合并两条件)
    bar_results = {}
    for test_key in ["same_day", "another_day"]:
        with open(os.path.join(OUTPUT_DIR, f"results_56_{test_key}.json")) as f:
            bar_results[test_key] = json.load(f)

    plot_accuracy_bars(
        bar_results,
        os.path.join(OUTPUT_DIR, "accuracy_56_comparison.png"),
        title="56-Device Ensemble Classification Accuracy (Per-Group Training)"
    )


# ========================================================================
#  任务 b: 18台设备消融实验
# ========================================================================

def _select_features(raw, key):
    ph = raw[:, 0:8]
    ph1 = raw[:, 0:4]
    e1, e2 = raw[:, 8:9], raw[:, 9:10]
    m = (e1+e2)/2
    d = e2 - e1
    cfo4 = np.hstack([e1, e2, m, d])
    cfo2 = np.hstack([e1, e2])

    MAP = {
        "base":            np.hstack([ph, cfo2]),
        "base_cfo_mean":   np.hstack([ph, m]),
        "cfo_only":        cfo4,
        "phase_single":    ph1,
        "phase_dual":      ph,
        "phase_dual_cfo":  np.hstack([ph, cfo4]),
        "phase_single_cfo": np.hstack([ph1, cfo4]),
    }
    return MAP[key]


def _run_single(X_tr, y_tr, X_te, y_te, clf_name):
    try:
        sc = StandardScaler()
        Xtr = sc.fit_transform(X_tr)
        Xte = sc.transform(X_te)
        k = min(5, max(1, len(Xtr)//max(1, len(np.unique(y_tr)))))
        clfs = {
            "XGBoost": GradientBoostingClassifier(n_estimators=200, max_depth=5,
                                                   random_state=42),
            "随机森林": RandomForestClassifier(n_estimators=200, random_state=42,
                                               n_jobs=-1),
            "SVM": SVC(kernel="rbf", C=10.0, gamma="scale", random_state=42,
                        max_iter=5000),
            "KNN": KNeighborsClassifier(n_neighbors=k, metric="minkowski", p=2),
        }
        clf = clfs[clf_name]
        clf.fit(Xtr, y_tr)
        return accuracy_score(y_te, clf.predict(Xte))
    except Exception as e:
        print(f"    [{clf_name} 异常: {e}]")
        return 0.0


def _run_ensemble_feat(X_tr, y_tr, X_te, y_te):
    try:
        n_classes = len(np.unique(y_tr))
        model = DualFrameCFOEnsemble(
            gamma=1.0, tau_1=0.3, tau_2=0.1,
            n_neighbors=min(5, max(1, len(X_tr)//n_classes - 1)),
            n_estimators=200, svm_C=10.0, random_state=42,
        )
        model.fit(X_tr, y_tr, val_ratio=0.2)
        return accuracy_score(y_te, model.predict(X_te))
    except Exception as e:
        print(f"    [集成学习异常: {e}]")
        # fallback: 用 RF 单独跑
        sc = StandardScaler()
        Xtr = sc.fit_transform(X_tr)
        Xte = sc.transform(X_te)
        rf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
        rf.fit(Xtr, y_tr)
        return accuracy_score(y_te, rf.predict(Xte))


def task_b():
    print("\n" + "="*70)
    print("  任务 b: 18台设备消融实验 (重新提取数据)")
    print("="*70)

    root = os.path.join(DATA_ROOT, "outputcsv18", "outputcsv18")
    ids = [str(i) for i in range(1, 19)]
    sp = SOURCES["18dev"]["splits"]

    # 加载全部 split (新数据, CFO 已正常, 无需清洗)
    raw_train, y_train = _load_csv_dir(root, *sp["train"], ids)
    raw_same, y_same = _load_csv_dir(root, *sp["same_day"], ids)
    raw_another, y_another = _load_csv_dir(root, *sp["another_day"], ids)

    print(f"  训练: {raw_train.shape}, "
          f"同天测试: {raw_same.shape}, 跨天测试: {raw_another.shape}")

    feature_configs = [
        ("连续双帧差分相位+CFO（Base）",   "base"),
        ("连续双帧差分相位+CFO 均值",       "base_cfo_mean"),
        ("只用CFO特征（连续双帧下的）",     "cfo_only"),
        ("只用单帧相位特征",                "phase_single"),
        ("只用双帧相位特征",                "phase_dual"),
        ("双帧相位特征+CFO 特征",           "phase_dual_cfo"),
        ("单帧相位特征+CFO 特征",           "phase_single_cfo"),
    ]
    clf_names = ["XGBoost", "随机森林", "SVM", "KNN", "集成学习"]

    # ---- 表2: 同天 ----
    print(f"\n{'─'*60}")
    print("  表2: 同天测试")
    print(f"{'─'*60}")
    table2 = []
    for label, key in feature_configs:
        X_tr = _select_features(raw_train, key)
        X_te = _select_features(raw_same, key)
        y_tr, y_te = y_train, y_same

        row = {"特征组合": label}
        print(f"\n  {label} (dim={X_tr.shape[1]})")
        for clf in clf_names:
            if clf == "集成学习":
                acc = _run_ensemble_feat(X_tr, y_tr, X_te, y_te)
            else:
                acc = _run_single(X_tr, y_tr, X_te, y_te, clf)
            row[clf] = acc
            print(f"    {clf}: {acc:.2%}")
        row["最大正确率"] = max(row[c] for c in clf_names)
        table2.append(row)

    # ---- 表3: 跨天 ----
    print(f"\n{'─'*60}")
    print("  表3: 跨天测试")
    print(f"{'─'*60}")
    table3 = []
    for label, key in feature_configs:
        X_tr = _select_features(raw_train, key)
        X_te = _select_features(raw_another, key)
        y_tr, y_te = y_train, y_another

        row = {"特征组合": label}
        print(f"\n  {label} (dim={X_tr.shape[1]})")
        for clf in clf_names:
            if clf == "集成学习":
                acc = _run_ensemble_feat(X_tr, y_tr, X_te, y_te)
            else:
                acc = _run_single(X_tr, y_tr, X_te, y_te, clf)
            row[clf] = acc
            print(f"    {clf}: {acc:.2%}")
        row["最大正确率"] = max(row[c] for c in clf_names)
        table3.append(row)

    # ---- 打印 & 保存 ----
    all_cols = ["特征组合", "XGBoost", "随机森林", "SVM", "KNN", "集成学习", "最大正确率"]

    def _print_table(table, title):
        print(f"\n{'='*110}")
        print(f"  {title}")
        print(f"{'='*110}")
        hdr = f"{'特征组合':30s}"
        for c in all_cols[1:]:
            hdr += f" | {c:>8s}"
        print(hdr)
        print("-" * len(hdr))
        for r in table:
            line = f"{r['特征组合']:30s}"
            for c in all_cols[1:]:
                line += f" | {r[c]:>7.0%} "
            print(line)

    _print_table(table2, "表2  训练集和测试集在同一天的识别结果（更新版）")
    _print_table(table3, "表3  训练集和测试集在不同天的识别结果（更新版）")

    # 保存 JSON
    def ser(table):
        return [{k: (f"{v:.4f}" if isinstance(v, float) else v)
                 for k, v in r.items()} for r in table]
    with open(os.path.join(OUTPUT_DIR, "results_18_ablation.json"), "w",
              encoding="utf-8") as f:
        json.dump({"table2_same_day": ser(table2),
                    "table3_another_day": ser(table3)}, f, indent=2,
                   ensure_ascii=False)

    # 绘制表格图
    for table, title, fname in [
        (table2, "表2  训练集和测试集在同一天的识别结果（更新版）",
         "table2_same_day.png"),
        (table3, "表3  训练集和测试集在不同天的识别结果（更新版）",
         "table3_another_day.png"),
    ]:
        _plot_table(table, all_cols, title, os.path.join(OUTPUT_DIR, fname))


def _plot_table(table, columns, title, save_path):
    n_rows, n_cols = len(table), len(columns)
    fig, ax = plt.subplots(figsize=(16, 0.5*n_rows + 2))
    ax.axis('off')
    ax.set_title(title, fontsize=14, pad=20, fontweight='bold')
    cells = []
    for r in table:
        row = []
        for c in columns:
            v = r[c]
            row.append(f"{v:.0%}" if isinstance(v, float) else str(v))
        cells.append(row)
    tbl = ax.table(cellText=cells, colLabels=columns, cellLoc='center',
                   loc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.5)
    for j in range(n_cols):
        tbl[0, j].set_facecolor('#2E5A3E')
        tbl[0, j].set_text_props(color='white', fontweight='bold')
    for i, r in enumerate(table):
        max_v = r.get("最大正确率", -1)
        for j, c in enumerate(columns[1:], start=1):
            v = r[c]
            if isinstance(v, float) and abs(v - max_v) < 1e-6:
                tbl[i+1, j].set_text_props(fontweight='bold')
            if c == "集成学习":
                tbl[i+1, j].set_facecolor('#E8F5E9')
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  -> {save_path}")


# ======================== 主函数 ========================

def main():
    print("="*70)
    print("  集成学习扩展实验 (优化版)")
    print("="*70)
    task_a()
    task_b()
    print("\n" + "="*70)
    print("  所有实验完成!")
    print("="*70)


if __name__ == "__main__":
    main()
