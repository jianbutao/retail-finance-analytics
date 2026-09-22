"""Plot functions return their own figure; no reliance on a global fig."""
import matplotlib.pyplot as plt


def plot_segments(summary):
    order = ["近期多次高贡献", "近期其他复购", "近期单次购买", "中等购买间隔", "较久未购买", "净额非正待核查"]
    labels = ["Recent frequent / higher net", "Other recent repeat buyers", "Recent single-order buyers",
              "Medium purchase gap", "Long purchase gap", "Non-positive net / review"]
    data = summary.reindex(order)
    if data[["customer_count", "net_amount"]].isna().any().any():
        raise ValueError("Missing expected customer segments")
    figure, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True, layout="constrained")
    colors = ["#2878B5", "#55A6C8", "#8CC8D9", "#A0A0A0", "#D8A14B", "#C85A54"]
    bars = axes[0].barh(range(6), data["customer_count"], color=colors)
    axes[0].set_yticks(range(6), labels=labels)
    axes[0].invert_yaxis()
    axes[0].bar_label(bars, labels=[f"{int(n):,} ({p:.2f}%)" for n, p in zip(data["customer_count"], data["customer_share_pct"])], padding=4)
    axes[0].set_xlim(0, data["customer_count"].max() * 1.5)
    axes[0].set_title("Customer count and share")
    axes[0].set_xlabel("Customers")
    bars = axes[1].barh(range(6), data["net_amount"] / 1e6, color=colors)
    axes[1].bar_label(bars, labels=[f"{v:,.2f}" for v in data["net_amount"]], padding=4)
    maximum = data["net_amount"].max() / 1e6
    axes[1].set_xlim(-maximum * .12, maximum * 1.45)
    axes[1].axvline(0, color="gray", linewidth=.8)
    axes[1].set_title("Product transaction net amount")
    axes[1].set_xlabel("GBP millions; labels in GBP")
    for ax in axes:
        ax.grid(axis="x", alpha=.2)
        ax.set_axisbelow(True)
    return figure
