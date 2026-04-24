"""
任务 c: 8台设备消融实验 — 复现原始表2/表3并新增集成学习列

输入: outputcsv8_full/ 下的34列CSV
  col 0-7:   phase diff (8)
  col 8-9:   CFO raw (2)
  col 10-11: CFO mean, diff (2)
  col 12-15: RSSI (rssi1, rssi2, mean, diff) (4)
  col 16-23: IQ stats (I_mean, Q_mean, I_std, Q_std × 2帧) (8)
  col 24-29: STFT (centroid, spread, flatness × 2帧) (6)
  col 30-33: EMD-like (envelope_mean, envelope_std, inst_freq_mean, inst_freq_std) (4)

特征组合对应原表行:
  1.  连续双帧差分相位+CFO（Base）      = phase(8) + cfo_raw(2) = 10D
  2.  连续双帧差分相位+CFO 均值          = phase(8) + cfo_mean(1) = 9D
  3.  只用CFO特征（连续双帧下的）         = cfo_raw(2) + cfo_derived(2) = 4D
  4.  只用RSSI特征（连续双帧下的）        = rssi(4) = 4D
  5.  只用IQ特征（连续双帧下的）          = iq_stats(8) = 8D
  6.  只用单帧相位特征                    = phase(4) = 4D (前4个)
  7.  只用双帧相位特征                    = phase(8) = 8D
  8.  双帧相位特征+CFO 特征              = phase(8) + cfo_all(4) = 12D
  9.  单帧相位特征+CFO 特征              = phase(4) + cfo_all(4) = 8D
  10. Base+STFT                          = phase(8) + cfo_raw(2) + stft(6) = 16D
  11. Base+EMD                           = phase(8) + cfo_raw(2) + emd(4) = 14D
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
from sklearn.metrics import accuracy_score
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "..", "dual_frame_cfo_identification"))
from ensemble_classifier import DualFrameCFOEnsemble

rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False

# ============ 路径 ============
DATA_ROOT = r"C:\Users\21398\Desktop\sophomore\SRTP\data\outputcsv8\outputcsv8_full"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DEVICES = ["009", "010", "011", "012", "020", "021", "022", "023"]
SPLITS = {
    "train": ("train_dataset", "train_data_device_"),
    "same_day": ("test_same_day", "test_same_data_device_"),
    "another_day": ("test_another_day", "test_another_data_device_"),
}


# ============ 数据加载 ============

def load_split(split_key):
    subdir, prefix = SPLITS[split_key]
    X_list, y_list = [], []
    for idx, dev_id in enumerate(DEVICES):
        path = os.path.join(DATA_ROOT, subdir, f"{prefix}{dev_id}.csv")
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path, header=None)
        X_list.append(df.values.astype(np.float64))
        y_list.append(np.full(len(df), idx, dtype=np.int32))
    return np.vstack(X_list), np.concatenate(y_list)


# ============ 特征选择 ============

def select_features(raw, key):
    """从34列原始数据中选取特定特征组合"""
    ph8 = raw[:, 0:8]       # 双帧相位差 (8D)
    ph4 = raw[:, 0:4]       # 单帧相位 (4D, 前4个)
    cfo_raw = raw[:, 8:10]   # CFO raw: cfo1, cfo2 (2D)
    cfo_mean = raw[:, 10:11] # CFO mean (1D)
    cfo_all = raw[:, 8:12]   # CFO 全部: raw + derived (4D)
    rssi = raw[:, 12:16]     # RSSI (4D)
    iq = raw[:, 16:24]       # IQ stats (8D)
    stft_feat = raw[:, 24:30] # STFT (6D)
    emd_feat = raw[:, 30:34]  # EMD-like (4D)

    MAP = {
        "base":            np.hstack([ph8, cfo_raw]),            # 10D
        "base_cfo_mean":   np.hstack([ph8, cfo_mean]),           # 9D
        "cfo_only":        cfo_all,                               # 4D
        "rssi_only":       rssi,                                  # 4D
        "iq_only":         iq,                                    # 8D
        "phase_single":    ph4,                                   # 4D
        "phase_dual":      ph8,                                   # 8D
        "phase_dual_cfo":  np.hstack([ph8, cfo_all]),            # 12D
        "phase_single_cfo": np.hstack([ph4, cfo_all]),           # 8D
        "base_stft":       np.hstack([ph8, cfo_raw, stft_feat]), # 16D
        "base_emd":        np.hstack([ph8, cfo_raw, emd_feat]),  # 14D
    }
    return MAP[key]


# ============ 分类器 ============

def run_single(X_tr, y_tr, X_te, y_te, clf_name):
    try:
        sc = StandardScaler()
        Xtr = sc.fit_transform(X_tr)
        Xte = sc.transform(X_te)
        k = min(5, max(1, len(Xtr) // max(1, len(np.unique(y_tr)))))
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
        print(f"    [{clf_name} error: {e}]")
        return 0.0


def run_ensemble(X_tr, y_tr, X_te, y_te):
    try:
        n_classes = len(np.unique(y_tr))
        model = DualFrameCFOEnsemble(
            gamma=1.0, tau_1=0.3, tau_2=0.1,
            n_neighbors=min(5, max(1, len(X_tr) // n_classes - 1)),
            n_estimators=200, svm_C=10.0, random_state=42,
        )
        model.fit(X_tr, y_tr, val_ratio=0.2)
        return accuracy_score(y_te, model.predict(X_te))
    except Exception as e:
        print(f"    [ensemble error: {e}]")
        sc = StandardScaler()
        Xtr = sc.fit_transform(X_tr)
        Xte = sc.transform(X_te)
        rf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
        rf.fit(Xtr, y_tr)
        return accuracy_score(y_te, rf.predict(Xte))


# ============ 绘制表格图片 ============

def plot_table(table, columns, title, save_path):
    n_rows, n_cols = len(table), len(columns)
    fig, ax = plt.subplots(figsize=(16, 0.5 * n_rows + 2.5))
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
                tbl[i + 1, j].set_text_props(fontweight='bold')
            if c == "集成学习":
                tbl[i + 1, j].set_facecolor('#E8F5E9')
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  -> {save_path}")


# ============ 主实验 ============

def main():
    print("=" * 70)
    print("  任务 c: 8台设备消融实验 (完整特征集)")
    print("=" * 70)

    # 加载数据
    raw_train, y_train = load_split("train")
    raw_same, y_same = load_split("same_day")
    raw_another, y_another = load_split("another_day")

    print(f"  训练: {raw_train.shape}, 同日: {raw_same.shape}, "
          f"跨日: {raw_another.shape}")

    feature_configs = [
        ("连续双帧差分相位+CFO（Base）",     "base"),
        ("连续双帧差分相位+CFO 均值",         "base_cfo_mean"),
        ("只用CFO特征（连续双帧下的）",       "cfo_only"),
        ("只用RSSI特征（连续双帧下的）",      "rssi_only"),
        ("只用IQ特征（连续双帧下的）",        "iq_only"),
        ("只用单帧相位特征",                  "phase_single"),
        ("只用双帧相位特征",                  "phase_dual"),
        ("双帧相位特征+CFO 特征",             "phase_dual_cfo"),
        ("单帧相位特征+CFO 特征",             "phase_single_cfo"),
        ("Base+STFT",                        "base_stft"),
        ("Base+EMD",                         "base_emd"),
    ]
    clf_names = ["XGBoost", "随机森林", "SVM", "KNN", "集成学习"]
    all_cols = ["特征组合"] + clf_names + ["最大正确率"]

    # ---- 表2: 同天 ----
    print(f"\n{'─'*60}")
    print("  表2: 同天测试 (8台设备)")
    print(f"{'─'*60}")
    table2 = []
    for label, key in feature_configs:
        X_tr = select_features(raw_train, key)
        X_te = select_features(raw_same, key)
        y_tr, y_te = y_train, y_same

        row = {"特征组合": label}
        print(f"\n  {label} (dim={X_tr.shape[1]})")
        for clf in clf_names:
            if clf == "集成学习":
                acc = run_ensemble(X_tr, y_tr, X_te, y_te)
            else:
                acc = run_single(X_tr, y_tr, X_te, y_te, clf)
            row[clf] = acc
            print(f"    {clf}: {acc:.2%}")
        row["最大正确率"] = max(row[c] for c in clf_names)
        table2.append(row)

    # ---- 表3: 跨天 ----
    print(f"\n{'─'*60}")
    print("  表3: 跨天测试 (8台设备)")
    print(f"{'─'*60}")
    table3 = []
    for label, key in feature_configs:
        X_tr = select_features(raw_train, key)
        X_te = select_features(raw_another, key)
        y_tr, y_te = y_train, y_another

        row = {"特征组合": label}
        print(f"\n  {label} (dim={X_tr.shape[1]})")
        for clf in clf_names:
            if clf == "集成学习":
                acc = run_ensemble(X_tr, y_tr, X_te, y_te)
            else:
                acc = run_single(X_tr, y_tr, X_te, y_te, clf)
            row[clf] = acc
            print(f"    {clf}: {acc:.2%}")
        row["最大正确率"] = max(row[c] for c in clf_names)
        table3.append(row)

    # ---- 打印结果 ----
    def print_table(table, title):
        print(f"\n{'='*120}")
        print(f"  {title}")
        print(f"{'='*120}")
        hdr = f"{'特征组合':30s}"
        for c in all_cols[1:]:
            hdr += f" | {c:>8s}"
        print(hdr)
        print("-" * 120)
        for r in table:
            line = f"{r['特征组合']:30s}"
            for c in all_cols[1:]:
                line += f" | {r[c]:>7.0%} "
            print(line)

    print_table(table2, "表2  训练集和测试集在同一天的识别结果（8台设备更新版）")
    print_table(table3, "表3  训练集和测试集在不同天的识别结果（8台设备更新版）")

    # ---- 保存 JSON ----
    def ser(table):
        return [{k: (f"{v:.4f}" if isinstance(v, float) else v)
                 for k, v in r.items()} for r in table]

    with open(os.path.join(OUTPUT_DIR, "results_8dev_ablation.json"), "w",
              encoding="utf-8") as f:
        json.dump({"table2_same_day": ser(table2),
                    "table3_another_day": ser(table3)}, f, indent=2,
                   ensure_ascii=False)

    # ---- 绘图 ----
    for table, title, fname in [
        (table2, "表2  训练集和测试集在同一天的识别结果（8台设备更新版）",
         "table2_8dev_same_day.png"),
        (table3, "表3  训练集和测试集在不同天的识别结果（8台设备更新版）",
         "table3_8dev_another_day.png"),
    ]:
        plot_table(table, all_cols, title, os.path.join(OUTPUT_DIR, fname))

    print("\n" + "=" * 70)
    print("  8台设备消融实验完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
