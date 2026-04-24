"""
测试预处理流程在 data_2026 新数据上的适用性。
流程: 帧同步(粗+精) -> 前导码提取(8*L) -> CFO补偿(粗+精) -> 幅度归一化
      -> 双帧CFO特征提取 -> 信道无关时频图提取

对应专利方案: 融合双帧载波频偏特征的LoRa终端识别方法v2.docx
"""
import numpy as np
import os
import sys
import time
from scipy import signal as scipy_signal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ============ LoRa 物理层参数 ============
B = 125000          # 带宽 125kHz
T = 128 / B         # 一个chirp符号周期
f_sample = 5000000  # 采样率 5MHz
Ts = 1 / f_sample   # 采样间隔
L = int(T * f_sample)  # 每个chirp的采样点数 = 1024
n_arr = np.arange(0, L, 1)
# 理想 upchirp 模板
ideal_sample = np.exp(1j * (-np.pi * B * n_arr * Ts + np.pi * B / T * (n_arr * Ts) ** 2))

# ============ 数据路径 ============
DATA_BASE = r"D:\srtp_data\data_2026"
OUTPUT_DIR = r"D:\srtp_data\data_2026\preprocessing_test_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============ 预处理函数 ============

def sync(sample):
    """
    帧同步: 粗同步(Schmidl-Cox, scipy correlate加速) + 精同步(瞬时频率互相关)
    返回前导码起始索引
    """
    from scipy.signal import fftconvolve

    N = len(sample)
    if N < 2 * L:
        raise ValueError(f"信号长度 {N} 过短, 无法同步 (需要至少 {2*L} 样本)")

    # --- 粗同步 ---
    # P(n) = sum_{k=0}^{L-1} r[n+k] * conj(r[n+k+L]), n=0..N-2L-1
    # product[k] = r[k] * conj(r[k+L])
    product = sample[:N-L] * np.conj(sample[L:N])
    # 前缀和 (prepend 0 使索引对齐)
    cs = np.concatenate(([0], np.cumsum(product)))
    # P(n) = cs[n+L] - cs[n], for n=0..N-2L-1
    num_pos = N - 2 * L
    P_abs = np.abs(cs[L:L+num_pos] - cs[:num_pos])

    # R(n) = sum_{k=0}^{L-1} |r[n+k+L]|^2, n=0..N-2L-1
    power = np.abs(sample) ** 2
    cs_pow = np.concatenate(([0], np.cumsum(power)))
    # R(n) = cs_pow[n+2L] - cs_pow[n+L]
    R = cs_pow[2*L:2*L+num_pos] - cs_pow[L:L+num_pos]

    M = np.where(R > 0, P_abs / R, 0)
    above = np.where(M > 0.95)[0]
    if len(above) == 0:
        raise ValueError("粗同步失败: 未找到M>0.95的位置")
    start_coarse = above[0]

    # --- 精同步 ---
    seg_start = max(0, start_coarse - 10)
    seg_end = min(N, start_coarse + 2 * L + 10)
    seg = sample[seg_start:seg_end]

    angle = np.unwrap(np.angle(seg))
    freq = np.diff(angle) / (2 * np.pi) * f_sample

    ideal_freq = -B / 2 + (B / T) * n_arr * Ts

    offset = start_coarse - seg_start
    search_start = offset
    search_end = min(offset + L, len(freq) - L)

    # 滤除异常频率值
    clip_region = slice(search_start, min(search_end + L, len(freq)))
    freq_clip = freq.copy()
    mask = (freq_clip[clip_region] < -80000) | (freq_clip[clip_region] > 80000)
    freq_clip[clip_region] = np.where(mask, 0, freq_clip[clip_region])

    n_windows = search_end - search_start
    if n_windows <= 0:
        return start_coarse

    # 向量化互相关
    windows = np.lib.stride_tricks.as_strided(
        freq_clip[search_start:],
        shape=(n_windows, L),
        strides=(freq_clip.strides[0], freq_clip.strides[0])
    )
    scores = np.abs(windows @ ideal_freq)
    best_local = np.argmax(scores)
    index = seg_start + search_start + best_local

    return index


