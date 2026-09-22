"""Offline regression validation; writes only a fresh stage1 report directory."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from retail_finance.config import load_config, resolve_path
from retail_finance.cleaning import read_raw, remove_cross_sheet_copies, classify_transactions
from retail_finance.metrics import overview, monthly_metrics, product_structure, customer_structure
from retail_finance.segmentation import build_rfm, score_rfm, segment_summary
from retail_finance.forecasting import weekly_history, baselines, split_time, fit_ridge, evaluate
from retail_finance.plots import plot_segments


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def compare_table(actual, expected, label):
    """CSV has no dtype metadata. Normalize keys, but compare every selected value."""
    actual, expected = actual.copy(), expected.copy()
    actual.index = actual.index.astype(str)
    expected.index = expected.index.astype(str)
    actual.index.name = expected.index.name
    pd.testing.assert_frame_equal(actual.sort_index(), expected.sort_index(),
        check_dtype=False, check_exact=False, rtol=1e-12, atol=1e-7, obj=label)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", action="store_true", help="Re-read original Excel and compare all cleaned fields")
    args = parser.parse_args()
    config = load_config()
    batch = resolve_path("cleaned_batch")
    customer_dir, business_dir = resolve_path("customer_report"), resolve_path("business_report")
    forecast_dir = resolve_path("forecast_report")
    for directory in [batch, business_dir, forecast_dir]:
        if not (directory / "SUCCESS.txt").is_file():
            raise ValueError(f"Missing success marker: {directory}")
    rules = json.loads((batch / "metadata.json").read_text(encoding="utf-8"))
    data = pd.read_parquet(batch / "classified_transactions.parquet")
    checked = []
    if digest(resolve_path("raw_file")) != rules["source_sha256"]:
        raise AssertionError("Raw source hash differs")
    checked.append("raw_sha256")
    if args.raw:
        print("Reading raw Excel and rebuilding cleaning in memory...", flush=True)
        raw = read_raw(resolve_path("raw_file"))
        kept, excluded = remove_cross_sheet_copies(raw)
        rebuilt = classify_transactions(kept, rules)
        if len(raw) != 1067371 or len(excluded) != 22523:
            raise AssertionError("Raw or exclusion row count changed")
        reference_excluded = pd.read_parquet(batch / "excluded_cross_sheet_duplicates.parquet")
        # Description string storage differs across the archive boundary; preserve null values.
        for frame in [excluded, reference_excluded]:
            frame["description"] = frame["description"].astype("string")
        # Archives intentionally omit the temporary pandas row index. Compare by
        # persistent source identity, not by the discarded in-memory position.
        keys = ["source_sheet", "source_excel_row"]
        for actual, expected in [(excluded, reference_excluded), (rebuilt, data)]:
            if actual.duplicated(keys).any() or expected.duplicated(keys).any():
                raise AssertionError("Nonunique source identifiers")
            pd.testing.assert_frame_equal(
                actual.set_index(keys).sort_index(), expected.set_index(keys).sort_index(),
                check_dtype=False, check_exact=True)
        checked.append("raw_cleaning_all_fields_and_excluded_rows")
        del raw, kept, excluded, rebuilt, reference_excluded
    totals = overview(data)
    expected = {"rows": 1044848, "gross_milli": 19700954457, "cancel_milli": 719692940,
                "net_milli": 18981261517, "sales_orders": 39516, "identified_customers": 5852}
    for key, value in expected.items():
        if totals[key] != value:
            raise AssertionError(f"Baseline differs: {key}")
    if data.duplicated(["source_sheet", "source_excel_row"]).any():
        raise AssertionError("Duplicate source keys")
    checked.append("overview_and_source_keys")
    monthly = monthly_metrics(data)
    reference = pd.read_csv(business_dir / "monthly_metrics.csv", index_col=0)
    compare_table(monthly, reference[monthly.columns], "monthly metrics")
    checked.append("monthly_metrics")
    products = product_structure(data)
    reference = pd.read_csv(business_dir / "product_summary.csv", index_col=0)
    compare_table(products, reference[products.columns], "product structure")
    checked.append("product_structure")
    customers = customer_structure(data)
    concentration = pd.read_csv(customer_dir / "overall_concentration.csv")
    for row, n in zip(concentration.itertuples(index=False, name=None), [1, 5, 10, 20]):
        np.testing.assert_allclose(customers["gross_amount"].head(n).sum(), row[1], rtol=0, atol=1e-7)
    checked.append("customer_topN_amounts")
    rfm, thresholds = score_rfm(build_rfm(data, config["rfm_start"], config["rfm_end_exclusive"]))
    reference = pd.read_parquet(customer_dir / "customer_segments.parquet")
    compare_table(rfm, reference, "RFM all fields")
    segments = segment_summary(rfm)
    reference = pd.read_csv(customer_dir / "segment_summary.csv", index_col=0)
    compare_table(segments, reference[segments.columns], "segment summary")
    checked.append("rfm_all_fields_and_summary")
    weekly = weekly_history(data, config["forecast_cutoff_exclusive"])
    reference = pd.read_csv(forecast_dir / "weekly_data.csv", index_col=0)
    compare_table(weekly, reference, "weekly data")
    base = baselines(weekly["gross_amount"])
    train, validation, test = split_time(base, config["validation_weeks"], config["test_weeks"])
    _, ridge, training_rows = fit_ridge(base.loc[:validation.index.max(), "gross_amount"], train.index, validation.index)
    if training_rows != 66 or [len(train), len(validation), len(test)] != [79, 12, 12]:
        raise AssertionError("Training or split row counts changed")
    validation = validation.join(ridge)
    reference = pd.read_csv(forecast_dir / "validation_predictions.csv", index_col=0)
    compare_table(validation, reference, "validation predictions")
    test["selected_error"] = test["pred_mean_4weeks"] - test["gross_amount"]
    reference = pd.read_csv(forecast_dir / "test_predictions.csv", index_col=0)
    compare_table(test, reference, "test predictions")
    for frame, filename, names in [
        (validation, "validation_metrics.csv", ["上周金额", "前四周平均", "岭回归"]),
        (test, "test_metrics.csv", ["上周金额（对照）", "前四周平均（已选定）"]),
    ]:
        reference = pd.read_csv(forecast_dir / filename, index_col=0)
        for column, name in zip(["pred_last_week", "pred_mean_4weeks", "pred_ridge"], names):
            values = evaluate(frame["gross_amount"], frame[column])
            np.testing.assert_allclose(list(values.values()), reference.loc[name].to_numpy(dtype=float), rtol=1e-12, atol=1e-7)
    checked.append("forecast_splits_predictions_and_metrics")
    out = ROOT / "reports/stage1_validation" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True, exist_ok=False)
    figure = plot_segments(segments)
    figure.suptitle("Customer segments | 2010-12-01 to 2011-11-30")
    figure.savefig(out / "customer_segments_corrected.png", dpi=140, bbox_inches="tight")
    plt.close(figure)
    report = {"status": "PASS", "raw_rebuilt": args.raw, "checks": checked,
              "baseline": totals, "config": config, "source_sha256": digest(batch / "classified_transactions.parquet"),
              "code_sha256": {str(p.relative_to(ROOT)): digest(p) for p in sorted((ROOT / "src").rglob("*.py"))},
              "scope": "Offline regression; no database access. CSV tolerance 1e-7 GBP; cleaning field equality exact. Old archives untouched."}
    (out / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "SUCCESS.txt").write_text("PASS\n", encoding="utf-8")
    print(f"PASS: {len(checked)} validation groups; raw_rebuilt={args.raw}")
    print(f"Report: {out}")


if __name__ == "__main__":
    main()
