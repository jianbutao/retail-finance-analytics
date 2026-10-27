from pathlib import Path
import os, psycopg
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

conn = psycopg.connect(
    host=os.getenv("PG_HOST"), port=os.getenv("PG_PORT"),
    dbname=os.getenv("PG_DATABASE"), user=os.getenv("PG_USER"),
    password=os.getenv("PG_PASSWORD"), connect_timeout=10)
conn.read_only = True
cur = conn.cursor()
cur.execute("""
  SELECT MIN(invoice_date), MAX(invoice_date),
         COUNT(DISTINCT customer_id), COUNT(*)
  FROM analytics.transactions
  WHERE include_customer_sales = TRUE""")
print("起止日期/客户数/行数:", cur.fetchone())
conn.close()
