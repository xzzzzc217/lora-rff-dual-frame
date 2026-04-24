"""
56台设备统一数据加载模块。

三个数据源:
  - outputcsv8   (8台, 采样率1MHz, 设备ID: 009,010,011,012,020,021,022,023)
  - outputcsv18  (18台, 采样率1MHz, 设备ID: 1-18)
  - output_csv   (30台, 采样率5MHz, 设备ID: 1-30)

统一标签编号: 0-7 (8台) | 8-25 (18台) | 26-55 (30台)

注意: 三组数据采样率不同，CFO数值量级差异大，
      通过对每个数据源单独做 Z-score 标准化后再合并来消除量级差异。
"""

import numpy as np
import pandas as pd
import os
from typing import Dict, Tuple, List

# ======================== 路径配置 ========================
DATA_ROOT = r"C:\Users\21398\Desktop\sophomore\SRTP\data"

# --- 8台设备 ---
DATA8_ROOT = os.path.join(DATA_ROOT, "outputcsv8", "outputcsv8")
DATA8_SPLITS = {
    "train":       ("train_dataset",    "train_data_device_"),
    "same_day":    ("test_same_day",    "test_same_data_device_"),
    "another_day": ("test_another_day", "test_another_data_device_"),
}
DATA8_DEVICE_IDS = ["009", "010", "011", "012", "020", "021", "022", "023"]

# --- 18台设备 ---
DATA18_ROOT = os.path.join(DATA_ROOT, "outputcsv18", "outputcsv18")
DATA18_SPLITS = {
    "train":       ("train_dataset",    "train_data_device_"),
    "same_day":    ("test_same_day",    "test_same_data_device_"),
    "another_day": ("test_another_day", "test_another_data_device_"),
}
DATA18_DEVICE_IDS = [str(i) for i in range(1, 19)]

# --- 30台设备 ---
DATA30_ROOT = os.path.join(DATA_ROOT, "output_csv")
DATA30_SPLITS = {
    "train":       ("train_dataset",    "train_data_device"),
    "same_day":    ("test_same_day",    "test_same_data_device"),
    "another_day": ("test_another_day", "test_another_data_device"),
}
DATA30_DEVICE_IDS = [str(i) for i in range(1, 31)]

NUM_DEVICES = 56  # 8 + 18 + 30

# 设备名映射（用于图表标签）
DEVICE_LABELS = (
    [f"8_{d}" for d in DATA8_DEVICE_IDS] +          # 0-7
    [f"18_{d}" for d in DATA18_DEVICE_IDS] +         # 8-25
    [f"30_{d}" for d in DATA30_DEVICE_IDS]           # 26-55
)


# ======================== 特征构造 ========================

def build_features(raw: np.ndarray) -> np.ndarray:
    """
    从原始10维数据构造12维特征向量。
    raw: shape (N, 10)
    返回: shape (N, 12)
    """
    phase_diff = raw[:, 0:8]
    eps1 = raw[:, 8:9]
    eps2 = raw[:, 9:10]
    mean_cfo = (eps1 + eps2) / 2
    diff_cfo = eps2 - eps1
    return np.hstack([phase_diff, eps1, eps2, mean_cfo, diff_cfo])


FEATURE_NAMES = [
    "phase_diff_0", "phase_diff_1", "phase_diff_2", "phase_diff_3",
    "phase_diff_4", "phase_diff_5", "phase_diff_6", "phase_diff_7",
    "cfo_1", "cfo_2", "cfo_mean", "cfo_diff",
]


# ======================== 单数据源加载 ========================

