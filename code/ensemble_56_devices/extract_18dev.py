"""
从 dataset_0316 原始数据重新提取18台设备特征，覆盖 outputcsv18。

改进点:
  1. 使用 frame_info 中的 m_cfo 作为 CFO 特征（真实设备频偏，有区分度）
  2. 利用全部 ~510 帧/设备 → ~255 对样本（原来只有 24~128）
  3. 按时间顺序分割: 60% 训练, 20% 同日测试, 20% 跨日测试

输出格式: 10列CSV (与原 outputcsv18 一致)
  col 0-7: 连续双帧差分相位 (normalized)
  col 8:   帧1的CFO (来自 frame_info m_cfo)
  col 9:   帧2的CFO (来自 frame_info m_cfo)
"""

import numpy as np
import struct
import csv
import os
import time

# ============ LoRa 参数 (1MHz 采样) ============
B = 125000           # 带宽 Hz
T = 128 / B          # 符号周期 = 1.024ms
f_sample = 1_000_000 # 采样率
Ts = 1 / f_sample
L = int(T * f_sample) # 1024 samples/chirp
n_arr = np.arange(0, L)
ideal_sample = np.exp(1j * (-np.pi * B * n_arr * Ts + np.pi * B / T * (n_arr * Ts) ** 2))
ideal_freq = -B / 2 + (B / T) * n_arr * Ts  # 理想 chirp 瞬时频率

# ============ 路径 ============
DATA_RAW = r"C:\Users\21398\Desktop\sophomore\SRTP\data\dataset_0316"
OUTPUT_ROOT = r"C:\Users\21398\Desktop\sophomore\SRTP\data\outputcsv18\outputcsv18"

TRAIN_RATIO = 0.6
SAME_DAY_RATIO = 0.2


# ============ 信号处理函数 (全向量化) ============

def sync_vectorized(sample):
    """向量化 Schmidl-Cox 粗同步 + stride_tricks 精同步"""
    N = len(sample)
    if N < 2 * L:
        return 0

    # --- 粗同步 (向量化) ---
    search_len = min(N - 2 * L, 5000)
    product = sample[:search_len + L] * np.conj(sample[L:search_len + 2 * L])
    cs = np.concatenate(([0], np.cumsum(product)))
    P_abs = np.abs(cs[L:L + search_len] - cs[:search_len])

    power = np.abs(sample[L:search_len + 2 * L]) ** 2
    cs_pow = np.concatenate(([0], np.cumsum(power)))
    R = cs_pow[L:L + search_len] - cs_pow[:search_len]

    with np.errstate(divide='ignore', invalid='ignore'):
        M = np.where(R > 0, P_abs / R, 0.0)

    above = np.where(M > 0.95)[0]
    if len(above) == 0:
        return 0
    start_coarse = int(above[0])

    # --- 精同步 (stride_tricks 向量化) ---
    seg_start = max(0, start_coarse - 10)
    seg_end = min(N, start_coarse + 2 * L + 10)
    seg = sample[seg_start:seg_end]

    angle = np.unwrap(np.angle(seg))
    freq = np.diff(angle) / (2 * np.pi) * f_sample

    offset = start_coarse - seg_start
    search_start = offset
    search_end = min(offset + L, len(freq) - L)
    n_windows = search_end - search_start

    if n_windows <= 0:
        return start_coarse

    # 清理异常频率
    freq_clean = freq.copy()
    clip_sl = slice(search_start, search_end + L)
    mask = (np.abs(freq_clean[clip_sl]) > 80000)
    freq_clean[clip_sl] = np.where(mask, 0.0, freq_clean[clip_sl])

    # stride_tricks 批量互相关
    windows = np.lib.stride_tricks.as_strided(
        freq_clean[search_start:],
        shape=(n_windows, L),
        strides=(freq_clean.strides[0], freq_clean.strides[0])
    )
    scores = np.abs(windows @ ideal_freq)
    best_local = int(np.argmax(scores))

    return seg_start + search_start + best_local


def cfo_compensation(sample):
    """两级 CFO 补偿"""
    sig = sample[0:8 * L].copy()

    # 粗估
    angle = np.unwrap(np.angle(sig[0:L]))
    freq = np.diff(angle) / (2 * np.pi) * f_sample
    cfo_coarse = np.mean(freq)

    # 粗补偿
    n = np.arange(0, 8 * L)
    sig *= np.exp(-1j * 2 * np.pi * cfo_coarse * n * Ts)

    # 细估
    temp = np.angle(np.sum(sig[0:L] * np.conj(sig[L:2 * L])))
    cfo_fine = temp / (-2 * np.pi * T)

    # 细补偿
    sig *= np.exp(-1j * 2 * np.pi * cfo_fine * n * Ts)

    return sig, cfo_coarse + cfo_fine


def cal_phase(sample):
    """计算8个 chirp 的相位残差 (向量化)"""
    # 重塑为 (8, L) 然后批量计算
    chirps = sample[:8 * L].reshape(8, L)
    corr = np.sum(chirps * np.conj(ideal_sample)[np.newaxis, :], axis=1) / L
    return np.angle(corr)


