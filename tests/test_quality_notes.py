import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "src")
)

from retail_finance.signals import identify_data_quality_notes


def sample_inputs():
    months = pd.period_range("2020-01", periods=2, freq="M")

    monthly = pd.DataFrame(
        {"month_boundary_truncated": [False, False]},
        index=months,
    )
    weekly = pd.DataFrame(
        {"recorded_days": [6, 6]},
        index=pd.period_range("2020-01-06", periods=2, freq="W-SUN"),
    )
    customers = pd.DataFrame(
        {
            "gross_amount": [100.0, 100.0],
            "active_identified_customers": [20, 20],
            "identified_coverage_pct": [90.0, 90.0],
        },
        index=months,
    )
    return monthly, weekly, customers


class QualityNoteTests(unittest.TestCase):
    def test_no_notes_preserves_columns(self):
        result = identify_data_quality_notes(*sample_inputs())
        self.assertTrue(result.empty)
        self.assertIn("note_id", result.columns)

    def test_coverage_threshold_is_strictly_below_80(self):
        monthly, weekly, customers = sample_inputs()
        customers["identified_coverage_pct"] = [80.0, 79.99]

        result = identify_data_quality_notes(monthly, weekly, customers)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["period"], "2020-02")

    def test_positive_amount_without_identified_customers(self):
        monthly, weekly, customers = sample_inputs()
        customers.iloc[0, customers.columns.get_loc(
            "active_identified_customers"
        )] = 0
        customers.iloc[0, customers.columns.get_loc(
            "identified_coverage_pct"
        )] = float("nan")

        result = identify_data_quality_notes(monthly, weekly, customers)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["observed_value"], 0.0)

    def test_zero_amount_is_not_low_coverage(self):
        monthly, weekly, customers = sample_inputs()
        customers["gross_amount"] = 0.0
        customers["identified_coverage_pct"] = 0.0

        result = identify_data_quality_notes(monthly, weekly, customers)

        self.assertTrue(result.empty)

    def test_boundary_and_no_record_week_are_separate(self):
        monthly, weekly, customers = sample_inputs()
        monthly.iloc[0, 0] = True
        weekly.iloc[0, 0] = 0

        result = identify_data_quality_notes(monthly, weekly, customers)

        self.assertEqual(len(result), 2)
        self.assertTrue(result["note_id"].is_unique)
        self.assertEqual(
            set(result["note_type"]),
            {"月份边界截断", "完整日历周无记录"},
        )


if __name__ == "__main__":
    unittest.main()