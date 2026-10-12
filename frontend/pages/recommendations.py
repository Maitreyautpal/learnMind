import streamlit as st

import api_client as api
from components import ui
from utils import demo_data, state
from utils.format import pct

st.title("💡 Recommendations")

if state.is_demo():
    ui.demo_notice()
    recs = demo_data.RECOMMENDATIONS
else:
    recs = ui.safe(api.recommendations, state.require_user())

if not recs:
    st.info("Recommendations appear after you answer some practice questions.")
    st.stop()

st.caption("Concepts are ordered by weakness score: 0.55 × (1 − effective mastery) + 0.25 × (1 − recent "
           "accuracy) + 0.20 × forgetting.")

for i, r in enumerate(recs):
    with st.container(border=True):
        st.markdown(f"{ui.priority_badge(r['priority'])} &nbsp; **{r['concept']}** — {r['recommended_action']}",
                    unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Effective mastery", pct(r["effective_mastery"]))
        c2.metric("Recent accuracy", pct(r["recent_accuracy"]))
        c3.metric("Forgetting", pct(r["forgetting_score"]))
        c4.metric("Weakness score", f"{r['weakness_score']:.2f}")

        if r.get("study_material"):
            with st.expander(f"Study this: {r['study_material']['material_title']}"):
                st.write(r["study_material"]["snippet"])
        if r.get("video"):
            v = r["video"]
            st.link_button(f"▶ Watch {v['range']} in “{v['title']}”", v["url"])
        if not state.is_demo() and st.button("Practice this concept", key=f"prac_{i}"):
            st.session_state["practice_focus"] = r["concept"]
            st.switch_page("pages/practice_test.py")
