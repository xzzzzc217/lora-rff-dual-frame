"""
从8台设备原始IQ数据提取完整特征集，用于消融实验。

提取特征:
  - Phase diff (8): 连续双帧差分相位
  - CFO raw (2): 帧1/帧2 CFO
  - CFO derived (2): mean, diff
  - RSSI (4): rssi1, rssi2, mean, diff
  - IQ stats (8): I/Q 均值/标准差 × 2帧
  - STFT (6): 谱质心/谱展度/谱平坦度 × 2帧
  - EMD-like (4): 包络均值/标准差, 瞬时频率均值/标准差

输出: 34列CSV per device per split
"""

import numpy as np
import csv
import os
import time
from scipy.signal import stft, hilbert

# ============ LoRa 参数 (1MHz) ============
B = 125000
T = 128 / B
f_sample = 1_000_000
Ts = 1 / f_sample
L = int(T * f_sample)  # 1024
n_arr = np.arange(0, L)
ideal_sample = np.exp(1j * (-np.pi * B * n_arr * Ts + np.pi * B / T * (n_arr * Ts) ** 2))
ideal_freq = -B / 2 + (B / T) * n_arr * Ts

# ============ 路径 ============
DATA_ROOT = r"C:\Users\21398\Desktop\sophomore\SRTP\data"
OUTPUT_ROOT = os.path.join(DATA_ROOT, "outputcsv8", "outputcsv8_full")

DEVICES = ["009", "010", "011", "012", "020", "021", "022", "023"]
SPLITS = {
    "train_dataset": ("train_dataset", "train_data_device_"),
    "test_same_day": ("test_same_day", "test_same_data_device_"),
    "test_another_day": ("test_another_day", "test_another_data_device_"),
}


# ============ 信号处理 (向量化) ============

def sync_vectorized(sample):
    N = len(sample)
    if N < 2 * L:
        return 0
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

    seg_start = max(0, start_coarse - 10)
    seg_end = min(N, start_coarse + 2 * L + 10)
    seg = sample[seg_start:seg_end]
    angle = np.unwrap(np.angle(seg))
    freq = np.diff(angle) / (2 * np.pi) * f_sample
    offset = start_coarse - seg_start
    search_end = min(offset + L, len(freq) - L)
    n_windows = search_end - offset
    if n_windows <= 0:
        return start_coarse
    freq_clean = freq.copy()
    clip_sl = slice(offset, search_end + L)
    mask = np.abs(freq_clean[clip_sl]) > 80000
    freq_clean[clip_sl] = np.where(mask, 0.0, freq_clean[clip_sl])
    windows = np.lib.stride_tricks.as_strided(
        freq_clean[offset:],
        shape=(n_windows, L),
        strides=(freq_clean.strides[0], freq_clean.strides[0])
    )
    scores = np.abs(windows @ ideal_freq)
    return seg_start + offset + int(np.argmax(scores))


def cfo_compensation(sample):
    sig = sample[0:8 * L].copy()
    angle = np.unwrap(np.angle(sig[0:L]))
    freq = np.diff(angle) / (2 * np.pi) * f_sample
    cfo_coarse = np.mean(freq)
    n = np.arange(0, 8 * L)
    sig *= np.exp(-1j * 2 * np.pi * cfo_coarse * n * Ts)
    temp = np.angle(np.sum(sig[0:L] * np.conj(sig[L:2 * L])))
    cfo_fine = temp / (-2 * np.pi * T)
    sig *= np.exp(-1j * 2 * np.pi * cfo_fine * n * Ts)
    return sig, cfo_coarse + cfo_fine


def cal_phase(sample):
    chirps = sample[:8 * L].reshape(8, L)
    corr = np.sum(chirps * np.conj(ideal_sample)[np.newaxis, :], axis=1) / L
    return np.angle(corr)


def normalized_minmax(x):
    r = x.max() - x.min()
    if r < 1e-15:
        return np.zeros_like(x)
    return (x - x.min()) / r


# ============ 特征提取 ============

def compute_rssi(sig):
    """RSSI = 10*log10(mean(|signal|^2))"""
    p = np.mean(np.abs(sig) ** 2)
    if p > 0:
        return 10 * np.log10(p)
    return -100.0


def compute_iq_stats(sig):
    """I/Q 统计: [I_mean, Q_mean, I_std, Q_std]"""
    I = sig.real
    Q = sig.imag
    return [np.mean(I), np.mean(Q), np.std(I), np.std(Q)]


def compute_stft_features(sig):
    """STFT 谱特征: [spectral_centroid, spectral_spread, spectral_flatness]"""
    f, t, Zxx = stft(sig, fs=f_sample, nperseg=128, noverlap=64, nfft=256)
    psd = np.mean(np.abs(Zxx) ** 2, axis=1)  # 时间平均功率谱
    psd = psd + 1e-20  # 避免 log(0)
    total = np.sum(psd)
    if total < 1e-18:
        return [0.0, 0.0, 0.0]

    # 谱质心
    centroid = np.sum(f * psd) / total
    # 谱展度
    spread = np.sqrt(np.sum((f - centroid) ** 2 * psd) / total)
    # 谱平坦度 (geometric mean / arithmetic mean)
    log_mean = np.mean(np.log(psd))
    arith_mean = np.mean(psd)
    flatness = np.exp(log_mean) / arith_mean if arith_mean > 0 else 0.0

    return [centroid, spread, flatness]


