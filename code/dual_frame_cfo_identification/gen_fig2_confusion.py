"""Generate confusion matrix figure for ensemble learning device identification."""
import numpy as np
import pandas as pd
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, confusion_matrix

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

DATA_DIR = r'C:\Users\21398\Desktop\sophomore\SRTP\data\output_csv'
OUT_DIR = r'C:\Users\21398\Desktop\sophomore\SRTP\code\dual_frame_cfo_identification\results'

def load_dataset(folder):
    """Load all device CSVs from a folder, return X (12-dim) and y."""
    X_all, y_all = [], []
    for dev_id in range(1, 31):
        # find file matching device id
        for fname in os.listdir(os.path.join(DATA_DIR, folder)):
            if fname.endswith(f'device{dev_id}.csv'):
                fpath = os.path.join(DATA_DIR, folder, fname)
                data = pd.read_csv(fpath, header=None).values
                # columns 0-7: phase diff, 8-9: CFO
                phase = data[:, 0:8]
                cfo1 = data[:, 8:9]
                cfo2 = data[:, 9:10]
                cfo_mean = (data[:, 8:9] + data[:, 9:10]) / 2.0
                cfo_diff = data[:, 9:10] - data[:, 8:9]
                features = np.hstack([phase, cfo1, cfo2, cfo_mean, cfo_diff])  # 12-dim
                X_all.append(features)
                y_all.append(np.full(features.shape[0], dev_id))
                break
    return np.vstack(X_all), np.concatenate(y_all)

print("Loading data...")
X_train, y_train = load_dataset('train_dataset')
X_test_same, y_test_same = load_dataset('test_same_day')
X_test_another, y_test_another = load_dataset('test_another_day')
print(f"Train: {X_train.shape}, Test same: {X_test_same.shape}, Test another: {X_test_another.shape}")

# Standardize
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_same_s = scaler.transform(X_test_same)
X_test_another_s = scaler.transform(X_test_another)

# Train classifiers
classifiers = {
    'SVM': SVC(kernel='rbf', C=10, gamma='scale', probability=True, random_state=42),
    'RF': RandomForestClassifier(n_estimators=200, max_depth=None, random_state=42, n_jobs=-1),
    'LDA': LinearDiscriminantAnalysis(),
    'KNN': KNeighborsClassifier(n_neighbors=5, n_jobs=-1),
}

# Static weights (based on typical relative performance)
static_weights = {'SVM': 0.30, 'RF': 0.30, 'LDA': 0.15, 'KNN': 0.25}

print("Training classifiers...")
trained = {}
for name, clf in classifiers.items():
    print(f"  Training {name}...")
    clf.fit(X_train_s, y_train)
    trained[name] = clf
    train_acc = accuracy_score(y_train, clf.predict(X_train_s))
    print(f"  {name} train accuracy: {train_acc:.4f}")

def ensemble_predict(X, trained_clfs, weights):
    """Weighted probability fusion prediction."""
    classes = trained_clfs['SVM'].classes_
    n_classes = len(classes)
    n_samples = X.shape[0]
    fused_probs = np.zeros((n_samples, n_classes))

    for name, clf in trained_clfs.items():
        probs = clf.predict_proba(X)
        # Dynamic confidence: entropy-based
        entropy = -np.sum(probs * np.log(probs + 1e-12), axis=1, keepdims=True)
        max_entropy = np.log(n_classes)
        confidence = 1.0 - entropy / max_entropy  # high confidence = low entropy
        # Combined weight
        w = weights[name] * confidence
        fused_probs += w * probs

    # Normalize
    fused_probs /= fused_probs.sum(axis=1, keepdims=True)
    predictions = classes[np.argmax(fused_probs, axis=1)]
    return predictions

print("Predicting...")
y_pred_same = ensemble_predict(X_test_same_s, trained, static_weights)
y_pred_another = ensemble_predict(X_test_another_s, trained, static_weights)

acc_same = accuracy_score(y_test_same, y_pred_same)
acc_another = accuracy_score(y_test_another, y_pred_another)
print(f"Ensemble accuracy - Same day: {acc_same:.4f}, Another day: {acc_another:.4f}")

# Confusion matrices
cm_same = confusion_matrix(y_test_same, y_pred_same, labels=range(1, 31))
cm_another = confusion_matrix(y_test_another, y_pred_another, labels=range(1, 31))

# Normalize
cm_same_norm = cm_same.astype(float) / cm_same.sum(axis=1, keepdims=True)
cm_another_norm = cm_another.astype(float) / cm_another.sum(axis=1, keepdims=True)

# Plot
fig, axes = plt.subplots(1, 2, figsize=(18, 8), dpi=300)

device_labels = [f'D{i}' for i in range(1, 31)]

for ax, cm_norm, title, acc in [
    (axes[0], cm_same_norm, 'Same-Day Test (同日测试)', acc_same),
    (axes[1], cm_another_norm, 'Cross-Day Test (跨日测试)', acc_another),
]:
    im = ax.imshow(cm_norm, interpolation='nearest', cmap='Blues', vmin=0, vmax=1)
    ax.set_title(f'{title}\nAccuracy: {acc:.2%}', fontsize=13, fontweight='bold', pad=10)
    ax.set_xlabel('Predicted Device (预测设备)', fontsize=11)
    ax.set_ylabel('True Device (真实设备)', fontsize=11)
    ax.set_xticks(range(30))
    ax.set_yticks(range(30))
    ax.set_xticklabels(device_labels, fontsize=5.5, rotation=90)
    ax.set_yticklabels(device_labels, fontsize=5.5)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Normalized Accuracy', fontsize=9)

fig.suptitle('Ensemble Learning Confusion Matrix (集成学习混淆矩阵)', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'fig_per_device_accuracy.png'),
            dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
plt.close()
print(f"Figure 2 saved successfully.")