def cfo_compensation(sample):
    """
    CFO补偿: 粗估+粗补偿 -> 精估+精补偿
    输入: 8*L长度的前导码信号
    返回: (补偿后信号, CFO估计值)
    """
    if len(sample) < 8 * L:
        raise ValueError(f"信号长度 {len(sample)} 不足8*L={8*L}")

    # 粗CFO估计: 第一个chirp的瞬时频率均值
    angle = np.unwrap(np.angle(sample[0:L]))
    freq = np.diff(angle) / (2 * np.pi) * f_sample
    cfo_coarse = np.sum(freq) / L

    # 粗补偿
    n_8L = np.arange(0, 8 * L, 1)
    cfo_corr_coarse = sample[0:8*L] * np.exp(-1j * 2 * np.pi * cfo_coarse * n_8L * Ts)

    # 精CFO估计: 相邻chirp自相关
    temp = np.angle(np.sum(cfo_corr_coarse[0:L] * np.conj(cfo_corr_coarse[L:2*L])))
    cfo_fine = temp / (-2 * np.pi * T)

    # 精补偿
    cfo_corr = cfo_corr_coarse * np.exp(-1j * 2 * np.pi * cfo_fine * n_8L * Ts)

    return cfo_corr, cfo_coarse + cfo_fine


def amplitude_normalize(signal_in):
    """
    幅度归一化: RMS归一化
    """
    rms = np.sqrt(np.mean(np.abs(signal_in) ** 2))
    if rms == 0:
        return signal_in
    return signal_in / rms


def cal_phase(sample):
    """
    计算8个chirp符号的相位残差
    """
    phases = []
    for i in range(8):
        ph = np.angle(np.sum(sample[i*L:(i+1)*L] * np.conj(ideal_sample)) / L)
        phases.append(ph)
    return np.array(phases)


def extract_dual_frame_cfo_features(cfo1, cfo2):
    """
    专利方案: 构建四维连续双帧频偏特征向量
    f_cfo = [epsilon_1, epsilon_2, (epsilon_1+epsilon_2)/2, epsilon_2-epsilon_1]
    """
    return np.array([
        cfo1,                       # 第一帧CFO
        cfo2,                       # 第二帧CFO
        (cfo1 + cfo2) / 2,          # 双帧均值 (抑制噪声)
        cfo2 - cfo1                 # 双帧差分 (频率漂移特性)
    ])


def extract_ci_time_frequency(signal_in):
    """
    提取信道无关时频图 (Channel-Independent Spectrogram)
    STFT -> FFT shift -> 相邻帧比值 -> log功率 -> 中心裁剪
    """
    f, t, spec = scipy_signal.stft(
        signal_in, window='boxcar', nperseg=256, noverlap=128,
        nfft=256, return_onesided=False, padded=False, boundary=None
    )
    spec = np.fft.fftshift(spec, axes=0)
    # 相邻时间帧比值 -> 消除信道频率响应
    chan_ind_spec = spec[:, 1:] / spec[:, :-1]
    chan_ind_spec_amp = np.log10(np.abs(chan_ind_spec) ** 2)
    # 中心裁剪40%
    return chan_ind_spec_amp[round(256 * 0.3):round(256 * 0.7)]


def normalized_minmax(x):
    """最大最小值归一化"""
    xmin, xmax = x.min(), x.max()
    if xmax == xmin:
        return np.zeros_like(x)
    return (x - xmin) / (xmax - xmin)


def extract_phase_diff_features(phase1, phase2):
    """
    归一化相位差特征 (已有方法)
    """
    return normalized_minmax(phase2) - normalized_minmax(phase1)


# ============ 单帧预处理测试 ============

def test_single_frame(file_path, frame_name=""):
    """测试单帧预处理全流程, 返回处理结果字典"""
    result = {"name": frame_name, "success": True, "errors": []}

    # 1. 读取原始IQ数据
    try:
        raw = np.fromfile(file_path, dtype=np.complex64)
        result["raw_length"] = len(raw)
        print(f"  [读取] {frame_name}: {len(raw)} 样本")
    except Exception as e:
        result["success"] = False
        result["errors"].append(f"读取失败: {e}")
        return result

    # 2. 帧同步
    try:
        t0 = time.time()
        start_idx = sync(raw)
        sync_time = time.time() - t0
        result["sync_index"] = start_idx
        result["sync_time"] = sync_time
        print(f"  [同步] 起始索引={start_idx}, 耗时={sync_time:.3f}s")
    except Exception as e:
        result["success"] = False
        result["errors"].append(f"同步失败: {e}")
        return result

    # 3. 前导码提取 (8个chirp)
    preamble_end = start_idx + 8 * L
    if preamble_end > len(raw):
        result["success"] = False
        result["errors"].append(f"前导码越界: 需要到{preamble_end}, 信号长度{len(raw)}")
        return result
    preamble = raw[start_idx:preamble_end]
    result["preamble_length"] = len(preamble)
    print(f"  [前导码] 提取 {len(preamble)} 样本 (8*{L})")

    # 4. CFO补偿
    try:
        compensated, cfo_val = cfo_compensation(preamble)
        result["cfo_value"] = cfo_val
        result["compensated_signal"] = compensated
        print(f"  [CFO补偿] 估计CFO = {cfo_val:.2f} Hz")
    except Exception as e:
        result["success"] = False
        result["errors"].append(f"CFO补偿失败: {e}")
        return result

    # 5. 幅度归一化
    normalized_sig = amplitude_normalize(compensated)
    result["normalized_signal"] = normalized_sig
    rms_after = np.sqrt(np.mean(np.abs(normalized_sig) ** 2))
    print(f"  [归一化] RMS归一化后: RMS={rms_after:.6f}")

    # 6. 相位残差
    phases = cal_phase(normalized_sig)
    result["phases"] = phases
    print(f"  [相位] 8-chirp相位残差: {np.round(phases, 4)}")

    # 7. 信道无关时频图
    try:
        ci_spec = extract_ci_time_frequency(normalized_sig)
        result["ci_spec"] = ci_spec
        print(f"  [CI时频图] shape={ci_spec.shape}")
    except Exception as e:
        result["errors"].append(f"CI时频图提取警告: {e}")
        print(f"  [CI时频图] 提取失败: {e}")

    return result


