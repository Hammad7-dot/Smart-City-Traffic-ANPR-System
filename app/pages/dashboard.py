# implements FR7, rules.md #12 (this page only — see decisions.md D-014); read-only from DB, no detection/tracking/OCR logic here
"""Analytics dashboard: live class-wise counts, plate logs, historical reports."""

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parents[2] / "database" / "traffic.db"

st.title("Smart City Traffic ANPR — Dashboard")


@st.cache_data(ttl=5)
def load_events() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM vehicle_events ORDER BY event_timestamp DESC", conn)
    conn.close()
    return df


df = load_events()

if df.empty:
    st.info("No vehicle events recorded yet. Run the pipeline to populate the database:\n\n"
            "`python -m pipeline.run_pipeline --source data/videos/traffic.mp4`\n\n"
            "or use the **Upload & Detect** page in the sidebar.")
else:
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"])

    st.sidebar.header("Filters")
    vehicle_types = sorted(df["vehicle_type"].unique())
    selected_types = st.sidebar.multiselect("Vehicle type", vehicle_types, default=vehicle_types)

    min_date, max_date = df["event_timestamp"].min().date(), df["event_timestamp"].max().date()
    date_range = st.sidebar.date_input(
        "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
    )

    filtered = df[df["vehicle_type"].isin(selected_types)]
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
        filtered = filtered[
            (filtered["event_timestamp"].dt.date >= start) & (filtered["event_timestamp"].dt.date <= end)
        ]

    if filtered.empty:
        st.warning("No events match the current filters. Try widening the vehicle type or date range in the sidebar.")
    else:
        st.subheader("Live class-wise counts")
        counts = filtered["vehicle_type"].value_counts()
        st.bar_chart(counts)

        col1, col2, col3 = st.columns(3)
        col1.metric("Total crossing events", len(filtered))
        col2.metric("Vehicle types seen", filtered["vehicle_type"].nunique())
        col3.metric("Low-confidence plate reads", int(filtered["is_low_confidence"].sum()))

        st.subheader("Plate log")
        st.dataframe(
            filtered[["event_timestamp", "vehicle_type", "plate_number", "ocr_confidence", "is_low_confidence", "track_id"]],
            use_container_width=True,
        )

        st.subheader("Historical report: events over time")
        timeline = filtered.set_index("event_timestamp").resample("1min").size()
        st.line_chart(timeline, use_container_width=True)
