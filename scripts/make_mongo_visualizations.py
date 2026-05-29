import textwrap
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from pymongo import MongoClient


MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "NYC_Payroll"
COLLECTION_NAME = "payroll_records"

OUTPUT_DIR = Path("reports/Mongo_figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Consistent visual theme
BG = "#F8FAFC"
TEXT = "#111827"
MUTED = "#6B7280"
GRID = "#E5E7EB"

ACCENT = "#10B981"       # MongoDB green
ACCENT_DARK = "#047857"  # darker green for second line in trend chart


def get_collection():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    return client, db[COLLECTION_NAME]


def money_billions(x, pos=None):
    return f"${x / 1_000_000_000:.1f}B"


def money_thousands(x, pos=None):
    return f"${x / 1000:.0f}K"


def percent_fmt(x, pos=None):
    return f"{x:.0f}%"


def clean_display_label(label):
    label = str(label).strip()

    label_replacements = {
        "WARDEN-ASSISTANT DEPUTY WARDEN TED < 11/1/92": "Warden / Assistant Deputy Warden",
        "LIEUTENANT D/A COMMANDER OF DETECTIVE SQUAD": "Lieutenant / Detective Squad Commander",
        "POLICE OFFICER D/A DETECTIVE 1ST GR": "Detective 1st Grade",
        "POLICE OFFICER D/A DETECTIVE 2ND GR": "Detective 2nd Grade",
        "CAPTAIN D/A DEPUTY CHIEF": "Captain / Deputy Chief",
        "CAPTAIN D/A INSPECTOR": "Captain / Inspector",
        "LIEUTENANT D/A SPECIAL ASSIGNMENT": "Lieutenant / Special Assignment",
    }

    if label.upper() in label_replacements:
        return label_replacements[label.upper()]

    label = label.rstrip("-–— ")

    return label.title()


def wrap_label(label, width=28):
    cleaned = clean_display_label(label)
    return "\n".join(textwrap.wrap(cleaned, width=width))


def clean_chart(ax):
    ax.set_facecolor(BG)
    ax.figure.set_facecolor(BG)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    ax.tick_params(axis="x", colors=MUTED, labelsize=10)
    ax.tick_params(axis="y", colors=TEXT, labelsize=10, length=0)

    ax.grid(axis="x", color=GRID, linewidth=1)
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


def aggregate_to_df(collection, pipeline):
    results = list(collection.aggregate(pipeline, allowDiskUse=True))
    return pd.DataFrame(results)



# CHART 1: TOP OVERTIME SPENDING BY AGENCY
# Question: Which agencies spend the most total money on overtime pay?
def chart_top_overtime_agencies(collection):
    pipeline = [
        {
            "$group": {
                "_id": "$agency_snapshot.agency_name",
                "total_overtime_spending": {
                    "$sum": "$compensation.total_overtime_paid"
                }
            }
        },
        {"$sort": {"total_overtime_spending": -1}},
        {"$limit": 10},
        {
            "$project": {
                "_id": 0,
                "agency_name": "$_id",
                "total_overtime_spending": 1
            }
        }
    ]

    df = aggregate_to_df(collection, pipeline)
    df = df.sort_values("total_overtime_spending", ascending=True)

    labels = [wrap_label(x, 28) for x in df["agency_name"]]

    fig, ax = plt.subplots(figsize=(11, 7))

    bars = ax.barh(
        labels,
        df["total_overtime_spending"],
        color=ACCENT,
        height=0.7
    )

    clean_chart(ax)
    ax.xaxis.set_major_formatter(FuncFormatter(money_billions))
    ax.set_xlabel("Total overtime spending", color=MUTED, fontsize=11)

    add_title(
        fig,
        "Police and Fire drive the largest overtime spending",
        "MongoDB aggregation: total overtime spending by NYC agency, fiscal years 2024–2025"
    )

    max_value = df["total_overtime_spending"].max()

    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + max_value * 0.015,
            bar.get_y() + bar.get_height() / 2,
            f"${width / 1_000_000_000:.2f}B",
            va="center",
            ha="left",
            fontsize=10,
            color=TEXT,
            fontweight="bold"
        )

    ax.set_xlim(0, max_value * 1.18)
    fig.subplots_adjust(top=0.84, left=0.31)

    save_fig(fig, "01_mongo_top_overtime_agencies.png")



