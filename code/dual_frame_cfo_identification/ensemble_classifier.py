"""
融合双帧载波频偏特征的LoRa终端识别 - 集成学习分类器

按专利方案实现:
  步骤3.1: 四种异构基础分类器 (SVM, RF, LDA, KNN) 独立训练
  步骤3.2: 静态权重 + 动态置信度联合估计
  步骤3.3: 加权概率融合 -> 设备身份输出
  步骤3.4: 双阈值拒识机制
"""

import numpy as np
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings("ignore")


class DualFrameCFOEnsemble:
    """
    融合双帧CFO特征的LoRa终端集成学习识别器。

    四种异构分类器:
      1. SVM (RBF核 + Platt缩放输出后验概率)
      2. RF  (随机森林, 类别票数比例输出后验概率)
      3. LDA (线性判别分析, 高斯后验概率)
      4. KNN (K近邻, 邻域类别分布估计后验概率)

    融合策略:
      - 静态基权重 alpha_k^0 = A_k / sum(A_j)  (验证集准确率)
      - 动态置信因子 beta_k = exp(-gamma * H_k)  (预测熵)
      - 联合权重 alpha_k = (alpha_k^0 * beta_k) / sum(...)

    拒识机制:
      - 绝对置信门限 tau_1
      - 相对置信差门限 tau_2
    """

    def __init__(self,
                 gamma: float = 1.0,
                 tau_1: float = 0.3,
                 tau_2: float = 0.1,
                 n_neighbors: int = 5,
                 n_estimators: int = 200,
                 svm_C: float = 10.0,
                 svm_gamma_param: str = "scale",
                 random_state: int = 42):
        """
        参数:
          gamma: 动态置信度衰减超参数
          tau_1:  绝对置信门限 (拒识: max_prob < tau_1)
          tau_2:  相对置信差门限 (拒识: delta_p < tau_2)
          n_neighbors: KNN的K值
          n_estimators: 随机森林树数量
          svm_C: SVM正则化参数
        """
        self.gamma = gamma
        self.tau_1 = tau_1
        self.tau_2 = tau_2
        self.random_state = random_state

        # 标准化器
        self.scaler = StandardScaler()

        # 四种异构基础分类器
        self.classifiers = {
            "SVM": SVC(
                kernel="rbf", C=svm_C, gamma=svm_gamma_param,
                probability=True,  # Platt缩放输出后验概率
                random_state=random_state, max_iter=5000
            ),
            "RF": RandomForestClassifier(
                n_estimators=n_estimators,
                random_state=random_state, n_jobs=-1
            ),
            "LDA": LinearDiscriminantAnalysis(
                solver="svd",  # 适合高维小样本
            ),
            "KNN": KNeighborsClassifier(
                n_neighbors=n_neighbors,
                metric="minkowski", p=2,  # 标准化后欧氏距离等效马氏距离
                n_jobs=-1
            ),
        }

        self.clf_names = list(self.classifiers.keys())
        self.static_weights: Optional[np.ndarray] = None
        self.classes_: Optional[np.ndarray] = None
        self.is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray,
            val_ratio: float = 0.2) -> "DualFrameCFOEnsemble":
        """
        训练所有基础分类器并估计静态权重。

        步骤:
          1. 特征标准化
          2. 分层划分训练/验证集
          3. 在训练集上训练4个分类器
          4. 在验证集上评估 -> 计算静态基权重
        """
        self.classes_ = np.unique(y)
        n_classes = len(self.classes_)

        # 标准化 (标准化后欧氏距离等效于原始空间的马氏距离)
        X_scaled = self.scaler.fit_transform(X)

        # 分层划分训练/验证集
        skf = StratifiedKFold(n_splits=max(2, int(1 / val_ratio)),
                              shuffle=True, random_state=self.random_state)
        train_idx, val_idx = next(skf.split(X_scaled, y))

        X_train, y_train = X_scaled[train_idx], y[train_idx]
        X_val,   y_val   = X_scaled[val_idx],   y[val_idx]

        print(f"\n训练集: {len(X_train)} 样本, 验证集: {len(X_val)} 样本, "
              f"类别数: {n_classes}")

        # 训练各分类器并在验证集上评估
        accuracies = {}
        for name, clf in self.classifiers.items():
            clf.fit(X_train, y_train)
            acc = clf.score(X_val, y_val)
            accuracies[name] = acc
            print(f"  {name:4s}: 验证集准确率 = {acc:.4f}")

        # 用全部数据重新训练 (充分利用数据)
        for name, clf in self.classifiers.items():
            clf.fit(X_scaled, y)

        # 静态基权重: alpha_k^0 = A_k / sum(A_j)
        acc_values = np.array([accuracies[n] for n in self.clf_names])
        self.static_weights = acc_values / acc_values.sum()
        print(f"\n静态权重: {dict(zip(self.clf_names, np.round(self.static_weights, 4)))}")

        self.is_fitted = True
        return self

    def predict_proba_ensemble(self, X: np.ndarray) -> np.ndarray:
        """
        计算集成后验概率 (加权融合)。

        返回: shape (N, n_classes) 的集成后验概率矩阵
        """
        X_scaled = self.scaler.transform(X)
        N = len(X_scaled)
        n_classes = len(self.classes_)

        # 收集各分类器的后验概率
        all_probs = np.zeros((len(self.clf_names), N, n_classes))
        for k, name in enumerate(self.clf_names):
            probs = self.classifiers[name].predict_proba(X_scaled)
            # 确保类别对齐
            clf_classes = self.classifiers[name].classes_
            aligned = np.zeros((N, n_classes))
            for i, c in enumerate(clf_classes):
                idx = np.where(self.classes_ == c)[0]
                if len(idx) > 0:
                    aligned[:, idx[0]] = probs[:, i]
            all_probs[k] = aligned

        # 逐样本计算联合权重并融合
        ensemble_probs = np.zeros((N, n_classes))

        for i in range(N):
            # 动态置信因子: beta_k = exp(-gamma * H_k)
            betas = np.zeros(len(self.clf_names))
            for k in range(len(self.clf_names)):
                p = all_probs[k, i]
                p_clipped = np.clip(p, 1e-12, 1.0)
                H_k = -np.sum(p_clipped * np.log2(p_clipped))  # 预测熵
                betas[k] = np.exp(-self.gamma * H_k)

            # 联合权重: alpha_k = (alpha_k^0 * beta_k) / sum(...)
            joint = self.static_weights * betas
            joint_sum = joint.sum()
            if joint_sum > 0:
                weights = joint / joint_sum
            else:
                weights = self.static_weights

            # 加权概率融合
            for k in range(len(self.clf_names)):
                ensemble_probs[i] += weights[k] * all_probs[k, i]

        return ensemble_probs

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        预测设备身份 (不含拒识)。
        返回: shape (N,) 预测标签
        """
        probs = self.predict_proba_ensemble(X)
        return self.classes_[np.argmax(probs, axis=1)]

    def predict_with_rejection(self, X: np.ndarray
                               ) -> Tuple[np.ndarray, np.ndarray]:
        """
        预测设备身份 (含双阈值拒识)。

        返回:
          predictions: shape (N,) 预测标签 (-1 表示拒识)
          confidences: shape (N,) 最大置信度
        """
        probs = self.predict_proba_ensemble(X)

        predictions = np.full(len(X), -1, dtype=np.int32)
        confidences = np.zeros(len(X))

        for i in range(len(X)):
            sorted_probs = np.sort(probs[i])[::-1]
            max_prob = sorted_probs[0]
            second_prob = sorted_probs[1] if len(sorted_probs) > 1 else 0
            delta_p = max_prob - second_prob

            confidences[i] = max_prob

            # 双阈值拒识判决
            if max_prob >= self.tau_1 and delta_p >= self.tau_2:
                predictions[i] = self.classes_[np.argmax(probs[i])]

        return predictions, confidences

    def evaluate(self, X: np.ndarray, y: np.ndarray,
                 description: str = "") -> Dict:
        """
        评估分类性能。
        返回: 包含准确率、各分类器独立准确率、混淆矩阵等的字典
        """
        from sklearn.metrics import accuracy_score, confusion_matrix

        X_scaled = self.scaler.transform(X)
        result = {"description": description}

        # 各分类器独立准确率
        for name, clf in self.classifiers.items():
            y_pred = clf.predict(X_scaled)
            acc = accuracy_score(y, y_pred)
            result[f"acc_{name}"] = acc

        # 集成准确率 (不拒识)
        y_pred_ensemble = self.predict(X)
        acc_ensemble = accuracy_score(y, y_pred_ensemble)
        result["acc_ensemble"] = acc_ensemble

        # 混淆矩阵
        cm = confusion_matrix(y, y_pred_ensemble, labels=self.classes_)
        result["confusion_matrix"] = cm

        # 拒识结果
        y_pred_rej, confs = self.predict_with_rejection(X)
        accepted = y_pred_rej != -1
        n_accepted = accepted.sum()
        n_rejected = (~accepted).sum()
        acc_accepted = accuracy_score(y[accepted], y_pred_rej[accepted]) if n_accepted > 0 else 0
        result["n_accepted"] = int(n_accepted)
        result["n_rejected"] = int(n_rejected)
        result["acc_accepted"] = acc_accepted
        result["rejection_rate"] = n_rejected / len(y)

        return result
