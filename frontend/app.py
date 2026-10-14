"""LearnMind frontend. Run:  streamlit run frontend/app.py"""
import streamlit as st

import api_client as api
from components import ui

st.set_page_config(page_title="LearnMind", page_icon="🧠", layout="wide")

online = api.online()
if not online and not api.is_local() and not st.session_state.get("_wake_tried"):
    st.session_state["_wake_tried"] = True
    with st.spinner("Waking up the server (free hosting sleeps when idle, up to 1 minute)..."):
        online = api.wake_up()
st.session_state["demo"] = not online

pages = [
    st.Page("pages/dashboard.py", title="Dashboard", icon="📊", default=True),
    st.Page("pages/my_learning.py", title="My Learning", icon="📚"),
    st.Page("pages/add_material.py", title="Add Material", icon="➕"),
    st.Page("pages/ai_tutor.py", title="AI Tutor", icon="🤖"),
    st.Page("pages/practice_test.py", title="Practice Test", icon="📝"),
    st.Page("pages/my_mastery.py", title="My Mastery", icon="🎯"),
    st.Page("pages/recommendations.py", title="Recommendations", icon="💡"),
]
current = st.navigation(pages)

with st.sidebar:
    st.markdown("### 🧠 LearnMind")
    if not online:
        ui.demo_badge()
        st.caption("Backend not connected.")
    else:
        # a student created in the previous run becomes the selected one
        if "_pending_user" in st.session_state:
            st.session_state["user_id"] = st.session_state.pop("_pending_user")
        users = ui.safe(api.list_users)
        if users:
            ids = [u["id"] for u in users]
            if st.session_state.get("user_id") not in ids:
                st.session_state["user_id"] = ids[0]
            st.selectbox("Student", ids, key="user_id",
                         format_func=lambda i: next(u["name"] for u in users if u["id"] == i))
        with st.form("new_student", clear_on_submit=True):
            name = st.text_input("New student name", placeholder="e.g. Maitreya")
            if st.form_submit_button("Create student") and name.strip():
                created = ui.safe(api.create_user, name.strip())
                st.session_state["_pending_user"] = created["id"]
                st.rerun()
        st.caption("Backend connected")

current.run()
