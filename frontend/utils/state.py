import streamlit as st


def is_demo() -> bool:
    return bool(st.session_state.get("demo", False))


def current_user_id():
    return st.session_state.get("user_id")


def require_user() -> int:
    """Return the selected student id, or stop the page with a hint."""
    uid = current_user_id()
    if uid is None:
        st.info("Pick or create a student in the sidebar to begin.")
        st.stop()
    return int(uid)
