import pandas as pd
from pathlib import Path
REPORTS = Path(__file__).resolve().parents[1] / "reports"
REPORTS.mkdir(exist_ok=True)
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score

df = pd.read_csv(REPORTS / "dataset.csv")
X, y = df.drop(columns=["customer_id","churn"]), df["churn"]
Xtr, Xte, ytr, yte = train_test_split(X,y,test_size=0.2,stratify=y,random_state=42)
models = {
 "RF": RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=42),
 "GB": GradientBoostingClassifier(random_state=42),
}
for name, m in models.items():
    m.fit(Xtr, ytr)
    p = m.predict_proba(Xte)[:,1]
    print(name, "AUC:", round(roc_auc_score(yte,p),4),
          "PR-AUC:", round(average_precision_score(yte,p),4))
