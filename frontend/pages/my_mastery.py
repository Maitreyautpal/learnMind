import pandas as pd
import streamlit as st

import api_client as api
from components import ui
from utils import demo_data, state

st.title("🎯 My Mastery")

if state.is_demo():
    ui.demo_notice()
    rows = demo_data.MASTERY
else:
    rows = ui.safe(api.mastery, state.require_user())

if not rows:
    st.info("No mastery data yet. Answer some practice questions first.")
    st.stop()

st.caption("BKT updates the mastery of each concept after every answer. Effective mastery also lowers it "
           "for concepts you have not practised for a while (forgetting).")
ui.mastery_chart(rows)

df = pd.DataFrame(rows)[["concept", "level", "bkt_mastery", "effective_mastery", "recent_accuracy",
                         "attempts", "interaction_gap", "forgetting_score", "weakness_score"]]
df.columns = ["Concept", "Level", "BKT mastery", "Effective mastery", "Recent accuracy",
              "Attempts", "Answers since practised", "Forgetting", "Weakness score"]
ui.show_df(df, column_config={
    "BKT mastery": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
    "Effective mastery": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
    "Recent accuracy": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
})
