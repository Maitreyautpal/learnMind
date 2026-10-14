import streamlit as st

import api_client as api
from components import ui
from utils import state

st.title("➕ Add Material")

if state.is_demo():
    ui.demo_notice()
    st.info("Connect the backend to add PDFs, notes or YouTube videos.")
    st.stop()

uid = state.require_user()
st.caption("Your material is split into chunks, embedded and indexed so the AI Tutor and the practice "
           "test can use it.")


def done(res):
    st.success(f"Added “{res['title']}”: {res['n_chunks']} chunks indexed. "
               "You can now ask the AI Tutor or generate a practice test.")


tab_pdf, tab_notes, tab_yt = st.tabs(["📄 PDF", "📝 Notes", "▶️ YouTube"])

with tab_pdf:
    f = st.file_uploader("Choose a PDF (text-based, not a scan)", type="pdf")
    t = st.text_input("Title (optional)", key="pdf_title")
    if st.button("Add PDF", disabled=f is None):
        with st.spinner("Reading, chunking and indexing…"):
            done(ui.safe(api.add_pdf, uid, f.name, f.getvalue(), t.strip() or None))

with tab_notes:
    nt = st.text_input("Title", key="notes_title")
    body = st.text_area("Paste your notes", height=260, key="notes_body")
    if st.button("Add notes", disabled=not (nt.strip() and len(body.strip()) >= 50)):
        with st.spinner("Chunking and indexing…"):
            done(ui.safe(api.add_notes, uid, nt.strip(), body.strip()))
    st.caption("Notes need at least 50 characters.")


with tab_yt:
    url = st.text_input("YouTube link", placeholder="https://www.youtube.com/watch?v=...")
    yt = st.text_input("Title (optional)", key="yt_title")
    st.caption("The video needs captions. The transcript is kept with its timestamps so a weak "
               "concept can be linked to the exact part of the video. If automatic fetching "
               "fails, copy the transcript and add it in the Notes tab.")
    if st.button("Add video", disabled=not url.strip()):
        with st.spinner("Fetching transcript and indexing..."):
            done(ui.safe(api.add_youtube, uid, url.strip(), yt.strip() or None))
