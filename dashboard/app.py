import streamlit as st
import pandas as pd
import plotly.express as px


st.set_page_config(
    page_title="NYC Payroll Overtime Dashboard",
    layout="wide"
)

st.title("NYC Payroll Overtime Analysis Dashboard")

st.markdown("""
This dashboard analyzes NYC payroll data from 2024–2025 with a focus on overtime spending.

Key analytical questions:
- Which agencies generate the highest overtime costs?
- Which jobs have the highest average overtime pay?
- How is overtime distributed across employees?
- What is the relationship between overtime hours and overtime pay?
""")

df = pd.read_csv("nyc_payroll_cleaned.csv", low_memory=False)

df["work_location_borough"] = (
    df["work_location_borough"]
    .astype(str)
    .str.strip()
    .str.upper()
)

df = df[
    (df["work_location_borough"] != "NAN") &
    (df["work_location_borough"] != "OTHER")
]

df = df[
    (df["overtime_hours"] >= 0) &
    (df["total_overtime_paid"] >= 0)
]

valid_boroughs = [
    "MANHATTAN",
    "BROOKLYN",
    "QUEENS",
    "BRONX",
    "RICHMOND"
]

df = df[df["work_location_borough"].isin(valid_boroughs)]

df["agency_name"] = (
    df["agency_name"]
    .astype(str)
    .str.strip()
    .str.upper()
)


numeric_cols = [
    "base_salary",
    "regular_gross_paid",
    "total_overtime_paid",
    "total_other_pay",
    "total_compensation",
    "regular_hours",
    "overtime_hours",
    "total_hours",
    "overtime_pay_share",
    "overtime_hours_share"
]

for col in numeric_cols:
    df[col] = (
        df[col]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
    )

    df[col] = pd.to_numeric(df[col], errors="coerce")


st.sidebar.header("Filters")


years = sorted(df["fiscal_year"].dropna().unique().tolist())

year_options = ["ALL YEARS"] + years

selected_year = st.sidebar.selectbox(
    "Select Fiscal Year",
    year_options
)

boroughs = sorted(df["work_location_borough"].dropna().unique().tolist())

borough_options = ["ALL BOROUGHS"] + boroughs

selected_borough = st.sidebar.selectbox(
    "Select Borough",
    borough_options
)


filtered_df = df.copy()

if selected_year != "ALL YEARS":
    filtered_df = filtered_df[
        filtered_df["fiscal_year"] == selected_year
    ]

if selected_borough != "ALL BOROUGHS":
    filtered_df = filtered_df[
        filtered_df["work_location_borough"] == selected_borough
    ]


st.subheader("Summary Metrics")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Employees",
        len(filtered_df)
    )

with col2:
    st.metric(
        "Total Overtime Paid",
        f"${filtered_df['total_overtime_paid'].sum():,.0f}"
    )

with col3:
    st.metric(
        "Average Overtime Paid",
        f"${filtered_df['total_overtime_paid'].mean():,.0f}"
    )


st.subheader("Top Agencies by Overtime Pay")

top_agencies = (
    filtered_df.groupby("agency_name")["total_overtime_paid"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
    .reset_index()
)

fig1 = px.bar(
    top_agencies,
    x="total_overtime_paid",
    y="agency_name",
    orientation="h",
    color="total_overtime_paid",
    title="Top 10 Agencies by Total Overtime Spending"
)

fig1.update_layout(
    yaxis_title="Agency Name",
    xaxis_title="Total Overtime Paid"
)

st.plotly_chart(fig1, use_container_width=True)

st.markdown("""
### Finding
Most of the overall overtime spending in concentrated in a few agencies. 
When looking at all boroughs combined and both 2024 and 2025, we see that the police department has the highest overtime spending amount followed by the fire department.
""")


st.subheader("Distribution of Employee Overtime Pay")

fig2 = px.histogram(
    filtered_df,
    x="total_overtime_paid",
    nbins=30,
    title="Distribution of Overtime Pay"
)

fig2.update_layout(
    yaxis_title="Count",
    xaxis_title="Total Overtime Paid"
)

st.plotly_chart(fig2, use_container_width=True)

st.markdown("""
### Finding
The majority of employees receive overtime pay on the lower end of the graph (0-10,000), resulting in a strongly right skewed distribution.
""")


st.subheader("Job Titles with Highest Average Overtime Pay")

top_titles = (
    filtered_df.groupby("title_description")["total_overtime_paid"]
    .mean()
    .sort_values(ascending=False)
    .head(10)
    .reset_index()
)

fig3 = px.bar(
    top_titles,
    x="total_overtime_paid",
    y="title_description",
    orientation="h",
    color="total_overtime_paid",
    title="Top 10 Job Titles by Average Overtime Pay"
)

fig3.update_layout(
    yaxis_title="Job Title",
    xaxis_title="Average Overtime Pay"
)

st.plotly_chart(fig3, use_container_width=True)

st.markdown("""
### Finding
Certain job titles receive substantially higher average overtime pay than others.
This could suggest that overtime demand is concentrated in specialized positions
that require extended work hours.
Across all boroughs and both years, the Chief Marine Engineer had the highest overtime pay.
""")


st.subheader("Overtime Hours vs Overtime Pay")

fig4 = px.scatter(
    filtered_df,
    x="overtime_hours",
    y="total_overtime_paid",
    color="agency_name",
    title="Relationship Between Overtime Hours and Overtime Pay",
    opacity=0.6
)

fig4.update_layout(
    yaxis_title="Total Overtime Pay",
    xaxis_title="Overtime Hours"
)

st.plotly_chart(fig4, use_container_width=True)

st.markdown("""
### Finding
Overtime hours and overtime pay are positively and strongly correlated for the most part, which makes sense since there is a regulation on what overtime pay should be per hour.
Interestingly, there are quite a few data points with 0 overtime hours and 
positive overtime pay, which may reflect payroll adjustments, retroactive payments, or data inconsistencies. 
""")

