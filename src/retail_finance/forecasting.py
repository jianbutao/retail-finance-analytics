"""Frozen first experiment: chronological, rolling one-week-ahead forecasts."""
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def weekly_history(transactions, cutoff):
    cutoff = pd.Timestamp(cutoff)
    history = transactions.loc[transactions["invoice_date"] < cutoff].copy()
    if history.empty:
        raise ValueError("No history before cutoff")
    history["week"] = history["invoice_date"].dt.to_period("W-SUN")
    history["day"] = history["invoice_date"].dt.normalize()
    sales = history.loc[history["include_product_sales"]]
    coverage = history.groupby("week").agg(recorded_days=("day", "nunique"))
    amounts = sales.groupby("week").agg(gross_amount=("line_amount", "sum"),
        sales_orders=("invoice_no", "nunique"), recorded_sales_days=("day", "nunique"))
    first = history["invoice_date"].min().normalize()
    weeks = pd.period_range(first.to_period("W-SUN"), (cutoff - pd.Timedelta(days=1)).to_period("W-SUN"), freq="W-SUN", name="week")
    result = coverage.join(amounts).reindex(weeks)
    result = result.loc[(weeks.start_time >= first) & (weeks.end_time < cutoff)].copy()
    cols = ["recorded_days", "recorded_sales_days"]
    result[cols] = result[cols].fillna(0).astype(int)
    return result


def make_features(amount):
    if not isinstance(amount.index, pd.PeriodIndex) or amount.index.freqstr != "W-SUN" or amount.empty:
        raise ValueError("Expected nonempty Monday-Sunday PeriodIndex")
    expected = pd.period_range(amount.index.min(), amount.index.max(), freq="W-SUN")
    if not amount.index.equals(expected):
        raise ValueError("Weeks must be unique, sorted and contiguous; preserve missing positions")
    features = pd.DataFrame({f"lag_{lag}": amount.shift(lag) for lag in range(1, 5)})
    dates = amount.index.start_time
    phase = (dates.dayofyear.to_numpy() - 1) / np.where(dates.is_leap_year, 366, 365)
    features["year_sin"] = np.sin(2 * np.pi * phase)
    features["year_cos"] = np.cos(2 * np.pi * phase)
    return features


def baselines(amount):
    make_features(amount)  # validates the calendar before shifting
    previous = amount.shift(1)
    return pd.DataFrame({"gross_amount": amount, "pred_last_week": previous,
                         "pred_mean_4weeks": previous.rolling(4, min_periods=4).mean()})


def split_time(data, validation_weeks=12, test_weeks=12):
    if min(validation_weeks, test_weeks) < 1 or len(data) <= validation_weeks + test_weeks + 4:
        raise ValueError("Insufficient history or invalid split sizes")
    end = len(data) - test_weeks
    return (data.iloc[:end-validation_weeks].copy(), data.iloc[end-validation_weeks:end].copy(), data.iloc[end:].copy())


def fit_ridge(amount, train_index, validation_index):
    if train_index.empty or validation_index.empty or train_index.max() >= validation_index.min():
        raise ValueError("Training must precede validation")
    x = make_features(amount)
    usable = x.loc[train_index].notna().all(axis=1) & amount.loc[train_index].notna()
    train_x = x.loc[train_index].loc[usable]
    validation_x = x.loc[validation_index]
    if train_x.empty or validation_x.isna().any().any():
        raise ValueError("Insufficient complete training or validation features")
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    model.fit(train_x, amount.loc[train_x.index])
    prediction = pd.Series(np.maximum(model.predict(validation_x), 0), index=validation_index, name="pred_ridge")
    return model, prediction, len(train_x)


def evaluate(actual, predicted):
    if not actual.index.equals(predicted.index) or actual.empty:
        raise ValueError("Evaluation requires nonempty aligned observations")
    if not np.isfinite(actual.to_numpy(dtype=float)).all() or not np.isfinite(predicted.to_numpy(dtype=float)).all():
        raise ValueError("Evaluation contains non-finite values")
    denominator = actual.abs().sum()
    if denominator <= 0:
        raise ValueError("WAPE undefined for a zero denominator")
    error = predicted - actual
    return {"weeks": len(actual), "MAE_GBP": float(error.abs().mean()),
            "WAPE_pct": float(error.abs().sum() / denominator * 100),
            "mean_bias_GBP": float(error.mean())}