# ============ 双帧测试 ============

def test_dual_frame(file1, file2, name1, name2):
    """测试连续双帧的特征提取"""
    print(f"\n{'='*60}")
    print(f"双帧测试: {name1} + {name2}")
    print(f"{'='*60}")

    r1 = test_single_frame(file1, name1)
    r2 = test_single_frame(file2, name2)

    if not (r1["success"] and r2["success"]):
        print("[双帧] 单帧处理失败, 跳过双帧特征提取")
        return r1, r2, None

    # 双帧CFO特征 (专利核心)
    cfo_features = extract_dual_frame_cfo_features(r1["cfo_value"], r2["cfo_value"])
    print(f"\n  [双帧CFO特征]")
    print(f"    epsilon_1       = {cfo_features[0]:.2f} Hz")
    print(f"    epsilon_2       = {cfo_features[1]:.2f} Hz")
    print(f"    均值(抑噪)      = {cfo_features[2]:.2f} Hz")
    print(f"    差分(漂移)      = {cfo_features[3]:.2f} Hz")

    # 相位差特征
    phase_diff = extract_phase_diff_features(r1["phases"], r2["phases"])
    print(f"  [相位差特征] {np.round(phase_diff, 4)}")

    # 双帧CI时频图拼接
    if "ci_spec" in r1 and "ci_spec" in r2:
        ci_pair = np.vstack([r1["ci_spec"], r2["ci_spec"]])
        print(f"  [双帧CI时频图] shape={ci_pair.shape}")

    return r1, r2, cfo_features


# ============ 主测试 ============

