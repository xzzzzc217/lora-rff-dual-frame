"""
拒识率对比实验：
  场景A: 训练30台设备 → 测试30台设备（已知设备，期望拒识率低）
  场景B: 训练30台设备 → 测试8台设备（未知设备，期望拒识率高）

分别在 same_day 和 another_day 两种测试条件下评估。
"""

import os, sys, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ensemble_classifier import DualFrameCFOEnsemble
from data_loader import (
    build_features,
    DATA8_ROOT, DATA8_SPLITS, DATA8_DEVICE_IDS,
    DATA18_ROOT, DATA18_SPLITS, DATA18_DEVICE_IDS,
    DATA30_ROOT, DATA30_SPLITS, DATA30_DEVICE_IDS,
)

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def load_source(root, split_info, device_ids, split):
    """加载单个数据源的一个split，标签从0开始"""
    folder, prefix = split_info[split]
    all_X, all_y = [], []
    for i, dev_id in enumerate(device_ids):
        csv_path = os.path.join(root, folder, f"{prefix}{dev_id}.csv")
        if not os.path.exists(csv_path):
            # 尝试 .tmp 后缀
            csv_path_tmp = csv_path + ".tmp"
            if os.path.exists(csv_path_tmp):
                csv_path = csv_path_tmp
            else:
                print(f"  [跳过] {csv_path}")
                continue
        raw = np.loadtxt(csv_path, delimiter=',')
        if raw.ndim == 1:
            raw = raw.reshape(1, -1)
        X = build_features(raw)
        y = np.full(len(X), i, dtype=np.int32)
        all_X.append(X)
        all_y.append(y)
    if not all_X:
        return np.zeros((0, 12)), np.zeros(0, dtype=np.int32)
    return np.vstack(all_X), np.concatenate(all_y)


def run_rejection_test(model, X_test, y_test, description):
    """在测试集上运行拒识测试，返回统计信息"""
    preds, confs = model.predict_with_rejection(X_test)

    n_total = len(y_test)
    rejected_mask = (preds == -1)
    accepted_mask = ~rejected_mask
    n_rejected = rejected_mask.sum()
    n_accepted = accepted_mask.sum()
    rejection_rate = n_rejected / n_total if n_total > 0 else 0

    # 对于被接受的样本，计算分类准确率
    if n_accepted > 0:
        # 注意：场景B中8台设备标签与30台不同，全部预测都应该是"错误的"
        acc_accepted = (preds[accepted_mask] == y_test[accepted_mask]).mean()
    else:
        acc_accepted = float('nan')

    # 置信度统计
    mean_conf = confs.mean()
    mean_conf_rejected = confs[rejected_mask].mean() if n_rejected > 0 else float('nan')
    mean_conf_accepted = confs[accepted_mask].mean() if n_accepted > 0 else float('nan')

    result = {
        "description": description,
        "n_total": int(n_total),
        "n_rejected": int(n_rejected),
        "n_accepted": int(n_accepted),
        "rejection_rate": round(rejection_rate, 4),
        "acc_on_accepted": round(acc_accepted, 4) if not np.isnan(acc_accepted) else "N/A",
        "mean_confidence": round(mean_conf, 4),
        "mean_conf_rejected": round(mean_conf_rejected, 4) if not np.isnan(mean_conf_rejected) else "N/A",
        "mean_conf_accepted": round(mean_conf_accepted, 4) if not np.isnan(mean_conf_accepted) else "N/A",
    }
    return result


