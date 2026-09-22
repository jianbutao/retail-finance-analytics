import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "src")
)

from retail_finance.signals import assess_monthly_signals


def sample_months():
    return pd.DataFrame(
        {
            "gross_amount": [100.0] * 8,
            "cancel_amount": [0.0] * 8,
            "days_with_product_sales": [24] * 8,
            "month_boundary_truncated": [False] * 8,
        },
        index=pd.period_range("2020-01", periods=8, freq="M"),
    )


class MonthlySignalTests(unittest.TestCase):
    def test_thresholds_and_initial_window(self):
        data = sample_months()
        data.iloc[3, data.columns.get_loc("gross_amount")] = 70.0
        data.iloc[3, data.columns.get_loc("cancel_amount")] = 3.5

        result = assess_monthly_signals(data)

        self.assertTrue(result["sales_drop_signal"].iloc[3])
        self.assertTrue(result["cancel_rise_signal"].iloc[3])
        self.assertTrue(result["sales_drop_signal"].iloc[:3].isna().all())
        self.assertTrue(result["cancel_rise_signal"].iloc[:3].isna().all())

    def test_weighted_cancellation_baseline(self):
        data = sample_months()
        data.loc[data.index[:3], "gross_amount"] = [100, 200, 700]
        data.loc[data.index[:3], "cancel_amount"] = [10, 10, 7]

        result = assess_monthly_signals(data)

        # (10 + 10 + 7) / (100 + 200 + 700) × 100
        self.assertAlmostEqual(
            result["baseline_cancel_pct"].iloc[3], 2.7
        )

    def test_current_and_future_do_not_change_baseline(self):
        data = sample_months()
        original = assess_monthly_signals(data)

        data.loc[
            data.index[4]:, ["gross_amount", "cancel_amount"]
        ] *= 10
        changed = assess_monthly_signals(data)

        columns = ["baseline_gross_amount", "baseline_cancel_pct"]
        pd.testing.assert_frame_equal(
            original[columns].iloc[:5],
            changed[columns].iloc[:5],
        )

    def test_unusable_month_and_following_baselines(self):
        for reason in ["missing", "zero", "truncated"]:
            with self.subTest(reason=reason):
                data = sample_months()
                month = data.index[3]

                if reason == "truncated":
                    data.loc[month, "month_boundary_truncated"] = True
                else:
                    data.loc[month, "gross_amount"] = (
                        float("nan") if reason == "missing" else 0.0
                    )

                result = assess_monthly_signals(data)

                self.assertFalse(
                    result["assessment_available"].iloc[3:7].any()
                )
                self.assertTrue(
                    result["sales_drop_signal"].iloc[3:7].isna().all()
                )
                self.assertTrue(result["assessment_available"].iloc[7])

    def test_empty_and_broken_calendar_rejected(self):
        data = sample_months()

        for invalid in [data.iloc[:0], data.drop(data.index[2])]:
            with self.assertRaises(ValueError):
                assess_monthly_signals(invalid)

    def test_input_not_modified(self):
        data = sample_months()
        original = data.copy(deep=True)

        assess_monthly_signals(data)

        pd.testing.assert_frame_equal(data, original)


if __name__ == "__main__":
    unittest.main()