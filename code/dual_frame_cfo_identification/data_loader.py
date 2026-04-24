"""
数据加载与特征构造模块。

原始CSV每行10列:
  col 0-7: 连续双帧归一化相位差 (8维)
  col 8  : 第一帧 CFO (epsilon_1)
  col 9  : 第二帧 CFO (epsilon_2)

按专利方案构造特征向量 F:
  - 8维相位差 (col 0-7)
  - 4维双帧CFO特征: [epsilon_1, epsilon_2, (e1+e2)/2, e2-e1]
  总计12维
"""

import numpy as np
import pandas as pd
import os
from typing import Dict, Tuple


# ======================== 路径配置 ========================
DATA_ROOT = r"C:\Users\21398\Desktop\sophomore\SRTP\data\output_csv"

SPLIT_DIRS = {
    "train":       "train_dataset",
    "same_day":    "test_same_day",
    "another_day": "test_another_day",
    "nlos":        "test_nlos_day",
}

FILE_PREFIXES = {
    "train":       "train_data_device",
    "same_day":    "test_same_data_device",
    "another_day": "test_another_data_device",
    "nlos":        "test_nlos_data_device",
}

NUM_DEVICES = 30


# ======================== 特征构造 ========================

def build_features(raw: np.ndarray) -> np.ndarray:
    """
    从原始10维数据构造12维特征向量。

    raw: shape (N, 10)
    返回: shape (N, 12)
      [phase_diff_0, ..., phase_diff_7, eps1, eps2, mean_cfo, diff_cfo]
    """
    phase_diff = raw[:, 0:8]        # 8维相位差
    eps1 = raw[:, 8:9]              # 第一帧CFO
    eps2 = raw[:, 9:10]             # 第二帧CFO
    mean_cfo = (eps1 + eps2) / 2    # 均值特征 (抑制噪声)
    diff_cfo = eps2 - eps1          # 差分特征 (频率漂移)

    return np.hstack([phase_diff, eps1, eps2, mean_cfo, diff_cfo])


FEATURE_NAMES = [
    "phase_diff_0", "phase_diff_1", "phase_diff_2", "phase_diff_3",
    "phase_diff_4", "phase_diff_5", "phase_diff_6", "phase_diff_7",
    "cfo_1", "cfo_2", "cfo_mean", "cfo_diff",
]


# ======================== 数据加载 ========================

def load_split(split: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    加载一个 split 的所有设备数据。

    参数:
      split: "train" | "same_day" | "another_day" | "nlos"

    返回:
      X: shape (N_total, 12) 特征矩阵
      y: shape (N_total,)    标签 (0-based: 0..29)
    """
    split_dir = os.path.join(DATA_ROOT, SPLIT_DIRS[split])
    prefix = FILE_PREFIXES[split]

    X_list, y_list = [], []

    for dev_id in range(1, NUM_DEVICES + 1):
        csv_path = os.path.join(split_dir, f"{prefix}{dev_id}.csv")
        if not os.path.exists(csv_path):
            print(f"  [警告] 文件不存在: {csv_path}")
            continue

        df = pd.read_csv(csv_path, header=None)
        if df.shape[1] != 10:
            print(f"  [警告] {csv_path} 列数={df.shape[1]}, 期望10")
            continue

        raw = df.values.astype(np.float64)
        features = build_features(raw)

        X_list.append(features)
        y_list.append(np.full(len(features), dev_id - 1, dtype=np.int32))

    X = np.vstack(X_list)
    y = np.concatenate(y_list)

    return X, y


def load_all_splits() -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """加载所有4个split, 返回字典 {split_name: (X, y)}"""
    data = {}
    for split in SPLIT_DIRS.keys():
        print(f"加载 {split} ...")
        X, y = load_split(split)
        data[split] = (X, y)
        print(f"  -> X: {X.shape}, y: {y.shape}, "
              f"设备数: {len(np.unique(y))}, "
              f"样本范围: {np.bincount(y).min()}-{np.bincount(y).max()}")
    return data


# ======================== 主函数 (调试用) ========================

if __name__ == "__main__":
    data = load_all_splits()

    print("\n各设备样本数:")
    for split, (X, y) in data.items():
        counts = np.bincount(y, minlength=NUM_DEVICES)
        print(f"\n{split}:")
        for i in range(NUM_DEVICES):
            print(f"  device{i+1:2d}: {counts[i]:4d}", end="")
            if (i + 1) % 6 == 0:
                print()
        print()