def main():
    print("=" * 60)
    print("拒识率对比实验")
    print("=" * 60)

    # ---- 加载30台设备训练集 ----
    print("\n[1] 加载30台设备训练集...")
    X_train_30, y_train_30 = load_source(DATA30_ROOT, DATA30_SPLITS, DATA30_DEVICE_IDS, "train")
    print(f"    训练集: {X_train_30.shape[0]} 样本, {len(np.unique(y_train_30))} 类")

    # ---- 训练集成模型 ----
    print("\n[2] 训练集成学习模型（30台设备）...")
    n_dev = len(DATA30_DEVICE_IDS)
    model = DualFrameCFOEnsemble(
        gamma=1.0, tau_1=0.3, tau_2=0.1,
        n_neighbors=min(5, max(1, X_train_30.shape[0] // n_dev - 1)),
        n_estimators=200, svm_C=10.0, random_state=42,
    )
    model.fit(X_train_30, y_train_30)
    print("    训练完成。")

    all_results = {}

    # ---- 场景A: 测试30台设备（已知设备）----
    for test_split in ["same_day", "another_day"]:
        print(f"\n[场景A] 30台设备 {test_split} 测试（已知设备）...")
        X_test, y_test = load_source(DATA30_ROOT, DATA30_SPLITS, DATA30_DEVICE_IDS, test_split)
        print(f"    测试集: {X_test.shape[0]} 样本")
        result = run_rejection_test(model, X_test, y_test, f"已知设备(30台)-{test_split}")
        all_results[f"known_30dev_{test_split}"] = result
        print(f"    拒识率: {result['rejection_rate']*100:.2f}%  "
              f"接受样本准确率: {result['acc_on_accepted']}")

    # ---- 场景B: 测试8台设备（未知设备）----
    for test_split in ["same_day", "another_day"]:
        print(f"\n[场景B] 8台设备 {test_split} 测试（未知设备）...")
        X_test_8, y_test_8 = load_source(DATA8_ROOT, DATA8_SPLITS, DATA8_DEVICE_IDS, test_split)
        # 标签设为 -99，表示这些设备不在训练集中
        y_test_8_unknown = np.full(len(y_test_8), -99, dtype=np.int32)
        print(f"    测试集: {X_test_8.shape[0]} 样本（全部为未知设备）")
        result = run_rejection_test(model, X_test_8, y_test_8_unknown,
                                    f"未知设备(8台)-{test_split}")
        # 对于未知设备：拒识=正确，接受=误识
        result["correct_rejection_rate"] = result["rejection_rate"]
        result["false_accept_rate"] = round(1 - result["rejection_rate"], 4)
        all_results[f"unknown_8dev_{test_split}"] = result
        print(f"    拒识率(正确拒识): {result['rejection_rate']*100:.2f}%  "
              f"误接受率: {result['false_accept_rate']*100:.2f}%")

    # ---- 场景C: 测试18台设备（未知设备）----
    for test_split in ["same_day", "another_day"]:
        print(f"\n[场景C] 18台设备 {test_split} 测试（未知设备）...")
        X_test_18, y_test_18 = load_source(DATA18_ROOT, DATA18_SPLITS, DATA18_DEVICE_IDS, test_split)
        y_test_18_unknown = np.full(len(y_test_18), -99, dtype=np.int32)
        print(f"    测试集: {X_test_18.shape[0]} 样本（全部为未知设备）")
        result = run_rejection_test(model, X_test_18, y_test_18_unknown,
                                    f"未知设备(18台)-{test_split}")
        result["correct_rejection_rate"] = result["rejection_rate"]
        result["false_accept_rate"] = round(1 - result["rejection_rate"], 4)
        all_results[f"unknown_18dev_{test_split}"] = result
        print(f"    拒识率(正确拒识): {result['rejection_rate']*100:.2f}%  "
              f"误接受率: {result['false_accept_rate']*100:.2f}%")

    # ---- 不同阈值的敏感性分析 ----
    print("\n[3] 阈值敏感性分析...")
    tau_configs = [
        (0.1, 0.05, "宽松"),
        (0.2, 0.08, "较宽松"),
        (0.3, 0.10, "默认"),
        (0.4, 0.15, "较严格"),
        (0.5, 0.20, "严格"),
        (0.6, 0.25, "非常严格"),
        (0.7, 0.30, "极严格"),
    ]

    # 加载 same_day 测试集
    X_30_test, y_30_test = load_source(DATA30_ROOT, DATA30_SPLITS, DATA30_DEVICE_IDS, "same_day")
    X_8_test, _ = load_source(DATA8_ROOT, DATA8_SPLITS, DATA8_DEVICE_IDS, "same_day")
    y_8_unknown = np.full(len(X_8_test), -99, dtype=np.int32)
    X_18_test, _ = load_source(DATA18_ROOT, DATA18_SPLITS, DATA18_DEVICE_IDS, "same_day")
    y_18_unknown = np.full(len(X_18_test), -99, dtype=np.int32)

    sensitivity = []
    print(f"\n  {'阈值配置':<12} {'tau1':>5} {'tau2':>5} | "
          f"{'已知拒识率':>10} {'8台拒识率':>10} {'18台拒识率':>10}")
    print("-" * 85)

    for tau1, tau2, name in tau_configs:
        model.tau_1 = tau1
        model.tau_2 = tau2

        r_known = run_rejection_test(model, X_30_test, y_30_test, "")
        r_unknown_8 = run_rejection_test(model, X_8_test, y_8_unknown, "")
        r_unknown_18 = run_rejection_test(model, X_18_test, y_18_unknown, "")

        row = {
            "name": name, "tau_1": tau1, "tau_2": tau2,
            "known_rejection_rate": r_known["rejection_rate"],
            "known_acc_accepted": r_known["acc_on_accepted"],
            "unknown_8dev_rejection_rate": r_unknown_8["rejection_rate"],
            "unknown_8dev_false_accept": round(1 - r_unknown_8["rejection_rate"], 4),
            "unknown_18dev_rejection_rate": r_unknown_18["rejection_rate"],
            "unknown_18dev_false_accept": round(1 - r_unknown_18["rejection_rate"], 4),
        }
        sensitivity.append(row)

        print(f"  {name:<12} {tau1:>5.2f} {tau2:>5.2f} | "
              f"{r_known['rejection_rate']*100:>9.2f}% "
              f"{r_unknown_8['rejection_rate']*100:>9.2f}% "
              f"{r_unknown_18['rejection_rate']*100:>9.2f}%")

    # 恢复默认
    model.tau_1 = 0.3
    model.tau_2 = 0.1

    all_results["sensitivity"] = sensitivity

    # ---- 保存结果 ----
    out_path = os.path.join(RESULTS_DIR, "results_rejection_test.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")

    # ---- 打印汇总 ----
    print("\n" + "=" * 60)
    print("汇总对比")
    print("=" * 60)
    print(f"\n{'场景':<35} {'样本数':>6} {'拒识率':>8} {'备注'}")
    print("-" * 70)
    for key in ["known_30dev_same_day", "known_30dev_another_day",
                "unknown_8dev_same_day", "unknown_8dev_another_day",
                "unknown_18dev_same_day", "unknown_18dev_another_day"]:
        r = all_results[key]
        note = ""
        if "unknown" in key:
            note = f"误接受率={r['false_accept_rate']*100:.2f}%"
        else:
            note = f"接受准确率={r['acc_on_accepted']}"
        print(f"  {r['description']:<33} {r['n_total']:>6} {r['rejection_rate']*100:>7.2f}% {note}")


if __name__ == "__main__":
    main()
