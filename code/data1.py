import os
import numpy as np
import json
import matplotlib.pyplot as plt

def coarse_synchronization(signal, L, threshold_factor=0.3, smooth_window=25):
    """
    粗同步：使用相关性方法检测帧的粗略起点。
    """
    P = np.zeros(len(signal) - 2 * L, dtype=np.complex64)
    R = np.zeros(len(signal) - 2 * L)
    M = np.zeros(len(signal) - 2 * L, dtype=np.complex64)  # 保留复数信息

    for n in range(len(signal) - 2 * L):
        P[n] = np.sum(signal[n:n + L] * np.conj(signal[n + L:n + 2 * L]))
        R[n] = np.sum(np.abs(signal[n + L:n + 2 * L])**2)
        if R[n] != 0:
            M[n] = P[n] / R[n]  # 不取绝对值，保留复数信息

    # 平滑处理
    weights = np.hanning(smooth_window)  # 使用汉宁窗作为平滑权重
    smoothed_M_real = np.convolve(M.real, weights / np.sum(weights), mode='same')  # 平滑实部
    smoothed_M_imag = np.convolve(M.imag, weights / np.sum(weights), mode='same')  # 平滑虚部

    smoothed_M = smoothed_M_real + 1j * smoothed_M_imag  # 组合成复数信号

    # 动态阈值基于平滑后的幅度
    background_noise_level = np.mean(np.abs(smoothed_M[:500]))  # 计算背景噪声
    dynamic_threshold = background_noise_level + threshold_factor * (np.max(np.abs(smoothed_M)) - background_noise_level)

    # 检测候选帧起点
    potential_starts = np.argwhere(np.abs(smoothed_M) > dynamic_threshold).flatten()

    if len(potential_starts) > 0:
        frame_start = potential_starts[0]  # 取第一个候选点
        return frame_start, smoothed_M
    else:
        return None, smoothed_M



def fine_synchronization(signal, L, B, T, Ts, coarse_start, search_window=50):
    """
    精同步：根据瞬时频率的互相关性，精确定位帧的起点。
    """
    if coarse_start is None:
        return None, None

    # 理想的瞬时频率
    n = np.arange(L)
    f_ideal = -B / 2 + (B / T) * n * Ts

    # 瞬时频率计算
    theta = np.angle(signal)
    f_received = np.diff(np.unwrap(theta)) / Ts

    # 滤波处理
    f_received_filtered = np.convolve(f_received, np.ones(20) / 20, mode='same')

    # 互相关计算，动态扩展搜索范围
    corr = np.zeros(search_window)
    for i in range(search_window):
        start_idx = coarse_start - search_window // 2 + i
        end_idx = start_idx + L
        if end_idx <= len(f_received_filtered) and start_idx >= 0:
            segment = f_received_filtered[start_idx:end_idx]
            corr[i] = np.sum(f_ideal * segment) / (np.linalg.norm(f_ideal) * np.linalg.norm(segment))

    fine_start_offset = np.argmax(corr) - search_window // 2
    fine_start = coarse_start + fine_start_offset

    return fine_start, corr


def read_file(file_path):
    """
    根据文件类型读取文件内容。
    """
    try:
        # 判断是否为二进制文件
        if "data" in file_path:
            signal = np.fromfile(file_path, dtype=np.complex64)
            return signal
        # elif "frame_info" in file_path:
        #     # 尝试读取 JSON 文件
        #     with open(file_path, 'r', encoding='utf-8') as f:
        #         content = f.read().strip()
        #         if not content:
        #             print(f"frame_info 文件 {file_path} 内容为空。")
        #             return None
        #         try:
        #             frame_info = json.loads(content)  # 解析为 JSON 格式
        #             return frame_info
        #         except json.JSONDecodeError:
        #             # 如果不是 JSON 文件，则尝试解析为复数数组
        #             return np.array(eval(content))
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return content
    except Exception as e:
        print(f"读取文件 {file_path} 时发生错误: {e}")
        return None

