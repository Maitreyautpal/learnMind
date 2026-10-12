"""Reusable interface pieces."""
import altair as alt
import pandas as pd
import streamlit as st

import api_client as api
from utils.format import LEVEL_COLORS, PRIORITY_COLORS


def safe(fn, *args, **kwargs):
    """Call the backend; on failure show a clear message and stop the page."""
    try:
        return fn(*args, **kwargs)
    except api.BackendOffline:
        st.error("The backend is not reachable. Start it with: uvicorn backend.main:app --port 8000")
    except api.ApiError as exc:
        st.error(f"Backend error ({exc.status}): {exc.detail}")
    st.stop()


def demo_badge():
    st.markdown(
        "<span style='background:#E0A526;color:#000;padding:2px 10px;border-radius:12px;"
        "font-size:0.8rem;font-weight:600'>Demo mode</span>", unsafe_allow_html=True)


def demo_notice():
    st.warning("Demo mode: the FastAPI backend is not connected, so this page shows sample data.")


def priority_badge(priority: str) -> str:
    color = PRIORITY_COLORS.get(priority, "#666")
    return (f"<span style='background:{color};color:#fff;padding:2px 10px;border-radius:12px;"
            f"font-size:0.8rem;font-weight:600'>{priority}</span>")


def show_chart(chart):
    try:
        st.altair_chart(chart, width="stretch")
    except TypeError:                      # older Streamlit
        st.altair_chart(chart, use_container_width=True)


def show_df(df, **kwargs):
    try:
        st.dataframe(df, width="stretch", hide_index=True, **kwargs)
    except TypeError:
        st.dataframe(df, use_container_width=True, hide_index=True, **kwargs)


def mastery_chart(rows: list):
    df = pd.DataFrame(rows)
    chart = (alt.Chart(df).mark_bar().encode(
        x=alt.X("effective_mastery:Q", scale=alt.Scale(domain=[0, 1]), title="Effective mastery"),
        y=alt.Y("concept:N", sort="-x", title=None),
        color=alt.Color("level:N", title="Level",
                        scale=alt.Scale(domain=list(LEVEL_COLORS), range=list(LEVEL_COLORS.values()))),
        tooltip=["concept", "level", "bkt_mastery", "effective_mastery", "attempts"])
        .properties(height=max(120, 36 * len(df))))
    show_chart(chart)