def normalized_minmax(x):
    r = x.max() - x.min()
    if r < 1e-15:
        return np.zeros_like(x)
    return (x - x.min()) / r


def read_frame_info(path):
    with open(path, 'rb') as f:
        data = f.read()
    return struct.unpack('ddd', data)


# ============ 主提取逻辑 ============

def extract_device(dev_id):
    """提取单个设备的所有帧对特征"""
    dev_dir = os.path.join(DATA_RAW, f"device_{dev_id}")
    data_dir = os.path.join(dev_dir, "data")
    info_dir = os.path.join(dev_dir, "frame_info")

    frames = sorted([int(f) for f in os.listdir(data_dir)
                     if os.path.isfile(os.path.join(data_dir, f))])

    features = []
    n_fail = 0

    i = 0
    while i + 1 < len(frames):
        f1, f2 = frames[i], frames[i + 1]
        i += 2

        try:
            raw1 = np.fromfile(os.path.join(data_dir, str(f1)), dtype=np.complex64)
            raw2 = np.fromfile(os.path.join(data_dir, str(f2)), dtype=np.complex64)

            s1 = sync_vectorized(raw1)
            s2 = sync_vectorized(raw2)

            if s1 + 8 * L > len(raw1) or s2 + 8 * L > len(raw2):
                n_fail += 1
                continue

            sig1, _ = cfo_compensation(raw1[s1:s1 + 8 * L])
            sig2, _ = cfo_compensation(raw2[s2:s2 + 8 * L])

            ph1 = cal_phase(sig1)
            ph2 = cal_phase(sig2)

            phase_diff = normalized_minmax(ph2) - normalized_minmax(ph1)

            _, _, cfo1 = read_frame_info(os.path.join(info_dir, str(f1)))
            _, _, cfo2 = read_frame_info(os.path.join(info_dir, str(f2)))

            row = np.concatenate([phase_diff, [cfo1, cfo2]])

            if np.any(np.isnan(row)) or np.any(np.isinf(row)):
                n_fail += 1
                continue

            features.append(row)

        except Exception:
            n_fail += 1
            continue

    return features, n_fail


def save_csv(features, filepath):
    """保存特征列表为 CSV"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except PermissionError:
            tmp = filepath + ".tmp"
            with open(tmp, 'w', newline='') as f:
                writer = csv.writer(f)
                for row in features:
                    writer.writerow(row)
            try:
                os.replace(tmp, filepath)
            except Exception:
                print(f"  [警告] 无法覆盖 {filepath}, 已写入 {tmp}")
            return
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        for row in features:
            writer.writerow(row)


def main():
    print("=" * 60)
    print("  从 dataset_0316 重新提取 18 台设备特征 (向量化)")
    print("=" * 60)

    for subdir in ["train_dataset", "test_same_day", "test_another_day"]:
        os.makedirs(os.path.join(OUTPUT_ROOT, subdir), exist_ok=True)

    total_train = 0
    total_same = 0
    total_another = 0
    t_start = time.time()

    for dev_id in range(1, 19):
        t0 = time.time()
        features, n_fail = extract_device(dev_id)
        elapsed = time.time() - t0

        n_total = len(features)
        if n_total == 0:
            print(f"  device_{dev_id}: 0 samples! ({n_fail} failed)")
            continue

        n_train = int(n_total * TRAIN_RATIO)
        n_same = int(n_total * SAME_DAY_RATIO)
        n_another = n_total - n_train - n_same

        train_data = features[:n_train]
        same_data = features[n_train:n_train + n_same]
        another_data = features[n_train + n_same:]

        save_csv(train_data, os.path.join(
            OUTPUT_ROOT, "train_dataset", f"train_data_device_{dev_id}.csv"))
        save_csv(same_data, os.path.join(
            OUTPUT_ROOT, "test_same_day", f"test_same_data_device_{dev_id}.csv"))
        save_csv(another_data, os.path.join(
            OUTPUT_ROOT, "test_another_day", f"test_another_data_device_{dev_id}.csv"))

        total_train += n_train
        total_same += n_same
        total_another += n_another

        cfo_vals = [f[8] for f in features] + [f[9] for f in features]
        cfo_mean = np.mean(cfo_vals)

        print(f"  device_{dev_id:2d}: {n_total:3d} samples "
              f"(train={n_train}, same={n_same}, another={n_another}), "
              f"fail={n_fail}, CFO={cfo_mean:.3f}Hz, {elapsed:.1f}s")

    elapsed_total = time.time() - t_start
    print(f"\n完成! 耗时 {elapsed_total:.1f}s")
    print(f"  训练集: {total_train}")
    print(f"  同日测试: {total_same}")
    print(f"  跨日测试: {total_another}")
    print(f"  总计: {total_train + total_same + total_another}")
    print(f"\n输出: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
