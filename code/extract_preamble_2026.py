"""
批量提取 D:\srtp_data\data_2026 各设备前导码 IQ 文件并删除原始大文件。

策略（两阶段，保证安全）:
  Phase 1: 对每个原始 frame 文件 → 同步 → 截取 8*L 前导码 → 写入 preamble_train_data / preamble_test_data
  Phase 2: 确认所有前导码文件均成功写入后，删除原始 train_data / test_data 目录

失败的帧会跳过并记录，不影响整体流程。
运行结束后打印统计报告。

LoRa 参数:
  BW=125kHz, SF=7, f_sample=5MHz → L=5120, 8*L=40960 samples
"""

import numpy as np
import os
import shutil
import time

# ============ LoRa 参数 ============
B        = 125000
T        = 128 / B
f_sample = 5_000_000
Ts       = 1 / f_sample
L        = int(T * f_sample)   # 5120 samples/chirp
PREAMBLE_LEN = 8 * L           # 40960 samples

print(f"LoRa参数: f_sample={f_sample/1e6:.0f}MHz, B={B/1e3:.0f}kHz, L={L}, 前导码长度={PREAMBLE_LEN} 样本")

# ============ 路径 ============
DATA_BASE = r"D:\srtp_data\data_2026"

# ============ 同步函数（矢量化 Schmidl-Cox + 精同步）============

def sync(sample):
    """
    粗同步(Schmidl-Cox 矢量化) + 精同步(瞬时频率互相关)
    返回前导码起始索引
    """
    N = len(sample)
    if N < 2 * L:
        raise ValueError(f"信号过短({N}), 需至少{2*L}")

    n_arr = np.arange(L)
    ideal_freq = -B / 2 + (B / T) * n_arr * Ts

    # --- 粗同步 ---
    product = sample[:N-L] * np.conj(sample[L:N])
    cs = np.concatenate(([0], np.cumsum(product)))
    num_pos = N - 2 * L
    P_abs = np.abs(cs[L:L+num_pos] - cs[:num_pos])

    power = np.abs(sample) ** 2
    cs_pow = np.concatenate(([0], np.cumsum(power)))
    R = cs_pow[2*L:2*L+num_pos] - cs_pow[L:L+num_pos]

    with np.errstate(divide='ignore', invalid='ignore'):
        M = np.where(R > 0, P_abs / R, 0.0)

    above = np.where(M > 0.95)[0]
    if len(above) == 0:
        raise ValueError("粗同步失败: 未找到 M>0.95")
    start_coarse = int(above[0])

    # --- 精同步 ---
    seg_start = max(0, start_coarse - 10)
    seg_end   = min(N, start_coarse + 2 * L + 10)
    seg = sample[seg_start:seg_end]

    angle = np.unwrap(np.angle(seg))
    freq  = np.diff(angle) / (2 * np.pi) * f_sample

    offset       = start_coarse - seg_start
    search_start = offset
    search_end   = min(offset + L, len(freq) - L)

    freq_clip = freq.copy()
    clip_sl = slice(search_start, min(search_end + L, len(freq)))
    mask = (freq_clip[clip_sl] < -B / 2 * 1.2) | (freq_clip[clip_sl] > B / 2 * 1.2)
    freq_clip[clip_sl] = np.where(mask, 0.0, freq_clip[clip_sl])

    n_windows = search_end - search_start
    if n_windows <= 0:
        return start_coarse

    windows = np.lib.stride_tricks.as_strided(
        freq_clip[search_start:],
        shape=(n_windows, L),
        strides=(freq_clip.strides[0], freq_clip.strides[0])
    )
    scores    = np.abs(windows @ ideal_freq)
    best_local = int(np.argmax(scores))
    return seg_start + search_start + best_local


# ============ 单文件提取 ============

def extract_preamble(src_path):
    """
    读取原始 IQ 文件 -> 同步 -> 截取前导码 -> 返回 complex64 数组
    成功返回 np.ndarray, 失败抛出异常
    """
    raw = np.fromfile(src_path, dtype=np.complex64)
    if len(raw) < PREAMBLE_LEN + 2 * L:
        raise ValueError(f"文件过短({len(raw)} 样本), 无法提取前导码")

    start = sync(raw)
    end   = start + PREAMBLE_LEN

    if end > len(raw):
        raise ValueError(f"前导码越界: start={start}, end={end}, len={len(raw)}")

    return raw[start:end]


# ============ 批量处理 ============

def process_device(dev_dir, split_name):
    """
    处理一个设备的一个 split（train_data 或 test_data）。
    原始目录: dev_dir/split_name/
    输出目录: dev_dir/preamble_split_name/   (e.g. preamble_train_data)
    返回 (success_count, fail_count, fail_list)
    """
    src_dir = os.path.join(dev_dir, split_name)
    dst_dir = os.path.join(dev_dir, f"preamble_{split_name}")
    os.makedirs(dst_dir, exist_ok=True)

    files = sorted(
        [f for f in os.listdir(src_dir) if os.path.isfile(os.path.join(src_dir, f))],
        key=lambda x: int(x.replace("frame", ""))
    )

    success, fail = 0, 0
    fail_list = []

    for fname in files:
        src_path = os.path.join(src_dir, fname)
        dst_path = os.path.join(dst_dir, fname)

        # 已存在则跳过（断点续传）
        if os.path.exists(dst_path) and os.path.getsize(dst_path) == PREAMBLE_LEN * 8:
            success += 1
            continue

        try:
            preamble = extract_preamble(src_path)
            preamble.tofile(dst_path)
            success += 1
        except Exception as e:
            fail += 1
            fail_list.append((fname, str(e)))

    return success, fail, fail_list


