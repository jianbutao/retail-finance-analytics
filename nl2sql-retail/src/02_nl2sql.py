"""阶段2：NL2SQL引擎（命令行版）。
中文问题 -> 基于语义层生成SQL -> 只读执行 -> 打印结果。
安全护栏：只读账号、禁止写操作、只允许单条SELECT、强制LIMIT、超时30秒。
"""
import importlib.util
import os
import re
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from openai import OpenAI
from tabulate import tabulate

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# 加载阶段1的语义层
_spec = importlib.util.spec_from_file_location(
    "semantic_loader", ROOT / "src" / "01_semantic_loader.py"
)
semantic_loader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(semantic_loader)

MAX_ROWS = 100
QUERY_TIMEOUT_MS = 30000
BATCH = "20260917T121850_455264Z"

SYSTEM_PROMPT = """你是一名严格的PostgreSQL数据分析工程师。
任务：根据用户的中文业务问题，生成一条且仅一条可执行的PostgreSQL只读SELECT语句。

硬性规则：
1. 只能查询表 analytics.transactions，禁止其他表，禁止任何写操作。
2. 所有业务查询必须带 WHERE source_batch = '20260917T121850_455264Z'。
3. 只能使用数据说明书中列出的字段和指标口径，禁止编造字段或指标。
4. 金额单位为GBP，汇总金额用 ROUND(..., 2) 保留两位小数。
5. 统计订单数必须用 COUNT(DISTINCT invoice_no)。
6. 按月分组用 DATE_TRUNC('month', invoice_date)::date；按日分组用 invoice_date::date。
7. 列别名统一用英文小写蛇形命名（如 gross_amount、order_count、buyer_count），禁止使用中文别名。
8. 排名类需求（TOP N、最高、前N、最大的几个）：必须用 LIMIT N，N取业务问题中明确要求的数量，如TOP5就写LIMIT 5，不要写LIMIT 100。
9. 做排名（ORDER BY 聚合金额 DESC）时，必须在 WHERE 中直接过滤业务口径标志（如 include_product_sales = TRUE），不要只靠 FILTER 子句，避免无此类业务的分组产生NULL值排到最前。
10. 若确实需要保留可能为NULL的分组，ORDER BY 时必须加 NULLS LAST。
11. 统计商品种类数、商品数必须加 include_product_sales = TRUE。
12. 非排名查询语句末尾加 LIMIT 100；排名查询按规则8写LIMIT N。

输出格式：只输出一条SQL语句，用 ```sql ``` 包裹，不要任何解释或前后缀。"""


def generate_sql(question, schema_prompt):
    client = OpenAI(
        base_url=os.getenv("ARK_BASE_URL"),
        api_key=os.getenv("ARK_API_KEY"),
    )
    resp = client.chat.completions.create(
        model=os.getenv("ARK_MODEL"),
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"【数据说明书】\n{schema_prompt}\n\n【业务问题】{question}",
            },
        ],
    )
    sql = extract_sql(resp.choices[0].message.content)
    usage = resp.usage
    return sql, usage


def extract_sql(text):
    match = re.search(r"```sql\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip().rstrip(";")


def validate_sql(sql):
    lowered = sql.strip().lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise ValueError("只允许 SELECT 或 WITH 查询")
    forbidden = [
        "insert", "update", "delete", "drop", "alter", "truncate",
        "create", "grant", "revoke", "copy", "vacuum",
    ]
    for word in forbidden:
        if re.search(rf"\b{word}\b", lowered):
            raise ValueError(f"检测到禁用操作: {word}")
    body = sql.strip().rstrip(";")
    if ";" in body:
        raise ValueError("只允许单条语句，不能包含分号")
    if not re.search(r"\blimit\b", body, re.IGNORECASE):
        body = body + " LIMIT 100"
    return body


def run_query(sql):
    conn = psycopg.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        dbname=os.getenv("PG_DATABASE"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        connect_timeout=10,
    )
    conn.read_only = True
    try:
        cur = conn.cursor()
        cur.execute(f"SET LOCAL statement_timeout = {QUERY_TIMEOUT_MS}")
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchmany(MAX_ROWS + 1)
        truncated = len(rows) > MAX_ROWS
        return columns, rows[:MAX_ROWS], truncated
    finally:
        conn.close()


def ask(question):
    schema_prompt = semantic_loader.build_schema_prompt()
    sql, usage = generate_sql(question, schema_prompt)
    print("=" * 60)
    print("【生成的SQL】")
    print(sql)
    print("=" * 60)
    safe_sql = validate_sql(sql)
    columns, rows, truncated = run_query(safe_sql)
    print("【查询结果】")
    print(tabulate(rows, headers=columns, tablefmt="github"))
    if truncated:
        print(f"（结果超过{MAX_ROWS}行，仅显示前{MAX_ROWS}行）")
    print("-" * 60)
    print(
        f"token用量：输入{usage.prompt_tokens}，输出{usage.completion_tokens}"
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("请输入业务问题：").strip()
    ask(question)
