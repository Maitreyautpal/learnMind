"""Sample data shown in Demo mode (backend not connected). Not real learner data."""

MASTERY = [
    {"concept": "Calvin Cycle", "bkt_mastery": 0.24, "effective_mastery": 0.22, "forgetting_score": 0.08,
     "interaction_gap": 8, "recent_accuracy": 0.0, "attempts": 5, "correct": 1, "level": "Weak",
     "weakness_score": 0.78, "priority": "Critical", "recommended_action": "Relearn concept from basics"},
    {"concept": "Light Reactions", "bkt_mastery": 0.46, "effective_mastery": 0.44, "forgetting_score": 0.05,
     "interaction_gap": 5, "recent_accuracy": 0.4, "attempts": 6, "correct": 3, "level": "Weak",
     "weakness_score": 0.55, "priority": "High", "recommended_action": "Review concept and practice more"},
    {"concept": "Stomata", "bkt_mastery": 0.66, "effective_mastery": 0.65, "forgetting_score": 0.01,
     "interaction_gap": 1, "recent_accuracy": 0.6, "attempts": 5, "correct": 3, "level": "Developing",
     "weakness_score": 0.37, "priority": "Medium", "recommended_action": "Practice targeted questions"},
    {"concept": "Respiration", "bkt_mastery": 0.93, "effective_mastery": 0.92, "forgetting_score": 0.02,
     "interaction_gap": 2, "recent_accuracy": 1.0, "attempts": 6, "correct": 6, "level": "Strong",
     "weakness_score": 0.06, "priority": "Low", "recommended_action": "Continue normal practice"},
]

DASHBOARD = {
    "user": {"id": 0, "name": "Demo student"},
    "n_materials": 2, "n_questions": 24, "n_answered": 22, "accuracy": 0.64, "n_concepts": 4,
    "avg_effective_mastery": 0.56, "levels": {"Weak": 2, "Developing": 1, "Strong": 1},
    "weakest": MASTERY[:3],
    "recent": [
        {"event": "answer", "detail": "Calvin Cycle: wrong (0.31 -> 0.24)", "created_at": "sample"},
        {"event": "tutor_question", "detail": "Where does the Calvin cycle get carbon dioxide?", "created_at": "sample"},
        {"event": "material_added", "detail": "pdf: Biology notes (6 chunks)", "created_at": "sample"},
    ],
}

MATERIALS = [
    {"id": 1, "title": "Biology notes (sample)", "kind": "pdf", "n_chunks": 6, "n_questions": 12,
     "concepts": ["Calvin Cycle", "Light Reactions", "Stomata"]},
    {"id": 2, "title": "Respiration lecture (sample)", "kind": "youtube", "n_chunks": 4, "n_questions": 12,
     "concepts": ["Respiration"]},
]

RECOMMENDATIONS = [
    {**MASTERY[0],
     "study_material": {"material_title": "Biology notes (sample)",
                        "snippet": "In the Calvin cycle, carbon dioxide from the air is fixed into glucose "
                                   "using the energy stored in ATP and NADPH..."},
     "video": {"title": "Respiration lecture (sample)", "url": "https://www.youtube.com/", "range": "08:42-11:15"}},
    {**MASTERY[1], "study_material": None, "video": None},
]