# def origin_frequency(file_content):


# def extract_theoretical_start(frame_info):
#     """
#     从 frame_info 提取理论帧起点。
#     假设 frame_info 是一个包含复数值的数组，起点可能是第一个值的某个属性（如实部或索引）。
#     """
#     try:
#         if isinstance(frame_info, np.ndarray) and frame_info.ndim == 1:
#             # 示例逻辑：提取数组中复数值的第一个索引为理论起点
#             return int(np.real(frame_info[0]))
#         else:
#             print("frame_info 文件格式未知，无法提取理论帧起点。")
#             return None
#     except Exception as e:
#         print(f"提取理论帧起点时发生错误: {e}")
#         return None

if __name__ == "__main__":
    # 参数设置
    L = 128  # 每个 upchirp 的采样点数
    B = 125e3  # 带宽，单位为 Hz
    T = 1e-3  # upchirp 的持续时间，单位为秒
    Ts = 1 / (B * 2)  # 采样间隔
    threshold = 0.3  # 粗同步的动态阈值因子

    folder_path_data = "processed_dataset/device_3/data"
    skipped_files = []

    for file in sorted(os.listdir(folder_path_data)):
        data_file_path = os.path.join(folder_path_data, file)

        # 读取数据文件和帧信息文件
        file_content = read_file(data_file_path)

        plt.figure()
        plt.subplot(3,1,1)
        plt.specgram(file_content[:10000], Fs=100, cmap='viridis')  # Fs 为采样频率，可根据需要调
        plt.ylim(-20, 20)  # 设置纵轴范围，适配信号频率范围
        plt.legend()

        if isinstance(file_content, np.ndarray):
            print(f"开始处理信号文件 {data_file_path}...")

            if len(file_content) < 2 * L:
                print(f"信号文件 {data_file_path} 长度为 {len(file_content)}，不足，跳过处理。")
                skipped_files.append((data_file_path, len(file_content)))
                continue
        coarse_start, M_values = coarse_synchronization(file_content, L, threshold)
        print(f"粗同步检测到帧起点：{coarse_start}")

        if coarse_start is not None:
            fine_start, corr = fine_synchronization(file_content, L, B, T, Ts, coarse_start)
            print(f"精同步检测到帧起点：{fine_start}")
            synced_signal = file_content[coarse_start:coarse_start + 10000]

            # 可视化
            plt.subplot(3,1,2)
            # plt.plot(M_values, label="M(n)")
            plt.specgram(synced_signal, Fs=100, cmap='viridis')
            # plt.axvline(x=expected_start, color='r', linestyle='--', label="Expected Start")
            plt.ylim(-20, 20)  # 设置纵轴范围，适配信号频率范围
            plt.axvline(x=coarse_start, color='g', linestyle='--', label="Detected Coarse Start")
            plt.legend()
            plt.title("coarse_synchronization result")
            plt.xlabel("sample points")
            plt.ylabel("M(n)")


            synced_signal = file_content[fine_start:fine_start + 10000]
            plt.subplot(3,1,3)
            # plt.plot(M_values, label="M(n)")
            plt.specgram(synced_signal, Fs=100, cmap='viridis')
            # plt.axvline(x=expected_start, color='r', linestyle='--', label="Expected Start")
            plt.ylim(-20, 20)  # 设置纵轴范围，适配信号频率范围
            plt.axvline(x=fine_start, color='g', linestyle='--', label="Detected Fine Start")
            plt.legend()
            plt.title("fine_synchronization result")
            plt.xlabel("sample points")
            plt.ylabel("M(n)")

            # plt.subplot(3,1,3)
            # plt.plot(corr, label="互相关 (Fine Sync)")
            # plt.legend()
            # plt.title("fine_synchronization result")
            # plt.xlabel("sample points offset")
            # plt.ylabel("相关值")

            # 调整布局
            plt.tight_layout()
            plt.show()

else:
    print("粗同步未检测到帧，请调整信号或参数。")