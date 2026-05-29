import textwrap
from pathlib import Path
from getpass import getpass
from urllib.parse import quote_plus

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from sqlalchemy import create_engine


DB_NAME = "nyc_payroll"
MYSQL_USER = "root"

OUTPUT_DIR = Path("reports/SQL_figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Consistent visual theme
BG = "#F8FAFC"
TEXT = "#111827"
MUTED = "#6B7280"
GRID = "#E5E7EB"

ACCENT = "#2563EB"       # main blue used across all charts
ACCENT_DARK = "#1E3A8A"  # darker blue for second line in trend chart


def get_engine():
    password = getpass("Enter MySQL password: ")
    password_encoded = quote_plus(password)

    return create_engine(
        f"mysql+pymysql://{MYSQL_USER}:{password_encoded}@localhost:3306/{DB_NAME}"
    )


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



# CHART 1: TOP OVERTIME SPENDING BY AGENCY
# Question: Which agencies spend the most total money on overtime pay?
def chart_top_overtime_agencies(engine):
    query = """
    SELECT 
        a.agency_name,
        SUM(pr.total_overtime_paid) AS total_overtime_spending
    FROM payroll_records pr
    JOIN agencies a 
        ON pr.agency_id = a.agency_id
    GROUP BY a.agency_name
    ORDER BY total_overtime_spending DESC
    LIMIT 10;
    """

    df = pd.read_sql(query, engine)
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
        "Total overtime spending by NYC agency, fiscal years 2024–2025"
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

    save_fig(fig, "01_top_overtime_agencies.png")



# CHART 2: OVERTIME RELIANCE BY AGENCY
# Question: Which agencies rely most heavily on overtime compared to regular gross pay?
def chart_overtime_reliance(engine):
    query = """
    SELECT 
        a.agency_name,
        SUM(pr.regular_gross_paid) AS total_regular_gross_paid,
        SUM(pr.total_overtime_paid) AS total_overtime_paid,
        SUM(pr.total_overtime_paid) / NULLIF(SUM(pr.regular_gross_paid), 0) AS overtime_to_regular_pay_ratio
    FROM payroll_records pr
    JOIN agencies a 
        ON pr.agency_id = a.agency_id
    GROUP BY a.agency_name
    HAVING 
        COUNT(*) >= 100
        AND SUM(pr.regular_gross_paid) > 0
    ORDER BY overtime_to_regular_pay_ratio DESC
    LIMIT 10;
    """

    df = pd.read_sql(query, engine)
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
        "Overtime pay compared to regular gross pay, fiscal years 2024–2025"
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

    save_fig(fig, "02_overtime_reliance_by_agency.png")



# CHART 3: TOTAL COMPENSATION BY AGENCY
# Question: How much does each agency spend on total compensation?
def chart_total_compensation_by_agency(engine):
    query = """
    SELECT 
        a.agency_name,
        SUM(pr.total_compensation) AS total_compensation_spending
    FROM payroll_records pr
    JOIN agencies a 
        ON pr.agency_id = a.agency_id
    GROUP BY a.agency_name
    ORDER BY total_compensation_spending DESC
    LIMIT 10;
    """

    df = pd.read_sql(query, engine)
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
        "Total compensation spending by NYC agency, fiscal years 2024–2025"
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

    save_fig(fig, "03_total_compensation_by_agency.png")



# CHART 4: PAYROLL AND OVERTIME TREND
# Question: How did payroll and overtime spending change from 2024 to 2025?
def chart_yearly_trend(engine):
    query = """
    SELECT 
        fy.fiscal_year,
        SUM(pr.total_compensation) AS total_compensation_spending,
        SUM(pr.total_overtime_paid) AS total_overtime_spending
    FROM payroll_records pr
    JOIN fiscal_years fy 
        ON pr.fiscal_year_id = fy.fiscal_year_id
    GROUP BY fy.fiscal_year
    ORDER BY fy.fiscal_year;
    """

    df = pd.read_sql(query, engine)

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
        "Total compensation and overtime spending by fiscal year"
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

    save_fig(fig, "04_yearly_payroll_overtime_trend.png")



# CHART 5: HIGHEST AVERAGE OVERTIME PAY BY JOB TITLE
# Question: Which job titles have the highest average overtime pay?
def chart_avg_overtime_pay_by_title(engine):
    query = """
    SELECT 
        jt.title_description,
        COUNT(*) AS payroll_record_count,
        AVG(pr.total_overtime_paid) AS avg_overtime_paid
    FROM payroll_records pr
    JOIN job_titles jt 
        ON pr.title_id = jt.title_id
    WHERE 
        pr.total_overtime_paid > 0
    GROUP BY jt.title_description
    HAVING COUNT(*) >= 100
    ORDER BY avg_overtime_paid DESC
    LIMIT 10;
    """

    df = pd.read_sql(query, engine)
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
        "Average overtime pay by job title among records with overtime pay, fiscal years 2024–2025"
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

    save_fig(fig, "05_avg_overtime_pay_by_title.png")



def main():
    engine = get_engine()

    chart_top_overtime_agencies(engine)
    chart_overtime_reliance(engine)
    chart_total_compensation_by_agency(engine)
    chart_yearly_trend(engine)
    chart_avg_overtime_pay_by_title(engine)

    print("\nDone. Slide-ready charts saved in:")
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()