def compute_emd_features(sig):
    """基于 Hilbert 变换的包络/瞬时频率特征 (EMD 近似)"""
    # 使用实部信号的 Hilbert 变换
    x = sig.real[:4 * L]  # 取前4个chirp
    analytic = hilbert(x)
    envelope = np.abs(analytic)
    inst_phase = np.unwrap(np.angle(analytic))
    inst_freq = np.diff(inst_phase) / (2 * np.pi) * f_sample

    return [
        np.mean(envelope),
        np.std(envelope),
        np.mean(inst_freq),
        np.std(inst_freq),
    ]


def extract_pair_features(raw1, raw2):
    """
    从一对原始 IQ 帧提取全部 34 维特征。
    返回 (features_34d, rssi1, rssi2) 或 None 如果失败。
    """
    s1 = sync_vectorized(raw1)
    s2 = sync_vectorized(raw2)

    if s1 + 8 * L > len(raw1) or s2 + 8 * L > len(raw2):
        return None

    preamble1 = raw1[s1:s1 + 8 * L]
    preamble2 = raw2[s2:s2 + 8 * L]

    # RSSI (用于质量过滤)
    rssi1 = compute_rssi(preamble1)
    rssi2 = compute_rssi(preamble2)

    # CFO 补偿 + 相位
    sig1, cfo1 = cfo_compensation(preamble1)
    sig2, cfo2 = cfo_compensation(preamble2)

    ph1 = cal_phase(sig1)
    ph2 = cal_phase(sig2)
    phase_diff = normalized_minmax(ph2) - normalized_minmax(ph1)

    # CFO 派生
    cfo_mean = (cfo1 + cfo2) / 2
    cfo_diff = cfo2 - cfo1

    # RSSI 派生
    rssi_mean = (rssi1 + rssi2) / 2
    rssi_diff = rssi2 - rssi1

    # IQ 统计 (补偿后信号)
    iq1 = compute_iq_stats(sig1)
    iq2 = compute_iq_stats(sig2)

    # STFT 特征
    stft1 = compute_stft_features(sig1)
    stft2 = compute_stft_features(sig2)

    # EMD-like 特征
    emd1 = compute_emd_features(preamble1)  # 用原始信号(未补偿)

    features = np.concatenate([
        phase_diff,                      # 0-7:   phase diff (8)
        [cfo1, cfo2],                    # 8-9:   CFO raw (2)
        [cfo_mean, cfo_diff],            # 10-11: CFO derived (2)
        [rssi1, rssi2, rssi_mean, rssi_diff],  # 12-15: RSSI (4)
        iq1, iq2,                        # 16-23: IQ stats (8)
        stft1, stft2,                    # 24-29: STFT (6)
        emd1,                            # 30-33: EMD-like (4)
    ])

    if np.any(np.isnan(features)) or np.any(np.isinf(features)):
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)

    return features


# ============ 批量处理 ============

def process_device_split(raw_dir, dev_id):
    """处理一个设备一个split的所有帧对"""
    dev_dir = os.path.join(raw_dir, f"device_{dev_id}")
    if not os.path.isdir(dev_dir):
        return [], 0

    files = sorted([int(f.replace('.bin', ''))
                    for f in os.listdir(dev_dir) if f.endswith('.bin')])

    features_list = []
    n_fail = 0

    i = 0
    while i + 1 < len(files):
        f1, f2 = files[i], files[i + 1]
        i += 2

        try:
            raw1 = np.fromfile(os.path.join(dev_dir, f"{f1}.bin"), dtype=np.complex64)
            raw2 = np.fromfile(os.path.join(dev_dir, f"{f2}.bin"), dtype=np.complex64)

            result = extract_pair_features(raw1, raw2)
            if result is not None:
                features_list.append(result)
            else:
                n_fail += 1
        except Exception:
            n_fail += 1

    return features_list, n_fail


def save_csv(features, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        for row in features:
            writer.writerow(row)


def main():
    print("=" * 60)
    print("  8台设备完整特征提取 (34维)")
    print("=" * 60)

    for subdir in SPLITS:
        os.makedirs(os.path.join(OUTPUT_ROOT, subdir), exist_ok=True)

    t_start = time.time()

    for split_key, (raw_subdir, csv_prefix) in SPLITS.items():
        print(f"\n--- {split_key} ---")
        raw_dir = os.path.join(DATA_ROOT, raw_subdir)

        for dev_id in DEVICES:
            t0 = time.time()
            features, n_fail = process_device_split(raw_dir, dev_id)
            elapsed = time.time() - t0

            if features:
                save_csv(features, os.path.join(
                    OUTPUT_ROOT, split_key, f"{csv_prefix}{dev_id}.csv"))
                cfo_vals = [f[8] for f in features]
                print(f"  device_{dev_id}: {len(features)} samples, "
                      f"fail={n_fail}, CFO_mean={np.mean(cfo_vals):.2f}Hz, "
                      f"{elapsed:.1f}s")
            else:
                print(f"  device_{dev_id}: 0 samples! fail={n_fail}, {elapsed:.1f}s")

    elapsed_total = time.time() - t_start
    print(f"\n完成! 耗时 {elapsed_total:.0f}s ({elapsed_total / 60:.1f}min)")
    print(f"输出: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
