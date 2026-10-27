from pathlib import Path
import os, numpy as np, pandas as pd, psycopg
from pathlib import Path
REPORTS = Path(__file__).resolve().parents[1] / "reports"
REPORTS.mkdir(exist_ok=True)
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

OBS_START, OBS_END = "2011-01-01", "2011-07-01"   # 观察窗口
PRED_START, PRED_END = "2011-07-01", "2011-10-01"  # 预测窗口
REF_DATE = pd.Timestamp(OBS_END)

conn = psycopg.connect(host=os.getenv("PG_HOST"),port=os.getenv("PG_PORT"),
    dbname=os.getenv("PG_DATABASE"),user=os.getenv("PG_USER"),
    password=os.getenv("PG_PASSWORD"))
conn.read_only=True
sql = """
WITH t AS (
  SELECT customer_id, invoice_no, invoice_date, line_amount, stock_code, quantity
  FROM analytics.transactions
  WHERE include_customer_sales=TRUE AND invoice_date>=%s AND invoice_date<%s)
SELECT customer_id,
  (%s::date - MAX(DATE(invoice_date))) AS recency_days,
  COUNT(DISTINCT invoice_no) AS frequency,
  COALESCE(SUM(line_amount),0) AS monetary,
  COUNT(DISTINCT stock_code) AS n_products,
  COALESCE(AVG(line_amount),0) AS avg_order_value,
  COUNT(DISTINCT DATE(invoice_date)) AS active_days
FROM t GROUP BY customer_id"""
feat = pd.read_sql(sql, conn, params=(OBS_START,OBS_END,REF_DATE))
churned = pd.read_sql("""
  SELECT DISTINCT customer_id FROM analytics.transactions
  WHERE include_customer_sales=TRUE AND invoice_date>=%s AND invoice_date<%s""",
  conn, params=(PRED_START,PRED_END))
conn.close()

feat["churn"] = (~feat["customer_id"].isin(churned["customer_id"])).astype(int)
print("样本数:", len(feat), "流失率:", feat["churn"].mean().round(3))
feat.to_csv(REPORTS / "dataset.csv", index=False)
