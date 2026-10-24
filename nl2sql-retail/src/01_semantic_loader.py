"""阶段1：读取语义层YAML，生成给大模型看的「数据说明书」。"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_DIR = ROOT / "semantic"


def load_yaml(filename):
    with (SEMANTIC_DIR / filename).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_schema_prompt():
    tables_doc = load_yaml("tables.yaml")
    metrics_doc = load_yaml("metrics.yaml")
    lines = []

    db = tables_doc["database"]
    lines.append("# 数据库说明")
    lines.append(
        f"数据库：{db['name']}，schema：{db['schema']}，金额单位：{db['currency']}"
    )
    lines.append(db["currency_note"])

    for table in tables_doc["tables"]:
        lines.append("")
        lines.append(f"## 表 {table['name']}")
        lines.append(table["description"])
        lines.append("固定过滤条件：")
        for rule in table.get("must_filter", []):
            lines.append(
                f"  - {rule['field']} = '{rule['value']}'（{rule['reason']}）"
            )
        lines.append("字段说明：")
        for col in table["columns"]:
            values = f"，取值：{'、'.join(col['values'])}" if col.get("values") else ""
            lines.append(
                f"  - {col['name']}（{col['cn']}，{col['type']}）：{col['desc']}{values}"
            )

    lines.append("")
    lines.append("## 固定时间口径")
    for window in tables_doc.get("time_windows", []):
        lines.append(
            f"  - {window['name']}：{window.get('start', '')} 至 "
            f"{window.get('end', '')}（{window['note']}）"
        )

    lines.append("")
    lines.append("## 可用业务指标（只能使用以下口径，禁止自行编造指标）")
    for metric in metrics_doc["metrics"]:
        lines.append(f"  - {metric['name']}（{metric['id']}）")
        lines.append(f"      同义词：{'、'.join(metric['synonyms'])}")
        lines.append(f"      口径：{metric['sql']}")
        if metric.get("known_result"):
            lines.append(f"      已知结果：{metric['known_result']}")
        lines.append(f"      边界：{metric['boundary']}")

    return "\n".join(lines)


if __name__ == "__main__":
    prompt = build_schema_prompt()
    print(prompt)
    print(f"\n\n说明书总长度：{len(prompt)} 字符")