def main():
    print("=" * 70)
    print("  预处理流程测试 - data_2026 新数据")
    print("  流程: 同步 -> 前导码提取 -> CFO补偿 -> 归一化 -> 特征提取")
    print("=" * 70)

    devices = [d for d in sorted(os.listdir(DATA_BASE)) if d.startswith("device")]
    print(f"\n发现 {len(devices)} 个设备: {devices}\n")

    all_results = {}

    for dev in devices:
        print(f"\n{'#'*70}")
        print(f"# 设备: {dev}")
        print(f"{'#'*70}")

        train_dir = os.path.join(DATA_BASE, dev, "train_data")
        test_dir = os.path.join(DATA_BASE, dev, "test_data")

        # 获取帧文件并按编号排序
        train_files = sorted(os.listdir(train_dir), key=lambda x: int(x.replace("frame", "")))
        test_files = sorted(os.listdir(test_dir), key=lambda x: int(x.replace("frame", "")))
        print(f"  训练集: {len(train_files)} 帧, 测试集: {len(test_files)} 帧")

        dev_results = {"train_cfo": [], "test_cfo": [], "dual_cfo_features": [],
                       "sync_failures": 0, "total_tested": 0}

        # --- 测试1: 前5帧单帧预处理 ---
        print(f"\n--- 单帧预处理测试 (前5帧) ---")
        for fname in train_files[:5]:
            fpath = os.path.join(train_dir, fname)
            r = test_single_frame(fpath, f"{dev}/train/{fname}")
            dev_results["total_tested"] += 1
            if r["success"]:
                dev_results["train_cfo"].append(r["cfo_value"])
            else:
                dev_results["sync_failures"] += 1
                print(f"  *** 失败: {r['errors']}")
            print()

        # --- 测试2: 连续双帧特征提取 (取前3对) ---
        print(f"\n--- 连续双帧特征提取测试 (前3对) ---")
        for pair_idx in range(min(3, len(train_files) // 2)):
            f1 = train_files[pair_idx * 2]
            f2 = train_files[pair_idx * 2 + 1]
            path1 = os.path.join(train_dir, f1)
            path2 = os.path.join(train_dir, f2)
            r1, r2, cfo_feat = test_dual_frame(path1, path2,
                                                f"{dev}/train/{f1}", f"{dev}/train/{f2}")
            dev_results["total_tested"] += 2
            if cfo_feat is not None:
                dev_results["dual_cfo_features"].append(cfo_feat)

        # --- 测试3: 测试集抽样 ---
        print(f"\n--- 测试集抽样 (前3帧) ---")
        for fname in test_files[:3]:
            fpath = os.path.join(test_dir, fname)
            r = test_single_frame(fpath, f"{dev}/test/{fname}")
            dev_results["total_tested"] += 1
            if r["success"]:
                dev_results["test_cfo"].append(r["cfo_value"])
            else:
                dev_results["sync_failures"] += 1
            print()

        all_results[dev] = dev_results

    # ============ 汇总报告 ============
    print("\n" + "=" * 70)
    print("  汇总报告")
    print("=" * 70)

    for dev, res in all_results.items():
        train_cfos = res["train_cfo"]
        test_cfos = res["test_cfo"]
        dual_feats = res["dual_cfo_features"]

        print(f"\n{dev}:")
        print(f"  测试帧数: {res['total_tested']}, 同步失败: {res['sync_failures']}")

        if train_cfos:
            print(f"  训练集CFO: 均值={np.mean(train_cfos):.2f} Hz, "
                  f"标准差={np.std(train_cfos):.2f} Hz, "
                  f"范围=[{np.min(train_cfos):.2f}, {np.max(train_cfos):.2f}]")
        if test_cfos:
            print(f"  测试集CFO: 均值={np.mean(test_cfos):.2f} Hz, "
                  f"标准差={np.std(test_cfos):.2f} Hz")
        if dual_feats:
            dual_arr = np.array(dual_feats)
            print(f"  双帧CFO特征 (4维):")
            labels = ["epsilon_1", "epsilon_2", "均值", "差分"]
            for k in range(4):
                print(f"    {labels[k]:12s}: 均值={np.mean(dual_arr[:,k]):.2f}, "
                      f"标准差={np.std(dual_arr[:,k]):.2f}")

    # ============ 可视化: CFO分布对比 ============
    print("\n生成CFO分布对比图...")
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 各设备CFO分布
    for dev, res in all_results.items():
        if res["train_cfo"]:
            axes[0].scatter([dev] * len(res["train_cfo"]), res["train_cfo"],
                           alpha=0.7, s=30, label=dev)
    axes[0].set_title("Device-wise training CFO distribution")
    axes[0].set_ylabel("CFO (Hz)")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # 双帧CFO特征对比
    for dev, res in all_results.items():
        if res["dual_cfo_features"]:
            feats = np.array(res["dual_cfo_features"])
            axes[1].scatter(feats[:, 2], feats[:, 3], alpha=0.7, s=50, label=dev)
    axes[1].set_title("Dual-frame CFO features: mean vs difference")
    axes[1].set_xlabel("CFO mean (Hz)")
    axes[1].set_ylabel("CFO difference (Hz)")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    fig_path = os.path.join(OUTPUT_DIR, "cfo_distribution.png")
    plt.savefig(fig_path, dpi=150)
    plt.close()
    print(f"图表已保存: {fig_path}")

    # ============ 可视化: CI时频图示例 ============
    print("\n生成CI时频图示例...")
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for idx, dev in enumerate(devices[:3]):
        train_dir = os.path.join(DATA_BASE, dev, "train_data")
        files = sorted(os.listdir(train_dir), key=lambda x: int(x.replace("frame", "")))

        for frame_idx in range(2):
            fpath = os.path.join(train_dir, files[frame_idx])
            raw = np.fromfile(fpath, dtype=np.complex64)
            try:
                start = sync(raw)
                preamble = raw[start:start+8*L]
                comp, _ = cfo_compensation(preamble)
                norm = amplitude_normalize(comp)
                ci = extract_ci_time_frequency(norm)
                axes[frame_idx][idx].imshow(ci, aspect='auto', cmap='viridis')
                axes[frame_idx][idx].set_title(f"{dev} frame{frame_idx+1}")
            except Exception as e:
                axes[frame_idx][idx].set_title(f"{dev} frame{frame_idx+1} FAIL")

    plt.suptitle("Channel-independent spectrogram examples (first 2 frames per device)")
    plt.tight_layout()
    fig_path = os.path.join(OUTPUT_DIR, "ci_spectrogram_examples.png")
    plt.savefig(fig_path, dpi=150)
    plt.close()
    print(f"图表已保存: {fig_path}")

    print("\n测试完成!")


if __name__ == "__main__":
    main()