# CHART 2: OVERTIME RELIANCE BY AGENCY
# Question: Which agencies rely most heavily on overtime compared to regular gross pay?
def chart_overtime_reliance(collection):
    pipeline = [
        {
            "$group": {
                "_id": "$agency_snapshot.agency_name",
                "payroll_record_count": {"$sum": 1},
                "total_regular_gross_paid": {
                    "$sum": "$compensation.regular_gross_paid"
                },
                "total_overtime_paid": {
                    "$sum": "$compensation.total_overtime_paid"
                }
            }
        },
        {
            "$match": {
                "payroll_record_count": {"$gte": 100},
                "total_regular_gross_paid": {"$gt": 0}
            }
        },
        {
            "$addFields": {
                "overtime_to_regular_pay_ratio": {
                    "$divide": [
                        "$total_overtime_paid",
                        "$total_regular_gross_paid"
                    ]
                }
            }
        },
        {"$sort": {"overtime_to_regular_pay_ratio": -1}},
        {"$limit": 10},
        {
            "$project": {
                "_id": 0,
                "agency_name": "$_id",
                "total_regular_gross_paid": 1,
                "total_overtime_paid": 1,
                "overtime_to_regular_pay_ratio": 1
            }
        }
    ]

    df = aggregate_to_df(collection, pipeline)
    df["overtime_percent"] = df["overtime_to_regular_pay_ratio"] * 100
    df = df.sort_values("overtime_percent", ascending=True)

    labels = [wrap_label(x, 28) for x in df["agency_name"]]

    fig, ax = plt.subplots(figsize=(11, 7))

    bars = ax.barh(
        labels,
        df["overtime_percent"],
        color=ACCENT,
        height=0.7
    )

    clean_chart(ax)
    ax.xaxis.set_major_formatter(FuncFormatter(percent_fmt))
    ax.set_xlabel("Overtime pay as % of regular gross pay", color=MUTED, fontsize=11)

    add_title(
        fig,
        "Correction and Fire rely most heavily on overtime",
        "MongoDB aggregation: overtime pay compared to regular gross pay, fiscal years 2024–2025"
    )

    max_value = df["overtime_percent"].max()

    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + max_value * 0.025,
            bar.get_y() + bar.get_height() / 2,
            f"{width:.1f}%",
            va="center",
            ha="left",
            fontsize=10,
            color=TEXT,
            fontweight="bold"
        )

    ax.set_xlim(0, max_value * 1.18)
    fig.subplots_adjust(top=0.84, left=0.31)

    save_fig(fig, "02_mongo_overtime_reliance_by_agency.png")



# CHART 3: TOTAL COMPENSATION BY AGENCY
# Question: How much does each agency spend on total compensation?
def chart_total_compensation_by_agency(collection):
    pipeline = [
        {
            "$group": {
                "_id": "$agency_snapshot.agency_name",
                "total_compensation_spending": {
                    "$sum": "$compensation.total_compensation"
                }
            }
        },
        {"$sort": {"total_compensation_spending": -1}},
        {"$limit": 10},
        {
            "$project": {
                "_id": 0,
                "agency_name": "$_id",
                "total_compensation_spending": 1
            }
        }
    ]

    df = aggregate_to_df(collection, pipeline)
    df = df.sort_values("total_compensation_spending", ascending=True)

    labels = [wrap_label(x, 28) for x in df["agency_name"]]

    fig, ax = plt.subplots(figsize=(11, 7))

    bars = ax.barh(
        labels,
        df["total_compensation_spending"],
        color=ACCENT,
        height=0.7
    )

    clean_chart(ax)
    ax.xaxis.set_major_formatter(FuncFormatter(money_billions))
    ax.set_xlabel("Total compensation spending", color=MUTED, fontsize=11)

    add_title(
        fig,
        "Education and public safety dominate total payroll spending",
        "MongoDB aggregation: total compensation spending by NYC agency, fiscal years 2024–2025"
    )

    max_value = df["total_compensation_spending"].max()

    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + max_value * 0.015,
            bar.get_y() + bar.get_height() / 2,
            f"${width / 1_000_000_000:.2f}B",
            va="center",
            ha="left",
            fontsize=10,
            color=TEXT,
            fontweight="bold"
        )

    ax.set_xlim(0, max_value * 1.18)
    fig.subplots_adjust(top=0.84, left=0.31)

    save_fig(fig, "03_mongo_total_compensation_by_agency.png")



