"""YouTube path: transcript -> timestamped chunks -> video guidance (network call is faked)."""
from backend import ingest


def _segments():
    topics = ["photosynthesis chlorophyll sunlight light reactions oxygen water",
              "mitochondria respiration glucose energy cells ATP cellular"]
    segs, t = [], 0.0
    for topic in topics:
        for _ in range(12):
            segs.append({"text": (topic + " ") * 2, "start": t, "duration": 5.0})
            t += 5.0
    return segs


def test_chunk_segments_keep_timestamps():
    chunks = ingest.chunk_segments(_segments(), size=60)
    assert len(chunks) >= 2
    assert chunks[0]["start_sec"] == 0.0
    assert all(c["end_sec"] > c["start_sec"] for c in chunks)
    assert chunks[1]["start_sec"] >= chunks[0]["end_sec"] - 1e-6


def test_parse_youtube_id():
    assert ingest.parse_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=5") == "dQw4w9WgXcQ"
    assert ingest.parse_youtube_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert ingest.parse_youtube_id("not a url") is None


def test_video_guidance_endpoint(client, monkeypatch):
    monkeypatch.setattr(ingest, "fetch_youtube_segments", lambda vid: _segments())
    uid = client.post("/users", json={"name": "Video user"}).json()["id"]
    r = client.post("/materials/youtube", json={"user_id": uid, "url": "https://youtu.be/dQw4w9WgXcQ",
                                                "title": "Biology lecture"})
    assert r.status_code == 200 and r.json()["n_chunks"] >= 2

    from backend import recommend
    g = recommend.video_guidance(uid, "mitochondria respiration glucose")
    assert g["title"] == "Biology lecture"
    assert "&t=" in g["url"] or "?t=" in g["url"]
    assert g["start_sec"] >= 50                    # respiration is discussed in the second half
    assert len(g["range"]) == 11 and g["range"][2] == ":"
    first = recommend.video_guidance(uid, "photosynthesis chlorophyll sunlight")
    assert first["start_sec"] < 50                 # photosynthesis is discussed in the first half

    bad = client.post("/materials/youtube", json={"user_id": uid, "url": "https://example.com/nothing"})
    assert bad.status_code == 422
