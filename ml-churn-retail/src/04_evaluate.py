from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (roc_curve, roc_auc_score, precision_recall_curve,
                             average_precision_score)

REPORTS = Path(__file__).resolve().parents[1] / "reports"
REPORTS.mkdir(exist_ok=True)

df = pd.read_csv(REPORTS / "dataset.csv")
X = df.drop(columns=["customer_id", "churn"])
y = df["churn"]
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
sc = StandardScaler()
Xtr_s, Xte_s = sc.fit_transform(Xtr), sc.transform(Xte)

model = LogisticRegression(max_iter=1000, class_weight="balanced").fit(Xtr_s, ytr)
proba = model.predict_proba(Xte_s)[:, 1]

fpr, tpr, _ = roc_curve(yte, proba)
auc = roc_auc_score(yte, proba)
prauc = average_precision_score(yte, proba)
ks = (tpr - fpr).max()
order = np.argsort(proba)[::-1]
top_n = int(0.2 * len(yte))
recall_at_k = yte.iloc[order[:top_n]].sum() / yte.sum()
lift_at_k = yte.iloc[order[:top_n]].mean() / yte.mean()

print(f"AUC={auc:.4f}  PR-AUC={prauc:.4f}  KS={ks:.4f}")
print(f"Recall@20%={recall_at_k:.4f}  Lift@20%={lift_at_k:.4f}")
coef = pd.Series(model.coef_[0], index=X.columns).sort_values(ascending=False)
print("\n标准化系数(正=促流失 / 负=防流失):")
print(coef.round(3).to_string())

pipe = Pipeline([("sc", StandardScaler()),
                 ("lr", LogisticRegression(max_iter=1000, class_weight="balanced"))])
cv_auc = cross_val_score(pipe, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=42),
                         scoring="roc_auc")
print(f"\n5折交叉验证 AUC: {cv_auc.round(3)} 均值={cv_auc.mean():.3f}")

fig, axes = plt.subplots(1, 2, figsize=(10, 4))
axes[0].plot(fpr, tpr, color="#1f77b4", label=f"AUC={auc:.3f}")
axes[0].plot([0, 1], [0, 1], "--", color="gray")
axes[0].set_title("ROC Curve"); axes[0].set_xlabel("False Positive Rate")
axes[0].set_ylabel("True Positive Rate"); axes[0].legend()
prec, rec, _ = precision_recall_curve(yte, proba)
axes[1].plot(rec, prec, color="#d62728", label=f"PR-AUC={prauc:.3f}")
axes[1].set_title("Precision-Recall Curve"); axes[1].set_xlabel("Recall")
axes[1].set_ylabel("Precision"); axes[1].legend()
plt.tight_layout()
fig.savefig(REPORTS / "roc_pr.png", dpi=150)
print(f"\n图已保存到 reports/roc_pr.png")
