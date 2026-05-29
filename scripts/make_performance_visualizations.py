from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


OUTPUT_DIR = Path("reports/performance_figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BG = "#F8FAFC"
TEXT = "#111827"
MUTED = "#6B7280"
GRID = "#E5E7EB"

MYSQL_COLOR = "#2563EB"   # blue
MONGO_COLOR = "#10B981"   # green
BEFORE = "#94A3B8"        # gray
AFTER = "#10B981"         # green


def clean_chart(ax):
    ax.set_facecolor(BG)
    ax.figure.set_facecolor(BG)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    ax.tick_params(axis="x", colors=TEXT, labelsize=10)
    ax.tick_params(axis="y", colors=MUTED, labelsize=10)

    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)


def add_title(fig, title, subtitle):
    fig.text(
        0.02, 0.96, title,
        fontsize=18,
        fontweight="bold",
        color=TEXT,
        ha="left",
        va="top"
    )

    fig.text(
        0.02, 0.91, subtitle,
        fontsize=11,
        color=MUTED,
        ha="left",
        va="top"
    )


def save_fig(fig, filename):
    path = OUTPUT_DIR / filename
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"Saved {path}")



# CHART 1: RUNTIME COMPARISON FOR 5 QUERIES
# Question: Which database performed faster across the main analytical queries?
def chart_runtime_comparison():
    data = [
        {
            "query": "Agency total\nOT spend",
            "mongodb_ms": 438,
            "mysql_ms": 858,
            "winner": "MongoDB"
        },
        {
            "query": "Agency OT\nreliance",
            "mongodb_ms": 260,
            "mysql_ms": 901,
            "winner": "MongoDB"
        },
        {
            "query": "Agency total\ncompensation",
            "mongodb_ms": 498,
            "mysql_ms": 1215,
            "winner": "MongoDB"
        },
        {
            "query": "Spending by\nfiscal year",
            "mongodb_ms": 1032,
            "mysql_ms": 843,
            "winner": "MySQL"
        },
        {
            "query": "Title avg\nOT pay",
            "mongodb_ms": 220,
            "mysql_ms": 394,
            "winner": "MongoDB"
        },
    ]

    df = pd.DataFrame(data)

    x = np.arange(len(df))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6.5))

    mongo_bars = ax.bar(
        x - width / 2,
        df["mongodb_ms"],
        width,
        label="MongoDB",
        color=MONGO_COLOR
    )

    mysql_bars = ax.bar(
        x + width / 2,
        df["mysql_ms"],
        width,
        label="MySQL",
        color=MYSQL_COLOR
    )

    clean_chart(ax)

    ax.set_xticks(x)
    ax.set_xticklabels(df["query"])
    ax.set_ylabel("Runtime (milliseconds)", color=MUTED, fontsize=11)
    ax.legend(frameon=False, fontsize=11)

    add_title(
        fig,
        "MongoDB was faster for 4 of 5 analytical queries",
        "Runtime comparison across the main MySQL and MongoDB queries"
    )

    for bars in [mongo_bars, mysql_bars]:
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 25,
                f"{height:.0f}ms",
                ha="center",
                va="bottom",
                fontsize=9,
                color=TEXT,
                fontweight="bold"
            )

    for i, row in df.iterrows():
        y_position = max(row["mongodb_ms"], row["mysql_ms"]) + 120
        ax.text(
            i,
            y_position,
            f"Winner: {row['winner']}",
            ha="center",
            va="bottom",
            fontsize=9,
            color=MUTED,
            fontweight="bold"
        )

    ax.set_ylim(0, max(df["mongodb_ms"].max(), df["mysql_ms"].max()) * 1.28)
    fig.subplots_adjust(top=0.82)

    save_fig(fig, "01_runtime_comparison_5_queries.png")



