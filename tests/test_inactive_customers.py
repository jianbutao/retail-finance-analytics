import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "src")
)

from retail_finance.signals import identify_high_value_inactive


def sample_rfm():
    return pd.DataFrame(
        {
            "recency_days": [146, 147, 200, 200, 200, 200],
            "frequency": [2] * 6,
            "monetary_gross": [1000.0] * 6,
            "cancel_amount": [0, 0, 0, 1000, 1100, 0],
            "monetary_net": [1000, 1000, 1000, 0, -100, 1000],
            "M_score": pd.array([3, 3, 2, 4, 4, None], dtype="Int64"),
        },
        index=pd.Index(
            ["A", "B", "C", "D", "E", "F"],
            name="customer_id",
        ),
    )


class InactiveCustomerTests(unittest.TestCase):
    def test_selection_boundaries(self):
        result = identify_high_value_inactive(sample_rfm())
        self.assertEqual(result.index.tolist(), ["B"])

    def test_no_matches_returns_empty_table(self):
        data = sample_rfm()
        data["recency_days"] = 1

        result = identify_high_value_inactive(data)

        self.assertTrue(result.empty)
        self.assertIn("monetary_net", result.columns)

    def test_duplicate_customer_rejected(self):
        data = sample_rfm()
        duplicated = pd.concat([data, data.iloc[[0]]])

        with self.assertRaises(ValueError):
            identify_high_value_inactive(duplicated)

    def test_missing_field_rejected(self):
        data = sample_rfm().drop(columns="M_score")

        with self.assertRaises(ValueError):
            identify_high_value_inactive(data)

    def test_input_not_modified(self):
        data = sample_rfm()
        original = data.copy(deep=True)

        identify_high_value_inactive(data)

        pd.testing.assert_frame_equal(data, original)


if __name__ == "__main__":
    unittest.main()