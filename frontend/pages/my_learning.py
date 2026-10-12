import streamlit as st

import api_client as api
from components import ui
from utils import demo_data, state

st.title("📚 My Learning")

if state.is_demo():
    ui.demo_notice()
    mats, uid = demo_data.MATERIALS, None
else:
    uid = state.require_user()
    mats = ui.safe(api.materials, uid)

if not mats:
    st.info("You have not added any study material yet. Go to **Add Material**.")

ICON = {"pdf": "📄", "notes": "📝", "youtube": "▶️"}
for m in mats:
    with st.expander(f"{ICON.get(m['kind'], '📄')} {m['title']}  ·  {m['kind']}", expanded=False):
        c1, c2 = st.columns(2)
        c1.metric("Chunks indexed", m["n_chunks"])
        c2.metric("Practice questions", m["n_questions"])
        if m["concepts"]:
            st.markdown("**Concepts:** " + ", ".join(m["concepts"]))
        else:
            st.caption("No practice questions yet. Generate them on the Practice Test page.")
        if uid is not None and st.button("Delete this material", key=f"del_{m['id']}"):
            ui.safe(api.delete_material, uid, m["id"])
            st.rerun()
