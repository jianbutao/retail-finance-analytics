import sys
import unittest
from pathlib import Path
import json
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from retail_finance.config import resolve_path
from retail_finance.cleaning import remove_cross_sheet_copies, classify_transactions, amount_milliunits
from retail_finance.forecasting import make_features, baselines, evaluate, split_time
from retail_finance.segmentation import build_rfm, score_rfm


def sample():
    return pd.DataFrame({"invoice_no": ["1"], "stock_code": ["100"], "description": [None],
        "quantity": [2], "invoice_date": pd.to_datetime(["2010-01-01"]), "unit_price": [.001],
        "customer_id": [None], "country": ["UK"], "source_sheet": ["Year 2009-2010"],
        "source_excel_row": [2]})


class CoreTests(unittest.TestCase):
    def test_milli_precision(self):
        self.assertEqual(amount_milliunits(sample()).iloc[0], 2)

    def test_reject_extra_price_precision(self):
        data = sample(); data["unit_price"] = .0001
        with self.assertRaises(ValueError): amount_milliunits(data)

    def test_keep_within_sheet_duplicates(self):
        raw = pd.concat([sample(), sample().assign(source_excel_row=3)], ignore_index=True)
        kept, excluded = remove_cross_sheet_copies(raw)
        self.assertEqual((len(kept), len(excluded)), (2, 0))

    def test_cross_sheet_equal_multiplicity(self):
        raw = pd.concat([sample(), sample().assign(source_sheet="Year 2010-2011")], ignore_index=True)
        kept, excluded = remove_cross_sheet_copies(raw)
        self.assertEqual((len(kept), len(excluded)), (1, 1))

    def test_cross_sheet_unequal_rejected(self):
        raw = pd.concat([sample(), sample().assign(source_excel_row=3),
                         sample().assign(source_sheet="Year 2010-2011")], ignore_index=True)
        with self.assertRaises(ValueError): remove_cross_sheet_copies(raw)

    def test_classification_boundaries(self):
        rules = {"special_code_map": {"B": "坏账调整"}, "reviewed_product_codes": []}
        data = pd.concat([sample()] * 5, ignore_index=True)
        data["invoice_no"] = ["1", "C2", "C3", "4", "5"]
        data["quantity"] = [2, -2, 2, -2, 1]
        data["unit_price"] = [1., 1., 1., 0., -1.]
        result = classify_transactions(data, rules)
        self.assertEqual(result["transaction_type"].tolist(),
                         ["正向交易", "取消或冲销", "待核查", "零单价记录", "负单价记录"])
        self.assertFalse(result["include_customer_sales"].any())

    def test_future_cannot_change_current_features(self):
        series = pd.Series(np.arange(12, dtype=float), index=pd.period_range("2010-01-04", periods=12, freq="W-SUN"))
        before = make_features(series)
        changed = series.copy(); changed.iloc[7:] = 999999
        pd.testing.assert_frame_equal(before.iloc[:8], make_features(changed).iloc[:8])

    def test_missing_week_propagates(self):
        series = pd.Series(np.arange(12, dtype=float), index=pd.period_range("2010-01-04", periods=12, freq="W-SUN"))
        series.iloc[5] = np.nan
        predicted = baselines(series)["pred_mean_4weeks"]
        self.assertTrue(predicted.iloc[6:10].isna().all())
        self.assertTrue(pd.notna(predicted.iloc[10]))

    def test_deleted_week_rejected(self):
        series = pd.Series(range(8), index=pd.period_range("2010-01-04", periods=8, freq="W-SUN"))
        with self.assertRaises(ValueError): make_features(series.drop(series.index[3]))

    def test_empty_and_zero_evaluation_rejected(self):
        for values in [[], [0., 0.]]:
            series = pd.Series(values, dtype=float)
            with self.assertRaises(ValueError): evaluate(series, series)

    def test_unaligned_evaluation_rejected(self):
        with self.assertRaises(ValueError): evaluate(pd.Series([1.], index=[1]), pd.Series([1.], index=[2]))

    def test_small_split_rejected(self):
        with self.assertRaises(ValueError): split_time(pd.DataFrame(index=range(10)))

    def test_rfm_exclusive_boundary_and_cancel_only(self):
        data = pd.concat([sample()] * 4, ignore_index=True)
        data["customer_id"] = ["A", "A", "B", "C"]
        data["invoice_date"] = pd.to_datetime(["2010-12-01", "2011-12-01", "2011-01-01", "2010-11-30"])
        data["include_product_sales"] = [True, True, False, True]
        data["include_product_cancellations"] = [False, False, True, False]
        data["line_amount"] = [10., 100., -5., 10.]
        result = build_rfm(data, "2010-12-01", "2011-12-01")
        self.assertEqual(result.index.tolist(), ["A"])
        self.assertEqual(result.loc["A", "monetary_gross"], 10.)

    def test_tied_m_quantiles_rejected(self):
        rfm = pd.DataFrame({"recency_days": [1]*4, "frequency": [1]*4, "monetary_net": [1.]*4})
        with self.assertRaises(ValueError): score_rfm(rfm)


if __name__ == "__main__":
    unittest.main()
