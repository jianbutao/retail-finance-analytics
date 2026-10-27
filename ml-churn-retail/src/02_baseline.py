import pandas as pd
from pathlib import Path
REPORTS = Path(__file__).resolve().parents[1] / "reports"
REPORTS.mkdir(exist_ok=True)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, classification_report

df = pd.read_csv(REPORTS / "dataset.csv")
X, y = df.drop(columns=["customer_id","churn"]), df["churn"]
Xtr, Xte, ytr, yte = train_test_split(X,y,test_size=0.2,stratify=y,random_state=42)
sc = StandardScaler()
Xtr_s, Xte_s = sc.fit_transform(Xtr), sc.transform(Xte)
m = LogisticRegression(max_iter=1000, class_weight="balanced")
m.fit(Xtr_s, ytr)
p = m.predict_proba(Xte_s)[:,1]
print("LR AUC:", round(roc_auc_score(yte,p),4))
print(classification_report(yte, m.predict(Xte_s)))