# CHART 2: SPEEDUP BY QUERY
# Question: How much faster was the winning database?
def chart_speedup_by_query():
    data = [
        {
            "query": "Agency total OT spend",
            "mongodb_ms": 438,
            "mysql_ms": 858
        },
        {
            "query": "Agency OT reliance",
            "mongodb_ms": 260,
            "mysql_ms": 901
        },
        {
            "query": "Agency total compensation",
            "mongodb_ms": 498,
            "mysql_ms": 1215
        },
        {
            "query": "Spending by fiscal year",
            "mongodb_ms": 1032,
            "mysql_ms": 843
        },
        {
            "query": "Title avg OT pay",
            "mongodb_ms": 220,
            "mysql_ms": 394
        },
    ]

    df = pd.DataFrame(data)

    df["winner"] = np.where(
        df["mongodb_ms"] < df["mysql_ms"],
        "MongoDB",
        "MySQL"
    )

    df["speedup"] = np.where(
        df["winner"] == "MongoDB",
        df["mysql_ms"] / df["mongodb_ms"],
        df["mongodb_ms"] / df["mysql_ms"]
    )

    df["label"] = df["query"] + "\n(" + df["winner"] + ")"
    df = df.sort_values("speedup", ascending=True)

    colors = np.where(df["winner"] == "MongoDB", MONGO_COLOR, MYSQL_COLOR)

    fig, ax = plt.subplots(figsize=(11, 6.5))

    bars = ax.barh(
        df["label"],
        df["speedup"],
        color=colors,
        height=0.7
    )

    clean_chart(ax)
    ax.set_xlabel("Winner speedup factor", color=MUTED, fontsize=11)

    add_title(
        fig,
        "MongoDB had the biggest advantage on overtime reliance",
        "Speedup factor of the faster database for each query"
    )

    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + 0.05,
            bar.get_y() + bar.get_height() / 2,
            f"{width:.1f}x",
            va="center",
            ha="left",
            fontsize=10,
            color=TEXT,
            fontweight="bold"
        )

    ax.set_xlim(0, df["speedup"].max() * 1.25)
    fig.subplots_adjust(top=0.82, left=0.33)

    save_fig(fig, "02_query_speedup_winners.png")



# CHART 3: INDEX BEFORE AND AFTER
# Question: How did indexing affect performance?
def chart_index_before_after():
    data = [
        {
            "database": "MySQL",
            "before_avg_seconds": 0.0163,
            "after_avg_seconds": 0.0108
        },
        {
            "database": "MongoDB",
            "before_avg_seconds": 0.3408,
            "after_avg_seconds": 0.0752
        },
    ]

    df = pd.DataFrame(data)

    x = np.arange(len(df))
    width = 0.35

    fig, ax = plt.subplots(figsize=(9, 6))

    before_bars = ax.bar(
        x - width / 2,
        df["before_avg_seconds"],
        width,
        label="Before index",
        color=BEFORE
    )

    after_bars = ax.bar(
        x + width / 2,
        df["after_avg_seconds"],
        width,
        label="After index",
        color=AFTER
    )

    clean_chart(ax)

    ax.set_xticks(x)
    ax.set_xticklabels(df["database"])
    ax.set_ylabel("Average runtime (seconds)", color=MUTED, fontsize=11)
    ax.legend(frameon=False, fontsize=11)

    add_title(
        fig,
        "Indexing improved query speed",
        "Before-and-after runtime for a high-compensation filter query"
    )

    for bars in [before_bars, after_bars]:
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + 0.01,
                f"{height:.3f}s",
                ha="center",
                va="bottom",
                fontsize=10,
                color=TEXT,
                fontweight="bold"
            )

    max_value = max(df["before_avg_seconds"].max(), df["after_avg_seconds"].max())
    ax.set_ylim(0, max_value * 1.3)
    fig.subplots_adjust(top=0.82)

    save_fig(fig, "03_index_before_after.png")



def main():
    chart_runtime_comparison()
    chart_speedup_by_query()
    chart_index_before_after()

    print("\nDone. Performance charts saved in:")
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()