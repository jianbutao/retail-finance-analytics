"""阶段3/5：golden评估集三层评分，支持输出不同版本报告。
用法：
  python 03_evaluate.py baseline    # 优化前
  python 03_evaluate.py optimized   # 优化后
三层：执行成功率、结果一致率、口径正确率。
"""
import importlib.util
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

import psycopg
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
REPORT_NAME = sys.argv[1] if len(sys.argv) > 1 else "baseline"


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "src" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


loader = load_module("semantic_loader", "01_semantic_loader.py")
nl2sql = load_module("nl2sql", "02_nl2sql.py")


def execute_reference(sql):
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
        cur.execute("SET LOCAL statement_timeout = 30000")
        cur.execute(sql)
        return cur.fetchall()
    finally:
        conn.close()


def norm_cell(v):
    if v is None:
        return None
    if isinstance(v, (int, float, Decimal)):
        return round(float(v), 2)
    return str(v).strip()


def close(a, b):
    if a is None or b is None:
        return a is None and b is None
    try:
        fa, fb = float(a), float(b)
        if abs(fb) < 1:
            return abs(fa - fb) < 0.02
        return abs(fa - fb) / abs(fb) < 0.01
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


def result_match(ref_rows, model_rows, result_type):
    if result_type == "scalar":
        if not ref_rows or not model_rows:
            return not ref_rows and not model_rows
        return close(ref_rows[0][0], model_rows[0][0])
    if len(ref_rows) != len(model_rows):
        return False
    if ref_rows and len(ref_rows[0]) != len(model_rows[0]):
        return False

    def flat(rows):
        return sorted(
            [norm_cell(v) for row in rows for v in row],
            key=lambda x: ("__none__" if x is None else str(x)),
        )

    return flat(ref_rows) == flat(model_rows)


def semantic_ok(model_sql, required):
    lowered = model_sql.lower()
    if "source_batch" not in lowered:
        return False
    return all(token.lower() in lowered for token in required)


def evaluate():
    with (ROOT / "evaluation" / "golden_questions.yaml").open(encoding="utf-8") as f:
        golden = yaml.safe_load(f)["questions"]

    schema_prompt = loader.build_schema_prompt()
    details = []
    counts = {"execution": 0, "result": 0, "semantic": 0}
    cat_stats = {}

    for i, item in enumerate(golden, 1):
        qid = item["id"]
        category = item["category"]
        question = item["question"]
        required = item.get("required_tokens", [])
        rtype = item.get("result_type", "scalar")
        print(f"[{i}/{len(golden)}] {qid} {question}")

        ref_rows = execute_reference(item["reference_sql"])

        execution_pass = False
        result_pass = False
        semantic_pass = False
        model_sql = ""
        error = ""
        model_rows = []

        try:
            model_sql, _ = nl2sql.generate_sql(question, schema_prompt)
            safe_sql = nl2sql.validate_sql(model_sql)
            semantic_pass = semantic_ok(safe_sql, required)
            _, model_rows, _ = nl2sql.run_query(safe_sql)
            execution_pass = True
            result_pass = result_match(ref_rows, model_rows, rtype)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            print("    失败:", error[:120])

        for key, passed in [
            ("execution", execution_pass),
            ("result", result_pass),
            ("semantic", semantic_pass),
        ]:
            if passed:
                counts[key] += 1

        cat = cat_stats.setdefault(
            category,
            {"total": 0, "execution": 0, "result": 0, "semantic": 0},
        )
        cat["total"] += 1
        for key, passed in [
            ("execution", execution_pass),
            ("result", result_pass),
            ("semantic", semantic_pass),
        ]:
            if passed:
                cat[key] += 1

        details.append(
            {
                "id": qid,
                "category": category,
                "question": question,
                "execution_pass": execution_pass,
                "result_pass": result_pass,
                "semantic_pass": semantic_pass,
                "required_tokens": required,
                "model_sql": model_sql,
                "error": error,
                "reference_result": [list(r) for r in ref_rows[:5]],
                "model_result": [list(r) for r in model_rows[:5]],
            }
        )
        time.sleep(0.4)

    n = len(golden)
    report = {
        "version": REPORT_NAME,
        "total": n,
        "execution_success_rate": round(counts["execution"] / n * 100, 2),
        "result_match_rate": round(counts["result"] / n * 100, 2),
        "semantic_correct_rate": round(counts["semantic"] / n * 100, 2),
        "by_category": cat_stats,
        "details": details,
    }
    out_path = ROOT / "reports" / f"{REPORT_NAME}_report.json"
    out_path.parent.mkdir(exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "=" * 60)
    print(f"【{REPORT_NAME}】评估结果（共{n}条）")
    print(f"执行成功率：{report['execution_success_rate']}%  ({counts['execution']}/{n})")
    print(f"结果一致率：{report['result_match_rate']}%  ({counts['result']}/{n})")
    print(f"口径正确率：{report['semantic_correct_rate']}%  ({counts['semantic']}/{n})")
    print("=" * 60)
    print("分层结果：")
    for cat, s in cat_stats.items():
        print(f"  {cat}: {s['total']}条，结果一致 {s['result']}/{s['total']}")
    print("明细已保存：", out_path)


if __name__ == "__main__":
    evaluate()
