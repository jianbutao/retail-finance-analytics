import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "src")
)

from retail_finance.signals import assess_customer_concentration


def sample_data():
    # 20名已识别客户各贡献100，匿名交易另贡献1000
    transactions = pd.DataFrame({
        "customer_id": [f"C{i:02d}" for i in range(20)] + [None],
        "invoice_date": pd.to_datetime(["2020-01-15"] * 21),
        "line_amount": [100.0] * 20 + [1000.0],
        "include_product_sales": [True] * 21,
    })

    monthly = pd.DataFrame(
        {
            "gross_amount": [3000.0],
            "month_boundary_truncated": [False],
        },
        index=pd.period_range("2020-01", periods=1, freq="M"),
    )
    return transactions, monthly


class CustomerSignalTests(unittest.TestCase):
    def test_denominators_and_anonymous_amount(self):
        transactions, monthly = sample_data()
        row = assess_customer_concentration(
            transactions, monthly
        ).iloc[0]

        self.assertEqual(row["active_identified_customers"], 20)
        self.assertEqual(row["top10_amount"], 1000.0)
        self.assertAlmostEqual(row["top10_share_identified_pct"], 50.0)
        self.assertAlmostEqual(row["top10_share_all_pct"], 100 / 3)
        self.assertAlmostEqual(row["identified_coverage_pct"], 200 / 3)

    def test_exact_threshold_triggers(self):
        transactions, monthly = sample_data()
        row = assess_customer_concentration(
            transactions, monthly, threshold_pct=50.0
        ).iloc[0]
        self.assertTrue(row["customer_concentration_signal"])

    def test_insufficient_customers_is_unavailable(self):
        transactions, monthly = sample_data()
        row = assess_customer_concentration(
            transactions, monthly, min_customers=21
        ).iloc[0]
        self.assertFalse(row["assessment_available"])
        self.assertTrue(pd.isna(row["customer_concentration_signal"]))

    def test_truncated_month_is_unavailable(self):
        transactions, monthly = sample_data()
        monthly["month_boundary_truncated"] = True

        row = assess_customer_concentration(
            transactions, monthly
        ).iloc[0]
        self.assertTrue(pd.isna(row["customer_concentration_signal"]))

    def test_no_identified_customers(self):
        transactions, monthly = sample_data()
        transactions["customer_id"] = None

        row = assess_customer_concentration(
            transactions, monthly
        ).iloc[0]
        self.assertEqual(row["active_identified_customers"], 0)
        self.assertTrue(pd.isna(row["customer_concentration_signal"]))


if __name__ == "__main__":
    unittest.main()