def delete_original_split(dev_dir, split_name):
    """删除原始 split 目录"""
    target = os.path.join(dev_dir, split_name)
    if os.path.isdir(target):
        shutil.rmtree(target)
        print(f"    [删除] {target}")
    else:
        print(f"    [跳过] {target} 不存在")


# ============ 主流程 ============

def main():
    devices = sorted(
        [d for d in os.listdir(DATA_BASE) if d.startswith("device") and
         os.path.isdir(os.path.join(DATA_BASE, d))],
        key=lambda x: int(x.replace("device", ""))
    )
    splits = ["train_data", "test_data"]

    print(f"\n发现 {len(devices)} 个设备: {devices}")
    print(f"处理 splits: {splits}\n")

    total_success = 0
    total_fail    = 0
    all_fails     = {}

    t_start = time.time()

    # ===== Phase 1: 提取前导码 =====
    print("=" * 60)
    print("Phase 1: 提取前导码 IQ 文件")
    print("=" * 60)

    for dev in devices:
        dev_dir = os.path.join(DATA_BASE, dev)
        print(f"\n[{dev}]")

        for split in splits:
            src_dir = os.path.join(dev_dir, split)
            if not os.path.isdir(src_dir):
                print(f"  {split}: 目录不存在, 跳过")
                continue

            n_files = len([f for f in os.listdir(src_dir)
                           if os.path.isfile(os.path.join(src_dir, f))])
            print(f"  {split}: {n_files} 帧 ...", end="", flush=True)

            t0 = time.time()
            ok, bad, fails = process_device(dev_dir, split)
            elapsed = time.time() - t0

            total_success += ok
            total_fail    += bad

            # 原始文件大小 vs 前导码大小
            src_sample = os.path.join(dev_dir, split,
                         sorted(os.listdir(src_dir),
                                key=lambda x: int(x.replace("frame","")))[0])
            orig_bytes = os.path.getsize(src_sample)
            print(f" 成功={ok}, 失败={bad}, 耗时={elapsed:.1f}s "
                  f"(原始帧~{orig_bytes//1024}KB → 前导码={PREAMBLE_LEN*8//1024}KB)")

            if fails:
                all_fails[f"{dev}/{split}"] = fails
                for fname, err in fails[:3]:
                    print(f"    !! {fname}: {err}")
                if len(fails) > 3:
                    print(f"    ... 共 {len(fails)} 个失败")

    # ===== Phase 2: 删除原始文件 =====
    print("\n" + "=" * 60)
    print("Phase 2: 删除原始 train_data / test_data 目录")
    print("=" * 60)

    if total_fail > 0:
        print(f"\n警告: 共有 {total_fail} 帧提取失败。")
        ans = input("仍要删除原始文件? [y/N]: ").strip().lower()
        if ans != "y":
            print("已取消删除。请检查失败帧后重新运行。")
            return

    for dev in devices:
        dev_dir = os.path.join(DATA_BASE, dev)
        print(f"\n[{dev}]")
        for split in splits:
            # 确认前导码目录存在且文件数量匹配
            src_dir = os.path.join(dev_dir, split)
            dst_dir = os.path.join(dev_dir, f"preamble_{split}")

            if not os.path.isdir(src_dir):
                continue

            n_src = len([f for f in os.listdir(src_dir) if os.path.isfile(os.path.join(src_dir, f))])
            n_dst = len([f for f in os.listdir(dst_dir) if os.path.isfile(os.path.join(dst_dir, f))]) if os.path.isdir(dst_dir) else 0

            if n_dst >= n_src - total_fail:
                delete_original_split(dev_dir, split)
            else:
                print(f"    [跳过删除] {split}: 前导码文件数({n_dst}) < 期望({n_src}), 请检查")

    # ===== 统计报告 =====
    elapsed_total = time.time() - t_start
    print("\n" + "=" * 60)
    print("统计报告")
    print("=" * 60)
    print(f"  总耗时        : {elapsed_total:.1f}s ({elapsed_total/60:.1f}min)")
    print(f"  成功提取      : {total_success} 帧")
    print(f"  提取失败      : {total_fail} 帧")
    print(f"  每帧前导码大小: {PREAMBLE_LEN * 8 / 1024:.1f} KB")
    print(f"  预计节省空间  : ~{total_success * (289000 - PREAMBLE_LEN) * 8 / 1024 / 1024:.0f} MB")

    if all_fails:
        print("\n失败帧汇总:")
        for key, fails in all_fails.items():
            print(f"  {key}: {len(fails)} 帧")
            for fname, err in fails[:2]:
                print(f"    {fname}: {err}")


if __name__ == "__main__":
    main()
