"""阶段0连通性验证：只读连接数据库 + 调用豆包API。"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def test_db():
    print("=== 1. 数据库连接测试（只读）===")
    conn = psycopg.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT"),
        dbname=os.getenv("PG_DATABASE"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        connect_timeout=10,
    )
    conn.read_only = True
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print("SELECT 1 =", cur.fetchone()[0])
    cur.execute(
        "SELECT schemaname || '.' || tablename FROM pg_tables "
        "WHERE schemaname NOT IN ('pg_catalog','information_schema') "
        "ORDER BY schemaname, tablename"
    )
    tables = [r[0] for r in cur.fetchall()]
    print(f"发现 {len(tables)} 张表: {tables}")
    conn.close()


def test_llm():
    print("\n=== 2. 豆包API测试 ===")
    client = OpenAI(
        base_url=os.getenv("ARK_BASE_URL"),
        api_key=os.getenv("ARK_API_KEY"),
    )
    resp = client.chat.completions.create(
        model=os.getenv("ARK_MODEL"),
        messages=[
            {"role": "user", "content": "用一句话介绍你自己，并说明你能把中文问题翻译成SQL。"}
        ],
    )
    print(resp.choices[0].message.content)


if __name__ == "__main__":
    test_db()
    test_llm()
