import streamlit as st

import api_client as api
from components import ui
from utils import state
from utils.format import LEVEL_COLORS

st.title("📝 Practice Test")

if state.is_demo():
    ui.demo_notice()
    st.info("Connect the backend to generate and take practice tests.")
    st.stop()

uid = state.require_user()
mats = ui.safe(api.materials, uid)
if not mats:
    st.info("Add some study material first.")
    st.stop()

# Reset the running test when another student is selected.
if st.session_state.get("pt_uid") != uid:
    st.session_state.update(pt_uid=uid, pt_q=None, pt_fb=None, pt_done=0, pt_right=0)

# ---------------------------------------------------------------- 1. generate
with st.expander("1. Generate practice questions from your material",
                 expanded=all(m["n_questions"] == 0 for m in mats)):
    mid = st.selectbox("Material", [m["id"] for m in mats],
                       format_func=lambda i: next(m["title"] for m in mats if m["id"] == i))
    n = st.slider("How many questions", 3, 15, 10)

    language_choice = st.selectbox(
    "Question language",
    ["Hinglish", "English", "Hindi"],
    index=0,)

    language_map = {
    "Hinglish": "hinglish",
    "English": "english",
    "Hindi": "hindi",}
    selected_language = language_map[language_choice]

    difficulty = st.selectbox(
    "Question difficulty",
    ["Medium", "Easy", "Hard"],
    index=0,)
    selected_difficulty = difficulty.lower()
    if st.button("Generate questions"):
        with st.spinner("Writing questions…"):
            res = ui.safe(api.generate,uid,mid,n,selected_language,selected_difficulty,)
        st.success(f"Created {res['created']} questions on: {', '.join(res['concepts']) or '—'}")
        if res["mode"] != "groq":
            st.info("Offline mode: simple fill-in-the-blank questions were created. Set GROQ_API_KEY in "
                    "the backend for proper LLM-written MCQs." + (f" ({res['note']})" if res.get("note") else ""))
        st.rerun()

# ------------------------------------------------------------------- 2. test
st.subheader("2. Take the adaptive test")
concepts = sorted({c for m in mats for c in m["concepts"]})
if not concepts:
    st.info("No questions yet. Generate some above.")
    st.stop()

default = st.session_state.pop("practice_focus", None)
options = ["Auto: weakest concept first"] + concepts
focus = st.selectbox("Focus", options, index=options.index(default) if default in options else 0)
concept = None if focus == options[0] else focus


def fetch():
    res = ui.safe(api.next_question, uid, concept)
    st.session_state.pt_fb = None
    st.session_state.pt_q = res["question"]
    if res["question"] is None:
        st.info(res["message"])


q, fb = st.session_state.get("pt_q"), st.session_state.get("pt_fb")

if st.session_state.pt_done:
    st.caption(f"This session: {st.session_state.pt_right} / {st.session_state.pt_done} correct")

if q is None:
    if st.button("Start / next question", type="primary"):
        fetch()
        st.rerun()
elif fb is None:
    with st.container(border=True):
        st.markdown(f"**Concept:** {q['concept']} · difficulty {q['difficulty']} "
                    f"(target {q['target_difficulty']}) · current mastery {q['current_mastery']:.2f}")
        st.markdown(f"### {q['question']}")
        picked = st.radio("Choose one answer", q["options"], index=None, key=f"opt_{q['question_id']}")
        if st.button("Submit answer", type="primary", disabled=picked is None):
            res = ui.safe(api.answer, uid, q["question_id"], q["options"].index(picked))
            st.session_state.pt_fb = {**res, "picked": picked}
            st.session_state.pt_done += 1
            st.session_state.pt_right += int(res["correct"])
            st.rerun()
else:
    with st.container(border=True):
        st.markdown(f"**Concept:** {q['concept']}")
        st.markdown(f"### {q['question']}")
        if fb["correct"]:
            st.success("Correct!")
        else:
            st.error(f"Not quite. You chose: {fb['picked']}")
        st.markdown(f"**Right answer:** {q['options'][fb['correct_idx']]}")
        if fb["explanation"]:
            st.caption(fb["explanation"])
        c1, c2 = st.columns(2)
        c1.metric("Mastery after this answer", f"{fb['mastery_after']:.2f}",
                  delta=f"{fb['mastery_after'] - fb['mastery_before']:+.2f}")
        c2.markdown(f"**Level:** <span style='color:{LEVEL_COLORS[fb['level']]}'>{fb['level']}</span>",
                    unsafe_allow_html=True)
    if st.button("Next question", type="primary"):
        fetch()
        st.rerun()
