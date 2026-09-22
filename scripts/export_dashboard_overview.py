"""导出看板总览指标；不修改交易明细和既有分析结果。"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from retail_finance.config import resolve_path
from retail_finance.metrics import overview


def main():
    batch_dir = resolve_path("cleaned_batch")
    business_dir = resolve_path("business_report")
    output = business_dir / "dashboard_overview.json"

    if output.exists():
        raise FileExistsError(f"已存在，未覆盖：{output}")

    for directory in (batch_dir, business_dir):
        if not (directory / "SUCCESS.txt").is_file():
            raise FileNotFoundError(f"缺少归档成功标记：{directory}")

    source = batch_dir / "classified_transactions.parquet"
    monthly_path = business_dir / "monthly_metrics.csv"

    transactions = pd.read_parquet(
        source,
        columns=[
            "quantity", "unit_price", "invoice_no", "customer_id",
            "include_product_sales", "include_product_cancellations",
        ],
    )
    totals = overview(transactions)
    monthly = pd.read_csv(monthly_path, index_col=0)

    for column, key in (
        ("gross_amount", "gross_milli"),
        ("cancel_amount", "cancel_milli"),
        ("net_amount", "net_milli"),
    ):
        if abs(monthly[column].sum() - totals[key] / 1000) > 0.01:
            raise ValueError(f"月度表与总览不一致：{column}")

    source_hashes = {}
    for path in (source, monthly_path):
        with path.open("rb") as file:
            source_hashes[path.relative_to(ROOT).as_posix()] = (
                hashlib.file_digest(file, "sha256").hexdigest()
            )

    payload = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_batch": batch_dir.name,
        "source_sha256": source_hashes,
        "totals": totals,
    }
    text = json.dumps(
        payload, ensure_ascii=False, indent=2, allow_nan=False
    )

    with output.open("x", encoding="utf-8") as file:
        file.write(text)

    saved = json.loads(output.read_text(encoding="utf-8"))
    if saved != payload:
        raise ValueError("指标快照重新读取验证失败")

    print("指标快照保存并验证通过：", output)
    print("正向金额：", f"{totals['gross_milli'] / 1000:,.2f}")
    print("取消金额：", f"{totals['cancel_milli'] / 1000:,.2f}")
    print("交易净额：", f"{totals['net_milli'] / 1000:,.2f}")
    print("已识别购买客户数：", totals["identified_customers"])


if __name__ == "__main__":
    main()