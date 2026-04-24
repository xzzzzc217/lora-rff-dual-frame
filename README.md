# 面向 LoRa 设备的连续双帧射频指纹提取与识别技术

> **Continuous Dual-Frame RF Fingerprint Extraction and Identification for LoRa Devices**

[English version below](#english-version) · [中文在前](#中文版本)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-1.10+-red.svg)](https://pytorch.org/)

---

## 中文版本

### 项目简介

本项目是东南大学网络空间安全学院的大学生创新训练项目（SRTP/国创），从 **2024 年 10 月校级立项** 走到 **2026 年 4 月国创结项**，历时一年半。研究问题是：**如何在仅观测射频信号的情况下，准确识别物联网中的 LoRa 终端设备身份**。

物联网中的射频设备指纹识别（Radio Frequency Fingerprinting, RFF）是一种基于硬件物理层非理想性的轻量级身份认证方法 —— 由于元器件制造工艺存在微小的容差，每个设备发射的射频信号都会带有不可复制的"指纹"特征。本项目的**核心创新**是提出了一种 **融合连续双帧载波频偏（CFO）特征的识别方法**，相比单帧方法在跨天、非视距等复杂场景下显著提升了鲁棒性。

### 研究背景

LoRa 是当前低功耗广域物联网（LPWAN）的主流通信协议之一，被广泛应用于智能抄表、农业监测、资产追踪等场景。然而 LoRa 现有的安全机制依赖预共享密钥，密钥泄露后无法快速识别冒名设备，因此基于物理层指纹的设备识别成为一种重要的补充防护手段。

现有 LoRa 射频指纹方法主要存在以下问题：
- **单帧 CFO 受瞬时噪声影响大**，跨时段稳定性差
- **基于深度学习的时频图方法**对信道环境敏感，跨场景泛化差
- **特征维度高、模型复杂**，不适合资源受限的边缘部署

### 核心方法

本项目提出 **融合连续双帧载波频偏特征的 LoRa 终端识别方法**（已申请国家发明专利），主要包含以下技术点：

#### 1. 双帧前导码同步与提取

针对 LoRa 帧结构，采用 **Schmidl-Cox 粗同步 + 瞬时频率互相关精同步** 的两级同步方案，对每个目标设备连续采集两帧前导码：

```
LoRa 物理层参数：
  带宽 B = 125 kHz, 扩频因子 SF = 7
  采样率 f_s = 5 MHz, 单 chirp 长度 L = 1024 samples
  前导码长度 = 8 chirps = 8L samples
```

#### 2. 双帧 CFO 特征构造（专利核心）

构建 **四维双帧 CFO 特征向量**：

```
f_cfo = [ε₁, ε₂, (ε₁+ε₂)/2, ε₂-ε₁]
       └─单帧─┘ └─均值（抑噪）─┘ └─差分（漂移）─┘
```

- **均值特征** 利用双帧平均抑制瞬时高斯噪声，提升 SNR
- **差分特征** 反映晶振温漂在两帧间的频率漂移特性，是设备特有的物理指纹

#### 3. 信道无关时频图（辅助特征）

通过 STFT + 相邻时间帧比值构造信道无关频谱图（Channel-Independent Spectrogram），消除信道频率响应：

```
chan_ind_spec[t] = STFT[t] / STFT[t-1]
```

#### 4. 异构集成学习分类器

采用四种异构基础分类器（**SVM、随机森林、LDA、KNN**）独立训练，配合 **静态权重 + 动态置信度** 加权融合：

```
α_k = (α_k^0 · β_k) / Σ(α_j^0 · β_j)
其中：α_k^0 = 验证集准确率比例（静态权重）
      β_k = exp(-γ · H_k)（动态置信度，H_k 为预测熵）
```

并设计 **双阈值拒识机制**（绝对置信门限 + 相对置信差门限）以处理未知设备。

### 实验结果

在 **30 设备 + 三种测试条件**（同天、跨天、非视距）下：

| 测试条件 | 准确率 |
|---------|-------|
| 同天测试（same day） | ~98% |
| 跨天测试（another day） | ~94% |
| 非视距测试（NLOS） | ~91% |

具体混淆矩阵、消融实验（8 设备 / 18 设备 / 56 设备）见 [`data/2026-04_结项/`](data/2026-04_结项/) 与 [`code/dual_frame_cfo_identification/results/`](code/dual_frame_cfo_identification/) 输出。

### 仓库结构

```
lora-rff-dual-frame/
├── README.md                          本文档
├── LICENSE                            MIT 开源许可证
│
├── code/                              ★ 自主实现的代码
│   ├── extract_preamble_2026.py       前导码批量提取（同步+截取）
│   ├── test_preprocessing_2026.py     预处理流程测试与可视化
│   ├── data1.py                       数据集划分脚本
│   ├── frame_sync_impl.cc / .h        GNU Radio 帧同步 C++ 实现
│   │
│   ├── dual_frame_cfo_identification/ ★ 双帧 CFO 集成识别（专利方案实现）
│   │   ├── main.py                    主实验脚本
│   │   ├── data_loader.py             特征构造（10维原始 → 12维特征）
│   │   ├── ensemble_classifier.py     四分类器集成 + 拒识机制
│   │   ├── gen_fig1_framework.py      系统框图生成
│   │   ├── gen_fig2_confusion.py      混淆矩阵绘制
│   │   └── results/                   实验输出（混淆矩阵 PNG、JSON）
│   │
│   ├── ensemble_56_devices/           大规模实验：56 设备消融
│   │   ├── main.py
│   │   ├── extract_8dev_full.py       8 设备完整实验
│   │   ├── extract_18dev.py           18 设备扩展实验
│   │   ├── task_c_8dev_ablation.py    特征消融
│   │   └── task_rejection_test.py     拒识机制测试
│   │
│   ├── 发射端代码/                    LoRa 发射端固件
│   │   ├── arduino_uno/               Arduino UNO + RFM95
│   │   ├── cubecell/                  CubeCell HTCC-AB02
│   │   ├── lora_32/                   Heltec WiFi LoRa 32
│   │   ├── SX126x_LoRa_transmitter_1212/  STM32 + SX126x
│   │   └── dual_frame_zzc/            自定义双帧发射逻辑
│   │
│   ├── my_heltec/, my_lora_1/         接收端 GNU Radio Companion 流图
│   ├── signal_to_csv/                 IQ 信号→CSV 特征转换
│   ├── 读frame_info的程序/             帧信息解析工具
│   └── README.md                      （注：第三方代码不在仓库内，见下方）
│
├── data/                              ★ 实验数据（小规模）
│   ├── 模型与图/
│   │   └── rff_cnn.pth                训练好的 CNN 模型权重
│   └── 2026-04_结项/                  最终结项实验输出
│       ├── output_csv/                30 设备四种条件下的 CSV 特征
│       ├── outputcsv8/                8 设备数据
│       ├── outputcsv18/               18 设备数据
│       └── 微信图片_*.png             实验现场照片
│
├── 1_校级立项/                        ★ 项目档案：2024-10 校级立项
│   ├── 立项申报书.docx
│   └── 立项答辩.pptx
├── 2_校级中期/                        ★ 2025-03 校级中期
│   ├── 中期报告v3.docx / .pdf
│   └── 中期检查表.xlsx
├── 3_国创立项/                        ★ 2025-04 国家级创新训练项目立项
│   ├── 创新训练项目申报表(终版).pdf
│   ├── 答辩稿.pptx
│   └── 论文调研/
├── 4_国创中期/                        ★ 2025-10 国创中期
│   ├── 国创中期检查报告.docx
│   ├── 国省创中期答辩.pptx
│   └── 经费使用表.xlsx
├── 5_国创结项/                        ★ 2026-03~04 国创结项
│   ├── 国创结题报告.docx
│   ├── 论文_融合双帧载波频偏特征的LoRa终端识别方法.docx
│   ├── 论文_第四部分_集成学习.docx
│   ├── 电子展板.png
│   ├── 致谢.docx
│   ├── 结题验收表.docx
│   ├── 项目内容诚信声明.docx
│   ├── 项目工作原始记录.docx
│   ├── 项目经费使用记录表.docx
│   ├── 结题终版PDF/                   8 个最终提交 PDF
│   └── 辅助生成脚本/                   自动生成致谢/工作记录的 Python 脚本
│
└── 专利/                              ★ 国家发明专利
    ├── 专利说明书(终版).docx
    ├── 受理通知书.pdf
    └── 起草过程稿/
```

### 环境要求

```bash
# Python 依赖
python >= 3.8
numpy >= 1.21
scipy >= 1.7
torch >= 1.10                 # CNN 模型推理
scikit-learn >= 1.0           # 集成分类器
pandas >= 1.3
matplotlib >= 3.5

# 信号采集（可选）
GNU Radio >= 3.10             # 接收端流图
USRP UHD                      # USRP B210/N210 驱动
```

安装：

```bash
pip install numpy scipy torch scikit-learn pandas matplotlib
```

### 快速开始

#### 1. 运行预处理流程测试

```bash
cd code
python test_preprocessing_2026.py
# 输出：CFO 分布图、信道无关时频图示例
```

#### 2. 运行集成学习分类实验

```bash
cd code/dual_frame_cfo_identification
# 修改 data_loader.py 中的 DATA_ROOT 指向你的 CSV 数据目录
python main.py
# 输出：30设备混淆矩阵 + 各条件准确率
```

#### 3. 大规模消融实验

```bash
cd code/ensemble_56_devices
python extract_8dev_full.py    # 8 设备完整实验
python extract_18dev.py        # 18 设备
python main.py                 # 56 设备主实验
```

### 数据说明

仓库中包含**最终结项实验数据**（`data/2026-04_结项/`，约 12MB），原始 IQ 帧数据（约 17GB，含 56 设备 × 多场景 × 双帧采集）由于 GitHub 仓库大小限制未上传。**如需完整原始数据用于复现或后续研究**，请通过 GitHub Issues 联系，或邮件联系作者。

### 第三方依赖项目

研究过程中参考、复现并对比了以下开源项目，特此致谢（这些项目未包含在本仓库中，请到原仓库获取）：

| 项目 | 用途 | 链接 |
|-----|-----|-----|
| **DR-RFF** | 解耦表示学习的 RFF 方法（基线对比） | https://github.com/{ref}/DR-RFF |
| **DeepCRF (TIFS)** | 信道鲁棒的深度学习 RFF（基线对比） | https://github.com/{ref}/DeepCRF |
| **EoRa-PI** | LoRa 边缘计算示例 | https://github.com/{ref}/EoRa-PI |
| **channel_ind_reproduction** | 信道无关时频图复现 | （上游论文复现） |

> 上表中具体的 GitHub 仓库 URL 请自行搜索 —— 由于上游项目可能更名或迁移，本 README 不固定链接以避免过期。

### 致谢

- 指导教师：东南大学网络空间安全学院 X 教授
- 参与者：东南大学网络空间安全学院 23 级 网安/网法 同学
- 实验设备：东南大学物联网安全实验室

### 引用

如果本工作对您的研究有帮助，欢迎引用：

```bibtex
@misc{lora-rff-dual-frame-2026,
  title  = {面向 LoRa 设备的连续双帧射频指纹提取与识别技术},
  author = {东南大学 SRTP 项目组},
  year   = {2026},
  note   = {国家级大学生创新训练项目 (2025-2026)},
  url    = {https://github.com/xzzzzc217/lora-rff-dual-frame}
}
```

### 许可证

本项目采用 [MIT License](LICENSE) 开源，欢迎学术与商业使用，唯一要求是保留版权声明。

---

## English Version

### Overview

This repository contains the full deliverables of an **undergraduate research training project (SRTP)** at Southeast University, China, running from **October 2024 to April 2026**. The research investigates **device identification of LoRa endpoints in IoT networks via physical-layer RF fingerprinting**.

Our **core contribution** is a novel **dual-frame carrier frequency offset (CFO) fusion method** that significantly improves cross-day and non-line-of-sight robustness over single-frame baselines.

### Background

Radio Frequency Fingerprinting (RFF) leverages hardware-level imperfections (e.g. crystal oscillator drift, PA non-linearities) to identify wireless devices without cryptographic credentials. For LoRa — a dominant LPWAN protocol used in smart metering, asset tracking, agriculture — RFF provides a complementary defense layer when pre-shared keys are compromised.

Existing LoRa RFF approaches suffer from:
- **Single-frame CFO** is corrupted by instantaneous noise, with poor temporal stability
- **Deep-learning spectrograms** are sensitive to channel conditions, with poor cross-scenario generalization
- **High feature dimensionality** is unsuitable for resource-constrained edge deployment

### Method

We propose a **dual-frame CFO fusion method** (Chinese national patent filed) consisting of four key components:

#### 1. Two-Stage Frame Synchronization
Schmidl-Cox coarse synchronization + instantaneous-frequency cross-correlation fine sync, applied to two consecutive preambles per device.

#### 2. Dual-Frame CFO Feature Vector (Patent Core)

```
f_cfo = [ε₁, ε₂, (ε₁+ε₂)/2, ε₂-ε₁]
```

- **Mean** — averages two frames to suppress instantaneous noise
- **Difference** — captures crystal-oscillator drift, a device-specific signature

#### 3. Channel-Independent Spectrogram (Auxiliary Feature)

```
chan_ind_spec[t] = STFT[t] / STFT[t-1]
```

Cancels channel frequency response via inter-frame ratio.

#### 4. Heterogeneous Ensemble Classifier

Four base learners (**SVM / RF / LDA / KNN**) fused via static accuracy weights + dynamic entropy-based confidence weights, with a dual-threshold rejection mechanism.

### Results

On **30 devices × 3 test conditions**:

| Test Condition | Accuracy |
|----------------|----------|
| Same day       | ~98% |
| Another day    | ~94% |
| NLOS           | ~91% |

### Repository Structure (Brief)

```
├── code/                Self-written code (preprocessing, classifiers, transmitter firmware)
├── data/                Final experimental results (~15MB)
├── 1_校级立项 ~ 5_国创结项/   Project archives across all milestones
├── 专利/                Patent filing
└── README.md            This document
```

See the Chinese section above for full file-by-file breakdown.

### Quick Start

```bash
# Install dependencies
pip install numpy scipy torch scikit-learn pandas matplotlib

# Test preprocessing pipeline
cd code
python test_preprocessing_2026.py

# Run main classification experiment
cd code/dual_frame_cfo_identification
# Edit DATA_ROOT in data_loader.py to point to your CSV path
python main.py
```

### Data Availability

The repository ships with **final experimental data** (`data/2026-04_结项/`, ~12MB). The full raw IQ dataset (~17GB, 56 devices × multiple scenarios × dual-frame captures) is excluded due to GitHub repo size limits. Please **open an issue** if you need it for reproduction.

### Third-Party Acknowledgments

This work builds on and compares against these open-source projects (not included in this repo, please fetch from upstream):

- **DR-RFF** — Disentangled Representation Learning for RFF
- **DeepCRF (TIFS)** — Channel-Robust Deep Learning RFF
- **EoRa-PI** — LoRa edge computing reference
- Channel-independent spectrogram reproduction code

### Citation

```bibtex
@misc{lora-rff-dual-frame-2026,
  title  = {Continuous Dual-Frame RF Fingerprint Extraction and Identification for LoRa Devices},
  author = {SRTP Team, School of Cyber Science and Engineering, Southeast University},
  year   = {2026},
  note   = {National College Student Innovation Training Program (2025-2026)},
  url    = {https://github.com/xzzzzc217/lora-rff-dual-frame}
}
```

### License

Released under the [MIT License](LICENSE).

---

### Contact

For data requests, collaboration, or questions, please open a GitHub Issue or contact the authors at the email listed in the patent filing.
