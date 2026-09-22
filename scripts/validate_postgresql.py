"""Read-only SQL/Python reconciliation for the fixed retail learning batch."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from getpass import getpass
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

BATCH = "20260917T121850_455264Z"
QUERY_FILES = {
    "03_core_metrics.sql": ["overall", "monthly_sales"],
    "04_monthly_growth.sql": ["monthly_growth"],
    "05_monthly_customer_concentration.sql": ["monthly_customers"],
}


def rounded(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def amount(milliunits):
    return rounded(Decimal(int(milliunits)) / 1000)


def percent(numerator, denominator):
    if denominator == 0:
        return None
    return rounded(Decimal(int(numerator)) / Decimal(int(denominator)) * 100)


def build_references(path):
    """Use integer thousandths, avoiding float rounding and SQL implementation reuse."""
    data = pd.read_parquet(path)
    if len(data) != 1_044_848:
        raise ValueError("Unexpected source row count")
    prices = data["unit_price"].to_numpy()
    if not np.isfinite(prices).all():
        raise ValueError("Non-finite price")
    milli_prices = np.rint(prices * 1000).astype("int64")
    if not np.allclose(prices, milli_prices / 1000, rtol=0, atol=1e-9):
        raise ValueError("Source price exceeds the three-decimal database scale")
    data["milli_amount"] = data["quantity"] * milli_prices
    if not np.allclose(data["line_amount"], data["milli_amount"] / 1000,
                       rtol=0, atol=1e-7):
        raise ValueError("Source line amount does not reconcile with quantity times price")
    data["month"] = data["invoice_date"].dt.to_period("M")
    data["day"] = data["invoice_date"].dt.normalize()
    sales = data.loc[data["include_product_sales"]]
    cancels = data.loc[data["include_product_cancellations"]]
    identified = data.loc[data["include_customer_sales"]]
    gross = int(sales["milli_amount"].sum())
    cancellation = -int(cancels["milli_amount"].sum())
    refs = {"overall": pd.DataFrame([{
        "retained_rows": len(data),
        "product_gross_amount": amount(gross),
        "product_cancel_amount": amount(cancellation),
        "product_net_amount": amount(gross - cancellation),
        "product_sales_orders": sales["invoice_no"].nunique(),
        "identified_buyers": identified["customer_id"].nunique(),
    }])}
    months = sales.groupby("month").agg(
        milli_amount=("milli_amount", "sum"),
        sales_orders=("invoice_no", "nunique"),
        recorded_sales_days=("day", "nunique"),
    )
    monthly_sales, growth = [], []
    previous_month, previous_value = None, None
    for month, row in months.iterrows():
        value = int(row["milli_amount"])
        monthly_sales.append({
            "month": str(month), "gross_amount": amount(value),
            "sales_orders": int(row["sales_orders"]),
            "recorded_sales_days": int(row["recorded_sales_days"]),
        })
        comparable = (previous_month is not None and month == previous_month + 1
                      and str(month) != "2011-12")
        growth.append({
            "month": str(month), "gross_amount": amount(value),
            "previous_amount": amount(previous_value) if previous_value is not None else None,
            "gross_mom_pct": percent(value - previous_value, previous_value)
                if comparable else None,
        })
        previous_month, previous_value = month, value
    refs["monthly_sales"] = pd.DataFrame(monthly_sales)
    refs["monthly_growth"] = pd.DataFrame(growth)
    customer_totals = identified.groupby(["month", "customer_id"])["milli_amount"].sum()
    concentration = []
    for month in months.index:
        # Ties do not change sums of the selected top-N amounts.
        values = customer_totals.loc[month].sort_values(ascending=False)
        total = int(values.sum())
        top1, top10 = int(values.iloc[0]), int(values.head(10).sum())
        all_amount = int(months.loc[month, "milli_amount"])
        concentration.append({
            "month": str(month), "active_identified_customers": len(values),
            "identified_coverage_pct": percent(total, all_amount),
            "top1_share_identified_pct": percent(top1, total),
            "top10_share_identified_pct": percent(top10, total),
            "top10_share_all_pct": percent(top10, all_amount),
            "boundary_truncated": str(month) == "2011-12",
        })
    refs["monthly_customers"] = pd.DataFrame(concentration)
    return refs


def compare(name, expected, actual):
    """Compare schema, month keys, nulls, booleans, counts and rounded decimals."""
    results = []
    if list(expected.columns) != list(actual.columns):
        return [{"query": name, "key": "schema", "metric": "columns",
                 "expected": str(list(expected.columns)),
                 "actual": str(list(actual.columns)), "passed": False}]
    expected, actual = expected.copy(), actual.copy()
    if "month" in expected:
        actual["month"] = pd.to_datetime(actual["month"]).dt.strftime("%Y-%m")
        if actual["month"].duplicated().any() or set(actual["month"]) != set(expected["month"]):
            return [{"query": name, "key": "months", "metric": "month_keys",
                     "expected": str(expected["month"].tolist()),
                     "actual": str(actual["month"].tolist()), "passed": False}]
        expected = expected.set_index("month").sort_index()
        actual = actual.set_index("month").sort_index()
    if len(expected) != len(actual):
        return [{"query": name, "key": "rows", "metric": "row_count",
                 "expected": len(expected), "actual": len(actual), "passed": False}]
    for i, key in enumerate(expected.index):
        for column in expected.columns:
            e, a = expected.iloc[i][column], actual.iloc[i][column]
            if pd.isna(e) or pd.isna(a):
                passed = bool(pd.isna(e) and pd.isna(a))
            elif isinstance(e, (bool, np.bool_)):
                passed = isinstance(a, (bool, np.bool_)) and bool(a) == bool(e)
            else:
                passed = Decimal(str(e)) == Decimal(str(a))
            results.append({"query": name, "key": str(key), "metric": column,
                            "expected": str(e), "actual": str(a), "passed": passed})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(r"D:\Retail-finance"))
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--prepare-only", action="store_true",
                        help="Check local inputs and Python references; no database or file writes")
    args = parser.parse_args()
    batch_dir = args.project / "data" / "processed" / BATCH
    if not (batch_dir / "SUCCESS.txt").is_file():
        raise FileNotFoundError("Verified source batch marker not found")
    source = batch_dir / "classified_transactions.parquet"
    scripts = {}
    for filename in QUERY_FILES:
        text = (args.project / "sql" / filename).read_text(encoding="utf-8-sig")
        body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("--")).strip()
        if not body or BATCH not in body:
            raise ValueError(f"SQL body or expected batch missing: {filename}")
        scripts[filename] = text
    references = build_references(source)
    if args.prepare_only:
        for name, frame in references.items():
            print(f"{name}: {len(frame)} reference rows")
        print("Local preparation passed. No database query or file write performed.")
        return

    comparisons = []
    password = getpass("PostgreSQL password (hidden): ")
    try:
        with psycopg.connect(host="localhost", port=5432, dbname="retail_finance",
                             user=args.user, password=password, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '120s'")
                for filename, names in QUERY_FILES.items():
                    cur.execute(scripts[filename])
                    for i, name in enumerate(names):
                        if cur.description is None:
                            raise ValueError(f"Expected SELECT result: {filename}")
                        actual = pd.DataFrame(cur.fetchall(),
                                              columns=[col.name for col in cur.description])
                        comparisons.extend(compare(name, references[name], actual))
                        if i < len(names) - 1 and not cur.nextset():
                            raise ValueError(f"Missing query result: {filename}")
                        print(f"Checked {name}: {len(actual)} SQL rows")
                    if cur.nextset():
                        raise ValueError(f"Unexpected extra statement: {filename}")
    finally:
        del password

    report = pd.DataFrame(comparisons)
    passed = bool(report["passed"].all())
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output = args.project / "reports" / "sql_validation" / run
    output.mkdir(parents=True, exist_ok=False)
    report.to_csv(output / "checks.csv", index=False, encoding="utf-8-sig")
    with source.open("rb") as source_file:
        source_hash = hashlib.file_digest(source_file, "sha256").hexdigest()
    summary = {
        "source_batch": BATCH, "database": "retail_finance", "read_only": True,
        "source_sha256": source_hash,
        "sql_sha256": {name: hashlib.sha256(text.encode("utf-8")).hexdigest()
                       for name, text in scripts.items()},
        "checks": len(report), "failed": int((~report["passed"]).sum()),
        "status": "PASS" if passed else "FAIL",
        "reference_method": "Integer thousandths; Decimal ROUND_HALF_UP for displayed results",
        "scope": "Aggregate validation; not a field-by-field database copy audit",
        "versions": {"pandas": pd.__version__, "psycopg": psycopg.__version__},
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"{summary['status']}: {len(report)} checks, {summary['failed']} failures")
    print(f"Report: {output}")
    if not passed:
        print(report.loc[~report["passed"]].to_string(index=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
