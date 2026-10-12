import streamlit as st

import api_client as api
from components import ui
from utils import state
from utils.format import mmss

st.title("🤖 AI Tutor")
language_choice = st.selectbox(
    "Response language",
    options=["Auto-detect", "Hinglish", "English"],
    index=0,
    help="Choose the language in which the AI Tutor should explain."
)

language_map = {
    "Auto-detect": "auto",
    "Hinglish": "hinglish",
    "English": "english",
}
selected_language = language_map[language_choice]

if state.is_demo():
    ui.demo_notice()
    st.info("Connect the backend to ask questions about your own material.")
    st.stop()

uid = state.require_user()
mats = ui.safe(api.materials, uid)
if not mats:
    st.info("Add some study material first. The tutor answers only from your material.")
    st.stop()

with st.expander("Limit the tutor to specific materials (optional)"):
    chosen = st.multiselect("Materials", [m["id"] for m in mats],
                            format_func=lambda i: next(m["title"] for m in mats if m["id"] == i))

chats = st.session_state.setdefault("chats", {})
history = chats.setdefault(uid, [])


def show(msg):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("mode"):
            st.caption(f"mode: {msg['mode']}")
        if msg.get("sources"):
            with st.expander(f"Sources ({len(msg['sources'])})"):
                for s in msg["sources"]:
                    where = f" · from {mmss(s['start_sec'])}" if s.get("start_sec") is not None else ""
                    st.markdown(f"**[{s['n']}] {s['material_title']}**{where} · similarity {s['score']}")
                    st.caption(s["text"][:500] + ("…" if len(s["text"]) > 500 else ""))


for m in history:
    show(m)

if q := st.chat_input("Ask a doubt about your material…"):
    history.append({"role": "user", "content": q})
    show(history[-1])
    with st.spinner("Searching your material…"):
        res = ui.safe(api.ask, uid, q, chosen or None, selected_language)
    history.append({"role": "assistant", "content": res["answer"],
                    "sources": res["sources"], "mode": res["mode"]})
    show(history[-1])

if history and st.button("Clear chat"):
    chats[uid] = []
    st.rerun()