# CHART 4: PAYROLL AND OVERTIME TREND
# Question: How did payroll and overtime spending change from 2024 to 2025?
def chart_yearly_trend(collection):
    pipeline = [
        {
            "$group": {
                "_id": "$fiscal_year",
                "total_compensation_spending": {
                    "$sum": "$compensation.total_compensation"
                },
                "total_overtime_spending": {
                    "$sum": "$compensation.total_overtime_paid"
                }
            }
        },
        {"$sort": {"_id": 1}},
        {
            "$project": {
                "_id": 0,
                "fiscal_year": "$_id",
                "total_compensation_spending": 1,
                "total_overtime_spending": 1
            }
        }
    ]

    df = aggregate_to_df(collection, pipeline)

    df["total_compensation_billions"] = (
        df["total_compensation_spending"] / 1_000_000_000
    )

    df["total_overtime_billions"] = (
        df["total_overtime_spending"] / 1_000_000_000
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(
        df["fiscal_year"],
        df["total_compensation_billions"],
        marker="o",
        linewidth=3,
        markersize=8,
        color=ACCENT,
        label="Total compensation"
    )

    ax.plot(
        df["fiscal_year"],
        df["total_overtime_billions"],
        marker="o",
        linewidth=3,
        markersize=8,
        color=ACCENT_DARK,
        label="Total overtime"
    )

    clean_chart(ax)

    ax.set_xlabel("Fiscal year", color=MUTED, fontsize=11)
    ax.set_ylabel("Spending ($ billions)", color=MUTED, fontsize=11)
    ax.set_xticks(df["fiscal_year"])
    ax.legend(frameon=False, fontsize=11, loc="upper right")

    add_title(
        fig,
        "Payroll and overtime spending dipped slightly in 2025",
        "MongoDB aggregation: total compensation and overtime spending by fiscal year"
    )

    for _, row in df.iterrows():
        ax.text(
            row["fiscal_year"],
            row["total_compensation_billions"] + 0.6,
            f"${row['total_compensation_billions']:.1f}B",
            ha="center",
            fontsize=10,
            color=ACCENT,
            fontweight="bold"
        )

        ax.text(
            row["fiscal_year"],
            row["total_overtime_billions"] + 0.35,
            f"${row['total_overtime_billions']:.1f}B",
            ha="center",
            fontsize=10,
            color=ACCENT_DARK,
            fontweight="bold"
        )

    fig.subplots_adjust(top=0.82)

    save_fig(fig, "04_mongo_yearly_payroll_overtime_trend.png")



# CHART 5: HIGHEST AVERAGE OVERTIME PAY BY JOB TITLE
# Question: Which job titles have the highest average overtime pay?
def chart_avg_overtime_pay_by_title(collection):
    pipeline = [
        {
            "$match": {
                "compensation.total_overtime_paid": {"$gt": 0}
            }
        },
        {
            "$group": {
                "_id": "$title_snapshot.title_description",
                "payroll_record_count": {"$sum": 1},
                "avg_overtime_paid": {
                    "$avg": "$compensation.total_overtime_paid"
                }
            }
        },
        {
            "$match": {
                "payroll_record_count": {"$gte": 100}
            }
        },
        {"$sort": {"avg_overtime_paid": -1}},
        {"$limit": 10},
        {
            "$project": {
                "_id": 0,
                "title_description": "$_id",
                "payroll_record_count": 1,
                "avg_overtime_paid": 1
            }
        }
    ]

    df = aggregate_to_df(collection, pipeline)
    df = df.sort_values("avg_overtime_paid", ascending=True)

    labels = [wrap_label(x, 30) for x in df["title_description"]]

    fig, ax = plt.subplots(figsize=(11, 7))

    bars = ax.barh(
        labels,
        df["avg_overtime_paid"],
        color=ACCENT,
        height=0.7
    )

    clean_chart(ax)
    ax.xaxis.set_major_formatter(FuncFormatter(money_thousands))
    ax.set_xlabel("Average overtime pay", color=MUTED, fontsize=11)

    add_title(
        fig,
        "Specialized and supervisory roles have the highest average overtime pay",
        "MongoDB aggregation: average overtime pay by job title among records with overtime pay"
    )

    max_value = df["avg_overtime_paid"].max()

    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + max_value * 0.015,
            bar.get_y() + bar.get_height() / 2,
            f"${width / 1000:.0f}K",
            va="center",
            ha="left",
            fontsize=10,
            color=TEXT,
            fontweight="bold"
        )

    ax.set_xlim(0, max_value * 1.18)
    fig.subplots_adjust(top=0.84, left=0.34)

    save_fig(fig, "05_mongo_avg_overtime_pay_by_title.png")



def main():
    client, collection = get_collection()

    print("MongoDB documents:", collection.count_documents({}))

    chart_top_overtime_agencies(collection)
    chart_overtime_reliance(collection)
    chart_total_compensation_by_agency(collection)
    chart_yearly_trend(collection)
    chart_avg_overtime_pay_by_title(collection)

    client.close()

    print("\nDone. MongoDB slide-ready charts saved in:")
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()