import pandas as pd
import streamlit as st

import api_client as api
from components import ui
from utils import demo_data, state
from utils.format import pct

st.title("📊 Dashboard")

if state.is_demo():
    ui.demo_notice()
    d = demo_data.DASHBOARD
else:
    d = ui.safe(api.dashboard, state.require_user())

st.subheader(f"Welcome, {d['user']['name']}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Study materials", d["n_materials"])
c2.metric("Questions answered", f"{d['n_answered']} / {d['n_questions']}")
c3.metric("Overall accuracy", pct(d["accuracy"]))
c4.metric("Concepts tracked", d["n_concepts"])

if d["n_concepts"] == 0:
    st.info("No mastery data yet. Add material, generate a practice test and answer a few questions.")
else:
    left, right = st.columns([1, 2])
    with left:
        st.markdown("**Average effective mastery**")
        st.progress(min(1.0, d["avg_effective_mastery"]), text=pct(d["avg_effective_mastery"]))
        st.markdown("**Concepts by level**")
        lv = d["levels"]
        ui.show_df(pd.DataFrame({"Level": ["Weak", "Developing", "Strong"],
                                 "Concepts": [lv.get("Weak", 0), lv.get("Developing", 0), lv.get("Strong", 0)]}))
    with right:
        st.markdown("**Weakest concepts right now**")
        for r in d["weakest"]:
            st.markdown(f"{ui.priority_badge(r['priority'])} &nbsp; **{r['concept']}** — effective mastery "
                        f"{pct(r['effective_mastery'])}, recent accuracy {pct(r['recent_accuracy'])}",
                        unsafe_allow_html=True)

st.markdown("**Recent activity**")
if d["recent"]:
    ui.show_df(pd.DataFrame(d["recent"]).rename(columns={"event": "Event", "detail": "Detail", "created_at": "When"}))
else:
    st.caption("Nothing yet.")