def _load_source(root: str, split_info: dict, device_ids: list,
                 split: str, label_offset: int) -> Tuple[np.ndarray, np.ndarray]:
    """加载单个数据源的一个split"""
    if split not in split_info:
        return np.zeros((0, 12)), np.zeros(0, dtype=np.int32)

    subdir, prefix = split_info[split]
    split_dir = os.path.join(root, subdir)

    X_list, y_list = [], []
    for local_idx, dev_id in enumerate(device_ids):
        csv_path = os.path.join(split_dir, f"{prefix}{dev_id}.csv")
        # 如果 .tmp 文件存在（说明原文件被锁），优先使用 .tmp
        tmp_path = csv_path + ".tmp"
        if os.path.exists(tmp_path):
            csv_path = tmp_path
        elif not os.path.exists(csv_path):
            continue
        df = pd.read_csv(csv_path, header=None)
        if df.shape[1] != 10:
            print(f"  [警告] {csv_path} 列数={df.shape[1]}, 跳过")
            continue
        raw = df.values.astype(np.float64)
        features = build_features(raw)
        global_label = label_offset + local_idx
        X_list.append(features)
        y_list.append(np.full(len(features), global_label, dtype=np.int32))

    if not X_list:
        return np.zeros((0, 12)), np.zeros(0, dtype=np.int32)
    return np.vstack(X_list), np.concatenate(y_list)


def _normalize_source(X: np.ndarray) -> np.ndarray:
    """对单个数据源做 Z-score 标准化（消除量级差异）"""
    if len(X) == 0:
        return X
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std < 1e-15] = 1.0
    return (X - mean) / std


# ======================== 统一加载接口 ========================

def load_split(split: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    加载56台设备的一个split。

    每个数据源先独立构造12维特征并做Z-score标准化，
    然后合并。这样不同采样率的CFO量级差异被消除。

    参数:
      split: "train" | "same_day" | "another_day"
    返回:
      X: (N_total, 12), y: (N_total,) 标签0-55
    """
    # 加载三个数据源
    X8, y8 = _load_source(DATA8_ROOT, DATA8_SPLITS, DATA8_DEVICE_IDS,
                           split, label_offset=0)
    X18, y18 = _load_source(DATA18_ROOT, DATA18_SPLITS, DATA18_DEVICE_IDS,
                             split, label_offset=8)
    X30, y30 = _load_source(DATA30_ROOT, DATA30_SPLITS, DATA30_DEVICE_IDS,
                             split, label_offset=26)

    # 对每个数据源独立标准化（消除不同采样率的量级差异）
    X8_norm = _normalize_source(X8)
    X18_norm = _normalize_source(X18)
    X30_norm = _normalize_source(X30)

    # 合并
    X_parts = [x for x in [X8_norm, X18_norm, X30_norm] if len(x) > 0]
    y_parts = [y for y in [y8, y18, y30] if len(y) > 0]

    X = np.vstack(X_parts)
    y = np.concatenate(y_parts)
    return X, y


def load_all_splits() -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """加载所有split"""
    splits = ["train", "same_day", "another_day"]
    data = {}
    for split in splits:
        print(f"加载 {split} ...")
        X, y = load_split(split)
        data[split] = (X, y)
        n_devices = len(np.unique(y))
        counts = np.bincount(y, minlength=NUM_DEVICES)
        active = (counts > 0).sum()
        print(f"  -> X: {X.shape}, 设备数: {active}, "
              f"样本范围: {counts[counts > 0].min()}-{counts[counts > 0].max()}")
    return data


# ======================== 单独加载 18 台设备 ========================

def load_split_18(split: str) -> Tuple[np.ndarray, np.ndarray]:
    """加载18台设备的一个split（标签 0-17）"""
    X, y = _load_source(DATA18_ROOT, DATA18_SPLITS, DATA18_DEVICE_IDS,
                         split, label_offset=0)
    return X, y


def load_all_splits_18() -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """加载18台设备所有split"""
    data = {}
    for split in ["train", "same_day", "another_day"]:
        X, y = load_split_18(split)
        data[split] = (X, y)
        if len(y) > 0:
            print(f"  18台 {split}: X={X.shape}, 设备数={len(np.unique(y))}")
    return data


if __name__ == "__main__":
    print("="*60)
    print("  56台设备数据加载测试")
    print("="*60)
    data = load_all_splits()

    print("\n各设备样本数 (训练集):")
    _, y_train = data["train"]
    counts = np.bincount(y_train, minlength=NUM_DEVICES)
    for i in range(NUM_DEVICES):
        print(f"  {DEVICE_LABELS[i]:>8s}: {counts[i]:4d}", end="")
        if (i + 1) % 6 == 0:
            print()
    print()
