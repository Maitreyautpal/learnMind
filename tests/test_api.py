"""End-to-end API test in offline mode (hash embedder, no Groq key)."""
import math

NOTES = (
    "Photosynthesis is the process by which green plants convert light energy into chemical energy. "
    "Chlorophyll inside the chloroplasts absorbs sunlight, mainly in the red and blue wavelengths. "
    "During the light reactions, water molecules are split and oxygen is released as a by-product. "
    "The energy captured is stored in molecules called ATP and NADPH. "
    "In the Calvin cycle, carbon dioxide from the air is fixed into glucose using that stored energy. "
    "Stomata are tiny pores on the leaf surface that allow carbon dioxide to enter and oxygen to leave. "
    "Respiration is the opposite process, in which cells break down glucose to release usable energy. "
    "Mitochondria are the organelles where most of this cellular respiration takes place. "
    "The overall balance between photosynthesis and respiration keeps oxygen and carbon dioxide stable. "
    "Plants therefore act as producers, and almost every food chain on Earth begins with them. "
    "Factors such as light intensity, temperature and carbon dioxide concentration control the rate of "
    "photosynthesis, and a shortage of any one of them becomes the limiting factor for the plant."
)


def _setup(client, name="Asha"):
    u = client.post("/users", json={"name": name}).json()
    r = client.post("/materials/notes", json={"user_id": u["id"], "title": "Biology notes", "text": NOTES})
    assert r.status_code == 200, r.text
    return u["id"], r.json()


def test_health(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["llm"].startswith("offline")


def test_validation_rejects_bad_data(client):
    assert client.post("/users", json={"name": ""}).status_code == 422
    assert client.post("/materials/notes", json={"user_id": 1, "title": "x", "text": "short"}).status_code == 422
    assert client.post("/practice/answer", json={"user_id": 1, "question_id": 1, "selected_idx": 9}).status_code == 422
    assert client.get("/materials/999").status_code == 404


def test_add_material_and_tutor(client):
    uid, m = _setup(client, "Tutor user")
    assert m["n_chunks"] >= 2
    r = client.post("/tutor/ask", json={"user_id": uid, "question": "Where does the Calvin cycle get carbon dioxide?"})
    body = r.json()
    assert body["mode"] == "offline" and body["sources"]
    assert "Calvin" in body["sources"][0]["text"] or "carbon dioxide" in body["answer"].lower()
    empty = client.post("/users", json={"name": "Nobody"}).json()["id"]
    assert client.post("/tutor/ask", json={"user_id": empty, "question": "anything at all?"}).json()["mode"] == "no-material"


def test_practice_and_bkt_flow(client):
    uid, m = _setup(client, "Practice user")
    gen = client.post("/practice/generate", json={"user_id": uid, "material_id": m["material_id"], "n": 6}).json()
    assert gen["created"] >= 3 and gen["mode"] == "offline"

    q = client.get("/practice/next", params={"user_id": uid}).json()["question"]
    assert "correct_idx" not in q and len(q["options"]) == 4
    first = client.post("/practice/answer", json={"user_id": uid, "question_id": q["question_id"], "selected_idx": 0}).json()
    expected = 0.65 if first["correct"] else 0.2462
    assert math.isclose(first["mastery_after"], expected, abs_tol=1e-3)
    assert math.isclose(first["mastery_before"], 0.30)

    # same question cannot be answered twice
    again = client.post("/practice/answer", json={"user_id": uid, "question_id": q["question_id"], "selected_idx": 0})
    assert again.status_code == 409

    # answer the rest correctly, using the stored correct index returned by the first call pattern
    answered = 1
    while True:
        nxt = client.get("/practice/next", params={"user_id": uid}).json()["question"]
        if nxt is None:
            break
        # discover the right answer by trying option 0..3 is impossible (one shot), so read it from the DB
        from backend import db
        right = db.get_question(nxt["question_id"])["correct_idx"]
        r = client.post("/practice/answer", json={"user_id": uid, "question_id": nxt["question_id"], "selected_idx": right}).json()
        assert r["correct"] and r["mastery_after"] > r["mastery_before"]
        answered += 1
    assert answered == gen["created"]

    mastery = client.get(f"/mastery/{uid}").json()
    assert mastery and all(0 <= r["effective_mastery"] <= 1 for r in mastery)
    assert mastery == sorted(mastery, key=lambda r: r["weakness_score"], reverse=True)

    recs = client.get(f"/recommendations/{uid}").json()
    assert recs[0]["priority"] in {"Critical", "High", "Medium", "Low"}
    assert recs[0]["study_material"]["snippet"] and recs[0]["video"] is None

    dash = client.get(f"/dashboard/{uid}").json()
    assert dash["n_answered"] == answered and dash["n_materials"] == 1 and dash["accuracy"] > 0


def test_delete_material(client):
    uid, m = _setup(client, "Delete user")
    assert client.delete(f"/materials/{uid}/{m['material_id']}").status_code == 200
    assert client.get(f"/materials/{uid}").json() == []
    assert client.delete(f"/materials/{uid}/{m['material_id']}").status_code == 404
